#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2026 虫志龙. All rights reserved.
"""收益结构拆解。

输入文件每行：分项名,近三个月合计金额
示例：
    阅读分成,4200
    广告分成,1800
    平台奖励,600
    版权收入,0

用法：
    python gate6_revenue.py --file revenue.txt

说明：本脚本只做结构分析，不判断金额高低；口径以后台展示为准。
"""
import argparse
import sys


def main():
    p = argparse.ArgumentParser(description="收益结构拆解")
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
                rows.append((parts[0], float(parts[1])))
    except (OSError, ValueError) as e:
        print("读取失败：%s" % e, file=sys.stderr)
        return 2

    total = sum(v for _, v in rows)
    if total <= 0:
        print("金额合计为 0，无法分析结构。", file=sys.stderr)
        return 2

    rows.sort(key=lambda x: -x[1])
    print("收益结构拆解（合计 %.0f）" % total)
    print("-" * 44)
    for name, val in rows:
        share = val / total
        bar = "#" * max(1, int(share * 30)) if val > 0 else ""
        print("%-10s %8.0f  %5.1f%%  %s" % (name, val, share * 100, bar))
    print("-" * 44)

    top_name, top_val = rows[0]
    top_share = top_val / total
    if top_share >= 0.8:
        print("结构  单腿走路（%s 占 %.0f%%）" % (top_name, top_share * 100))
        print("风险  单一分项波动会直接决定总收入")
        print("动作  优先提升留存以稳住阅读侧；同时核对奖励条件是否可达")
    elif top_share >= 0.55:
        print("结构  偏集中（%s 占 %.0f%%）" % (top_name, top_share * 100))
        print("动作  观察第二分项趋势，判断它是涨是塌")
    else:
        print("结构  相对均衡")
        print("动作  分项各自看趋势，不看合计")
    print()
    print("注：金额与分成比例以后台当月公告及合同为准，本脚本不做收益预测。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
