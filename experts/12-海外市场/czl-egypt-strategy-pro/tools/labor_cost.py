#!/usr/bin/env python3
"""G5 全口径人工成本：把"月薪 x 人数"算成"每年到底花多少"。

全口径 = 基本工资 + 固定津贴 + 加班 + 雇主社保 + 招聘培训 + 离职补偿计提
再除以年产量，得到单位产品人工成本。

用法
    python labor_cost.py input.json
    python labor_cost.py --demo

input.json 结构
    {
      "positions": [
        {"role": "普工",   "headcount": 80, "monthly_wage_egp": 9000,
         "allowances_pct": 0.12, "overtime_pct": 0.08},
        {"role": "技术员", "headcount": 12, "monthly_wage_egp": 18000,
         "allowances_pct": 0.15, "overtime_pct": 0.05}
      ],
      "employer_si_rate": 0.1875,
      "annual_increment_pct": 0.08,
      "recruiting_pct": 0.02,
      "turnover_provision_pct": 0.03,
      "annual_output_units": 200000
    }

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
    "positions": [
        {"role": "普工", "headcount": 80, "monthly_wage_egp": 9000, "allowances_pct": 0.12, "overtime_pct": 0.08},
        {"role": "技术员", "headcount": 12, "monthly_wage_egp": 18000, "allowances_pct": 0.15, "overtime_pct": 0.05},
        {"role": "工程师", "headcount": 4, "monthly_wage_egp": 35000, "allowances_pct": 0.18, "overtime_pct": 0.0},
        {"role": "管理与财务", "headcount": 5, "monthly_wage_egp": 45000, "allowances_pct": 0.20, "overtime_pct": 0.0},
    ],
    "employer_si_rate": 0.1875,
    "annual_increment_pct": 0.08,
    "recruiting_pct": 0.02,
    "turnover_provision_pct": 0.03,
    "annual_output_units": 200000,
}


def compute(p: dict) -> dict:
    si = float(p.get("employer_si_rate", 0.1875))
    rows = []
    total_base = total_cost = 0.0
    headcount = 0
    for pos in p["positions"]:
        hc = float(pos["headcount"])
        base = hc * float(pos["monthly_wage_egp"]) * 12
        allow = base * float(pos.get("allowances_pct", 0.0))
        ot = base * float(pos.get("overtime_pct", 0.0))
        si_cost = (base + allow) * si
        recruit = base * float(p.get("recruiting_pct", 0.0))
        turnover = base * float(p.get("turnover_provision_pct", 0.0))
        cost = base + allow + ot + si_cost + recruit + turnover
        rows.append({
            "role": pos["role"],
            "headcount": int(hc),
            "annual_base_egp": round(base, 0),
            "annual_cost_egp": round(cost, 0),
            "per_head_cost_egp": round(cost / hc, 0),
            "multiplier": round(cost / base, 3),
        })
        total_base += base
        total_cost += cost
        headcount += int(hc)

    inc = float(p.get("annual_increment_pct", 0.0))
    output = float(p.get("annual_output_units", 0) or 0)
    return {
        "headcount": headcount,
        "rows": rows,
        "total_base_egp": round(total_base, 0),
        "total_cost_egp": round(total_cost, 0),
        "year2_cost_egp": round(total_cost * (1 + inc), 0),
        "blended_multiplier": round(total_cost / total_base, 3) if total_base else 0.0,
        "per_head_cost_egp": round(total_cost / headcount, 0) if headcount else 0.0,
        "labor_per_unit_egp": round(total_cost / output, 3) if output else None,
        "labor_share_note": "单位产品人工成本仅在提供年产量时给出" if not output else "",
    }


def render(r: dict) -> str:
    lines = ["{:<12} {:>6} {:>14} {:>14} {:>12} {:>6}".format("岗位", "人数", "年基本工资", "年全口径", "人均全口径", "倍数")]
    lines.append("-" * 70)
    for row in r["rows"]:
        lines.append("{:<12} {:>6} {:>14,.0f} {:>14,.0f} {:>12,.0f} {:>6.2f}".format(
            row["role"], row["headcount"], row["annual_base_egp"],
            row["annual_cost_egp"], row["per_head_cost_egp"], row["multiplier"]))
    lines.append("-" * 70)
    lines.append("合计 {} 人；年基本工资 {:,.0f}；年全口径 {:,.0f}；综合倍数 {:.2f}".format(
        r["headcount"], r["total_base_egp"], r["total_cost_egp"], r["blended_multiplier"]))
    lines.append("第二年（含调薪）{:,.0f}".format(r["year2_cost_egp"]))
    if r["labor_per_unit_egp"] is not None:
        lines.append("单位产品人工 {:,.3f} EGP".format(r["labor_per_unit_egp"]))
    else:
        lines.append(r["labor_share_note"])
    lines.append("")
    lines.append("提示：用月薪乘人数会低估 {:.0f}% 的成本，报价与可研必须用全口径。".format(
        (r["blended_multiplier"] - 1) * 100))
    return "\n".join(lines)


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    payload = DEMO if args[0] == "--demo" else json.loads(Path(args[0]).read_text(encoding="utf-8"))
    r = compute(payload)
    print(render(r))
    if "--json" in args:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
