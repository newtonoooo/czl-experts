#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2026 虫志龙. All rights reserved.
"""书评区情绪读法（关键词归类）。

输入：每行一条评论。用法：
    python gate4_sentiment.py --file comments.txt

归类规则为关键词初筛，需人工抽查复核。
"""
import argparse
import sys

RULES = [
    ("二创", ["画了", "同人", "二创", "剪辑", "配音", "手书"]),
    ("设定争论", ["战力", "设定", "时间线", "不合理", "bug", "崩了", "逻辑"]),
    ("剧情争论", ["该和", "站", "cp", "谁对", "应该选", "气死", "洗白"]),
    ("纯夸", ["好看", "支持", "加油", "追了", "喜欢", "催更"]),
    ("负面", ["弃了", "垃圾", "退钱", "难看", "别写", "失望"]),
]


def classify(line):
    low = line.lower()
    for name, words in RULES:
        if any(w in low for w in words):
            return name
    return "其他"


def main():
    p = argparse.ArgumentParser(description="书评区情绪读法")
    p.add_argument("--file", required=True)
    a = p.parse_args()

    try:
        with open(a.file, encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
    except OSError as e:
        print("读取失败：%s" % e, file=sys.stderr)
        return 2

    if not lines:
        print("评论为空。", file=sys.stderr)
        return 2

    counts = {}
    for l in lines:
        k = classify(l)
        counts[k] = counts.get(k, 0) + 1

    n = len(lines)
    story = counts.get("剧情争论", 0)
    setting = counts.get("设定争论", 0)
    neg = counts.get("负面", 0)
    fan = counts.get("二创", 0)

    setting_ratio = setting / n
    real_engage = (story + fan) / n

    if setting_ratio >= 0.3:
        polarity = "危险（设定失守）"
        action = "优先修逻辑，用正文回应，不在评论区辩论"
    elif real_engage >= 0.2 or fan > 0:
        polarity = "健康（读者投入）"
        action = "保持不动，可顺着争论推进后续剧情"
    elif neg / n >= 0.4:
        polarity = "偏冷（口碑受损）"
        action = "回 G3-08 找掉量原因，不要先改简介"
    else:
        polarity = "中性偏冷"
        action = "补冲突，制造可站队的立场"

    print("书评区情绪读法（样本 %d 条）" % n)
    print("-" * 38)
    for k in ["剧情争论", "设定争论", "二创", "纯夸", "负面", "其他"]:
        print("%-6s %3d 条  %s" % (k, counts.get(k, 0), "#" * counts.get(k, 0)))
    print("-" * 38)
    print("极性    %s" % polarity)
    print("动作    %s" % action)
    print()
    print("注：关键词初筛，请抽查原文复核；读者骂主角但不弃书属于正向信号。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
