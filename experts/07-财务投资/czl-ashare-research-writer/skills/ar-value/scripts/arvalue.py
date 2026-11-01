#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""估值计算：两阶段 DCF、隐含增长反推、敏感性表（零第三方依赖）。

设计原则：
  1. 参数全部显式传入，脚本不内置任何"合理"假设。
  2. 永续增长率超过 3% 直接拒绝计算——那是把乐观写进公式。
  3. 折现率必须大于永续增长率，否则终端价值无意义。

CLI:
  python arvalue.py dcf --fcf 100 --wacc 9 --growth 12 --years 5 --terminal 2
  python arvalue.py implied --ev 3000 --fcf 100 --wacc 9 --years 5 --terminal 2
  python arvalue.py sens --fcf 100 --wacc 8,9,10 --growth 8,12,16 --years 5 --terminal 2
  python arvalue.py selftest
"""
import argparse
import json
import sys

MAX_TERMINAL = 3.0


class ValueError_(ValueError):
    pass


def _pct(x):
    return float(x) / 100.0


def two_stage_dcf(fcf0, wacc_pct, growth_pct, years, terminal_pct, net_debt=0.0, shares=None):
    """两阶段自由现金流折现。

    fcf0        基期自由现金流（与市值同单位，如亿元）
    wacc_pct    加权平均资本成本（%）
    growth_pct  第一阶段增长率（%）
    years       第一阶段年数
    terminal_pct 永续增长率（%）
    net_debt    净债务（现金为负），用于从企业价值转到股权价值
    shares      股本（亿股），给出则计算每股价值
    """
    wacc, g, gt = _pct(wacc_pct), _pct(growth_pct), _pct(terminal_pct)
    if terminal_pct > MAX_TERMINAL:
        raise ValueError_("永续增长率 %.2f%% 超过上限 %.1f%%，拒绝计算" % (terminal_pct, MAX_TERMINAL))
    if wacc <= gt:
        raise ValueError_("WACC(%.2f%%) 必须大于永续增长率(%.2f%%)" % (wacc_pct, terminal_pct))
    if years < 1:
        raise ValueError_("第一阶段年数至少为 1")
    if fcf0 <= 0:
        raise ValueError_("基期自由现金流为负或零，DCF 不适用，请改用相对估值")

    flows, pv_flows = [], []
    fcf = fcf0
    for t in range(1, years + 1):
        fcf = fcf * (1 + g)
        pv = fcf / ((1 + wacc) ** t)
        flows.append(round(fcf, 4))
        pv_flows.append(round(pv, 4))

    fcf_terminal = flows[-1] * (1 + gt)
    tv = fcf_terminal / (wacc - gt)
    pv_tv = tv / ((1 + wacc) ** years)

    ev = sum(pv_flows) + pv_tv
    equity = ev - net_debt
    out = {
        "method": "two_stage_dcf",
        "assumptions": {
            "fcf0": fcf0, "wacc_pct": wacc_pct, "growth_pct": growth_pct,
            "years": years, "terminal_pct": terminal_pct, "net_debt": net_debt,
        },
        "projected_fcf": flows,
        "pv_explicit": round(sum(pv_flows), 4),
        "terminal_value": round(tv, 4),
        "pv_terminal": round(pv_tv, 4),
        "enterprise_value": round(ev, 4),
        "equity_value": round(equity, 4),
        "tv_share_pct": round(pv_tv / ev * 100, 2) if ev else None,
    }
    if shares:
        out["value_per_share"] = round(equity / shares, 2)
    if out["tv_share_pct"] and out["tv_share_pct"] > 75:
        out["warning"] = "终端价值占比 %.0f%% 过高，结论对永续假设高度敏感" % out["tv_share_pct"]
    return out


def implied_growth(ev, fcf0, wacc_pct, years, terminal_pct, net_debt=0.0, lo=-30.0, hi=80.0):
    """反推当前企业价值隐含的第一阶段增长率（二分法）。

    这一步回答的是"市场现在在假设什么"，比给目标价有用得多。
    """
    if fcf0 <= 0:
        raise ValueError_("基期自由现金流为负，无法反推隐含增长")
    target = ev + net_debt  # EV = 股权价值 + 净债务

    def ev_at(g):
        return two_stage_dcf(fcf0, wacc_pct, g, years, terminal_pct, net_debt=0.0)["enterprise_value"]

    if ev_at(lo) > target:
        return {"solvable": False, "note": "即使增长率为 %.0f%%，模型价值仍高于当前市值，说明当前价格隐含了负增长或存在其他因素（如周期底部、资产价值）。" % lo}
    if ev_at(hi) < target:
        return {"solvable": False, "note": "即使增长率达 %.0f%%，模型价值仍低于当前市值，说明价格隐含了超出模型能力的预期。" % hi}

    for _ in range(80):
        mid = (lo + hi) / 2
        if ev_at(mid) < target:
            lo = mid
        else:
            hi = mid
    g = round((lo + hi) / 2, 2)
    return {
        "solvable": True,
        "implied_growth_pct": g,
        "assumptions": {"wacc_pct": wacc_pct, "years": years, "terminal_pct": terminal_pct, "fcf0": fcf0},
        "reading": "当前价格隐含未来 %d 年自由现金流复合增速约 %.1f%%" % (years, g),
    }


def sensitivity(fcf0, wacc_list, growth_list, years, terminal_pct, net_debt=0.0, shares=None):
    """二维敏感性表：行=增长率，列=WACC。"""
    rows = []
    for g in growth_list:
        row = {"growth_pct": g, "values": []}
        for w in wacc_list:
            try:
                r = two_stage_dcf(fcf0, w, g, years, terminal_pct, net_debt, shares)
                row["values"].append(r.get("value_per_share") or r["equity_value"])
            except ValueError_:
                row["values"].append(None)
        rows.append(row)
    return {
        "columns_wacc_pct": list(wacc_list),
        "rows_growth_pct": rows,
        "unit": "每股价值" if shares else "股权价值",
    }


def _floats(text):
    return [float(x) for x in str(text).split(",") if x.strip()]


def selftest():
    r = two_stage_dcf(100, 9, 12, 5, 2, net_debt=200)
    checks = [
        ("企业价值为正", r["enterprise_value"] > 0),
        ("股权价值小于企业价值", r["equity_value"] < r["enterprise_value"]),
        ("终端价值占比在 0-100", 0 < r["tv_share_pct"] < 100),
        ("五年现金流", len(r["projected_fcf"]) == 5),
    ]
    imp = implied_growth(r["enterprise_value"], 100, 9, 5, 2)
    checks.append(("隐含增长可解", imp.get("solvable") is True))
    checks.append(("隐含增长接近 12%", abs(imp.get("implied_growth_pct", 0) - 12) < 0.5))

    try:
        two_stage_dcf(100, 9, 12, 5, 5)
        checks.append(("拒绝高永续增长", False))
    except ValueError_:
        checks.append(("拒绝高永续增长", True))

    try:
        two_stage_dcf(100, 2, 12, 5, 3)
        checks.append(("拒绝 WACC<=g", False))
    except ValueError_:
        checks.append(("拒绝 WACC<=g", True))

    s = sensitivity(100, [8, 9, 10], [8, 12, 16], 5, 2)
    checks.append(("敏感性 3x3", len(s["rows_growth_pct"]) == 3 and
                   all(len(x["values"]) == 3 for x in s["rows_growth_pct"])))
    checks.append(("增长越高价值越高",
                   s["rows_growth_pct"][2]["values"][1] > s["rows_growth_pct"][0]["values"][1]))

    failed = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print(("  PASS  " if ok else "  FAIL  ") + n)
    print("结果：%d/%d 通过" % (len(checks) - len(failed), len(checks)))
    return 0 if not failed else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="估值计算")
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("dcf")
    d.add_argument("--fcf", type=float, required=True)
    d.add_argument("--wacc", type=float, required=True)
    d.add_argument("--growth", type=float, required=True)
    d.add_argument("--years", type=int, default=5)
    d.add_argument("--terminal", type=float, default=2.0)
    d.add_argument("--net-debt", type=float, default=0.0)
    d.add_argument("--shares", type=float, default=None)

    i = sub.add_parser("implied")
    i.add_argument("--ev", type=float, required=True, help="当前企业价值=总市值+净债务")
    i.add_argument("--fcf", type=float, required=True)
    i.add_argument("--wacc", type=float, required=True)
    i.add_argument("--years", type=int, default=5)
    i.add_argument("--terminal", type=float, default=2.0)

    s = sub.add_parser("sens")
    s.add_argument("--fcf", type=float, required=True)
    s.add_argument("--wacc", required=True, help="逗号分隔，如 8,9,10")
    s.add_argument("--growth", required=True, help="逗号分隔，如 8,12,16")
    s.add_argument("--years", type=int, default=5)
    s.add_argument("--terminal", type=float, default=2.0)
    s.add_argument("--shares", type=float, default=None)

    sub.add_parser("selftest")
    args = ap.parse_args(argv)

    if args.cmd == "selftest":
        return selftest()
    try:
        if args.cmd == "dcf":
            out = two_stage_dcf(args.fcf, args.wacc, args.growth, args.years,
                                args.terminal, args.net_debt, args.shares)
        elif args.cmd == "implied":
            out = implied_growth(args.ev, args.fcf, args.wacc, args.years, args.terminal)
        else:
            out = sensitivity(args.fcf, _floats(args.wacc), _floats(args.growth),
                              args.years, args.terminal, shares=args.shares)
    except ValueError_ as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
