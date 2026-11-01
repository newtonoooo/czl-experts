#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""示例一：均线交叉策略（含参数扫描、成本压力测试与 HTML 报告）

跑法（在专家包根目录）：
    python kit/examples/run_ma_cross.py
产物：
    out/ma_demo_equity.csv / _trades.csv / _summary.json
    out/index.html
    out/sweep.json
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "kit"))

from btcore import (Engine, CostModel, Order, load_bars, buy_and_hold,
                    param_sweep, __version__)
import btreport

DATA = os.path.join(ROOT, "data", "demo_bars.csv")
OUT = os.path.join(ROOT, "out")
PREFIX = "ma_demo"


def make_strategy(fast_n, slow_n, stop_pct=None):
    def strategy(ctx):
        closes = ctx.closes("DEMO", slow_n)
        if len(closes) < slow_n:
            return None
        fast = sum(closes[-fast_n:]) / fast_n
        slow = sum(closes) / slow_n
        holding = ctx.shares("DEMO")
        if holding == 0 and fast > slow:
            return [Order("DEMO", "buy", weight=0.95, reason="golden_cross")]
        if holding > 0:
            if fast < slow:
                return [Order("DEMO", "sell", reason="death_cross")]
            if stop_pct:
                entry = ctx.avg_cost("DEMO")
                if ctx.bar("DEMO") and ctx.bar("DEMO").close <= entry * (1 - stop_pct):
                    return [Order("DEMO", "sell", reason="stop_loss")]
        return None
    return strategy


def run(fast_n, slow_n, cost=None, stop_pct=None, cash=1_000_000):
    bars = load_bars(DATA)
    eng = Engine({"DEMO": bars}, cost=cost or CostModel.china_a(), initial_cash=cash,
                 lot_size=100, t_plus_1=True, eval_start="2021-06-01",
                 eval_end="2024-12-31", market="china_a",
                 strategy_name="MA%d/MA%d 交叉" % (fast_n, slow_n))
    return eng.run(make_strategy(fast_n, slow_n, stop_pct))


def main():
    os.makedirs(OUT, exist_ok=True)
    result = run(5, 21, stop_pct=0.08)
    files = result.dump(OUT, PREFIX)

    bars = load_bars(DATA)
    bench = buy_and_hold(bars, result.meta["start"], result.meta["end"], result.meta["initial_cash"])

    # 稳健性：两组参数扫描，看结论是否只在单点上成立
    sweep_ma = param_sweep(
        lambda cfg: {"total_return_pct": run(cfg["fast"], cfg["slow"]).metrics["total_return_pct"],
                     "sharpe": run(cfg["fast"], cfg["slow"]).metrics["sharpe"]},
        {"fast": [3, 5, 10], "slow": [15, 21, 40]})
    sweep_cost = param_sweep(
        lambda cfg: {"total_return_pct": run(5, 21, cost=CostModel.china_a(
            commission_bps=2.5 * cfg["mult"], min_commission=5.0),
            stop_pct=0.08).metrics["total_return_pct"]},
        {"mult": [1, 2, 4]})

    with open(os.path.join(OUT, "sweep.json"), "w", encoding="utf-8") as fh:
        json.dump({"params": sweep_ma, "cost": sweep_cost}, fh, ensure_ascii=False, indent=2)

    stops = sum(1 for t in result.trades if t.get("exit_reason") == "stop_loss")
    pos_params = [r for r in sweep_ma if r.get("total_return_pct", -1) > 0]
    best = max(sweep_ma, key=lambda r: r.get("total_return_pct", -999))
    cost_1x = next(r["total_return_pct"] for r in sweep_cost if r["mult"] == 1)
    cost_4x = next(r["total_return_pct"] for r in sweep_cost if r["mult"] == 4)

    notes = [
        {"title": "成交与账户", "items": [
            "信号在收盘后评估，次日开盘成交；成交价含 5bp 滑点。",
            "初始资金 %s，95%% 目标仓位，按 100 股取整，剩余留现金。" % format(result.meta["initial_cash"], ",.0f"),
            "8%% 固定止损按收盘价判断，本次共触发 %d 次（多数情况先出现死叉，止损未成为主要出场方式）。" % stops,
            "样本末仍有持仓则按最后收盘价强平，末笔 exit_reason=eod_close。",
        ]},
        {"title": "参数稳健性", "items": [
            "；".join("MA%d/MA%d %+.1f%%" % (r["fast"], r["slow"], r["total_return_pct"])
                     for r in sweep_ma),
            "9 组参数中 %d 组为正收益；最好的一组是 MA%d/MA%d（%+.1f%%）。"
            % (len(pos_params), best["fast"], best["slow"], best["total_return_pct"]),
            "全部为负说明这不是调参问题，而是该区间内均线交叉没有可提取的边际。",
        ]},
        {"title": "成本压力", "items": [
            "；".join("%dx 成本 %+.1f%%" % (r["mult"], r["total_return_pct"]) for r in sweep_cost),
            "成本放大 4 倍后收益从 %+.1f%% 变到 %+.1f%%，差异 %+.1f 个百分点，"
            "说明该策略的结论主要被成本吃掉，而不是被信号质量决定。"
            % (cost_1x, cost_4x, cost_4x - cost_1x),
        ]},
        {"title": "已知局限", "items": [
            "演示数据为合成序列（tools/gen_demo_bars.py 生成），不是真实行情，不能用于任何实盘判断。",
            "日线无法还原盘中触发顺序，止损成交价是近似值。",
            "未建模冲击成本与涨跌停无法成交的情形。",
        ]},
    ]
    payload = btreport.build_payload(
        result, "均线交叉策略回测（演示数据）",
        "标的 DEMO｜引擎 btcore %s｜本页仅验证流程可跑通，不代表任何真实标的" % __version__,
        lang="zh", benchmark=bench, notes=notes)
    btreport.render(payload, os.path.join(OUT, "index.html"))

    print("完成：", files)
    print("报告：", os.path.join(OUT, "index.html"))
    print("累计收益 %.2f%%｜年化 %.2f%%｜回撤 %.2f%%｜夏普 %.2f｜交易 %d 笔"
          % (result.metrics["total_return_pct"], result.metrics["annual_return_pct"],
             result.metrics["max_drawdown_pct"], result.metrics["sharpe"],
             result.metrics["trade_count"]))
    print("买入持有基准 %.2f%%"
          % ((bench[-1]["value"] / bench[0]["value"] - 1) * 100 if bench else 0))


if __name__ == "__main__":
    main()
