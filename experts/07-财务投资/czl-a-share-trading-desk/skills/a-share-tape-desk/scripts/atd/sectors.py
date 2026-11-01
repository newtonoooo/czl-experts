"""板块排行与龙头识别。

数据源：新浪行业板块 / 概念板块聚合接口（一次返回全部板块与领涨股）。
龙头判定不只看涨幅，还要看成交额与换手，避免把一字板的小票当主线龙头。

另外把每日板块涨幅落盘，积累几天后可以给出"连续上榜"这类持续性证据；
样本不足时如实标注"需次日验证"，不假装知道持续性。
"""

import datetime as dt
import json
import os

from . import net

HY_URL = "http://vip.stock.finance.sina.com.cn/q/view/newSinaHy.php"
GN_URL = "http://vip.stock.finance.sina.com.cn/q/view/newFLJK.php?param=class"
CONST_URL = (
    "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
    "Market_Center.getHQNodeData?page=1&num=%d&sort=changepercent&asc=0&node=%s&symbol=&_s_r_a=page"
)
REFERER = "https://finance.sina.com.cn"


def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_boards(text):
    """解析 var X = {"node":"node,名称,家数,均价,均涨跌额,涨跌幅,量,额,领涨代码,领涨涨幅,领涨价,领涨涨跌额,领涨名称", ...}"""
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return []
    try:
        payload = json.loads(text[start : end + 1])
    except ValueError:
        return []
    boards = []
    for node, csv in payload.items():
        f = str(csv).split(",")
        if len(f) < 9:
            continue
        boards.append(
            {
                "node": node,
                "name": f[1],
                "count": int(_num(f[2])),
                "avg_price": _num(f[3]),
                "pct": _num(f[5]),
                "volume": _num(f[6]),
                "amount": _num(f[7]),
                "leader_symbol": f[8] if len(f) > 8 else "",
                "leader_pct": _num(f[9]) if len(f) > 9 else None,
                "leader_price": _num(f[10]) if len(f) > 10 else None,
                "leader_name": f[12] if len(f) > 12 else "",
            }
        )
    return boards


def _store_path():
    return os.path.join(net.cache_dir(), "board_history.json")


def _load_store():
    path = _store_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_store(store):
    # 只保留最近 20 个交易日
    keys = sorted(store.keys())[-20:]
    trimmed = {k: store[k] for k in keys}
    try:
        with open(_store_path(), "w", encoding="utf-8") as fh:
            json.dump(trimmed, fh, ensure_ascii=False)
    except OSError:
        pass


def _streak(store, kind, node, today_key):
    """连续上涨天数（含今日）。仅用已落盘的历史。"""
    dates = [d for d in sorted(store.keys()) if d < today_key]
    streak = 0
    for date in reversed(dates):
        pct = store.get(date, {}).get(kind, {}).get(node)
        if pct is not None and pct > 0:
            streak += 1
        else:
            break
    return streak


def load_boards(kind="industry", ttl=60):
    url = HY_URL if kind == "industry" else GN_URL
    text, ts, cached = net.fetch(url, referer=REFERER, encoding="gbk", ttl=ttl)
    boards = _parse_boards(text)
    return boards, {"cached": cached, "fetched_at": ts, "kind": kind}


def _classify(boards, market_median_pct=None):
    for b in boards:
        up_share = b.get("up_share")
        if up_share is None:
            up_share = 1.0 if b["pct"] > 0 else 0.0
        b["tag"] = "中性"
        if b["pct"] >= 1.5 and b["count"] >= 12:
            b["tag"] = "强势"
        if b["pct"] >= 2.5 and b["count"] < 12:
            b["tag"] = "情绪"
        if b["pct"] <= -1.5:
            b["tag"] = "弱势"
    return boards


