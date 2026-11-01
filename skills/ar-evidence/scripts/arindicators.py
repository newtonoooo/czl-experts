#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""技术指标计算（零第三方依赖）。

输入：K线序列，每根含 date/open/high/low/close/volume。
输出：MA/EMA/MACD/KDJ/RSI/BOLL/ATR/区间统计。

设计约束：
1. 不猜数据。长度不足时对应指标返回 None，不做近似。
2. 所有指标使用同一份序列，不复权混用。复权由上游负责。
3. 计算结果带 sample_size，供报告标注"基于 N 根 K 线"。

CLI:
  python arindicators.py --file bars.json
  python arindicators.py --csv bars.csv
  python arindicators.py --selftest
"""
import argparse
import csv
import json
import math
import sys


# ---------- 基础工具 ----------

def _closes(bars):
    return [float(b["close"]) for b in bars]


def sma(values, n):
    """简单移动平均，返回与输入等长的列表，前 n-1 位为 None。"""
    out = [None] * len(values)
    if n <= 0 or len(values) < n:
        return out
    window = 0.0
    for i, v in enumerate(values):
        window += v
        if i >= n:
            window -= values[i - n]
        if i >= n - 1:
            out[i] = window / n
    return out


def ema(values, n):
    """指数移动平均。首值用前 n 个的简单均值作种子。"""
    out = [None] * len(values)
    if n <= 0 or len(values) < n:
        return out
    k = 2.0 / (n + 1)
    seed = sum(values[:n]) / n
    out[n - 1] = seed
    prev = seed
    for i in range(n, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def macd(closes, fast=12, slow=26, signal=9):
    """返回 dif/dea/hist 三条与输入等长的序列（hist 为 2*(dif-dea)，A股常用口径）。"""
    ef, es = ema(closes, fast), ema(closes, slow)
    dif = [None if (a is None or b is None) else a - b for a, b in zip(ef, es)]
    valid = [x for x in dif if x is not None]
    dea_valid = ema(valid, signal)
    dea = [None] * len(dif)
    j = 0
    for i, v in enumerate(dif):
        if v is not None:
            dea[i] = dea_valid[j]
            j += 1
    hist = [None if (a is None or b is None) else 2 * (a - b) for a, b in zip(dif, dea)]
    return dif, dea, hist


def kdj(bars, n=9, k_smooth=3, d_smooth=3):
    """经典 KDJ。K/D 初值 50。"""
    k_list, d_list, j_list = [], [], []
    k_prev, d_prev = 50.0, 50.0
    for i, b in enumerate(bars):
        if i < n - 1:
            k_list.append(None)
            d_list.append(None)
            j_list.append(None)
            continue
        window = bars[i - n + 1: i + 1]
        hi = max(float(x["high"]) for x in window)
        lo = min(float(x["low"]) for x in window)
        close = float(b["close"])
        rsv = 50.0 if hi == lo else (close - lo) / (hi - lo) * 100
        k_prev = (rsv + (k_smooth - 1) * k_prev) / k_smooth
        d_prev = (k_prev + (d_smooth - 1) * d_prev) / d_smooth
        k_list.append(k_prev)
        d_list.append(d_prev)
        j_list.append(3 * k_prev - 2 * d_prev)
    return k_list, d_list, j_list


def rsi(closes, n=14):
    """Wilder RSI。"""
    out = [None] * len(closes)
    if len(closes) <= n:
        return out
    gains, losses = 0.0, 0.0
    for i in range(1, n + 1):
        diff = closes[i] - closes[i - 1]
        gains += max(diff, 0.0)
        losses += max(-diff, 0.0)
    avg_g, avg_l = gains / n, losses / n
    out[n] = 100.0 if avg_l == 0 else 100 - 100 / (1 + avg_g / avg_l)
    for i in range(n + 1, len(closes)):
        diff = closes[i] - closes[i - 1]
        avg_g = (avg_g * (n - 1) + max(diff, 0.0)) / n
        avg_l = (avg_l * (n - 1) + max(-diff, 0.0)) / n
        out[i] = 100.0 if avg_l == 0 else 100 - 100 / (1 + avg_g / avg_l)
    return out


def boll(closes, n=20, k=2.0):
    mid = sma(closes, n)
    up, low = [None] * len(closes), [None] * len(closes)
    for i in range(len(closes)):
        if mid[i] is None:
            continue
        window = closes[i - n + 1: i + 1]
        mean = mid[i]
        var = sum((x - mean) ** 2 for x in window) / n
        sd = math.sqrt(var)
        up[i] = mean + k * sd
        low[i] = mean - k * sd
    return mid, up, low


def atr(bars, n=14):
    trs = []
    for i, b in enumerate(bars):
        hi, lo, close = float(b["high"]), float(b["low"]), float(b["close"])
        if i == 0:
            trs.append(hi - lo)
        else:
            prev = float(bars[i - 1]["close"])
            trs.append(max(hi - lo, abs(hi - prev), abs(lo - prev)))
    return sma(trs, n), trs


# ---------- 统计 ----------

def percentile_rank(values, target):
    """target 在 values 中的百分位（0-100），使用严格小于的比例。"""
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    below = sum(1 for v in vals if v < target)
    return round(below / len(vals) * 100, 1)


def max_drawdown(series):
    """最大回撤（负值，如 -23.4 表示回撤 23.4%）。"""
    peak, mdd = None, 0.0
    for v in series:
        if v is None:
            continue
        if peak is None or v > peak:
            peak = v
        if peak and peak > 0:
            dd = (v - peak) / peak * 100
            if dd < mdd:
                mdd = dd
    return round(mdd, 2)


def annualized_vol(closes, periods=250):
    rets = []
    for i in range(1, len(closes)):
        if closes[i - 1]:
            rets.append(closes[i] / closes[i - 1] - 1)
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return round(math.sqrt(var) * math.sqrt(periods) * 100, 2)


def interval_return(closes, n):
    """最近 n 根 K 线的累计涨幅（%）。"""
    if len(closes) < n + 1:
        return None
    base = closes[-n - 1]
    if not base:
        return None
    return round((closes[-1] / base - 1) * 100, 2)


# ---------- 汇总 ----------

def compute(bars):
    """计算全部指标，返回结构化字典。数据不足时相应字段为 None。"""
    if not bars:
        raise ValueError("K线为空")
    closes = _closes(bars)
    ma = {f"ma{n}": (None if sma(closes, n)[-1] is None else round(sma(closes, n)[-1], 3))
          for n in (5, 10, 20, 60, 120, 250)}
    dif, dea, hist = macd(closes)
    kl, dl, jl = kdj(bars)
    rs = rsi(closes)
    mid, up, low = boll(closes)
    at, trs = atr(bars)

    last_close = closes[-1]
    ma20 = ma["ma20"]
    bias20 = None if not ma20 else round((last_close - ma20) / ma20 * 100, 2)

    trend = "数据不足"
    if ma["ma5"] and ma["ma10"] and ma["ma20"]:
        if ma["ma5"] > ma["ma10"] > ma["ma20"]:
            trend = "多头排列"
        elif ma["ma5"] < ma["ma10"] < ma["ma20"]:
            trend = "空头排列"
        else:
            trend = "均线粘合/交织"

    vols = [float(b["volume"]) for b in bars]
    vol5 = sma(vols, 5)[-1]
    vol20 = sma(vols, 20)[-1]
    vol_ratio = round(vol5 / vol20, 2) if (vol5 and vol20) else None

    return {
        "sample_size": len(bars),
        "first_date": bars[0].get("date"),
        "last_date": bars[-1].get("date"),
        "last_close": last_close,
        "ma": ma,
        "bias_ma20_pct": bias20,
        "trend": trend,
        "macd": {
            "dif": None if dif[-1] is None else round(dif[-1], 4),
            "dea": None if dea[-1] is None else round(dea[-1], 4),
            "hist": None if hist[-1] is None else round(hist[-1], 4),
            "cross": _macd_cross(dif, dea),
        },
        "kdj": {
            "k": None if kl[-1] is None else round(kl[-1], 2),
            "d": None if dl[-1] is None else round(dl[-1], 2),
            "j": None if jl[-1] is None else round(jl[-1], 2),
        },
        "rsi14": None if rs[-1] is None else round(rs[-1], 2),
        "boll": {
            "mid": None if mid[-1] is None else round(mid[-1], 3),
            "upper": None if up[-1] is None else round(up[-1], 3),
            "lower": None if low[-1] is None else round(low[-1], 3),
            "position": _boll_pos(last_close, up[-1], low[-1]),
        },
        "atr14": None if at[-1] is None else round(at[-1], 3),
        "atr_pct": None if (at[-1] is None or not last_close) else round(at[-1] / last_close * 100, 2),
        "volume": {
            "vol5_avg": None if not vol5 else round(vol5, 0),
            "vol20_avg": None if not vol20 else round(vol20, 0),
            "vol_ratio_5_20": vol_ratio,
        },
        "returns": {
            "ret_5d": interval_return(closes, 5),
            "ret_20d": interval_return(closes, 20),
            "ret_60d": interval_return(closes, 60),
            "ret_250d": interval_return(closes, 250),
        },
        "vol_annual_pct": annualized_vol(closes),
        "max_drawdown_pct": max_drawdown(closes),
        "close_percentile_250": percentile_rank(closes[-250:], last_close),
    }


def _macd_cross(dif, dea):
    if len(dif) < 2 or dif[-1] is None or dea[-1] is None or dif[-2] is None or dea[-2] is None:
        return None
    prev = dif[-2] - dea[-2]
    now = dif[-1] - dea[-1]
    if prev <= 0 < now:
        return "金叉"
    if prev >= 0 > now:
        return "死叉"
    return "无交叉"


def _boll_pos(close, upper, lower):
    if upper is None or lower is None:
        return None
    if close >= upper:
        return "上轨之上"
    if close <= lower:
        return "下轨之下"
    span = upper - lower
    if span <= 0:
        return None
    return "轨道内 %.0f%% 位置" % ((close - lower) / span * 100)


def load_bars(path):
    if path.lower().endswith(".csv"):
        bars = []
        with open(path, "r", encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                bars.append({
                    "date": row.get("date") or row.get("日期"),
                    "open": float(row.get("open") or row.get("开盘")),
                    "high": float(row.get("high") or row.get("最高")),
                    "low": float(row.get("low") or row.get("最低")),
                    "close": float(row.get("close") or row.get("收盘")),
                    "volume": float(row.get("volume") or row.get("成交量") or 0),
                })
        return bars
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict) and "bars" in data:
        data = data["bars"]
    return data


def selftest():
    """内置合成序列自检，不依赖网络。"""
    bars = []
    price = 10.0
    for i in range(300):
        price = price * (1 + (0.004 if i % 3 else -0.002))
        bars.append({
            "date": "2025-%03d" % i,
            "open": price * 0.995,
            "high": price * 1.01,
            "low": price * 0.99,
            "close": price,
            "volume": 10000 + i * 10,
        })
    res = compute(bars)
    checks = [
        ("样本数", res["sample_size"] == 300),
        ("MA5 非空", res["ma"]["ma5"] is not None),
        ("MA250 非空", res["ma"]["ma250"] is not None),
        ("MACD 非空", res["macd"]["dif"] is not None),
        ("KDJ 在 0-100 附近", res["kdj"]["k"] is not None),
        ("RSI 在 0-100", 0 <= (res["rsi14"] or -1) <= 100),
        ("ATR 为正", (res["atr14"] or 0) > 0),
        ("趋势已判定", res["trend"] in ("多头排列", "空头排列", "均线粘合/交织")),
        ("回撤非正", (res["max_drawdown_pct"] or 0) <= 0),
        ("20日涨幅可算", res["returns"]["ret_20d"] is not None),
    ]
    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(("  PASS  " if ok else "  FAIL  ") + name)
    print("结果：%d/%d 通过" % (len(checks) - len(failed), len(checks)))
    return 0 if not failed else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="技术指标计算")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", help="K线 JSON")
    src.add_argument("--csv", help="K线 CSV")
    src.add_argument("--selftest", action="store_true", help="内置自检")
    ap.add_argument("--out", help="结果写入文件")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    bars = load_bars(args.file or args.csv)
    res = compute(bars)
    text = json.dumps(res, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("已写入 %s（%d 根K线）" % (args.out, res["sample_size"]))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
