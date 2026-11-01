#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_demo_data.py — 生成数证台样例数据（真值可手算）。

设计好的真值：
  orders_demo.csv
    2026-05：线上 240 单 × 100 元 = 24,000；门店 160 单 × 100 元 = 16,000；合计 40,000（400 单）
    2026-06：线上 120 单 × 100 元 = 12,000；门店 160 单 × 150 元 = 24,000；合计 36,000（280 单）
    变化：-4,000（-10.00%）
    三因子：量 -12,000；价 +11,428.57；交互 -3,428.57（合计 -4,000.00）

  events_demo.csv
    漏斗去重人数：访问 1000 → 加购 320 → 下单 150 → 支付 98
    单步率：32.00% / 46.88%（150/320）/ 65.33%（98/150）

  cohort_demo.csv
    3 个同期群（2026-07 / 08 / 09），各 20 人；留存结构手工指定。

  ab_demo.csv
    对照组 1000 人，转化 51（5.10%）
    实验组 1000 人，转化 78（7.80%）

用法：python make_demo_data.py <输出目录>
"""

import csv
import os
import sys


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out, exist_ok=True)

    # ---------- 订单表
    rows = []
    oid = 1
    customers = ["C%03d" % i for i in range(1, 21)]
    plan = [("2026-05", "线上", 240, 100.0), ("2026-05", "门店", 160, 100.0),
            ("2026-06", "线上", 120, 100.0), ("2026-06", "门店", 160, 150.0)]
    import calendar
    for month, channel, n, price in plan:
        y, m = int(month[:4]), int(month[5:7])
        days_in_month = calendar.monthrange(y, m)[1]
        for i in range(n):
            # 让每个月每一天都有数据，避免样例数据自带「断档」
            day = (i % days_in_month) + 1
            cat = "日用品" if i % 2 == 0 else "食品"
            rows.append([
                "SO%04d" % oid,
                customers[i % len(customers)],
                "%s-%02d" % (month, day),
                channel,
                cat,
                1,
                "%.2f" % price,
                "已完成" if i % 17 else "已退款",
            ])
            oid += 1

    p1 = os.path.join(out, "orders_demo.csv")
    with open(p1, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["订单号", "客户ID", "支付日期", "渠道", "品类", "件数", "金额", "状态"])
        w.writerows(rows)

    # ---------- 漏斗事件表
    ev = []
    total_view = 1000
    for i in range(total_view):
        u = "U%04d" % i
        ev.append([u, "2026-09-%02d" % ((i % 28) + 1), "访问"])
        if i < 320:
            ev.append([u, "2026-09-%02d" % ((i % 28) + 1), "加购"])
        if i < 150:
            ev.append([u, "2026-09-%02d" % ((i % 28) + 1), "下单"])
        if i < 98:
            ev.append([u, "2026-09-%02d" % ((i % 28) + 1), "支付"])

    p2 = os.path.join(out, "events_demo.csv")
    with open(p2, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["用户ID", "日期", "步骤"])
        w.writerows(ev)

    # ---------- 同期群事件表
    # 2026-07 群 20 人：第2期 12 人、第3期 8 人
    # 2026-08 群 20 人：第2期 10 人
    # 2026-09 群 20 人：只有首期
    co = []
    for i in range(20):
        u = "K%03d" % i
        co.append([u, "2026-07-05", "1"])
        if i < 12:
            co.append([u, "2026-08-05", "1"])
        if i < 8:
            co.append([u, "2026-09-05", "1"])
    for i in range(20):
        u = "M%03d" % i
        co.append([u, "2026-08-06", "1"])
        if i < 10:
            co.append([u, "2026-09-06", "1"])
    for i in range(20):
        u = "N%03d" % i
        co.append([u, "2026-09-07", "1"])

    p3 = os.path.join(out, "cohort_demo.csv")
    with open(p3, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["用户ID", "日期", "访问次数"])
        w.writerows(co)

    # ---------- A/B 明细
    ab = []
    for i in range(1000):
        ab.append(["control", 1 if i < 51 else 0, "%.2f" % (80 + (i % 40))])
    for i in range(1000):
        ab.append(["treat", 1 if i < 78 else 0, "%.2f" % (84 + (i % 40))])

    p4 = os.path.join(out, "ab_demo.csv")
    with open(p4, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["组别", "是否转化", "客单价"])
        w.writerows(ab)

    for p in (p1, p2, p3, p4):
        print("生成 %s（%.1f KB）" % (p, os.path.getsize(p) / 1024))

    print("\n手算真值：")
    print("  orders: 2026-05 合计 40,000 / 2026-06 合计 36,000 / 变化 -4,000（-10.00%）")
    print("  orders 按渠道: 线上 -12,000；门店 +8,000")
    print("  funnel: 访问 1000 → 加购 320（32.00%）→ 下单 150（46.88%）→ 支付 98（65.33%）")
    print("  cohort: 2026-07 群第2期 12/20=60.0%%，第3期 8/20=40.0%%；2026-08 群第2期 10/20=50.0%%")
    print("  ab: 对照 51/1000=5.10%%，实验 78/1000=7.80%%，绝对差 +2.70 个百分点")


if __name__ == "__main__":
    main()
