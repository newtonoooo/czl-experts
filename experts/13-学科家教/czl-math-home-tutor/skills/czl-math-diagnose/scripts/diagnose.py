#!/usr/bin/env python3
"""diagnose.py - turn a marked paper into a ranked list of breakpoints.

Input is a CSV you can build in Excel in two minutes: one row per question.

    tehao,knowledge,score,got,code
    1,集合,5,5,
    7,导数单调性,5,0,C
    12,圆锥曲线,17,9,M
    ...

Accepted headers (Chinese or English, case-insensitive, order free):
    题号 / no / id
    知识点 / knowledge / topic
    分值 / score / full
    得分 / got / earned
    错因码 / code / error   (optional, C/M/A/W/R)

What it computes
----------------
* 得分率 per knowledge point, sorted by marks lost (not by rate - a 90% point
  worth 40 marks loses more than a 50% point worth 5)
* error-code mix, so the prescription targets a mechanism instead of a mood
* a prescription per breakpoint with a time budget, plus an acceptance test
  ("下次验收") that the next session can actually check

Usage
-----
    python diagnose.py scores.csv
    python diagnose.py scores.csv --top 4 --md report.md
    python diagnose.py --template > scores.csv    # print a blank template

Exit code: 0 ok, 2 bad input.
"""

import argparse
import csv
import io
import sys
from collections import Counter, OrderedDict

HEADER_ALIASES = {
    "no": {"题号", "no", "id", "序号", "题"},
    "knowledge": {"知识点", "knowledge", "topic", "考点", "模块"},
    "full": {"分值", "score", "full", "满分"},
    "got": {"得分", "got", "earned", "实得"},
    "code": {"错因码", "code", "error", "错因"},
}

CODE_NAMES = OrderedDict([
    ("C", "概念"),
    ("M", "方法"),
    ("A", "运算"),
    ("W", "书写"),
    ("R", "读题"),
])

CODE_ACTIONS = {
    "C": ("回定义：把这条定义/定理的适用条件手写一遍，再用一个反例打一遍", 15),
    "M": ("只练入口：拿到题先写三条路各一行，不求解，写完对照入口表", 20),
    "A": ("限时计算：8 道纯计算，10 分钟内做完，错一道加做两道", 10),
    "W": ("抄骨架：抄一遍标准答案的连接词与结论句，只抄骨架不抄算式", 15),
    "R": ("读题划条件：读完不复述不许动笔，复述一遍再开始", 10),
}

TEMPLATE = """题号,知识点,分值,得分,错因码
1,集合与逻辑,5,5,
2,复数,5,5,
3,函数性质,5,0,C
4,导数单调性,5,0,M
5,三角函数化简,5,5,
6,解三角形,5,3,A
7,数列通项,5,0,M
8,立体几何线面角,5,5,
9,概率分布列,6,4,W
10,解析几何弦长,6,0,M
11,导数压轴,6,2,C
12,三角函数图像,5,5,
13,数列求和,5,0,A
14,圆锥曲线离心率,5,0,R
15,解三角形综合,13,9,A
16,立体几何证明,15,11,W
17,概率统计,15,12,A
18,导数综合,17,6,M
19,数列压轴,17,3,M
"""


def norm_header(name):
    key = name.strip().lower().lstrip("\ufeff")
    for canon, aliases in HEADER_ALIASES.items():
        if key in aliases:
            return canon
    return None


def to_float(text, default=None):
    text = (text or "").strip().replace("，", "").replace(",", "")
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def load(path):
    with io.open(path, encoding="utf-8-sig", newline="") as fh:
        sample = fh.read(4096)
        fh.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.reader(fh, dialect)
        rows = [r for r in reader if any(c.strip() for c in r)]
    if not rows:
        raise ValueError("empty file")

    header = [norm_header(c) for c in rows[0]]
    if "knowledge" not in header or "full" not in header:
        raise ValueError(
            "header must contain 知识点 and 分值 (got: %s)" % ", ".join(rows[0]))

    idx = {name: i for i, name in enumerate(header) if name}
    items = []
    for r in rows[1:]:
        def cell(key):
            i = idx.get(key)
            return r[i] if i is not None and i < len(r) else ""

        full = to_float(cell("full"))
        if full is None or full <= 0:
            continue
        got = to_float(cell("got"), 0.0)
        got = min(max(got, 0.0), full)
        code = (cell("code") or "").strip().upper()[:1]
        items.append({
            "no": (cell("no") or "").strip() or "-",
            "knowledge": (cell("knowledge") or "未分类").strip(),
            "full": full,
            "got": got,
            "code": code if code in CODE_NAMES else "",
        })
    if not items:
        raise ValueError("no usable rows (need 分值 > 0)")
    return items


