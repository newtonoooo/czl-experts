"""全市场扫描与情绪评分。

做法：拉一遍沪深A股全量快照（新浪分页接口，约 56 页、2 秒），
在本地把"涨跌家数 / 涨跌停 / 涨跌分布 / 成交额 / 赚钱效应"全部算出来，
再用固定权重压成一个 0-100 的情绪温度与风险等级。

为什么不直接用行情软件公布的"情绪值"：口径不透明、无法复核。
这里的每一项都能在输出里看到原始计数，用户能自己核对。
"""

import concurrent.futures as futures
import datetime as dt
import json
import os
import time

from . import clock, codes, net, quotes

SINA_LIST = (
    "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
    "Market_Center.getHQNodeData?page=%d&num=100&sort=changepercent&asc=0&node=hs_a&symbol=&_s_r_a=page"
)
SINA_COUNT = (
    "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
    "Market_Center.getHQNodeStockCount?node=hs_a"
)
SINA_REFERER = "https://finance.sina.com.cn"

BUCKETS = [
    ("涨9.8%以上", 9.8, 99),
    ("涨7%~9.8%", 7, 9.8),
    ("涨4%~7%", 4, 7),
    ("涨1%~4%", 1, 4),
    ("涨0~1%", 0.0001, 1),
    ("平盘", -0.0001, 0.0001),
    ("跌0~1%", -1, -0.0001),
    ("跌1%~4%", -4, -1),
    ("跌4%~7%", -7, -4),
    ("跌7%~9.8%", -9.8, -7),
    ("跌9.8%以下", -99, -9.8),
]


def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _fetch_page(page, ttl):
    text, ts, cached = net.fetch(SINA_LIST % page, referer=SINA_REFERER, ttl=ttl)
    body = text.strip()
    if not body or body == "null":
        return [], ts
    try:
        rows = json.loads(body)
    except ValueError:
        return [], ts
    return (rows or []), ts


def sweep(ttl=25, workers=10, max_pages=70):
    """拉全市场快照。返回 (rows, meta)。"""
    errors = []
    count = None
    try:
        text, _, _ = net.fetch(SINA_COUNT, referer=SINA_REFERER, ttl=600)
        count = int(text.strip().strip('"'))
    except (RuntimeError, ValueError) as exc:
        errors.append("总数接口失败：%s" % exc)

    pages = max_pages if not count else min(max_pages, (count + 99) // 100)
    rows, stamps = [], []
    with futures.ThreadPoolExecutor(max_workers=workers) as pool:
        jobs = {pool.submit(_fetch_page, p, ttl): p for p in range(1, pages + 1)}
        for job in futures.as_completed(jobs):
            page = jobs[job]
            try:
                data, ts = job.result()
                rows.extend(data)
                stamps.append(ts)
            except RuntimeError as exc:
                errors.append("第%s页失败：%s" % (page, exc))

    seen = set()
    uniq = []
    for row in rows:
        sym = row.get("symbol") or ""
        if not sym or sym in seen:
            continue
        seen.add(sym)
        uniq.append(row)

    meta = {
        "declared_total": count,
        "pages": pages,
        "rows": len(uniq),
        "errors": errors,
        "fetched_at": max(stamps) if stamps else time.time(),
        "source": "新浪行情（hs_a 全量分页）",
    }
    return uniq, meta


def _classify(rows):
    """逐只归类：涨、跌、平、停牌、涨停、跌停。"""
    stats = {
        "total": len(rows),
        "suspended": 0,
        "up": 0,
        "down": 0,
        "flat": 0,
        "limit_up": 0,
        "limit_down": 0,
        "up5": 0,
        "down5": 0,
        "amount": 0.0,
        "pcts": [],
        "buckets": {label: 0 for label, _, _ in BUCKETS},
        "limit_up_names": [],
        "limit_down_names": [],
        "unknown": 0,
    }
    for row in rows:
        name = (row.get("name") or "").strip()
        code = row.get("code") or (row.get("symbol") or "")[2:]
        price = _num(row.get("trade"))
        prev = _num(row.get("settlement"))
        pct = _num(row.get("changepercent"))
        amount = _num(row.get("amount"))
        volume = _num(row.get("volume"))

        if price <= 0 or prev <= 0 or volume <= 0:
            stats["suspended"] += 1
            continue

        stats["amount"] += amount
        stats["pcts"].append(pct)

        try:
            info = codes.parse(code)
            ratio = codes.limit_ratio(info, name)
            limit_up, limit_down = codes.limit_prices(prev, ratio)
        except codes.CodeError:
            stats["unknown"] += 1
            limit_up = limit_down = None

        if pct > 0.0001:
            stats["up"] += 1
        elif pct < -0.0001:
            stats["down"] += 1
        else:
            stats["flat"] += 1

        if pct >= 5:
            stats["up5"] += 1
        if pct <= -5:
            stats["down5"] += 1

        if limit_up is not None and abs(price - limit_up) < 0.005:
            stats["limit_up"] += 1
            if len(stats["limit_up_names"]) < 30:
                stats["limit_up_names"].append("%s(%s)" % (name, code))
        if limit_down is not None and abs(price - limit_down) < 0.005:
            stats["limit_down"] += 1
            if len(stats["limit_down_names"]) < 30:
                stats["limit_down_names"].append("%s(%s)" % (name, code))

        for label, lo, hi in BUCKETS:
            if lo <= pct < hi:
                stats["buckets"][label] += 1
                break
    return stats


def _median(values):
    if not values:
        return None
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    return ordered[mid] if n % 2 else (ordered[mid - 1] + ordered[mid]) / 2.0


def _clamp(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, v))


