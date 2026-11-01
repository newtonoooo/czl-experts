#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""portfolio_fit.py - capacity-calibrated prioritisation.

Part of the Setpoint / 产品决策审校专家 package (czl-product-decision-audit).

RICE scores rank ideas. They do not tell you how many ideas fit. This tool does:

  1. turns headcount + weeks + utilisation into person-weeks of real capacity
  2. reserves capacity for must-do items (compliance, contractual, defect)
  3. fills the rest by score density (RICE per person-week) - a knapsack, not a
     ranking, so one huge item cannot silently swallow the quarter
  4. compares the plan against historical throughput and says so when the plan
     is bigger than the team has ever delivered
  5. re-runs at -20% / +20% capacity and marks the items that only survive in
     the optimistic case (the fragile ones)

Columns required in the backlog CSV:
    id, name, reach, impact, confidence, effort
Optional:
    must   - yes/no, reserved before scoring
    deadline - any text; flagged in the cut list so it is not silently dropped

Pure standard library. No network. No writes.

Example
-------
    python portfolio_fit.py backlog.csv --headcount 5 --weeks 12 --utilization 0.65

Exit codes
----------
    0  plan fits inside capacity
    1  plan exceeds capacity (cut list produced)
    2  usage or file problem
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import sys

REQUIRED = ["id", "name", "reach", "impact", "confidence", "effort"]


def read_backlog(path):
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        sample = fh.read(2048)
        fh.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(fh, dialect=dialect)
        fields = [f.strip().lower() for f in (reader.fieldnames or [])]
        rows = [
            {(k or "").strip().lower(): (v or "").strip() for k, v in r.items()}
            for r in reader
        ]
    return rows, fields


def number(value, default=None):
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return default


def normalise_confidence(raw, warnings, item_id):
    if raw is None:
        warnings.append(f"[{item_id}] confidence 缺失，按 50% 计")
        return 0.5
    if raw > 1.0:
        # accept 0-100 scale
        value = raw / 100.0
    else:
        value = raw
    if value <= 0 or value > 1.0:
        warnings.append(f"[{item_id}] confidence {raw} 超出 (0,1]，按 0.5 计")
        return 0.5
    return value


def build_items(rows, warnings):
    items = []
    for row in rows:
        if not row.get("id") and not row.get("name"):
            continue
        iid = row.get("id") or row.get("name")
        reach = number(row.get("reach"))
        impact = number(row.get("impact"))
        conf_raw = number(row.get("confidence"))
        effort = number(row.get("effort"))

        if reach is None or impact is None or effort is None:
            warnings.append(f"[{iid}] reach/impact/effort 缺失或非数字，已跳过")
            continue
        if effort <= 0:
            warnings.append(f"[{iid}] effort <= 0，已跳过")
            continue

        confidence = normalise_confidence(conf_raw, warnings, iid)
        rice = reach * impact * confidence / effort
        items.append(
            {
                "id": iid,
                "name": row.get("name", iid),
                "reach": reach,
                "impact": impact,
                "confidence": confidence,
                "effort": effort,
                "rice": rice,
                "density": rice,  # RICE already divides by effort
                "must": (row.get("must", "").strip().lower() in ("yes", "y", "1", "true", "是")),
                "deadline": row.get("deadline", ""),
            }
        )
    return items


def plan(items, capacity, must_cost):
    """Reserve must-dos, then fill remaining capacity by density."""
    remaining = capacity
    must_items, flex = [], []
    for it in items:
        if it["must"]:
            must_items.append(it)
            remaining -= it["effort"]
        else:
            flex.append(it)

    flex.sort(key=lambda x: x["density"], reverse=True)
    chosen = list(must_items)
    for it in flex:
        if it["effort"] <= remaining + 1e-9:
            chosen.append(it)
            remaining -= it["effort"]

    chosen_ids = {it["id"] for it in chosen}
    cut = [it for it in items if it["id"] not in chosen_ids]
    used = sum(it["effort"] for it in chosen)
    return chosen, cut, used, remaining


