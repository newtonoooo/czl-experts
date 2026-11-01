"""日线历史。

主源：腾讯前复权日线（一次可要 320 根，足够算 MA250）。
备源：东方财富前复权日线。

统一返回前复权序列，避免除权造成的均线与指标断裂。
"""

import time

from . import codes, net

TENCENT_KLINE = (
    "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=%s,day,,,%d,qfq"
)
TENCENT_REFERER = "https://gu.qq.com"
EM_KLINE = (
    "https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=%s"
    "&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58"
    "&klt=101&fqt=1&end=20500101&lmt=%d"
)
EM_REFERER = "https://quote.eastmoney.com/"


def _num(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _from_tencent(text):
    body = text.strip()
    try:
        import json

        payload = json.loads(body)
    except ValueError:
        return []
    data = payload.get("data") or {}
    if not data:
        return []
    node = None
    for key in data.values():
        if isinstance(key, dict):
            node = key
            break
    if not node:
        return []
    rows = node.get("qfqday") or node.get("day") or []
    out = []
    for row in rows:
        if len(row) < 6:
            continue
        out.append(
            {
                "date": row[0],
                "open": _num(row[1]),
                "close": _num(row[2]),
                "high": _num(row[3]),
                "low": _num(row[4]),
                "volume": _num(row[5]),  # 手
                "amount": None,
                "pct": None,
            }
        )
    return out


def _from_eastmoney(text):
    body = text.strip()
    try:
        import json

        payload = json.loads(body)
    except ValueError:
        return []
    data = (payload.get("data") or {}).get("klines") or []
    out = []
    for line in data:
        f = line.split(",")
        if len(f) < 7:
            continue
        out.append(
            {
                "date": f[0],
                "open": _num(f[1]),
                "close": _num(f[2]),
                "high": _num(f[3]),
                "low": _num(f[4]),
                "volume": _num(f[5]),
                "amount": _num(f[6]),
                "pct": _num(f[8]) if len(f) > 8 else None,
            }
        )
    return out


def load(raw_code, days=250, ttl=300):
    """取前复权日线，升序。返回 (bars, meta)。"""
    info = codes.parse(raw_code)
    errors = []
    for name, url, parser, referer in (
        ("腾讯行情", TENCENT_KLINE % (info["prefixed"], max(days, 60)), _from_tencent, TENCENT_REFERER),
        ("东方财富", EM_KLINE % (info["secid"], max(days, 60)), _from_eastmoney, EM_REFERER),
    ):
        try:
            text, ts, cached = net.fetch(url, referer=referer, ttl=ttl)
            bars = parser(text)
            if len(bars) >= 30:
                bars.sort(key=lambda b: b["date"])
                # 补齐涨跌幅
                for i, bar in enumerate(bars):
                    if bar["pct"] is None and i > 0 and bars[i - 1]["close"]:
                        bar["pct"] = round(
                            (bar["close"] - bars[i - 1]["close"]) / bars[i - 1]["close"] * 100.0, 2
                        )
                return bars[-days:], {
                    "source": name,
                    "cached": cached,
                    "fetched_at": time.time(),
                    "bars": len(bars[-days:]),
                    "errors": errors,
                    "info": info,
                }
            errors.append("%s 返回K线不足" % name)
        except RuntimeError as exc:
            errors.append(str(exc))
    return [], {"source": None, "errors": errors, "info": info, "bars": 0}


def last_trade_date(raw_index="sh000001"):
    """用上证指数日线推断最近交易日。"""
    try:
        bars, _ = load(raw_index, days=10, ttl=300)
    except codes.CodeError:
        return None
    if not bars:
        return None
    return bars[-1]["date"]
