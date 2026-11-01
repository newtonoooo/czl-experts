#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""selftest.py — 回测内核的自动化自检

跑法：python tools/selftest.py -v
全部用例通过才算「装得上、跑得对」；任何一条失败都不应对外交付结果。
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "kit"))

from btcore import (Bar, Broker, CostModel, Engine, Order, compute_metrics,
                    event_stats, event_study, load_bars, monthly_table)
import btreport


def make_bars(n=60, start=10.0, step=0.1, base_date="2024-01-01"):
    """构造 n 根单调上涨的日线，日期用自然日递增（够用即可）。"""
    from datetime import date, timedelta
    d0 = date.fromisoformat(base_date)
    out = []
    px = start
    for i in range(n):
        o = px
        c = px + step
        out.append(Bar((d0 + timedelta(days=i)).isoformat(), o, c + 0.05, o - 0.05, c, 1e6))
        px = c
    return out


class TestExecution(unittest.TestCase):
    def test_signal_on_close_fills_next_open(self):
        bars = make_bars(10)
        eng = Engine({"X": bars}, cost=CostModel.zero(), initial_cash=100_000,
                     lot_size=1, t_plus_1=False, market="us")
        first = bars[0].date
        want_open = bars[1].open

        def strat(ctx):
            if ctx.shares("X") == 0:
                return [Order("X", "buy", shares=10, reason="always")]
            return None

        res = eng.run(strat)
        # 第一笔买入发生在第二根 bar 的开盘价
        self.assertAlmostEqual(res.trades[0]["entry_price"], want_open, places=4)
        self.assertGreaterEqual(res.trades[0]["entry_date"], bars[1].date)
        self.assertGreaterEqual(res.trades[0]["entry_date"], first)

    def test_warmup_does_not_trade(self):
        bars = make_bars(40)
        eval_start = bars[20].date
        eng = Engine({"X": bars}, cost=CostModel.zero(), initial_cash=100_000,
                     lot_size=1, t_plus_1=False, eval_start=eval_start, market="us")

        def strat(ctx):
            return [Order("X", "buy", shares=5, reason="always")] if ctx.shares("X") == 0 else None

        res = eng.run(strat)
        self.assertTrue(res.trades, "应当产生交易")
        for t in res.trades:
            self.assertGreaterEqual(t["entry_date"], eval_start,
                                    "预热段不应产生成交，实际 %s" % t["entry_date"])
        self.assertAlmostEqual(res.equity[0]["value"], 100_000, places=2)

    def test_t_plus_1_blocks_same_day_sell(self):
        bars = make_bars(10)
        broker = Broker(100_000, CostModel.zero(), lot_size=1, t_plus_1=True)
        broker.buy("X", 10.0, 100, bars[0].date)
        sold = broker.sell("X", 10.0, 100, bars[0].date)
        self.assertEqual(sold, 0, "T+1 当日买入不应允许卖出")
        self.assertTrue(any("T+1" in r["why"] for r in broker.rejects))
        broker.unlock_all()
        self.assertEqual(broker.sell("X", 10.0, 100, bars[1].date), 100)

    def test_lot_rounding(self):
        broker = Broker(100_000, CostModel.zero(), lot_size=100, t_plus_1=True)
        got = broker.buy("X", 33.33, 1234, "2024-01-02")
        self.assertEqual(got % 100, 0)
        self.assertEqual(got, 1200)

    def test_accounting_identity(self):
        broker = Broker(100_000, CostModel.china_a(), lot_size=100, t_plus_1=True)
        broker.buy("X", 10.0, 500, "2024-01-02")
        marks = {"X": 9.5}
        self.assertAlmostEqual(broker.equity(marks), broker.cash + 500 * 9.5, places=6)
        broker.unlock_all()
        broker.sell("X", 9.5, 500, "2024-01-03")
        self.assertEqual(broker.shares("X"), 0)
        self.assertEqual(len(broker.trades), 1)
        self.assertLess(broker.trades[0]["pnl"], 0, "含费用后亏损应为负")

    def test_forced_liquidation_at_end(self):
        bars = make_bars(20)
        eng = Engine({"X": bars}, cost=CostModel.zero(), initial_cash=100_000,
                     lot_size=1, t_plus_1=False, market="us")
        res = eng.run(lambda ctx: [Order("X", "buy", shares=100)] if ctx.shares("X") == 0 else None)
        self.assertTrue(res.trades)
        self.assertEqual(res.trades[-1]["exit_reason"], "eod_close")
        self.assertEqual(res.trades[-1]["exit_date"], bars[-1].date)


