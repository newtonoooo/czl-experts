#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2026 虫志龙. All rights reserved.
"""支线回收率统计。

输入文件每行：支线名,状态
状态取值：已回收 / 半回收 / 未回收 / 作废

用法：
    python gate5_thread_close.py --file threads.txt
"""
import argparse
import sys

VALID = ["已回收", "半回收", "未回收", "作废"]


def main():
    p = argparse.ArgumentParser(description="支线回收率统计")
    p.add_argument("--file", required=True)
    a = p.parse_args()

    rows = []
    try:
        with open(a.file, encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = [x.strip() for x in line.split(",")]
                if len(parts) < 2:
                    raise ValueError("第 %d 行字段不足" % i)
                if parts[1] not in VALID:
                    raise ValueError("第 %d 行状态非法：%s（应为 %s）"
                                     % (i, parts[1], "/".join(VALID)))
                rows.append((parts[0], parts[1]))
    except (OSError, ValueError) as e:
        print("读取失败：%s" % e, file=sys.stderr)
        return 2

    if not rows:
        print("没有有效数据。", file=sys.stderr)
        return 2

    c = {k: sum(1 for _, s in rows if s == k) for k in VALID}
    rate = (c["已回收"] + c["作废"]) / len(rows)

    print("支线回收率统计（%d 条）" % len(rows))
    print("-" * 38)
    for k in VALID:
        print("%-6s %3d 条" % (k, c[k]))
    print("-" * 38)
    print("回收率  %.0f%%（合格线 70%%）" % (rate * 100))
    if rate >= 0.7:
        print("判定    合格")
    else:
        print("判定    不合格")
        if c["未回收"]:
            print("处理    未回收的按「能否 3 章内交代」分类，不能交代的明确作废")
    if c["半回收"]:
        print("提醒    半回收 %d 条，补一句交代即可，成本最低" % c["半回收"])
    return 0 if rate >= 0.7 else 1


if __name__ == "__main__":
    sys.exit(main())