def fmt_pct(x):
    return f"{x * 100:.0f}%"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Capacity-calibrated portfolio planning (RICE + knapsack)."
    )
    parser.add_argument("backlog", help="候选需求 CSV")
    parser.add_argument("--headcount", type=float, required=True, help="可投入人数")
    parser.add_argument("--weeks", type=float, default=12.0, help="周期长度（周），默认 12")
    parser.add_argument(
        "--utilization",
        type=float,
        default=0.65,
        help="有效投入比例（扣会议、支持、值班、休假），默认 0.65",
    )
    parser.add_argument(
        "--reserve",
        type=float,
        default=0.10,
        help="预留比例给临时插入与线上问题，默认 0.10",
    )
    parser.add_argument(
        "--history",
        type=float,
        default=None,
        help="历史同期实际完成条数，用于吞吐比对",
    )
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args(argv)

    warnings = []
    try:
        rows, fields = read_backlog(args.backlog)
    except FileNotFoundError:
        print(f"错误：找不到文件 {args.backlog}", file=sys.stderr)
        return 2
    except UnicodeDecodeError:
        print("错误：文件编码无法识别，请另存为 UTF-8", file=sys.stderr)
        return 2

    missing = [c for c in REQUIRED if c not in fields]
    if missing:
        print("缺少必需列: " + ", ".join(missing), file=sys.stderr)
        return 2

    items = build_items(rows, warnings)
    if not items:
        print("没有可用的候选需求。", file=sys.stderr)
        return 2

    gross = args.headcount * args.weeks * args.utilization
    reserve = gross * args.reserve
    capacity = gross - reserve

    must_cost = sum(it["effort"] for it in items if it["must"])
    chosen, cut, used, remaining = plan(items, capacity, must_cost)

    # sensitivity
    def ids_at(scale):
        cap = capacity * scale
        c, _, _, _ = plan(items, cap, must_cost)
        return {it["id"] for it in c}

    tight = ids_at(0.8)
    loose = ids_at(1.2)
    fragile = [it for it in chosen if it["id"] not in tight]
    safe = [it for it in chosen if it["id"] in tight]
    optimistic_only = [it for it in items if it["id"] in loose and it["id"] not in {c["id"] for c in chosen}]

    if args.json:
        payload = {
            "capacity_person_weeks": round(capacity, 1),
            "gross_person_weeks": round(gross, 1),
            "reserve_person_weeks": round(reserve, 1),
            "must_cost": round(must_cost, 1),
            "used": round(used, 1),
            "remaining": round(remaining, 1),
            "chosen": [it["id"] for it in chosen],
            "cut": [it["id"] for it in cut],
            "fragile": [it["id"] for it in fragile],
            "warnings": warnings,
        }
        import json

        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if not cut else 1

    print("组合容量校准")
    print("=" * 62)
    print(
        f"名义产能: {args.headcount:g} 人 × {args.weeks:g} 周 × {fmt_pct(args.utilization)} "
        f"= {gross:.1f} 人周"
    )
    print(f"预留 {fmt_pct(args.reserve)}: {reserve:.1f} 人周   可用于排期: {capacity:.1f} 人周")
    if must_cost:
        share = must_cost / capacity * 100 if capacity else float("inf")
        print(f"必做项（合规/合同/缺陷）: {must_cost:.1f} 人周，占可用产能 {share:.0f}%")
        if share > 40:
            print("  注意：必做项已吃掉四成以上产能，新功能的实际空间比看上去小得多。")

    print("\n候选排序（按 RICE 密度 = reach × impact × confidence ÷ effort）")
    print("-" * 62)
    print(f"{'#':<3}{'需求':<20}{'人周':>7}{'RICE':>9}{'必做':>6}  结论")
    ordered = sorted(items, key=lambda x: (not x["must"], -x["density"]))
    chosen_ids = {it["id"] for it in chosen}
    for i, it in enumerate(ordered, start=1):
        tag = "必做" if it["must"] else ""
        verdict = "排入" if it["id"] in chosen_ids else "砍掉/延后"
        name = it["name"][:18]
        print(f"{i:<3}{name:<20}{it['effort']:>7.1f}{it['rice']:>9.1f}{tag:>6}  {verdict}")

    print("-" * 62)
    print(f"排入 {len(chosen)} 项，占用 {used:.1f} 人周，剩余 {remaining:.1f} 人周")
    print(f"砍掉/延后 {len(cut)} 项，合计 {sum(it['effort'] for it in cut):.1f} 人周")

    if args.history is not None:
        print(f"\n吞吐比对：历史同期实际完成 {args.history:g} 项，本次计划 {len(chosen)} 项")
        if len(chosen) > args.history:
            over = len(chosen) - args.history
            print(
                f"  警告：计划量高于历史吞吐 {over} 项。团队从未在同期完成这么多，"
                "按历史数据这张表会延期。"
            )
        else:
            print("  计划量在历史吞吐之内。")

    if fragile:
        print("\n脆弱项（产能缩 20% 时会被挤掉）：")
        for it in fragile:
            print(f"  - {it['name']}（{it['effort']:.1f} 人周）")

    if cut:
        print("\n砍单清单（对外说法要写清被挤掉的是什么）：")
        for it in cut:
            extra = f"，截止 {it['deadline']}" if it["deadline"] else ""
            if it["must"]:
                reason = "必做项但产能不足，必须加人或回退范围"
            elif it["effort"] > remaining + 1e-9:
                reason = (
                    f"装不进剩余容量（需 {it['effort']:.1f} 人周，"
                    f"排完已排入项后只剩 {remaining:.1f} 人周）"
                )
            else:
                reason = "排名靠后，被容量截断"
            print(f"  - {it['name']}（{it['effort']:.1f} 人周{extra}）— {reason}")
        squeezed = [
            (c, it)
            for it in cut
            for c in chosen
            if it["density"] > c["density"] and it["effort"] > remaining + 1e-9
        ]
        if squeezed:
            print("\n注意：下列被砍项的单周产出高于部分已排入项，只是体积太大塞不进剩余容量。")
            shown = set()
            for c, it in squeezed:
                if it["id"] in shown:
                    continue
                shown.add(it["id"])
                print(f"  - {it['name']}（{it['density']:.0f}/人周）高过已排入的 {c['name']}（{c['density']:.0f}/人周）")
            print("  这正是排序法看不出来的损失：可以考虑拆分，把其中一部分排进来。")
        print("\n结论：当前产能下做不完。要么砍上面这些，要么加人，要么改周期。")
        print("三个选项都要给老板，不要只给他一张做不完的表。")
    else:
        print("\n结论：全部排入且有余量。可以再补 1–2 项，或把余量投到技术健康。")

    if warnings:
        print("\n数据提示：")
        for w in warnings:
            print(f"  - {w}")

    return 0 if not cut else 1


if __name__ == "__main__":
    sys.exit(main())
