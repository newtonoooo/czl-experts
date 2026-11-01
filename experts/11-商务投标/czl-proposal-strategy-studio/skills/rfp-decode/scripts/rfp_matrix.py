#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Scoring-table back-solve and disqualification scan for tender documents.

Two sub-commands:

1) matrix - turn a scoring table into a work matrix and rank by payoff.
   python rfp_matrix.py matrix items.csv [--md out.md]
   CSV header: item,score,evidence,section,owner
   (evidence may be empty; section may be empty)

   Empty evidence  -> flagged 缺证据
   Empty section   -> flagged 未落章
   Prints coverage, total points, and a writing order sorted by score.

2) scan - find disqualification candidates in the tender text.
   python rfp_matrix.py scan rfp.txt [--md out.md]
   Keywords: 否决 无效 废标 不予受理 不接受 不得 必须 应当 拒绝
   Prints one line per hit with the sentence it came from.

Exit codes: 0 ok, 2 invalid input.
"""
import csv
import re
import sys

DISQ_KEYWORDS = ["否决", "无效", "废标", "不予受理", "不接受", "不得", "拒绝", "视为放弃"]
MUST_KEYWORDS = ["必须", "应当", "须提供", "加盖", "密封", "原件"]


def out(text=""):
    sys.stdout.write(text + "\n")


def fail(msg):
    out("ERROR: " + msg)
    sys.exit(2)


def read_csv_rows(path):
    for enc in ("utf-8-sig", "gbk"):
        try:
            with open(path, "r", encoding=enc, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
        except FileNotFoundError:
            fail("找不到文件: %s" % path)
    fail("文件编码无法识别（试过 utf-8 / gbk）: %s" % path)


def to_num(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return 0.0


def cmd_matrix(path):
    rows = read_csv_rows(path)
    if not rows:
        fail("CSV 没有数据行")
    items = []
    for r in rows:
        name = (r.get("item") or "").strip()
        if not name:
            continue
        items.append({
            "item": name,
            "score": to_num(r.get("score")),
            "evidence": (r.get("evidence") or "").strip(),
            "section": (r.get("section") or "").strip(),
            "owner": (r.get("owner") or "").strip(),
        })
    if not items:
        fail("CSV 中没有任何 item 列内容")

    total = sum(i["score"] for i in items)
    no_ev = [i for i in items if not i["evidence"]]
    no_sec = [i for i in items if not i["section"]]
    big_no_ev = [i for i in no_ev if total and i["score"] / total >= 0.1]

    items.sort(key=lambda i: -i["score"])
    lines = ["# 得分点矩阵", ""]
    lines.append("| 写作顺序 | 得分点 | 分值 | 占比 | 现有证据 | 落章 | 责任人 |")
    lines.append("|---|---|---|---|---|---|---|")
    for n, i in enumerate(items, 1):
        share = (i["score"] / total * 100) if total else 0
        lines.append("| %d | %s | %.1f | %.0f%% | %s | %s | %s |" % (
            n, i["item"], i["score"], share,
            i["evidence"] or "**缺**", i["section"] or "**未落章**", i["owner"] or "-"))
    lines.append("")
    lines.append("**合计分值：%.1f**　得分点：%d 项" % (total, len(items)))
    lines.append("")
    lines.append("覆盖率：证据 %d/%d（%.0f%%），落章 %d/%d（%.0f%%）" % (
        len(items) - len(no_ev), len(items), (len(items) - len(no_ev)) / len(items) * 100,
        len(items) - len(no_sec), len(items), (len(items) - len(no_sec)) / len(items) * 100))
    if no_ev:
        lines.append("")
        lines.append("缺证据的得分点：%s" % "、".join(i["item"] for i in no_ev))
    if big_no_ev:
        lines.append("")
        lines.append("⚠️ 高价值但无证据（占比≥10%%）：%s —— 先补证据或考虑战略性放弃。" % "、".join(
            "%s（%.0f分）" % (i["item"], i["score"]) for i in big_no_ev))
    if no_sec:
        lines.append("")
        lines.append("未落章：%s" % "、".join(i["item"] for i in no_sec))
    return "\n".join(lines)


def split_sentences(text):
    parts = re.split(r"(?<=[。！？；\n])", text)
    return [p.strip() for p in parts if p and p.strip()]


def cmd_scan(path):
    try:
        raw = open(path, "r", encoding="utf-8", errors="replace").read()
    except FileNotFoundError:
        fail("找不到文件: %s" % path)
    sents = split_sentences(raw)
    disq, must = [], []
    for s in sents:
        if any(k in s for k in DISQ_KEYWORDS):
            disq.append(s)
        elif any(k in s for k in MUST_KEYWORDS):
            must.append(s)

    lines = ["# 否决项与硬性要求候选清单", ""]
    lines.append("文件：%s　句数：%d" % (path, len(sents)))
    lines.append("")
    lines.append("## 一、否决 / 废标 候选（%d 条）" % len(disq))
    lines.append("")
    if disq:
        for n, s in enumerate(disq, 1):
            lines.append("%d. %s" % (n, s))
    else:
        lines.append("未命中否决类关键词。注意：关键词命中率不等于风险为零，仍需人工通读「投标人须知」。")
    lines.append("")
    lines.append("## 二、硬性要求候选（%d 条）" % len(must))
    lines.append("")
    if must:
        for n, s in enumerate(must, 1):
            lines.append("%d. %s" % (n, s))
    else:
        lines.append("未命中硬性要求关键词。")
    lines.append("")
    lines.append("> 本清单由关键词抽取生成，只用于缩小人工复核范围，不能替代逐条核对原文。")
    return "\n".join(lines)


def main():
    argv = sys.argv[1:]
    if len(argv) < 2:
        out(__doc__)
        sys.exit(2)
    cmd, path = argv[0], argv[1]
    md_path = None
    if "--md" in argv:
        i = argv.index("--md")
        md_path = argv[i + 1] if i + 1 < len(argv) else None
    if cmd == "matrix":
        report = cmd_matrix(path)
    elif cmd == "scan":
        report = cmd_scan(path)
    else:
        out(__doc__)
        sys.exit(2)
    out(report)
    if md_path:
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(report + "\n")
        out("\n已写入: %s" % md_path)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