def summarise(items):
    groups = OrderedDict()
    for it in items:
        g = groups.setdefault(it["knowledge"], {
            "full": 0.0, "got": 0.0, "n": 0, "codes": Counter(), "rows": []})
        g["full"] += it["full"]
        g["got"] += it["got"]
        g["n"] += 1
        g["rows"].append(it)
        if it["code"] and it["got"] < it["full"]:
            g["codes"][it["code"]] += 1
    for g in groups.values():
        g["rate"] = g["got"] / g["full"] if g["full"] else 0.0
        g["lost"] = g["full"] - g["got"]
        g["main_code"] = g["codes"].most_common(1)[0][0] if g["codes"] else ""
    return groups


def band(rate):
    if rate < 0.4:
        return "基础缺口", "这条线的定义和条件还没立住，先把课本定义和一个反例过一遍"
    if rate < 0.7:
        return "方法缺口", "定义会，但不知道从哪句话切进去，缺的是入口训练"
    if rate < 0.85:
        return "执行缺口", "入口找得到，分丢在算错和写不全，属可快速回收的分"
    return "稳定度", "基本掌握，失分多为偶发，靠变式维持手感即可"


# 错因码一旦确定，就由码决定性质——不要出现"主码是方法、性质写基础缺口"这种自相矛盾
CODE_LABELS = {
    "C": ("基础缺口", "定义或适用条件没立住，讲方法之前先补概念"),
    "M": ("方法缺口", "单步都会，连起来不知道从哪下手，缺的是入口"),
    "A": ("执行缺口", "入口和思路都对，分丢在算错，属可快速回收的分"),
    "W": ("执行缺口", "会做但写不全，被判卷扣步骤分，改书写就能拿回来"),
    "R": ("读题缺口", "题没读准，答案再对也拿不到分，先练划条件"),
}

# 验收用绝对档位，不用"当前 +20 个百分点"——后者对低分点位没有压迫感
def accept_line(rate, code):
    if code in ("C", "R") or (not code and rate < 0.4):
        return "下次同类题得分率 ≥ 60%，且不再出现同一条定义用错"
    if code == "M" or (not code and rate < 0.7):
        return "下次同类题得分率 ≥ 80%，且能独立写出入口那一行"
    if code in ("A", "W") or (not code and rate < 0.85):
        return "下次同类题得分率 ≥ 90%，且过程分不被扣"
    return "下次同类题满分，连续两次才算通过"


def prescription(g, minutes_budget):
    rate = g["rate"]
    code = g["main_code"]
    if code:
        label, why = CODE_LABELS[code]
    else:
        label, why = band(rate)

    if code:
        action, mins = CODE_ACTIONS[code]
        basis = "主码 %s（%s）" % (code, CODE_NAMES[code])
    elif rate < 0.4:
        action, mins = CODE_ACTIONS["C"]
        basis = "无错因码，按得分率推定"
    elif rate < 0.7:
        action, mins = CODE_ACTIONS["M"]
        basis = "无错因码，按得分率推定"
    elif rate < 0.85:
        action, mins = CODE_ACTIONS["A"]
        basis = "无错因码，按得分率推定"
    else:
        action, mins = ("换轴变式 2 道：改问法不改知识点，检验迁移", 15)
        basis = "无错因码，按得分率推定"

    mins = max(10, min(mins, minutes_budget))
    if g["lost"] <= 2 and not code:
        accept = "下次同类题满分即视为通过"
    else:
        accept = accept_line(rate, code)
    return {
        "label": label, "why": why, "action": action, "mins": mins,
        "basis": basis, "accept": accept,
    }


