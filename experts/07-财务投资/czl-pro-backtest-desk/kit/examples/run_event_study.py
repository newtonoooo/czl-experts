#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""示例二：事件研究（事件后持有 N 个交易日的收益分布）

跑法：
    python kit/examples/run_event_study.py

与策略回测的区别（这是回测里最容易做错的一类）：
- 不建账户、不算净值、不计佣金（除非用户要求），一个事件 = 一行收益；
- 核心统计是平均/中位数/胜率/最好/最差，**不报夏普、年化、最大回撤**；
- 每条记录必须有 label，否则图上的点无法解释。

演示用事件日期是人为构造的（不是真实新闻事件），只用于验证流程。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "kit"))

from btcore import load_bars, event_study, event_stats
import btreport

DATA = os.path.join(ROOT, "data", "demo_bars.csv")
OUT = os.path.join(ROOT, "out")

# 演示事件：每季度第一个交易日，label 说明这只是占位事件
DEMO_EVENTS = [
    {"date": "2021-07-01", "label": "演示事件 A"},
    {"date": "2021-10-08", "label": "演示事件 B"},
    {"date": "2022-01-04", "label": "演示事件 C"},
    {"date": "2022-04-06", "label": "演示事件 D"},
    {"date": "2022-07-01", "label": "演示事件 E"},
    {"date": "2022-10-10", "label": "演示事件 F"},
    {"date": "2023-01-03", "label": "演示事件 G"},
    {"date": "2023-04-03", "label": "演示事件 H"},
    {"date": "2023-07-03", "label": "演示事件 I"},
    {"date": "2023-10-09", "label": "演示事件 J"},
    {"date": "2024-01-02", "label": "演示事件 K"},
    {"date": "2024-04-01", "label": "演示事件 L"},
]


def main():
    os.makedirs(OUT, exist_ok=True)
    bars = load_bars(DATA)
    rows = event_study(bars, DEMO_EVENTS, hold_bars=20)
    stats = event_stats(rows)

    with open(os.path.join(OUT, "event_trades.csv"), "w", newline="", encoding="utf-8") as fh:
        import csv
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(OUT, "event_stats.json"), "w", encoding="utf-8") as fh:
        json.dump(stats, fh, ensure_ascii=False, indent=2)

    notes = [
        {"title": "口径", "items": [
            "事件日收盘确认，次一交易日开盘买入，持有 20 个交易日后收盘卖出。",
            "不计佣金与滑点：事件研究的目的是看价格反应，不是模拟交易成本。",
            "事件日若为非交易日，自动顺延到下一个交易日。",
        ]},
        {"title": "怎么读", "items": [
            "先看中位数，再看平均：少数极端事件会把平均拉偏。",
            "样本 %d 个事件，统计显著性有限；标准差 %.2f%%，均值标准误约 %.2f%%。"
            % (stats["event_count"], stats["stdev_pct"],
               stats["stdev_pct"] / max(1, stats["event_count"]) ** 0.5),
            "事件研究只能说明「事件后平均涨了/跌了」，不能说明是事件导致的。",
        ]},
    ]
    payload = btreport.event_payload(
        rows, stats, "事件后 20 个交易日收益（演示事件，非真实事件）", lang="zh", extra=notes)
    payload["chips"] = [
        {"k": "标的", "v": "DEMO"},
        {"k": "持有", "v": "20 个交易日"},
        {"k": "事件数", "v": str(stats["event_count"])},
        {"k": "数据", "v": "合成演示序列"},
    ]
    btreport.render(payload, os.path.join(OUT, "event_index.html"))

    print("事件数 %d｜平均 %+.2f%%｜中位 %+.2f%%｜胜率 %.1f%%｜最好 %+.2f%%｜最差 %+.2f%%"
          % (stats["event_count"], stats["avg_pct"], stats["median_pct"],
             stats["win_rate_pct"], stats["best_pct"], stats["worst_pct"]))
    print("报告：", os.path.join(OUT, "event_index.html"))


if __name__ == "__main__":
    main()
