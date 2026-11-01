#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sku_margin.py - 单品/单链接成本瀑布与盈亏测算（纯标准库）。

三个子命令
----------
ledger      一条链接的完整成本瀑布：单均贡献毛利、保本 ROI、保本价、盈亏平衡单量
sensitivity 退货率敏感性表 + 最大可承受退货率
batch       多条链接一起算，按单均贡献毛利排序，标出亏损款

金额单位统一为元，比例统一为小数（0.05 表示 5%）。

退出码：0 = 全部健康；1 = 存在亏损或不可承受项；2 = 输入错误。
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys

EPS = 1e-9


# ---------------------------------------------------------------- 成本模型


class Sku:
    """一条链接的全部参数。所有 per-order 成本按"发货订单"计。"""

    def __init__(self, **kw):
        self.name = kw.get("name") or "未命名链接"
        self.price = float(kw["price"])                 # 成交价（买家实付，不含运费）
        self.cost = float(kw["cost"])                   # 商品成本（含到仓/头程）
        self.ship = float(kw.get("ship", 0))            # 发货运费
        self.pack = float(kw.get("pack", 0))            # 包装耗材
        self.commission = float(kw.get("commission", 0))  # 平台佣金率
        self.payment = float(kw.get("payment", 0))      # 支付手续费率
        self.tax = float(kw.get("tax", 0))              # 税费率（按收入计）
        self.refund = float(kw.get("refund", 0))        # 退货率
        self.return_ship = float(kw.get("return_ship", 0))      # 退货回程运费（按退货单）
        self.return_handling = float(kw.get("return_handling", 0))  # 退货质检/折损处理费（按退货单）
        self.restock = float(kw.get("restock", 1.0))    # 退货可二次销售比例，1 = 全部可再卖
        self.ad_ratio = float(kw.get("ad_ratio", 0))    # 广告费占成交额比例
        self.fixed = float(kw.get("fixed", 0))          # 期间固定费用（人工/软件/仓储月租）
        self.orders = int(kw.get("orders", 100))        # 测算基准单量

    # --- 逐层成本（按 orders 单基准）

    def lines(self):
        n = self.orders
        r = self.refund
        sold = n * (1 - r)
        revenue = sold * self.price
        cogs = sold * self.cost + n * r * (1 - self.restock) * self.cost
        pack = n * self.pack
        outbound = n * self.ship
        back_ship = n * r * self.return_ship
        back_handling = n * r * self.return_handling
        commission = revenue * self.commission
        payment = revenue * self.payment
        tax = revenue * self.tax
        ad = revenue * self.ad_ratio
        non_ad = cogs + pack + outbound + back_ship + back_handling + commission + payment + tax
        contribution = revenue - non_ad - ad
        return {
            "orders": n,
            "sold_orders": sold,
            "revenue": revenue,
            "cogs": cogs,
            "pack": pack,
            "outbound": outbound,
            "back_ship": back_ship,
            "back_handling": back_handling,
            "commission": commission,
            "payment": payment,
            "tax": tax,
            "ad": ad,
            "non_ad_cost": non_ad,
            "contribution": contribution,
        }

    # --- 派生指标

    def metrics(self):
        L = self.lines()
        n = L["orders"]
        rev = L["revenue"]
        contrib = L["contribution"]
        per_order = contrib / n if n else 0.0
        gross_margin = (rev - L["non_ad_cost"]) / rev if rev > EPS else 0.0   # 不含广告毛利率
        net_margin = contrib / rev if rev > EPS else 0.0
        ad_ceiling = rev - L["non_ad_cost"]                                   # 广告费上限（贡献归零）
        be_roi = (rev / ad_ceiling) if ad_ceiling > EPS else None
        actual_roi = (1 / self.ad_ratio) if self.ad_ratio > EPS else None
        be_price = self._breakeven_price()
        be_orders = (self.fixed / per_order) if per_order > EPS else None
        critical_refund = self._critical_refund()
        return {
            "name": self.name,
            "price": self.price,
            "refund": self.refund,
            "per_order_contribution": per_order,
            "gross_margin_excl_ad": gross_margin,
            "net_margin": net_margin,
            "ad_ceiling_total": ad_ceiling,
            "breakeven_roi": be_roi,
            "actual_roi": actual_roi,
            "breakeven_price": be_price,
            "fixed": self.fixed,
            "breakeven_orders": be_orders,
            "critical_refund": critical_refund,
            "lines": L,
        }

    def _breakeven_price(self):
        """不含广告、贡献归零时的成交价。"""
        n = self.orders
        r = self.refund
        sold = n * (1 - r)
        if sold <= EPS:
            return None
        # 与价格无关的成本
        fixed_cost = (
            sold * self.cost
            + n * r * (1 - self.restock) * self.cost
            + n * self.pack
            + n * self.ship
            + n * r * self.return_ship
            + n * r * self.return_handling
        )
        rate = 1 - self.commission - self.payment - self.tax - self.ad_ratio
        if rate <= EPS:
            return None
        return fixed_cost / (sold * rate)

    def _critical_refund(self):
        """在现价与现广告比下，贡献刚好归零的退货率。线性求解。"""
        n = self.orders
        p, c = self.price, self.cost
        # contribution(r) = a*r + b
        const = (
            n * p
            - n * c
            - n * self.pack
            - n * self.ship
            - n * p * (self.commission + self.payment + self.tax + self.ad_ratio)
        )
        coef = (
            -n * p
            + n * c
            - n * (1 - self.restock) * c
            - n * self.return_ship
            - n * self.return_handling
            + n * p * (self.commission + self.payment + self.tax + self.ad_ratio)
        )
        if abs(coef) < EPS:
            return None if const > 0 else 0.0
        r = -const / coef
        if r < 0 or r > 1:
            return None if coef > 0 else max(0.0, min(1.0, r))
        return r

    def verdict(self):
        per_order = self.metrics()["per_order_contribution"]
        if per_order < -EPS:
            return "亏损", "单均贡献毛利为负，卖得越多亏得越多"
        rev_per_order = self.price * (1 - self.refund)
        if rev_per_order > EPS and per_order / rev_per_order < 0.08:
            return "薄利", "单均贡献毛利占净收入不足 8%，抗不住退货或广告波动"
        return "健康", "单均贡献毛利为正且有缓冲"


