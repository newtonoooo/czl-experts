#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2026 虫志龙. All rights reserved.
"""单章信息增量核算。

输入文件每行：章号,增量类型（逗号分隔，可多选）
类型取值：事实 / 关系 / 能力 / 处境 / 认知 / 情绪
示例：
    1,事实,处境
    2,情绪
    3,关系,认知

用法：
    python gate3_info_gain.py --file gains.txt
"""
import argparse
import sys

VALID = {"事实", "关系", "能力", "处境", "认知", "情绪"}
SUBSTANTIVE = {"事实", "关系", "能力", "处境", "认知"}


def main():
    p = argparse.ArgumentParser(description="单章信息增量核算")
    p.add_argument("--file", required=True)
    p.add_argument("--min", type=int, default=2, help="每章最低增量项数，默认 2")
    a = p.parse_args()

    rows = []
    try:
        with open(a.file, encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = [x.strip() for x in line.split(",") if x.strip()]
                if len(parts) < 2:
                    raise ValueError("第 %d 行缺少增量类型" % i)
                try:
                    ch = int(parts[0])
                except ValueError:
                    raise ValueError("第 %d 行章号不是数字" % i)
                kinds = parts[1:]
                bad = [k for k in kinds if k not in VALID]
                if bad:
                    raise ValueError("第 %d 行有非法类型：%s" % (i, "/".join(bad)))
                rows.append((ch, kinds))
    except (OSError, ValueError) as e:
        print("读取失败：%s" % e, file=sys.stderr)
        return 2

    if not rows:
        print("没有有效数据。", file=sys.stderr)
        return 2

    low = []
    only_emotion = []
    for ch, kinds in rows:
        sub = [k for k in kinds if k in SUBSTANTIVE]
        if len(sub) < a.min:
            low.append((ch, len(sub)))
        if not sub:
            only_emotion.append(ch)

    ok = len(rows) - len(low)
    print("单章信息增量核算（%d 章）" % len(rows))
    print("-" * 38)
    print("达标章        %d" % ok)
    print("低增量章      %d" % len(low))
    if low:
        print("低增量明细    " + "、".join("第%d章(%d项)" % (c, n) for c, n in low))
    print("只有情绪增量  %s" % ("、".join("第%d章" % c for c in only_emotion) if only_emotion else "无"))
    print("-" * 38)
    if not low:
        print("判定  合格")
    else:
        print("判定  不合格")
        print("处理  低增量章压缩合并，或补一个不可逆的小变化（处境/关系优先）")
        print("      只给情绪不给处境的章，读者会判定「这章可以不看」")
    return 0 if not low else 1


if __name__ == "__main__":
    sys.exit(main())