def render(items, top, md_path):
    total_full = sum(i["full"] for i in items)
    total_got = sum(i["got"] for i in items)
    rate = total_got / total_full if total_full else 0.0
    groups = summarise(items)
    ranked = sorted(groups.items(), key=lambda kv: (-kv[1]["lost"], kv[1]["rate"]))[:top]
    codes = Counter()
    for it in items:
        if it["code"] and it["got"] < it["full"]:
            codes[it["code"]] += 1

    budget = 45
    out = []
    out.append("# 学情诊断表")
    out.append("")
    out.append("## 一、样本")
    out.append("")
    out.append("- 题目数量：%d 道" % len(items))
    out.append("- 总分 / 实得：%s / %s" % (fmt(total_full), fmt(total_got)))
    out.append("- 总得分率：%.1f%%" % (rate * 100))
    out.append("- 覆盖知识点：%d 个" % len(groups))
    out.append("")
    out.append("## 二、断点排序（按失分多少，不按得分率）")
    out.append("")
    out.append("| 排序 | 知识点 | 题数 | 满分 | 实得 | 得分率 | 失分 | 主码 | 性质 |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    for i, (name, g) in enumerate(ranked, 1):
        code = g["main_code"]
        label = CODE_LABELS[code][0] if code else band(g["rate"])[0]
        code_text = code or "-"
        out.append("| %d | %s | %d | %s | %s | %.0f%% | %s | %s | %s |"
                   % (i, name, g["n"], fmt(g["full"]), fmt(g["got"]),
                      g["rate"] * 100, fmt(g["lost"]), code_text, label))
    out.append("")
    out.append("## 三、错因码分布")
    out.append("")
    if codes:
        out.append("| 码 | 名称 | 命中题数 | 说明 |")
        out.append("|---|---|---|---|")
        for c, n in codes.most_common():
            out.append("| %s | %s | %d | %s |"
                       % (c, CODE_NAMES[c], n, CODE_ACTIONS[c][0].split("：")[0]))
        out.append("")
        main = codes.most_common(1)[0][0]
        out.append("**主码是 %s（%s）。**本轮训练只针对这一个码，其他码先记账不训练。"
                   % (main, CODE_NAMES[main]))
    else:
        out.append("这份 CSV 没填错因码。补上错因码，处方才能指到机制；"
                   "不填时下面按得分率推定。")
    out.append("")
    out.append("## 四、处方")
    out.append("")
    out.append("单次训练总时长上限 %d 分钟，按断点顺序做，做完到点就停。" % budget)
    out.append("")
    for i, (name, g) in enumerate(ranked, 1):
        p = prescription(g, budget)
        out.append("### %d. %s（失 %s 分）" % (i, name, fmt(g["lost"])))
        out.append("")
        out.append("- 性质：%s —— %s" % (p["label"], p["why"]))
        out.append("- 动作：%s" % p["action"])
        out.append("- 时长：%d 分钟" % p["mins"])
        out.append("- 依据：%s" % p["basis"])
        out.append("- 下次验收：%s" % p["accept"])
        out.append("")
    out.append("## 五、这周只做三件事")
    out.append("")
    for i, (name, g) in enumerate(ranked[:3], 1):
        out.append("%d. %s —— %s（%d 分钟）"
                   % (i, name, prescription(g, budget)["action"],
                      prescription(g, budget)["mins"]))
    out.append("")
    out.append("> 超过三条的处方一律不做。断点一次只补一个，补完再补下一个。")

    text = "\n".join(out)
    print(text)
    if md_path:
        with io.open(md_path, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print("\n[written] %s" % md_path, file=sys.stderr)
    return text


def fmt(v):
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return ("%.1f" % v).rstrip("0").rstrip(".")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Rank the breakpoints in a marked paper.")
    ap.add_argument("csv", nargs="?", help="CSV with 题号,知识点,分值,得分,错因码")
    ap.add_argument("--top", type=int, default=4, help="how many breakpoints to report")
    ap.add_argument("--md", help="also write the report to this path")
    ap.add_argument("--template", action="store_true", help="print a blank CSV template")
    args = ap.parse_args(argv)

    if args.template:
        sys.stdout.write(TEMPLATE)
        return 0
    if not args.csv:
        ap.print_help()
        return 2
    try:
        items = load(args.csv)
        render(items, max(1, args.top), args.md)
    except (OSError, ValueError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
