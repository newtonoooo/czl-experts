"""技术指标计算：输入原始序列，输出标量指标。

设计原则：
- 只用标准库，浮点结果四舍五入到 4 位，方便测试与人工复核；
- 数据不足时返回 None 而不是猜一个值——缺失要能被上层看见；
- 所有函数都是纯函数，不读写文件，不联网。
"""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence


def _r(x: Optional[float], nd: int = 4) -> Optional[float]:
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if v != v or v in (float("inf"), float("-inf")):
        return None
    return round(v, nd)


def _clean(seq: Iterable[float]) -> List[float]:
    out: List[float] = []
    for v in seq or []:
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if f != f:
            continue
        out.append(f)
    return out


def sma(values: Sequence[float], n: int) -> Optional[float]:
    v = _clean(values)
    if n <= 0 or len(v) < n:
        return None
    return _r(sum(v[-n:]) / n)


def ema_series(values: Sequence[float], n: int) -> List[float]:
    v = _clean(values)
    if not v or n <= 0:
        return []
    k = 2.0 / (n + 1)
    out = [v[0]]
    for x in v[1:]:
        out.append(x * k + out[-1] * (1 - k))
    return out


def ema(values: Sequence[float], n: int) -> Optional[float]:
    s = ema_series(values, n)
    return _r(s[-1]) if s else None


def macd(closes: Sequence[float], fast: int = 12, slow: int = 26, signal: int = 9):
    """返回 (DIF, DEA, MACD 柱)。柱按国内习惯取 2*(DIF-DEA)。"""
    v = _clean(closes)
    if len(v) < slow + signal:
        return None, None, None
    ef, es = ema_series(v, fast), ema_series(v, slow)
    dif = [a - b for a, b in zip(ef, es)]
    dea = ema_series(dif, signal)
    dif_last, dea_last = dif[-1], dea[-1]
    return _r(dif_last), _r(dea_last), _r(2 * (dif_last - dea_last))


def rsi(closes: Sequence[float], n: int = 14) -> Optional[float]:
    """Wilder 平滑 RSI。"""
    v = _clean(closes)
    if len(v) < n + 1:
        return None
    gains, losses = 0.0, 0.0
    for i in range(1, n + 1):
        d = v[i] - v[i - 1]
        gains += max(d, 0.0)
        losses += max(-d, 0.0)
    ag, al = gains / n, losses / n
    for i in range(n + 1, len(v)):
        d = v[i] - v[i - 1]
        ag = (ag * (n - 1) + max(d, 0.0)) / n
        al = (al * (n - 1) + max(-d, 0.0)) / n
    if al == 0:
        return 100.0 if ag > 0 else 50.0
    rs = ag / al
    return _r(100 - 100 / (1 + rs))


def kdj(closes: Sequence[float], highs: Sequence[float], lows: Sequence[float], n: int = 9):
    """返回 (K, D, J)，采用 2/3-1/3 递推，初值 50。"""
    c, h, l = _clean(closes), _clean(highs), _clean(lows)
    m = min(len(c), len(h), len(l))
    if m < n:
        return None, None, None
    c, h, l = c[-m:], h[-m:], l[-m:]
    k = d = 50.0
    for i in range(n - 1, m):
        hh = max(h[i - n + 1 : i + 1])
        ll = min(l[i - n + 1 : i + 1])
        rsv = 50.0 if hh == ll else (c[i] - ll) / (hh - ll) * 100
        k = 2 / 3 * k + 1 / 3 * rsv
        d = 2 / 3 * d + 1 / 3 * k
    return _r(k), _r(d), _r(3 * k - 2 * d)


def boll(closes: Sequence[float], n: int = 20, mult: float = 2.0):
    """返回 (上轨, 中轨, 下轨)，标准差用总体口径。"""
    v = _clean(closes)
    if len(v) < n:
        return None, None, None
    w = v[-n:]
    mid = sum(w) / n
    var = sum((x - mid) ** 2 for x in w) / n
    sd = var ** 0.5
    return _r(mid + mult * sd), _r(mid), _r(mid - mult * sd)