def leaders(node, top=3, ttl=60):
    """取某板块成分股，按涨幅为主、成交额与换手为辅综合排序。

    权重：涨幅 55（按 9.8% 封顶归一）、成交额分位 25、换手分位 12、涨停加成 8。
    用"分位"而不是"绝对值"，是因为不同板块的成交体量差一个数量级，
    直接比绝对成交额会把大盘股永远排成龙头。
    """
    try:
        text, ts, cached = net.fetch(CONST_URL % (80, node), referer=REFERER, ttl=ttl)
        rows = json.loads(text.strip() or "[]")
    except (RuntimeError, ValueError):
        return [], {"error": "成分股抓取失败"}

    pool = []
    for row in rows or []:
        name = (row.get("name") or "").strip()
        price = _num(row.get("trade"))
        pct = _num(row.get("changepercent"))
        amount = _num(row.get("amount"))
        turnover = _num(row.get("turnoverratio"))
        if price <= 0 or "ST" in name.upper() or "退" in name:
            continue
        if amount < 5e7:  # 成交额低于 5000 万不参与龙头评选
            continue
        pool.append(
            {
                "code": row.get("code"),
                "name": name,
                "price": price,
                "pct": pct,
                "amount": amount,
                "turnover": turnover,
            }
        )
    if not pool:
        return [], {"cached": cached, "rows": len(rows or []), "note": "无满足流动性门槛的成分股"}

    by_amount = sorted(pool, key=lambda x: x["amount"])
    by_turnover = sorted(pool, key=lambda x: x["turnover"])
    n = len(pool) - 1 or 1
    amount_rank = {id(x): i / float(n) for i, x in enumerate(by_amount)}
    turnover_rank = {id(x): i / float(n) for i, x in enumerate(by_turnover)}

    for x in pool:
        x["score"] = round(
            min(x["pct"] / 9.8, 1.0) * 55
            + amount_rank[id(x)] * 25
            + turnover_rank[id(x)] * 12
            + (8 if x["pct"] >= 9.7 else 0),
            1,
        )
    pool.sort(key=lambda x: x["score"], reverse=True)
    out = [
        {
            "code": x["code"],
            "name": x["name"],
            "price": round(x["price"], 2),
            "pct": round(x["pct"], 2),
            "amount_yi": round(x["amount"] / 1e8, 2),
            "turnover": round(x["turnover"], 2),
            "score": x["score"],
        }
        for x in pool[:top]
    ]
    return out, {"cached": cached, "rows": len(rows or []), "pool": len(pool)}


def rank(kind="industry", top=8, with_leaders=True, ttl=60, trade_date=None):
    boards, meta = load_boards(kind=kind, ttl=ttl)
    if not boards:
        return {"ok": False, "reason": "板块数据抓取失败", "meta": meta}

    _classify(boards)
    boards.sort(key=lambda b: b["pct"], reverse=True)
    today_key = trade_date or dt.date.today().isoformat()

    store = _load_store()
    snapshot = {b["node"]: round(b["pct"], 3) for b in boards}
    store.setdefault(today_key, {})[kind] = snapshot
    _save_store(store)

    hot = boards[:top]
    cold = boards[-min(top, len(boards)) :][::-1]

    enriched = []
    for b in hot:
        item = dict(b)
        item["streak"] = _streak(store, kind, b["node"], today_key)
        item["leader_candidates"] = []
        if with_leaders:
            cand, lmeta = leaders(b["node"], top=3, ttl=ttl)
            item["leader_candidates"] = cand
            item["leader_meta"] = lmeta
        enriched.append(item)

    return {
        "ok": True,
        "kind": kind,
        "trade_date": today_key,
        "hot": enriched,
        "cold": [
            {
                "name": b["name"],
                "pct": round(b["pct"], 2),
                "count": b["count"],
                "amount_yi": round(b["amount"] / 1e8, 2),
                "leader_name": b["leader_name"],
            }
            for b in cold
        ],
        "stat": {
            "boards": len(boards),
            "up_boards": len([b for b in boards if b["pct"] > 0]),
            "down_boards": len([b for b in boards if b["pct"] < 0]),
            "history_days": len([d for d in store.keys() if d < today_key]),
        },
        "meta": meta,
    }
