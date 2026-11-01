#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_demo_bars.py — 生成演示用日线数据（合成数据，非真实行情）

用途：让用户在没有数据接口时也能一键跑通内核与报告，验证「装得上、跑得动」。
数据说明：几何随机游走 + 三段趋势切换 + 波动率聚集，随机种子固定，
每次生成结果完全一致。文件头不写注释（CSV 保持干净），来源说明见 README。

用法：
    python tools/gen_demo_bars.py            # 写入 data/demo_bars.csv
    python tools/gen_demo_bars.py --seed 7 --years 5
"""
import argparse
import csv
import math
import os
import random
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def trading_days(start, years):
    d = start
    end = date(start.year + years, start.month, start.day)
    while d <= end:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


def build(seed=20240501, years=4, start=date(2021, 1, 4), p0=3.42):
    rng = random.Random(seed)
    px = p0
    vol = 0.014
    drift = 0.00035
    rows = []
    for i, d in enumerate(trading_days(start, years)):
        # 每 180 个交易日切换一次趋势与波动状态
        if i and i % 180 == 0:
            regime = rng.choice(["up", "down", "flat", "up"])
            drift = {"up": 0.0007, "down": -0.0006, "flat": 0.00002}[regime]
            vol = rng.uniform(0.011, 0.024)
        shock = rng.gauss(0, 1)
        ret = drift + vol * shock
        px = max(1.0, px * math.exp(ret))
        o = px * (1 + rng.gauss(0, vol * 0.25))
        c = px
        h = max(o, c) * (1 + abs(rng.gauss(0, vol * 0.35)))
        l = min(o, c) * (1 - abs(rng.gauss(0, vol * 0.35)))
        v = int(abs(rng.gauss(1.0, 0.35)) * 9_000_000) + 500_000
        rows.append([d.strftime("%Y-%m-%d"), round(o, 3), round(h, 3), round(l, 3),
                     round(c, 3), v])
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20240501)
    ap.add_argument("--years", type=int, default=4)
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "demo_bars.csv"))
    args = ap.parse_args()
    rows = build(seed=args.seed, years=args.years)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "open", "high", "low", "close", "volume"])
        w.writerows(rows)
    print("已写入 %s：%d 根 bar，%s ~ %s" % (args.out, len(rows), rows[0][0], rows[-1][0]))


if __name__ == "__main__":
    main()
