#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audit every claim in a proposal draft for an evidence level tag.

Usage:
    python claim_audit.py draft.md [--strict] [--md out.md]

Tag convention inside the draft: [E1] [E2] [E3] [E4] (full-width brackets ok)
  E1 客户侧可核实数据（客户提供的报表、现场实测、合同条款）
  E2 同类项目实证（可提供联系人/验收单的案例）
  E3 方法可复现（标准、流程、工具，任何人照做能复现）
  E4 假设（尚未验证的判断，必须写"预计/计划"）

A sentence counts as a claim when it contains a number or an assertive verb.
Exit: 0 ok, 1 strict-mode failure, 2 invalid input.
"""
import re
import sys

ASSERTIVE = ["提供", "实现", "提升", "降低", "减少", "保证", "确保", "支持", "覆盖",
             "完成", "达到", "节省", "缩短", "满足", "通过", "获得", "领先", "稳定",
             "兼容", "响应", "承担", "承诺"]
EMPTY_WORDS = ["行业领先", "国内领先", "一流", "顶尖", "全方位", "全维度", "深度赋能",
               "极致", "颠覆", "完美", "最强", "最佳", "唯一", "首创", "闭环生态"]
E_TAG = re.compile(r"[\[【（(]\s*E([1-4])\s*[\]】）)]")


def out(text=""):
    sys.stdout.write(text + "\n")


def main():
    argv = sys.argv[1:]
    if not argv:
        out(__doc__)
        sys.exit(2)
    path = argv[0]
    strict = "--strict" in argv
    md = None
    if "--md" in argv:
        i = argv.index("--md")
        md = argv[i + 1] if i + 1 < len(argv) else None

    try:
        text = open(path, "r", encoding="utf-8", errors="replace").read()
    except FileNotFoundError:
        out("ERROR: 找不到文件: %s" % path)
        sys.exit(2)

    lines = text.split("\n")
    claims = []
    for ln, line in enumerate(lines, 1):
        if line.strip().startswith("#"):
            continue
        for s in re.split(r"(?<=[。！？；])", line):
            s = s.strip()
            if len(s) < 8:
                continue
            has_digit = bool(re.search(r"\d", s))
            has_verb = any(v in s for v in ASSERTIVE)
            if not (has_digit or has_verb):
                continue
            tags = E_TAG.findall(s)
            claims.append({"line": ln, "text": s, "tags": tags})

    tagged = [c for c in claims if c["tags"]]
    untagged = [c for c in claims if not c["tags"]]
    e4 = [c for c in claims if "4" in c["tags"]]
    empty_hits = sum(text.count(w) for w in EMPTY_WORDS)
    total = len(claims)
    ratio = (len(untagged) / total) if total else 0.0

    report = ["# 主张体检", ""]
    report.append("文件：%s" % path)
    report.append("")
    report.append("| 指标 | 数值 |")
    report.append("|---|---|")
    report.append("| 主张句 | %d |" % total)
    report.append("| 已标证据 | %d |" % len(tagged))
    report.append("| 未标证据 | %d |" % len(untagged))
    report.append("| 未标比例 | %.0f%% |" % (ratio * 100))
    report.append("| E4 假设 | %d |" % len(e4))
    report.append("| 空词出现 | %d 次 |" % empty_hits)
    report.append("")

    if untagged:
        report.append("## 未标证据的主张（前 15 条）")
        report.append("")
        for c in untagged[:15]:
            report.append("- L%d：%s" % (c["line"], c["text"][:120]))
        report.append("")
    if e4:
        report.append("## E4 假设（交付前确认表述含「预计/计划/待验证」）")
        report.append("")
        for c in e4[:10]:
            report.append("- L%d：%s" % (c["line"], c["text"][:120]))
        report.append("")

    verdict = []
    if ratio > 0.4:
        verdict.append("未标比例 %.0f%%，超过 40%% 的上限：评委任取一句追问依据，方案就会塌。" % (ratio * 100))
    if empty_hits:
        verdict.append("空词出现 %d 次，逐个删掉或换成数字/动作。" % empty_hits)
    if not verdict:
        verdict.append("主张标注密度合格。仍需抽查：标了 E1/E2 的句子，证据文件是否真的在手。")
    report.extend(["## 结论", ""] + ["- " + v for v in verdict])
    report.append("")
    report.append("> 本检查只看标注是否存在，不判断证据真假。E1/E2 必须有可提供的原始材料，否则应降为 E4。")

    result = "\n".join(report)
    out(result)
    if md:
        with open(md, "w", encoding="utf-8") as f:
            f.write(result + "\n")
        out("\n已写入: %s" % md)
    if strict and ratio > 0.4:
        sys.exit(1)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
