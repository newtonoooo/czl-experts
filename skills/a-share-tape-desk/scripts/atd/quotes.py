"""实时快照。

主源：腾讯行情（qt.gtimg.cn），一次可批量多只，且自带涨跌停价、量比、PE/PB、市值。
备源：新浪行情（hq.sinajs.cn），字段更少，但稳定性好。

两个源拿到的原始字符串都会重新计算涨跌幅、振幅、日内位置，
厂商给的派生字段只用于交叉校验，不一致时以重算值为准并打标记。
"""

import time

from . import codes, net

TENCENT_BASE = "http://qt.gtimg.cn/q="
TENCENT_REFERER = "https://gu.qq.com"
SINA_BASE = "http://hq.sinajs.cn/list="
SINA_REFERER = "https://finance.sina.com.cn"

BATCH = 40


def _fmt(value, digits=2, default=None):
    try:
        num = float(value)
    except (TypeError, ValueError):
        return default
    if num != num:  # NaN
        return default
    return round(num, digits)


def _parse_tencent_line(line):
    """解析一条 v_sh600519="1~贵州茅台~600519~..."。"""
    if "=" not in line:
        return None
    payload = line.split("=", 1)[1].strip().strip('";')
    if not payload or "~" not in payload:
        return None
    f = payload.split("~")
    if len(f) < 50:
        return None

    info = None
    try:
        info = codes.parse(f[2])
    except codes.CodeError:
        return None

    name = f[1].strip()
    price = _fmt(f[3])
    prev_close = _fmt(f[4])
    if not price or not prev_close or prev_close <= 0:
        return None

    high = _fmt(f[33])
    low = _fmt(f[34])
    open_ = _fmt(f[5])
    volume_hand = _fmt(f[36], 0)          # 手
    amount_yuan = None
    # 字段 35 形如 "1348.00/16961/2286351076"，第三段是精确成交额（元），比字段 37 的万元更准
    if "/" in f[35]:
        parts = f[35].split("/")
        if len(parts) >= 3:
            amount_yuan = _fmt(parts[2])
    if amount_yuan is None:
        wan = _fmt(f[37])
        amount_yuan = wan * 10000 if wan is not None else None

    pct = (price - prev_close) / prev_close * 100.0
    chg = price - prev_close
    amplitude = ((high - low) / prev_close * 100.0) if (high and low) else None
    ratio = codes.limit_ratio(info, name)
    limit_up, limit_down = codes.limit_prices(prev_close, ratio)

    vendor_pct = _fmt(f[32])
    vendor_amp = _fmt(f[43])
    flags = []
    if vendor_pct is not None and abs(vendor_pct - pct) > 0.05:
        flags.append("涨跌幅与厂商字段有差异，已按价格重算")
    if vendor_amp is not None and amplitude is not None and abs(vendor_amp - amplitude) > 0.05:
        flags.append("振幅与厂商字段有差异，已按价格重算")

    record = {
        "code": info["code"],
        "market": info["market"],
        "board": info["board"],
        "prefixed": info["prefixed"],
        "name": name,
        "price": price,
        "prev_close": prev_close,
        "open": open_,
        "high": high,
        "low": low,
        "chg": round(chg, 2),
        "pct": round(pct, 2),
        "amplitude": round(amplitude, 2) if amplitude is not None else None,
        "volume_hand": volume_hand,
        "amount": amount_yuan,
        "turnover": _fmt(f[38]),
        "vol_ratio": _fmt(f[49]),
        "pe_ttm": _fmt(f[39]),
        "pb": _fmt(f[46]),
        "float_mv": _fmt(f[44]),   # 亿元
        "total_mv": _fmt(f[45]),   # 亿元
        "limit_up": limit_up,
        "limit_down": limit_down,
        "limit_ratio": ratio,
        "vendor_timestamp": f[30],
        "source": "腾讯行情",
        "flags": flags,
    }
    return _enrich(record)


def _parse_sina_line(line):
    """解析 var hq_str_sh600519="名称,今开,昨收,现价,最高,最低,..."。"""
    if "=" not in line:
        return None
    head, payload = line.split("=", 1)
    if "hq_str_" not in head:
        return None
    symbol = head.split("hq_str_")[1].strip()
    if symbol.startswith("s_"):
        return None
    payload = payload.strip().strip('";')
    f = payload.split(",")
    if len(f) < 32:
        return None
    try:
        info = codes.parse(symbol[2:])
    except codes.CodeError:
        return None

    name = f[0].strip()
    open_ = _fmt(f[1])
    prev_close = _fmt(f[2])
    price = _fmt(f[3])
    high = _fmt(f[4])
    low = _fmt(f[5])
    volume_hand = _fmt(f[8], 0)
    amount_yuan = _fmt(f[9])
    if not price or not prev_close or prev_close <= 0:
        return None

    pct = (price - prev_close) / prev_close * 100.0
    amplitude = ((high - low) / prev_close * 100.0) if (high and low) else None
    ratio = codes.limit_ratio(info, name)
    limit_up, limit_down = codes.limit_prices(prev_close, ratio)

    record = {
        "code": info["code"],
        "market": info["market"],
        "board": info["board"],
        "prefixed": info["prefixed"],
        "name": name,
        "price": price,
        "prev_close": prev_close,
        "open": open_,
        "high": high,
        "low": low,
        "chg": round(price - prev_close, 2),
        "pct": round(pct, 2),
        "amplitude": round(amplitude, 2) if amplitude is not None else None,
        "volume_hand": volume_hand,
        "amount": amount_yuan,
        "turnover": None,
        "vol_ratio": None,
        "pe_ttm": None,
        "pb": None,
        "float_mv": None,
        "total_mv": None,
        "limit_up": limit_up,
        "limit_down": limit_down,
        "limit_ratio": ratio,
        "vendor_timestamp": "%s %s" % (f[30], f[31]),
        "source": "新浪行情",
        "flags": ["备源数据，缺换手率与量比"],
    }
    return _enrich(record)


