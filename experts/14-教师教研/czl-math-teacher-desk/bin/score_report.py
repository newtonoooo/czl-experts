#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""score_report.py —— 从原始分题得分表算出学情报告（纯标准库，零依赖）。

为什么要有这个脚本：
    均分、得分率、标准差这类数，模型心算必错。本脚本把统计从"叙述"里剥出来，
    先算出可靠的数，再让文字去解释数。

输入两种格式，自动识别：
    1) 宽表（推荐）：第一行是题号，每行一个学生
           学号,1,2,3,...,19
           01,5,5,0,...,9
           02,5,0,5,...,12
    2) 窄表：三列 学生,题号,得分（长格式）

用法：
    python bin/score_report.py 成绩.csv --full-marks 5,5,5,5,5,5,5,5,6,6,6,5,5,5,13,15,15,17,17
    python bin/score_report.py 成绩.csv --full-marks ... --out 报告.md --json 数据.json
    python bin/score_report.py 成绩.csv --full-marks ... --pass-line 90 --excellent 120

输出：
    Markdown 学情报告（stdout 或 --out 文件）+ 可选 JSON（供后续程序读）
"""

import argparse
import csv
import json
import os
import sys
import statistics

# Windows 控制台默认 GBK，中文与符号会炸，这里统一成 UTF-8
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 可教性：这个分数段的题，讲一遍能挽回多少。
# 依据：选择题/填空题讲一遍基本都会；中档解答要练；压轴题讲了多数人仍拿不到。
TEACHABILITY_BY_MARK = [
    (6, 0.90),    # 单选、填空
    (8, 0.85),    # 多选
    (15, 0.70),   # 中档解答
    (10 ** 6, 0.25),  # 17 分及以上的压轴
]


def teachability(mark):
    for upper, value in TEACHABILITY_BY_MARK:
        if mark <= upper:
            return value
    return 0.25


def parse_numbers(text):
    """把 '5,5,5' / '5 5 5' / '5，5，5' 解析成浮点列表。"""
    if not text:
        return []
    for ch in "，、；;":
        text = text.replace(ch, ",")
    parts = [p.strip() for p in text.replace(" ", ",").split(",") if p.strip()]
    return [float(p) for p in parts]


def read_table(path):
    """返回 (题号列表, 学生行列表[(id, [得分或None])])。"""
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
        except csv.Error:
            dialect = csv.excel
        rows = [r for r in csv.reader(f, dialect) if any(c.strip() for c in r)]

    if not rows:
        raise SystemExit("错误：文件为空 %s" % path)

    header = [c.strip() for c in rows[0]]
    body = rows[1:]

    # 窄表：三列且第二列表头像"题号"
    if len(header) == 3 and ("题号" in header[1] or header[1].lower() in ("q", "item")):
        by_student = {}
        order = []
        for r in body:
            if len(r) < 3:
                continue
            sid, q, s = r[0].strip(), r[1].strip(), r[2].strip()
            if sid not in by_student:
                by_student[sid] = {}
                order.append(sid)
            by_student[sid][q] = to_float(s)
        qs = []
        for r in body:
            if len(r) >= 2 and r[1].strip() not in qs:
                qs.append(r[1].strip())
        return qs, [(sid, [by_student[sid].get(q) for q in qs]) for sid in order]

    # 宽表：第一列是学生标识，其余是题
    qs = header[1:]
    out = []
    for r in body:
        if len(r) < 2:
            continue
        sid = r[0].strip() or "row%d" % (len(out) + 1)
        vals = [to_float(c) for c in r[1:1 + len(qs)]]
        while len(vals) < len(qs):
            vals.append(None)
        out.append((sid, vals))
    return qs, out


def to_float(text):
    if text is None:
        return None
    t = str(text).strip()
    if t == "" or t in ("-", "—", "缺", "缺考", "na", "NA", "N/A"):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def bucket_labels(top):
    """按满分生成六档分数段。

    150 分制用教师习惯的分档（130+/120-129/…/90 以下）；
    小分值（单元小卷、随堂测）用等距六档，避免出现"16-16"这种退化区间。
    """
    if top >= 100:
        edges = [round(top * r) for r in (0.8667, 0.8, 0.7333, 0.6667, 0.6)]
    else:
        step = top / 6.0
        edges = [round(top - step * i) for i in range(1, 6)]
    edges = sorted({e for e in edges if 0 < e < top}, reverse=True)
    if not edges:
        return [("%g 分及以上" % top, top, None), ("不足 %g 分" % top, None, top - 1)]

    labels = []
    prev = None
    for e in edges:
        if prev is None:
            labels.append(("%g 分及以上" % e, e, None))
        else:
            labels.append(("%g–%g 分" % (e, prev - 1), e, prev - 1))
        prev = e
    labels.append(("不足 %g 分" % prev, None, prev - 1))
    return labels


def analyze(qs, rows, full_marks, pass_line=None, excellent=None):
    n = len(rows)
    if n == 0:
        raise SystemExit("错误：没有学生数据行")

    if not full_marks:
        raise SystemExit("错误：请用 --full-marks 指定每题满分，数量应与题号数量一致")
    if len(full_marks) != len(qs):
        raise SystemExit(
            "错误：满分个数(%d)与题号个数(%d)不一致。\n题号：%s"
            % (len(full_marks), len(qs), ",".join(qs))
        )

    total_full = sum(full_marks)
    totals = []
    per_q = [[] for _ in qs]
    absent_per_q = [0] * len(qs)
    for _sid, vals in rows:
        if all(v is None for v in vals):
            continue
        s = 0.0
        for i, v in enumerate(vals):
            if v is None:
                absent_per_q[i] += 1
            else:
                per_q[i].append(v)
                s += v
        totals.append(s)

    n_eff = len(totals)
    mean = statistics.fmean(totals)
    med = statistics.median(totals)
    sd = statistics.stdev(totals) if n_eff > 1 else 0.0

    pass_line = pass_line if pass_line is not None else total_full * 0.6
    excellent = excellent if excellent is not None else total_full * 0.8

    q_stats = []
    for i, q in enumerate(qs):
        vals = per_q[i]
        fm = full_marks[i]
        m = statistics.fmean(vals) if vals else 0.0
        rate = (m / fm) if fm else 0.0
        recoverable = fm * (1 - rate)
        teach = teachability(fm)
        q_stats.append({
            "q": q,
            "full": fm,
            "mean": m,
            "rate": rate,
            "recoverable": recoverable,
            "teachability": teach,
            "priority": recoverable * teach,
            "answered": len(vals),
            "absent": absent_per_q[i],
            "level": "易" if rate >= 0.7 else ("中" if rate >= 0.4 else "难"),
        })

    buckets = []
    for label, lo, hi in bucket_labels(total_full):
        cnt = sum(1 for t in totals
                  if (lo is None or t >= lo) and (hi is None or t <= hi))
        buckets.append({"label": label, "count": cnt, "ratio": cnt / n_eff if n_eff else 0})

    # 临界生：及格线上下浮动 10% 满分
    margin = total_full * 0.05
    near = [i for i, t in enumerate(totals) if abs(t - pass_line) <= margin]

    return {
        "questions": qs,
        "full_marks": full_marks,
        "total_full": total_full,
        "students": n_eff,
        "rows_in_file": n,
        "mean": mean,
        "median": med,
        "stdev": sd,
        "max": max(totals),
        "min": min(totals),
        "difficulty": mean / total_full if total_full else 0,
        "pass_line": pass_line,
        "excellent_line": excellent,
        "pass_rate": sum(1 for t in totals if t >= pass_line) / n_eff,
        "excellent_rate": sum(1 for t in totals if t >= excellent) / n_eff,
        "buckets": buckets,
        "items": q_stats,
        "near_pass_count": len(near),
        "totals": totals,
    }


def render_markdown(data, title):
    L = []
    A = L.append
    A("# %s" % title)
    A("")
    A("**参考人数**：%d　**满分**：%g　**均分**：%.1f　**难度系数**：%.2f"
      % (data["students"], data["total_full"], data["mean"], data["difficulty"]))
    A("")
    A("> 本报告全部数字由 `bin/score_report.py` 计算得出，可复算。"
      "文字部分是对数字的解释，不改动数字。")
    A("")
    A("## 一、总体")
    A("")
    A("| 指标 | 数值 |")
    A("|---|---|")
    A("| 均分 / 满分 | %.1f / %g |" % (data["mean"], data["total_full"]))
    A("| 难度系数 | %.2f |" % data["difficulty"])
    A("| 中位数 | %.1f |" % data["median"])
    A("| 标准差 | %.1f |" % data["stdev"])
    A("| 最高 / 最低 | %g / %g |" % (data["max"], data["min"]))
    A("| 及格率（≥%g） | %.1f%% |" % (data["pass_line"], data["pass_rate"] * 100))
    A("| 优秀率（≥%g） | %.1f%% |" % (data["excellent_line"], data["excellent_rate"] * 100))
    A("| 临界生（及格线 ±5%% 满分） | %d 人 |" % data["near_pass_count"])
    A("")
    A("### 分数段分布")
    A("")
    A("| 分数段 | 人数 | 占比 |")
    A("|---|---|---|")
    for b in data["buckets"]:
        A("| %s | %d | %.1f%% |" % (b["label"], b["count"], b["ratio"] * 100))
    A("")
    A("## 二、各题得分情况")
    A("")
    A("| 题号 | 满分 | 均分 | 得分率 | 难度 | 可挽回分 | 讲评优先级 |")
    A("|---|---|---|---|---|---|---|")

    def sort_key(it):
        try:
            return (0, int("".join(ch for ch in it["q"] if ch.isdigit()) or 0))
        except ValueError:
            return (1, 0)

    for it in sorted(data["items"], key=sort_key):
        A("| %s | %g | %.1f | %.2f | %s | %.1f | %.1f |"
          % (it["q"], it["full"], it["mean"], it["rate"], it["level"],
             it["recoverable"], it["priority"]))
    A("")
    A("> 讲评优先级 = 可挽回分 × 可教性。可挽回分 = 分值 ×(1 − 得分率)。"
      "可教性按分值分档：≤6 分记 0.90，≤15 分记 0.70，17 分及以上记 0.25。")
    A("")
    A("## 三、讲评重点（按优先级取前 3）")
    A("")
    top = sorted(data["items"], key=lambda x: -x["priority"])[:3]
    for i, it in enumerate(top, 1):
        A("### %d. 第 %s 题（得分率 %.2f，可挽回 %.1f 分）" % (i, it["q"], it["rate"], it["recoverable"]))
        A("")
        A("- 满分 %g，均分 %.1f，%d 人作答%s"
          % (it["full"], it["mean"], it["answered"],
             "，%d 人缺答" % it["absent"] if it["absent"] else ""))
        A("- 建议动作：讲这一步的**起手动作**，当堂练 2 道同型题")
        A("")
    zero = [it["q"] for it in data["items"] if it["rate"] == 0]
    if zero:
        A("> 得分率为 0 的题：%s。若整题 0 分，先确认是否漏批或数据错位。" % "、".join(zero))
        A("")
    A("## 四、口径说明")
    A("")
    A("- 缺考/空值不计入该题均分，分母为该题实际作答人数。")
    A("- 若缺考按 0 分计入，均分与及格率都会下降，本报告不采用该口径。")
    A("- 标准差为样本标准差（n−1）。")
    A("- 本报告用于教学决策，不用于给学生排名或贴标签。")
    A("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="分题得分表 → 学情报告")
    ap.add_argument("file", help="分题得分表（CSV/TSV）")
    ap.add_argument("--full-marks", required=True, help="每题满分，逗号分隔，如 5,5,5,6,6,6,5,5,5")
    ap.add_argument("--pass-line", type=float, default=None, help="及格线，默认满分×0.6")
    ap.add_argument("--excellent", type=float, default=None, help="优秀线，默认满分×0.8")
    ap.add_argument("--out", default=None, help="输出 Markdown 路径")
    ap.add_argument("--json", dest="json_out", default=None, help="输出 JSON 路径")
    ap.add_argument("--title", default="学情分析报告", help="报告标题")
    args = ap.parse_args()

    if not os.path.isfile(args.file):
        raise SystemExit("错误：找不到文件 %s" % args.file)

    qs, rows = read_table(args.file)
    full = parse_numbers(args.full_marks)
    data = analyze(qs, rows, full, args.pass_line, args.excellent)
    md = render_markdown(data, args.title)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(md)
        print("已生成报告：%s" % args.out)
        print("均分 %.1f / 难度系数 %.2f / 及格率 %.1f%%"
              % (data["mean"], data["difficulty"], data["pass_rate"] * 100))
    else:
        print(md)

    if args.json_out:
        slim = {k: v for k, v in data.items() if k != "totals"}
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(slim, f, ensure_ascii=False, indent=2)
        print("已生成数据：%s" % args.json_out)


if __name__ == "__main__":
    main()
