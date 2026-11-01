#!/usr/bin/env python3
"""
intel_query.py - Query the UAE market intelligence base.

Read-only helper. It retrieves and summarises; it never makes a recommendation.
The judgement stays with the agent.

Usage:
    python intel_query.py segments
    python intel_query.py channel --id tiktok
    python intel_query.py sector --id beauty
    python intel_query.py channels-for --sector beauty
    python intel_query.py list-sectors

Options:
    --format markdown|json   (default markdown)

Exit codes: 0 ok, 2 bad usage / unknown id, 4 data file problem.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def load(name: str) -> dict:
    path = DATA_DIR / name
    if not path.exists():
        print(f"[FAIL] data file missing: {path}", file=sys.stderr)
        raise SystemExit(4)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"[FAIL] invalid JSON in {path}: {exc}", file=sys.stderr)
        raise SystemExit(4)


def fmt_band(band, unit: str) -> str:
    if not band:
        return "—"
    return f"{band[0]}–{band[1]} {unit}"


def print_segments(fmt: str) -> None:
    data = load("audience_segments.json")
    if fmt == "json":
        print(json.dumps(data["segments"], ensure_ascii=False, indent=2))
        return
    print(f"# 人群分层（口径日期 {data['as_of']}）\n")
    for s in data["segments"]:
        print(f"## {s['name_zh']} / {s['name_en']}  `{s['id']}`")
        print(f"- 体量：{s['share_band']}（{s['basis']}）")
        print(f"- 语言：{'、'.join(s['languages'])}")
        print(f"- 主媒介：{'、'.join(s['primary_platforms'])}")
        print(f"- 决策驱动：{'、'.join(s['decision_drivers'])}")
        print(f"- 敏感点：{'、'.join(s['sensitivities'])}")
        print(f"- 预算指数：{s['budget_index']}")
        print(f"- 备注：{s['notes']}\n")


def print_channel(fmt: str, cid: str) -> None:
    data = load("channel_catalog.json")
    hit = next((c for c in data["channels"] if c["id"] == cid), None)
    if not hit:
        ids = ", ".join(c["id"] for c in data["channels"])
        print(f"[FAIL] unknown channel '{cid}'. known: {ids}", file=sys.stderr)
        raise SystemExit(2)
    if fmt == "json":
        print(json.dumps(hit, ensure_ascii=False, indent=2))
        return
    print(f"# {hit['name_zh']} / {hit['name_en']}  `{hit['id']}`\n")
    print(f"- 渠道角色：{hit['role']}")
    print(f"- CPM：{fmt_band(hit['cpm_band'], 'AED')}")
    print(f"- CPC：{fmt_band(hit['cpc_band'], 'AED')}")
    print(f"- 最低预算：{hit['min_budget']} AED")
    print(f"- 优势：{'；'.join(hit['strengths'])}")
    print(f"- 限制：{'；'.join(hit['constraints'])}")
    print(f"- 素材要求：{'；'.join(hit['creative_requirements'])}")
    print(f"- 适用行业：{'、'.join(hit['best_for_sectors']) or '—'}")
    print(f"- 慎用行业：{'、'.join(hit['weak_for_sectors']) or '—'}")
    print(f"- KPI 形态：{hit['kpi_shape']}")
    print(f"- 口径：{hit['basis']}")


def print_sector(fmt: str, sid: str) -> None:
    data = load("sector_notes.json")
    hit = next((s for s in data["sectors"] if s["id"] == sid), None)
    if not hit:
        ids = ", ".join(s["id"] for s in data["sectors"])
        print(f"[FAIL] unknown sector '{sid}'. known: {ids}", file=sys.stderr)
        raise SystemExit(2)
    if fmt == "json":
        print(json.dumps(hit, ensure_ascii=False, indent=2))
        return
    print(f"# {hit['name_zh']} / {hit['name_en']}  `{hit['id']}`\n")
    print(f"- 建议渠道：{'、'.join(hit['channel_bias'])}")
    print(f"- 回避渠道：{'、'.join(hit['avoid']) or '无'}")
    print(f"- 合规红线：{'、'.join(hit['compliance_flags'])}")
    print(f"- 行业备注：{hit['notes']}")


def print_channels_for(fmt: str, sector: str) -> None:
    channels = load("channel_catalog.json")["channels"]
    notes = load("sector_notes.json")["sectors"]
    sec = next((s for s in notes if s["id"] == sector), None)
    if not sec:
        ids = ", ".join(s["id"] for s in notes)
        print(f"[FAIL] unknown sector '{sector}'. known: {ids}", file=sys.stderr)
        raise SystemExit(2)

    scored = []
    for ch in channels:
        score = 3
        if sector in ch.get("best_for_sectors", []):
            score += 2
        if sector in ch.get("weak_for_sectors", []):
            score -= 2
        if ch["id"] in sec.get("channel_bias", []):
            score += 1
        if ch["id"] in sec.get("avoid", []):
            score = 0
        scored.append((score, ch))
    scored.sort(key=lambda pair: (-pair[0], pair[1]["min_budget"]))

    if fmt == "json":
        payload = [{"id": ch["id"], "fit_score": score, "role": ch["role"],
                    "min_budget": ch["min_budget"]} for score, ch in scored]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print(f"# {sec['name_zh']} 的渠道适配排序（5=强适配，0=回避）\n")
    print("| 适配度 | 渠道 | 角色 | 最低预算 AED |")
    print("|-------|------|------|-------------|")
    for score, ch in scored:
        print(f"| {score} | {ch['name_zh']} `{ch['id']}` | {ch['role']} | {ch['min_budget']} |")
    print(f"\n合规红线：{'、'.join(sec['compliance_flags'])}")


def print_list_sectors(fmt: str) -> None:
    notes = load("sector_notes.json")["sectors"]
    if fmt == "json":
        print(json.dumps([{"id": s["id"], "name_zh": s["name_zh"]} for s in notes],
                         ensure_ascii=False, indent=2))
        return
    for s in notes:
        print(f"- `{s['id']}`  {s['name_zh']}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Query the UAE market intelligence base.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("segments", help="list all audience segments")
    p.add_argument("--format", default="markdown", choices=["markdown", "json"])

    p = sub.add_parser("channel", help="show one channel")
    p.add_argument("--id", required=True)
    p.add_argument("--format", default="markdown", choices=["markdown", "json"])

    p = sub.add_parser("sector", help="show one sector")
    p.add_argument("--id", required=True)
    p.add_argument("--format", default="markdown", choices=["markdown", "json"])

    p = sub.add_parser("channels-for", help="rank channels for a sector")
    p.add_argument("--sector", required=True)
    p.add_argument("--format", default="markdown", choices=["markdown", "json"])

    p = sub.add_parser("list-sectors", help="list sector ids")
    p.add_argument("--format", default="markdown", choices=["markdown", "json"])

    args = parser.parse_args(argv)
    if args.cmd == "segments":
        print_segments(args.format)
    elif args.cmd == "channel":
        print_channel(args.format, args.id)
    elif args.cmd == "sector":
        print_sector(args.format, args.id)
    elif args.cmd == "channels-for":
        print_channels_for(args.format, args.sector)
    elif args.cmd == "list-sectors":
        print_list_sectors(args.format)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
