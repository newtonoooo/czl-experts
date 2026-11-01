#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2026 虫志龙. All rights reserved.
"""同类作品近期表现读取。

输入文件每行：书名,是否仍在更新(1/0),当前字数万,是否进过推荐(1/0)
示例：
    甲书,1,58,1
    乙书,0,12,0

用法：
    python gate1_rival_read.py --file rivals.txt
"""
import argparse
import sys


def parse(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [x.strip() for x in line.split(",")]
            if len(parts) < 4:
                raise ValueError("第 %d 行字段不足 4 个：%s" % (i, line))
            name, upd, words, rec = parts[0], parts[1], parts[2], parts[3]
            rows.append({
                "name": name,
                "updating": upd == "1",
                "words": float(words),
                "recommended": rec == "1",
            })
    return rows


def main():
    p = argparse.ArgumentParser(description="同类作品近期表现读取")
    p.add_argument("--file", required=True, help="样本文件路径")
    a = p.parse_args()

    try:
        rows = parse(a.file)
    except (OSError, ValueError) as e:
        print("读取失败：%s" % e, file=sys.stderr)
        return 2

    n = len(rows)
    if n == 0:
        print("样本为空。", file=sys.stderr)
        return 2

    upd = sum(1 for r in rows if r["updating"])
    rec = sum(1 for r in rows if r["recommended"])
    longrun = sum(1 for r in rows if r["words"] >= 30)
    upd_rate = upd / n
    rec_rate = rec / n
    long_rate = longrun / n

    signals = 0
    if rec_rate < 0.2:
        signals += 1
    if upd_rate < 0.5:
        signals += 1
    if long_rate < 0.3:
        signals += 1

    trend = "上升" if signals == 0 else ("平稳" if signals == 1 else "退潮")
    advice = "进场" if trend == "上升" else ("观望 1 个月后再判" if trend == "平稳" else "绕开")

    print("同类样本：%d 本" % n)
    print("-" * 34)
    print("仍在更新     %d 本（%.0f%%）" % (upd, upd_rate * 100))
    print("进过推荐     %d 本（%.0f%%）" % (rec, rec_rate * 100))
    print("写到 30 万字 %d 本（%.0f%%）" % (longrun, long_rate * 100))
    print("-" * 34)
    print("退潮信号     %d 项" % signals)
    print("趋势判定     %s" % trend)
    print("建议         %s" % advice)
    print()
    print("注：阈值（20% / 50% / 30%）为经验参考，非平台官方标准。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
