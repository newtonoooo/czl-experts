#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
topic_score.py — 选题打分与查重（朱笔 / topic-radar 技能）

给 5 个候选选题打分排序，并检查它们是否互相重复。
解决的问题：模型一口气生成 5 个选题，往往 3 个是同义反复，用户等于只拿到 2 个选择。

用法:
    python topic_score.py topics.json
    python topic_score.py topics.json --top 5
    python topic_score.py topics.json --json

输入格式（JSON 数组）:
[
  {
    "title": "2027 成都中考体育分值调整",
    "angle": "分值涨了，但选考科目的训练周期没变，这才是坑",
    "type": "热点",
    "evidence": "官方文件 2026-09 发布，第 3 条；可查证",
    "audience_fit": 5,
    "window": "7天"
  }
]
type: 热点 / 常销 / 争议 / 骨架
window: 7天 / 30天 / 长期（可选，热点题必填）
audience_fit: 1—5，选题与目标读者的贴合度（自评）
"""

import argparse
import json
import re
import sys

NUM = re.compile(r"\d")
# 中文数量词：量词表要覆盖"三项/两种/几条/三门"这类选择题常见说法，
# 漏了量词会把"三项选哪一项"误判成"没有具体锚点"（v3.0 开发时踩过）
CN_NUM = re.compile(
    r"[零一二三四五六七八九十百千万两]{1,3}"
    r"(?=[个年月日岁块份人天篇次条所校科分项门种类步张届名位组场套期本页章])"
)
# 明确的选择指向：指向具体选项，本身就是"具体"的一种
CHOICE = re.compile(r"(哪一|哪个|哪种|哪类|几条|几类|怎么选|选哪|该不该|要不要|值不值)")
PLACE = re.compile(r"(成都|四川|重庆|北京|上海|广州|深圳|杭州|武汉|西安|南京|绵阳|德阳|眉山|乐山|"
                   r"中考|高考|小学|初中|高中|大学|附中|校区|教育局|考试院)")
# 具体动作与场景，比"如何/怎样"更像一个能写的故事
CONCRETE = re.compile(r"(调整|取消|新增|缩招|扩招|涨价|降价|停办|合并|拆分|改名|延期|提前|"
                      r"公布|发布|退费|收费|报名|录取|摇号|划片|分班|转学|复读)")
# 平铺直叙的标题模板（不是错，但缺少张力）
FLAT = re.compile(r"^(如何|怎样|怎么|为什么|浅谈|关于|解读|分析|一文|全面|详解)")
CONTRAST = re.compile(r"(但|却|反而|只|才|竟|不是|并不|不到|越|其实|真相|没那么)")

MAX = {"具体性": 25, "角度张力": 25, "时机": 20, "可写性": 20, "受众贴合": 10}


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def bigrams(s):
    s = re.sub(r"[\s\W]+", "", s)
    return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) > 1 else {s}


def similarity(a, b):
    A, B = bigrams(a), bigrams(b)
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def score_one(t):
    title = (t.get("title") or "").strip()
    angle = (t.get("angle") or "").strip()
    typ = (t.get("type") or "").strip()
    evidence = (t.get("evidence") or "").strip()
    fit = t.get("audience_fit") or 3
    window = (t.get("window") or "").strip()
    text = title + angle

    scores = {}
    notes = []

    # 1 具体性：有没有可抓的锚点
    s = 0
    if NUM.search(text) or CN_NUM.search(text):
        s += 9
    if PLACE.search(text):
        s += 8
    if CONCRETE.search(text):
        s += 8
    if CHOICE.search(text):
        s += 5
    # 全是抽象词，扣分
    if re.search(r"(底层逻辑|认知|思维|格局|价值|意义|体系|生态)", text):
        s = max(0, s - 6)
        notes.append("用了抽象词，读者抓不住画面")
    scores["具体性"] = min(25, s)

    # 2 角度张力
    s = 6
    if CONTRAST.search(angle) or CONTRAST.search(title):
        s += 11
    if typ == "争议":
        s += 5
    if FLAT.match(title):
        s -= 8
        notes.append("标题是平铺模板（如何/浅谈/解读），缺一个钩子")
    if len(angle) >= 12:
        s += 4          # 角度写得出来，说明想清楚了
    else:
        notes.append("角度这句太短，等于没说清这篇要讲什么")
    scores["角度张力"] = clamp(s, 0, 25)

    # 3 时机：热点看窗口，常销不看
    if typ == "热点":
        s = 20 if window in ("7天", "3天", "当天") else (14 if window == "30天" else 10)
        if not window:
            s = 10
            notes.append("热点题没标时间窗，容易过期")
    elif typ == "常销":
        s = 16          # 常销稳定，略低于新鲜热点
    elif typ == "争议":
        s = 15
    else:
        s = 12
    scores["时机"] = s

    # 4 可写性：素材够不够
    s = 6
    if len(evidence) >= 10:
        s += 8
    if NUM.search(evidence) or re.search(r"(文件|公告|通知|第\d+条|数据|样本)", evidence):
        s += 6
    if not evidence:
        notes.append("没写素材来源，写的时候会卡")
    scores["可写性"] = min(20, s)

    # 5 受众贴合
    scores["受众贴合"] = clamp(int(fit) * 2, 2, 10)

    total = round(sum(scores.values()), 1)
    weak = min(scores, key=lambda k: scores[k] / MAX[k])
    return {"title": title, "type": typ, "scores": scores, "total": total,
            "weak": weak, "notes": notes}


def main():
    ap = argparse.ArgumentParser(description="选题打分与查重")
    ap.add_argument("path", help="选题 JSON 文件，或 - 从标准输入读")
    ap.add_argument("--top", type=int, default=0, help="只显示前 N 个")
    ap.add_argument("--dup", type=float, default=0.45, help="重复判定阈值，默认 0.45")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    try:
        raw = sys.stdin.read() if args.path == "-" else open(args.path, "r", encoding="utf-8-sig").read()
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as e:
        print(f"读取选题失败：{e}", file=sys.stderr)
        sys.exit(2)

    if not isinstance(data, list) or not data:
        print("需要非空的 JSON 数组", file=sys.stderr)
        sys.exit(2)
    if len(data) < 2:
        print("至少给 2 个选题才能比较", file=sys.stderr)
        sys.exit(2)

    results = [score_one(t) for t in data]

    # 两两查重
    dups = []
    for i in range(len(results)):
        for j in range(i + 1, len(results)):
            sim = similarity(results[i]["title"] + results[i].get("angle", ""),
                             results[j]["title"] + results[j].get("angle", ""))
            sim2 = similarity(results[i]["title"], results[j]["title"])
            if max(sim, sim2) >= args.dup:
                dups.append((i, j, round(max(sim, sim2), 2)))

    # 类型分布
    types = {}
    for t in data:
        k = (t.get("type") or "未标").strip()
        types[k] = types.get(k, 0) + 1

    ranked = sorted(results, key=lambda x: -x["total"])
    if args.top:
        ranked = ranked[:args.top]

    if args.json:
        print(json.dumps({"ranked": ranked, "duplicates": dups, "types": types},
                         ensure_ascii=False, indent=2))
    else:
        print("=" * 56)
        print("选题打分")
        print("=" * 56)
        print(f"{'#':<3}{'分':<7}{'类型':<6}{'短板':<8}标题")
        print("-" * 56)
        for i, r in enumerate(ranked, 1):
            print(f"{i:<3}{r['total']:<7}{r['type'] or '—':<6}{r['weak']:<8}{r['title'][:32]}")
        print("-" * 56)
        for i, r in enumerate(ranked, 1):
            d = " ".join(f"{k}{v}" for k, v in r["scores"].items())
            print(f"[{i}] {r['total']} 分  {d}")
            for n in r["notes"]:
                print(f"     → {n}")
        if dups:
            print("-" * 56)
            print("⚠ 选题重复（用户拿到的不是 5 个选择）")
            for i, j, s in dups:
                print(f"   · 「{results[i]['title'][:18]}」 ↔ 「{results[j]['title'][:18]}」  相似度 {s}")
        if types:
            print("-" * 56)
            print("类型分布：" + "、".join(f"{k}{v}个" for k, v in types.items()))
            if len(types) == 1 and len(data) >= 4:
                print("   ⚠ 五个选题全是一个类型，读者会觉得你没换角度")
        print("=" * 56)

    sys.exit(0 if not dups else 1)


if __name__ == "__main__":
    main()
