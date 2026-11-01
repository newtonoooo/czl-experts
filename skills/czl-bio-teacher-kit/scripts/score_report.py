#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""score_report.py — 班级成绩统计与题目质量分析（纯标准库，无需安装依赖）

输入：CSV，第一列为学号（仅用于计数，不进入输出），其余列依次为 Q1..Qn 得分。
用法：
    python score_report.py -i scores.csv -f 2,2,2,4,6,10 -o report.md
    python score_report.py -i scores.csv -f 2,2,2,4 --sections 1-2:分离定律,3-4:自由组合

约定：
    - 空单元格视为缺失，不计入该题均值，也不把学生总分记 0。
    - 全列为空的行视为缺考，单独计数并从统计中剔除。
    - 区分度采用高低分组各 27% 的通过率之差（D = P_high - P_low）。
"""

import argparse
import csv
import os
import statistics
import sys
from typing import Dict, List, Optional, Tuple

BANDS = [(0, 45), (45, 60), (60, 75), (75, 90), (90, 100.0001)]
BAND_LABELS = ["<45%", "45–59%", "60–74%", "75–89%", "≥90%"]


def read_csv(path: str) -> Tuple[List[str], List[str], List[List[Optional[float]]]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh))
    if len(rows) < 2:
        raise ValueError("CSV 至少需要表头行和一行数据")
    header = [c.strip() for c in rows[0]]
    ids: List[str] = []
    values: List[List[Optional[float]]] = []
    for r in rows[1:]:
        if not r or all(not c.strip() for c in r):
            continue
        sid = r[0].strip() if r else ""
        cells = r[1:]
        parsed: List[Optional[float]] = []
        for c in cells:
            c = c.strip()
            if c == "" or c.upper() in ("NA", "N/A", "-", "缺考"):
                parsed.append(None)
            else:
                try:
                    parsed.append(float(c))
                except ValueError:
                    parsed.append(None)
        ids.append(sid)
        values.append(parsed)
    return header[1:], ids, values


def parse_full_marks(spec: str, n: int) -> List[float]:
    marks = [float(x) for x in spec.replace("，", ",").split(",") if x.strip()]
    if len(marks) != n:
        raise ValueError(f"满分个数({len(marks)})与题目列数({n})不一致")
    if any(m <= 0 for m in marks):
        raise ValueError("满分必须为正数")
    return marks


def parse_sections(spec: Optional[str], n: int) -> Dict[str, List[int]]:
    """spec 形如 '1-5:分离定律,6-10:自由组合'，题号从 1 开始。"""
    if not spec:
        return {}
    out: Dict[str, List[int]] = {}
    for part in spec.replace("，", ",").split(","):
        if not part.strip():
            continue
        if ":" not in part:
            raise ValueError(f"板块定义缺少冒号: {part}")
        rng, name = part.split(":", 1)
        rng = rng.strip()
        if "-" in rng:
            a, b = rng.split("-", 1)
            idx = list(range(int(a), int(b) + 1))
        else:
            idx = [int(rng)]
        for i in idx:
            if i < 1 or i > n:
                raise ValueError(f"板块题号越界: {i}")
        out[name.strip()] = idx
    return out


def band_of(pct: float) -> str:
    for (lo, hi), label in zip(BANDS, BAND_LABELS):
        if lo <= pct < hi:
            return label
    return BAND_LABELS[-1]


def analyse(values: List[List[Optional[float]]], marks: List[float], sections: Dict[str, List[int]]):
    n_q = len(marks)
    full_total = sum(marks)
    totals: List[float] = []
    absent = 0
    for row in values:
        row = (row + [None] * n_q)[:n_q]
        if all(v is None for v in row):
            absent += 1
            continue
        totals.append(sum(v for v in row if v is not None))

    if not totals:
        raise ValueError("没有可用于统计的有效成绩行")

    per_q = []
    for qi in range(n_q):
        scores = [(row + [None] * n_q)[qi] for row in values]
        got = [s for s in scores if s is not None]
        mean = statistics.fmean(got) if got else 0.0
        per_q.append({
            "no": qi + 1,
            "full": marks[qi],
            "mean": mean,
            "rate": mean / marks[qi] if marks[qi] else 0.0,
            "n": len(got),
        })

    # 区分度：按总分排序，取上下 27%
    paired = []
    for row in values:
        row = (row + [None] * n_q)[:n_q]
        if all(v is None for v in row):
            continue
        paired.append((sum(v for v in row if v is not None), row))
    paired.sort(key=lambda x: x[0], reverse=True)
    k = max(1, int(round(len(paired) * 0.27)))
    high = paired[:k]
    low = paired[-k:]
    for qi in range(n_q):
        hp = [r[qi] for _, r in high if r[qi] is not None]
        lp = [r[qi] for _, r in low if r[qi] is not None]
        p_h = (statistics.fmean(hp) / marks[qi]) if hp and marks[qi] else 0.0
        p_l = (statistics.fmean(lp) / marks[qi]) if lp and marks[qi] else 0.0
        per_q[qi]["d"] = p_h - p_l

    sec_rows = []
    for name, idx in sections.items():
        got = 0.0
        cap = 0.0
        for row in values:
            row = (row + [None] * n_q)[:n_q]
            if all(v is None for v in row):
                continue
            for i in idx:
                if row[i - 1] is not None:
                    got += row[i - 1]
                    cap += marks[i - 1]
        sec_rows.append({"name": name, "got": got, "cap": cap, "rate": (got / cap) if cap else 0.0})

    bands = {label: 0 for label in BAND_LABELS}
    for t in totals:
        bands[band_of(t / full_total * 100)] += 1

    return {
        "n": len(totals),
        "absent": absent,
        "full_total": full_total,
        "mean": statistics.fmean(totals),
        "median": statistics.median(totals),
        "stdev": statistics.stdev(totals) if len(totals) > 1 else 0.0,
        "max": max(totals),
        "min": min(totals),
        "bands": bands,
        "per_q": per_q,
        "sections": sec_rows,
    }


def render_md(res, title: str) -> str:
    lines = [f"# {title}", ""]
    lines.append(f"有效人数 {res['n']}｜缺考 {res['absent']}｜满分 {res['full_total']:g}")
    lines.append("")
    lines.append("## 一、总体")
    lines.append(f"- 均分 {res['mean']:.1f}｜中位数 {res['median']:.1f}｜标准差 {res['stdev']:.1f}")
    lines.append(f"- 最高 {res['max']:g}｜最低 {res['min']:g}")
    lines.append("")
    lines.append("| 分数段 | 人数 |")
    lines.append("|---|---|")
    for label, cnt in res["bands"].items():
        lines.append(f"| {label} | {cnt} |")
    lines.append("")
    lines.append("## 二、题目质量")
    lines.append("| 题号 | 满分 | 均分 | 得分率 | 难度 | 区分度 | 判定 |")
    lines.append("|---|---|---|---|---|---|---|")
    for q in res["per_q"]:
        if q["rate"] < 0.4:
            verdict = "塌方，需重教"
        elif q["rate"] < 0.6:
            verdict = "补漏"
        else:
            verdict = "巩固"
        if q.get("d", 0) < 0.2:
            verdict += "；题质待改"
        lines.append(
            f"| {q['no']} | {q['full']:g} | {q['mean']:.2f} | {q['rate']*100:.0f}% | "
            f"{q['rate']:.2f} | {q.get('d', 0):+.2f} | {verdict} |"
        )
    if res["sections"]:
        lines.append("")
        lines.append("## 三、板块得分率")
        lines.append("| 板块 | 得分 | 满分 | 得分率 | 判定 |")
        lines.append("|---|---|---|---|---|")
        for s in res["sections"]:
            if s["rate"] < 0.4:
                v = "塌方"
            elif s["rate"] < 0.6:
                v = "补漏"
            else:
                v = "过关"
            lines.append(f"| {s['name']} | {s['got']:g} | {s['cap']:g} | {s['rate']*100:.0f}% | {v} |")
    lines.append("")
    lines.append("## 四、判读提示")
    lines.append("- 得分率 <40% 的题：先查教学是否覆盖，再查题目表述，不直接归因为学生不努力。")
    lines.append("- 区分度 <0.2 的题：多为过易或表述有歧义，优先改题。")
    lines.append("- 区分度为负的题：先核对答案与题干，通常是命题问题。")
    lines.append("")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="班级成绩统计与题目质量分析")
    ap.add_argument("-i", "--input", required=True, help="成绩 CSV 路径")
    ap.add_argument("-f", "--full-marks", required=True, help="每题满分，逗号分隔，如 2,2,4,6")
    ap.add_argument("-o", "--output", help="Markdown 报告输出路径")
    ap.add_argument("--sections", help="板块定义，如 1-5:分离定律,6-10:自由组合")
    ap.add_argument("--title", default="班级成绩分析报告")
    ap.add_argument("--csv-out", help="题目统计 CSV 输出路径")
    args = ap.parse_args(argv)

    try:
        header, ids, values = read_csv(args.input)
        marks = parse_full_marks(args.full_marks, len(header))
        sections = parse_sections(args.sections, len(marks))
        res = analyse(values, marks, sections)
    except Exception as exc:  # noqa: BLE001
        print(f"[错误] {exc}", file=sys.stderr)
        return 2

    md = render_md(res, args.title)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(md)
        print(f"已写入 {args.output}")
    else:
        print(md)

    if args.csv_out:
        with open(args.csv_out, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["题号", "满分", "均分", "得分率", "区分度"])
            for q in res["per_q"]:
                w.writerow([q["no"], q["full"], round(q["mean"], 3), round(q["rate"], 4), round(q.get("d", 0), 4)])
        print(f"题目统计已写入 {args.csv_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
