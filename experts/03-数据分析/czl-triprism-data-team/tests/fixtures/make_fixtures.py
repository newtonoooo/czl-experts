# -*- coding: utf-8 -*-
"""生成测试用示例数据（可复现）。

运行：python tests/fixtures/make_fixtures.py
产出：sales_demo.csv（干净表） / dirty_demo.csv（含缺陷表）
数据为合成数据，仅用于功能测试，不代表任何真实企业。
"""

import csv
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))

REGIONS = [("华东", 1.00), ("华南", 0.72), ("华北", 0.55)]
LINES = [("标准版", 0.55), ("专业版", 0.33), ("旗舰版", 0.12)]
MONTHS = [f"2025-{m:02d}" for m in range(1, 13)]


def build_sales():
    random.seed(20261028)
    rows = []
    for mi, month in enumerate(MONTHS):
        base = 420000 * (1 + 0.021 * mi)              # 缓慢上行
        season = 1 + 0.18 * (1 if month[-2:] in ("03", "06", "09", "12") else 0)
        for region, rw in REGIONS:
            for line, lw in LINES:
                noise = random.uniform(0.94, 1.06)
                amount = base * rw * lw * season * noise
                orders = max(4, int(amount / random.uniform(2600, 3400)))
                cost = amount * random.uniform(0.52, 0.63)
                rows.append([month, region, line, orders, round(amount, 2), round(cost, 2)])
    # 人为埋一个结构性下跌：2025-09 华南专业版被压价
    for r in rows:
        if r[0] == "2025-09" and r[1] == "华南" and r[2] == "专业版":
            r[4] = round(r[4] * 0.42, 2)
            r[5] = round(r[4] * 0.86, 2)      # 成本率异常抬升
    return rows


def build_dirty():
    rows = build_sales()[:20]
    rows[3][4] = ""                            # 缺失
    rows[5][4] = -15800                        # 负金额
    rows[7] = list(rows[7])
    rows[7][0] = "2027-03"                     # 未来日期
    rows.append(list(rows[2]))                 # 整行重复
    rows.append(list(rows[4]))
    return rows


def write(name, rows):
    path = os.path.join(HERE, name)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["月份", "区域", "产品线", "订单数", "销售额", "成本"])
        w.writerows(rows)
    return path


if __name__ == "__main__":
    print(write("sales_demo.csv", build_sales()))
    print(write("dirty_demo.csv", build_dirty()))
