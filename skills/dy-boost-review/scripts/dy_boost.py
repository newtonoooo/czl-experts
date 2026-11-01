#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dy_boost.py — 投放保本测算与直播盈亏平衡

归属：czl-douyin-growth-ops / skills/dy-boost-review
作者：虫志龙 <47190078@qq.com>

解决的问题
----------
"要不要投 DOU+""这场直播卖多少才不亏"——绝大多数人靠感觉答，
结果是投了钱不知道赚没赚，播完不知道亏在哪。

本工具只做一件事：把毛利、退款、转化、消耗摆到一条公式上，
算出三个硬数：**保本 ROAS、保本 CPA、保本 GMV**，再看你手上的
实际数据是过线还是不过线。

用法
----
    python dy_boost.py --demo
    python dy_boost.py ads  --aov 129 --margin 0.4 --refund 0.15 --cpc 0.8 --cvr 0.02 --spend 3000
    python dy_boost.py live --aov 129 --margin 0.4 --refund 0.15 --fixed 3000 --spend 2000 --views 30000
    python dy_boost.py plan --aov 129 --margin 0.4 --refund 0.15 --budgets 1000,3000,5000
"""

import argparse
import json
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

VERSION = "1.0.0"

# 参考口径：DOU+ 常见投放档位约 100 元对应 5000 次播放（CPM ≈ 20 元）。
# 这是经验参考值，不同行业、不同定向差异很大，仅用于反算"需要多少播放"。
REF_CPM = 20.0


def safe_div(a, b):
    return None if not b else a / b


def net_unit_margin(aov, margin, refund):
    """单笔成交净毛利 = 客单价 × 毛利率 × (1 - 退款率)。"""
    return aov * margin * (1 - refund)


def breakeven_roas(margin, refund):
    """保本 ROAS（GMV / 消耗）= 1 / (毛利率 × (1 - 退款率))。"""
    denom = margin * (1 - refund)
    return safe_div(1.0, denom)


def calc_ads(aov, margin, refund, cpc, cvr, spend):
    unit = net_unit_margin(aov, margin, refund)
    cpa = safe_div(cpc, cvr)
    roas_be = breakeven_roas(margin, refund)
    orders_be = safe_div(spend, unit)
    gmv_be = spend * roas_be if roas_be else None

    verdict = None
    gap = None
    if cpa and unit:
        gap = round(unit - cpa, 2)
        if cpa <= unit * 0.8:
            verdict = "有安全垫，可以小步放量"
        elif cpa <= unit:
            verdict = "刚好过线，没有容错，退款率一涨就亏"
        else:
            verdict = "跑不通，先降 CPC 或提转化，别加预算"
    return {
        "mode": "ads",
        "inputs": {"aov": aov, "margin": margin, "refund": refund,
                   "cpc": cpc, "cvr": cvr, "spend": spend},
        "net_unit_margin": round(unit, 2),
        "cpa": round(cpa, 2) if cpa else None,
        "cpa_gap": gap,
        "breakeven_roas": round(roas_be, 2) if roas_be else None,
        "breakeven_orders": round(orders_be, 1) if orders_be else None,
        "breakeven_gmv": round(gmv_be, 2) if gmv_be else None,
        "verdict": verdict,
    }


def calc_live(aov, margin, refund, fixed, spend, views):
    unit = net_unit_margin(aov, margin, refund)
    roas_be = breakeven_roas(margin, refund)
    gmv_be = (fixed + spend) * roas_be if roas_be else None
    orders_be = safe_div(gmv_be, aov)
    gpm_be = safe_div(gmv_be * 1000.0, views) if views else None
    views_be = safe_div(gmv_be * 1000.0, gpm_be) if gpm_be else None

    verdict = None
    if gpm_be:
        if gpm_be <= 300:
            verdict = "保本门槛低，正常发挥能过，重点放在拉停留"
        elif gpm_be <= 800:
            verdict = "保本门槛中等，排品要有利润款托底，福袋别排太密"
        else:
            verdict = "保本门槛偏高，要么提客单、要么压固定成本，别硬播"
    return {
        "mode": "live",
        "inputs": {"aov": aov, "margin": margin, "refund": refund,
                   "fixed": fixed, "spend": spend, "views": views},
        "net_unit_margin": round(unit, 2),
        "breakeven_roas": round(roas_be, 2) if roas_be else None,
        "breakeven_gmv": round(gmv_be, 2) if gmv_be else None,
        "breakeven_orders": round(orders_be, 1) if orders_be else None,
        "breakeven_gpm": round(gpm_be, 2) if gpm_be else None,
        "verdict": verdict,
    }


def calc_plan(aov, margin, refund, budgets):
    unit = net_unit_margin(aov, margin, refund)
    roas_be = breakeven_roas(margin, refund)
    rows = []
    for b in budgets:
        gmv_be = b * roas_be if roas_be else None
        orders = safe_div(gmv_be, aov)
        plays = gmv_be * 1000.0 / REF_CPM if gmv_be else None
        rows.append({
            "budget": b,
            "breakeven_gmv": round(gmv_be, 2) if gmv_be else None,
            "breakeven_orders": round(orders, 1) if orders else None,
            "needed_plays": int(plays) if plays else None,
        })
    return {
        "mode": "plan",
        "inputs": {"aov": aov, "margin": margin, "refund": refund, "budgets": budgets},
        "net_unit_margin": round(unit, 2),
        "breakeven_roas": round(roas_be, 2) if roas_be else None,
        "rows": rows,
        "ref_cpm": REF_CPM,
    }


def fmt_money(v):
    return "—" if v is None else f"{v:,.0f}"


MODE_TITLE = {"ads": "投放测算", "live": "直播保本测算", "plan": "分档预算压力测试"}


def render_md(rep):
    inputs = rep["inputs"]
    lines = [f"# {MODE_TITLE.get(rep['mode'], '测算')}", ""]
    lines.append("## 一、口径")
    lines.append("")
    lines.append(f"- 客单价 {inputs['aov']} 元｜毛利率 {inputs['margin']*100:.0f}%｜退款率 {inputs['refund']*100:.0f}%")
    lines.append(f"- 单笔净毛利 = {inputs['aov']} × {inputs['margin']*100:.0f}% × (1 − {inputs['refund']*100:.0f}%) "
                 f"= **{rep['net_unit_margin']} 元**")
    if rep.get("breakeven_roas"):
        lines.append(f"- 保本 ROAS = 1 ÷ (毛利率 × (1 − 退款率)) = **{rep['breakeven_roas']}**")
    lines.append("")

    if rep["mode"] == "ads":
        lines += ["## 二、投放能不能跑通", ""]
        lines.append("| 项 | 数值 | 含义 |")
        lines.append("|---|---|---|")
        lines.append(f"| 单笔净毛利 | {rep['net_unit_margin']} 元 | 一单最多能拿出这么多钱买流量 |")
        lines.append(f"| 实际 CPA | {rep['cpa']} 元 | CPC {inputs['cpc']} ÷ 转化率 {inputs['cvr']*100:.1f}% |")
        lines.append(f"| 毛利 − CPA | {rep['cpa_gap']} 元 | 负数就是每单在亏 |")
        lines.append(f"| 保本订单数 | {rep['breakeven_orders']} 单 | 消耗 {inputs['spend']} 元打平需要 |")
        lines.append(f"| 保本 GMV | {fmt_money(rep['breakeven_gmv'])} 元 | 同上，按金额算 |")
        lines.append("")
        lines.append(f"**判定：{rep['verdict']}**")
        lines.append("")

    elif rep["mode"] == "live":
        lines += ["## 二、这场直播的保本线", ""]
        lines.append("| 指标 | 数值 | 说明 |")
        lines.append("|---|---|---|")
        lines.append(f"| 保本 GMV | {fmt_money(rep['breakeven_gmv'])} 元 | （固定成本 {inputs['fixed']} + 投流 {inputs['spend']}）× 保本 ROAS |")
        lines.append(f"| 保本订单数 | {rep['breakeven_orders']} 单 | 按客单价 {inputs['aov']} 元折算 |")
        lines.append(f"| 保本 GPM | {rep['breakeven_gpm']} 元 | 每千次观看必须产出这么多 GMV |")
        lines.append("")
        if rep["breakeven_gpm"]:
            lines.append(f"**判定：{rep['verdict']}**")
            lines.append("")
            lines.append(f"换算成人话：这场每进来 1000 个人，必须成交 {rep['breakeven_gpm']:.0f} 元。"
                         f"低于这个数，播得越久亏得越多。")
            lines.append("")

    elif rep["mode"] == "plan":
        lines += ["## 二、分档预算压力测试", ""]
        lines.append("| 预算 | 需要 GMV | 需要订单数 | 需要播放量（按 CPM 参考） |")
        lines.append("|---|---|---|---|")
        for r in rep["rows"]:
            lines.append(f"| {r['budget']} 元 | {fmt_money(r['breakeven_gmv'])} 元 | "
                         f"{r['breakeven_orders']} 单 | 约 {r['needed_plays']:,} 次 |")
        lines.append("")
        lines.append(f"> 播放量按 CPM {rep['ref_cpm']} 元参考值反算（经验值，用于估算量级，不是承诺）。")

    lines.append("")
    lines.append("## 三、这三个数的用法")
    lines.append("")
    lines.append("1. 投放前先用保本 CPA 卡一道：跑不到这个数就不加预算，改素材而不是加钱。")
    lines.append("2. 直播前用保本 GPM 定排品：算出来门槛高，就必须排利润款托底，不能全靠引流款。")
    lines.append("3. 复盘时用保本 ROAS 判生死：低于它，问题在货或转化，不在流量。")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="投放保本测算与直播盈亏平衡")
    sub = ap.add_subparsers(dest="cmd")

    def common(p):
        p.add_argument("--aov", type=float, required=True, help="客单价（元）")
        p.add_argument("--margin", type=float, required=True, help="毛利率，0-1")
        p.add_argument("--refund", type=float, default=0.0, help="退款率，0-1，默认 0")

    p_ads = sub.add_parser("ads", help="付费投放测算")
    common(p_ads)
    p_ads.add_argument("--cpc", type=float, required=True, help="平均点击成本（元）")
    p_ads.add_argument("--cvr", type=float, required=True, help="点击到成交转化率，0-1")
    p_ads.add_argument("--spend", type=float, required=True, help="计划消耗（元）")

    p_live = sub.add_parser("live", help="直播盈亏平衡")
    common(p_live)
    p_live.add_argument("--fixed", type=float, default=0.0, help="单场固定成本（人力、场地、赠品）")
    p_live.add_argument("--spend", type=float, default=0.0, help="单场投流消耗")
    p_live.add_argument("--views", type=float, default=0.0, help="预计观看人次")

    p_plan = sub.add_parser("plan", help="分档预算压力测试")
    common(p_plan)
    p_plan.add_argument("--budgets", default="1000,3000,5000", help="预算档位，逗号分隔")

    ap.add_argument("--format", choices=("md", "json"), default="md")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--version", action="version", version=f"dy_boost {VERSION}")
    args = ap.parse_args()

    if args.demo:
        reps = [
            calc_ads(129, 0.40, 0.15, 0.8, 0.02, 3000),
            calc_live(129, 0.40, 0.15, 3000, 2000, 30000),
            calc_plan(129, 0.40, 0.15, [1000, 3000, 5000]),
        ]
        print("\n\n---\n\n".join(render_md(r) for r in reps))
        return 0

    if not args.cmd:
        ap.print_help()
        return 2

    for name, val in (("margin", args.margin), ("refund", args.refund)):
        if not 0 <= val <= 1:
            print(f"错误：{name} 必须在 0 到 1 之间，当前 {val}", file=sys.stderr)
            return 2

    if args.cmd == "ads":
        rep = calc_ads(args.aov, args.margin, args.refund, args.cpc, args.cvr, args.spend)
    elif args.cmd == "live":
        rep = calc_live(args.aov, args.margin, args.refund, args.fixed, args.spend, args.views)
    else:
        try:
            budgets = [float(x) for x in str(args.budgets).split(",") if x.strip()]
        except ValueError:
            print("错误：--budgets 需要逗号分隔的数字，如 1000,3000,5000", file=sys.stderr)
            return 2
        if not budgets:
            print("错误：--budgets 为空", file=sys.stderr)
            return 2
        rep = calc_plan(args.aov, args.margin, args.refund, budgets)

    out = render_md(rep) if args.format == "md" else json.dumps(rep, ensure_ascii=False, indent=2)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
