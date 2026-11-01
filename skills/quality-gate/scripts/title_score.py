#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
title_score.py — 公众号标题批量打分（朱笔 / quality-gate 技能）

把「感觉这个标题不错」换成六维评分 + 排序 + 短板提示。
纯标准库，不联网。

用法:
    python title_score.py 标题1 标题2 标题3
    python title_score.py --file titles.txt        # 一行一个
    python title_score.py --file titles.txt --top 3
    python title_score.py --json --file titles.txt

输入约定:
    标题里可以用 "/" 分成主标题与副标题（公众号标题常见两段式），
    打分时会分别计算主标与整体长度。
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict

# ---------------------------------------------------------------- 词表

# 具体锚点：数字、量词、专名标记
NUM_RE = re.compile(r"\d")
NUM_GROUP_RE = re.compile(r"\d+")
CN_NUM_RE = re.compile(r"[零一二三四五六七八九十百千万亿两]{1,4}(?=[个张页元年月日岁块份人天篇次条台本件])")
PROPER_RE = re.compile(r"[「“《][^」”》]{1,15}[」”》]")
# 具体名词提示：地名/机构/平台类常见后缀（启发式，命中即视为有可抓的实体）
CONCRETE_RE = re.compile(
    r"(小学|中学|大学|附中|校区|市|区|县|镇|街|班|年级|学校|医院|公司|"
    r"教育局|考试院|中考|高考|考研|公务员|手机|微信|抖音|小红书|B站|淘宝)"
)

# 反差张力
CONTRAST_RE = re.compile(
    r"(但|却|反而|只|才|竟|居然|不是|并不|不到|越|一边|同一|"
    r"连.{0,10}(都|也)|一个.{0,20}一个|从.{0,6}到)"
)

# 留白杀手：把结论写进标题，读者点开的动机被提前用完
CONCLUSION_WORDS = [
    "应该", "必须", "一定要", "原来", "其实", "答案", "关键", "本质", "真相",
    "原因", "如何", "怎样", "怎么办", "三个办法", "五个方法", "方法", "攻略",
    "技巧", "指南", "建议", "诀窍", "秘诀", "教你", "告诉",
]

# 抽象名词：读者抓不住画面
ABSTRACT_WORDS = [
    "底层逻辑", "认知", "思维", "格局", "价值", "意义", "问题", "根源",
    "方式", "路径", "维度", "体系", "生态", "势能", "能力", "逻辑",
]

# 标题党与合规风险
CLICKBAIT = [
    "震惊", "惊呆", "吓人", "必看", "速看", "重磅", "全网", "疯传", "沸腾",
    "刚刚", "紧急", "最高级", "第一", "绝对", "100%", "史上最", "千万",
    "不看后悔", "删前速看", "内幕",
]

MAX = {
    "具体锚点": 20,
    "反差张力": 15,
    "留白": 20,
    "长度": 15,
    "抽象程度": 10,
    "合规风险": 20,
}


@dataclass
class TitleScore:
    title: str
    main: str = ""
    scores: dict = field(default_factory=dict)
    total: float = 0.0
    weak: str = ""
    strong: str = ""
    notes: list = field(default_factory=list)


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def cjk_len(s):
    return len(re.sub(r"\s", "", s))