def atr(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], n: int = 14) -> Optional[float]:
    h, l, c = _clean(highs), _clean(lows), _clean(closes)
    m = min(len(h), len(l), len(c))
    if m < n + 1:
        return None
    h, l, c = h[-m:], l[-m:], c[-m:]
    trs = []
    for i in range(1, m):
        trs.append(max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])))
    if len(trs) < n:
        return None
    a = sum(trs[:n]) / n
    for x in trs[n:]:
        a = (a * (n - 1) + x) / n
    return _r(a)


def bias(closes: Sequence[float], n: int = 20) -> Optional[float]:
    """乖离率（%）。"""
    m = sma(closes, n)
    v = _clean(closes)
    if not m or not v:
        return None
    return _r((v[-1] / m - 1) * 100, 2)


def volume_ratio(volumes: Sequence[float], short: int = 5, long: int = 20) -> Optional[float]:
    """量比：短均量 / 长均量。"""
    a, b = sma(volumes, short), sma(volumes, long)
    if not a or not b:
        return None
    return _r(a / b, 3)


def pct_from_high(closes: Sequence[float], n: int = 250) -> Optional[float]:
    v = _clean(closes)
    if not v:
        return None
    w = v[-n:]
    hi = max(w)
    if hi == 0:
        return None
    return _r((v[-1] / hi - 1) * 100, 2)


def position_in_range(closes: Sequence[float], n: int = 250) -> Optional[float]:
    """收盘价在 N 日高低区间中的相对位置，0=最低，1=最高。"""
    v = _clean(closes)
    if not v:
        return None
    w = v[-n:]
    hi, lo = max(w), min(w)
    if hi == lo:
        return None
    return _r((v[-1] - lo) / (hi - lo), 3)


def swing(highs: Sequence[float], lows: Sequence[float], n: int = 20):
    h, l = _clean(highs), _clean(lows)
    if len(h) < n or len(l) < n:
        return None, None
    return _r(max(h[-n:])), _r(min(l[-n:]))


def derive_technical(series: dict) -> dict:
    """从原始 K 线序列推导技术指标字典；已有字段以传入值为准（不覆盖用户给的口径）。

    series 允许的键：closes / highs / lows / volumes（按时间正序，最后一根为最新）。
    """
    closes = _clean(series.get("closes") or [])
    highs = _clean(series.get("highs") or [])
    lows = _clean(series.get("lows") or [])
    volumes = _clean(series.get("volumes") or [])

    out: dict = {}
    if closes:
        out["close"] = _r(closes[-1])
        for n in (5, 10, 20, 60, 120, 250):
            out[f"ma{n}"] = sma(closes, n)
        dif, dea, hist = macd(closes)
        out["macd_dif"], out["macd_dea"], out["macd_hist"] = dif, dea, hist
        out["rsi14"] = rsi(closes, 14)
        up, mid, low = boll(closes, 20)
        out["boll_upper"], out["boll_mid"], out["boll_lower"] = up, mid, low
        out["bias20"] = bias(closes, 20)
        out["pct_from_high_250"] = pct_from_high(closes, 250)
        out["position_250"] = position_in_range(closes, 250)
    if closes and highs and lows:
        k, d, j = kdj(closes, highs, lows)
        out["kdj_k"], out["kdj_d"], out["kdj_j"] = k, d, j
        a = atr(highs, lows, closes, 14)
        out["atr14"] = a
        if a and closes:
            out["atr_pct"] = _r(a / closes[-1] * 100, 2)
    if volumes:
        out["vol_ratio5_20"] = volume_ratio(volumes, 5, 20)
    hi, lo = swing(highs, lows, 20)
    out["swing_high_20"], out["swing_low_20"] = hi, lo
    return {k: v for k, v in out.items() if v is not None}


def merge_technical(provided: dict, series: dict) -> dict:
    """用户显式给出的指标优先，其余用序列推导补齐。"""
    derived = derive_technical(series or {})
    merged = dict(derived)
    for k, v in (provided or {}).items():
        if v is None:
            continue
        if isinstance(v, (int, float)):
            merged[k] = _r(v)
    return merged
