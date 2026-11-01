#!/usr/bin/env python3
"""G4 进入路径比选：先按硬约束过滤，再按四维加权排序。

设计要点
    过滤在前、排序在后。不能先排名再解释"第一名为什么做不到"。

用法
    python entry_route.py input.json
    python entry_route.py --demo

input.json 结构
    {
      "weights": {"control": 0.35, "speed": 0.25, "capital_efficiency": 0.20, "risk_control": 0.20},
      "constraints": {"max_capex_usd": 20000000, "max_months": 24, "allow_tech_leak": false},
      "routes": [
        {"key": "greenfield", "label": "绿地全资", "control": 5, "speed": 1,
         "capital_efficiency": 1, "risk_control": 3,
         "capex_usd": 20000000, "months": 30, "exit_cost_pct": 0.60, "tech_leak": false},
        ...
      ]
    }

四维均为 1-5 分，5 最好。仅依赖标准库。
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
    "weights": {"control": 0.35, "speed": 0.25, "capital_efficiency": 0.20, "risk_control": 0.20},
    "constraints": {"max_capex_usd": 20_000_000, "max_months": 24, "allow_tech_leak": False},
    "routes": [
        {"key": "greenfield", "label": "绿地全资建厂", "control": 5, "speed": 1, "capital_efficiency": 1,
         "risk_control": 3, "capex_usd": 20_000_000, "months": 30, "exit_cost_pct": 0.60, "tech_leak": False},
        {"key": "jv", "label": "控股合资", "control": 4, "speed": 3, "capital_efficiency": 3,
         "risk_control": 2, "capex_usd": 12_000_000, "months": 18, "exit_cost_pct": 0.35, "tech_leak": True},
        {"key": "ma", "label": "并购本地企业", "control": 4, "speed": 4, "capital_efficiency": 3,
         "risk_control": 2, "capex_usd": 15_000_000, "months": 10, "exit_cost_pct": 0.20, "tech_leak": False},
        {"key": "toll", "label": "合同制造/代工", "control": 2, "speed": 5, "capital_efficiency": 5,
         "risk_control": 4, "capex_usd": 500_000, "months": 5, "exit_cost_pct": 0.05, "tech_leak": True},
        {"key": "agent", "label": "代理分销", "control": 1, "speed": 5, "capital_efficiency": 5,
         "risk_control": 4, "capex_usd": 200_000, "months": 3, "exit_cost_pct": 0.10, "tech_leak": True},
        {"key": "fz", "label": "自由区贸易公司", "control": 3, "speed": 4, "capital_efficiency": 4,
         "risk_control": 3, "capex_usd": 800_000, "months": 6, "exit_cost_pct": 0.10, "tech_leak": False},
    ],
}


def compute(payload: dict) -> dict:
    w = payload["weights"]
    cons = payload.get("constraints", {})
    routes = payload["routes"]
    total_w = sum(w.values()) or 1.0

    feasible, blocked = [], []
    for r in routes:
        reasons = []
        if cons.get("max_capex_usd") is not None and r["capex_usd"] > cons["max_capex_usd"]:
            reasons.append("资本 {:,} 超过上限 {:,}".format(r["capex_usd"], cons["max_capex_usd"]))
        if cons.get("max_months") is not None and r["months"] > cons["max_months"]:
            reasons.append("周期 {} 个月超过上限 {} 个月".format(r["months"], cons["max_months"]))
        if r.get("tech_leak") and not cons.get("allow_tech_leak", True):
            reasons.append("存在技术外流风险，客户不允许")
        row = {
            "key": r["key"], "label": r["label"],
            "capex_usd": r["capex_usd"], "months": r["months"],
            "exit_cost_usd": round(r["capex_usd"] * r.get("exit_cost_pct", 0.3), 0),
            "score": round(sum(w[k] * r[k] for k in w) / total_w / 5 * 100, 1),
        }
        if reasons:
            row["blocked_by"] = reasons
            blocked.append(row)
        else:
            feasible.append(row)

    feasible.sort(key=lambda x: x["score"], reverse=True)
    for i, r in enumerate(feasible, 1):
        r["rank"] = i

    verdict = "PASS"
    note = ""
    if not feasible:
        verdict = "STOP"
        counts = {}
        for b in blocked:
            for reason in b["blocked_by"]:
                key = reason.split(" ")[0]
                counts[key] = counts.get(key, 0) + 1
        top = max(counts, key=counts.get) if counts else "约束"
        note = "全部路径被过滤，最紧的约束是「{}」，需与客户确认能否放宽".format(top)
    elif len(feasible) == 1:
        note = "只剩一条可行路径，建议直接采用并说明为何其他路径不可行"
    else:
        gap = feasible[0]["score"] - feasible[1]["score"]
        note = "首选 {}，与次优分差 {:.1f}；若分差 <5 需补一条定性理由".format(feasible[0]["label"], gap)

    return {"feasible": feasible, "blocked": blocked, "verdict": verdict, "note": note}


def render(result: dict) -> str:
    lines = []
    lines.append("可行路径（已过硬约束）")
    lines.append("-" * 62)
    if result["feasible"]:
        lines.append("{:<4} {:<16} {:>8} {:>8} {:>12} {:>8}".format("排名", "路径", "得分", "周期", "退出成本", "资本"))
        for r in result["feasible"]:
            lines.append("{:<4} {:<16} {:>8.1f} {:>7}月 {:>12,.0f} {:>8,.0f}".format(
                r["rank"], r["label"], r["score"], r["months"], r["exit_cost_usd"], r["capex_usd"]))
    else:
        lines.append("（无）")
    if result["blocked"]:
        lines.append("")
        lines.append("被过滤的路径")
        lines.append("-" * 62)
        for b in result["blocked"]:
            lines.append("{}：{}".format(b["label"], "；".join(b["blocked_by"])))
    lines.append("")
    lines.append("判定：{} — {}".format(result["verdict"], result["note"]))
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