def score_one(title):
    title = title.strip()
    ts = TitleScore(title=title)
    main = title.split("/")[0].strip()
    ts.main = main
    n = cjk_len(title)

    # 1) 具体锚点
    anchors = 0
    if NUM_RE.search(title):
        anchors += 1
    if CN_NUM_RE.search(title):
        anchors += 1
    if PROPER_RE.search(title):
        anchors += 1
    if CONCRETE_RE.search(title):
        anchors += 1
    s_anchor = min(20, anchors * 6)
    if anchors >= 3:
        s_anchor = 20

    # 2) 反差张力
    contrasts = len(set(CONTRAST_RE.findall(title)))
    # 数字落差：标题里出现两个以上不同数量，本身就是反差
    nums = set(NUM_GROUP_RE.findall(title)) | set(CN_NUM_RE.findall(title))
    if len(nums) >= 2:
        contrasts += 1
    s_contrast = clamp(contrasts * 6, 0, 15)

    # 3) 留白：结论词越多，空位越小
    hits_concl = [w for w in CONCLUSION_WORDS if w in title]
    s_space = clamp(20 - len(hits_concl) * 8, 0, 20)
    if "？" in title or "?" in title:
        # 问句式标题本身是留白，但如果同时给了答案（"为什么X？因为Y"）反而扣
        if hits_concl:
            s_space = clamp(s_space - 6, 0, 20)
        else:
            s_space = clamp(s_space + 4, 0, 20)

    # 4) 长度：主标 10—24 字最舒服，整体不超过 34
    mn = cjk_len(main)
    if mn <= 8:
        s_len = 6
    elif mn <= 24:
        s_len = 15
    elif mn <= 30:
        s_len = 9
    else:
        s_len = 3
    if n > 34:
        s_len = max(0, s_len - 5)

    # 5) 抽象程度
    hits_abs = [w for w in ABSTRACT_WORDS if w in title]
    s_abs = clamp(10 - len(hits_abs) * 5, 0, 10)

    # 6) 合规风险
    hits_cb = [w for w in CLICKBAIT if w in title]
    s_risk = clamp(20 - len(hits_cb) * 10, 0, 20)

    ts.scores = {
        "具体锚点": s_anchor,
        "反差张力": s_contrast,
        "留白": s_space,
        "长度": s_len,
        "抽象程度": s_abs,
        "合规风险": s_risk,
    }
    ts.total = round(sum(ts.scores.values()), 1)

    # 强项 / 短板
    ratios = {k: v / MAX[k] for k, v in ts.scores.items()}
    lo = min(ratios.values())
    hi = max(ratios.values())
    ts.weak = min(ratios, key=ratios.get) if lo < 0.98 else "—"
    ts.strong = max(ratios, key=ratios.get) if hi > 0.1 else "—"

    if anchors == 0:
        ts.notes.append("没有可抓的具体物：补一个数字、价格、日期、地名或校名。")
    if hits_concl:
        ts.notes.append("结论进了标题：" + "、".join(hits_concl[:3]) + "，把答案删掉，留空位。")
    if hits_abs:
        ts.notes.append("抽象词：" + "、".join(hits_abs[:3]) + "，换成读者能拍到的东西。")
    if hits_cb:
        ts.notes.append("标题党风险词：" + "、".join(hits_cb[:3]) + "，平台审核与读者信任双输。")
    if contrasts == 0:
        ts.notes.append("没有反差：找两个极端值或一个反常识的动作。")
    if mn > 30:
        ts.notes.append(f"主标 {mn} 字，手机上会被截断，压到 24 字以内。")

    return ts


def render(scores, top=0):
    ranked = sorted(scores, key=lambda x: x.total, reverse=True)
    if top:
        ranked = ranked[:top]
    L = []
    L.append(f"{'排名':<4}{'分数':<7}{'短板':<10}{'强项':<10}标题")
    L.append("-" * 74)
    for i, ts in enumerate(ranked, 1):
        L.append(f"{i:<4}{ts.total:<7}{ts.weak:<10}{ts.strong:<10}{ts.title}")
    L.append("-" * 74)
    for i, ts in enumerate(ranked, 1):
        detail = " ".join(f"{k}{v}" for k, v in ts.scores.items())
        L.append(f"[{i}] {ts.total} 分  {detail}")
        for note in ts.notes:
            L.append(f"     → {note}")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="公众号标题六维打分")
    ap.add_argument("titles", nargs="*", help="待打分标题，可多个")
    ap.add_argument("--file", help="从文件读取，一行一个标题")
    ap.add_argument("--top", type=int, default=0, help="只显示前 N 个")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    items = list(args.titles)
    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                items += [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
        except OSError as e:
            print(f"读取失败：{e}", file=sys.stderr)
            sys.exit(2)

    if not items:
        print("没有输入标题。用法：python title_score.py 标题1 标题2", file=sys.stderr)
        sys.exit(2)

    scores = [score_one(t) for t in items]
    if args.json:
        print(json.dumps([asdict(s) for s in sorted(scores, key=lambda x: -x.total)],
                         ensure_ascii=False, indent=2))
    else:
        print(render(scores, args.top))


if __name__ == "__main__":
    main()
