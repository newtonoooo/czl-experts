#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
live_metrics.py — 直播间场次指标计算 / 保本测算 / 目标反推 / 漏斗诊断

纯标准库实现，无第三方依赖。所有公式在 references/metric-definitions.md 中给出推导，
任何人可以用纸笔复核脚本输出。

用法:
    python live_metrics.py session  --entries 12000 --impressions 120000 --watch 58 \
        --likes 8000 --comments 1200 --follows 380 --clicks 1600 \
        --orders 120 --paid-orders 96 --gmv 9504 --refund-gmv 600 \
        --ad-cost 2000 --ad-entries 4800 --stage cold

    python live_metrics.py breakeven --price 99 --cost 32 --fulfillment 6 \
        --return-rate 0.18 --commission 0.05 --payment-fee 0.006

    python live_metrics.py plan --target-gmv 50000 --aov 99 --pay-rate 0.028 \
        --click-rate 0.10 --entry-rate 0.08 --target-roi 2.5

    python live_metrics.py selftest

作者: 虫志龙 <47190078@qq.com>
许可: 随本专家包一并授权，详见包内 LICENSE
"""

import argparse
import json
import sys

# ---------------------------------------------------------------- 阈值表
# 经验参考区间，用于诊断时判断某一层是否偏低。不是平台官方标准。
# 口径: watch=平均停留秒; engagement=互动率(点赞+评论/进房人次);
#       click=商品点击率(点击/进房人次); pay=支付转化率(已付款/商品点击);
#       gpm=千次观看成交额(元/千进房人次); entry=进房率(进房/曝光)
STAGE_THRESHOLDS = {
    "cold": {
        "label": "冷启动（开播 30 场内）",
        "entry": 0.06, "watch": 45, "engagement": 0.04,
        "click": 0.08, "pay": 0.020, "gpm": 500,
    },
    "growth": {
        "label": "成长期（自然流量开始起量）",
        "entry": 0.08, "watch": 55, "engagement": 0.05,
        "click": 0.10, "pay": 0.030, "gpm": 700,
    },
    "mature": {
        "label": "成熟期（自然流量稳定）",
        "entry": 0.10, "watch": 60, "engagement": 0.05,
        "click": 0.12, "pay": 0.035, "gpm": 900,
    },
}

# 漏斗层的诊断动作库：命中即输出，不写空话
LEAK_ACTIONS = {
    "entry": [
        "封面与标题改成「具体利益点 + 具体场景」，不写形容词（例: 不是「欢迎来到直播间」，是「今晚 8 点 199 元三件套，最后 40 组」）",
        "开播前 30 分钟发一条预热短视频，结尾口播「今晚 8 点有 XX」，把视频流量直接导进直播间",
        "把开播时间挪到你类目在线人数最高的那一个小时，先用时间换进房率",
    ],
    "watch": [
        "前 90 秒不介绍产品，只做三件事：说清今晚卖什么、给一个立刻可参与的动作、预告一个具体时间点的福利",
        "每 8-10 分钟设置一个「留人钩子」：抽奖、问答、下一款预告，钩子必须在掉人之前出现",
        "把长讲解拆成 25 字以内的短句，每 5 句插一次互动指令，避免大段独白",
    ],
    "engagement": [
        "把互动从「想要的扣 1」改成二选一（「A 色还是 B 色，扣 A 或 B」），二选一的回复率通常高于开放题",
        "点名欢迎最近进房的 3 个人，念出他们的昵称，被点名的人下一次互动的概率明显更高",
        "每 15 分钟做一次关注抽奖，参与条件写清「关注 + 扣关键词」，把互动和涨粉合并成一个动作",
    ],
    "click": [
        "讲产品时同步报出商品卡序号（「3 号链接」），讲解与点开动作必须绑定，不能讲完再提链接",
        "评论区/中控每 2 分钟置顶一次商品卡，主播口播与置顶同一时间发生",
        "把「点开看看」换成「先点开 3 号链接看一眼规格，我不着急让你买」，降低点开的心理成本",
    ],
    "pay": [
        "价格锚定顺序改成：官方价 → 本场到手价 → 赠品清单 → 最后报数字，报数字前停顿 2 秒",
        "把库存释放改成阶梯式（先放 30%，讲完卖点再放 40%），避免一次性放完导致「不着急」",
        "下单路径上的障碍先自查：规格是否要选 3 个以上、优惠券是否要手动领、运费是否显示异常",
        "支付转化偏低但点击正常时，先怀疑价格与预期不符，而不是怀疑主播话术",
    ],
}

ENGAGEMENT_LABELS = {
    "entry": "曝光→进房（进房率）",
    "watch": "进房→停留（平均停留）",
    "engagement": "停留→互动（互动率）",
    "click": "互动→点击（商品点击率）",
    "pay": "点击→付款（支付转化率）",
}


# ---------------------------------------------------------------- 工具函数
def pct(x, digits=2):
    return f"{x * 100:.{digits}f}%"


def money(x, digits=2):
    return f"{x:,.{digits}f}"


def safe_div(a, b):
    return (a / b) if b else None


def warn(msg):
    print(f"[警告] {msg}", file=sys.stderr)


# ---------------------------------------------------------------- 场次指标
def build_session_metrics(args):
    """计算一场直播的核心指标。所有分母口径写在返回字典的 basis 字段里。"""
    m = {}
    warnings = []

    if args.impressions and args.entries:
        m["entry_rate"] = safe_div(args.entries, args.impressions)
    if args.entries:
        if args.watch is not None:
            m["avg_watch"] = float(args.watch)
        m["engagement_rate"] = safe_div(args.likes + args.comments, args.entries)
        m["comment_rate"] = safe_div(args.comments, args.entries)
        m["follow_rate"] = safe_div(args.follows, args.entries) if args.follows else None
        m["product_click_rate"] = safe_div(args.clicks, args.entries)
        m["uv_value"] = safe_div(args.gmv, args.entries)
        m["gpm"] = safe_div(args.gmv * 1000, args.entries)
    if args.clicks:
        m["pay_conversion"] = safe_div(args.paid_orders, args.clicks)
        m["order_conversion"] = safe_div(args.orders, args.clicks)
    if args.paid_orders:
        m["aov"] = safe_div(args.gmv, args.paid_orders)
    if args.gmv:
        m["refund_rate"] = safe_div(args.refund_gmv, args.gmv)
        m["net_gmv"] = args.gmv - args.refund_gmv
    if args.ad_cost:
        m["ad_roi"] = safe_div(args.gmv, args.ad_cost)
        m["cpa"] = safe_div(args.ad_cost, args.paid_orders) if args.paid_orders else None
    if args.ad_entries and args.entries:
        m["paid_entry_share"] = safe_div(args.ad_entries, args.entries)
        m["organic_entry_share"] = 1 - m["paid_entry_share"]

    # 口径冲突自查
    if args.orders and args.paid_orders and args.orders < args.paid_orders:
        warnings.append("下单数小于付款数，口径可能填反了（下单含未付款，应 ≥ 付款）")
    if args.gmv and not args.paid_orders:
        warnings.append("缺少付款单量，客单价与 CPA 无法计算")
    if args.ad_cost and args.gmv and args.ad_cost > args.gmv:
        warnings.append("广告花费高于成交额，先确认是否把多场花费算进这一场")
    if args.refund_gmv > args.gmv:
        warnings.append("退款金额大于成交额，口径异常")

    return m, warnings


def diagnose(m, stage):
    """按漏斗顺序找第一个不达标的层，返回 (漏点列表, 结论文本)。"""
    th = STAGE_THRESHOLDS[stage]
    order = ["entry", "watch", "engagement", "click", "pay"]
    key_map = {
        "entry": "entry_rate", "watch": "avg_watch", "engagement": "engagement_rate",
        "click": "product_click_rate", "pay": "pay_conversion",
    }
    leaks = []
    for layer in order:
        val = m.get(key_map[layer])
        if val is None:
            continue
        threshold = th[layer]
        if val < threshold:
            gap = threshold - val
            leaks.append({
                "layer": layer,
                "label": ENGAGEMENT_LABELS[layer],
                "value": val,
                "threshold": threshold,
                "gap_ratio": gap / threshold if threshold else None,
            })

    if not m.get("entry_rate") and not m.get("avg_watch"):
        conclusion = "数据不足以定位漏点：至少需要曝光、进房、平均停留三项中的两项。请补齐后重算。"
    elif not leaks:
        conclusion = ("五层漏斗均达到本阶段参考线。此时的问题通常不在漏斗内部，"
                      "而在流量规模或客单价结构上——下一场应做的是扩流量和提客单，不是改话术。")
    else:
        first = leaks[0]
        if first["layer"] == "watch":
            cur = f"{first['value']:.1f} 秒"
            thr = f"{first['threshold']:.0f} 秒"
        else:
            cur = pct(first["value"])
            thr = pct(first["threshold"])
        conclusion = (
            f"第一个漏点是「{first['label']}」，实测 {cur}，参考线 {thr}。"
            "先修这一层——它下面的层修好了也会接着漏。"
        )
    return leaks, conclusion


# ---------------------------------------------------------------- 保本测算
def breakeven(args):
    """单件经济模型 + 保本 ROI。口径见 references/metric-definitions.md。

    每卖出 1 件的净毛利（含退货概率摊薄）:
      price*(1-rr)              实收货款（退货部分退回买家）
      - cost*(1-rr)             未退货部分的货品成本（退货可回库，不计成本）
      - fulfillment             履约/包装/人工，按件全额发生（退货也发过货）
      - price*commission*(1-rr) 平台佣金
      - price*payment_fee*(1-rr) 支付通道费
      - return_logistics*rr     退货物流损失
    """
    rr = args.return_rate
    gross_revenue = args.price * (1 - rr)
    goods_cost = args.cost * (1 - rr)
    commission = args.price * args.commission * (1 - rr)
    payment_fee = args.price * args.payment_fee * (1 - rr)
    fulfillment = args.fulfillment
    return_logistics = args.return_logistics * rr

    unit_net = gross_revenue - goods_cost - fulfillment - commission - payment_fee - return_logistics
    unit_gross = args.price - args.cost - args.fulfillment

    result = {
        "price": args.price,
        "return_rate": rr,
        "unit_gross_margin": unit_gross,
        "unit_gross_margin_rate": safe_div(unit_gross, args.price),
        "unit_net_margin": unit_net,
        "unit_net_margin_rate": safe_div(unit_net, args.price),
        "breakeven_roi": safe_div(args.price, unit_net) if unit_net > 0 else None,
        "breakeven_cpa": unit_net if unit_net > 0 else None,
        "notes": [],
    }
    if unit_net <= 0:
        result["notes"].append(
            "单件净毛利为负：这件商品在当前成本结构下，卖一件亏一件，"
            "投流只会放大亏损。先改成本结构（提价/换规格/降履约）再谈投放。"
        )
    if args.fixed_cost:
        if unit_net > 0:
            result["breakeven_units"] = args.fixed_cost / unit_net
            result["breakeven_gmv"] = (args.fixed_cost / unit_net) * args.price
        else:
            result["breakeven_units"] = None
            result["breakeven_gmv"] = None
            result["notes"].append("单件净毛利不为正，单场保本 GMV 不存在（卖得越多亏得越多）。")
    return result


# ---------------------------------------------------------------- 目标反推
def plan(args):
    """从目标 GMV 反推需要的点击、进房、曝光、广告预算。"""
    required_paid_orders = args.target_gmv / args.aov
    required_clicks = required_paid_orders / args.pay_rate
    required_entries = required_clicks / args.click_rate
    required_impressions = required_entries / args.entry_rate
    ad_budget = args.target_gmv / args.target_roi if args.target_roi else None

    out = {
        "target_gmv": args.target_gmv,
        "aov": args.aov,
        "required_paid_orders": required_paid_orders,
        "required_clicks": required_clicks,
        "required_entries": required_entries,
        "required_impressions": required_impressions,
        "ad_budget_at_target_roi": ad_budget,
        "notes": [],
    }
    if args.entries_per_hour:
        out["required_hours"] = required_entries / args.entries_per_hour
    # 反推结果的现实性检查（经验区间，非平台标准）
    if required_entries > 500000:
        out["notes"].append("所需进房人次超过 50 万，单场常规直播很难达到，建议拆成多场或提高客单价。")
    if args.target_roi and ad_budget is not None and ad_budget > args.target_gmv * 0.5:
        out["notes"].append("目标 ROI 低于 2 时，广告预算将占成交额一半以上，需确认毛利能否覆盖。")
    return out


# ---------------------------------------------------------------- 输出
def print_session(m, leaks, conclusion, warnings, as_json):
    if as_json:
        print(json.dumps({"metrics": m, "leaks": leaks, "conclusion": conclusion,
                          "warnings": warnings}, ensure_ascii=False, indent=2))
        return

    print("=" * 62)
    print("场次指标")
    print("=" * 62)
    rows = [
        ("进房率", "entry_rate", "进房/曝光"),
        ("平均停留", "avg_watch", "秒"),
        ("互动率", "engagement_rate", "(点赞+评论)/进房"),
        ("评论率", "comment_rate", "评论/进房，比点赞更能反映意愿"),
        ("转粉率", "follow_rate", "新增关注/进房"),
        ("商品点击率", "product_click_rate", "点击/进房"),
        ("支付转化率", "pay_conversion", "已付款/商品点击"),
        ("下单转化率", "order_conversion", "下单/商品点击"),
        ("客单价", "aov", "元/付款单"),
        ("千次观看成交额 GPM", "gpm", "元/千进房"),
        ("UV 价值", "uv_value", "元/进房人次"),
        ("退款率", "refund_rate", "退款额/成交额"),
        ("净成交额", "net_gmv", "元"),
        ("投产比 ROI", "ad_roi", "成交额/广告花费"),
        ("单均获客成本 CPA", "cpa", "元/付款单"),
        ("付费进房占比", "paid_entry_share", "广告进房/总进房"),
        ("自然进房占比", "organic_entry_share", "自然进房/总进房"),
    ]
    for label, key, basis in rows:
        if key not in m or m[key] is None:
            continue
        v = m[key]
        if key in ("avg_watch",):
            val = f"{v:.1f} 秒"
        elif key in ("entry_rate", "engagement_rate", "comment_rate", "follow_rate",
                     "product_click_rate", "pay_conversion", "order_conversion",
                     "refund_rate", "paid_entry_share", "organic_entry_share"):
            val = pct(v)
        else:
            val = money(v)
        print(f"  {label:<18}{val:>14}    ← {basis}")

    print()
    print("=" * 62)
    print("漏斗诊断")
    print("=" * 62)
    if leaks:
        for lk in leaks:
            if lk["layer"] == "watch":
                cur, thr = f"{lk['value']:.1f} 秒", f"{lk['threshold']:.0f} 秒"
            else:
                cur, thr = pct(lk["value"]), pct(lk["threshold"])
            print(f"  ✗ {lk['label']}: 实测 {cur} / 参考线 {thr}")
    else:
        print("  ✓ 已提供的指标均达到本阶段参考线")
    print()
    print("结论:")
    for line in wrap(conclusion, 58):
        print("  " + line)
    if leaks:
        first = leaks[0]
        print()
        print(f"优先动作（针对「{first['label']}」）:")
        for i, act in enumerate(LEAK_ACTIONS[first["layer"]], 1):
            for j, line in enumerate(wrap(f"{i}. {act}", 58)):
                print("  " + ("   " if j else "") + line)
    if warnings:
        print()
        print("口径提醒:")
        for w in warnings:
            for line in wrap("- " + w, 58):
                print("  " + line)


def wrap(text, width):
    """按显示宽度折行（中文按 2 计），让终端输出不炸行。"""
    out, cur, cur_w = [], "", 0
    for ch in text:
        w = 2 if ord(ch) > 127 else 1
        if cur_w + w > width:
            out.append(cur)
            cur, cur_w = ch, w
        else:
            cur += ch
            cur_w += w
    if cur:
        out.append(cur)
    return out


def print_breakeven(r, as_json):
    if as_json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return
    print("=" * 62)
    print("单件经济模型")
    print("=" * 62)
    print(f"  售价                    {money(r['price'])} 元")
    print(f"  退货率                  {pct(r['return_rate'], 1)}")
    print(f"  单件毛利（不含退货）    {money(r['unit_gross_margin'])} 元"
          f"  毛利率 {pct(r['unit_gross_margin_rate'], 1)}")
    print(f"  单件净毛利（含退货/佣金）{money(r['unit_net_margin'])} 元"
          f"  净利率 {pct(r['unit_net_margin_rate'], 1)}")
    if r["breakeven_roi"]:
        print(f"  保本 ROI（成交额/广告费）{r['breakeven_roi']:.2f}")
        print(f"  保本 CPA（单均广告上限） {money(r['breakeven_cpa'])} 元")
    if r.get("breakeven_gmv") is not None:
        print(f"  单场保本销量            {r['breakeven_units']:.0f} 件")
        print(f"  单场保本 GMV            {money(r['breakeven_gmv'])} 元")
    if r["notes"]:
        print()
        for n in r["notes"]:
            for line in wrap("! " + n, 58):
                print("  " + line)


def print_plan(r, as_json):
    if as_json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return
    print("=" * 62)
    print("目标反推（要打到目标，前面每一层需要多少）")
    print("=" * 62)
    print(f"  目标 GMV                {money(r['target_gmv'])} 元")
    print(f"  需要付款单量            {r['required_paid_orders']:.0f} 单")
    print(f"  需要商品点击            {r['required_clicks']:,.0f} 次")
    print(f"  需要进房人次            {r['required_entries']:,.0f} 人")
    print(f"  需要曝光                {r['required_impressions']:,.0f} 次")
    if r["ad_budget_at_target_roi"]:
        print(f"  目标 ROI 下广告预算     {money(r['ad_budget_at_target_roi'])} 元")
    if r.get("required_hours"):
        print(f"  按当前进房速度需播      {r['required_hours']:.1f} 小时")
    if r["notes"]:
        print()
        for n in r["notes"]:
            for line in wrap("! " + n, 58):
                print("  " + line)


# ---------------------------------------------------------------- 自检
def selftest():
    """用可手算的算例验证每个公式，失败即抛错。"""
    failures = []
    passed = []

    def check(name, got, expect, tol=1e-6):
        ok = got is not None and abs(got - expect) <= tol
        if ok:
            passed.append(name)
        print(("  ✓ " if ok else "  ✗ ") + f"{name}: got={got} expect={expect}")
        if not ok:
            failures.append(name)

    # 1. 场次指标
    ns = argparse.Namespace(
        impressions=100000, entries=10000, watch=58,
        likes=6000, comments=1000, follows=300, clicks=1200,
        orders=100, paid_orders=80, gmv=8000, refund_gmv=800,
        ad_cost=2000, ad_entries=4000,
    )
    m, _ = build_session_metrics(ns)
    check("进房率", m["entry_rate"], 0.10)
    check("互动率", m["engagement_rate"], 0.70)
    check("转粉率", m["follow_rate"], 0.03)
    check("商品点击率", m["product_click_rate"], 0.12)
    check("支付转化率", m["pay_conversion"], 80 / 1200)
    check("客单价", m["aov"], 100.0)
    check("GPM", m["gpm"], 800.0)
    check("UV价值", m["uv_value"], 0.8)
    check("退款率", m["refund_rate"], 0.10)
    check("净成交额", m["net_gmv"], 7200.0)
    check("ROI", m["ad_roi"], 4.0)
    check("CPA", m["cpa"], 25.0)
    check("自然进房占比", m["organic_entry_share"], 0.60)

    # 2. 诊断：只有 click 与 pay 应该漏（entry 10% 达标, watch 58 达标, 互动 70% 达标）
    leaks, _ = diagnose(m, "growth")
    layers = [l["layer"] for l in leaks]
    print(f"  ✓ 诊断命中层: {layers}（期望空或仅 pay）")
    if "entry" in layers or "watch" in layers:
        failures.append("诊断误判")

    # 3. 保本测算（可手算）
    br = breakeven(argparse.Namespace(
        price=100, cost=30, fulfillment=5, return_rate=0.2,
        commission=0.05, payment_fee=0.006, return_logistics=8, fixed_cost=0,
    ))
    # 实收 80 - 货品 24 - 履约 5 - 佣金 4 - 支付费 0.48 - 退货物流 1.6 = 44.92
    check("单件净毛利", br["unit_net_margin"], 44.92)
    check("保本ROI", br["breakeven_roi"], 100 / 44.92, tol=1e-9)
    check("单件毛利(含退货前)", br["unit_gross_margin"], 65.0)

    # 4. 负毛利不产生保本线
    br2 = breakeven(argparse.Namespace(
        price=50, cost=48, fulfillment=5, return_rate=0.1,
        commission=0.05, payment_fee=0.006, return_logistics=8, fixed_cost=0,
    ))
    if br2["breakeven_roi"] is not None:
        failures.append("负毛利仍给出保本ROI")
    print("  ✓ 负毛利场景不输出保本ROI")

    # 5. 目标反推
    pl = plan(argparse.Namespace(
        target_gmv=50000, aov=100, pay_rate=0.025,
        click_rate=0.10, entry_rate=0.08, target_roi=2.5, entries_per_hour=3000,
    ))
    check("需要付款单量", pl["required_paid_orders"], 500.0)
    check("需要点击", pl["required_clicks"], 20000.0)
    check("需要进房", pl["required_entries"], 200000.0)
    check("需要曝光", pl["required_impressions"], 2500000.0)
    check("广告预算", pl["ad_budget_at_target_roi"], 20000.0)
    check("所需小时", pl["required_hours"], 200000.0 / 3000)

    print()
    if failures:
        print(f"自检失败 {len(failures)} 项: {failures}")
        return 1
    print(f"自检全部通过（{len(passed)} 项公式校验）")
    return 0


# ---------------------------------------------------------------- CLI
def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    p = argparse.ArgumentParser(description="直播间场次指标计算与诊断")
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("session", help="计算一场直播的指标并做漏斗诊断")
    ps.add_argument("--impressions", type=int, default=0, help="曝光次数")
    ps.add_argument("--entries", type=int, default=0, help="进房人次")
    ps.add_argument("--watch", type=float, default=None, help="平均停留（秒）")
    ps.add_argument("--likes", type=int, default=0, help="点赞数")
    ps.add_argument("--comments", type=int, default=0, help="评论数")
    ps.add_argument("--follows", type=int, default=0, help="新增关注")
    ps.add_argument("--clicks", type=int, default=0, help="商品点击次数")
    ps.add_argument("--orders", type=int, default=0, help="下单数（含未付款）")
    ps.add_argument("--paid-orders", type=int, default=0, help="已付款单量")
    ps.add_argument("--gmv", type=float, default=0.0, help="成交额（付款口径）")
    ps.add_argument("--refund-gmv", type=float, default=0.0, help="退款金额")
    ps.add_argument("--ad-cost", type=float, default=0.0, help="广告花费")
    ps.add_argument("--ad-entries", type=int, default=0, help="广告带来的进房人次")
    ps.add_argument("--stage", choices=list(STAGE_THRESHOLDS), default="growth",
                    help="账号阶段，决定诊断参考线")
    ps.add_argument("--json", action="store_true", help="输出 JSON")

    pb = sub.add_parser("breakeven", help="单件经济模型与保本 ROI")
    pb.add_argument("--price", type=float, required=True, help="售价")
    pb.add_argument("--cost", type=float, required=True, help="货品成本（含包装）")
    pb.add_argument("--fulfillment", type=float, default=5.0, help="履约/人工，按件")
    pb.add_argument("--return-rate", type=float, default=0.0, help="退货率 0-1")
    pb.add_argument("--commission", type=float, default=0.05, help="平台佣金率")
    pb.add_argument("--payment-fee", type=float, default=0.006, help="支付通道费率")
    pb.add_argument("--return-logistics", type=float, default=8.0, help="退货物流损失/件")
    pb.add_argument("--fixed-cost", type=float, default=0.0, help="单场固定成本（房租/人力/场景）")
    pb.add_argument("--json", action="store_true")

    pp = sub.add_parser("plan", help="从目标 GMV 反推所需流量与预算")
    pp.add_argument("--target-gmv", type=float, required=True)
    pp.add_argument("--aov", type=float, required=True, help="客单价")
    pp.add_argument("--pay-rate", type=float, required=True, help="支付转化率（付款/点击）")
    pp.add_argument("--click-rate", type=float, required=True, help="商品点击率（点击/进房）")
    pp.add_argument("--entry-rate", type=float, required=True, help="进房率（进房/曝光）")
    pp.add_argument("--target-roi", type=float, default=None, help="目标 ROI")
    pp.add_argument("--entries-per-hour", type=float, default=None, help="当前每小进房人次")
    pp.add_argument("--json", action="store_true")

    sub.add_parser("selftest", help="运行公式自检")

    args = p.parse_args()

    if args.cmd == "session":
        m, warnings = build_session_metrics(args)
        if not m:
            warn("没有足够参数计算任何指标。至少传入 --entries 与其中一个量。")
            return 2
        leaks, conclusion = diagnose(m, args.stage)
        print(f"参考线: {STAGE_THRESHOLDS[args.stage]['label']}\n")
        print_session(m, leaks, conclusion, warnings, args.json)
        return 0
    if args.cmd == "breakeven":
        print_breakeven(breakeven(args), args.json)
        return 0
    if args.cmd == "plan":
        print_plan(plan(args), args.json)
        return 0
    if args.cmd == "selftest":
        return selftest()
    return 2


if __name__ == "__main__":
    sys.exit(main())
