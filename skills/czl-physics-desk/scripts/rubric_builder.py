#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""评分细则生成：把步骤清单转成分步给分的表格。

输入 CSV 列：问,步骤,分值,说明
  - 问：1 / 2 / 3 或 (1) / (2)
  - 说明：可留空；用于写"常见错误扣分""可替代解法"
输出：Markdown 评分细则（按问分组、含小计与合计）

用法：
  python rubric_builder.py --template 步骤模板.csv
  python rubric_builder.py --in 步骤.csv --out 评分细则.md --total 12
"""

import argparse
import csv
import os
import sys
from collections import OrderedDict


def _u(t):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    return t


def norm_no(v):
    v = str(v).strip()
    if not v:
        return "1"
    v = v.strip("()（） ")
    return v or "1"


def fnum(v, default=0.0):
    try:
        return float(str(v).strip())
    except Exception:
        return default


def build(rows, total=None):
    groups = OrderedDict()
    problems = []
    grand = 0.0
    for r in rows:
        no = norm_no(r.get("问"))
        step = (r.get("步骤") or "").strip()
        score = fnum(r.get("分值"), -1)
        note = (r.get("说明") or "").strip()
        if not step:
            problems.append("存在空步骤行，已跳过")
            continue
        if score <= 0:
            problems.append(f"第({no})问「{step}」分值非法：{r.get('分值')}")
            continue
        groups.setdefault(no, []).append((step, score, note))
        grand += score

    lines = ["| 问 | 给分点 | 分值 | 说明 |", "|---|---|---|---|"]
    for no, items in groups.items():
        sub = sum(s for _, s, _ in items)
        for step, score, note in items:
            lines.append(f"| ({no}) | {step} | {score:g} | {note} |")
        lines.append(f"|  | **小计** | **{sub:g}** |  |")
    lines.append(f"|  | **合计** | **{grand:g}** |  |")

    lines.append("")
    lines.append("## 评分说明")
    lines.append("")
    lines.append("1. 分步给分，错误不连坐：模型选错但受力图正确，仍给对应分。")
    lines.append("2. 方程正确而代入错误，只扣结果分；单位缺失扣该步一半分。")
    lines.append("3. 有效数字与题给数据位数不一致，扣 1 分（不重复扣）。")
    lines.append("4. 其他正确解法按对应步骤等分给分，不因解法不同降分。")

    if total is not None and abs(grand - total) > 1e-6:
        problems.append(f"细则合计 {grand:g} 分 ≠ 题目总分 {total:g} 分")
    return "\n".join(lines), grand, problems


TEMPLATE = """问,步骤,分值,说明
1,画出受力分析图并写明研究对象,1,漏画摩擦力不给分
1,列出牛顿第二定律方程 F-μmg=ma,2,符号错但形式对给1分
1,代入数据得 a=2.0 m/s²（带单位）,1,无单位扣0.5
2,判断两段过程并写出衔接量 v,2,只写一段不给分
2,第一段运动学方程,2,
2,第二段运动学方程,2,
2,结果 x=12 m（带单位）,2,结果错但过程对给前6分
"""


def main():
    ap = argparse.ArgumentParser(description="评分细则生成")
    ap.add_argument("--in", dest="inp")
    ap.add_argument("--out", dest="out")
    ap.add_argument("--template")
    ap.add_argument("--total", type=float, default=None, help="题目总分，用于校验")
    ap.add_argument("--title", default="评分细则")
    args = ap.parse_args()

    if args.template:
        with open(args.template, "w", encoding="utf-8-sig", newline="") as f:
            f.write(TEMPLATE)
        print(_u(f"已生成模板：{args.template}"))
        return 0

    if not args.inp or not os.path.exists(args.inp):
        ap.print_help()
        return 2

    with open(args.inp, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print(_u("CSV 没有数据行"))
        return 2

    md, grand, problems = build(rows, args.total)
    out = f"# {args.title}\n\n" + md + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out)
        print(_u(f"已写入：{args.out}（合计 {grand:g} 分）"))
    else:
        print(out)

    if problems:
        for p in problems:
            print(_u("注意：" + p))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
