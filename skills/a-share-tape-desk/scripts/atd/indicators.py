"""技术指标：全部本地计算，不用模型"估算"数值。

指标口径（与国内行情软件一致）：
    MA      简单移动平均
    EMA     指数移动平均，平滑系数 2/(n+1)
    MACD    DIF = EMA12 - EMA26；DEA = EMA9(DIF)；柱 = 2 x (DIF - DEA)
    KDJ     RSV = (C - LLV9) / (HHV9 - LLV9) x 100；K = 2/3 K' + 1/3 RSV；D 同理；J = 3K - 2D
    RSI      Wilder 平滑
    BOLL    MID = MA20；UP/DN = MID ± 2 x 标准差
    ATR     Wilder 平滑的真实波幅
"""

import math


def sma(values, n):
    if not values or n <= 0:
        return []
    out = []
    total = 0.0
    for i, v in enumerate(values):
        total += v
        if i >= n:
            total -= values[i - n]
        out.append(total / n if i >= n - 1 else None)
    return out


def ema(values, n):
    if not values or n <= 0:
        return []
    k = 2.0 / (n + 1)
    out = []
    prev = None
    for v in values:
        if prev is None:
            prev = v
        else:
            prev = v * k + prev * (1 - k)
        out.append(prev)
    return out


def macd(closes, fast=12, slow=26, signal=9):
    if len(closes) < slow + signal:
        return {"dif": [], "dea": [], "hist": []}
    ef, es = ema(closes, fast), ema(closes, slow)
    dif = [a - b for a, b in zip(ef, es)]
    dea = ema(dif, signal)
    hist = [2 * (a - b) for a, b in zip(dif, dea)]
    return {"dif": dif, "dea": dea, "hist": hist}


def kdj(highs, lows, closes, n=9, k_period=3, d_period=3):
    k_list, d_list, j_list = [], [], []
    k_prev, d_prev = 50.0, 50.0
    for i in range(len(closes)):
        start = max(0, i - n + 1)
        hh = max(highs[start : i + 1])
        ll = min(lows[start : i + 1])
        rsv = 50.0 if hh == ll else (closes[i] - ll) / (hh - ll) * 100.0
        k_prev = (k_period - 1) / k_period * k_prev + 1.0 / k_period * rsv
        d_prev = (d_period - 1) / d_period * d_prev + 1.0 / d_period * k_prev
        k_list.append(k_prev)
        d_list.append(d_prev)
        j_list.append(3 * k_prev - 2 * d_prev)
    return {"k": k_list, "d": d_list, "j": j_list}


def rsi(closes, n=14):
    if len(closes) <= n:
        return []
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    avg_gain = sum(gains[:n]) / n
    avg_loss = sum(losses[:n]) / n
    out = [None] * n
    out.append(100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss))
    for i in range(n, len(gains)):
        avg_gain = (avg_gain * (n - 1) + gains[i]) / n
        avg_loss = (avg_loss * (n - 1) + losses[i]) / n
        out.append(100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss))
    return out


def boll(closes, n=20, mult=2.0):
    mid = sma(closes, n)
    up, dn = [], []
    for i, m in enumerate(mid):
        if m is None:
            up.append(None)
            dn.append(None)
            continue
        window = closes[i - n + 1 : i + 1]
        var = sum((x - m) ** 2 for x in window) / n
        sd = math.sqrt(var)
        up.append(m + mult * sd)
        dn.append(m - mult * sd)
    return {"mid": mid, "up": up, "dn": dn}


def atr(highs, lows, closes, n=14):
    if len(closes) < n + 1:
        return []
    trs = [highs[0] - lows[0]]
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    out = [None] * n
    prev = sum(trs[1 : n + 1]) / n
    out.append(prev)
    for i in range(n + 1, len(trs)):
        prev = (prev * (n - 1) + trs[i]) / n
        out.append(prev)
    return out


def _last(seq):
    for v in reversed(seq):
        if v is not None:
            return v
    return None


def _r(v, digits=2):
    return None if v is None else round(v, digits)


def _cross(fast, slow, index=-1):
    """判断最近一根是否发生金叉/死叉。"""
    if len(fast) < 2 or len(slow) < 2:
        return None
    a0, a1 = fast[index - 1], fast[index]
    b0, b1 = slow[index - 1], slow[index]
    if None in (a0, a1, b0, b1):
        return None
    if a0 <= b0 and a1 > b1:
        return "金叉"
    if a0 >= b0 and a1 < b1:
        return "死叉"
    return None