def _enrich(rec):
    """补充与交易直接相关的判定字段。"""
    price = rec["price"]
    rec["is_limit_up"] = abs(price - rec["limit_up"]) < 0.005
    rec["is_limit_down"] = abs(price - rec["limit_down"]) < 0.005
    rec["to_limit_up_pct"] = round((rec["limit_up"] - price) / price * 100.0, 2)
    rec["to_limit_down_pct"] = round((rec["limit_down"] - price) / price * 100.0, 2)
    high, low = rec["high"], rec["low"]
    if high is not None and low is not None and high > low:
        rec["day_position"] = round((price - low) / (high - low), 3)
    else:
        rec["day_position"] = None
    rec["is_one_word"] = bool(
        rec["open"] and abs(rec["open"] - rec["limit_up"]) < 0.005 and abs(price - rec["limit_up"]) < 0.005
    )
    rec["gap_pct"] = (
        round((rec["open"] - rec["prev_close"]) / rec["prev_close"] * 100.0, 2)
        if rec["open"]
        else None
    )
    return rec


def _chunks(items, size):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def snapshot(raw_codes, ttl=20):
    """批量取快照。

    返回 (records, meta)。records 以输入顺序排列，缺失的代码进入 meta["missing"]。
    """
    parsed = []
    rejected = []
    for raw in raw_codes:
        try:
            parsed.append(codes.parse(raw))
        except codes.CodeError as exc:
            rejected.append({"input": raw, "reason": str(exc)})

    if not parsed:
        return [], {"missing": [], "rejected": rejected, "sources": [], "fetched_at": time.time()}

    found = {}
    sources = []
    errors = []

    # 主源：腾讯
    for group in _chunks(parsed, BATCH):
        url = TENCENT_BASE + ",".join(item["prefixed"] for item in group)
        try:
            text, ts, cached = net.fetch(url, referer=TENCENT_REFERER, encoding="gbk", ttl=ttl)
            for line in text.split(";"):
                rec = _parse_tencent_line(line.strip())
                if rec:
                    found[rec["code"]] = rec
            sources.append({"name": "腾讯行情", "cached": cached})
        except RuntimeError as exc:
            errors.append(str(exc))

    # 备源：腾讯没拿到的用新浪补齐
    missing_codes = [item for item in parsed if item["code"] not in found]
    if missing_codes:
        for group in _chunks(missing_codes, BATCH):
            url = SINA_BASE + ",".join(item["prefixed"] for item in group)
            try:
                text, ts, cached = net.fetch(url, referer=SINA_REFERER, encoding="gbk", ttl=ttl)
                for line in text.split(";"):
                    rec = _parse_sina_line(line.strip())
                    if rec and rec["code"] not in found:
                        found[rec["code"]] = rec
                sources.append({"name": "新浪行情", "cached": cached})
            except RuntimeError as exc:
                errors.append(str(exc))

    records = [found[item["code"]] for item in parsed if item["code"] in found]
    missing = [item["prefixed"] for item in parsed if item["code"] not in found]
    meta = {
        "missing": missing,
        "rejected": rejected,
        "sources": sources,
        "errors": errors,
        "fetched_at": time.time(),
    }
    return records, meta


def index_snapshot(ttl=20):
    """上证 / 深证成指 / 创业板指 三个指数。"""
    wanted = [("sh000001", "上证指数"), ("sz399001", "深证成指"), ("sz399006", "创业板指")]
    url = SINA_BASE + ",".join("s_" + code for code, _ in wanted)
    out = []
    try:
        text, ts, cached = net.fetch(url, referer=SINA_REFERER, encoding="gbk", ttl=ttl)
    except RuntimeError:
        return [], {"errors": ["指数抓取失败"]}
    line_map = {}
    for line in text.split(";"):
        if "hq_str_s_" not in line:
            continue
        head, payload = line.split("=", 1)
        symbol = head.split("hq_str_s_")[1].strip()
        line_map[symbol] = payload.strip().strip('";').split(",")
    for code, label in wanted:
        f = line_map.get(code)
        if not f or len(f) < 6:
            continue
        out.append(
            {
                "code": code,
                "name": f[0] or label,
                "price": _fmt(f[1]),
                "chg": _fmt(f[2]),
                "pct": _fmt(f[3]),
                "volume_hand": _fmt(f[4], 0),
                "amount": (_fmt(f[5]) or 0) * 10000,  # 万元 -> 元
                "source": "新浪行情",
            }
        )
    return out, {"cached": cached, "fetched_at": time.time()}
