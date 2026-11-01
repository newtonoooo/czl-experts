#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2026 虫志龙. All rights reserved.
"""改编适配度评分（五项，满分 25）。

用法：
    python gate6_adapt_score.py --visual 4 --unit 3 --scene 2 --character 4 --genre 5
"""
import argparse
import sys

DIMS = [
    ("visual", "场景可视度", "有多少场景能直接拍（不靠旁白解释）"),
    ("unit", "单元结构", "能否切成 3-5 分钟的独立单元"),
    ("scene", "名场面密度", "每 30 章有几个能剪成片花的场面"),
    ("character", "人物辨识度", "主要角色能否靠外形+一句话被记住"),
    ("genre", "题材适配", "题材是否在改编需求范围内"),
]


def main():
    p = argparse.ArgumentParser(description="改编适配度评分")
    for k, label, _ in DIMS:
        p.add_argument("--" + k, type=int, required=True, help=label + "（1-5）")
    a = p.parse_args()

    scores = {}
    for k, label, _ in DIMS:
        v = getattr(a, k)
        if not 1 <= v <= 5:
            print("错误：--%s 必须在 1-5 之间" % k, file=sys.stderr)
            return 2
        scores[k] = v

    total = sum(scores.values())
    if total >= 20:
        verdict = "高（可主动推改编）"
    elif total >= 15:
        verdict = "中（先补短板再谈）"
    else:
        verdict = "低（不建议主动推）"

    print("改编适配度评分")
    print("-" * 46)
    for k, label, hint in DIMS:
        print("%-10s %d/5   %s" % (label, scores[k], hint))
    print("-" * 46)
    print("总分   %d/25" % total)
    print("判定   %s" % verdict)

    weak = [(label, scores[k]) for k, label, _ in DIMS if scores[k] <= 2]
    if weak:
        print()
        print("短板：" + "、".join("%s(%d)" % (n, s) for n, s in weak))
        print("补法：每卷补 3 个可拍场景 + 2 个名场面；把心理描写改成动作与对话")
    return 0


if __name__ == "__main__":
    sys.exit(main())
