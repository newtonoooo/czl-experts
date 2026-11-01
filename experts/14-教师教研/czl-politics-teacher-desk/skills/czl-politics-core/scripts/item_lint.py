#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""试题文件检查器（纯标准库）。

用法:
    python item_lint.py <试题.md>

检查：题干/设问/答案/分档/干扰项/命题意图/材料来源/空答案/占位符。
退出码 0 = 无错误，1 = 有错误。
"""

import argparse
import re
import sys
from pathlib import Path

PLACEHOLDER = re.compile(r"\{\{[^}]{0,60}\}\}")
EMPTY_ANSWER = ["言之有理即可", "酌情给分", "意思对即可", "答案略", "略。", "其他答案合理即可"]
OPTION = re.compile(r"^\s*([A-D])[\.．、]\s*\S", re.M)


def split_items(text):
    """按 '## 第 N 题' 或 '---' 切题；没有标记则整体算一题。"""
    parts = re.split(r"^##\s*第\s*\d+\s*题.*$", text, flags=re.M)
    if len(parts) <= 1:
        return [text]
    return [p for p in parts[1:] if p.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    args = ap.parse_args()

    p = Path(args.path)
    if not p.exists():
        print(f"[FAIL] 文件不存在: {p}")
        return 1
    text = p.read_text(encoding="utf-8")
    errors, warns = [], []

    ph = PLACEHOLDER.findall(text)
    if ph:
        errors.append(f"残留占位符 {len(ph)} 处，例如 {ph[0]}")

    for w in EMPTY_ANSWER:
        if w in text:
            errors.append(f"出现空答案表述「{w}」，评分标准必须写分档与踩分点")

    items = split_items(text)
    print(f"识别到 {len(items)} 道题")

    for idx, it in enumerate(items, 1):
        tag = f"第 {idx} 题"
        if "设问" not in it:
            errors.append(f"{tag}：缺少「设问」")
        if "参考答案" not in it:
            errors.append(f"{tag}：缺少「参考答案」")

        opts = OPTION.findall(it)
        is_choice = len(opts) >= 3 or "选择" in it.split("设问")[0][-200:]
        if is_choice:
            if len(set(opts)) < 4:
                errors.append(f"{tag}：选择题选项不足四个（识别到 {sorted(set(opts))}）")
            if "干扰项" not in it:
                errors.append(f"{tag}：选择题缺少「干扰项分析」")
        else:
            if "分档" not in it:
                errors.append(f"{tag}：主观题缺少「分档评分标准」")
            if "踩分点" not in it:
                warns.append(f"{tag}：未见「踩分点」，请确认是否写在分档表内")

        if "命题意图" not in it:
            warns.append(f"{tag}：缺少「命题意图」")

        if not re.search(r"(摘自|据\s*《|来源[:：]|材料来源)", it):
            warns.append(f"{tag}：材料未见来源标注（摘自/据/来源）")

    print(f"\n错误：{len(errors)}　告警：{len(warns)}")
    for e in errors:
        print(f"  [ERROR] {e}")
    for w in warns:
        print(f"  [WARN ] {w}")
    if not errors:
        print("\n结论：机械检查通过（12 条命题硬伤仍需人工过一遍）")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
