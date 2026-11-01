#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""promo_math.py - 大促机制算账与备货现金测算（纯标准库）。

两个子命令
----------
stack  多层优惠叠加后的实收、毛利与保本实收；标出哪一层把毛利打穿
stock  备货量、采购金额、现金占用天数，以及 5 档达成率下的断货/滞销风险

叠加顺序（固定，不随平台改变）：单品折扣 -> 会员折扣 -> 店铺券/店铺满减 -> 跨店满减按金额占比分摊。
平台真实叠加顺序若有差异，结果会变，必须以后台活动规则页为准并在交付时注明。

退出码：0 = 健康；1 = 活动价亏损或备货触发单一风险；2 = 输入错误。
"""

from __future__ import annotations

import argparse
import json
import math
import sys

EPS = 1e-9


def _money(x):
    if abs(x) < 0.005:
        x = 0.0
    return f"{x:,.2f}"


def _pct(x):
    return f"{x * 100:.1f}%"


# ---------------------------------------------------------------- stack


def calc_stack(a):
    layers = []
    price = a.price
    layers.append(("活动前成交价", price, 0.0, 1.0))

    step = price * a.item_discount
    layers.append(("单品折扣 ×%.2f" % a.item_discount, step, price - step, step / price if price else 0))
    price = step

    step = price * a.member
    layers.append(("会员折扣 ×%.2f" % a.member, step, price - step, step / a.price if a.price else 0))
    price = step

    if a.store_coupon > 0:
        gate = price >= a.store_threshold - EPS
        step = price - a.store_coupon if gate else price
        label = f"店铺券 满{a.store_threshold:g}减{a.store_coupon:g}" + ("" if gate else "（未达门槛）")
        layers.append((label, step, price - step, step / a.price if a.price else 0))
        price = step

    cross_share = 0.0
    if a.cross_off > 0:
        if a.order_amount >= a.cross_threshold - EPS:
            cross_share = a.cross_off * (price / a.order_amount)
            step = price - cross_share
            label = f"跨店满减 {a.cross_threshold:g}-{a.cross_off:g}（按金额占比分摊）"
            layers.append((label, step, price - step, step / a.price if a.price else 0))
            price = step
        else:
            layers.append((f"跨店满减（整单 {a.order_amount:g} 未达 {a.cross_threshold:g}）", price, 0.0,
                           price / a.price if a.price else 0))

    received = price
    rate = a.commission + a.payment + a.tax
    variable = received * rate
    margin = received - a.cost - a.ship - a.pack - a.gift_cost - variable
    margin_rate = margin / received if received > EPS else 0.0
    breakeven_received = (a.cost + a.ship + a.pack + a.gift_cost) / (1 - rate) if rate < 1 else None
    gap = (received - breakeven_received) if breakeven_received is not None else None

    if margin < -EPS:
        verdict = "亏损"
    elif margin_rate < 0.08:
        verdict = "薄利"
    else:
        verdict = "健康"

    return {
        "list_price": a.price,
        "received": received,
        "total_discount": a.price - received,
        "discount_rate": (a.price - received) / a.price if a.price else 0.0,
        "unit_cost_total": a.cost + a.ship + a.pack + a.gift_cost,
        "platform_rate": rate,
        "platform_fee": variable,
        "margin": margin,
        "margin_rate": margin_rate,
        "breakeven_received": breakeven_received,
        "margin_buffer": gap,
        "verdict": verdict,
        "layers": [{"layer": n, "after": round(v, 4), "give": round(g, 4), "ratio": round(p, 4)}
                   for n, v, g, p in layers],
    }


def print_stack(r):
    print("## 活动机制叠加账本")
    print()
    print("| 层 | 本层后实收 | 本层让利 | 累计实收/活动前价 |")
    print("|---|---:|---:|---:|")
    for row in r["layers"]:
        print(f"| {row['layer']} | {_money(row['after'])} | {_money(row['give'])} | {_pct(row['ratio'])} |")
    print()
    print("| 指标 | 数值 | 口径 |")
    print("|---|---:|---|")
    print(f"| 活动价实收 | {_money(r['received'])} | 买家实付扣除各类优惠后商家到手（未扣平台费） |")
    print(f"| 总让利率 | {_pct(r['discount_rate'])} | 相对活动前成交价 |")
    print(f"| 商品侧成本 | {_money(r['unit_cost_total'])} | 拿货+发货+包装+赠品 |")
    print(f"| 平台费率 | {_pct(r['platform_rate'])} | 佣金+支付+税费，按实收计 |")
    print(f"| 单件毛利 | {_money(r['margin'])} | 实收 − 商品侧成本 − 平台费 |")
    print(f"| 毛利率 | {_pct(r['margin_rate'])} | 按实收计 |")
    if r["breakeven_received"] is None:
        print("| 保本实收 | 不成立 | 平台费率已 ≥100% |")
    else:
        print(f"| 保本实收 | {_money(r['breakeven_received'])} | 毛利归零的实收金额 |")
    print()
    if r["margin_buffer"] is not None:
        if r["margin_buffer"] >= 0:
            print(f"余量：实收比保本线高 {_money(r['margin_buffer'])} 元/件。")
        else:
            print(f"缺口：实收比保本线低 {_money(-r['margin_buffer'])} 元/件，按预估销量算，卖得越多亏得越多。")
    # 找出让利最大的一层（不含首个基准层）
    if len(r["layers"]) > 1:
        worst = max(r["layers"][1:], key=lambda x: x["give"])
        print(f"让利最大的一层：{worst['layer']}，让出 {_money(worst['give'])} 元/件。")
    print(f"判定：{r['verdict']}")


# ---------------------------------------------------------------- stock


def calc_stock(a):
    demand = a.daily * a.uplift * a.days + a.daily * a.lead_days
    safety = a.daily * a.uplift * a.safety_days
    target = demand + safety
    need = max(0.0, target - a.current)
    qty = need
    if a.moq > 0:
        qty = math.ceil(need / a.moq) * a.moq
    qty = int(math.ceil(qty))
    purchase = qty * a.unit_cost
    cash_days = a.lead_days + a.days + a.settle_days - a.payable_days
    peak_cash = purchase if a.payable_days <= 0 else purchase * max(0.0, 1 - a.payable_days / max(1.0, a.lead_days + a.days + a.settle_days))

    scenarios = []
    for ratio in (0.6, 0.8, 1.0, 1.2, 1.5):
        sold = demand * ratio
        stock_left = a.current + qty - sold
        stockout = max(0.0, sold - (a.current + qty))
        frozen = max(0.0, stock_left) * a.unit_cost
        scenarios.append({
            "ratio": ratio,
            "sold": round(sold, 0),
            "left": round(stock_left, 0),
            "stockout": round(stockout, 0),
            "frozen_cash": round(frozen, 2),
        })

    risk = []
    # 断货风险：达成 120% 就缺货，说明备货偏紧到正常波动即断
    short = next((s for s in scenarios if s["ratio"] <= 1.2 + EPS and s["stockout"] > 0), None)
    # 滞销风险：只达成 80% 时，期末库存仍超过一整期活动需求
    over = next((s for s in scenarios if abs(s["ratio"] - 0.8) < EPS and s["left"] > demand), None)
    if short:
        risk.append("断货")
    if over:
        risk.append("滞销")

    return {
        "demand": round(demand, 0),
        "safety": round(safety, 0),
        "target": round(target, 0),
        "current": a.current,
        "buy_qty": qty,
        "purchase_amount": round(purchase, 2),
        "cash_days": cash_days,
        "peak_cash": round(peak_cash, 2),
        "unit_cost": a.unit_cost,
        "scenarios": scenarios,
        "risks": risk,
    }


def print_stock(r):
    print("## 备货与现金占用")
    print(f"- 活动期需求：{r['demand']:.0f} 件（含备货提前期的日常销量）")
    print(f"- 安全库存：{r['safety']:.0f} 件")
    print(f"- 现有库存：{r['current']:.0f} 件")
    print(f"- 建议采购：{r['buy_qty']} 件（已按起订量取整）")
    print(f"- 采购金额：{_money(r['purchase_amount'])} 元")
    print(f"- 现金占用天数：约 {r['cash_days']:.0f} 天（提前期 + 活动天数 + 结算周期 − 供应商账期）")
    print(f"- 现金峰值：约 {_money(r['peak_cash'])} 元")
    print()
    print("| 销量达成 | 卖出 | 期末库存 | 断货量 | 占用资金 |")
    print("|---:|---:|---:|---:|---:|")
    for s in r["scenarios"]:
        print(f"| {_pct(s['ratio'])} | {s['sold']:.0f} | {s['left']:.0f} | {s['stockout']:.0f} | {_money(s['frozen_cash'])} |")
    print()
    if r["risks"]:
        print("风险：" + " + ".join(r["risks"]))
        if "断货" in r["risks"]:
            print("断货对策：把安全库存从当前档提高一档，或对爆款做二批小单快返，不要一次压满。")
        if "滞销" in r["risks"]:
            print("滞销对策：把首批量压到预测的 60–70%，活动第二天按实时动销补单；同时准备返场价与清货渠道。")
    else:
        print("风险：断货与滞销两端都在容忍范围内。")
    print("提醒：现金峰值超过可动用现金时，先减备货量，不要靠账期硬扛。")


# ---------------------------------------------------------------- 入口


def add_stack(p):
    p.add_argument("--price", type=float, required=True, help="活动前成交价，元")
    p.add_argument("--item-discount", dest="item_discount", type=float, default=1.0)
    p.add_argument("--member", type=float, default=1.0, help="会员折扣，0.95=95折")
    p.add_argument("--store-threshold", dest="store_threshold", type=float, default=0)
    p.add_argument("--store-coupon", dest="store_coupon", type=float, default=0)
    p.add_argument("--cross-threshold", dest="cross_threshold", type=float, default=0)
    p.add_argument("--cross-off", dest="cross_off", type=float, default=0)
    p.add_argument("--order-amount", dest="order_amount", type=float, default=0,
                   help="整单金额，用于分摊跨店满减；默认取跨店门槛")
    p.add_argument("--cost", type=float, required=True, help="商品成本，元")
    p.add_argument("--ship", type=float, default=0)
    p.add_argument("--pack", type=float, default=0)
    p.add_argument("--gift-cost", dest="gift_cost", type=float, default=0)
    p.add_argument("--commission", type=float, default=0)
    p.add_argument("--payment", type=float, default=0)
    p.add_argument("--tax", type=float, default=0)
    p.add_argument("--json", action="store_true")


def add_stock(p):
    p.add_argument("--daily", type=float, required=True, help="日常日均销量，件")
    p.add_argument("--uplift", type=float, default=2.0, help="活动期销量倍数")
    p.add_argument("--days", type=float, default=3, help="活动天数")
    p.add_argument("--lead-days", dest="lead_days", type=float, default=7, help="备货提前期")
    p.add_argument("--safety-days", dest="safety_days", type=float, default=3)
    p.add_argument("--current", type=float, default=0, help="现有库存")
    p.add_argument("--moq", type=float, default=0, help="起订量，0=不取整")
    p.add_argument("--unit-cost", dest="unit_cost", type=float, required=True)
    p.add_argument("--settle-days", dest="settle_days", type=float, default=15, help="平台结算周期")
    p.add_argument("--payable-days", dest="payable_days", type=float, default=0, help="供应商账期")
    p.add_argument("--json", action="store_true")


def main(argv=None):
    ap = argparse.ArgumentParser(description="大促机制算账与备货测算")
    sub = ap.add_subparsers(dest="cmd", required=True)
    add_stack(sub.add_parser("stack", help="优惠叠加后的实收与毛利"))
    add_stock(sub.add_parser("stock", help="备货量与现金占用"))
    a = ap.parse_args(argv)

    if a.cmd == "stack":
        if a.cross_off > 0 and a.cross_threshold <= 0:
            print("输入错误：给了 --cross-off 就必须给 --cross-threshold", file=sys.stderr)
            return 2
        if a.order_amount <= 0:
            a.order_amount = a.cross_threshold if a.cross_threshold > 0 else 1.0
        if a.order_amount < a.cross_threshold:
            a.order_amount = a.cross_threshold
        for k in ("price", "cost"):
            if getattr(a, k) <= 0:
                print(f"输入错误：--{k} 必须为正", file=sys.stderr)
                return 2
        for k in ("item_discount", "member"):
            if not (0 < getattr(a, k) <= 1):
                print(f"输入错误：--{k.replace('_', '-')} 应在 (0,1] 区间", file=sys.stderr)
                return 2
        for k in ("commission", "payment", "tax"):
            if getattr(a, k) < 0:
                print(f"输入错误：--{k} 不能为负", file=sys.stderr)
                return 2
        if a.commission + a.payment + a.tax >= 1:
            print("输入错误：平台费率合计必须小于 100%", file=sys.stderr)
            return 2
        r = calc_stack(a)
        if a.json:
            print(json.dumps(r, ensure_ascii=False, indent=2))
        else:
            print_stack(r)
        return 1 if r["margin"] < -EPS else 0

    if a.daily <= 0 or a.unit_cost <= 0 or a.uplift <= 0 or a.days <= 0:
        print("输入错误：--daily / --unit-cost / --uplift / --days 必须为正", file=sys.stderr)
        return 2
    if a.current < 0:
        print("输入错误：--current 不能为负", file=sys.stderr)
        return 2
    r = calc_stock(a)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print_stock(r)
    return 1 if r["risks"] else 0


if __name__ == "__main__":
    sys.exit(main())