# ---------------------------------------------------------------- 输出


def _money(x):
    if x is None:
        return "—"
    if abs(x) < 0.005:
        x = 0.0
    return f"{x:,.2f}"


def _pct(x):
    return "—" if x is None else f"{x * 100:.1f}%"


def print_ledger(m):
    L = m["lines"]
    print(f"## 单链接账本：{m['name']}")
    print(f"基准：{L['orders']} 单发货 / 有效成交 {L['sold_orders']:.1f} 单 / 退货率 {_pct(m['refund'])}")
    print()
    print("| 层 | 金额（元） | 占成交额 |")
    print("|---|---:|---:|")
    rev = L["revenue"] if L["revenue"] > EPS else 1.0
    rows = [
        ("成交额（净成交，已扣退款）", L["revenue"]),
        ("商品成本（含退货不能二次销售的部分）", -L["cogs"]),
        ("包装耗材", -L["pack"]),
        ("发货运费", -L["outbound"]),
        ("退货回程运费", -L["back_ship"]),
        ("退货质检/折损", -L["back_handling"]),
        ("平台佣金", -L["commission"]),
        ("支付手续费", -L["payment"]),
        ("税费", -L["tax"]),
        ("广告费", -L["ad"]),
        ("单均贡献毛利", L["contribution"]),
    ]
    for label, val in rows:
        print(f"| {label} | {_money(val)} | {_pct(val / rev)} |")
    print()
    print("### 三个生死数")
    print(f"- 单均贡献毛利：{_money(m['per_order_contribution'])} 元/单（口径：{L['orders']} 单发货均摊，已扣广告）")
    print(f"- 不含广告毛利率：{_pct(m['gross_margin_excl_ad'])}（售价口径，已含运费与退货损耗）")
    if m["breakeven_roi"] is None:
        print("- 保本 ROI：不成立 —— 不含广告的毛利已经为负，任何投放都放大亏损")
    else:
        print(f"- 保本 ROI：{m['breakeven_roi']:.2f}（广告 ROI 低于此值即亏）")
    if m["actual_roi"] is not None:
        gap = m["actual_roi"] - m["breakeven_roi"] if m["breakeven_roi"] else None
        print(f"- 当前投放 ROI：{m['actual_roi']:.2f}" + (f"，距保本线 {gap:+.2f}" if gap is not None else ""))
    print(f"- 保本成交价（不含广告）：{_money(m['breakeven_price'])} 元")
    if m["fixed"] > 0:
        if m["breakeven_orders"] is None:
            print(f"- 盈亏平衡单量：不存在 —— 单均贡献毛利不为正，固定费用 {_money(m['fixed'])} 元无法覆盖")
        else:
            print(f"- 盈亏平衡单量：{m['breakeven_orders']:.0f} 单/期（固定费用 {_money(m['fixed'])} 元 ÷ 单均贡献毛利）")
    if m["critical_refund"] is not None:
        print(f"- 最大可承受退货率：{_pct(m['critical_refund'])}（超过即亏）")
    print()


