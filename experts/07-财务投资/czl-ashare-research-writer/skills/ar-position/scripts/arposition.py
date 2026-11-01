#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""持仓体检计算：集中度、行业暴露、相关性、事件撞车、流动性（零第三方依赖）。

输入全部为本地 JSON，不联网。行情与行业分类由 arfetch / 用户提供后填入。

holdings.json:
  [{"code":"600519.SH","name":"贵州茅台","shares":100,"cost":1400,
    "price":1349.47,"industry":"食品饮料","style":"大盘价值","amount_avg20":2300000000}]

events.json:
  [{"date":"2026-10-31","code":"600519.SH","name":"贵州茅台","event":"三季报","impact":"高"}]

series.json:
  {"600519.SH":[1340,1355,...], "000001.SZ":[11.2,11.4,...]}

CLI:
  python arposition.py check --file holdings.json
  python arposition.py events --file events.json
  python arposition.py corr --file series.json
  python arposition.py selftest
"""
import argparse
import json
import sys
from itertools import combinations

CONCENTRATION_SINGLE = 30.0   # 单票占比告警线 %
CONCENTRATION_INDUSTRY = 50.0  # 单行业占比告警线 %
ILLIQUID_RATIO = 10.0          # 持仓市值/日均成交额 告警线 %
ILLIQUID_AMOUNT = 5e7          # 日均成交额告警线（元）


def load(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def concentration(holdings):
    rows, total = [], 0.0
    for h in holdings:
        shares = float(h.get("shares") or 0)
        price = float(h.get("price") or 0)
        mv = shares * price
        total += mv
        rows.append({"code": h.get("code"), "name": h.get("name"), "mv": mv,
                     "industry": h.get("industry") or "未分类",
                     "style": h.get("style") or "未分类",
                     "amount_avg20": h.get("amount_avg20"),
                     "shares": shares, "price": price,
                     "cost": h.get("cost")})
    if total <= 0:
        raise ValueError("持仓市值为 0，请检查 shares 与 price")

    for r in rows:
        r["weight_pct"] = round(r["mv"] / total * 100, 2)
        if r.get("cost"):
            r["pnl_pct"] = round((r["price"] / float(r["cost"]) - 1) * 100, 2)
        else:
            r["pnl_pct"] = None
        if r.get("amount_avg20"):
            r["liq_ratio_pct"] = round(r["mv"] / float(r["amount_avg20"]) * 100, 2)
        else:
            r["liq_ratio_pct"] = None

    rows.sort(key=lambda x: x["mv"], reverse=True)
    top3 = round(sum(r["weight_pct"] for r in rows[:3]), 2)

    by_ind, by_style = {}, {}
    for r in rows:
        by_ind[r["industry"]] = round(by_ind.get(r["industry"], 0) + r["weight_pct"], 2)
        by_style[r["style"]] = round(by_style.get(r["style"], 0) + r["weight_pct"], 2)

    flags = []
    for r in rows:
        if r["weight_pct"] >= CONCENTRATION_SINGLE:
            flags.append({"level": "high", "item": r["name"],
                          "msg": "单票占比 %.1f%%，超过 %.0f%% 集中度告警线"
                                 % (r["weight_pct"], CONCENTRATION_SINGLE)})
    for ind, w in by_ind.items():
        if w >= CONCENTRATION_INDUSTRY:
            flags.append({"level": "high", "item": ind,
                          "msg": "行业「%s」占比 %.1f%%，超过 %.0f%%"
                                 % (ind, w, CONCENTRATION_INDUSTRY)})
    for r in rows:
        if r["liq_ratio_pct"] is not None and r["liq_ratio_pct"] >= ILLIQUID_RATIO:
            flags.append({"level": "mid", "item": r["name"],
                          "msg": "持仓市值占 20 日均成交额 %.1f%%，退出需要多个交易日"
                                 % r["liq_ratio_pct"]})
        if r["amount_avg20"] is not None and float(r["amount_avg20"]) < ILLIQUID_AMOUNT:
            flags.append({"level": "mid", "item": r["name"],
                          "msg": "20 日均成交额不足 5000 万元，存在流动性折价"})

    return {
        "count": len(rows),
        "total_mv": round(total, 2),
        "total_mv_yi": round(total / 1e8, 4),
        "top3_weight_pct": top3,
        "holdings": rows,
        "by_industry": dict(sorted(by_ind.items(), key=lambda x: -x[1])),
        "by_style": dict(sorted(by_style.items(), key=lambda x: -x[1])),
        "flags": flags,
    }


def pearson(a, b):
    n = min(len(a), len(b))
    if n < 3:
        return None
    a, b = list(a)[:n], list(b)[:n]
    ra = [a[i] / a[i - 1] - 1 for i in range(1, n) if a[i - 1]]
    rb = [b[i] / b[i - 1] - 1 for i in range(1, n) if b[i - 1]]
    m = min(len(ra), len(rb))
    if m < 3:
        return None
    ra, rb = ra[:m], rb[:m]
    ma, mb = sum(ra) / m, sum(rb) / m
    cov = sum((ra[i] - ma) * (rb[i] - mb) for i in range(m))
    va = sum((x - ma) ** 2 for x in ra) ** 0.5
    vb = sum((x - mb) ** 2 for x in rb) ** 0.5
    if va == 0 or vb == 0:
        return None
    return round(cov / (va * vb), 3)


def correlation_matrix(series):
    keys = [k for k, v in series.items() if len(v) >= 3]
    pairs = []
    for a, b in combinations(keys, 2):
        r = pearson(series[a], series[b])
        if r is None:
            continue
        level = "高" if abs(r) >= 0.7 else ("中" if abs(r) >= 0.4 else "低")
        pairs.append({"a": a, "b": b, "corr": r, "level": level,
                      "note": "同涨同跌，不构成分散" if r >= 0.7 else
                              ("反向，可部分对冲" if r <= -0.7 else "")})
    pairs.sort(key=lambda x: -abs(x["corr"]))
    return {"sample_window": {k: len(v) for k, v in series.items()},
            "pairs": pairs,
            "max_corr": pairs[0] if pairs else None}


def event_timeline(events, window_days=7):
    rows = sorted(events, key=lambda e: str(e.get("date")))
    clusters = []
    for i in range(len(rows)):
        group = [rows[i]]
        for j in range(i + 1, len(rows)):
            d1 = _parse(rows[i].get("date"))
            d2 = _parse(rows[j].get("date"))
            if d1 and d2 and (d2 - d1).days <= window_days:
                group.append(rows[j])
            else:
                break
        if len(group) >= 3:
            clusters.append({"start": group[0]["date"], "end": group[-1]["date"],
                             "count": len(group),
                             "items": [g.get("name") for g in group],
                             "msg": "%s 至 %s 有 %d 个事件集中发生，注意同时暴露"
                                    % (group[0]["date"], group[-1]["date"], len(group))})
    uniq, seen = [], set()
    for c in clusters:
        key = (c["start"], c["end"], c["count"])
        if key not in seen:
            seen.add(key)
            uniq.append(c)
    return {"count": len(rows), "timeline": rows, "clusters": uniq}


def _parse(text):
    from datetime import date
    try:
        y, m, d = str(text)[:10].split("-")
        return date(int(y), int(m), int(d))
    except (ValueError, AttributeError):
        return None


def selftest():
    holdings = [
        {"code": "600519.SH", "name": "贵州茅台", "shares": 100, "cost": 1400,
         "price": 1349.47, "industry": "食品饮料", "style": "大盘价值",
         "amount_avg20": 2.3e9},
        {"code": "000858.SZ", "name": "五粮液", "shares": 1000, "cost": 140,
         "price": 132.0, "industry": "食品饮料", "style": "大盘价值",
         "amount_avg20": 1.1e9},
        {"code": "300750.SZ", "name": "宁德时代", "shares": 500, "cost": 200,
         "price": 250.0, "industry": "电力设备", "style": "大盘成长",
         "amount_avg20": 4.0e9},
    ]
    r = concentration(holdings)
    checks = [
        ("总市值计算", r["total_mv"] > 0),
        ("权重合计 100", abs(sum(h["weight_pct"] for h in r["holdings"]) - 100) < 0.05),
        ("行业集中告警", any("食品饮料" in f["msg"] for f in r["flags"])),
        ("盈亏可算", r["holdings"][0]["pnl_pct"] is not None),
        ("top3 为 100", abs(r["top3_weight_pct"] - 100) < 0.05),
    ]

    series = {
        "A": [10, 10.2, 10.1, 10.4, 10.5, 10.7],
        "B": [20, 20.4, 20.2, 20.8, 21.0, 21.4],
        "C": [30, 29.5, 29.8, 29.1, 28.9, 28.4],
    }
    m = correlation_matrix(series)
    checks.append(("相关性可算", len(m["pairs"]) == 3))
    checks.append(("A/B 高度正相关", abs(m["pairs"][0]["corr"]) > 0.9))

    ev = [
        {"date": "2026-10-30", "code": "600519.SH", "name": "贵州茅台", "event": "三季报", "impact": "高"},
        {"date": "2026-10-31", "code": "000858.SZ", "name": "五粮液", "event": "三季报", "impact": "高"},
        {"date": "2026-11-02", "code": "300750.SZ", "name": "宁德时代", "event": "解禁", "impact": "中"},
        {"date": "2027-03-01", "code": "600519.SH", "name": "贵州茅台", "event": "年报", "impact": "高"},
    ]
    t = event_timeline(ev)
    checks.append(("事件排序", t["timeline"][0]["date"] == "2026-10-30"))
    checks.append(("撞车识别", len(t["clusters"]) == 1 and t["clusters"][0]["count"] == 3))

    failed = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print(("  PASS  " if ok else "  FAIL  ") + n)
    print("结果：%d/%d 通过" % (len(checks) - len(failed), len(checks)))
    return 0 if not failed else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="持仓体检计算")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("check", "events", "corr"):
        p = sub.add_parser(name)
        p.add_argument("--file", required=True)
    sub.add_parser("selftest")
    args = ap.parse_args(argv)

    if args.cmd == "selftest":
        return selftest()
    try:
        if args.cmd == "check":
            out = concentration(load(args.file))
        elif args.cmd == "events":
            out = event_timeline(load(args.file))
        else:
            out = correlation_matrix(load(args.file))
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
