#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""replenish_plan.py — 跨境补货计划与库存现金占用

输入日均销量、海运/空运时效、安全天数、MOQ、在库与在途，输出：
补货点、预计断货日、建议补货量、海空切分、在售天数、压货金额、下单触发日。

用法：
    python replenish_plan.py --daily 18 --sea-days 42 --air-days 12 --moq 500 \
        --stock 600 --in-transit 500 --unit-cost 8.46 --cash-budget 20000
    python replenish_plan.py --input case.json
    python replenish_plan.py --selftest
"""

import argparse
import datetime
import json
import math
import sys

DEFAULTS = {
    "daily": None,
    "monthly": None,
    "sea_days": 42,
    "air_days": 12,
    "safety_days": 21,
    "moq": 1,
    "stock": 0,
    "in_transit": 0,
    "unit_cost": 0.0,
    "cash_budget": 0.0,
    "target_cover_days": 75,
    "unit_margin": 0.0,
    "as_of": None,
    "currency": "USD",
}


def load_case(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    case = dict(DEFAULTS)
    case.update({k: v for k, v in data.items() if k in DEFAULTS})
    return case


def parse_date(s):
    if not s:
        return datetime.date.today()
    return datetime.datetime.strptime(s, "%Y-%m-%d").date()


def compute(c):
    if c.get("daily") is None and c.get("monthly") is None:
        raise ValueError("需要 --daily 或 --monthly 之一")
    daily = float(c["daily"]) if c.get("daily") is not None else float(c["monthly"]) / 30.0
    if daily <= 0:
        raise ValueError("日均销量必须大于 0")

    sea = float(c["sea_days"])
    air = float(c["air_days"])
    safety_days = float(c["safety_days"])
    moq = max(1, int(c["moq"]))
    stock = float(c["stock"])
    transit = float(c["in_transit"])
    cost = float(c["unit_cost"])
    cover_target = float(c["target_cover_days"])
    today = parse_date(c["as_of"])

    safety = daily * safety_days
    rop = daily * sea + safety
    available = stock + transit
    cover_days = available / daily
    stock_days = stock / daily
    stockout = today + datetime.timedelta(days=int(math.floor(stock_days)))

    need_cover = daily * cover_target
    raw_need = max(0.0, need_cover - available)
    qty = int(math.ceil(raw_need / moq) * moq) if raw_need > 0 else 0
    if qty == 0 and available < rop:
        qty = moq

    # 海空切分：若在途到货前会断货，缺口用空运补
    gap_days = (sea + safety_days) - cover_days
    air_qty = 0
    if gap_days > 0 and qty > 0:
        air_qty = int(min(qty, math.ceil(daily * gap_days)))
    sea_qty = qty - air_qty

    cash = qty * cost
    over_budget = bool(c["cash_budget"] and cash > float(c["cash_budget"]))

    # 最晚下单日：可用库存（含在途）耗尽前，倒推海运时效
    order_by = today + datetime.timedelta(days=int(math.floor(cover_days - sea)))
    if qty == 0:
        status = "无需下单"
    elif cover_days <= sea + safety_days:
        status = "已触及补货点，立即下单"
    else:
        status = "未触及补货点，按期复核"

    lost_per_day = float(c["unit_margin"]) * daily if c["unit_margin"] else 0.0

    return {
        "currency": c["currency"],
        "daily": daily,
        "safety_stock": safety,
        "safety_days": safety_days,
        "rop": rop,
        "available": available,
        "stock_days": stock_days,
        "cover_days": cover_days,
        "stockout_date": stockout.isoformat(),
        "order_by": order_by.isoformat(),
        "status": status,
        "need_cover": need_cover,
        "qty": qty,
        "sea_qty": sea_qty,
        "air_qty": air_qty,
        "cash": cash,
        "over_budget": over_budget,
        "cash_budget": float(c["cash_budget"]),
        "lost_per_day": lost_per_day,
        "target_cover_days": cover_target,
        "sea_days": sea,
        "air_days": air,
        "moq": moq,
        "as_of": today.isoformat(),
    }


def money(x, cur):
    if abs(x) < 0.005:
        x = 0.0
    return "%.2f %s" % (x, cur)


def render(r):
    cur = r["currency"]
    L = []
    L.append("# 补货与库存现金计划")
    L.append("")
    L.append("基准日 %s｜日均销量 %.1f 件｜海运 %d 天｜空运 %d 天｜安全库存 %d 天"
             % (r["as_of"], r["daily"], r["sea_days"], r["air_days"], r["safety_days"]))
    L.append("")
    L.append("## 一、关键结论")
    L.append("")
    L.append("| 指标 | 数值 | 说明 |")
    L.append("|---|---|---|")
    L.append("| 安全库存 | %.0f 件 | 日均 × 安全天数，断货缓冲垫 |" % r["safety_stock"])
    L.append("| 补货点（ROP） | %.0f 件 | 可用库存低于此值即须下单（按海运时效算） |" % r["rop"])
    L.append("| 可用库存 | %.0f 件 | 在库 + 在途 |" % r["available"])
    L.append("| 在库可售天数 | %.1f 天 | 只算在库，不算在途 |" % r["stock_days"])
    L.append("| 含在途可售天数 | %.1f 天 | 决定是否需要用空运接续 |" % r["cover_days"])
    L.append("| 在库耗尽日 | %s | 只算在库，不含在途 |" % r["stockout_date"])
    L.append("| 最晚下单日 | %s | 从含在途可售天数倒推海运时效，再晚就断档 |" % r["order_by"])
    L.append("| 当前状态 | **%s** | |" % r["status"])
    L.append("")
    L.append("## 二、本次补货建议")
    L.append("")
    L.append("| 项 | 数值 |")
    L.append("|---|---|")
    L.append("| 目标覆盖 | %.0f 天 → 需要 %.0f 件 |" % (r["target_cover_days"], r["need_cover"]))
    L.append("| 建议补货量（按 MOQ %d 取整） | **%d 件** |" % (r["moq"], r["qty"]))
    L.append("| 其中 海运 | %d 件 |" % r["sea_qty"])
    L.append("| 其中 空运 | %d 件 |" % r["air_qty"])
    L.append("| 占用资金 | **%s** |" % money(r["cash"], cur))
    L.append("")
    if r["over_budget"]:
        L.append("> ⚠️ 占用资金 %s 超过现金预算 %s，需减少批量或改分批到货。"
                 % (money(r["cash"], cur), money(r["cash_budget"], cur)))
        L.append("")
    L.append("## 三、为什么这样切海空")
    L.append("")
    if r["air_qty"] > 0:
        L.append("含在途可售 %.1f 天，短于海运时效加安全天数（%d 天）。若全走海运，中间会断货约 %.0f 天。"
                 % (r["cover_days"], int(r["sea_days"] + r["safety_days"]),
                    max(0.0, r["sea_days"] + r["safety_days"] - r["cover_days"])))
        L.append("因此先用空运补 %d 件接续（约 %.0f 天量），其余 %d 件走海运。"
                 % (r["air_qty"], r["air_qty"] / r["daily"], r["sea_qty"]))
        L.append("空运单件成本更高，只补缺口不补库存，是首单阶段的常规做法。")
    else:
        L.append("含在途可售 %.1f 天，长于海运时效加安全天数，无需空运接续，全部走海运。"
                 % r["cover_days"])
    L.append("")
    if r["lost_per_day"] > 0:
        L.append("断货成本参考：按单件毛利 %s 计，断货一天少赚 %s。用这个数去对比空运溢价是否值得。"
                 % (money(r["lost_per_day"] / r["daily"], cur), money(r["lost_per_day"], cur)))
        L.append("")
    L.append("## 四、执行检查")
    L.append("")
    L.append("- [ ] 下单前确认工厂排产期，排产期要算进海运时效之外")
    L.append("- [ ] 到仓后核对实际到货数与破损率，回填日均销量重跑一次")
    L.append("- [ ] 若日均销量较本次假设上下浮动 20%，补货点与批量都要重算")
    L.append("- [ ] 旺季（黑五、圣诞、斋月）前把安全天数上调 7–14 天")
    return "\n".join(L)


def selftest():
    ok = 0
    c = dict(DEFAULTS)
    c.update({"daily": 10, "sea_days": 40, "safety_days": 20, "moq": 100,
              "stock": 100, "in_transit": 0, "unit_cost": 5, "as_of": "2026-10-01"})
    r = compute(c)
    assert r["safety_stock"] == 200
    assert r["rop"] == 600
    assert r["stockout_date"] == "2026-10-11"
    assert r["qty"] % 100 == 0 and r["qty"] > 0
    assert r["air_qty"] > 0, "库存仅 10 天、海运 40 天，应建议空运接续"
    assert r["sea_qty"] + r["air_qty"] == r["qty"]
    ok += 1

    c2 = dict(c)
    c2.update({"stock": 5000, "in_transit": 0})
    r2 = compute(c2)
    assert r2["status"] == "无需下单" and r2["qty"] == 0
    ok += 1

    c3 = dict(c)
    c3.update({"cash_budget": 100})
    r3 = compute(c3)
    assert r3["over_budget"] is True
    ok += 1

    c4 = dict(c)
    c4.update({"daily": 0})
    try:
        compute(c4)
        raise AssertionError("日均 0 应报错")
    except ValueError:
        ok += 1

    c5 = dict(DEFAULTS)
    try:
        compute(c5)
        raise AssertionError("缺销量应报错")
    except ValueError:
        ok += 1

    c6 = dict(DEFAULTS)
    c6.update({"monthly": 300, "as_of": "2026-10-01"})
    r6 = compute(c6)
    assert abs(r6["daily"] - 10) < 1e-9
    ok += 1

    c7 = dict(c)
    c7.update({"unit_margin": 6})
    r7 = compute(c7)
    assert abs(r7["lost_per_day"] - 60) < 1e-9
    ok += 1

    print("selftest passed: %d checks" % ok)
    return 0


def main():
    ap = argparse.ArgumentParser(description="跨境补货计划与库存现金占用")
    ap.add_argument("--input", help="JSON 案例文件")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    for key, val in DEFAULTS.items():
        flag = "--" + key.replace("_", "-")
        if val is None:
            ap.add_argument(flag, default=None)
        elif isinstance(val, str):
            ap.add_argument(flag, default=None)
        elif isinstance(val, int):
            ap.add_argument(flag, type=float, default=None)
        else:
            ap.add_argument(flag, type=float, default=None)
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    case = dict(DEFAULTS)
    if args.input:
        case = load_case(args.input)
    for key in DEFAULTS:
        v = getattr(args, key, None)
        if v is not None:
            case[key] = v

    try:
        r = compute(case)
    except ValueError as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(render(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
