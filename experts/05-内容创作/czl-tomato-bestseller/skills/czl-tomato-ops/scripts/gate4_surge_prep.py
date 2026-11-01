#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2026 虫志龙. All rights reserved.
"""推荐窗口承接准备清单。

用法：
    python gate4_surge_prep.py --selfcheck 8 --stock 5 --intro-lines 3 --title-ok 1
"""
import argparse
import sys


def main():
    p = argparse.ArgumentParser(description="推荐窗口承接准备清单")
    p.add_argument("--selfcheck", type=int, required=True, help="G2-07 自检通过项数（0-8）")
    p.add_argument("--stock", type=int, required=True, help="存稿章数")
    p.add_argument("--intro-lines", type=int, required=True, help="简介句数")
    p.add_argument("--title-ok", type=int, required=True, help="首章标题能否独立成立（1/0）")
    a = p.parse_args()

    items = [
        ("前三章自检", a.selfcheck >= 8, "通过 %d/8" % a.selfcheck),
        ("存稿", a.stock >= 5, "%d 章（要求 >=5）" % a.stock),
        ("简介长度", 1 <= a.intro_lines <= 3, "%d 句（要求 1-3 句）" % a.intro_lines),
        ("首章标题", a.title_ok == 1, "可独立成立" if a.title_ok else "依赖上下文"),
    ]
    ready = sum(1 for _, ok, _ in items if ok)

    print("推荐窗口承接准备")
    print("-" * 40)
    for name, ok, detail in items:
        print("[%s] %-8s %s" % ("就位" if ok else "缺", name, detail))
    print("-" * 40)
    print("就位项  %d/4" % ready)
    if ready == 4:
        print("判定    可以接窗口")
        print("提醒    窗口期内不要改前三章，改稿会破坏数据基线")
    else:
        print("判定    不建议现在接窗口")
        print("建议    缺项补齐再上；宁可延期一次，不要浪费一次推荐")
    return 0 if ready == 4 else 1


if __name__ == "__main__":
    sys.exit(main())
