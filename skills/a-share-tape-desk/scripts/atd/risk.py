"""仓位、止损与盈亏比计算。

原则：先定亏多少，再定买多少。
单笔风险预算 = 总资金 x 单笔风险比例（默认 1%）；
可买股数 = 单笔风险预算 / 每股风险（入场价与止损价之差），向下取整到 100 股；
再与"最大仓位"和"实际可用资金"取小。

所有数字都是算出来的，不是估的。算完之后逐项做检查，把不合法的地方指出来。
"""

from . import codes

BOARD_LOT = 100


def _r(v, digits=2):
    return None if v is None else round(v, digits)


def plan(
    entry,
    stop=None,
    capital=100000.0,
    risk_pct=1.0,
    max_position_pct=30.0,
    atr=None,
    atr_mult=2.0,
    prev_close=None,
    limit_up=None,
    is_limit_up=False,
    name=None,
    targets_r=(1.5, 2.5, 4.0),
    lot=BOARD_LOT,
):
    """生成一份交易计划。

    entry / stop 单位元；capital 元；risk_pct、max_position_pct 为百分数。
    stop 缺省时用 ATR 计算（entry - atr_mult x ATR）。
    """
    checks = []
    warnings = []

    entry = float(entry)
    if stop is None and atr:
        stop = entry - atr_mult * float(atr)
        stop_source = "ATR%d倍（%.2f x %s）" % (atr_mult, atr_mult, round(float(atr), 3))
    elif stop is not None:
        stop = float(stop)
        stop_source = "用户指定"
    else:
        stop = entry * 0.93
        stop_source = "缺省 -7%（未给止损也未给ATR）"
        warnings.append("既没有指定止损价，也没有ATR数据，止损按 -7% 兜底估算，建议用户明确止损位")

    if stop >= entry:
        checks.append({"item": "止损价必须低于入场价", "pass": False, "detail": "止损 %.2f >= 入场 %.2f" % (stop, entry)})
        stop = entry * 0.95
    else:
        checks.append({"item": "止损价低于入场价", "pass": True, "detail": "止损 %.2f / 入场 %.2f" % (stop, entry)})

    per_share_risk = entry - stop
    stop_pct = per_share_risk / entry * 100.0
    risk_budget = capital * risk_pct / 100.0

    shares_by_risk = int(risk_budget // per_share_risk // lot) * lot if per_share_risk > 0 else 0
    cap_by_position = capital * max_position_pct / 100.0
    shares_by_position = int(cap_by_position // entry // lot) * lot
    shares = min(shares_by_risk, shares_by_position)

    position_value = shares * entry
    position_pct = position_value / capital * 100.0
    actual_risk = shares * per_share_risk
    actual_risk_pct = actual_risk / capital * 100.0

    binding = "单笔风险预算" if shares_by_risk <= shares_by_position else "仓位上限"

    if shares == 0:
        lot_cost = lot * entry
        checks.append(
            {
                "item": "股数计算",
                "pass": False,
                "detail": "算不出可买股数。1 手需要 %.0f 元，仓位上限只允许 %.0f 元；"
                "按单笔风险 %.0f 元与每股风险 %.2f 元最多 %.0f 股。结论：这笔交易在当前资金与风控参数下做不了，"
                "要么放宽仓位上限，要么等价格回落后止损收窄" % (lot_cost, cap_by_position, risk_budget, per_share_risk, shares_by_risk),
            }
        )
    else:
        checks.append(
            {
                "item": "股数与资金",
                "pass": True,
                "detail": "%d 股，占用 %.0f 元（%.1f%% 仓位），触发止损亏 %.0f 元（%.2f%%）；约束项：%s"
                % (shares, position_value, position_pct, actual_risk, actual_risk_pct, binding),
            }
        )

    if position_pct > max_position_pct + 0.01:
        warnings.append("仓位超过上限 %.0f%%" % max_position_pct)
    if stop_pct > 10:
        warnings.append("止损距离 %.1f%% 偏宽，单笔波动可能超出承受范围" % stop_pct)
    if stop_pct < 1.5:
        warnings.append("止损距离仅 %.1f%%，日内噪声就可能打掉，注意被扫损" % stop_pct)
    if is_limit_up:
        warnings.append("标的当前处于涨停价，涨停板上排队成交概率低，计划价可能买不到")
    if name and codes.is_st(name):
        warnings.append("ST 标的涨跌幅限制 5%，流动性与退市风险都需单独评估")

    targets = []
    for multi in targets_r:
        price = entry + per_share_risk * multi
        if limit_up and price > float(limit_up):
            note = "超出今日涨停价，需分日实现"
        else:
            note = ""
        targets.append(
            {
                "r": multi,
                "price": _r(price),
                "gain_pct": _r((price / entry - 1) * 100),
                "note": note,
            }
        )

    if prev_close:
        gap = (entry - float(prev_close)) / float(prev_close) * 100.0
        if abs(gap) >= 5:
            warnings.append("入场价较昨收偏离 %.1f%%，注意跳空缺口回补风险" % gap)

    # 最小可行规模：算不出整手时，把"买 1 手会承担多少风险"摆出来让用户自己判断
    lot_cost = lot * entry
    lot_risk = lot * per_share_risk
    min_viable = {
        "lot_cost": _r(lot_cost),
        "lot_risk": _r(lot_risk),
        "lot_risk_pct": _r(lot_risk / capital * 100) if capital else None,
        "lot_position_pct": _r(lot_cost / capital * 100) if capital else None,
        "within_budget": lot_risk <= risk_budget * 1.5,
        "suggestion": None,
    }
    if shares == 0:
        if min_viable["within_budget"]:
            min_viable["suggestion"] = (
                "最小可行规模是 1 手：占用 %.0f 元（%.1f%% 仓位），止损亏 %.0f 元（%.2f%% 资金），"
                "比 1%% 的风险预算略高但在可接受范围。要么接受这一手的超配，要么把止损收窄到 %.2f 元以内"
                % (
                    lot_cost,
                    min_viable["lot_position_pct"] or 0,
                    lot_risk,
                    min_viable["lot_risk_pct"] or 0,
                    entry - risk_budget / lot,
                )
            )
        else:
            min_viable["suggestion"] = (
                "1 手就要亏 %.0f 元（%.2f%% 资金），远超单笔风险预算。这只票的波动对当前资金体量太大，"
                "建议换标的、降杠杆，或用更紧的结构性止损（例如跌破前低而非 ATR 止损）"
                % (lot_risk, min_viable["lot_risk_pct"] or 0)
            )

    risk_reward = {}
    for t in targets:
        risk_reward["R%.1f" % t["r"]] = t["r"]

    return {
        "entry": _r(entry),
        "stop": _r(stop),
        "stop_pct": _r(stop_pct),
        "stop_source": stop_source,
        "per_share_risk": _r(per_share_risk),
        "risk_budget": _r(risk_budget),
        "shares": shares,
        "position_value": _r(position_value),
        "position_pct": _r(position_pct),
        "actual_risk": _r(actual_risk),
        "actual_risk_pct": _r(actual_risk_pct),
        "targets": targets,
        "risk_reward": risk_reward,
        "min_viable": min_viable,
        "checks": checks,
        "warnings": warnings,
        "assumptions": {
            "capital": _r(capital),
            "risk_pct": risk_pct,
            "max_position_pct": max_position_pct,
            "lot": lot,
            "atr_mult": atr_mult,
            "fee_note": "未计入佣金、印花税与过户费；短线高频交易需自行把这些成本折算进盈亏比",
        },
    }


def portfolio_risk(positions, capital):
    """组合层面：所有持仓同时触发止损时的总亏损占比。

    positions: [{"code","name","entry","stop","shares"}]
    """
    total = 0.0
    detail = []
    for p in positions:
        risk = max(0.0, (float(p["entry"]) - float(p["stop"])) * int(p["shares"]))
        total += risk
        detail.append(
            {
                "code": p.get("code"),
                "name": p.get("name"),
                "risk": _r(risk),
                "risk_pct": _r(risk / capital * 100) if capital else None,
            }
        )
    pct = total / capital * 100 if capital else None
    level = "可控" if pct is not None and pct <= 3 else ("偏高" if pct is not None and pct <= 6 else "过高")
    return {
        "total_risk": _r(total),
        "total_risk_pct": _r(pct),
        "level": level,
        "detail": detail,
        "advice": "全部止损同时发生时的回撤上限；超过 6% 说明同一逻辑押得太重，需要分散到不同驱动因素",
    }
