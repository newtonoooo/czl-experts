#!/usr/bin/env python3
"""G5 进口到岸成本：从 FOB 一路算到"到厂每件成本"。

包含常被漏算的四项：清关固定费、内陆运费、滞港预备金、在途资金成本。
增值税按"可抵扣的现金流"单列，不计入成本基数（除非客户不能抵扣）。

用法
    python landed_cost.py input.json
    python landed_cost.py --demo

input.json 结构
    {
      "quantity": 10000,
      "fob_unit_usd": 100.0,
      "freight_unit_usd": 8.0,
      "insurance_pct": 0.005,
      "duty_rate": 0.15,
      "vat_rate": 0.14,
      "vat_recoverable": true,
      "clearance_fixed_usd": 3000,
      "inland_fixed_usd": 2000,
      "port_delay_days": 5,
      "demurrage_per_day_usd": 300,
      "transit_days": 45,
      "carry_rate_annual": 0.18,
      "local_assembly_cost_per_unit": 0.0
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
    "quantity": 10000,
    "fob_unit_usd": 100.0,
    "freight_unit_usd": 8.0,
    "insurance_pct": 0.005,
    "duty_rate": 0.15,
    "vat_rate": 0.14,
    "vat_recoverable": True,
    "clearance_fixed_usd": 3000,
    "inland_fixed_usd": 2000,
    "port_delay_days": 5,
    "demurrage_per_day_usd": 300,
    "transit_days": 45,
    "carry_rate_annual": 0.18,
    "local_assembly_cost_per_unit": 12.0,
}


def compute(p: dict) -> dict:
    q = float(p["quantity"])
    fob = float(p["fob_unit_usd"])
    freight = float(p["freight_unit_usd"])
    insurance = (fob + freight) * float(p.get("insurance_pct", 0.0))
    cif_unit = fob + freight + insurance

    duty_unit = cif_unit * float(p.get("duty_rate", 0.0))
    vat_unit = (cif_unit + duty_unit) * float(p.get("vat_rate", 0.0))

    clearance_unit = float(p.get("clearance_fixed_usd", 0.0)) / q
    inland_unit = float(p.get("inland_fixed_usd", 0.0)) / q
    demurrage_unit = float(p.get("port_delay_days", 0.0)) * float(p.get("demurrage_per_day_usd", 0.0)) / q
    carry_unit = cif_unit * float(p.get("carry_rate_annual", 0.0)) * float(p.get("transit_days", 0)) / 365.0

    cost_unit = cif_unit + duty_unit + clearance_unit + inland_unit + demurrage_unit + carry_unit
    if not p.get("vat_recoverable", True):
        cost_unit += vat_unit

    assembly = float(p.get("local_assembly_cost_per_unit", 0.0) or 0.0)
    local_unit = cost_unit + assembly if assembly else None

    return {
        "quantity": q,
        "cif_unit": round(cif_unit, 3),
        "duty_unit": round(duty_unit, 3),
        "vat_unit_cash": round(vat_unit, 3),
        "vat_recoverable": bool(p.get("vat_recoverable", True)),
        "clearance_unit": round(clearance_unit, 3),
        "inland_unit": round(inland_unit, 3),
        "demurrage_unit": round(demurrage_unit, 3),
        "carry_unit": round(carry_unit, 3),
        "landed_unit_cost": round(cost_unit, 3),
        "landed_total": round(cost_unit * q, 0),
        "local_assembly_unit_cost": None if local_unit is None else round(local_unit, 3),
        "assembly_delta_unit": None if local_unit is None else round(local_unit - cost_unit, 3),
        "vat_cash_out": round(vat_unit * q, 0),
        "hidden_share_pct": round(
            (clearance_unit + inland_unit + demurrage_unit + carry_unit) / cost_unit * 100, 1),
    }


def render(r: dict) -> str:
    lines = ["数量 {:,.0f} 件".format(r["quantity"]), "-" * 46]
    rows = [
        ("CIF 单价", r["cif_unit"]),
        ("关税", r["duty_unit"]),
        ("清关费", r["clearance_unit"]),
        ("内陆运费", r["inland_unit"]),
        ("滞港预备金", r["demurrage_unit"]),
        ("在途资金成本", r["carry_unit"]),
    ]
    for name, v in rows:
        lines.append("{:<14} {:>10.3f}".format(name, v))
    if not r["vat_recoverable"]:
        lines.append("{:<14} {:>10.3f}".format("增值税(不可抵扣)", r["vat_unit_cash"]))
    lines.append("-" * 46)
    lines.append("{:<14} {:>10.3f}".format("到厂单价", r["landed_unit_cost"]))
    lines.append("{:<14} {:>10,.0f}".format("到厂总额", r["landed_total"]))
    if r["local_assembly_unit_cost"] is not None:
        lines.append("{:<14} {:>10.3f}".format("本地组装后", r["local_assembly_unit_cost"]))
        lines.append("{:<14} {:>+10.3f}".format("组装差额", r["assembly_delta_unit"]))
    lines.append("")
    lines.append("隐性成本占比 {:.1f}%（清关+内陆+滞港+资金）".format(r["hidden_share_pct"]))
    lines.append("增值税现金流占用 {:,.0f}（可抵扣：{}）".format(
        r["vat_cash_out"], "是" if r["vat_recoverable"] else "否"))
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
