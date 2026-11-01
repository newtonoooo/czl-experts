#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""双向细目表生成与校验。

输入 CSV 列：题号,题型,考点,认知层级,难度,分值,用时
  - 难度：0-1 之间的小数（预设难度系数）
  - 用时：分钟，可写 1.5
输出：Markdown 细目表 + 汇总校验（总分、加权难度、题型配比、考点占比、总用时）

用法：
  python blueprint.py --template 细目表模板.csv
  python blueprint.py --in 细目表.csv --out 细目表.md --total 100 --difficulty 0.65 --minutes 75
"""

import argparse
import csv
import os
import sys
from collections import defaultdict

LEVELS = ("识记", "理解", "应用", "分析")


def _u(text):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    return text


def read_csv(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def fnum(value, default=0.0):
    try:
        return float(str(value).strip())
    except Exception:
        return default


def build(rows, total=None, target_diff=None, minutes=None):
    lines, problems, notes = [], [], []
    score_sum = 0.0
    time_sum = 0.0
    weighted = 0.0
    by_type = defaultdict(float)
    by_point = defaultdict(float)
    by_level = defaultdict(float)
    by_type_count = defaultdict(int)

    for r in rows:
        q = (r.get("题号") or "").strip()
        typ = (r.get("题型") or "").strip()
        point = (r.get("考点") or "").strip()
        level = (r.get("认知层级") or "").strip()
        diff = fnum(r.get("难度"), -1)
        score = fnum(r.get("分值"), -1)
        tm = fnum(r.get("用时"), 0)

        if not q or not typ:
            problems.append("存在缺少题号或题型的行，已跳过")
            continue
        if score < 0:
            problems.append(f"第 {q} 题分值缺失或非法")
            continue
        if not (0 < diff <= 1):
            problems.append(f"第 {q} 题难度应在 0~1 之间，当前 {diff}")
            diff = max(min(diff, 1.0), 0.01)

        score_sum += score
        time_sum += tm
        weighted += diff * score
        by_type[typ] += score
        by_type_count[typ] += 1
        by_point[point] += score
        by_level[level] += score

    if score_sum > 0:
        avg_diff = weighted / score_sum
    else:
        avg_diff = 0.0

    if total is not None and abs(score_sum - total) > 1e-6:
        problems.append(f"分值合计 {score_sum:g} ≠ 目标总分 {total:g}")
    if target_diff is not None and abs(avg_diff - target_diff) > 0.03:
        problems.append(f"加权难度 {avg_diff:.2f} 偏离目标 {target_diff:.2f} 超过 0.03")
    if minutes is not None and time_sum > minutes * 0.9:
        problems.append(f"预估用时 {time_sum:g} 分钟超过规定时长 {minutes:g} 分钟的 90%")

    if score_sum > 0:
        for p, s in by_point.items():
            if p and s / score_sum > 0.18:
                problems.append(f"考点「{p}」占 {s / score_sum:.0%}，超过 18%")
        for lv, s in by_level.items():
            if lv and lv not in LEVELS:
                notes.append(f"认知层级「{lv}」不在四档内（识记/理解/应用/分析）")
        if by_level.get("识记", 0) / score_sum > 0.15:
            problems.append("识记类占比超过 15%")
        if by_level.get("分析", 0) / score_sum > 0.50:
            problems.append("分析类占比超过 50%，缺少基础题")
        if (by_level.get("理解", 0) + by_level.get("应用", 0)) / score_sum < 0.35:
            problems.append("理解+应用类不足 35%，基础题保底不够")

    lines.append("| 题号 | 题型 | 考点 | 认知层级 | 预设难度 | 分值 | 用时(min) |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in rows:
        q = (r.get("题号") or "").strip()
        if not q:
            continue
        lines.append(
            "| {} | {} | {} | {} | {} | {} | {} |".format(
                q,
                (r.get("题型") or "").strip(),
                (r.get("考点") or "").strip(),
                (r.get("认知层级") or "").strip(),
                fnum(r.get("难度")),
                fnum(r.get("分值")),
                fnum(r.get("用时")),
            )
        )

    summary = [
        "",
        "## 校验汇总",
        "",
        f"- 题量：{sum(by_type_count.values())} 题（" + "，".join(f"{k} {v} 题" for k, v in by_type_count.items()) + "）",
        f"- 分值合计：{score_sum:g}",
        f"- 加权难度：{avg_diff:.2f}",
        f"- 预估总用时：{time_sum:g} 分钟",
        "- 题型配比：" + "，".join(f"{k} {v:g} 分（{v / score_sum:.0%}）" for k, v in by_type.items()) if score_sum else "",
        "- 认知层级：" + "，".join(f"{k or '未标'} {v:g} 分" for k, v in by_level.items()) if score_sum else "",
    ]
    lines.extend(x for x in summary if x)

    lines.append("")
    lines.append("## 结论")
    if problems:
        lines.append("")
        lines.append("需要修改：")
        lines.extend(f"- {p}" for p in problems)
    else:
        lines.append("")
        lines.append("校验通过：总分、难度、配比、用时均在设定范围内。")
    if notes:
        lines.append("")
        lines.append("提示：")
        lines.extend(f"- {n}" for n in notes)

    return "\n".join(lines), problems


TEMPLATE = """题号,题型,考点,认知层级,难度,分值,用时
1,单选,匀变速直线运动图像,理解,0.85,4,1.5
2,单选,摩擦力方向判断,理解,0.80,4,1.5
3,单选,牛顿第二定律简单应用,应用,0.75,4,2
4,多选,连接体受力分析,分析,0.55,6,3
5,实验,打点计时器测加速度,应用,0.70,8,9
6,计算,多过程动力学,分析,0.55,12,10
7,计算,功能关系综合,分析,0.40,14,12
"""


def main():
    ap = argparse.ArgumentParser(description="双向细目表生成与校验")
    ap.add_argument("--in", dest="inp", help="输入 CSV")
    ap.add_argument("--out", dest="out", help="输出 Markdown")
    ap.add_argument("--template", help="生成空白模板 CSV 到指定路径")
    ap.add_argument("--total", type=float, default=None, help="目标总分，默认 100")
    ap.add_argument("--difficulty", type=float, default=None, help="目标加权难度，如 0.65")
    ap.add_argument("--minutes", type=float, default=None, help="规定时长（分钟）")
    args = ap.parse_args()

    if args.template:
        with open(args.template, "w", encoding="utf-8-sig", newline="") as f:
            f.write(TEMPLATE)
        print(_u(f"已生成模板：{args.template}"))
        return 0

    if not args.inp:
        ap.print_help()
        return 2
    if not os.path.exists(args.inp):
        print(_u(f"找不到输入文件：{args.inp}"))
        return 2

    rows = read_csv(args.inp)
    if not rows:
        print(_u("CSV 没有数据行"))
        return 2

    total = 100 if args.total is None else args.total
    md, problems = build(rows, total=total, target_diff=args.difficulty, minutes=args.minutes)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write("# 双向细目表\n\n" + md + "\n")
        print(_u(f"已写入：{args.out}"))
    else:
        print(md)

    if problems:
        print(_u(f"\n发现 {len(problems)} 处需要调整"))
        return 1
    print(_u("\n校验通过"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
