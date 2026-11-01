"""交易时段与数据时效。

不写死节假日表（会过期），改为"时钟 + 数据日期"双判定：
时钟给出当前处于哪个交易阶段；数据日期由指数日线的最新一根K线决定。
两者结合就能区分"盘中实时""午休定格""今日休市（沿用上一交易日收盘）"。
"""

import datetime as dt

MORNING_OPEN = dt.time(9, 15)
MORNING_AUCTION_END = dt.time(9, 25)
CONTINUOUS_OPEN = dt.time(9, 30)
MORNING_CLOSE = dt.time(11, 30)
AFTERNOON_OPEN = dt.time(13, 0)
CLOSING_AUCTION = dt.time(14, 57)
MARKET_CLOSE = dt.time(15, 0)

TOTAL_MINUTES = 240  # 上午120 + 下午120


def now():
    return dt.datetime.now()


def phase(ts=None):
    """返回当前交易阶段。

    phase 取值：盘前 / 集合竞价 / 待开盘 / 早盘 / 午间休市 / 午盘 / 收盘集合竞价 / 已收盘 / 休市
    """
    ts = ts or now()
    if ts.weekday() >= 5:
        return {
            "phase": "休市",
            "is_open": False,
            "is_weekend": True,
            "elapsed_minutes": 0,
            "progress": 0.0,
            "note": "周末休市，行情为上一交易日收盘数据",
        }
    t = ts.time()
    if t < MORNING_OPEN:
        p, is_open, note = "盘前", False, "开盘前，行情为上一交易日收盘数据"
    elif t < MORNING_AUCTION_END:
        p, is_open, note = "集合竞价", False, "9:15-9:25 集合竞价，可挂单不成交，价格不连续"
    elif t < CONTINUOUS_OPEN:
        p, is_open, note = "待开盘", False, "9:25-9:30 撮合完成，开盘价已定，连续竞价未开始"
    elif t < MORNING_CLOSE:
        p, is_open, note = "早盘", True, "早盘连续竞价"
    elif t < AFTERNOON_OPEN:
        p, is_open, note = "午间休市", False, "11:30-13:00 休市，上午数据已定格"
    elif t < CLOSING_AUCTION:
        p, is_open, note = "午盘", True, "午盘连续竞价"
    elif t < MARKET_CLOSE:
        p, is_open, note = "收盘集合竞价", False, "14:57-15:00 收盘集合竞价，只可挂单"
    else:
        p, is_open, note = "已收盘", False, "已收盘，行情为今日收盘数据"

    return {
        "phase": p,
        "is_open": is_open,
        "is_weekend": False,
        "elapsed_minutes": elapsed_minutes(ts),
        "progress": round(elapsed_minutes(ts) / float(TOTAL_MINUTES), 3),
        "note": note,
    }


def elapsed_minutes(ts=None):
    """已完成的交易分钟数（0-240）。"""
    ts = ts or now()
    t = ts.time()
    if t < CONTINUOUS_OPEN:
        return 0
    if t <= MORNING_CLOSE:
        return int((ts - ts.replace(hour=9, minute=30, second=0, microsecond=0)).total_seconds() // 60)
    if t < AFTERNOON_OPEN:
        return 120
    if t <= MARKET_CLOSE:
        return 120 + int((ts - ts.replace(hour=13, minute=0, second=0, microsecond=0)).total_seconds() // 60)
    return TOTAL_MINUTES


def describe_data_age(data_date, ts=None):
    """根据数据日期与当前时钟判断数据性质。

    返回 dict：kind（实时/定格/历史）、label（中文说明）、age_days。
    """
    ts = ts or now()
    today = ts.date()
    if not data_date:
        return {"kind": "未知", "label": "数据日期未知", "age_days": None}
    if isinstance(data_date, str):
        try:
            data_date = dt.date.fromisoformat(data_date[:10])
        except ValueError:
            return {"kind": "未知", "label": "数据日期格式无法解析：%s" % data_date, "age_days": None}
    gap = (today - data_date).days
    if gap == 0:
        p = phase(ts)["phase"]
        if p in ("早盘", "午盘", "收盘集合竞价"):
            return {"kind": "实时", "label": "今日盘中实时数据", "age_days": 0}
        return {"kind": "定格", "label": "今日数据（当前%s）" % p, "age_days": 0}
    if gap == 1:
        return {"kind": "历史", "label": "上一交易日收盘数据（今日未开盘或休市）", "age_days": 1}
    return {"kind": "历史", "label": "最近交易日 %s 的收盘数据，距今 %d 天" % (data_date, gap), "age_days": gap}


def session_block(ts=None):
    """给报告用的时段块。"""
    ts = ts or now()
    p = phase(ts)
    return {
        "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
        "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][ts.weekday()],
        "phase": p["phase"],
        "is_open": p["is_open"],
        "elapsed_minutes": p["elapsed_minutes"],
        "progress": p["progress"],
        "note": p["note"],
    }