def _scale(value, low, high):
    """把 value 从 [low, high] 线性映射到 0-100，并截断。"""
    if high == low:
        return 50.0
    return _clamp((value - low) / (high - low) * 100.0)


def _amount_store_path():
    return os.path.join(net.cache_dir(), "amount_history.json")


def _load_amount_store():
    path = _amount_store_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_amount_store(store):
    try:
        with open(_amount_store_path(), "w", encoding="utf-8") as fh:
            json.dump(store, fh, ensure_ascii=False)
    except OSError:
        pass


def score(stats, indices, amount_prev_avg=None, trade_date=None):
    """情绪温度与风险等级。权重与阈值见 references/sentiment-rubric.md。"""
    active = max(1, stats["up"] + stats["down"] + stats["flat"])
    up_share = stats["up"] / active

    parts = {}

    # 1) 涨跌家数结构 25 分：上涨占比 0.15 视为冰点，0.75 视为普涨
    parts["涨跌家数"] = {
        "weight": 25,
        "score": round(_scale(up_share, 0.15, 0.75) * 0.25, 2),
        "detail": "上涨 %d 家 / 下跌 %d 家，上涨占比 %.1f%%" % (stats["up"], stats["down"], up_share * 100),
    }

    # 2) 涨跌停结构 20 分：对数缩放，避免几十家涨停就把分数顶满；跌停惩罚更重
    import math as _math

    limit_raw = 50 + 16.0 * _math.log(1 + stats["limit_up"]) - 22.0 * _math.log(1 + stats["limit_down"])
    parts["涨停跌停"] = {
        "weight": 20,
        "score": round(_clamp(limit_raw) * 0.20, 2),
        "detail": "涨停 %d 家 / 跌停 %d 家" % (stats["limit_up"], stats["limit_down"]),
    }

    # 3) 指数表现 15 分：三指数等权，-1.5% 到 +1.5% 线性
    if indices:
        avg_pct = sum(i["pct"] or 0 for i in indices) / float(len(indices))
    else:
        avg_pct = 0.0
    parts["指数"] = {
        "weight": 15,
        "score": round(_scale(avg_pct, -1.5, 1.5) * 0.15, 2),
        "detail": "三大指数平均涨跌 %.2f%%" % avg_pct,
    }

    # 4) 赚钱效应 15 分：涨超5% 与跌超5% 的净差，占总家数比例
    net5 = (stats["up5"] - stats["down5"]) / float(active) * 100.0
    parts["赚钱效应"] = {
        "weight": 15,
        "score": round(_scale(net5, -8, 8) * 0.15, 2),
        "detail": "涨超5%% %d 家 / 跌超5%% %d 家（净差 %.1f 个百分点）" % (stats["up5"], stats["down5"], net5),
    }

    # 5) 量能 15 分：与近 5 个交易日平均成交额比较；样本不足给中性 50
    amount_yi = stats["amount"] / 1e8
    if amount_prev_avg:
        ratio = amount_yi / amount_prev_avg if amount_prev_avg else None
        vol_score = _scale(ratio, 0.7, 1.4) if ratio else 50.0
        vol_detail = "两市成交 %.0f 亿，近5日均额 %.0f 亿，量比 %.2f" % (amount_yi, amount_prev_avg, ratio or 0)
    else:
        vol_score = 50.0
        vol_detail = "两市成交 %.0f 亿（历史样本不足，量能项按中性计）" % amount_yi
    parts["量能"] = {"weight": 15, "score": round(vol_score * 0.15, 2), "detail": vol_detail}

    # 6) 分布重心 10 分：中位数涨跌幅，-1.5% 到 +1.5%
    med = _median(stats["pcts"]) or 0.0
    parts["中位涨幅"] = {
        "weight": 10,
        "score": round(_scale(med, -1.5, 1.5) * 0.10, 2),
        "detail": "个股涨跌幅中位数 %.2f%%" % med,
    }

    total = round(sum(v["score"] for v in parts.values()), 1)

    if total < 20:
        temp, temp_label = total, "冰点"
    elif total < 40:
        temp, temp_label = total, "偏冷"
    elif total < 60:
        temp, temp_label = total, "中性"
    elif total < 80:
        temp, temp_label = total, "偏热"
    else:
        temp, temp_label = total, "过热"

    # 风险等级：情绪极端 + 跌停数量 + 指数跌幅共同决定
    risk_pts = 0
    if total >= 85 or total <= 15:
        risk_pts += 2
    elif total >= 75 or total <= 25:
        risk_pts += 1
    if stats["limit_down"] >= 20:
        risk_pts += 2
    elif stats["limit_down"] >= 8:
        risk_pts += 1
    if indices and min((i["pct"] or 0) for i in indices) <= -1.5:
        risk_pts += 1
    if stats["down5"] >= active * 0.15:
        risk_pts += 1

    if risk_pts >= 4:
        risk_level, risk_note = "高", "波动与分化同时放大，追高的回撤风险显著"
    elif risk_pts >= 2:
        risk_level, risk_note = "中", "结构性行情，方向对了才赚钱，方向错了亏得快"
    else:
        risk_level, risk_note = "低", "情绪与波动都在正常区间，容错相对高"

    # 建议仓位上限：情绪驱动，但过热时反向收紧
    if temp_label == "冰点":
        pos, pos_note = 20, "冰点不抢反弹，等确认信号；试探仓不超过两成"
    elif temp_label == "偏冷":
        pos, pos_note = 30, "偏冷阶段以观察为主，三成以内试错"
    elif temp_label == "中性":
        pos, pos_note = 50, "中性环境可正常参与，五成为中枢"
    elif temp_label == "偏热":
        pos, pos_note = 60, "偏热可适度提高仓位，但只做主线"
    else:
        pos, pos_note = 30, "过热阶段收紧仓位，兑现优先于加仓"
    if risk_level == "高":
        pos = min(pos, 40)
        pos_note += "；风险等级高，实际仓位再打七折"

    return {
        "score": total,
        "temperature": temp_label,
        "risk_level": risk_level,
        "risk_note": risk_note,
        "suggested_max_position": pos,
        "position_note": pos_note,
        "parts": parts,
        "metrics": {
            "active": active,
            "up_share": round(up_share, 4),
            "limit_ratio": round(
                stats["limit_up"] / float((stats["limit_up"] + stats["limit_down"]) or 1), 3
            ),
            "median_pct": round(med, 2),
            "avg_pct": round(sum(stats["pcts"]) / len(stats["pcts"]), 2) if stats["pcts"] else None,
            "amount_yi": round(amount_yi, 1),
            "up5": stats["up5"],
            "down5": stats["down5"],
        },
        "trade_date": trade_date,
    }


