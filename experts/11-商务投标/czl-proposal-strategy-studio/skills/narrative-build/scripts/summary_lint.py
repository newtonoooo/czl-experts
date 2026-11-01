#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lint an executive summary: structure, length, evidence density, empty words.

Usage:
    python summary_lint.py summary.md [--anchor 某某医院] [--max 700]

Checks:
  C1 非空白字数 <= max (default 700)
  C2 段落数 4-8（五段式：处境/张力/主张/证据/交付后状态）
  C3 首段出现客户锚点（传 --anchor 时）
  C4 全文数字 >= 2（没有数字的摘要通常在讲态度）
  C5 空词命中数 == 0
  C6 首段不以「我们高度重视/秉承/致力于/随着」开头
  C7 任一段落不超过 260 字（评委不会读长段）

Exit codes: 0 pass, 1 fail, 2 invalid input.
"""
import re
import sys

EMPTY_WORDS = ["行业领先", "国内领先", "一流", "顶尖", "全方位", "全维度", "深度赋能",
               "极致", "颠覆", "完美", "最强", "最佳", "唯一", "首创", "闭环生态"]
BAD_OPENERS = ["我们高度重视", "我公司高度重视", "秉承", "致力于", "随着", "在当今", "近年来"]


def out(text=""):
    sys.stdout.write(text + "\n")


def load_text(path):
    try:
        return open(path, "r", encoding="utf-8", errors="replace").read()
    except FileNotFoundError:
        out("ERROR: 找不到文件: %s" % path)
        sys.exit(2)


def main():
    argv = sys.argv[1:]
    if not argv:
        out(__doc__)
        sys.exit(2)
    path = argv[0]
    anchor = ""
    max_chars = 700
    if "--anchor" in argv:
        i = argv.index("--anchor")
        anchor = argv[i + 1] if i + 1 < len(argv) else ""
    if "--max" in argv:
        i = argv.index("--max")
        try:
            max_chars = int(argv[i + 1])
        except (IndexError, ValueError):
            out("ERROR: --max 需要一个整数")
            sys.exit(2)

    text = load_text(path)
    body = re.sub(r"^#.*$", "", text, flags=re.M)
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    plain = re.sub(r"\s", "", body)
    n_chars = len(plain)
    digits = len(re.findall(r"\d+(?:\.\d+)?", body))
    hits = [w for w in EMPTY_WORDS if w in body]
    long_paras = [(n, len(re.sub(r"\s", "", p))) for n, p in enumerate(paras, 1)
                  if len(re.sub(r"\s", "", p)) > 260]

    results = []
    results.append(("C1 字数", n_chars <= max_chars, "%d 字（上限 %d）" % (n_chars, max_chars)))
    results.append(("C2 段落数", 4 <= len(paras) <= 8, "%d 段（建议 5 段）" % len(paras)))
    if anchor:
        first = paras[0] if paras else ""
        results.append(("C3 客户锚点", anchor in first, "首段%s出现「%s」" % (
            "已" if anchor in first else "未", anchor)))
    results.append(("C4 数字密度", digits >= 2, "%d 处数字（建议 ≥2）" % digits))
    results.append(("C5 空词", not hits, "命中：%s" % ("、".join(hits) if hits else "无")))
    first = paras[0] if paras else ""
    bad = [o for o in BAD_OPENERS if first.startswith(o)]
    results.append(("C6 开场", not bad, "以「%s」开头" % bad[0] if bad else "开场直接说客户的事"))
    results.append(("C7 段落长度", not long_paras, "超 260 字的段落：%s" % (
        "、".join("第%d段(%d字)" % p for p in long_paras) if long_paras else "无")))

    lines = ["# 执行摘要体检", "", "文件：%s" % path, ""]
    lines.append("| 检查项 | 结果 | 说明 |")
    lines.append("|---|---|---|")
    for name, ok, detail in results:
        lines.append("| %s | %s | %s |" % (name, "PASS" if ok else "FAIL", detail))
    fails = [r for r in results if not r[1]]
    lines.append("")
    if fails:
        lines.append("**未通过 %d 项。**" % len(fails))
        lines.append("")
        lines.append("改法建议：")
        tips = {
            "C1": "砍掉背景铺垫，只留客户处境、张力、主张、证据、结果五件事。",
            "C2": "五段式：处境 / 张力 / 主张 / 证据 / 交付后状态。缺哪段补哪段。",
            "C3": "首段第一句就写客户和项目，别先介绍自己公司。",
            "C4": "把形容词换成数字：停机几小时、省多少钱、多少天上线。",
            "C5": "删掉空词，换成可验证的动作或结果。",
            "C6": "删掉开场套话，直接从客户的麻烦写起。",
            "C7": "长段拆成两三段，每段只讲一件事。",
        }
        for name, _, _ in fails:
            code = name.split()[0]
            lines.append("- %s：%s" % (name, tips.get(code, "按检查项说明修改。")))
    else:
        lines.append("**全部通过。** 仍需人工确认：这段摘要能不能单独当一页纸给人看。")
    out("\n".join(lines))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
