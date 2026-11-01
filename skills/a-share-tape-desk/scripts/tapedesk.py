#!/usr/bin/env python3
"""盘锋 · A股盘中交易参谋 命令行入口。

用法示例：
    python tapedesk.py session
    python tapedesk.py quote 600519 300750
    python tapedesk.py tech 600519 --days 250
    python tapedesk.py pulse
    python tapedesk.py sectors --kind both --top 8
    python tapedesk.py plan 600519 --capital 200000 --risk-pct 1
    python tapedesk.py watch add 600519 --type price_above --threshold 1400 --note 突破前高
    python tapedesk.py watch check

任何命令加 --json 输出结构化数据，便于二次加工。
"""

import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from atd import clock, codes, history, indicators, market, net, quotes, risk, sectors, watch  # noqa: E402

DISCLAIMER = "以上为公开数据与规则化计算的结果，不构成投资建议；据此操作风险自担。"


def _out(text):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    print(text)


def _fmt_money(yuan):
    if yuan is None:
        return "—"
    return "%.2f 亿" % (yuan / 1e8) if yuan >= 1e8 else "%.0f 万" % (yuan / 1e4)


def _fmt_pct(v, digits=2):
    return "—" if v is None else ("%+.*f%%" % (digits, v))


def _arrow(pct):
    if pct is None:
        return ""
    if pct > 0:
        return "↑"
    if pct < 0:
        return "↓"
    return "→"


def _n(value, digits=2):
    """数值为空时输出破折号，避免报告里出现 None。"""
    if value is None:
        return "—"
    if isinstance(value, float):
        return ("%." + str(digits) + "f") % value
    return str(value)


# ---------------------------------------------------------------- session
def cmd_session(args):
    block = clock.session_block()
    if args.json:
        return _out(json.dumps(block, ensure_ascii=False, indent=2))
    lines = [
        "## 交易时段",
        "",
        "- 当前时间：%s（%s）" % (block["timestamp"], block["weekday"]),
        "- 阶段：%s%s" % (block["phase"], "（连续竞价中）" if block["is_open"] else "（非连续竞价）"),
        "- 已走完交易分钟：%d / 240（%.0f%%）" % (block["elapsed_minutes"], block["progress"] * 100),
        "- 说明：%s" % block["note"],
    ]
    _out("\n".join(lines))


