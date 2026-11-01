#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2026 虫志龙. All rights reserved.
"""选题闸五维评分。

用法示例：
    python gate1_topic_scan.py --capacity 4 --diff 2 --reader 3 --rivals 4 --monetize 3
    python gate1_topic_scan.py --capacity 2 --diff 2 --reader 2 --rivals 3 --monetize 3 --json

每维 1-5 分，5 最好。评分口径见 references/G1-01。
"""
import argparse
import json
import sys

DIMS = [
    ("capacity", "赛道容量"),
    ("diff", "设定差异度"),
    ("reader", "读者画像匹配"),
    ("rivals", "同类近期表现"),
    ("monetize", "变现路径"),
]

WEAK = 2  # <=2 视为弱


def verdict(scores):
    weak = [k for k, _ in DIMS if scores[k] <= WEAK]
    if len(weak) >= 2:
        return "弃", weak
    if len(weak) == 1:
        return "调整后开", weak
    return "开", weak


def main():
    p = argparse.ArgumentParser(description="选题闸五维评分（每维 1-5 分）")
    for k, label in DIMS:
        p.add_argument("--" + k, type=int, required=True, help=label + "（1-5）")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    a = p.parse_args()

    scores = {}
    for k, _ in DIMS:
        v = getattr(a, k)
        if not 1 <= v <= 5:
            print("错误：--%s 必须在 1-5 之间，收到 %s" % (k, v), file=sys.stderr)
            return 2
        scores[k] = v

    result, weak = verdict(scores)
    weakest = min(scores, key=lambda k: scores[k])

    if a.json:
        print(json.dumps({
            "scores": scores,
            "verdict": result,
            "weak_dims": weak,
            "weakest": weakest,
            "note": "阈值为经验参考，非平台官方标准",
        }, ensure_ascii=False, indent=2))
        return 0

    print("选题闸 · 五维评分")
    print("-" * 34)
    for k, label in DIMS:
        bar = "#" * scores[k]
        flag = "  <- 弱" if scores[k] <= WEAK else ""
        print("%-10s %d  %s%s" % (label, scores[k], bar, flag))
    print("-" * 34)
    print("总分        %d/25" % sum(scores.values()))
    print("最弱一维    %s（%d 分）" % (dict(DIMS)[weakest], scores[weakest]))
    print("结论        %s" % result)
    if result == "弃":
        print("建议        五项中两项为弱，优先换题材；确要写请先看 G1-05 换核换壳")
    elif result == "调整后开":
        print("建议        先补最弱一维，再复评一次")
    else:
        print("建议        进开局闸，先做首屏 200 字压强测试")
    print()
    print("注：本阈值为经验参考，非平台官方标准。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
