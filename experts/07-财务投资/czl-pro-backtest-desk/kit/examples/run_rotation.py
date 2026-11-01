#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""示例三：两标的动量轮动（组合模式）

演示三件事：
1. 多标的引擎怎么跑（同一份 bars 字典，按日期对齐，缺 bar 的标的沿用上一收盘价）；
2. 目标权重下单（weight=0.95 表示调到位），而不是「买多少股」；
3. 组合模式的两个必查项：换手率与调仓频率是否与口径卡一致。

跑法：python kit/examples/run_rotation.py
产物：out/rotation_* 三件套 + out/rotation.html
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "kit"))

from btcore import Engine, CostModel, Order, load_bars, buy_and_hold
import btreport

A = os.path.join(ROOT, "data", "demo_bars.csv")
B = os.path.join(ROOT, "data", "demo_bars_2.csv")
OUT = os.path.join(ROOT, "out")


def momentum(ctx, sym, n):
    c = ctx.closes(sym, n + 1)
    if len(c) < n + 1:
        return None
    return c[-1] / c[0] - 1


def strategy(lookback=20, rebalance_every=5):
    state = {"last": None, "i": 0}

    def run(ctx):
        state["i"] += 1
        if state["last"] and state["i"] - state["last"] < rebalance_every:
            return None
        ma = momentum(ctx, "A", lookback)
        mb = momentum(ctx, "B", lookback)
        if ma is None or mb is None:
            return None
        pick = "A" if ma >= mb else "B"
        other = "B" if pick == "A" else "A"
        orders = []
        if ctx.shares(other) > 0:
            orders.append(Order(other, "sell", reason="rotate_out"))
        if ctx.shares(pick) == 0:
            orders.append(Order(pick, "buy", weight=0.95, reason="rotate_in:%s" % round(max(ma, mb) * 100, 2)))
            state["last"] = state["i"]
        elif orders:
            state["last"] = state["i"]
        return orders
    return run


def main():
    os.makedirs(OUT, exist_ok=True)
    bars = {"A": load_bars(A, "A"), "B": load_bars(B, "B")}
    eng = Engine(bars, cost=CostModel.china_a(), initial_cash=1_000_000, lot_size=100,
                 t_plus_1=True, eval_start="2021-06-01", eval_end="2024-12-31",
                 market="china_a", strategy_name="20 日动量轮动（5 日一次评估）")
    res = eng.run(strategy(20, 5))
    files = res.dump(OUT, "rotation")

    bh_a = buy_and_hold(bars["A"], res.meta["start"], res.meta["end"])
    m = res.metrics
    turnover_note = ("共 %d 笔平仓，平均持有 %.1f 天，在场时间 %.0f%%。"
                     % (m["trade_count"], m["avg_holding_days"], m["exposure_pct"]))
    notes = [
        {"title": "组合口径", "items": [
            "两标的等风险预算、单标的满仓：每次只持有一只，切换时先卖后买（同一开盘价成交）。",
            "每 5 个交易日评估一次动量，避免每天来回打脸；评估频率是参数，不是事实。",
            "交易日取并集；某标的当日无 bar 时沿用上一收盘价计价，不做成交。",
            turnover_note,
        ]},
        {"title": "必查项", "items": [
            "切换次数是否远高于预期：若每月换手 4 次以上，成本会吃掉大部分超额。",
            "两只标的的相关性：相关性接近 1 时，轮动等于随机选一只，别把运气当能力。",
            "单一标的买入持有基准 %+.1f%%（A），策略 %+.1f%%。"
            % ((bh_a[-1]["value"] / bh_a[0]["value"] - 1) * 100, m["total_return_pct"]),
        ]},
        {"title": "局限", "items": [
            "演示数据为合成序列，结论不对应任何真实标的。",
            "未建模冲击成本与两只标的的成交时点差异。",
            "参数（20 日 / 5 日）未经样本外验证。",
        ]},
    ]
    payload = btreport.build_payload(res, "双标的动量轮动（演示数据）",
                                     "组合模式示例：一仓一只、定期评估、先卖后买",
                                     lang="zh", benchmark=bh_a, notes=notes)
    btreport.render(payload, os.path.join(OUT, "rotation.html"))

    print("累计 %+.2f%%｜年化 %+.2f%%｜回撤 %.2f%%｜夏普 %.2f｜平仓 %d 笔｜在场 %.0f%%"
          % (m["total_return_pct"], m["annual_return_pct"], m["max_drawdown_pct"],
             m["sharpe"], m["trade_count"], m["exposure_pct"]))
    print("报告：", os.path.join(OUT, "rotation.html"))
    print(json.dumps({"files": files}, ensure_ascii=False))


if __name__ == "__main__":
    main()
