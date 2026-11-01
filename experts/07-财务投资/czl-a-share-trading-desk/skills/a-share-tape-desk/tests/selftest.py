#!/usr/bin/env python3
"""离线自测：不依赖网络，用固定样本验证解析、指标、风控与评分逻辑。

运行：
    python selftest.py            # 全部离线用例
    python selftest.py -v         # 详细输出

联网相关的检查由 `tapedesk.py doctor` 负责，两者分开，
这样网络不通时仍然可以证明"计算逻辑是对的"。
"""

import datetime as dt
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

from atd import clock, codes, indicators, market, quotes, risk, sectors, watch  # noqa: E402

# 2026-10-27 12:15 实测抓取的腾讯行情原文（贵州茅台）
TENCENT_SAMPLE = (
    'v_sh600519="1~贵州茅台~600519~1348.00~1349.98~1343.88~16961~10353~6608~1347.99~1~1347.79~1~'
    "1347.74~1~1347.53~1~1347.50~8~1349.31~1~1349.32~1~1349.33~3~1349.37~3~1349.39~1~~20261027120552"
    "~-1.98~-0.15~1352.90~1338.01~1348.00/16961/2286351076~16961~228635~0.14~20.69~~1352.90~1338.01"
    "~1.10~16851.10~16851.10~6.71~1484.98~1214.98~0.80~5~1348.02~18.93~20.47~~~0.04~228635.1076"
    '~0.0000~0~   A~GP-A~-0.09~1.21~3.86~32.41~27.30~1539.98~1151.01~5.73~7.62~4.54~1250081601'
    '~1250081601~26.32~2.98~1250081601~~~-2.91~-0.13~~CNY~0~___D__F__N~1347.37~3~";'
)

# 新浪行情原文（同一时刻）
SINA_SAMPLE = (
    'var hq_str_sh600519="贵州茅台,1343.880,1349.980,1348.000,1352.900,1338.010,1347.990,1349.310,'
    '1696076,2286351076.000,100,1347.990,100,1347.790,100,1347.740,100,1347.530,800,1347.500,100,'
    '1349.310,100,1349.320,100,1349.330,300,1349.370,100,1349.390,2026-10-27,11:30:00,00,";'
)

# 新浪行业板块原文片段
BOARD_SAMPLE = (
    'var S_Finance_bankuai_sinaindustry = {"new_blhy":"new_blhy,玻璃行业,19,14.464736842105,'
    '0.076842105263158,0.5340746972967,431055786,4759700007,sz002623,8.846,18.580,1.510,亚玛顿",'
    '"new_cbzz":"new_cbzz,船舶制造,8,13.784285714286,-0.052857142857143,-0.3819946314268,'
    '104087535,1563272574,sz002608,0.711,7.080,0.050,江苏国信"};'
)