def pulse(ttl=25, with_indices=True):
    """一次大盘体检：全市场扫描 + 指数 + 情绪评分。"""
    session = clock.session_block()
    rows, meta = sweep(ttl=ttl)
    if not rows:
        return {"ok": False, "reason": "全市场快照抓取失败", "meta": meta, "session": session}

    stats = _classify(rows)
    indices = []
    idx_meta = {}
    if with_indices:
        indices, idx_meta = quotes.index_snapshot(ttl=ttl)

    trade_date = None
    if indices:
        trade_date = session["timestamp"][:10]
    else:
        from . import history

        trade_date = history.last_trade_date() or session["timestamp"][:10]

    # 量能基准：缓存里同日期之前的成交额
    store = _load_amount_store()
    today_key = trade_date or dt.date.today().isoformat()
    prev_avg = None
    history_amounts = [v for k, v in sorted(store.items()) if k < today_key][-5:]
    if len(history_amounts) >= 3:
        prev_avg = sum(history_amounts) / float(len(history_amounts))
    store[today_key] = round(stats["amount"] / 1e8, 1)
    _save_amount_store(store)

    scored = score(stats, indices, amount_prev_avg=prev_avg, trade_date=trade_date)
    age = clock.describe_data_age(trade_date) if trade_date else {"kind": "未知", "label": "数据日期未知"}

    dist = [
        {"label": label, "count": stats["buckets"][label]}
        for label, _, _ in BUCKETS
        if stats["buckets"][label] > 0
    ]

    return {
        "ok": True,
        "session": session,
        "data_age": age,
        "indices": indices,
        "breadth": {
            "total": stats["total"],
            "active": stats["up"] + stats["down"] + stats["flat"],
            "suspended": stats["suspended"],
            "up": stats["up"],
            "down": stats["down"],
            "flat": stats["flat"],
            "limit_up": stats["limit_up"],
            "limit_down": stats["limit_down"],
            "up5": stats["up5"],
            "down5": stats["down5"],
            "amount_yi": round(stats["amount"] / 1e8, 1),
            "amount_prev_avg_yi": round(prev_avg, 1) if prev_avg else None,
        },
        "distribution": dist,
        "limit_up_sample": stats["limit_up_names"],
        "limit_down_sample": stats["limit_down_names"],
        "sentiment": scored,
        "meta": meta,
        "index_meta": idx_meta,
    }
