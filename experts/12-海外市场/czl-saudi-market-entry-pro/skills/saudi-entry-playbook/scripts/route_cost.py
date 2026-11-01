#!/usr/bin/env python3
"""G2 路径三年账与综合比选。

输入全部由使用者显式提供，脚本不内置任何国家费率、不猜成本。
只做同一口径下的可比计算：净现值、回收期、控制力、风险调整综合分。

用法：
    python route_cost.py --input routes.json
    python route_cost.py --input routes.json --format md
"""

import argparse
import json
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

DEFAULT_ASSUMPTIONS = {
    "horizon_years": 3,
    "discount_rate": 0.12,
    "cost_inflation": 0.03,
}

WEIGHTS = {"npv": 0.60, "control": 0.25, "risk": 0.15}


def _num(route, key, default=0.0):
    val = route.get(key, default)
    if val is None:
        return default
    if not isinstance(val, (int, float)):
        raise ValueError(f"字段 {key} 必须为数字，收到 {val!r}")
    return float(val)


def compute_route(route, assumptions):
    horizon = int(assumptions["horizon_years"])
    rate = float(assumptions["discount_rate"])
    infl = float(assumptions["cost_inflation"])

    setup = _num(route, "setup_cost_sar")
    months = max(1, int(_num(route, "months_to_operate", 1)))
    control = min(5.0, max(1.0, _num(route, "control_score", 3)))
    risk = min(5.0, max(1.0, _num(route, "risk_score", 3)))
    fixed = _num(route, "fixed_cost_year_sar")
    margin = _num(route, "gross_margin_pct")
    y1_rev = _num(route, "year1_revenue_sar")
    growth = _num(route, "revenue_growth_pct")
    tax = _num(route, "effective_tax_pct")
    commission = _num(route, "channel_commission_pct")

    if margin > 1:
        raise ValueError(f"{route.get('name')}: gross_margin_pct 应为小数（0.32 表示 32%）")
    if tax > 1:
        raise ValueError(f"{route.get('name')}: effective_tax_pct 应为小数")
    if commission > 1:
        raise ValueError(f"{route.get('name')}: channel_commission_pct 应为小数")

    year1_factor = max(0.0, (12 - (months - 1)) / 12.0)
    rows = []
    cumulative = 0.0
    npv = 0.0
    payback_month = None

    for y in range(1, horizon + 1):
        factor = year1_factor if y == 1 else 1.0
        revenue = y1_rev * ((1 + growth) ** (y - 1)) * factor
        gross = revenue * margin
        channel = revenue * commission
        cost_fixed = fixed * ((1 + infl) ** (y - 1)) * factor
        ebit = gross - channel - cost_fixed
        tax_amt = max(0.0, ebit) * tax
        net = ebit - tax_amt
        cash = net - (setup if y == 1 else 0.0)
        cumulative += cash
        npv += cash / ((1 + rate) ** y)

        if payback_month is None and y == 1 and cumulative >= 0:
            payback_month = months
        elif payback_month is None and y > 1 and cumulative >= 0:
            prev = cumulative - cash
            frac = 0.0 if cash == 0 else (0 - prev) / cash
            payback_month = (y - 1) * 12 + int(round(frac * 12))

        rows.append(
            {
                "year": y,
                "revenue": round(revenue, 2),
                "gross_profit": round(gross, 2),
                "channel_cost": round(channel, 2),
                "fixed_cost": round(cost_fixed, 2),
                "ebit": round(ebit, 2),
                "tax": round(tax_amt, 2),
                "net": round(net, 2),
                "cash_flow": round(cash, 2),
                "cumulative": round(cumulative, 2),
            }
        )

    return {
        "name": route.get("name", "unnamed"),
        "years": rows,
        "npv": round(npv, 2),
        "cumulative": round(cumulative, 2),
        "payback_month": payback_month,
        "control_score": control,
        "risk_score": risk,
        "year1_operating_factor": round(year1_factor, 4),
    }


def rank(results):
    if not results:
        return results
    npvs = [r["npv"] for r in results]
    lo, hi = min(npvs), max(npvs)
    span = hi - lo

    for r in results:
        npv_norm = 1.0 if span == 0 else (r["npv"] - lo) / span
        control_norm = (r["control_score"] - 1) / 4.0
        risk_norm = 1.0 - (r["risk_score"] - 1) / 4.0
        r["composite"] = round(
            WEIGHTS["npv"] * npv_norm
            + WEIGHTS["control"] * control_norm
            + WEIGHTS["risk"] * risk_norm,
            4,
        )
    return sorted(results, key=lambda r: r["composite"], reverse=True)


def analyze(payload):
    assumptions = dict(DEFAULT_ASSUMPTIONS)
    assumptions.update(payload.get("assumptions") or {})
    routes = payload.get("routes") or []
    if not routes:
        raise ValueError("routes 不能为空")

    results = [compute_route(r, assumptions) for r in routes]
    ranked = rank(results)
    best = ranked[0]
    runner = ranked[1] if len(ranked) > 1 else None
    return {
        "assumptions": assumptions,
        "weights": WEIGHTS,
        "ranking": [
            {
                "rank": i + 1,
                "name": r["name"],
                "npv": r["npv"],
                "cumulative": r["cumulative"],
                "payback_month": r["payback_month"],
                "control_score": r["control_score"],
                "risk_score": r["risk_score"],
                "composite": r["composite"],
            }
            for i, r in enumerate(ranked)
        ],
        "detail": ranked,
        "recommendation": {
            "primary": best["name"],
            "alternate": runner["name"] if runner else None,
            "note": "综合分仅用于同一口径下的相对比较，不能替代对许可与合规的独立判断。",
        },
    }


def to_markdown(result):
    a = result["assumptions"]
    lines = [
        "## 路径比选（三年账）",
        "",
        f"- 计算期：{a['horizon_years']} 年；折现率：{a['discount_rate']:.0%}；"
        f"成本年增：{a['cost_inflation']:.1%}",
        f"- 权重：净现值 {WEIGHTS['npv']:.0%} / 控制力 {WEIGHTS['control']:.0%} / 风险 {WEIGHTS['risk']:.0%}",
        "",
        "| 排名 | 路径 | 三年净现值 | 三年累计 | 回收月 | 控制力 | 风险 | 综合分 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in result["ranking"]:
        payback = r["payback_month"] if r["payback_month"] is not None else "期内未回收"
        lines.append(
            f"| {r['rank']} | {r['name']} | {r['npv']:,.0f} | {r['cumulative']:,.0f} | "
            f"{payback} | {r['control_score']:.0f} | {r['risk_score']:.0f} | {r['composite']:.3f} |"
        )
    lines += ["", f"**推荐**：{result['recommendation']['primary']}"]
    if result["recommendation"]["alternate"]:
        lines.append(f"**备选**：{result['recommendation']['alternate']}")
    lines += ["", f"> {result['recommendation']['note']}"]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="G2 路径三年账")
    ap.add_argument("--input", required=True)
    ap.add_argument("--format", choices=["json", "md"], default="json")
    args = ap.parse_args()

    try:
        with open(args.input, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        result = analyze(payload)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1

    if args.format == "md":
        print(to_markdown(result))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
