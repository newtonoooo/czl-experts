"""输入规范化与校验。

真实使用中最常见的三个错，全部在这里拦下来：
1. 单位混用：ROE 给 0.241 还是 24.1（本模块统一成百分数，并记录归一化动作）；
2. 口径不清：没写复权方式 / 没写报告期 / 把静态 PE 当 TTM；
3. 结构缺失：估值、财务、技术任何一块整体缺失时，后续不该硬算分。
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List, Optional, Tuple

from . import indicators

# 字段 -> 类型。pct 表示百分数，ratio 表示倍数/比值，money 表示金额（元），num 普通数值。
FIELD_TYPES: Dict[str, Dict[str, str]] = {
    "valuation": {
        "pe_ttm": "ratio",
        "pe_static": "ratio",
        "pb": "ratio",
        "ps_ttm": "ratio",
        "peg": "ratio",
        "ev_ebitda": "ratio",
        "dividend_yield": "pct",
        "pe_percentile_5y": "pct",
        "pb_percentile_5y": "pct",
        "industry_pe_median": "ratio",
        "industry_pb_median": "ratio",
    },
    "profitability": {
        "roe_ttm": "pct",
        "roe_3y_avg": "pct",
        "gross_margin": "pct",
        "net_margin": "pct",
        "roic": "pct",
        "asset_turnover": "ratio",
    },
    "growth": {
        "rev_yoy": "pct",
        "np_yoy": "pct",
        "rev_cagr_3y": "pct",
        "np_cagr_3y": "pct",
        "q_rev_yoy": "pct",
        "q_np_yoy": "pct",
    },
    "health": {
        "debt_ratio": "pct",
        "current_ratio": "ratio",
        "quick_ratio": "ratio",
        "interest_coverage": "ratio",
        "ocf_to_np": "ratio",
        "goodwill_to_equity": "pct",
        "fcf_positive_years": "num",
        "receivable_days": "num",
        "inventory_days": "num",
    },
    "capital": {
        "main_net_inflow_5d": "money",
        "main_net_inflow_20d": "money",
        "main_net_inflow_20d_pct": "pct",
        "north_hold_change_20d": "pct",
        "margin_balance_change_20d": "pct",
        "holder_count_change": "pct",
        "institution_hold_change": "pct",
    },
    "governance": {
        "pledge_ratio": "pct",
        "insider_net_change_90d": "pct",
        "top1_holder_ratio": "pct",
        "audit_opinion": "str",
        "restructuring": "bool",
    },
}

# 百分数字段里，只有这些字段的“小数写法”是行业惯例、且按百分数读会明显不合理，
# 才允许自动 ×100。其余字段（增速、资金占比等）0.9 可能本来就是 0.9%，
# 一律不动，只提示人工确认——宁可让模型去问，也不要在数据层偷偷改数。
_AUTO_DECIMAL_FIELDS = {
    "roe_ttm", "roe_3y_avg", "gross_margin", "net_margin",
    "debt_ratio", "goodwill_to_equity", "pledge_ratio", "top1_holder_ratio",
}
_AMBIGUOUS_HINT = 1.5

# 覆盖率的统计口径：只统计评分真正会用到的“主字段”，
# 可选字段（如 EV/EBITDA、应收天数）缺失不算数据不全。
PRIMARY_FIELDS: Dict[str, tuple] = {
    "valuation": ("pe_ttm", "pb", "peg", "pe_percentile_5y", "industry_pe_median", "dividend_yield"),
    "profitability": ("roe_ttm", "gross_margin", "net_margin", "roic", "asset_turnover"),
    "growth": ("rev_yoy", "np_yoy", "rev_cagr_3y", "np_cagr_3y", "q_np_yoy"),
    "health": ("debt_ratio", "current_ratio", "ocf_to_np", "interest_coverage",
                "goodwill_to_equity", "fcf_positive_years"),
    "capital": ("main_net_inflow_20d", "main_net_inflow_20d_pct", "north_hold_change_20d",
                 "margin_balance_change_20d", "holder_count_change"),
    "governance": ("pledge_ratio", "audit_opinion"),
    "technical": ("close", "ma20", "ma60", "macd_dif", "macd_dea", "rsi14", "atr14", "vol_ratio5_20"),
}

_TECH_KEYS = (
    "close", "ma5", "ma10", "ma20", "ma60", "ma120", "ma250",
    "macd_dif", "macd_dea", "macd_hist", "rsi14", "kdj_k", "kdj_d", "kdj_j",
    "boll_upper", "boll_mid", "boll_lower", "bias20",
    "atr14", "atr_pct", "vol_ratio5_20", "turnover",
    "pct_from_high_250", "position_250", "swing_high_20", "swing_low_20",
)


def _num(v: Any):
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        f = float(v)
    elif isinstance(v, str):
        s = v.strip().replace(",", "").replace("%", "")
        try:
            f = float(s)
        except ValueError:
            return None
    else:
        return None
    if f != f or f in (float("inf"), float("-inf")):
        return None
    return f


def _norm_pct(field: str, value: Any, notes: List[str], force_decimal: bool = False,
              warns: Optional[List[str]] = None) -> Any:
    f = _num(value)
    if f is None:
        return None
    if force_decimal:
        notes.append(f"{field} 按 meta.units 声明的小数口径折算：{f} -> {round(f * 100, 4)}")
        return round(f * 100, 4)
    if f != 0 and abs(f) <= _AMBIGUOUS_HINT:
        if field in _AUTO_DECIMAL_FIELDS:
            notes.append(f"{field} 以小数形式输入（{f}），已按百分数折算为 {round(f * 100, 4)}")
            return round(f * 100, 4)
        if warns is not None:
            warns.append(
                f"{field} 的取值 {f} 小于 1.5，可能把百分数写成了小数；已按原值使用，请确认单位"
            )
    return f


def _norm_block(block: str, raw: Any, notes: List[str], warns: List[str],
                force_decimal: bool = False) -> Dict[str, Any]:
    spec = FIELD_TYPES.get(block, {})
    out: Dict[str, Any] = {}
    if not isinstance(raw, dict):
        if raw not in (None, {}):
            warns.append(f"{block} 字段结构异常（期望对象），已忽略")
        return out
    for key, value in raw.items():
        kind = spec.get(key)
        if kind == "pct":
            f = _norm_pct(key, value, notes, force_decimal, warns)
        elif kind in ("ratio", "money", "num"):
            f = _num(value)
        elif kind == "str":
            f = value.strip() if isinstance(value, str) and value.strip() else None
        elif kind == "bool":
            f = value if isinstance(value, bool) else None
        else:  # 未登记的扩展字段：能转数字就转，否则原样保留
            f = _num(value)
            if f is None and isinstance(value, str):
                f = value.strip() or None
            if f is None and isinstance(value, (list, dict, bool)):
                f = value
        if f is not None:
            out[key] = f
    return out


def _parse_date(s: Any):
    if not isinstance(s, str) or len(s) < 10:
        return None
    try:
        return _dt.date.fromisoformat(s[:10])
    except ValueError:
        return None


def normalize(payload: Any) -> Tuple[Dict[str, Any], Dict[str, List[str]]]:
    """把原始输入整理成引擎内部结构。

    返回 (data, report)。report 含 normalized / warnings / errors 三个列表。
    data 中的 business 子块是规范化后的财务与资金指标，technical 是合并推导后的技术指标，
    series 是原始序列（供关键价位计算使用）。
    """
    report: Dict[str, List[str]] = {"normalized": [], "warnings": [], "errors": []}
    notes, warns, errs = report["normalized"], report["warnings"], report["errors"]

    if not isinstance(payload, dict):
        errs.append("输入必须是 JSON 对象")
        return {}, report

    meta_raw = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    meta = {
        "code": str(meta_raw.get("code") or "").strip(),
        "name": str(meta_raw.get("name") or "").strip(),
        "market": str(meta_raw.get("market") or "").strip().upper(),
        "industry": str(meta_raw.get("industry") or "").strip(),
        "as_of": str(meta_raw.get("as_of") or "").strip(),
        "adjust": str(meta_raw.get("adjust") or "").strip(),
        "report_period": str(meta_raw.get("report_period") or "").strip(),
        "currency": str(meta_raw.get("currency") or "CNY").strip(),
    }
    if not meta["code"]:
        errs.append("meta.code 缺失：无法确认诊断标的")
    if not meta["as_of"]:
        warns.append("meta.as_of 缺失：数据时效性无法校验，报告将按“日期未标注”处理")
    if not meta["adjust"]:
        warns.append("meta.adjust 缺失：未声明复权方式，技术面结论的置信度按“中”封顶")

    business: Dict[str, Dict[str, Any]] = {}
    units = meta_raw.get("units") if isinstance(meta_raw.get("units"), dict) else {}
    force_decimal = str(units.get("percent_format") or "").strip().lower() in ("decimal", "ratio", "小数")
    if force_decimal:
        notes.append("meta.units.percent_format=decimal：所有百分数字段按小数口径换算")
    for block in ("valuation", "profitability", "growth", "health", "capital", "governance"):
        business[block] = _norm_block(block, payload.get(block), notes, warns, force_decimal)

    # 事件：只保留结构化字段，摘要留空也允许
    events: List[Dict[str, Any]] = []
    for ev in payload.get("events") or []:
        if not isinstance(ev, dict):
            continue
        tone = str(ev.get("tone") or ev.get("impact") or "").strip()
        events.append({
            "date": str(ev.get("date") or "").strip(),
            "type": str(ev.get("type") or "其他").strip(),
            "summary": str(ev.get("summary") or "").strip(),
            "tone": tone,
            "confidence": str(ev.get("confidence") or "中").strip(),
        })

    peers: List[Dict[str, Any]] = []
    for p in payload.get("peers") or []:
        if not isinstance(p, dict) or not str(p.get("name") or "").strip():
            continue
        peers.append({
            "name": str(p.get("name")).strip(),
            "code": str(p.get("code") or "").strip(),
            "pe_ttm": _num(p.get("pe_ttm")),
            "pb": _num(p.get("pb")),
            "roe_ttm": _norm_pct("roe_ttm", p.get("roe_ttm"), notes),
            "np_yoy": _norm_pct("np_yoy", p.get("np_yoy"), notes),
            "rev_yoy": _norm_pct("rev_yoy", p.get("rev_yoy"), notes),
        })

    series_raw = payload.get("series") if isinstance(payload.get("series"), dict) else {}
    series = {
        "closes": series_raw.get("closes") or [],
        "highs": series_raw.get("highs") or [],
        "lows": series_raw.get("lows") or [],
        "volumes": series_raw.get("volumes") or [],
    }
    tech_provided = payload.get("technical") if isinstance(payload.get("technical"), dict) else {}
    technical = indicators.merge_technical(tech_provided, series)
    unknown_tech = [k for k in tech_provided if k not in _TECH_KEYS and k not in series]
    if unknown_tech:
        warns.append("technical 中存在未识别字段，已忽略：" + "、".join(sorted(unknown_tech)[:6]))

    if not technical.get("close"):
        last = [c for c in series.get("closes") or [] if isinstance(c, (int, float))]
        if last:
            technical["close"] = round(float(last[-1]), 4)
        else:
            warns.append("缺少收盘价与 K 线序列：技术面维度无法评分")

    data = {
        "meta": meta,
        "business": business,
        "technical": technical,
        "events": events,
        "peers": peers,
        "series": series,
        "notes": payload.get("notes") if isinstance(payload.get("notes"), str) else "",
    }
    return data, report


def freshness(data: Dict[str, Any]) -> Dict[str, Any]:
    """判断财务数据的“年龄”，用于给基本面结论定置信度。"""
    meta = data.get("meta") or {}
    as_of, period = _parse_date(meta.get("as_of")), _parse_date(meta.get("report_period"))
    if not as_of or not period:
        return {"status": "unknown", "days": None, "hint": "缺少 as_of 或 report_period"}
    days = (as_of - period).days
    if days < 0:
        return {"status": "invalid", "days": days, "hint": "报告期晚于数据日期，疑似填写错误"}
    if days <= 150:
        status, hint = "fresh", "报告期为最近一期"
    elif days <= 300:
        status, hint = "acceptable", "距报告期超过一个季度，需确认是否有更新报告"
    else:
        status, hint = "stale", "距报告期超过 300 天，基本面结论应降级"
    return {"status": status, "days": days, "hint": hint}
