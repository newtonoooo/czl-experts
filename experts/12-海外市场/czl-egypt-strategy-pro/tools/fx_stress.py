#!/usr/bin/env python3
"""G1 汇率压力测试：三档贬值情景下的毛利与现金缺口。

模型（全部折算成美元口径比较）
    收入 = 本地销售(埃镑) / 当期汇率 + 出口销售(美元)
    成本 = 进口料件(美元) + 本地费用(埃镑) / 当期汇率 + 人工(埃镑) / 当期汇率
    贬值 d 时：汇率 = 基准汇率 x (1 + d)
              本地售价可按 pass_through x d 的比例上调（0 = 完全不涨价，1 = 完全跟随）

用法
    python fx_stress.py input.json
    python fx_stress.py --demo

input.json 结构
    {
      "fx_rate": 56.1,
      "revenue": {"local_egp": 560000000, "export_usd": 3000000},
      "costs":   {"import_usd": 4000000, "local_egp": 168000000, "labor_egp": 56000000},
      "pass_through": 0.5,
      "scenarios": [0, 0.10, 0.25, 0.40],
      "hedge_ratio": 0.0
    }

输出：每个情景的美元毛利、毛利率、相对基准变动、现金缺口、维持毛利率所需涨价比例。
仅依赖标准库。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


DEMO = {
    "fx_rate": 56.1,
    "revenue": {"local_egp": 560_000_000, "export_usd": 3_000_000},
    "costs": {"import_usd": 4_000_000, "local_egp": 168_000_000, "labor_egp": 56_000_000},
    "pass_through": 0.5,
    "scenarios": [0.0, 0.10, 0.25, 0.40],
    "hedge_ratio": 0.0,
}


def _margin(rate: float, rev: dict, cost: dict, d: float, pass_through: float) -> tuple[float, float]:
    new_rate = rate * (1 + d)
    local_rev = rev["local_egp"] * (1 + pass_through * d) / new_rate
    total_rev = local_rev + rev["export_usd"]
    total_cost = cost["import_usd"] + (cost["local_egp"] + cost["labor_egp"]) / new_rate
    return total_rev - total_cost, total_rev


def compute(payload: dict) -> dict:
    rate = float(payload["fx_rate"])
    rev = payload["revenue"]
    cost = payload["costs"]
    pt = float(payload.get("pass_through", 0.0))
    hedge = float(payload.get("hedge_ratio", 0.0))
    scenarios = payload.get("scenarios") or [0.0, 0.10, 0.25, 0.40]

    base_gm, base_rev = _margin(rate, rev, cost, 0.0, 0.0)
    base_pct = base_gm / base_rev if base_rev else 0.0

    import_share = cost["import_usd"] / (cost["import_usd"] + cost["local_egp"] / rate)
    net_usd_short = max(0.0, cost["import_usd"] - rev["export_usd"])
    hedged = net_usd_short * hedge

    rows = []
    for d in scenarios:
        gm, total_rev = _margin(rate, rev, cost, d, pt)
        pct = gm / total_rev if total_rev else 0.0

        # 维持基准毛利率所需的本地涨价比例（对 pass_through 做二分）
        need = None
        lo, hi = 0.0, 2.0
        for _ in range(80):
            mid = (lo + hi) / 2
            g, r = _margin(rate, rev, cost, d, mid)
            if (g / r if r else 0.0) < base_pct:
                lo = mid
            else:
                hi = mid
        need = (lo + hi) / 2

        rows.append({
            "devaluation": round(d, 4),
            "fx_rate": round(rate * (1 + d), 2),
            "revenue_usd": round(total_rev, 0),
            "cost_usd": round(total_rev - gm, 0),
            "gross_margin_usd": round(gm, 0),
            "gross_margin_pct": round(pct * 100, 2),
            "delta_pp": round((pct - base_pct) * 100, 2),
            "cash_gap_usd": round(min(0.0, gm), 0),
            "required_price_hike_pct": round(need * d * 100, 2),
        })

    worst = min(rows, key=lambda r: r["gross_margin_pct"])
    flags = []
    if import_share > 0.60 and hedge < 0.5:
        flags.append("进口件占比 %.0f%% 且对冲比例 %.0f%% -> CONDITIONAL" % (import_share * 100, hedge * 100))
    mid = next((r for r in rows if abs(r["devaluation"] - 0.20) < 1e-9), None)
    ref = mid or worst
    if abs(ref["delta_pp"]) > 8:
        flags.append("20%% 贬值下毛利率变动 %.1f 个百分点 -> CONDITIONAL" % ref["delta_pp"])
    if worst["gross_margin_pct"] < 0:
        flags.append("最差情景毛利为负 -> STOP 或重设体量/路径")

    verdict = "PASS"
    if any("STOP" in f for f in flags):
        verdict = "STOP"
    elif flags:
        verdict = "CONDITIONAL"

    return {
        "base_fx_rate": rate,
        "base_gross_margin_pct": round(base_pct * 100, 2),
        "import_share_of_material": round(import_share * 100, 1),
        "net_usd_short": round(net_usd_short, 0),
        "hedged_notional": round(hedged, 0),
        "unhedged_notional": round(net_usd_short - hedged, 0),
        "scenarios": rows,
        "verdict": verdict,
        "flags": flags,
    }


def render(result: dict) -> str:
    lines = []
    lines.append("基准汇率 USD/EGP = %.2f   基准毛利率 %.2f%%" % (
        result["base_fx_rate"], result["base_gross_margin_pct"]))
    lines.append("进口件占物料成本 %.1f%%   美元净缺口 %.0f   已对冲 %.0f   未对冲 %.0f" % (
        result["import_share_of_material"], result["net_usd_short"],
        result["hedged_notional"], result["unhedged_notional"]))
    lines.append("")
    lines.append("{:<8} {:<9} {:>14} {:>14} {:>8} {:>8} {:>12} {:>11}".format(
        "贬值", "汇率", "收入(USD)", "毛利(USD)", "毛利率", "变动pp", "现金缺口", "需涨价"))
    for r in result["scenarios"]:
        lines.append("{:<8} {:<9} {:>14} {:>14} {:>8} {:>8} {:>12} {:>11}".format(
            "{:.0f}%".format(r["devaluation"] * 100),
            "{:.2f}".format(r["fx_rate"]),
            "{:,.0f}".format(r["revenue_usd"]),
            "{:,.0f}".format(r["gross_margin_usd"]),
            "{:.1f}%".format(r["gross_margin_pct"]),
            "{:+.1f}".format(r["delta_pp"]),
            "{:,.0f}".format(r["cash_gap_usd"]),
            "{:.1f}%".format(r["required_price_hike_pct"])))
    lines.append("")
    lines.append("判定：%s" % result["verdict"])
    for f in result["flags"]:
        lines.append("  - %s" % f)
    return "\n".join(lines)


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    payload = DEMO if args[0] == "--demo" else json.loads(Path(args[0]).read_text(encoding="utf-8"))
    result = compute(payload)
    print(render(result))
    if "--json" in args:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