def swing_levels(highs, lows, closes, lookback=60, pivot=3):
    """用分形高低点找支撑压力，再夹进均线与区间高低。"""
    n = len(closes)
    start = max(0, n - lookback)
    highs_in = highs[start:]
    lows_in = lows[start:]
    price = closes[-1]
    pivots = []
    for i in range(pivot, len(highs_in) - pivot):
        window_h = highs_in[i - pivot : i + pivot + 1]
        window_l = lows_in[i - pivot : i + pivot + 1]
        if highs_in[i] == max(window_h):
            pivots.append(highs_in[i])
        if lows_in[i] == min(window_l):
            pivots.append(lows_in[i])
    pivots = sorted(set(round(p, 2) for p in pivots))
    resist = [p for p in pivots if p > price * 1.001]
    support = [p for p in pivots if p < price * 0.999]
    return {
        "pivot_support": sorted(support, reverse=True)[:3],
        "pivot_resistance": resist[:3],
        "range_high_20": _r(max(highs[-20:])) if n >= 20 else None,
        "range_low_20": _r(min(lows[-20:])) if n >= 20 else None,
        "range_high_60": _r(max(highs[-60:])) if n >= 60 else None,
        "range_low_60": _r(min(lows[-60:])) if n >= 60 else None,
    }


def analyze(bars):
    """输入升序日线，输出指标快照与信号。"""
    if len(bars) < 30:
        return {"ok": False, "reason": "K线不足30根，无法计算有效指标"}

    closes = [b["close"] for b in bars]
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    vols = [b["volume"] or 0 for b in bars]
    price = closes[-1]

    ma = {n: sma(closes, n) for n in (5, 10, 20, 60, 120, 250)}
    ma5, ma10, ma20, ma60 = (_last(ma[5]), _last(ma[10]), _last(ma[20]), _last(ma[60]))
    ma120, ma250 = _last(ma[120]), _last(ma[250])

    macd_v = macd(closes)
    dif, dea, hist = _last(macd_v["dif"]), _last(macd_v["dea"]), _last(macd_v["hist"])
    kdj_v = kdj(highs, lows, closes)
    k, d, j = _last(kdj_v["k"]), _last(kdj_v["d"]), _last(kdj_v["j"])
    rsi6, rsi14 = _last(rsi(closes, 6)), _last(rsi(closes, 14))
    boll_v = boll(closes)
    atr_v = _last(atr(highs, lows, closes, 14))

    vol_ma5 = _last(sma(vols, 5))
    vol_ma10 = _last(sma(vols, 10))
    vol_ratio_5 = (vols[-1] / vol_ma5) if vol_ma5 else None

    # 均线排列
    align = "数据不足"
    if all(v is not None for v in (ma5, ma10, ma20)):
        if ma20 is not None and ma60 is not None:
            if ma5 > ma10 > ma20 > ma60:
                align = "多头排列"
            elif ma5 < ma10 < ma20 < ma60:
                align = "空头排列"
            else:
                align = "交织"
        else:
            align = "短期多头" if ma5 > ma10 > ma20 else ("短期空头" if ma5 < ma10 < ma20 else "交织")

    # 趋势强度：价格相对 20/60 日均线的偏离
    dev20 = (price / ma20 - 1) * 100 if ma20 else None
    dev60 = (price / ma60 - 1) * 100 if ma60 else None

    # 量价关系
    pct_today = bars[-1].get("pct")
    if pct_today is None and len(closes) > 1:
        pct_today = (closes[-1] / closes[-2] - 1) * 100
    vol_price = "量能平稳"
    if vol_ratio_5:
        if pct_today is not None and pct_today > 1 and vol_ratio_5 > 1.3:
            vol_price = "放量上涨"
        elif pct_today is not None and pct_today < -1 and vol_ratio_5 > 1.3:
            vol_price = "放量下跌"
        elif pct_today is not None and pct_today > 1 and vol_ratio_5 < 0.8:
            vol_price = "缩量上涨"
        elif pct_today is not None and pct_today < -1 and vol_ratio_5 < 0.8:
            vol_price = "缩量下跌"

    levels = swing_levels(highs, lows, closes)

    signals = []
    c = _cross(macd_v["dif"], macd_v["dea"])
    if c:
        signals.append("MACD %s" % c)
    ck = _cross(kdj_v["k"], kdj_v["d"])
    if ck:
        signals.append("KDJ %s" % ck)
    if dif is not None and dea is not None:
        signals.append("MACD 位于零轴上方" if dif > 0 and dea > 0 else ("MACD 位于零轴下方" if dif < 0 and dea < 0 else "MACD 跨零轴"))
    if k is not None:
        if k > 80 and d > 80:
            signals.append("KDJ 超买区")
        elif k < 20 and d < 20:
            signals.append("KDJ 超卖区")
    if rsi14 is not None:
        if rsi14 > 75:
            signals.append("RSI14 偏高（%.1f）" % rsi14)
        elif rsi14 < 25:
            signals.append("RSI14 偏低（%.1f）" % rsi14)

    atr_pct = (atr_v / price * 100) if atr_v and price else None
    return {
        "ok": True,
        "bars": len(bars),
        "last_date": bars[-1]["date"],
        "price": _r(price),
        "ma": {str(n): _r(v) for n, v in ((5, ma5), (10, ma10), (20, ma20), (60, ma60), (120, ma120), (250, ma250))},
        "ma_alignment": align,
        "dev_ma20_pct": _r(dev20),
        "dev_ma60_pct": _r(dev60),
        "macd": {
            "dif": _r(dif, 3),
            "dea": _r(dea, 3),
            "hist": _r(hist, 3),
            "hist_prev": _r(macd_v["hist"][-2], 3) if len(macd_v["hist"]) > 1 else None,
            "zero_axis": "上方" if (dif or 0) > 0 and (dea or 0) > 0 else ("下方" if (dif or 0) < 0 and (dea or 0) < 0 else "跨轴"),
        },
        "kdj": {"k": _r(k), "d": _r(d), "j": _r(j)},
        "rsi": {"rsi6": _r(rsi6), "rsi14": _r(rsi14)},
        "boll": {"up": _r(_last(boll_v["up"])), "mid": _r(_last(boll_v["mid"])), "dn": _r(_last(boll_v["dn"]))},
        "atr14": _r(atr_v, 3),
        "atr_pct": _r(atr_pct),
        "vol_ratio_5": _r(vol_ratio_5),
        "vol_ma5": _r(vol_ma5, 0),
        "vol_price": vol_price,
        "pct_last": _r(pct_today),
        "levels": levels,
        "signals": signals,
    }


