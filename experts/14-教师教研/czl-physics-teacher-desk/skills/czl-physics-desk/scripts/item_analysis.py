#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""成绩表分析：难度、区分度、分数段、讲评建议。

输入
  --scores 成绩.csv   第一列为学号/编号，其余列为各题得分（可含"总分"列）
  --full   满分.csv   两列：题号,满分   （或 --full-marks "4,4,4,6,8,12,14"）
输出
  Markdown 学情报告

用法
  python item_analysis.py --scores 成绩.csv --full 满分.csv --out 学情.md
  python item_analysis.py --scores 成绩.csv --full-marks "4,4,4,6,8,12,14" --class 高二3班
"""

import argparse
import csv
import math
import os
import sys
from collections import OrderedDict

TOTAL_KEYS = {"总分", "合计", "总成绩", "score", "total"}
ID_KEYS = {"学号", "编号", "id", "序号", "考号"}


def _u(t):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    return t


def fnum(v, default=0.0):
    try:
        s = str(v).strip()
        if s == "":
            return default
        return float(s)
    except Exception:
        return default


def read_scores(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    if len(rows) < 2:
        raise ValueError("成绩表至少需要表头和一行数据")
    header = [h.strip() for h in rows[0]]
    data = [r for r in rows[1:] if any(str(c).strip() for c in r)]
    return header, data


def read_full(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    full = OrderedDict()
    for r in rows[1:]:
        if len(r) >= 2 and str(r[0]).strip():
            full[str(r[0]).strip()] = fnum(r[1])
    return full


def percentile_cut(values, ratio):
    """按总分取高/低分组（各取 ratio 比例，至少 1 人）。"""
    n = len(values)
    k = max(1, int(round(n * ratio)))
    ordered = sorted(range(n), key=lambda i: values[i], reverse=True)
    return ordered[:k], ordered[-k:]


def analyze(header, data, full_map=None, full_marks=None, ratio=0.27):
    # 识别列
    id_idx = 0
    for i, h in enumerate(header):
        if h.lower() in ID_KEYS:
            id_idx = i
            break
    q_cols = [i for i in range(len(header)) if i != id_idx and header[i] and header[i].lower() not in TOTAL_KEYS]
    total_idx = None
    for i, h in enumerate(header):
        if h.lower() in TOTAL_KEYS:
            total_idx = i
            break

    q_names = [header[i] for i in q_cols]
    # 满分
    full = []
    inferred = False
    for name in q_names:
        if full_map and name in full_map:
            full.append(full_map[name])
        elif full_marks and len(full_marks) == len(q_names):
            full.append(full_marks[q_names.index(name)])
        else:
            mx = max((fnum(r[i]) for r in data if i < len(r)), default=0)
            full.append(mx if mx > 0 else 1)
            inferred = True

    records = []
    for r in data:
        qs = [fnum(r[i]) if i < len(r) else 0.0 for i in q_cols]
        total = fnum(r[total_idx]) if total_idx is not None and total_idx < len(r) else sum(qs)
        if total_idx is None:
            total = sum(qs)
        records.append({"id": (r[id_idx] if id_idx < len(r) else ""), "q": qs, "total": total})

    n = len(records)
    totals = [x["total"] for x in records]
    full_total = sum(full)
    mean = sum(totals) / n
    var = sum((t - mean) ** 2 for t in totals) / n
    std = math.sqrt(var)
    mx, mn = max(totals), min(totals)
    pass_line = 0.6 * full_total
    exc_line = 0.85 * full_total
    pass_rate = sum(1 for t in totals if t >= pass_line) / n
    exc_rate = sum(1 for t in totals if t >= exc_line) / n

    # 分数段（按得分率）
    bands = [("90-100%", 0.9, 1.01), ("80-89%", 0.8, 0.9), ("70-79%", 0.7, 0.8),
             ("60-69%", 0.6, 0.7), ("50-59%", 0.5, 0.6), ("<50%", -0.01, 0.5)]
    band_count = []
    for label, lo, hi in bands:
        c = sum(1 for t in totals if lo * full_total <= t < hi * full_total)
        band_count.append((label, c))

    hi_idx, lo_idx = percentile_cut(totals, ratio)

    q_stats = []
    for j, name in enumerate(q_names):
        scores = [x["q"][j] for x in records]
        m = sum(scores) / n
        p = m / full[j] if full[j] else 0
        hi_m = sum(records[i]["q"][j] for i in hi_idx) / len(hi_idx)
        lo_m = sum(records[i]["q"][j] for i in lo_idx) / len(lo_idx)
        d = (hi_m - lo_m) / full[j] if full[j] else 0
        q_stats.append({"name": name, "full": full[j], "mean": m, "p": p, "d": d})

    return {
        "n": n, "full_total": full_total, "mean": mean, "std": std, "max": mx, "min": mn,
        "pass_rate": pass_rate, "exc_rate": exc_rate, "bands": band_count,
        "q_stats": q_stats, "inferred": inferred, "hi": len(hi_idx), "lo": len(lo_idx),
        "records": records, "ratio": ratio, "ids": q_names,
    }


def render(res, class_name="", pass_line=0.6, exc_line=0.85):
    n = res["n"]
    L = []
    L.append(f"# 学情分析报告{'（' + class_name + '）' if class_name else ''}")
    L.append("")
    L.append("## 一、总体")
    L.append("")
    L.append("| 指标 | 数值 |")
    L.append("|---|---|")
    L.append(f"| 实考人数 | {n} |")
    L.append(f"| 卷面满分 | {res['full_total']:g} |")
    L.append(f"| 平均分 | {res['mean']:.1f} |")
    L.append(f"| 标准差 | {res['std']:.1f} |")
    L.append(f"| 最高 / 最低 | {res['max']:g} / {res['min']:g} |")
    L.append(f"| 及格率（≥{pass_line:.0%}） | {res['pass_rate']:.0%} |")
    L.append(f"| 优秀率（≥{exc_line:.0%}） | {res['exc_rate']:.0%} |")
    L.append(f"| 整卷难度 | {res['mean'] / res['full_total']:.2f} |")
    L.append("")
    L.append("### 分数段分布")
    L.append("")
    L.append("| 得分率区间 | 人数 | 占比 | 图示 |")
    L.append("|---|---|---|---|")
    for label, c in res["bands"]:
        bar = "█" * int(round(c / max(n, 1) * 30))
        L.append(f"| {label} | {c} | {c / n:.0%} | {bar} |")
    L.append("")
    L.append("## 二、逐题难度与区分度")
    L.append("")
    L.append(f"区分度按总分高低分组各 {res['ratio']:.0%} 计算（高分组 {res['hi']} 人，低分组 {res['lo']} 人）。")
    L.append("")
    L.append("| 题号 | 满分 | 平均分 | 难度 P | 区分度 D | 判定 |")
    L.append("|---|---|---|---|---|---|")
    for q in sorted(res["q_stats"], key=lambda x: x["p"]):
        if q["p"] < 0.6 and q["d"] >= 0.3:
            verdict = "真难点，必讲"
        elif q["p"] < 0.6 and q["d"] < 0.2:
            verdict = "普遍不会，先查教学"
        elif q["p"] >= 0.85:
            verdict = "送分题，不讲"
        elif q["d"] >= 0.4:
            verdict = "区分良好"
        else:
            verdict = "一般"
        L.append(f"| {q['name']} | {q['full']:g} | {q['mean']:.1f} | {q['p']:.2f} | {q['d']:.2f} | {verdict} |")
    L.append("")
    L.append("## 三、讲评选题建议")
    L.append("")
    must = [q for q in res["q_stats"] if q["p"] < 0.6 and q["d"] >= 0.3]
    check = [q for q in res["q_stats"] if q["p"] < 0.6 and q["d"] < 0.2]
    hard = [q for q in res["q_stats"] if q["p"] < 0.35]
    if must:
        L.append("优先讲（难度低且区分度好，说明是方法问题）：" + "、".join(f"第{q['name']}题" for q in must))
    else:
        L.append("没有「难度低且区分度好」的题，讲评重点放在错因归类上。")
    if check:
        L.append("")
        L.append("需要先查教学（几乎全班不会，可能是没讲到或超纲）：" + "、".join(f"第{q['name']}题" for q in check))
    if hard:
        L.append("")
        L.append("压轴类（难度 <0.35，只对拔高层讲）：" + "、".join(f"第{q['name']}题" for q in hard))
    L.append("")
    L.append("## 四、分层建议")
    L.append("")
    lo_group = sorted(res["records"], key=lambda x: x["total"])[: max(1, n // 4)]
    hi_group = sorted(res["records"], key=lambda x: x["total"], reverse=True)[: max(1, n // 4)]
    L.append(f"- 保底层（约 {len(lo_group)} 人，总分后 25%）：主攻单过程基础题与公式条件默写，面批检查步骤完整性。")
    L.append(f"- 拔高层（约 {len(hi_group)} 人，总分前 25%）：给综合题与开放设问，要求交思路而非只交答案。")
    L.append(f"- 中间层（约 {n - len(lo_group) - len(hi_group)} 人）：按逐题得分率补 2–3 个断点，配变式题。")
    L.append("")
    L.append("## 五、数据说明")
    L.append("")
    if res["inferred"]:
        L.append("- 未提供满分表，部分题目满分取该题最高得分推断，难度值仅供参考。")
    if n < 30:
        L.append("- 样本量小于 30，区分度波动较大，只作参考。")
    L.append(f"- 分母口径：实考 {n} 人；缺考与空白按 0 分计入。")
    L.append("- 学生以学号标识，报告不含姓名等个人信息。")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="成绩表分析")
    ap.add_argument("--scores", required=False)
    ap.add_argument("--full")
    ap.add_argument("--full-marks")
    ap.add_argument("--out")
    ap.add_argument("--class", dest="klass", default="")
    ap.add_argument("--ratio", type=float, default=0.27)
    ap.add_argument("--pass-rate", type=float, default=0.6)
    ap.add_argument("--excellent-rate", type=float, default=0.85)
    args = ap.parse_args()

    if not args.scores or not os.path.exists(args.scores):
        ap.print_help()
        return 2

    header, data = read_scores(args.scores)
    full_map = read_full(args.full) if args.full and os.path.exists(args.full) else None
    full_marks = None
    if args.full_marks:
        full_marks = [fnum(x) for x in args.full_marks.replace("，", ",").split(",") if x.strip()]

    res = analyze(header, data, full_map=full_map, full_marks=full_marks, ratio=args.ratio)
    md = render(res, args.klass, args.pass_rate, args.excellent_rate)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(md + "\n")
        print(_u(f"已写入：{args.out}（{res['n']} 人，均分 {res['mean']:.1f}）"))
    else:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
