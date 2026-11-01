#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""招标文件解码器：把评审办法拆成「分数地图 + 废标红线 + 隐性偏好」三张清单。

设计原则：
1. 只抽取文件里写出来的东西，抽不到就标 未量化，绝不猜分值。
2. 每条结论带来源行号，方便人工回原文核对。
3. 分类（客观/主观/门槛）是启发式判断，统一标 [推测]，由人复核。

用法：
    python rfp_decode.py 招标文件.txt
    python rfp_decode.py 招标文件.txt --out ./out --total 100
    cat 招标文件.txt | python rfp_decode.py -
"""

import argparse
import json
import re
import sys
from pathlib import Path

# ---------- 词表 ----------

# 门槛类：不满足即出局，写作无法改变
GATE_WORDS = ["资格", "资质", "注册资金", "注册资本", "营业执照", "许可证",
              "认证证书", "社保", "纳税", "信用中国", "失信", "行贿犯罪",
              "联合体", "分包", "法定代表人"]

# 客观类：靠材料说话，写作只能影响呈现顺序
OBJECTIVE_WORDS = ["报价", "价格分", "业绩", "案例", "同类项目", "合同",
                   "证书", "资质等级", "奖项", "荣誉", "专利", "著作权",
                   "人员", "职称", "注册建造师", "项目经理", "财务报表",
                   "注册资本", "纳税额", "信用等级", "本地化", "注册地"]

# 主观类：靠写作与论证争取
SUBJECTIVE_WORDS = ["方案", "理解", "认识", "思路", "措施", "方法", "组织",
                    "实施", "计划", "进度", "质量", "保障", "服务", "培训",
                    "应急", "风险", "创新", "优化", "建议", "承诺", "管理",
                    "技术路线", "架构", "运维", "售后", "响应", "演示", "答辩"]

# 废标红线
REDLINE_WORDS = ["否决", "无效投标", "废标", "不予受理", "拒绝其投标",
                 "资格审查不合格", "未实质性响应", "重大偏离", "取消投标资格"]

# 实质性条款标记
SUBSTANTIVE_MARKERS = ["★", "▲", "*", "＊"]

# 隐性偏好信号词
PREFERENCE_WORDS = ["本地化", "本地", "驻场", "现场", "同类项目", "类似业绩",
                    "自主知识产权", "国产化", "信创", "等保", "密评",
                    "7×24", "7*24", "2小时", "4小时", "24小时", "响应时间",
                    "免费", "质保", "培训", "巡检", "应急演练", "数据迁移"]

# 名字里允许出现数字（"三级资质""2025年业绩""7×24小时"都是常见评分项名），
# 但整行必须以「数字+分」结尾，避免把正文里的"3分钟"当成分值。
SCORE_LINE = re.compile(
    r"^(?P<name>.{2,60}?)[\s\.、:：\-—]{0,3}[（(]?\s*(?P<score>\d{1,3}(?:\.\d)?)\s*分[）)]?\s*$"
)
SCORE_INLINE = re.compile(
    r"(?P<name>[^\d，。；;:：]{2,30})[（(]?\s*(?:满分|共|合计)?\s*(?P<score>\d{1,3}(?:\.\d)?)\s*分[）)]?"
)
WEIGHT_INLINE = re.compile(
    r"(?P<name>[^\d，。；;:：]{2,30})[（(]?\s*(?P<score>\d{1,3}(?:\.\d)?)\s*%"
)


def read_text(src: str) -> str:
    if src == "-":
        return sys.stdin.read()
    p = Path(src)
    if not p.exists():
        raise SystemExit(f"文件不存在: {p}")
    raw = p.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gb18030", "utf-16"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise SystemExit("无法识别文件编码，请另存为 UTF-8 后重试")


def hit_any(text: str, words) -> list:
    return [w for w in words if w in text]


def classify(name: str) -> tuple:
    """返回 (类型, 可争取度, 理由)。类型仅作启发式判断。"""
    gate = hit_any(name, GATE_WORDS)
    obj = hit_any(name, OBJECTIVE_WORDS)
    subj = hit_any(name, SUBJECTIVE_WORDS)

    if "报价" in name or "价格" in name:
        return "客观", 0.35, "价格分由报价决定，写作只能影响呈现"
    if gate and not subj:
        return "门槛", 0.0, f"命中门槛词：{'、'.join(gate[:3])}"
    if subj and not obj:
        return "主观", 0.9, f"命中主观词：{'、'.join(subj[:3])}"
    if obj and not subj:
        return "客观", 0.45, f"命中客观词：{'、'.join(obj[:3])}"
    if obj and subj:
        return "混合", 0.6, f"同时命中：{'、'.join((subj + obj)[:3])}"
    return "未定", 0.5, "无明确关键词，需人工判定"


ENUM_PREFIX = re.compile(
    r"^\s*(?:[（(]?\d{1,2}[）)]|\d{1,2}[\.、]|[一二三四五六七八九十]{1,3}[、\.）)])\s*"
)


def strip_enum(s: str) -> str:
    """去掉行首编号（1. / （1） / 一、），否则名字里的数字会打乱分值匹配。"""
    prev = None
    while prev != s:
        prev = s
        s = ENUM_PREFIX.sub("", s)
    return s


HEADER_WORDS = {"评分标准", "评分办法", "评审办法", "评分细则", "评标办法", "总分",
                "合计", "共计", "分值", "评审因素", "评分项", "得分"}


def clean_name(name: str) -> str:
    n = name.strip(" ·-—:：、）)")
    n = re.sub(r"[（(]\s*(?:满分|共|合计|计|总分)?\s*$", "", n).strip(" ·-—:：、）)")
    return n


def is_header(name: str) -> bool:
    if name in HEADER_WORDS:
        return True
    if any(w in name for w in ("满分", "总分", "合计", "共计")):
        return True
    return len(name) < 2


def extract_scores(lines):
    items = []
    for idx, line in enumerate(lines, start=1):
        s = line.strip()
        if not s or len(s) > 120:
            continue
        s = strip_enum(s)
        m = SCORE_LINE.match(s)
        score = None
        name = None
        if m:
            name, score = clean_name(m.group("name")), float(m.group("score"))
        else:
            m2 = SCORE_INLINE.search(s)
            if m2 and any(k in s for k in ("分", "评分", "得分")):
                name, score = clean_name(m2.group("name")), float(m2.group("score"))
        if name and is_header(name):
            continue
        if name and score is not None and 0 < score <= 100:
            kind, weight, why = classify(name)
            items.append({
                "line": idx,
                "item": name[:40],
                "max_score": score,
                "type": kind,
                "winnable": weight,
                "reason": why,
                "source": s[:80],
                "evidence": "[事实]分值来自原文",
            })
    return items


def extract_weight_percent(lines):
    """有些文件用权重百分比而非分值。"""
    out = []
    for idx, line in enumerate(lines, start=1):
        s = line.strip()
        if not s or "分" in s:
            continue
        m = WEIGHT_INLINE.search(s)
        if m:
            out.append({"line": idx, "item": m.group("name").strip(" ·-—:：")[:40],
                        "weight_percent": float(m.group("score")), "source": s[:80]})
    return out


def extract_redlines(lines):
    out = []
    for idx, line in enumerate(lines, start=1):
        s = line.strip()
        if not s:
            continue
        hits = hit_any(s, REDLINE_WORDS)
        marks = [m for m in SUBSTANTIVE_MARKERS if m in s]
        if hits or marks:
            level = "阻断" if hits else "实质性条款"
            out.append({
                "line": idx,
                "level": level,
                "marker": "".join(marks),
                "text": s[:160],
                "hit": "、".join(hits) if hits else "带实质性标记",
            })
    return out


def extract_preferences(lines):
    counter = {}
    for idx, line in enumerate(lines, start=1):
        for w in PREFERENCE_WORDS:
            if w in line:
                counter.setdefault(w, []).append(idx)
    out = []
    for w, locs in sorted(counter.items(), key=lambda kv: -len(kv[1])):
        out.append({"signal": w, "count": len(locs), "lines": locs[:8],
                    "note": "[推断] 反复出现通常意味着评审会看这一项，需在方案中有对应段落"})
    return out


def build_report(items, weights, redlines, prefs, total_hint):
    total = sum(i["max_score"] for i in items)
    winnable = sum(i["max_score"] * i["winnable"] for i in items)
    subj = sum(i["max_score"] for i in items if i["type"] in ("主观", "混合"))
    gate = sum(i["max_score"] for i in items if i["type"] == "门槛")

    lines = ["# 分数地图", ""]
    lines.append(f"- 抓到的评分项：**{len(items)}** 条，分值合计 **{total:g}** 分")
    if total_hint and abs(total - total_hint) > 0.5:
        lines.append(f"- ⚠️ 与满分 {total_hint:g} 分不一致，差 {total_hint - total:g} 分。"
                     f"常见原因：分值分散在跨页表格、或含未量化的定性项。请回原文补齐。")
    lines.append(f"- 主观可写分（写作能影响的）：**{subj:g}** 分，占 {pct(subj, total)}")
    lines.append(f"- 门槛相关：**{gate:g}** 分（不满足即出局，不是加分项）")
    lines.append(f"- 可争取分（分值×可争取度 加权）：**{winnable:.1f}** / {total:g}")
    lines.append("")
    lines.append("| # | 评分项 | 满分 | 类型 | 可争取度 | 判定依据 | 行号 |")
    lines.append("|---|---|---|---|---|---|---|")
    for i, it in enumerate(items, 1):
        lines.append(f"| {i} | {it['item']} | {it['max_score']:g} | {it['type']} | "
                     f"{it['winnable']:.2f} | {it['reason']} | {it['line']} |")
    lines.append("")
    lines.append("> 类型与可争取度是启发式判断，请按原文复核。分值来自原文，不猜。")

    if weights:
        lines += ["", "## 以权重百分比表述的条目", "",
                  "| 条目 | 权重 | 行号 |", "|---|---|---|"]
        for w in weights:
            lines.append(f"| {w['item']} | {w['weight_percent']:g}% | {w['line']} |")

    lines += ["", "# 废标红线", ""]
    if not redlines:
        lines.append("未自动命中否决类表述。**这不等于没有红线**——请人工通读「投标人须知」与「评标办法」中的否决条款。")
    else:
        lines.append(f"命中 {len(redlines)} 处，其中否决类 "
                     f"{sum(1 for r in redlines if r['level'] == '阻断')} 处。")
        lines += ["", "| 级别 | 标记 | 原文（截断） | 行号 |", "|---|---|---|---|"]
        for r in redlines[:40]:
            lines.append(f"| {r['level']} | {r['marker']} | {r['text']} | {r['line']} |")
        if len(redlines) > 40:
            lines.append(f"| … | | 其余 {len(redlines) - 40} 处见 JSON | |")

    lines += ["", "# 隐性偏好（推断）", ""]
    if not prefs:
        lines.append("未命中常见偏好信号词。")
    else:
        lines += ["| 信号 | 出现次数 | 行号 | 含义 |", "|---|---|---|---|"]
        for p in prefs[:15]:
            lines.append(f"| {p['signal']} | {p['count']} | {p['lines']} | {p['note']} |")

    lines += ["", "## 下一步", ""]
    if total:
        if subj / total < 0.4:
            lines.append("- 主观可分占比低于 40%：这份标书靠写作能动的空间有限，"
                         "先把报价策略和材料完备性做扎实，再谈叙事。")
        else:
            lines.append("- 主观可分占比够用：按分值从高到低排章节，逐项落任务书。")
    lines.append("- 分值合计与满分不符时，先补齐评分表，再算可争取分。")
    return "\n".join(lines), {
        "total_score": total, "subjective_score": subj, "gate_score": gate,
        "winnable_score": round(winnable, 2), "item_count": len(items),
    }


def pct(a, b):
    return f"{(a / b * 100):.0f}%" if b else "n/a"


def main():
    ap = argparse.ArgumentParser(description="招标文件解码：分数地图 / 废标红线 / 隐性偏好")
    ap.add_argument("source", help="招标文件路径，或 - 表示从标准输入读取")
    ap.add_argument("--out", default=".", help="输出目录（默认当前目录）")
    ap.add_argument("--total", type=float, default=None, help="满分，用于校验抓取是否完整")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    text = read_text(args.source)
    lines = text.splitlines()

    items = extract_scores(lines)
    weights = extract_weight_percent(lines)
    redlines = extract_redlines(lines)
    prefs = extract_preferences(lines)

    md, stats = build_report(items, weights, redlines, prefs, args.total)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "分数地图.md").write_text(md, encoding="utf-8")
    (out / "分数地图.json").write_text(
        json.dumps({"stats": stats, "items": items, "weights": weights,
                    "redlines": redlines, "preferences": prefs},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    print(md.split("# 废标红线")[0])
    print(f"\n已写出：{out/'分数地图.md'}")
    print(f"已写出：{out/'分数地图.json'}")
    print(f"废标红线 {len(redlines)} 处，偏好信号 {len(prefs)} 个（详见 md）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
