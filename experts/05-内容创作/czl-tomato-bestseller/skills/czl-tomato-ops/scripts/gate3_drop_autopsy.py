#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2026 虫志龙. All rights reserved.
"""掉量解剖：从数据到章号。

输入文件每行：章号,留存率（百分比或小数均可）
示例：
    1,88
    2,76
    3,71
    4,43
    5,39

用法：
    python gate3_drop_autopsy.py --file retention.txt --top 3
"""
import argparse
import sys


def load(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [x.strip() for x in line.split(",")]
            if len(parts) < 2:
                raise ValueError("第 %d 行字段不足" % i)
            try:
                ch = int(parts[0])
                v = float(parts[1])
            except ValueError:
                raise ValueError("第 %d 行数值无法解析" % i)
            if v > 1:
                v = v / 100.0
            rows.append((ch, v))
    return rows


def main():
    p = argparse.ArgumentParser(description="掉量解剖：定位拐点")
    p.add_argument("--file", required=True)
    p.add_argument("--top", type=int, default=3, help="输出前 N 个跌幅点，默认 3")
    p.add_argument("--lookback", type=int, default=3, help="往回看 N 章，默认 3")
    a = p.parse_args()

    try:
        rows = load(a.file)
    except (OSError, ValueError) as e:
        print("读取失败：%s" % e, file=sys.stderr)
        return 2

    if len(rows) < 3:
        print("数据太少（至少 3 章）。", file=sys.stderr)
        return 2

    deltas = []
    for i in range(1, len(rows)):
        prev_ch, prev_v = rows[i - 1]
        cur_ch, cur_v = rows[i]
        deltas.append((cur_ch, cur_v - prev_v))

    drops = sorted([d for d in deltas if d[1] < 0], key=lambda x: x[1])[:a.top]

    print("掉量解剖（%d 章样本）" % len(rows))
    print("-" * 40)
    first = rows[0][1]
    last = rows[-1][1]
    print("首章留存 %.1f%%  末章留存 %.1f%%  总衰减 %.1f 个百分点"
          % (first * 100, last * 100, (first - last) * 100))
    print("-" * 40)
    if not drops:
        print("未发现下跌点。")
        return 0

    print("主要拐点：")
    for ch, d in drops:
        start = max(1, ch - a.lookback)
        print("  第 %d 章   跌 %.1f 个百分点   回看第 %d-%d 章的章末"
              % (ch, abs(d) * 100, start, ch))

    earliest = min(drops, key=lambda x: x[0])[0]
    print("-" * 40)
    print("优先处理：第 %d 章之前（原因永远在拐点之前）" % earliest)
    print("归因四项：钩子弱 / 增量低 / 情绪断供 / 设定混乱")
    print("纪律：一次只改一到两处，改完观察 7 天再动第二次")
    print()
    print("注：留存为平台后台指标，口径以后台展示为准。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