def print_sensitivity(sku):
    m = sku.metrics()
    base = sku.refund
    print("## 退货率敏感性")
    print("| 退货率 | 单均贡献毛利 | 毛利率 | 判定 |")
    print("|---:|---:|---:|---|")
    worst = None
    for i in range(0, 11):
        r = i / 20.0
        trial = Sku(**{**sku.__dict__, "refund": r})
        mt = trial.metrics()
        mark = " ←当前" if abs(r - base) < 1e-9 else ""
        flag = "亏损" if mt["per_order_contribution"] < -EPS else ("薄利" if mt["net_margin"] < 0.08 else "健康")
        print(f"| {_pct(r)}{mark} | {_money(mt['per_order_contribution'])} | {_pct(mt['net_margin'])} | {flag} |")
        if worst is None and mt["per_order_contribution"] < -EPS:
            worst = r
    print()
    if m["critical_refund"] is not None:
        print(f"临界退货率：{_pct(m['critical_refund'])}。当前 {_pct(base)}，余量 {_pct(m['critical_refund'] - base)}。")
    else:
        print("临界退货率：在 0–100% 区间内不存在（当前结构下退货率不是致命项）。")
    if worst is not None:
        print(f"从 {_pct(worst)} 起转亏。")


def load_batch(path):
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise ValueError("CSV 无表头")
        need = {"sku", "price", "cost", "ship", "refund"}
        missing = need - set(reader.fieldnames)
        if missing:
            raise ValueError("缺少必需列：" + ", ".join(sorted(missing)))
        for raw in reader:
            kw = {
                "name": raw["sku"],
                "price": raw["price"],
                "cost": raw["cost"],
                "ship": raw["ship"],
                "refund": raw["refund"],
                "pack": raw.get("pack") or 0,
                "commission": raw.get("commission") or 0,
                "payment": raw.get("payment") or 0,
                "tax": raw.get("tax") or 0,
                "return_ship": raw.get("return_ship") or 0,
                "return_handling": raw.get("return_handling") or 0,
                "restock": raw.get("restock") or 1.0,
                "ad_ratio": raw.get("ad_ratio") or 0,
                "orders": raw.get("orders") or 100,
            }
            rows.append(Sku(**kw))
    return rows


# ---------------------------------------------------------------- 入口


def build_from_args(a):
    return Sku(
        name=a.name,
        price=a.price,
        cost=a.cost,
        ship=a.ship,
        pack=a.pack,
        commission=a.commission,
        payment=a.payment,
        tax=a.tax,
        refund=a.refund,
        return_ship=a.return_ship,
        return_handling=a.return_handling,
        restock=a.restock,
        ad_ratio=a.ad_ratio,
        fixed=a.fixed,
        orders=a.orders,
    )


def add_common(p):
    p.add_argument("--name", default="未命名链接")
    p.add_argument("--price", type=float, required=True, help="成交价，元")
    p.add_argument("--cost", type=float, required=True, help="商品成本（含到仓），元")
    p.add_argument("--ship", type=float, default=0, help="发货运费，元/单")
    p.add_argument("--pack", type=float, default=0, help="包装耗材，元/单")
    p.add_argument("--commission", type=float, default=0, help="平台佣金率，0.05=5%%")
    p.add_argument("--payment", type=float, default=0, help="支付手续费率")
    p.add_argument("--tax", type=float, default=0, help="税费率（按收入）")
    p.add_argument("--refund", type=float, default=0, help="退货率")
    p.add_argument("--return-ship", dest="return_ship", type=float, default=0, help="退货回程运费，元/退货单")
    p.add_argument("--return-handling", dest="return_handling", type=float, default=0, help="退货质检折损，元/退货单")
    p.add_argument("--restock", type=float, default=1.0, help="退货可二次销售比例")
    p.add_argument("--ad-ratio", dest="ad_ratio", type=float, default=0, help="广告费占成交额比例")
    p.add_argument("--fixed", type=float, default=0, help="期间固定费用，元")
    p.add_argument("--orders", type=int, default=100, help="测算基准单量")
    p.add_argument("--json", action="store_true")


