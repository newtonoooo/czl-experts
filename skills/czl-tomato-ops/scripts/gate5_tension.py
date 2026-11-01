#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2026 虫志龙. All rights reserved.
"""主线张力余额盘查。

输入文件每行：承诺名,预计兑现章,难度(高/中/低),是否已兑现(1/0)
示例：
    拿回铺子,120,高,0
    查清母亲死因,80,中,1

用法：
    python gate5_tension.py --file promises.txt --current 95
"""
import argparse
import sys

WEIGHT = {"高": 2, "中": 1, "低": 1}


def main():
    p = argparse.ArgumentParser(description="主线张力余额盘查")
    p.add_argument("--file", required=True)
    p.add_argument("--current", type=int, required=True, help="当前写到第几章")
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
                name, due, diff, done = parts[0], int(parts[1]), parts[2], parts[3]
                if diff not in WEIGHT:
                    raise ValueError("第 %d 行难度必须是 高/中/低" % i)
                rows.append((name, due, diff, done == "1"))
    except (OSError, ValueError) as e:
        print("读取失败：%s" % e, file=sys.stderr)
        return 2

    open_items = [r for r in rows if not r[3]]
    balance = sum(WEIGHT[r[2]] for r in open_items)
    overdue = [r for r in open_items if r[1] <= a.current]

    if balance >= 4:
        verdict = "充足"
    elif balance >= 2:
        verdict = "偏薄"
    else:
        verdict = "见底"

    print("主线张力余额盘查（当前第 %d 章）" % a.current)
    print("-" * 40)
    print("承诺总数    %d" % len(rows))
    print("已兑现      %d" % (len(rows) - len(open_items)))
    print("未兑现      %d" % len(open_items))
    print("余额加权分  %d" % balance)
    if open_items:
        print()
        print("未兑现明细：")
        for name, due, diff, _ in open_items:
            mark = "  [已过期]" if due <= a.current else ""
            print("  %-16s 预计第 %3d 章  难度%s%s" % (name, due, diff, mark))
    print("-" * 40)
    print("判定        %s" % verdict)
    if verdict == "见底":
        print("建议        停止加新设定；把已有承诺拆成阶段目标，或进 G5-07 评估收尾")
    elif verdict == "偏薄":
        print("建议        补中层目标（拆阶段），不要靠引入新角色续命")
    else:
        print("建议        正常推进；每兑现一个，补一个新的小承诺维持余额")
    if overdue:
        print()
        print("警告        有过期承诺 %d 条，读者会认为作者忘了" % len(overdue))
    return 0


if __name__ == "__main__":
    sys.exit(main())