def trend_score(ind):
    """把指标压成 -100 ~ +100 的趋势分，供策略模块引用。

    权重固定：均线排列 40、价格相对MA20 20、MACD 25、KDJ 15。
    """
    if not ind.get("ok"):
        return {"score": 0, "parts": {}, "note": "指标不足"}
    parts = {}
    align = ind["ma_alignment"]
    parts["均线排列"] = {"多头排列": 40, "短期多头": 22, "交织": 0, "短期空头": -22, "空头排列": -40}.get(align, 0)

    dev = ind.get("dev_ma20_pct") or 0
    if dev > 8:
        parts["偏离MA20"] = 12  # 过热，减分
    elif dev > 0:
        parts["偏离MA20"] = 20
    elif dev > -8:
        parts["偏离MA20"] = -12
    else:
        parts["偏离MA20"] = -20

    macd_sig = 0
    if ind["macd"]["dif"] is not None and ind["macd"]["dea"] is not None:
        if ind["macd"]["hist"] and ind["macd"]["hist"] > 0:
            macd_sig += 15
        else:
            macd_sig -= 15
        if ind["macd"]["zero_axis"] == "上方":
            macd_sig += 10
        elif ind["macd"]["zero_axis"] == "下方":
            macd_sig -= 10
    parts["MACD"] = macd_sig

    kdj_sig = 0
    k, d = ind["kdj"]["k"], ind["kdj"]["d"]
    if k is not None and d is not None:
        kdj_sig = 8 if k > d else -8
        if k > 85:
            kdj_sig -= 6
        if k < 15:
            kdj_sig += 6
    parts["KDJ"] = kdj_sig

    score = sum(parts.values())
    score = max(-100, min(100, score))
    if score >= 45:
        label = "偏强"
    elif score >= 15:
        label = "偏多"
    elif score > -15:
        label = "中性"
    elif score > -45:
        label = "偏弱"
    else:
        label = "偏空"
    return {"score": score, "label": label, "parts": parts}
