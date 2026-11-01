#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""qa_gate.py —— 交付前的结构质检门（纯标准库，零依赖）。

它检查的不是"写得好不好"，而是"该有的有没有、对不上的地方在哪"：
    · 占位符没填（〔 〕、TODO、XXX）
    · 题号与答案数量对不上
    · 分值加不到目标分
    · 教案时间预算不等于课时
    · 表格列数不齐
    · 公式符号成对（$ 与 **）
    · 空话套话（"引导学生体会""激发学习兴趣"这类）

用法：
    python bin/qa_gate.py 教案.md --kind lesson --minutes 45
    python bin/qa_gate.py 试卷.md --kind paper --total 150
    python bin/qa_gate.py 报告.md --kind report
    python bin/qa_gate.py 学案.md --kind explain
    python bin/qa_gate.py 任意.md --kind generic

退出码：0 通过（可能有警告）；1 有错误。
"""

import argparse
import os
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

PLACEHOLDER_PATTERNS = [
    (re.compile(r"〔[^〕]{0,40}〕"), "未填写的〔 〕占位"),
    (re.compile(r"\[TODO[^\]]*\]", re.I), "[TODO] 未处理"),
    (re.compile(r"\bXXX\b"), "XXX 未替换"),
    (re.compile(r"（此处[^）]{0,20}）"), "括号内待补说明"),
]

# 空话套话：放在任何一节课都成立，等于没写
HOLLOW_PHRASES = [
    "引导学生体会", "激发学生兴趣", "激发学习兴趣", "培养学生核心素养",
    "旨在培养", "让学生在轻松愉快", "充分发挥学生的主体作用",
    "体现新课改理念", "落实立德树人",
]

REQUIRED_SECTIONS = {
    "lesson": [
        ("教学目标", [r"教学目标"]),
        ("重点难点", [r"重点", r"难点"]),
        ("教学过程", [r"教学过程", r"教学环节"]),
        ("板书设计", [r"板书"]),
        ("作业", [r"作业"]),
    ],
    "paper": [
        ("答案部分", [r"参考答案", r"答案"]),
        ("评分细则或解析", [r"评分", r"解析", r"解答"]),
    ],
    "report": [
        ("数据表", [r"\|"]),
        ("口径说明", [r"口径"]),
    ],
    "explain": [
        ("概念或定义", [r"概念", r"定义"]),
        ("例题", [r"例题", r"例\s*\d"]),
        ("易错", [r"易错", r"错法"]),
        ("变式", [r"变式"]),
    ],
    "generic": [],
}


def read(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read()


def check_tables(lines):
    """表格列数一致性。"""
    errs = []
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("|") and i + 1 < len(lines) and re.match(
                r"^\s*\|?[\s:\-|]+\|[\s:\-|]*$", lines[i + 1]):
            head = [c for c in lines[i].strip().strip("|").split("|")]
            n = len(head)
            start = i + 1
            while i < len(lines) and lines[i].strip().startswith("|"):
                cols = len(lines[i].strip().strip("|").split("|"))
                if cols != n:
                    errs.append("第 %d 行表格列数 %d，与表头 %d 不一致" % (i + 1, cols, n))
                i += 1
            if i - start < 2:
                errs.append("第 %d 行起的表格只有表头，没有数据行" % (start + 1))
        else:
            i += 1
    return errs


def check_paper(text):
    errs, warns = [], []
    # 题号：以 **N.** 或 N. 开头的行
    nums = re.findall(r"^\s*\*\*(\d{1,2})[.．]", text, re.M)
    if not nums:
        nums = re.findall(r"^\s*(\d{1,2})[.．]\s*\S", text, re.M)
    if nums:
        seq = [int(x) for x in nums]
        if seq != list(range(1, len(seq) + 1)):
            errs.append("题号不连续或重复：%s" % ",".join(map(str, seq)))

    # 选择题答案表
    m = re.search(r"\|\s*题号\s*\|(.+?)\n\|\s*-{2,}.*?\n\|(.+?)\n", text)
    if m:
        qn = [c.strip() for c in m.group(1).strip().strip("|").split("|") if c.strip()]
        an = [c.strip() for c in m.group(2).strip().strip("|").split("|") if c.strip()]
        if len(qn) != len(an):
            errs.append("答案表题号 %d 列，答案 %d 列，对不上" % (len(qn), len(an)))
        empty = [q for q, a in zip(qn, an) if a in ("", "〔", "〕")]
        if empty:
            warns.append("答案表中题号 %s 的答案为空" % "、".join(empty))

    # 分值合计
    marks = [int(x) for x in re.findall(r"[（(]\s*(\d{1,3})\s*分\s*[）)]", text)]
    if marks:
        total = sum(marks)
        if total < 40:
            warns.append("文中标注分值的合计仅 %d 分，请确认是否漏标" % total)

    # 选择题选项完整性
    for block in re.findall(r"(?m)^\*\*\d+[.．]\*\*.*$", text):
        if ("A." in block or "A．" in block) and not ("D." in block or "D．" in block):
            errs.append("选择题选项不足四个：%s" % block[:30])
    return errs, warns


def time_from_table(lines):
    """从"时长"列求和。优先用表格，因为正文里的 ′ 可能是在举例子。"""
    i = 0
    while i < len(lines) - 1:
        if lines[i].strip().startswith("|") and re.match(r"^\s*\|?[\s:\-|]+\|[\s:\-|]*$", lines[i + 1]):
            header = [c.strip() for c in lines[i].strip().strip("|").split("|")]
            idx = next((k for k, h in enumerate(header) if "时长" in h), None)
            if idx is not None:
                total, found = 0, False
                j = i + 2
                while j < len(lines) and lines[j].strip().startswith("|"):
                    cells = [c.strip() for c in lines[j].strip().strip("|").split("|")]
                    if idx < len(cells):
                        m = re.match(r"^(\d{1,3})", cells[idx])
                        if m:
                            total += int(m.group(1))
                            found = True
                    j += 1
                if found:
                    return total
                i = j
                continue
            while i < len(lines) and lines[i].strip().startswith("|"):
                i += 1
            continue
        i += 1
    return None


def check_lesson(text, minutes, lines=None):
    errs, warns = [], []
    lines = lines or text.split("\n")
    total = time_from_table(lines)
    loose = False
    if total is None:
        times = [int(x) for x in re.findall(r"(\d{1,3})\s*[′']", text)]
        if times:
            total = sum(times)
            loose = True
        else:
            warns.append("没有找到时间标注（如 5′）或『时长』列，无法核对课时")

    if total is not None:
        if minutes and not loose and abs(total - minutes) > minutes * 0.15:
            errs.append("时间合计 %d 分钟，与课时 %d 分钟相差超过 15%%" % (total, minutes))
        elif minutes and loose and abs(total - minutes) > minutes * 0.15:
            warns.append("正文中 ′ 标注合计 %d 分钟（可能含举例），请确认时间预算表" % total)
        elif not minutes and (total < 30 or total > 60):
            warns.append("时间合计 %d 分钟，不像一节常规课（40–50 分钟）" % total)

    if text.count("?") + text.count("？") < 3:
        warns.append("问句少于 3 个，问题链可能没展开")

    for k in ("基础", "提高", "挑战"):
        if k not in text:
            warns.append("作业缺少『%s』档" % k)
    return errs, warns


def check_report(text):
    errs, warns = [], []
    if "得分率" not in text:
        warns.append("报告中未出现『得分率』，可能没做分题统计")
    if not re.search(r"参考人数|样本|人数", text):
        warns.append("报告未说明样本量")
    if re.search(r"(整体情况良好|仍需努力|再接再厉)", text):
        warns.append("出现空泛评语（'整体情况良好''仍需努力'），建议改成数据或具体动作")
    # 数据一致性：表格里的百分比
    for pct in re.findall(r"(\d{1,3}(?:\.\d+)?)\s*%", text):
        if float(pct) > 100:
            errs.append("百分比超过 100%%：%s%%" % pct)
    return errs, warns


def main():
    ap = argparse.ArgumentParser(description="交付前结构质检")
    ap.add_argument("file", help="待检 Markdown")
    ap.add_argument("--kind", default="generic",
                    choices=["lesson", "paper", "report", "explain", "generic"])
    ap.add_argument("--minutes", type=int, default=None, help="课时长度（分钟），用于核对时间预算")
    ap.add_argument("--total", type=float, default=None, help="试卷目标总分")
    ap.add_argument("--strict", action="store_true", help="把警告也当错误")
    args = ap.parse_args()

    if not os.path.isfile(args.file):
        raise SystemExit("错误：找不到文件 %s" % args.file)

    text = read(args.file)
    lines = text.replace("\r\n", "\n").split("\n")
    errs, warns = [], []

    for pat, label in PLACEHOLDER_PATTERNS:
        hits = pat.findall(text)
        if hits:
            errs.append("%s ×%d：%s" % (label, len(hits), "、".join(hits[:3])))

    for p in HOLLOW_PHRASES:
        if p in text:
            warns.append("空话套话：『%s』——换成具体动作或删掉" % p)

    for name, pats in REQUIRED_SECTIONS[args.kind]:
        if not any(re.search(p, text) for p in pats):
            errs.append("缺少必备部分：%s" % name)

    errs += check_tables(lines)

    if text.count("**") % 2 != 0:
        warns.append("** 个数为奇数（%d），可能有未闭合的加粗" % text.count("**"))
    if text.count("$") % 2 != 0:
        warns.append("$ 个数为奇数（%d），可能有未闭合的公式" % text.count("$"))

    if args.kind == "paper":
        e, w = check_paper(text)
        errs += e
        warns += w
        if args.total:
            m = re.search(r"满分[^0-9]{0,6}(\d{2,3})", text)
            if m and abs(float(m.group(1)) - args.total) > 0.5:
                errs.append("卷面标注满分 %s，与目标 %g 不符" % (m.group(1), args.total))
    elif args.kind == "lesson":
        e, w = check_lesson(text, args.minutes, lines)
        errs += e
        warns += w
    elif args.kind == "report":
        e, w = check_report(text)
        errs += e
        warns += w

    print("质检文件：%s（类型：%s）" % (args.file, args.kind))
    print("-" * 52)
    if not errs and not warns:
        print("✅ 全部通过，没有发现问题。")
    for e in errs:
        print("  [错误] %s" % e)
    for w in warns:
        print("  [警告] %s" % w)
    print("-" * 52)
    print("错误 %d 项，警告 %d 项。" % (len(errs), len(warns)))

    sys.exit(1 if (errs or (args.strict and warns)) else 0)


if __name__ == "__main__":
    main()
