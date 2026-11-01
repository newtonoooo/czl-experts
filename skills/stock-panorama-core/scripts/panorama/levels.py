"""关键价位：只给观察位与风险位，不给买卖指令。

输出里所有价格都是“由已有数据推导”的结果，并带推导依据；
推导不出来的字段返回 None，而不是拍一个数字。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _f(v) -> Optional[float]:
    return float(v) if isinstance(v, (int, float)) else None


def compute_levels(tech: Dict[str, Any]) -> Dict[str, Any]:
    close = _f(tech.get("close"))
    if not close:
        return {"available": False, "reason": "缺少收盘价"}

    ma20, ma60, ma120 = _f(tech.get("ma20")), _f(tech.get("ma60")), _f(tech.get("ma120"))
    sh20, sl20 = _f(tech.get("swing_high_20")), _f(tech.get("swing_low_20"))
    atr = _f(tech.get("atr14"))

    below = [x for x in (ma20, ma60, ma120, sl20) if x and x < close]
    above = [x for x in (ma20, ma60, ma120, sh20) if x and x > close]

    support = max(below) if below else None
    support_basis = ""
    if support is not None:
        for name, val in (("20 日均线", ma20), ("60 日均线", ma60), ("120 日均线", ma120), ("20 日低点", sl20)):
            if val == support:
                support_basis = name
                break
    resistance = min(above) if above else None
    resistance_basis = ""
    if resistance is not None:
        for name, val in (("20 日均线", ma20), ("60 日均线", ma60), ("120 日均线", ma120), ("20 日高点", sh20)):
            if val == resistance:
                resistance_basis = name
                break

    risk_line = round(close - 2 * atr, 2) if atr else None
    pos = _f(tech.get("position_250"))
    # 展示层面统一保留两位小数，避免 227.0075 这种“精确的错觉”
    support = round(support, 2) if support is not None else None
    resistance = round(resistance, 2) if resistance is not None else None

    notes: List[str] = []
    if support is not None and close:
        notes.append(f"第一支撑 {support}（{support_basis}），距现价 {round((close / support - 1) * 100, 2)}%")
    else:
        notes.append("现价下方缺少可用的均线/低点参照，支撑位需结合更长周期数据补充")
    if resistance is not None and close:
        notes.append(f"第一压力 {resistance}（{resistance_basis}），距现价 {round((resistance / close - 1) * 100, 2)}%")
    if risk_line:
        notes.append(f"两倍 ATR 风险位 {risk_line}，跌破视为短线结构走坏（ATR={round(atr, 2)}）")
    if pos is not None:
        zone = "高位区" if pos >= 0.7 else ("中位区" if pos >= 0.3 else "低位区")
        notes.append(f"现价处于近 250 日区间 {round(pos * 100)}% 位置（{zone}）")

    return {
        "available": True,
        "close": close,
        "support": support,
        "support_basis": support_basis,
        "resistance": resistance,
        "resistance_basis": resistance_basis,
        "risk_line": risk_line,
        "position_250": pos,
        "notes": notes,
        "disclaimer": "以上为技术参照位，不构成买卖建议；跳空、除权、涨跌停会使参照失效。",
    }
