"""结构化预警清单。

用 JSON 而不是自由文本，原因是：
1. 条件能被程序判定，不依赖模型"记得"上次说了什么；
2. 多次对话之间可复现，触发记录可以留痕；
3. 用户随时能自己打开文件核对、修改。
"""

import datetime as dt
import json
import os
import uuid

from . import net, quotes

CONDITION_TYPES = {
    "price_above": "价格突破",
    "price_below": "价格跌破",
    "pct_above": "当日涨幅超过(%)",
    "pct_below": "当日跌幅超过(%)",
    "limit_up": "触及涨停",
    "limit_down": "触及跌停",
    "vol_ratio_above": "量比超过",
    "amount_above": "成交额超过(亿元)",
}


def default_path():
    """预警清单的固定位置。

    放在固定的缓存目录而不是当前工作目录，是因为对话中每条命令的工作目录可能不同，
    如果跟着 cwd 走，下一次对话就找不到上次的清单了。
    """
    override = os.environ.get("ATD_WATCHLIST", "").strip()
    if override:
        return override
    local = os.path.join(os.getcwd(), ".tapedesk", "watchlist.json")
    if os.path.exists(local):
        return local
    return os.path.join(net.cache_dir(), "watchlist.json")


def _load(path):
    if not os.path.exists(path):
        return {"version": 1, "updated_at": None, "items": []}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict) or "items" not in data:
            raise ValueError("结构不正确")
        return data
    except (OSError, ValueError):
        return {"version": 1, "updated_at": None, "items": [], "warning": "原文件损坏，已按空清单处理"}


def _save(path, data):
    data["updated_at"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def add(raw_code, cond_type, threshold=None, note="", path=None):
    if cond_type not in CONDITION_TYPES:
        raise ValueError("不支持的条件类型：%s（可用：%s）" % (cond_type, ", ".join(CONDITION_TYPES)))
    path = path or default_path()
    rec, _ = quotes.snapshot([raw_code])
    if not rec:
        raise ValueError("取不到 %s 的行情，无法建立预警" % raw_code)
    q = rec[0]

    data = _load(path)
    item = {
        "id": "w" + uuid.uuid4().hex[:8],
        "code": q["code"],
        "name": q["name"],
        "type": cond_type,
        "type_label": CONDITION_TYPES[cond_type],
        "threshold": threshold,
        "note": note,
        "status": "active",
        "created_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "created_price": q["price"],
        "triggered_at": None,
        "last_checked": None,
        "last_price": None,
    }
    data["items"].append(item)
    _save(path, data)
    return item, path


def remove(item_id, path=None):
    path = path or default_path()
    data = _load(path)
    before = len(data["items"])
    data["items"] = [i for i in data["items"] if i["id"] != item_id]
    _save(path, data)
    return before - len(data["items"])


def listing(path=None, include_closed=False):
    path = path or default_path()
    data = _load(path)
    items = data["items"]
    if not include_closed:
        items = [i for i in items if i["status"] == "active"]
    return items, path


def _evaluate(item, q):
    t, th = item["type"], item.get("threshold")
    price = q["price"]
    if t == "price_above":
        return price >= float(th), "现价 %.2f %s 阈值 %.2f" % (price, "≥" if price >= float(th) else "<", float(th))
    if t == "price_below":
        return price <= float(th), "现价 %.2f %s 阈值 %.2f" % (price, "≤" if price <= float(th) else ">", float(th))
    if t == "pct_above":
        return q["pct"] >= float(th), "涨幅 %.2f%% %s 阈值 %.2f%%" % (q["pct"], "≥" if q["pct"] >= float(th) else "<", float(th))
    if t == "pct_below":
        return q["pct"] <= -abs(float(th)), "涨幅 %.2f%% %s 阈值 -%.2f%%" % (
            q["pct"],
            "≤" if q["pct"] <= -abs(float(th)) else ">",
            abs(float(th)),
        )
    if t == "limit_up":
        return q["is_limit_up"], "现价 %.2f，涨停价 %.2f" % (price, q["limit_up"])
    if t == "limit_down":
        return q["is_limit_down"], "现价 %.2f，跌停价 %.2f" % (price, q["limit_down"])
    if t == "vol_ratio_above":
        vr = q.get("vol_ratio")
        if vr is None:
            return False, "该数据源没有量比字段"
        return vr >= float(th), "量比 %.2f %s 阈值 %.2f" % (vr, "≥" if vr >= float(th) else "<", float(th))
    if t == "amount_above":
        amt = (q.get("amount") or 0) / 1e8
        return amt >= float(th), "成交额 %.2f 亿 %s 阈值 %.2f 亿" % (amt, "≥" if amt >= float(th) else "<", float(th))
    return False, "未知条件"


def check(path=None, mark=True):
    path = path or default_path()
    data = _load(path)
    active = [i for i in data["items"] if i["status"] == "active"]
    if not active:
        return {"ok": True, "checked": 0, "triggered": [], "pending": [], "path": path}

    codes = sorted(set(i["code"] for i in active))
    recs, meta = quotes.snapshot(codes)
    by_code = {r["code"]: r for r in recs}

    triggered, pending, missed = [], [], []
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for item in active:
        q = by_code.get(item["code"])
        if not q:
            missed.append(item)
            continue
        hit, detail = _evaluate(item, q)
        item["last_checked"] = now
        item["last_price"] = q["price"]
        row = {
            "id": item["id"],
            "code": item["code"],
            "name": item["name"],
            "type_label": item["type_label"],
            "note": item["note"],
            "detail": detail,
            "price": q["price"],
            "pct": q["pct"],
            "source": q["source"],
        }
        if hit:
            item["status"] = "triggered"
            item["triggered_at"] = now
            triggered.append(row)
        else:
            pending.append(row)

    if mark:
        _save(path, data)
    return {
        "ok": True,
        "checked": len(active),
        "triggered": triggered,
        "pending": pending,
        "missing": [{"id": i["id"], "code": i["code"], "name": i["name"]} for i in missed],
        "path": path,
        "checked_at": now,
        "meta": meta,
    }
