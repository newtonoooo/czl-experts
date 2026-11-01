#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""landed_cost.py — 到岸成本瀑布与保本线计算器

按"每成交一单"（per kept order）建模，退货按 1/(1-r) 稀释发货量。
纯标准库，无第三方依赖。

用法：
    python landed_cost.py --input case.json
    python landed_cost.py --price 19.99 --unit-cost 12 --cost-in-cny --fx 7.15 \
        --freight 3.2 --fulfillment 4.75 --commission-pct 15 --return-rate 8 --ad-pct 12
    python landed_cost.py --selftest
    python landed_cost.py --input case.json --json

所有金额单位一致（目标币）。--cost-in-cny 只折算中国侧成本（采购/包装/头程）；
目的国侧费用（配送费/仓储/退货处理）本身就是目标币，不折算。
缺参数不猜：未给出的费率保持 0，输出中会提示需要补充。"""

import argparse
import json
import sys

DEFAULTS = {
    "currency": "USD",
    "price": None,
    "unit_cost": None,
    "packaging": 0.0,
    "freight": 0.0,
    "duty_pct": 0.0,
    "vat_pct": 0.0,
    "vat_recoverable": True,
    "commission_pct": 0.0,
    "fulfillment": 0.0,
    "storage": 0.0,
    "storage_months": 2.0,
    "return_rate": 0.0,
    "return_handling": 0.0,
    "return_recovery_pct": 0.0,
    "payment_pct": 0.0,
    "other_pct": 0.0,
    "ad_pct": 0.0,
    "fixed_monthly": 0.0,
    "target_margin_pct": 15.0,
    "fx": None,
    "cost_in_cny": False,
}

FEE_KEYS = [
    ("duty_pct", "关税税率", "%"),
    ("commission_pct", "平台佣金率", "%"),
    ("payment_pct", "收款手续费率", "%"),
    ("ad_pct", "广告费占售价", "%"),
]


def load_case(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    case = dict(DEFAULTS)
    case.update({k: v for k, v in data.items() if k in DEFAULTS})
    return case


def merge_args(case, args):
    if args.input:
        pass
    for key in DEFAULTS:
        val = getattr(args, key, None)
        if val is not None:
            case[key] = val
    return case


def compute(c, deep=True):
    """核心模型。返回 dict，含瀑布明细与三条保本线。

    deep=False 时跳过敏感性网格（敏感性内部递归调用，避免无限展开）。
    """
    missing = [k for k in ("price", "unit_cost") if c.get(k) is None]
    if missing:
        raise ValueError("缺少必需参数: " + ", ".join(missing))

    fx = c.get("fx") or None
    if c["cost_in_cny"]:
        if not fx:
            raise ValueError("--cost-in-cny 需要同时给出 --fx（人民币兑目标币汇率）")
        div = float(fx)
    else:
        div = 1.0

    price = float(c["price"])
    # 中国侧成本可按人民币给，按汇率折算；目的国侧费用（配送/仓储/退货处理）本身就是目标币，不折算。
    unit_cost = float(c["unit_cost"]) / div
    packaging = float(c["packaging"]) / div
    freight = float(c["freight"]) / div
    fulfillment = float(c["fulfillment"])
    return_handling = float(c["return_handling"])
    storage = float(c["storage"])

    r = float(c["return_rate"]) / 100.0
    if not 0.0 <= r < 1.0:
        raise ValueError("退货率必须在 0 与 100 之间（不含 100）")
    shipped = 1.0 / (1.0 - r)

    duty = (unit_cost + freight) * float(c["duty_pct"]) / 100.0
    vat_unit = (unit_cost + freight) * float(c["vat_pct"]) / 100.0
    vat_cost = 0.0 if c["vat_recoverable"] else vat_unit * shipped

    goods_unit = unit_cost + packaging + freight + duty
    goods_total = goods_unit * shipped
    recovered = r * shipped * unit_cost * float(c["return_recovery_pct"]) / 100.0
    fulfillment_total = fulfillment * shipped
    return_handling_total = r * shipped * return_handling
    storage_total = storage * float(c["storage_months"])

    landed = goods_total - recovered + fulfillment_total + return_handling_total \
        + storage_total + vat_cost

    k_pct = sum(float(c[x]) for x in ("commission_pct", "payment_pct", "other_pct", "ad_pct")) / 100.0
    commission = price * float(c["commission_pct"]) / 100.0
    payment = price * float(c["payment_pct"]) / 100.0
    other = price * float(c["other_pct"]) / 100.0
    ad = price * float(c["ad_pct"]) / 100.0

    net = price - landed - commission - payment - other - ad
    margin = net / price if price else 0.0
    cm_before_ad = price - landed - commission - payment - other
    be_acos = cm_before_ad / price if price else 0.0

    be_price = landed / (1.0 - k_pct) if k_pct < 1.0 else float("inf")
    target_price = landed / (1.0 - k_pct - float(c["target_margin_pct"]) / 100.0)

    fixed = float(c["fixed_monthly"])
    be_daily = fixed / net if (fixed > 0 and net > 0) else None

    ladder = []
    for tag, mult in (("低价切入", 0.90), ("主流", 1.00), ("溢价", 1.10)):
        p = price * mult
        n = p - landed - p * (k_pct)
        ladder.append({
            "档位": tag, "价格": p, "净利": n,
            "净利率": n / p if p else 0.0,
        })

    sens = []
    if deep:
        for cost_mult in (0.90, 1.00, 1.10):
            row = {"采购价系数": cost_mult, "格": {}}
            for rr in (-5.0, 0.0, 5.0):
                c2 = dict(c)
                c2["unit_cost"] = unit_cost * cost_mult * div
                c2["return_rate"] = max(0.0, min(99.0, float(c["return_rate"]) + rr))
                res = compute(c2, deep=False)
                row["格"]["%+.0fpct" % rr] = res["net_margin"]
            sens.append(row)

    return {
        "currency": c["currency"],
        "price": price,
        "shipped_per_kept": shipped,
        "waterfall": {
            "采购": unit_cost * shipped,
            "包装": packaging * shipped,
            "头程": freight * shipped,
            "关税": duty * shipped,
            "退货回收抵扣": -recovered,
            "配送费": fulfillment_total,
            "退货处理": return_handling_total,
            "仓储": storage_total,
            "进口VAT(不可抵扣)": vat_cost,
            "落地成本合计": landed,
            "平台佣金": commission,
            "收款手续费": payment,
            "其他变动": other,
            "广告": ad,
        },
        "landed": landed,
        "net": net,
        "net_margin": margin,
        "cm_before_ad": cm_before_ad,
        "be_acos": be_acos,
        "ad_pct": float(c["ad_pct"]) / 100.0,
        "be_price": be_price,
        "target_price": target_price,
        "target_margin": float(c["target_margin_pct"]) / 100.0,
        "be_daily": be_daily,
        "fixed_monthly": fixed,
        "ladder": ladder,
        "sensitivity": sens,
        "vat_cash_lock": vat_unit * shipped if c["vat_recoverable"] else 0.0,
        "return_rate": float(c["return_rate"]),
    }


def pct(x):
    return "%.1f%%" % (x * 100.0)


def money(x, cur):
    if abs(x) < 0.005:
        x = 0.0
    return "%.2f %s" % (x, cur)


def render(res, c):
    cur = res["currency"]
    L = []
    L.append("# 到岸成本与保本线")
    L.append("")
    L.append("口径：按 **每成交一单** 计算；退货率 %.0f%% → 每成交一单需发出 %.2f 件。"
             % (res["return_rate"], res["shipped_per_kept"]))
    L.append("")
    L.append("## 一、成本瀑布（每成交一单）")
    L.append("")
    L.append("| 科目 | 金额 | 占售价 |")
    L.append("|---|---|---|")
    for k, v in res["waterfall"].items():
        share = (v / res["price"]) if res["price"] else 0.0
        L.append("| %s | %s | %s |" % (k, money(v, cur), pct(share)))
    L.append("| **净利** | **%s** | **%s** |" % (money(res["net"], cur), pct(res["net_margin"])))
    L.append("")
    L.append("## 二、三条保本线")
    L.append("")
    L.append("| 指标 | 数值 | 怎么用 |")
    L.append("|---|---|---|")
    L.append("| 保本售价（净利=0） | %s | 低于这个价，卖一件亏一件 |" % money(res["be_price"], cur))
    L.append("| 保本 ACOS（广告前贡献率） | %s | 广告 ACOS 高于此值即亏损，当前设定广告占比 %s |"
             % (pct(res["be_acos"]), pct(res["ad_pct"])))
    tgt = money(res["target_price"], cur)
    L.append("| 目标净利率 %s 对应售价 | %s | 定价谈判的锚 |" % (pct(res["target_margin"]), tgt))
    if res["be_daily"] is not None:
        L.append("| 保本日销（覆盖固定费用 %s/月） | %.1f 单/天 | 低于这个量，固定费用吃光利润 |"
                 % (money(res["fixed_monthly"], cur), res["be_daily"]))
    L.append("")
    L.append("## 三、价格阶梯")
    L.append("")
    L.append("| 档位 | 售价 | 净利 | 净利率 | 判定 |")
    L.append("|---|---|---|---|---|")
    for row in res["ladder"]:
        verdict = "过线" if row["净利率"] >= 0.15 else ("薄" if row["净利率"] >= 0.10 else "不可做")
        L.append("| %s | %s | %s | %s | %s |" % (
            row["档位"], money(row["价格"], cur), money(row["净利"], cur),
            pct(row["净利率"]), verdict))
    L.append("")
    L.append("## 四、敏感性（净利率）")
    L.append("")
    L.append("| 采购价 \\ 退货率 | -5pct | 基准 | +5pct |")
    L.append("|---|---|---|---|")
    for row in res["sensitivity"]:
        vals = row["格"]
        L.append("| x%.2f | %s | %s | %s |" % (
            row["采购价系数"], pct(vals["-5pct"]), pct(vals["+0pct"]), pct(vals["+5pct"])))
    L.append("")
    L.append("## 五、结论")
    L.append("")
    m = res["net_margin"]
    if m < 0.10:
        L.append("- **不可做（当前成本结构下）**：净利率 %s，低于 10%% 下限。要么提价到 %s 以上，要么把落地成本压到 %s 以下。"
                 % (pct(m), money(res["target_price"], cur), money(res["landed"], cur)))
    elif m < 0.15:
        L.append("- **偏薄**：净利率 %s，低于 15%% 警戒线。可以做，但要接受广告试错空间很小，且先做小批量验证。" % pct(m))
    else:
        L.append("- **可做**：净利率 %s，高于 15%% 警戒线，具备投放试错空间。" % pct(m))
    if res["be_acos"] < res["ad_pct"]:
        L.append("- ⚠️ 保本 ACOS（%s）已低于当前广告占比（%s），意味着当前投放强度下必然亏损。" % (
            pct(res["be_acos"]), pct(res["ad_pct"])))
    if res["vat_cash_lock"] > 0:
        L.append("- 进口 VAT %s 可抵扣，但先垫付，属于现金流占用，不计入成本。" % money(res["vat_cash_lock"], cur))
    L.append("")
    L.append("> 费率与税率的取数日期、来源需在交付时注明；本表不替任何一方保证平台实际扣费。")
    return "\n".join(L)


def selftest():
    ok = 0
    c = dict(DEFAULTS)
    c.update({"price": 100.0, "unit_cost": 20.0, "commission_pct": 15.0, "ad_pct": 10.0})
    res = compute(c)
    assert abs(res["landed"] - 20.0) < 1e-9
    assert abs(res["net"] - (100 - 20 - 15 - 10)) < 1e-9
    ok += 1

    c2 = dict(c)
    res2 = compute(c2)
    be = res2["be_price"]
    c3 = dict(c2)
    c3["price"] = be
    res3 = compute(c3)
    assert abs(res3["net"]) < 1e-6, "保本价代入后净利应为 0，实际 %s" % res3["net"]
    ok += 1

    tgt = res2["target_price"]
    c4 = dict(c2)
    c4["price"] = tgt
    res4 = compute(c4)
    assert abs(res4["net_margin"] - 0.15) < 1e-6, "目标净利率未命中"
    ok += 1

    c5 = dict(c2)
    c5["return_rate"] = 20.0
    res5 = compute(c5)
    assert abs(res5["shipped_per_kept"] - 1.25) < 1e-9
    assert res5["landed"] > res2["landed"], "退货率上升后落地成本应上升"
    ok += 1

    c6 = dict(c2)
    c6["return_rate"] = 100.0
    try:
        compute(c6)
        raise AssertionError("退货率 100 应报错")
    except ValueError:
        ok += 1

    c7 = dict(c2)
    c7.update({"cost_in_cny": True})
    try:
        compute(c7)
        raise AssertionError("缺 fx 应报错")
    except ValueError:
        ok += 1

    c8 = dict(c2)
    c8.update({"cost_in_cny": True, "fx": 7.0, "unit_cost": 140.0})
    res8 = compute(c8)
    assert abs(res8["waterfall"]["采购"] - 20.0) < 1e-9
    ok += 1

    print("selftest passed: %d checks" % ok)
    return 0


def main():
    ap = argparse.ArgumentParser(description="到岸成本瀑布与保本线计算器")
    ap.add_argument("--input", help="JSON 案例文件")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--selftest", action="store_true", help="运行自检")
    for key, val in DEFAULTS.items():
        if isinstance(val, bool):
            ap.add_argument("--" + key.replace("_", "-"), action="store_true", default=None)
        else:
            ap.add_argument("--" + key.replace("_", "-"), type=type(val) if val is not None else str,
                            default=None)
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    case = dict(DEFAULTS)
    if args.input:
        case = load_case(args.input)
    case = merge_args(case, args)

    try:
        res = compute(case)
    except ValueError as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(render(res, case))
    return 0


if __name__ == "__main__":
    sys.exit(main())