class TestMetrics(unittest.TestCase):
    def test_total_return_and_drawdown(self):
        eq = [{"date": "2024-01-01", "value": 100.0},
              {"date": "2024-06-01", "value": 120.0},
              {"date": "2024-09-01", "value": 90.0},
              {"date": "2024-12-31", "value": 110.0}]
        m = compute_metrics(eq, [], 100.0)
        self.assertAlmostEqual(m["total_return_pct"], 10.0, places=2)
        self.assertAlmostEqual(m["max_drawdown_pct"], -25.0, places=2)
        self.assertEqual(m["max_drawdown_date"], "2024-09-01")

    def test_monthly_compounding(self):
        eq = [{"date": "2024-01-02", "value": 100.0},
              {"date": "2024-01-31", "value": 110.0},
              {"date": "2024-02-29", "value": 99.0}]
        rows = monthly_table(eq)
        self.assertEqual(rows[0]["year"], 2024)
        self.assertAlmostEqual(rows[0]["months"][0], 10.0, places=2)
        self.assertAlmostEqual(rows[0]["months"][1], -10.0, places=2)
        self.assertAlmostEqual(rows[0]["ytd"], -1.0, places=2)


class TestEventStudy(unittest.TestCase):
    def test_hold_window_and_return(self):
        bars = make_bars(30, start=10.0, step=1.0)
        events = [{"date": bars[5].date, "label": "E1"}]
        rows = event_study(bars, events, hold_bars=3)
        r = rows[0]
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["entry_date"], bars[6].date)
        self.assertEqual(r["exit_date"], bars[8].date)
        expect = (bars[8].close / bars[6].open - 1) * 100
        self.assertAlmostEqual(r["pnl_pct"], expect, places=2)
        st = event_stats(rows)
        self.assertEqual(st["event_count"], 1)
        self.assertEqual(st["skipped"], 0)

    def test_event_beyond_sample_is_skipped_not_faked(self):
        bars = make_bars(10)
        rows = event_study(bars, [{"date": bars[8].date, "label": "late"}], hold_bars=20)
        self.assertEqual(rows[0]["status"] != "ok", True)
        st = event_stats(rows)
        self.assertEqual(st["event_count"], 0)


class TestIOAndReport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bt_selftest_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_bad_csv_raises_with_clear_message(self):
        p = os.path.join(self.tmp, "bad.csv")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("day,o,h,l,c\n2024-01-01,1,1,1,1\n")
        with self.assertRaises(ValueError) as ctx:
            load_bars(p)
        self.assertIn("缺少列", str(ctx.exception))

    def test_export_three_files(self):
        bars = make_bars(30)
        eng = Engine({"X": bars}, cost=CostModel.zero(), initial_cash=100_000,
                     lot_size=1, t_plus_1=False, market="us", strategy_name="t")
        res = eng.run(lambda ctx: [Order("X", "buy", shares=10)] if ctx.shares("X") == 0 else None)
        files = res.dump(self.tmp, "t")
        for k in ("equity", "trades", "summary"):
            self.assertTrue(os.path.getsize(files[k]) > 0, k)
        with open(files["summary"], encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertIn("metrics", s)
        self.assertIn("total_return_pct", s["metrics"])

    def test_report_placeholders_replaced(self):
        bars = make_bars(30)
        eng = Engine({"X": bars}, cost=CostModel.zero(), initial_cash=100_000,
                     lot_size=1, t_plus_1=False, market="us", strategy_name="t")
        res = eng.run(lambda ctx: [Order("X", "buy", shares=10)] if ctx.shares("X") == 0 else None)
        out = os.path.join(self.tmp, "index.html")
        btreport.report_from_result(res, out, "自检报告")
        with open(out, encoding="utf-8") as fh:
            html = fh.read()
        self.assertNotIn("__PAYLOAD__", html)
        self.assertNotIn("__TITLE__", html)
        self.assertIn("自检报告", html)
        self.assertIn("<svg", html)  # 模板里的图表容器


if __name__ == "__main__":
    unittest.main(verbosity=2)
