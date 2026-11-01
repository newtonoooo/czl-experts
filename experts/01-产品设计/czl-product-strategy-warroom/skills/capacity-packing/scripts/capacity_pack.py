#!/usr/bin/env python3
"""Capacity packer.

Packs a backlog into real person-week capacity instead of ranking it. Produces
the committed set, the deferred set with reasons, the commitment rate, and the
dependency breaks that appear once something is cut.

Standard library only. Exit code 0 = plan is internally valid, 1 = blocker.

Usage:
    python capacity_pack.py --backlog backlog.csv --people 6 --weeks 13 \
        [--focus 0.65] [--buffer 0.15] [--out plan.csv] [--json]
"""
import argparse
import csv
import json
import os
import sys

PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2}
MAX_SINGLE_SHARE = 0.40
HEALTHY_LOW, HEALTHY_HIGH = 0.60, 0.85


def load_backlog(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        rows = []
        for raw in csv.DictReader(fh):
            if not (raw.get("id") or "").strip():
                continue
            deps = [d.strip() for d in (raw.get("depends_on") or "").replace(";", ",").split(",") if d.strip()]
            rows.append({
                "id": raw["id"].strip(),
                "req_id": (raw.get("req_id") or "").strip(),
                "title": (raw.get("title") or "").strip(),
                "pw": float(raw.get("pw") or 0),
                "priority": (raw.get("priority") or "P2").strip().upper(),
                "depends_on": deps,
                "stop_loss": (raw.get("stop_loss") or "").strip(),
            })
        return rows


def topo_order(items):
    """Dependency-first order; ties broken by priority then size."""
    by_id = {i["id"]: i for i in items}
    ordered, placed, visiting = [], set(), set()

    def visit(item, trail):
        if item["id"] in placed:
            return
        if item["id"] in visiting:
            raise ValueError("依赖成环：%s" % " -> ".join(trail + [item["id"]]))
        visiting.add(item["id"])
        for dep in item["depends_on"]:
            if dep in by_id:
                visit(by_id[dep], trail + [item["id"]])
        visiting.discard(item["id"])
        placed.add(item["id"])
        ordered.append(item)

    for item in sorted(items, key=lambda i: (PRIORITY_RANK.get(i["priority"], 9), i["pw"])):
        visit(item, [])
    return ordered


def pack(items, committable, existing_ids):
    errors, warnings = [], []
    order = topo_order(items)
    remaining = committable
    status = {}
    capacity_broken = False

    for item in order:
        unknown = [d for d in item["depends_on"] if d not in existing_ids]
        if unknown:
            warnings.append("%s 依赖不存在的编号：%s" % (item["id"], ",".join(unknown)))
        blocked = [d for d in item["depends_on"] if status.get(d) not in (None, "committed")]
        if blocked:
            status[item["id"]] = "deferred"
            item["reason"] = "上游被砍：%s" % ",".join(blocked)
            continue
        if capacity_broken:
            status[item["id"]] = "deferred"
            item["reason"] = "更高优先级项未装下，不用小项填缝"
            continue
        if item["pw"] > committable * MAX_SINGLE_SHARE:
            warnings.append("%s 单项 %.1f 人周超过可承诺的 40%%，建议切片" % (item["id"], item["pw"]))
        if item["pw"] <= remaining + 1e-9:
            status[item["id"]] = "committed"
            item["reason"] = ""
            remaining -= item["pw"]
        else:
            status[item["id"]] = "deferred"
            item["reason"] = "产能不足：剩余 %.1f 人周 < 需要 %.1f" % (remaining, item["pw"])
            capacity_broken = True

    committed_pw = sum(i["pw"] for i in items if status[i["id"]] == "committed")
    rate = committed_pw / committable if committable > 0 else 0

    for item in items:
        if item["priority"] == "P0" and status[item["id"]] != "committed":
            errors.append("P0 未装进计划：%s（%s）" % (item["id"], item["reason"]))
    for item in items:
        if status[item["id"]] == "committed":
            for dep in item["depends_on"]:
                if dep in status and status[dep] != "committed":
                    errors.append("%s 已承诺但上游 %s 被砍" % (item["id"], dep))
        if status[item["id"]] == "committed" and not item["stop_loss"]:
            warnings.append("%s 已承诺但没写止损线" % item["id"])

    if rate > HEALTHY_HIGH:
        warnings.append("承诺率 %.0f%% 超过 85%%，没有任何余量吸收线上问题" % (rate * 100))
    elif rate < HEALTHY_LOW:
        warnings.append("承诺率 %.0f%% 低于 60%%，产能未用满或估算虚高" % (rate * 100))

    return status, committed_pw, remaining, rate, errors, warnings, order


def main(argv=None):
    ap = argparse.ArgumentParser(description="Capacity packer")
    ap.add_argument("--backlog", required=True)
    ap.add_argument("--people", type=float, required=True)
    ap.add_argument("--weeks", type=float, required=True)
    ap.add_argument("--focus", type=float, default=0.65)
    ap.add_argument("--buffer", type=float, default=0.15)
    ap.add_argument("--out", default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if not os.path.exists(args.backlog):
        print("[ERR] 找不到 backlog：%s" % args.backlog)
        return 1

    items = load_backlog(args.backlog)
    if not items:
        print("[ERR] backlog 为空")
        return 1

    theoretical = args.people * args.weeks
    usable = theoretical * args.focus
    buffer_pw = usable * args.buffer
    committable = usable - buffer_pw
    if committable <= 0:
        print("[ERR] 可承诺人周 <= 0，检查人数/周期/专注系数")
        return 1

    try:
        status, committed_pw, remaining, rate, errors, warnings, order = pack(
            items, committable, {i["id"] for i in items})
    except ValueError as exc:
        print("[ERR] %s" % exc)
        return 1

    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["id", "req_id", "title", "pw", "priority", "depends_on",
                        "status", "reason", "stop_loss"])
            for item in order:
                w.writerow([item["id"], item["req_id"], item["title"], "%.1f" % item["pw"],
                            item["priority"], ",".join(item["depends_on"]),
                            status[item["id"]], item.get("reason", ""), item.get("stop_loss", "")])

    payload = {
        "capacity": {
            "theoretical_pw": round(theoretical, 2),
            "usable_pw": round(usable, 2),
            "buffer_pw": round(buffer_pw, 2),
            "committable_pw": round(committable, 2),
        },
        "committed_pw": round(committed_pw, 2),
        "remaining_pw": round(remaining, 2),
        "commitment_rate": round(rate, 3),
        "plan": [{"id": i["id"], "req_id": i["req_id"], "pw": i["pw"],
                  "priority": i["priority"], "status": status[i["id"]],
                  "reason": i.get("reason", "")} for i in order],
        "errors": errors,
        "warnings": warnings,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("产能测算：%.0f 人 x %.0f 周 = %.1f 人周" % (args.people, args.weeks, theoretical))
        print("  专注系数 %.2f -> 可用 %.1f 人周；缓冲 %.1f -> 可承诺 %.1f 人周"
              % (args.focus, usable, buffer_pw, committable))
        print("")
        print("  %-6s %-8s %-5s %-10s %s" % ("id", "req", "pw", "status", "note"))
        for item in order:
            print("  %-6s %-8s %-5.1f %-10s %s"
                  % (item["id"], item["req_id"], item["pw"], status[item["id"]], item.get("reason", "")))
        print("")
        print("承诺 %.1f 人周，剩余 %.1f，承诺率 %.0f%%" % (committed_pw, remaining, rate * 100))
        for w in warnings:
            print("[WARN] %s" % w)
        for e in errors:
            print("[ERR] %s" % e)
        print("结果：%s" % ("通过" if not errors else "存在 %d 个阻断项" % len(errors)))

    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
