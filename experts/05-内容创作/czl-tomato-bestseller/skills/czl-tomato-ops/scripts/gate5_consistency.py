#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2026 虫志龙. All rights reserved.
"""设定与战力自洽校验（数值跳变检测）。

输入文件每行：角色,章号,数值,正文是否有解释(1/0)
示例：
    主角,10,100,1
    主角,45,900,0

用法：
    python gate5_consistency.py --file power.txt --jump 0.4
"""
import argparse
import sys


def main():
    p = argparse.ArgumentParser(description="战力跳变检测")
    p.add_argument("--file", required=True)
    p.add_argument("--jump", type=float, default=0.4, help="跳变阈值（比例），默认 0.4")
    a = p.parse_args()

    rows = []
    try:
        with open(a.file, encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = [x.strip() for x in line.split(",")]
                if len(parts) < 4:
                    raise ValueError("第 %d 行字段不足 4 个" % i)
                rows.append((parts[0], int(parts[1]), float(parts[2]), parts[3] == "1"))
    except (OSError, ValueError) as e:
        print("读取失败：%s" % e, file=sys.stderr)
        return 2

    if len(rows) < 2:
        print("数据太少。", file=sys.stderr)
        return 2

    by_char = {}
    for name, ch, val, expl in rows:
        by_char.setdefault(name, []).append((ch, val, expl))

    anomalies = []
    for name, series in by_char.items():
        series.sort()
        for i in range(1, len(series)):
            ch, val, expl = series[i]
            pch, pval, _ = series[i - 1]
            if pval <= 0:
                continue
            ratio = (val - pval) / pval
            if abs(ratio) >= a.jump and not expl:
                anomalies.append((name, pch, pval, ch, val, ratio))

    print("设定与战力自洽校验（%d 条记录 / %d 个角色）" % (len(rows), len(by_char)))
    print("-" * 44)
    if not anomalies:
        print("未发现无解释的跳变。")
        print("注意：本脚本只查数值跳变，规则反复与世界规则总量需人工核对。")
        return 0

    print("无解释跳变 %d 处：" % len(anomalies))
    for name, pch, pval, ch, val, ratio in anomalies:
        print("  %s  第 %d 章 %.0f -> 第 %d 章 %.0f（%+.0f%%）"
              % (name, pch, pval, ch, val, ratio * 100))
    print("-" * 44)
    print("处理  每处补一句原因（突破/代价/外力），或在前文补一个铺垫")
    print("纪律  连续 3 处以上无法解释，按 G5-03 判定为设定崩坏")
    return 1


if __name__ == "__main__":
    sys.exit(main())