def main(argv=None):
    ap = argparse.ArgumentParser(description="单品成本瀑布与盈亏测算")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("ledger", help="单链接账本")
    add_common(p1)

    p2 = sub.add_parser("sensitivity", help="退货率敏感性")
    add_common(p2)

    p3 = sub.add_parser("batch", help="多条链接批量测算")
    p3.add_argument("csv")
    p3.add_argument("--fixed", type=float, default=0)
    p3.add_argument("--json", action="store_true")

    a = ap.parse_args(argv)

    try:
        if a.cmd in ("ledger", "sensitivity"):
            for k in ("price", "cost", "ship", "pack", "commission", "payment", "tax",
                      "refund", "return_ship", "return_handling", "restock", "ad_ratio"):
                v = getattr(a, k)
                if v < 0:
                    print(f"输入错误：--{k.replace('_', '-')} 不能为负", file=sys.stderr)
                    return 2
            if not (0 <= a.refund <= 1):
                print("输入错误：--refund 应在 0–1 之间", file=sys.stderr)
                return 2
            for k in ("commission", "payment", "tax", "restock"):
                if getattr(a, k) > 1:
                    print(f"输入错误：--{k.replace('_', '-')} 是比例，不能大于 1", file=sys.stderr)
                    return 2
            if a.price <= 0 or a.orders <= 0:
                print("输入错误：--price 与 --orders 必须为正", file=sys.stderr)
                return 2
            sku = build_from_args(a)
            m = sku.metrics()
            if a.cmd == "ledger":
                if a.json:
                    print(json.dumps(m, ensure_ascii=False, indent=2))
                else:
                    print_ledger(m)
                    verdict, note = sku.verdict()
                    print(f"判定：{verdict} —— {note}")
            else:
                if a.json:
                    print(json.dumps(m, ensure_ascii=False, indent=2))
                else:
                    print_sensitivity(sku)
                    verdict, note = sku.verdict()
                    print(f"\n判定：{verdict} —— {note}")
            return 1 if m["per_order_contribution"] < -EPS else 0

        if a.cmd == "batch":
            try:
                rows = load_batch(a.csv)
            except FileNotFoundError:
                print(f"输入错误：找不到文件 {a.csv}", file=sys.stderr)
                return 2
            except ValueError as exc:
                print(f"输入错误：{exc}", file=sys.stderr)
                return 2
            out = []
            for sku in rows:
                sku.fixed = a.fixed
                mt = sku.metrics()
                v, _note = sku.verdict()
                out.append({
                    "sku": mt["name"],
                    "price": mt["price"],
                    "refund": mt["refund"],
                    "per_order_contribution": round(mt["per_order_contribution"], 2),
                    "net_margin": round(mt["net_margin"], 4),
                    "breakeven_roi": None if mt["breakeven_roi"] is None else round(mt["breakeven_roi"], 2),
                    "breakeven_price": None if mt["breakeven_price"] is None else round(mt["breakeven_price"], 2),
                    "verdict": v,
                })
            out.sort(key=lambda x: x["per_order_contribution"], reverse=True)
            if a.json:
                print(json.dumps({"skus": out}, ensure_ascii=False, indent=2))
            else:
                print("## 链接账本汇总（按单均贡献毛利排序）")
                print("| 链接 | 售价 | 退货率 | 单均贡献毛利 | 净利率 | 保本 ROI | 保本价 | 判定 |")
                print("|---|---:|---:|---:|---:|---:|---:|---|")
                for row in out:
                    roi = "—" if row["breakeven_roi"] is None else f"{row['breakeven_roi']:.2f}"
                    print(
                        f"| {row['sku']} | {_money(row['price'])} | {_pct(row['refund'])} | "
                        f"{_money(row['per_order_contribution'])} | {_pct(row['net_margin'])} | "
                        f"{roi} | {_money(row['breakeven_price'])} | {row['verdict']} |"
                    )
                losers = [r for r in out if r["verdict"] == "亏损"]
                thin = [r for r in out if r["verdict"] == "薄利"]
                print()
                print(f"合计 {len(out)} 条：健康 {len(out) - len(losers) - len(thin)}，薄利 {len(thin)}，亏损 {len(losers)}。")
                if losers:
                    print("先处理亏损款：" + "、".join(r["sku"] for r in losers))
            return 1 if any(r["verdict"] == "亏损" for r in out) else 0

    except (TypeError, ValueError) as exc:
        print(f"输入错误：{exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
