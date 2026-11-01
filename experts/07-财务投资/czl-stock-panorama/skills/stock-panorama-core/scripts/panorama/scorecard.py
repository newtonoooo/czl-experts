"""六维评分卡。

打分规则的三个约束（写死在这里，评测时可逐条对照）：
1. 每一个分项都必须给出“用了哪个数、落在哪一档”，不允许只给分数；
2. 缺数据的分项不猜值，只从分母里剔除，并降低该维度覆盖率；
3. 分档阈值是公开的常数，改动必须在 references/scoring_rules.md 同步登记。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

GRADE_BANDS: Sequence[Tuple[float, str, str]] = (
    (85, "A", "六维共振，风险点少"),
    (75, "B+", "多数维度占优，存在个别短板"),
    (65, "B", "中性偏强，需要条件才能成立"),
    (55, "C", "多空拉扯，缺乏明确优势"),
    (45, "D", "短板明显，防守优先"),
    (0, "E", "多项走弱，风险高于机会"),
)


def _step(value: Optional[float], points: Sequence[Tuple[float, float]], higher_better: bool) -> Optional[float]:
    """points 为 (阈值, 得分) 列表，按阈值单调排列。"""
    if value is None:
        return None
    seq = sorted(points, key=lambda p: p[0], reverse=higher_better)
    for bound, score in seq:
        if higher_better and value >= bound:
            return score
        if not higher_better and value <= bound:
            return score
    return seq[-1][1]


# ---------------------------------------------------------------- 分项规则

def _f_valuation(block: dict, tech: dict) -> List[dict]:
    pe, pb = block.get("pe_ttm"), block.get("pb")
    pct = block.get("pe_percentile_5y")
    ind = block.get("industry_pe_median")
    rel = round(pe / ind, 3) if pe and ind and ind > 0 else None
    return [
        {
            "key": "pe_ttm", "label": "PE(TTM)", "weight": 0.24,
            "score": _step(pe, [(60, 20), (40, 40), (25, 62), (15, 78), (0, 88)], False)
            if (pe or 0) > 0 else (0.0 if pe is not None and pe <= 0 else None),
            "evidence": f"PE(TTM)={pe}" if pe is not None else "未取到 PE(TTM)",
            "caveat": "亏损股 PE 无经济含义" if pe is not None and pe <= 0 else "",
        },
        {
            "key": "pe_percentile_5y", "label": "PE 五年分位", "weight": 0.22,
            "score": _step(pct, [(90, 15), (75, 35), (55, 55), (35, 72), (0, 88)], False),
            "evidence": f"位于近五年 {pct}% 分位" if pct is not None else "未取到历史分位",
            "caveat": "",
        },
        {
            "key": "pb", "label": "PB", "weight": 0.18,
            "score": _step(pb, [(10, 20), (6, 35), (4, 55), (2, 75), (0, 88)], False)
            if (pb or 0) > 0 else None,
            "evidence": f"PB={pb}" if pb is not None else "未取到 PB",
            "caveat": "",
        },
        {
            "key": "peg", "label": "PEG", "weight": 0.16,
            "score": _step(block.get("peg"), [(2.5, 25), (2, 40), (1.5, 58), (1, 75), (0, 88)], False)
            if (block.get("peg") or 0) > 0 else None,
            "evidence": f"PEG={block.get('peg')}" if block.get("peg") is not None else "未取到 PEG",
            "caveat": "",
        },
        {
            "key": "pe_rel_industry", "label": "PE 相对行业中位", "weight": 0.12,
            "score": _step(rel, [(2.0, 25), (1.5, 40), (1.2, 55), (1.0, 70), (0, 85)], False),
            "evidence": f"为行业中位的 {rel} 倍" if rel is not None else "缺行业中位 PE",
            "caveat": "",
        },
        {
            "key": "dividend_yield", "label": "股息率", "weight": 0.08,
            "score": _step(block.get("dividend_yield"), [(0.5, 40), (1.5, 55), (3, 72), (4.5, 85)], True),
            "evidence": f"股息率 {block.get('dividend_yield')}%" if block.get("dividend_yield") is not None else "未取到股息率",
            "caveat": "",
        },
    ]


def _f_profit(block: dict, tech: dict) -> List[dict]:
    return [
        {
            "key": "roe_ttm", "label": "ROE(TTM)", "weight": 0.30,
            "score": _step(block.get("roe_ttm"), [(6, 25), (10, 45), (15, 65), (20, 82), (25, 92)], True),
            "evidence": f"ROE={block.get('roe_ttm')}%" if block.get("roe_ttm") is not None else "未取到 ROE",
            "caveat": "高杠杆推高的 ROE 需结合负债率看",
        },
        {
            "key": "gross_margin", "label": "毛利率", "weight": 0.20,
            "score": _step(block.get("gross_margin"), [(15, 30), (20, 45), (30, 62), (45, 78), (60, 88)], True),
            "evidence": f"毛利率 {block.get('gross_margin')}%" if block.get("gross_margin") is not None else "未取到毛利率",
            "caveat": "",
        },
        {
            "key": "net_margin", "label": "净利率", "weight": 0.20,
            # 负净利率不走档位，直接给 8 分，避免“越小越好”的误判
            "score": 8.0 if (block.get("net_margin") is not None and block["net_margin"] < 0)
            else _step(block.get("net_margin"), [(3, 32), (5, 45), (10, 62), (18, 78), (25, 88)], True),
            "evidence": f"净利率 {block.get('net_margin')}%" if block.get("net_margin") is not None else "未取到净利率",
            "caveat": "",
        },
        {
            "key": "roic", "label": "ROIC", "weight": 0.18,
            "score": _step(block.get("roic"), [(4, 30), (6, 45), (10, 65), (15, 82)], True),
            "evidence": f"ROIC={block.get('roic')}%" if block.get("roic") is not None else "未取到 ROIC",
            "caveat": "ROIC 低于 6% 说明主业回报接近资金成本",
        },
        {
            "key": "asset_turnover", "label": "总资产周转率", "weight": 0.12,
            "score": _step(block.get("asset_turnover"), [(0.3, 35), (0.5, 50), (0.8, 68), (1.2, 82)], True),
            "evidence": f"周转率 {block.get('asset_turnover')}" if block.get("asset_turnover") is not None else "未取到周转率",
            "caveat": "",
        },
    ]


def _f_growth(block: dict, tech: dict) -> List[dict]:
    return [
        {
            "key": "np_yoy", "label": "净利同比", "weight": 0.30,
            "score": _step(block.get("np_yoy"), [(-20, 12), (-5, 30), (0, 45), (10, 62), (20, 78), (35, 90)], True),
            "evidence": f"净利同比 {block.get('np_yoy')}%" if block.get("np_yoy") is not None else "未取到净利同比",
            "caveat": "",
        },
        {
            "key": "rev_yoy", "label": "营收同比", "weight": 0.25,
            "score": _step(block.get("rev_yoy"), [(-15, 18), (0, 38), (5, 52), (10, 66), (20, 80), (30, 90)], True),
            "evidence": f"营收同比 {block.get('rev_yoy')}%" if block.get("rev_yoy") is not None else "未取到营收同比",
            "caveat": "",
        },
        {
            "key": "np_cagr_3y", "label": "净利三年复合", "weight": 0.20,
            "score": _step(block.get("np_cagr_3y"), [(-10, 15), (0, 35), (8, 55), (15, 72), (25, 88)], True),
            "evidence": f"三年复合 {block.get('np_cagr_3y')}%" if block.get("np_cagr_3y") is not None else "未取到三年复合增速",
            "caveat": "三年复合比单季更难被基数效应扭曲",
        },
        {
            "key": "rev_cagr_3y", "label": "营收三年复合", "weight": 0.15,
            "score": _step(block.get("rev_cagr_3y"), [(-5, 20), (0, 38), (8, 56), (15, 72)], True),
            "evidence": f"三年复合 {block.get('rev_cagr_3y')}%" if block.get("rev_cagr_3y") is not None else "未取到营收三年复合",
            "caveat": "",
        },
        {
            "key": "q_np_yoy", "label": "单季净利同比", "weight": 0.10,
            "score": _step(block.get("q_np_yoy"), [(-25, 12), (0, 35), (15, 58), (30, 76)], True),
            "evidence": f"单季同比 {block.get('q_np_yoy')}%" if block.get("q_np_yoy") is not None else "未取到单季同比",
            "caveat": "单季波动大，权重最低",
        },
    ]


def _f_health(block: dict, tech: dict) -> List[dict]:
    return [
        {
            "key": "debt_ratio", "label": "资产负债率", "weight": 0.24,
            "score": _step(block.get("debt_ratio"), [(75, 20), (65, 38), (55, 55), (40, 72), (0, 85)], False),
            "evidence": f"负债率 {block.get('debt_ratio')}%" if block.get("debt_ratio") is not None else "未取到负债率",
            "caveat": "地产/建筑等重资产行业需放宽标准",
        },
        {
            "key": "current_ratio", "label": "流动比率", "weight": 0.18,
            "score": _step(block.get("current_ratio"), [(0.8, 20), (1.0, 40), (1.5, 62), (2.5, 80), (3.0, 72)], True),
            "evidence": f"流动比率 {block.get('current_ratio')}" if block.get("current_ratio") is not None else "未取到流动比率",
            "caveat": "过高常意味着资金闲置",
        },
        {
            "key": "ocf_to_np", "label": "经营现金流/净利", "weight": 0.24,
            "score": _step(block.get("ocf_to_np"), [(0, 12), (0.5, 35), (0.8, 58), (1.0, 78), (1.3, 88)], True),
            "evidence": f"现金流/净利={block.get('ocf_to_np')}" if block.get("ocf_to_np") is not None else "未取到现金流利润比",
            "caveat": "长期低于 0.8 说明利润含金量不足",
        },
        {
            "key": "interest_coverage", "label": "利息保障倍数", "weight": 0.14,
            "score": _step(block.get("interest_coverage"), [(2, 25), (4, 48), (8, 70), (15, 85)], True),
            "evidence": f"{block.get('interest_coverage')} 倍" if block.get("interest_coverage") is not None else "未取到利息保障倍数",
            "caveat": "",
        },
        {
            "key": "goodwill_to_equity", "label": "商誉/净资产", "weight": 0.12,
            "score": _step(block.get("goodwill_to_equity"), [(30, 20), (20, 38), (10, 60), (0, 82)], False),
            "evidence": f"{block.get('goodwill_to_equity')}%" if block.get("goodwill_to_equity") is not None else "未取到商誉占比",
            "caveat": "高商誉对应减值风险",
        },
        {
            "key": "fcf_positive_years", "label": "近五年自由现金流转正年数", "weight": 0.08,
            "score": _step(block.get("fcf_positive_years"), [(1, 25), (2, 42), (3, 60), (4, 76), (5, 86)], True),
            "evidence": f"{block.get('fcf_positive_years')} 年" if block.get("fcf_positive_years") is not None else "未取到自由现金流年数",
            "caveat": "",
        },
    ]


def _ma_alignment(tech: dict) -> Tuple[Optional[float], str]:
    close = tech.get("close")
    ma20, ma60, ma120 = tech.get("ma20"), tech.get("ma60"), tech.get("ma120")
    if not close:
        return None, "缺收盘价"
    pairs = []
    if ma20 is not None:
        pairs.append(close > ma20)
    if ma20 is not None and ma60 is not None:
        pairs.append(ma20 > ma60)
    if ma60 is not None and ma120 is not None:
        pairs.append(ma60 > ma120)
    if not pairs:
        return None, "缺均线数据"
    ratio = sum(1 for x in pairs if x) / len(pairs)
    score = round(20 + 72 * ratio, 1)
    desc = "多头排列" if ratio == 1 else ("空头排列" if ratio == 0 else "均线交织")
    return score, f"{desc}（{sum(1 for x in pairs if x)}/{len(pairs)} 项多头）"


def _f_technical(block: dict, tech: dict) -> List[dict]:
    close = tech.get("close")
    ma_score, ma_note = _ma_alignment(tech)
    dif, dea = tech.get("macd_dif"), tech.get("macd_dea")
    if dif is None or dea is None:
        macd_score, macd_note = None, "缺 MACD"
    elif dif > dea and dif > 0:
        macd_score, macd_note = 82.0, "零轴上方金叉"
    elif dif > dea:
        macd_score, macd_note = 66.0, "零轴下方金叉"
    elif dif > 0:
        macd_score, macd_note = 52.0, "零轴上方死叉"
    else:
        macd_score, macd_note = 30.0, "零轴下方死叉"

    up, low = tech.get("boll_upper"), tech.get("boll_lower")
    boll_score = boll_note = None
    if close and up and low and up > low:
        pos = (close - low) / (up - low)
        boll_score = 70.0
        boll_note = f"布林带位置 {round(pos * 100)}%"
        if pos >= 0.95:
            boll_score, boll_note = 45.0, f"贴近上轨（{round(pos * 100)}%），短线过热"
        elif pos <= 0.05:
            boll_score, boll_note = 48.0, f"贴近下轨（{round(pos * 100)}%），弱势"
        elif 0.35 <= pos <= 0.75:
            boll_score = 76.0

    rsi_v = tech.get("rsi14")
    rsi_score = _step(rsi_v, [(30, 45), (40, 62), (50, 78), (70, 68), (80, 42), (100, 25)], True)
    if rsi_v is not None and 45 <= rsi_v <= 65:
        rsi_score = 76.0

    return [
        {"key": "ma_alignment", "label": "均线结构", "weight": 0.26, "score": ma_score,
         "evidence": f"收盘 {close}，" + ma_note, "caveat": ""},
        {"key": "macd", "label": "MACD 状态", "weight": 0.20, "score": macd_score,
         "evidence": macd_note, "caveat": "MACD 滞后，只用于确认而非预判"},
        {"key": "boll", "label": "布林带位置", "weight": 0.14, "score": boll_score,
         "evidence": boll_note or "缺布林带数据", "caveat": ""},
        {"key": "rsi14", "label": "RSI(14)", "weight": 0.12, "score": rsi_score,
         "evidence": f"RSI={round(rsi_v, 1)}" if rsi_v is not None else "缺 RSI", "caveat": ""},
        {"key": "bias20", "label": "20 日乖离", "weight": 0.10,
         "score": _step(tech.get("bias20"), [(15, 30), (10, 48), (6, 62), (2, 72), (-2, 78), (-8, 62), (-15, 40), (-100, 30)], True),
         "evidence": f"乖离 {tech.get('bias20')}%" if tech.get("bias20") is not None else "缺乖离率",
         "caveat": "短期偏离度过大时，均值回归压力上升"},
        {"key": "vol_ratio5_20", "label": "量能比（5/20 日）", "weight": 0.10,
         "score": _step(tech.get("vol_ratio5_20"), [(0.6, 50), (0.9, 62), (1.2, 76), (2.0, 70), (3.0, 48), (99, 35)], True),
         "evidence": f"量比 {tech.get('vol_ratio5_20')}" if tech.get("vol_ratio5_20") is not None else "缺成交量序列",
         "caveat": ""},
        {"key": "atr_pct", "label": "波动率（ATR/收盘）", "weight": 0.08,
         "score": _step(tech.get("atr_pct"), [(2, 78), (3.5, 66), (5, 52), (8, 38), (99, 26)], False),
         "evidence": f"ATR 占收盘 {tech.get('atr_pct')}%" if tech.get("atr_pct") is not None else "缺 ATR",
         "caveat": "波动越大，同等仓位下的实际风险越高"},
    ]


_TONE_POS = {"正面", "利好", "positive", "+"}
_TONE_NEG = {"负面", "利空", "negative", "-"}


def _f_capital(block: dict, tech: dict, events: Optional[list] = None, gov: Optional[dict] = None) -> List[dict]:
    events = events or []
    gov = gov or {}
    pct_flow = block.get("main_net_inflow_20d_pct")
    flow_score, flow_note = None, "缺主力资金数据"
    if pct_flow is not None:
        flow_score = _step(pct_flow, [(-3, 20), (-1, 38), (0, 52), (1, 70), (3, 84)], True)
        flow_note = f"20 日主力净流入占流通市值 {pct_flow}%"
    else:
        v = block.get("main_net_inflow_20d")
        if v is not None:
            flow_score = 70.0 if v > 0 else 35.0
            flow_note = f"20 日主力净流入 {round(v / 1e8, 2)} 亿元（仅按方向计分，未按市值标准化）"

    pos = sum(1 for e in events if e.get("tone") in _TONE_POS)
    neg = sum(1 for e in events if e.get("tone") in _TONE_NEG)
    if events:
        net = pos - neg
        ev_score = 62.0 + max(-32, min(24, net * 8))
        ev_note = f"已识别事件 {len(events)} 条，正面 {pos} 条、负面 {neg} 条"
    else:
        ev_score, ev_note = None, "事件清单为空"

    audit = gov.get("audit_opinion")
    audit_score = None
    audit_note = "未取到审计意见"
    if isinstance(audit, str):
        # 先认“无保留”（标准无保留意见里也含“保留意见”四个字），再认非标短语
        if "无保留" in audit:
            audit_score, audit_note = 82.0, f"审计意见：{audit}"
        elif any(bad in audit for bad in ("无法表示", "否定意见", "保留意见", "拒绝表示")):
            audit_score, audit_note = 18.0, f"审计意见：{audit}（非标）"
        else:
            audit_score, audit_note = 55.0, f"审计意见：{audit}（表述未识别，按中性计）"

    return [
        {"key": "main_flow", "label": "主力资金 20 日", "weight": 0.30, "score": flow_score,
         "evidence": flow_note, "caveat": "" if pct_flow is not None else "未标准化时置信度下调"},
        {"key": "north", "label": "北向持股变化", "weight": 0.18,
         "score": _step(block.get("north_hold_change_20d"), [(-1, 30), (-0.3, 45), (0, 58), (0.3, 72), (1.5, 82)], True),
         "evidence": f"20 日变化 {block.get('north_hold_change_20d')}%" if block.get("north_hold_change_20d") is not None else "未取到北向数据",
         "caveat": "北向披露口径曾多次调整，需确认数据来源"},
        {"key": "margin", "label": "融资余额变化", "weight": 0.14,
         "score": _step(block.get("margin_balance_change_20d"), [(-10, 38), (-2, 50), (2, 62), (10, 72), (30, 60)], True),
         "evidence": f"20 日变化 {block.get('margin_balance_change_20d')}%" if block.get("margin_balance_change_20d") is not None else "未取到融资余额",
         "caveat": "融资余额过快抬升常伴随拥挤交易"},
        {"key": "holder_count", "label": "股东户数变化", "weight": 0.10,
         "score": _step(block.get("holder_count_change"), [(15, 35), (5, 50), (0, 62), (-10, 74), (-25, 82)], False),
         "evidence": f"变化 {block.get('holder_count_change')}%" if block.get("holder_count_change") is not None else "未取到股东户数",
         "caveat": "户数下降通常意味着筹码集中"},
        {"key": "event_tone", "label": "事件情绪", "weight": 0.18, "score": ev_score,
         "evidence": ev_note, "caveat": "事件性质由录入者判定，非系统推断"},
        {"key": "audit", "label": "审计意见", "weight": 0.10, "score": audit_score,
         "evidence": audit_note, "caveat": ""},
    ]


DIMENSIONS: Sequence[dict] = (
    {"key": "valuation", "label": "估值", "weight": 0.16,
     "builder": _f_valuation, "blocks": ("valuation",)},
    {"key": "profitability", "label": "盈利质量", "weight": 0.20,
     "builder": _f_profit, "blocks": ("profitability",)},
    {"key": "growth", "label": "成长性", "weight": 0.18,
     "builder": _f_growth, "blocks": ("growth",)},
    {"key": "health", "label": "财务健康", "weight": 0.14,
     "builder": _f_health, "blocks": ("health",)},
    {"key": "technical", "label": "技术结构", "weight": 0.20,
     "builder": _f_technical, "blocks": ()},
    {"key": "capital", "label": "资金与事件", "weight": 0.12,
     "builder": _f_capital, "blocks": ("capital", "governance")},
)

MIN_DIM_COVERAGE = 0.4      # 单维度覆盖率低于此值视为该维度失效
MIN_TOTAL_COVERAGE = 0.6    # 总覆盖率低于此值不给总分评级


def grade_of(score: Optional[float]) -> Tuple[str, str]:
    if score is None:
        return "N/A", "数据不足，不予评级"
    for bound, letter, desc in GRADE_BANDS:
        if score >= bound:
            return letter, desc
    return "E", "多项走弱"


def _judge(score: Optional[float]) -> str:
    if score is None:
        return "未评级"
    if score >= 75:
        return "占优"
    if score >= 60:
        return "中性偏强"
    if score >= 45:
        return "中性"
    return "偏弱"


def evaluate(data: Dict[str, Any]) -> Dict[str, Any]:
    """核心入口：规范化后的 data -> 结构化评分结果。"""
    biz = data.get("business") or {}
    tech = data.get("technical") or {}
    events = data.get("events") or []
    gov = biz.get("governance") or {}

    dims: List[dict] = []
    for spec in DIMENSIONS:
        if spec["key"] == "capital":
            factors = spec["builder"](biz.get("capital") or {}, tech, events, gov)
        else:
            block = biz.get(spec["blocks"][0]) if spec["blocks"] else {}
            factors = spec["builder"](block or {}, tech)

        avail = [f for f in factors if isinstance(f.get("score"), (int, float))]
        total_w = sum(f["weight"] for f in factors) or 1.0
        cov = sum(f["weight"] for f in avail) / total_w
        if avail:
            dim_score = round(sum(f["score"] * f["weight"] for f in avail) / sum(f["weight"] for f in avail), 1)
        else:
            dim_score = None
        dims.append({
            "key": spec["key"],
            "label": spec["label"],
            "weight": spec["weight"],
            "score": dim_score,
            "coverage": round(cov, 2),
            "verdict": _judge(dim_score) if cov >= MIN_DIM_COVERAGE else "数据不足",
            "factors": factors,
        })

    usable = [d for d in dims if d["score"] is not None and d["coverage"] >= MIN_DIM_COVERAGE]
    total_cov = round(sum(d["weight"] * d["coverage"] for d in dims), 2)
    if usable and sum(d["weight"] for d in usable) > 0 and total_cov >= MIN_TOTAL_COVERAGE:
        overall = round(
            sum(d["score"] * d["weight"] for d in usable) / sum(d["weight"] for d in usable), 1
        )
    else:
        overall = None

    letter, desc = grade_of(overall)
    ranked = sorted([d for d in dims if d["score"] is not None], key=lambda d: d["score"], reverse=True)
    return {
        "overall": overall,
        "grade": letter,
        "grade_desc": desc,
        "total_coverage": total_cov,
        "dimensions": dims,
        "strongest": ranked[0]["key"] if ranked else None,
        "weakest": ranked[-1]["key"] if ranked else None,
        "ranked": [d["key"] for d in ranked],
    }


def bear_case(result: Dict[str, Any], limit: int = 4) -> List[str]:
    """从最弱分项自动生成反方论据，避免报告单边看多。"""
    items: List[Tuple[float, str]] = []
    for d in result.get("dimensions") or []:
        for f in d.get("factors") or []:
            s = f.get("score")
            if isinstance(s, (int, float)) and s < 55:
                items.append((s, f"{d['label']}·{f['label']}：{f.get('evidence','')}（{s} 分）"))
    items.sort(key=lambda x: x[0])
    return [t for _, t in items[:limit]]


def bull_case(result: Dict[str, Any], limit: int = 4) -> List[str]:
    items: List[Tuple[float, str]] = []
    for d in result.get("dimensions") or []:
        for f in d.get("factors") or []:
            s = f.get("score")
            if isinstance(s, (int, float)) and s >= 75:
                items.append((s, f"{d['label']}·{f['label']}：{f.get('evidence','')}（{s} 分）"))
    items.sort(key=lambda x: x[0], reverse=True)
    return [t for _, t in items[:limit]]


def peer_matrix(data: Dict[str, Any]) -> Dict[str, Any]:
    """同业横向对标：把标的放进同业样本里算分位（样本不足时只列值不排名）。"""
    peers = data.get("peers") or []
    if not peers:
        return {"available": False, "reason": "未提供同业样本", "rows": []}
    biz = data.get("business") or {}
    target = {
        "name": (data.get("meta") or {}).get("name") or "本标的",
        "pe_ttm": (biz.get("valuation") or {}).get("pe_ttm"),
        "roe_ttm": (biz.get("profitability") or {}).get("roe_ttm"),
        "np_yoy": (biz.get("growth") or {}).get("np_yoy"),
    }
    rows = [target] + peers
    metrics = ("pe_ttm", "roe_ttm", "np_yoy")
    for m in metrics:
        vals = sorted([r[m] for r in rows if isinstance(r.get(m), (int, float))])
        for r in rows:
            v = r.get(m)
            r[f"{m}_rank"] = (vals.index(v) + 1) if (isinstance(v, (int, float)) and v in vals) else None
            r[f"{m}_n"] = len(vals)
    return {"available": True, "reason": "", "rows": rows, "metrics": list(metrics)}