# ---------------------------------------------------------------- quote
def cmd_quote(args):
    recs, meta = quotes.snapshot(args.codes, ttl=0 if args.no_cache else 20)
    if args.json:
        return _out(json.dumps({"records": recs, "meta": meta}, ensure_ascii=False, indent=2))

    if not recs:
        detail = "；".join(meta.get("errors") or []) or "无有效返回"
        _out("取不到行情。原因：%s" % detail)
        if meta.get("rejected"):
            for r in meta["rejected"]:
                _out("  · %s" % r["reason"])
        # 全部被拒或全部失败，用非零退出码让调用方能感知
        sys.exit(2)

    lines = ["## 实时行情", ""]
    lines.append("| 名称 | 代码 | 最新 | 涨跌幅 | 今开 | 最高 | 最低 | 成交额 | 换手 | 量比 |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for r in recs:
        lines.append(
            "| %s | %s | %.2f | %s | %.2f | %.2f | %.2f | %s | %s | %s |"
            % (
                r["name"],
                r["code"],
                r["price"],
                _fmt_pct(r["pct"]),
                r["open"] or 0,
                r["high"] or 0,
                r["low"] or 0,
                _fmt_money(r["amount"]),
                "—" if r["turnover"] is None else "%.2f%%" % r["turnover"],
                "—" if r["vol_ratio"] is None else "%.2f" % r["vol_ratio"],
            )
        )

    lines.append("")
    for r in recs:
        bits = [
            "%s（%s·%s）" % (r["name"], r["code"], r["board"]),
            "涨停 %.2f / 跌停 %.2f（限制 ±%d%%）" % (r["limit_up"], r["limit_down"], int(r["limit_ratio"] * 100)),
            "距涨停 %s，距跌停 %s" % (_fmt_pct(r["to_limit_up_pct"]), _fmt_pct(r["to_limit_down_pct"])),
        ]
        if r["day_position"] is not None:
            bits.append("日内位置 %.0f%%（0=最低 100=最高）" % (r["day_position"] * 100))
        if r["gap_pct"] is not None:
            bits.append("开盘跳空 %s" % _fmt_pct(r["gap_pct"]))
        if r["is_limit_up"]:
            bits.append("**已封涨停%s**" % ("（一字板）" if r["is_one_word"] else ""))
        if r["is_limit_down"]:
            bits.append("**已封跌停**")
        if r["pe_ttm"] is not None:
            bits.append("PE(TTM) %s / PB %s" % (r["pe_ttm"], r["pb"]))
        lines.append("- " + "；".join(bits))
        if r["flags"]:
            lines.append("  - 数据提示：%s" % "；".join(r["flags"]))

    block = clock.session_block()
    srcs = "、".join(sorted(set(s["name"] for s in meta.get("sources", [])))) or "—"
    lines.append("")
    lines.append(
        "数据：%s｜获取 %s｜市场状态 %s"
        % (srcs, dt.datetime.fromtimestamp(meta["fetched_at"]).strftime("%Y-%m-%d %H:%M:%S"), block["phase"])
    )
    lines.append(DISCLAIMER)
    _out("\n".join(lines))


# ---------------------------------------------------------------- tech
def cmd_tech(args):
    bars, hmeta = history.load(args.code, days=args.days, ttl=0 if args.no_cache else 300)
    if not bars:
        _out("取不到K线。原因：%s" % ("；".join(hmeta.get("errors") or ["未知"])))
        sys.exit(2)
    ind = indicators.analyze(bars)
    trend = indicators.trend_score(ind)
    info = hmeta["info"]

    if args.json:
        payload = {"code": info["code"], "bars": bars, "indicators": ind, "trend": trend, "meta": hmeta}
        return _out(json.dumps(payload, ensure_ascii=False, indent=2, default=str))

    if not ind.get("ok"):
        _out("K线不足：%s" % ind.get("reason"))
        return

    lines = [
        "## %s（%s）技术面" % (args.code, ind["last_date"]),
        "",
        "- 收盘：%.2f（当日 %s）｜区间样本 %d 根K线，%s数据"
        % (ind["price"], _fmt_pct(ind["pct_last"]), ind["bars"], hmeta["source"]),
        "- 均线：MA5 %s / MA10 %s / MA20 %s / MA60 %s / MA120 %s｜排列：%s"
        % (
            _n(ind["ma"]["5"]),
            _n(ind["ma"]["10"]),
            _n(ind["ma"]["20"]),
            _n(ind["ma"]["60"]),
            _n(ind["ma"]["120"]),
            ind["ma_alignment"],
        ),
        "- 偏离：距MA20 %s，距MA60 %s" % (_fmt_pct(ind["dev_ma20_pct"]), _fmt_pct(ind["dev_ma60_pct"])),
        "- MACD：DIF %.3f / DEA %.3f / 柱 %.3f（零轴%s）"
        % (ind["macd"]["dif"] or 0, ind["macd"]["dea"] or 0, ind["macd"]["hist"] or 0, ind["macd"]["zero_axis"]),
        "- KDJ：K %.2f / D %.2f / J %.2f" % (ind["kdj"]["k"] or 0, ind["kdj"]["d"] or 0, ind["kdj"]["j"] or 0),
        "- RSI：6日 %s / 14日 %s" % (ind["rsi"]["rsi6"], ind["rsi"]["rsi14"]),
        "- BOLL：上轨 %s / 中轨 %s / 下轨 %s" % (ind["boll"]["up"], ind["boll"]["mid"], ind["boll"]["dn"]),
        "- ATR14：%.3f 元（占股价 %s）｜量比(5日) %s｜量价：%s"
        % (ind["atr14"] or 0, _fmt_pct(ind["atr_pct"]), ind["vol_ratio_5"], ind["vol_price"]),
        "",
        "**支撑压力（分形高低点+区间高低）**",
        "",
        "- 上方压力：%s" % ("、".join("%.2f" % x for x in ind["levels"]["pivot_resistance"]) or "近期无有效压力，处于新高区"),
        "- 下方支撑：%s" % ("、".join("%.2f" % x for x in ind["levels"]["pivot_support"]) or "近期无有效支撑，处于新低区"),
        "- 20日区间：%s ~ %s｜60日区间：%s ~ %s"
        % (
            _n(ind["levels"]["range_low_20"]),
            _n(ind["levels"]["range_high_20"]),
            _n(ind["levels"]["range_low_60"]),
            _n(ind["levels"]["range_high_60"]),
        ),
        "",
        "**信号**",
        "",
    ]
    for sig in ind["signals"] or ["无明确交叉信号"]:
        lines.append("- %s" % sig)
    lines.append("")
    lines.append(
        "**趋势评分**：%d / 100（%s）｜分项：%s"
        % (trend["score"], trend["label"], "，".join("%s %+d" % (k, v) for k, v in trend["parts"].items()))
    )
    lines.append("")
    lines.append(DISCLAIMER)
    _out("\n".join(lines))


# ---------------------------------------------------------------- pulse
def cmd_pulse(args):
    data = market.pulse(ttl=0 if args.no_cache else 25)
    if args.json:
        return _out(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    if not data.get("ok"):
        _out("大盘扫描失败：%s" % data.get("reason"))
        meta = data.get("meta") or {}
        for err in meta.get("errors") or []:
            _out("  · %s" % err)
        return

    b, s, age = data["breadth"], data["sentiment"], data["data_age"]
    lines = [
        "## 大盘情绪体检",
        "",
        "- 时间：%s（%s）｜阶段：%s｜数据性质：%s"
        % (data["session"]["timestamp"], data["session"]["weekday"], data["session"]["phase"], age["label"]),
        "",
        "**情绪温度 %s / 100（%s）｜风险等级 %s｜建议仓位上限 %d%%**"
        % (s["score"], s["temperature"], s["risk_level"], s["suggested_max_position"]),
        "",
        "| 指标 | 数值 |",
        "|---|---|",
        "| 上涨 / 下跌 / 平盘 | %d / %d / %d |" % (b["up"], b["down"], b["flat"]),
        "| 涨停 / 跌停 | %d / %d |" % (b["limit_up"], b["limit_down"]),
        "| 涨超5%% / 跌超5%% | %d / %d |" % (b["up5"], b["down5"]),
        "| 涨跌幅中位数 | %s |" % _fmt_pct(s["metrics"]["median_pct"]),
        "| 两市成交额 | %.0f 亿%s |"
        % (b["amount_yi"], "" if not b["amount_prev_avg_yi"] else "（近5日均 %.0f 亿）" % b["amount_prev_avg_yi"]),
        "| 有效样本（含停牌） | %d（停牌 %d） |" % (b["active"], b["suspended"]),
        "",
    ]
    if data["indices"]:
        lines.append("| 指数 | 点位 | 涨跌幅 |")
        lines.append("|---|---|---|")
        for idx in data["indices"]:
            lines.append("| %s | %.2f | %s |" % (idx["name"], idx["price"] or 0, _fmt_pct(idx["pct"])))
        lines.append("")

    lines.append("**评分构成**")
    lines.append("")
    for name, part in s["parts"].items():
        lines.append(
            "- %s（权重%d）：%.1f/%d 分 — %s" % (name, part["weight"], part["score"], part["weight"], part["detail"])
        )
    lines.append("")

    if data["distribution"]:
        lines.append("**涨跌分布**")
        lines.append("")
        for row in data["distribution"]:
            bar = "█" * max(1, int(row["count"] / max(1, max(x["count"] for x in data["distribution"])) * 24))
            lines.append("- %-10s %4d  %s" % (row["label"], row["count"], bar))
        lines.append("")
    lines.append("**判断**：%s。%s。" % (s["risk_note"], s["position_note"]))
    lines.append("")
    lines.append(DISCLAIMER)
    _out("\n".join(lines))


# ---------------------------------------------------------------- sectors
def _render_sectors(kind_label, data):
    lines = ["### %s" % kind_label, ""]
    if not data.get("ok"):
        lines.append("抓取失败：%s" % data.get("reason"))
        return lines
    lines.append("| 板块 | 涨幅 | 家数 | 成交额 | 领涨 | 连续上涨 |")
    lines.append("|---|---|---|---|---|---|")
    for b in data["hot"]:
        streak = b.get("streak") or 0
        leader = b["leader_name"] or "—"
        if "ST" in (b["leader_name"] or "").upper():
            leader += "（ST，参考性弱）"
        lines.append(
            "| %s | %s | %d | %.1f 亿 | %s %s | %s |"
            % (
                b["name"],
                _fmt_pct(b["pct"]),
                b["count"],
                b["amount"] / 1e8,
                leader,
                _fmt_pct(b["leader_pct"]),
                ("%d 天" % (streak + 1)) if streak else "—",
            )
        )
    lines.append("")
    for b in data["hot"]:
        if b.get("leader_candidates"):
            top = b["leader_candidates"][0]
            names = "、".join("%s(%s %.2f)" % (c["name"], c["code"], c["pct"]) for c in b["leader_candidates"])
            lines.append(
                "- **%s**｜%s｜龙头候选：%s｜首选 %s（成交额 %.2f 亿，换手 %.2f%%）"
                % (b["name"], b["tag"], names, top["name"], top["amount_yi"], top["turnover"])
            )
    lines.append("")
    if data.get("cold"):
        lines.append("弱势板块：" + "、".join("%s %s" % (c["name"], _fmt_pct(c["pct"])) for c in data["cold"][:5]))
        lines.append("")
    stat = data["stat"]
    lines.append(
        "统计：%d 个板块，上涨 %d / 下跌 %d；板块历史样本 %d 个交易日（不足 2 日时不判断持续性）"
        % (stat["boards"], stat["up_boards"], stat["down_boards"], stat["history_days"])
    )
    return lines


def cmd_sectors(args):
    kinds = ["industry", "concept"] if args.kind == "both" else [args.kind]
    payload = {}
    for kind in kinds:
        payload[kind] = sectors.rank(
            kind=kind, top=args.top, with_leaders=not args.no_leaders, ttl=0 if args.no_cache else 60
        )
    if args.json:
        return _out(json.dumps(payload, ensure_ascii=False, indent=2, default=str))

    lines = ["## 板块与龙头"]
    lines.append("")
    for kind in kinds:
        lines.extend(_render_sectors("行业板块" if kind == "industry" else "概念板块", payload[kind]))
        lines.append("")
    lines.append("判断口径：涨幅≥1.5%且家数≥12 记为强势；涨幅≥2.5%但家数不足 12 记为情绪板块（持续性差）；")
    lines.append("龙头综合涨幅、成交额、换手评分，成交额低于 5000 万的个股不参与评选。")
    lines.append("")
    lines.append(DISCLAIMER)
    _out("\n".join(lines))


# ---------------------------------------------------------------- plan
def cmd_plan(args):
    recs, meta = quotes.snapshot([args.code], ttl=0 if args.no_cache else 20)
    if not recs:
        _out("取不到行情：%s" % ("；".join(meta.get("errors") or ["未知"])))
        sys.exit(2)
    q = recs[0]
    bars, _ = history.load(args.code, days=120, ttl=300)
    ind = indicators.analyze(bars) if bars else {"ok": False}

    entry = args.entry if args.entry else q["price"]
    atr = ind.get("atr14") if ind.get("ok") else None
    stop = args.stop if args.stop else None
    max_pos = args.max_position
    if max_pos is None:
        max_pos = 30.0
        pos_note = "仓位上限取默认 30%（未传入大盘情绪结论）"
    else:
        pos_note = "仓位上限取用户指定的 %.0f%%" % max_pos

    result = risk.plan(
        entry=entry,
        stop=stop,
        capital=args.capital,
        risk_pct=args.risk_pct,
        max_position_pct=max_pos,
        atr=atr,
        atr_mult=args.atr_mult,
        prev_close=q["prev_close"],
        limit_up=q["limit_up"],
        is_limit_up=q["is_limit_up"],
        name=q["name"],
    )
    trend = indicators.trend_score(ind) if ind.get("ok") else {"score": 0, "label": "数据不足", "parts": {}}

    if args.json:
        return _out(
            json.dumps(
                {"quote": q, "plan": result, "trend": trend, "indicators": ind, "max_position_note": pos_note},
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )

    lines = [
        "## 交易计划：%s（%s）" % (q["name"], q["code"]),
        "",
        "- 现价 %.2f（%s）｜涨停 %.2f / 跌停 %.2f｜ATR14 %s（%s）"
        % (
            q["price"],
            _fmt_pct(q["pct"]),
            q["limit_up"],
            q["limit_down"],
            ind.get("atr14") if ind.get("ok") else "—",
            _fmt_pct(ind.get("atr_pct")) if ind.get("ok") else "—",
        ),
        "- 技术面：%s（趋势分 %d）｜%s" % (trend["label"], trend["score"], ind.get("ma_alignment", "—") if ind.get("ok") else "—"),
        "",
        "| 项目 | 数值 |",
        "|---|---|",
        "| 入场参考 | %.2f |" % result["entry"],
        "| 止损 | %.2f（-%s%%） |" % (result["stop"], result["stop_pct"]),
        "| 止损依据 | %s |" % result["stop_source"],
        "| 每股风险 | %.2f 元 |" % result["per_share_risk"],
        "| 单笔风险预算 | %.0f 元 |" % result["risk_budget"],
        "| 可买股数 | %d 股 |" % result["shares"],
        "| 占用资金 | %.0f 元（%.1f%% 仓位） |" % (result["position_value"], result["position_pct"]),
        "| 触发止损实亏 | %.0f 元（%.2f%%） |" % (result["actual_risk"], result["actual_risk_pct"]),
        "",
        "**分批止盈**",
        "",
    ]
    for t in result["targets"]:
        lines.append("- %.1fR → %.2f 元（%s）%s" % (t["r"], t["price"], _fmt_pct(t["gain_pct"]), "；" + t["note"] if t["note"] else ""))
    lines.append("")
    lines.append("**检查项**")
    lines.append("")
    for c in result["checks"]:
        lines.append("- %s %s：%s" % ("✅" if c["pass"] else "❌", c["item"], c["detail"]))
    if result["shares"] == 0 and result["min_viable"].get("suggestion"):
        lines.append("")
        lines.append("**最小可行规模**：%s" % result["min_viable"]["suggestion"])
    if result["warnings"]:
        lines.append("")
        lines.append("**风险提示**")
        lines.append("")
        for w in result["warnings"]:
            lines.append("- ⚠️ %s" % w)
    lines.append("")
    lines.append("假设：总资金 %.0f 元，单笔风险 %.1f%%，仓位上限 %s，%s。" % (args.capital, args.risk_pct, pos_note, result["assumptions"]["fee_note"]))
    lines.append("")
    lines.append(DISCLAIMER)
    _out("\n".join(lines))


# ---------------------------------------------------------------- watch
def cmd_watch(args):
    if args.action == "add":
        item, path = watch.add(args.code, args.type, args.threshold, args.note)
        if args.json:
            return _out(json.dumps({"item": item, "path": path}, ensure_ascii=False, indent=2))
        _out(
            "- 已加入预警：%s（%s）%s 阈值 %s，备注「%s」\n- 清单文件：%s"
            % (item["name"], item["code"], item["type_label"], item["threshold"], item["note"] or "无", path)
        )
        return

    if args.action == "list":
        items, path = watch.listing(include_closed=args.all)
        if args.json:
            return _out(json.dumps({"items": items, "path": path}, ensure_ascii=False, indent=2))
        if not items:
            _out("预警清单为空：%s" % path)
            return
        lines = ["## 预警清单（%s）" % path, "", "| ID | 标的 | 条件 | 阈值 | 备注 | 状态 |", "|---|---|---|---|---|---|"]
        for i in items:
            lines.append(
                "| %s | %s(%s) | %s | %s | %s | %s |"
                % (i["id"], i["name"], i["code"], i["type_label"], i["threshold"], i["note"] or "—", i["status"])
            )
        _out("\n".join(lines))
        return

    if args.action == "check":
        res = watch.check()
        if args.json:
            return _out(json.dumps(res, ensure_ascii=False, indent=2))
        if res["checked"] == 0:
            _out("清单里没有待检查的条件（%s）" % res["path"])
            return
        lines = ["## 预警检查（%s，共 %d 条）" % (res["checked_at"], res["checked"]), ""]
        if res["triggered"]:
            lines.append("**已触发**")
            lines.append("")
            for t in res["triggered"]:
                lines.append("- 🔔 %s（%s）%s — %s%s" % (t["name"], t["code"], t["type_label"], t["detail"], "｜" + t["note"] if t["note"] else ""))
        else:
            lines.append("已触发：无")
        lines.append("")
        if res["pending"]:
            lines.append("**未触发**")
            lines.append("")
            for t in res["pending"]:
                lines.append("- %s（%s）%s — %s" % (t["name"], t["code"], t["type_label"], t["detail"]))
        if res["missing"]:
            lines.append("")
            lines.append("**取不到行情**：" + "、".join("%s(%s)" % (m["name"], m["code"]) for m in res["missing"]))
        _out("\n".join(lines))
        return

    if args.action == "rm":
        n = watch.remove(args.id)
        _out("删除 %d 条（ID %s）" % (n, args.id))


# ---------------------------------------------------------------- doctor
def cmd_doctor(args):
    checks = []

    probe = [
        ("腾讯行情", "http://qt.gtimg.cn/q=sh600519", "https://gu.qq.com", "gbk"),
        ("新浪行情", "http://hq.sinajs.cn/list=sh600519", "https://finance.sina.com.cn", "gbk"),
        ("新浪全市场", market.SINA_COUNT, "https://finance.sina.com.cn", "utf-8"),
        ("新浪行业板块", sectors.HY_URL, "https://finance.sina.com.cn", "gbk"),
        ("腾讯日线", history.TENCENT_KLINE % ("sh600519", 60), "https://gu.qq.com", "utf-8"),
    ]
    for name, url, referer, enc in probe:
        try:
            text, ts, cached = net.fetch(url, referer=referer, encoding=enc, ttl=0, retries=0, timeout=8)
            checks.append({"name": name, "ok": True, "bytes": len(text), "cached": cached, "error": None})
        except RuntimeError as exc:
            checks.append({"name": name, "ok": False, "bytes": 0, "cached": False, "error": str(exc)})

    try:
        recs, _ = quotes.snapshot(["600519"])
        parse_ok = bool(recs)
        parse_err = None if parse_ok else "解析失败"
    except Exception as exc:  # 解析路径异常要暴露出来
        parse_ok, parse_err = False, str(exc)
    checks.append({"name": "代码解析与快照", "ok": parse_ok, "bytes": 0, "cached": False, "error": parse_err})

    try:
        bars, _ = history.load("600519", days=80, ttl=0)
        ind = indicators.analyze(bars) if bars else {"ok": False}
        ind_ok = bool(ind.get("ok"))
    except Exception as exc:
        ind_ok, ind = False, {"ok": False}
        checks.append({"name": "指标计算", "ok": False, "bytes": 0, "cached": False, "error": str(exc)})
    if ind_ok:
        checks.append({"name": "指标计算", "ok": True, "bytes": 0, "cached": False, "error": None})

    passed = len([c for c in checks if c["ok"]])
    if args.json:
        return _out(json.dumps({"checks": checks, "health": net.health_report(), "passed": passed, "total": len(checks)}, ensure_ascii=False, indent=2))
    lines = ["## 数据链路自检", "", "| 检查项 | 结果 | 详情 |", "|---|---|---|"]
    for c in checks:
        lines.append("| %s | %s | %s |" % (c["name"], "✅" if c["ok"] else "❌", c["error"] or ("%d 字节" % c["bytes"] if c["bytes"] else "ok")))
    lines.append("")
    lines.append("通过 %d / %d 项。" % (passed, len(checks)))
    if passed < len(checks):
        lines.append("")
        lines.append("失败项说明：公开行情接口有频率限制，连续高频请求会临时断流。建议稍等 1-2 分钟重试，或改用 --no-cache 之外的其他命令错峰调用。")
    _out("\n".join(lines))


# ---------------------------------------------------------------- main
def build_parser():
    p = argparse.ArgumentParser(prog="tapedesk", description="盘锋 · A股盘中交易参谋 数据引擎")
    p.add_argument("--json", action="store_true", help="输出 JSON（也可写在子命令后面）")
    # 允许 --json 写在子命令后面：用 SUPPRESS 避免覆盖前面的全局开关
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="输出 JSON")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("session", help="当前交易时段", parents=[common])
    s.add_argument("--no-cache", action="store_true")
    s.set_defaults(func=cmd_session)

    q = sub.add_parser("quote", help="实时快照", parents=[common])
    q.add_argument("codes", nargs="+")
    q.add_argument("--no-cache", action="store_true")
    q.set_defaults(func=cmd_quote)

    t = sub.add_parser("tech", help="技术面体检", parents=[common])
    t.add_argument("code")
    t.add_argument("--days", type=int, default=250)
    t.add_argument("--no-cache", action="store_true")
    t.set_defaults(func=cmd_tech)

    pl = sub.add_parser("pulse", help="大盘情绪体检", parents=[common])
    pl.add_argument("--no-cache", action="store_true")
    pl.set_defaults(func=cmd_pulse)

    se = sub.add_parser("sectors", help="板块与龙头", parents=[common])
    se.add_argument("--kind", choices=["industry", "concept", "both"], default="both")
    se.add_argument("--top", type=int, default=8)
    se.add_argument("--no-leaders", action="store_true")
    se.add_argument("--no-cache", action="store_true")
    se.set_defaults(func=cmd_sectors)

    pn = sub.add_parser("plan", help="交易计划与仓位", parents=[common])
    pn.add_argument("code")
    pn.add_argument("--entry", type=float, default=None)
    pn.add_argument("--stop", type=float, default=None)
    pn.add_argument("--capital", type=float, default=100000.0)
    pn.add_argument("--risk-pct", type=float, default=1.0, dest="risk_pct")
    pn.add_argument("--max-position", type=float, default=None, dest="max_position")
    pn.add_argument("--atr-mult", type=float, default=2.0, dest="atr_mult")
    pn.add_argument("--no-cache", action="store_true")
    pn.set_defaults(func=cmd_plan)

    w = sub.add_parser("watch", help="预警清单", parents=[common])
    w.add_argument("action", choices=["add", "list", "check", "rm"])
    w.add_argument("code", nargs="?", default=None)
    w.add_argument("--type", default="price_above", dest="type")
    w.add_argument("--threshold", type=float, default=None)
    w.add_argument("--note", default="")
    w.add_argument("--id", default=None)
    w.add_argument("--all", action="store_true")
    w.set_defaults(func=cmd_watch)

    d = sub.add_parser("doctor", help="数据链路自检", parents=[common])
    d.add_argument("--no-cache", action="store_true")
    d.set_defaults(func=cmd_doctor)

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except codes.CodeError as exc:
        _out("代码不在服务范围：%s" % exc)
        sys.exit(2)
    except KeyboardInterrupt:
        _out("已中断")
        sys.exit(130)


if __name__ == "__main__":
    main()