def _mk_bars(prices):
    bars = []
    for i, p in enumerate(prices):
        bars.append(
            {
                "date": "2026-%02d-%02d" % (1 + i // 28, 1 + i % 28),
                "open": p,
                "close": p,
                "high": p * 1.01,
                "low": p * 0.99,
                "volume": 10000 + i * 100,
                "amount": None,
                "pct": 0.0,
            }
        )
    return bars


class TestCodes(unittest.TestCase):
    def test_markets(self):
        self.assertEqual(codes.parse("600519")["market"], "SH")
        self.assertEqual(codes.parse("688981")["market"], "SH")
        self.assertEqual(codes.parse("000001")["market"], "SZ")
        self.assertEqual(codes.parse("300750")["market"], "SZ")
        self.assertEqual(codes.parse("sh600519")["prefixed"], "sh600519")
        self.assertEqual(codes.parse("sz300750")["secid"], "0.300750")

    def test_rejects_non_a_share(self):
        for raw in ["00700.HK", "AAPL", "830799", "430047", "000001.HK"]:
            with self.assertRaises(codes.CodeError):
                codes.parse(raw)

    def test_limit_ratio(self):
        self.assertAlmostEqual(codes.limit_ratio(codes.parse("600519"), "贵州茅台"), 0.10)
        self.assertAlmostEqual(codes.limit_ratio(codes.parse("300750"), "宁德时代"), 0.20)
        self.assertAlmostEqual(codes.limit_ratio(codes.parse("600519"), "ST板块"), 0.05)
        # 创业板 ST 仍是 20%
        self.assertAlmostEqual(codes.limit_ratio(codes.parse("300001"), "*ST某某"), 0.20)

    def test_limit_prices(self):
        up, down = codes.limit_prices(1349.98, 0.10)
        self.assertAlmostEqual(up, 1484.98)
        self.assertAlmostEqual(down, 1214.98)
        up, down = codes.limit_prices(238.00, 0.20)
        self.assertAlmostEqual(up, 285.60)
        self.assertAlmostEqual(down, 190.40)


class TestParsing(unittest.TestCase):
    def test_tencent_line(self):
        rec = quotes._parse_tencent_line(TENCENT_SAMPLE)
        self.assertEqual(rec["code"], "600519")
        self.assertEqual(rec["name"], "贵州茅台")
        self.assertAlmostEqual(rec["price"], 1348.00)
        self.assertAlmostEqual(rec["prev_close"], 1349.98)
        self.assertAlmostEqual(rec["pct"], -0.15, places=1)
        self.assertAlmostEqual(rec["limit_up"], 1484.98)
        self.assertAlmostEqual(rec["amplitude"], 1.10, places=1)
        self.assertAlmostEqual(rec["amount"], 2286351076.0, delta=1)
        self.assertFalse(rec["is_limit_up"])
        self.assertEqual(rec["source"], "腾讯行情")

    def test_sina_line(self):
        rec = quotes._parse_sina_line(SINA_SAMPLE)
        self.assertEqual(rec["code"], "600519")
        self.assertAlmostEqual(rec["price"], 1348.00)
        self.assertAlmostEqual(rec["prev_close"], 1349.98)
        self.assertAlmostEqual(rec["limit_up"], 1484.98)
        self.assertIn("备源", " ".join(rec["flags"]))

    def test_board_parse(self):
        boards = sectors._parse_boards(BOARD_SAMPLE)
        self.assertEqual(len(boards), 2)
        glass = [b for b in boards if b["name"] == "玻璃行业"][0]
        self.assertAlmostEqual(glass["pct"], 0.534, places=3)
        self.assertEqual(glass["count"], 19)
        self.assertEqual(glass["leader_name"], "亚玛顿")


class TestIndicators(unittest.TestCase):
    def test_sma_ema(self):
        vals = [1, 2, 3, 4, 5]
        self.assertAlmostEqual(indicators.sma(vals, 5)[-1], 3.0)
        self.assertAlmostEqual(indicators.sma(vals, 2)[-1], 4.5)
        e = indicators.ema(vals, 2)
        self.assertEqual(len(e), 5)
        self.assertGreater(e[-1], e[0])

    def test_uptrend_detected(self):
        bars = _mk_bars([10 + i * 0.5 for i in range(80)])
        ind = indicators.analyze(bars)
        self.assertTrue(ind["ok"])
        self.assertGreater(ind["ma"]["5"], ind["ma"]["20"])
        self.assertEqual(ind["ma_alignment"], "多头排列")
        trend = indicators.trend_score(ind)
        self.assertGreater(trend["score"], 45)

    def test_downtrend_detected(self):
        bars = _mk_bars([60 - i * 0.4 for i in range(80)])
        ind = indicators.analyze(bars)
        self.assertTrue(ind["ok"])
        trend = indicators.trend_score(ind)
        self.assertLess(trend["score"], -45)

    def test_short_series_rejected(self):
        ind = indicators.analyze(_mk_bars([10, 11, 12]))
        self.assertFalse(ind["ok"])

    def test_bounds(self):
        bars = _mk_bars([20 + (i % 7) * 0.3 for i in range(120)])
        ind = indicators.analyze(bars)
        self.assertTrue(0 <= ind["kdj"]["k"] <= 100)
        self.assertTrue(0 <= ind["rsi"]["rsi14"] <= 100)
        self.assertGreater(ind["boll"]["up"], ind["boll"]["mid"])
        self.assertLess(ind["boll"]["dn"], ind["boll"]["mid"])
        self.assertGreater(ind["atr14"], 0)


class TestRisk(unittest.TestCase):
    def test_basic_sizing(self):
        p = risk.plan(entry=100, stop=95, capital=100000, risk_pct=1, max_position_pct=30)
        self.assertAlmostEqual(p["per_share_risk"], 5.0)
        self.assertAlmostEqual(p["risk_budget"], 1000.0)
        self.assertEqual(p["shares"], 200)
        self.assertAlmostEqual(p["position_value"], 20000.0)
        self.assertAlmostEqual(p["actual_risk"], 1000.0)
        self.assertEqual(p["targets"][0]["price"], 107.5)

    def test_position_cap_binds(self):
        p = risk.plan(entry=100, stop=99, capital=100000, risk_pct=5, max_position_pct=10)
        # 风险预算允许 5000 股，但 10% 仓位只允许 100 股
        self.assertEqual(p["shares"], 100)
        self.assertIn("仓位上限", p["checks"][1]["detail"])

    def test_zero_shares_flagged(self):
        p = risk.plan(entry=1348, stop=1301.34, capital=200000, risk_pct=1, max_position_pct=5)
        self.assertEqual(p["shares"], 0)
        self.assertFalse(p["checks"][1]["pass"])
        self.assertTrue(p["min_viable"]["suggestion"])

    def test_bad_stop_corrected(self):
        p = risk.plan(entry=100, stop=101, capital=100000)
        self.assertFalse(p["checks"][0]["pass"])

    def test_atr_stop(self):
        p = risk.plan(entry=100, atr=2, atr_mult=2, capital=100000, risk_pct=1)
        self.assertAlmostEqual(p["stop"], 96.0)
        self.assertIn("ATR2倍", p["stop_source"])


class TestSentiment(unittest.TestCase):
    def _stats(self, up, down, flat, limit_up, limit_down, up5=50, down5=50, amount=8e11):
        total = up + down + flat
        return {
            "total": total,
            "active": total,
            "suspended": 0,
            "up": up,
            "down": down,
            "flat": flat,
            "limit_up": limit_up,
            "limit_down": limit_down,
            "up5": up5,
            "down5": down5,
            "amount": amount,
            "pcts": [1.0] * up + [-1.0] * down + [0.0] * flat,
            "buckets": {},
            "limit_up_names": [],
            "limit_down_names": [],
            "unknown": 0,
        }

    def test_monotonic(self):
        weak = market.score(self._stats(500, 4800, 200, 5, 40), [{"pct": -1.5}])
        strong = market.score(self._stats(4800, 500, 200, 90, 2), [{"pct": 1.5}])
        self.assertLess(weak["score"], strong["score"])
        self.assertIn(weak["temperature"], ("冰点", "偏冷"))
        self.assertIn(strong["temperature"], ("偏热", "过热"))

    def test_position_ceiling(self):
        for stats in (
            self._stats(300, 5000, 100, 3, 60, up5=10, down5=300),
            self._stats(5000, 300, 100, 120, 1, up5=300, down5=10),
        ):
            res = market.score(stats, [{"pct": -2.0}])
            self.assertTrue(0 <= res["suggested_max_position"] <= 60)
            self.assertIn(res["risk_level"], ("低", "中", "高"))

    def test_score_bounds(self):
        res = market.score(self._stats(2600, 2700, 100, 30, 10), [{"pct": 0.1}])
        self.assertTrue(0 <= res["score"] <= 100)
        self.assertAlmostEqual(
            sum(p["score"] for p in res["parts"].values()), res["score"], places=1
        )


class TestWatch(unittest.TestCase):
    Q = {
        "price": 100.0,
        "pct": 2.5,
        "limit_up": 110.0,
        "limit_down": 90.0,
        "is_limit_up": False,
        "is_limit_down": False,
        "vol_ratio": 2.1,
        "amount": 5e8,
    }

    def test_conditions(self):
        cases = [
            ({"type": "price_above", "threshold": 99}, True),
            ({"type": "price_above", "threshold": 101}, False),
            ({"type": "price_below", "threshold": 101}, True),
            ({"type": "pct_above", "threshold": 2}, True),
            ({"type": "pct_below", "threshold": 2}, False),
            ({"type": "vol_ratio_above", "threshold": 2}, True),
            ({"type": "amount_above", "threshold": 4}, True),
            ({"type": "limit_up"}, False),
        ]
        for item, expected in cases:
            hit, _ = watch._evaluate(item, self.Q)
            self.assertEqual(hit, expected, item)

    def test_file_roundtrip(self):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "watchlist.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"version": 1, "items": []}, fh)
        data = watch._load(path)
        self.assertEqual(data["items"], [])
        # 损坏文件应被容错
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{坏掉的json")
        data = watch._load(path)
        self.assertEqual(data["items"], [])
        self.assertIn("warning", data)


class TestClock(unittest.TestCase):
    def _at(self, y, m, d, hh, mm):
        return dt.datetime(y, m, d, hh, mm)

    def test_phases(self):
        # 2026-10-27 是周二
        self.assertEqual(clock.phase(self._at(2026, 10, 27, 8, 0))["phase"], "盘前")
        self.assertEqual(clock.phase(self._at(2026, 10, 27, 9, 20))["phase"], "集合竞价")
        self.assertEqual(clock.phase(self._at(2026, 10, 27, 10, 0))["phase"], "早盘")
        self.assertEqual(clock.phase(self._at(2026, 10, 27, 12, 0))["phase"], "午间休市")
        self.assertEqual(clock.phase(self._at(2026, 10, 27, 14, 0))["phase"], "午盘")
        self.assertEqual(clock.phase(self._at(2026, 10, 27, 15, 30))["phase"], "已收盘")
        self.assertEqual(clock.phase(self._at(2026, 10, 25, 10, 0))["phase"], "休市")

    def test_elapsed_minutes(self):
        self.assertEqual(clock.elapsed_minutes(self._at(2026, 10, 27, 9, 45)), 15)
        self.assertEqual(clock.elapsed_minutes(self._at(2026, 10, 27, 12, 0)), 120)
        self.assertEqual(clock.elapsed_minutes(self._at(2026, 10, 27, 14, 0)), 180)
        self.assertEqual(clock.elapsed_minutes(self._at(2026, 10, 27, 16, 0)), 240)

    def test_data_age(self):
        age = clock.describe_data_age("2026-10-24", self._at(2026, 10, 27, 10, 0))
        self.assertEqual(age["kind"], "历史")
        self.assertEqual(age["age_days"], 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
