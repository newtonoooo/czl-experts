#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2026 虫志龙. All rights reserved.
"""签约版权字段检查表。

未填写的字段一律视为「未约定」，未约定等于按对方解释。
用法：
    python gate6_contract_check.py --scope "仅信息网络传播权" --exclusive "独家3年" ...

留空的字段请写 "-"。

本脚本不构成法律意见，重大条款请咨询专业人士。
"""
import argparse
import sys

FIELDS = [
    ("scope", "授权范围", "只授信息网络传播权，还是含改编权"),
    ("exclusive", "独家性", "是否独家、期限、到期后处理"),
    ("base", "分成基数", "按流水还是净收入"),
    ("cycle", "结算周期", "多久结、起结门槛"),
    ("finish", "完本要求", "最低字数、最长断更、未达标后果"),
    ("exit", "解约条件", "能否解约、解约后版权归属"),
]


def main():
    p = argparse.ArgumentParser(description="签约版权字段检查表")
    for k, label, _ in FIELDS:
        p.add_argument("--" + k, default="-", help=label)
    a = p.parse_args()

    missing = []
    print("签约版权字段检查")
    print("-" * 50)
    for k, label, hint in FIELDS:
        val = (getattr(a, k) or "-").strip()
        if val == "-":
            missing.append(label)
            print("[未约定] %-6s %s" % (label, hint))
        else:
            print("[已填]   %-6s %s" % (label, val))
    print("-" * 50)
    print("未约定项  %d/6" % len(missing))
    if missing:
        print("风险      " + "、".join(missing) + " 未约定，发生争议时按对方解释")
        print("动作      把这 %d 项写成问题清单，逐条书面问清并留存答复" % len(missing))
        return 1
    print("结论      六项均有约定，仍需核对条款表述是否与你理解一致")
    print()
    print("注：本脚本只做清单核对，不构成法律意见。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
