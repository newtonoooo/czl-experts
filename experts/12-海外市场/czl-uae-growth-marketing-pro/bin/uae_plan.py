#!/usr/bin/env python3
"""
uae_plan.py - Deterministic channel budget model for the UAE market.

This is the computational core of the W3 Spend architecture workflow. It turns
(budget, objective, audience, sector, market) into a channel mix with exact
integer allocation, expected impression/clicks ranges, and a sensitivity band.

Design rules encoded here
-------------------------
1. The allocation always sums exactly to (budget - test reserve). No rounding drift.
2. Budget tier caps the number of channels: small budgets are not spread thin.
3. A trust channel is mandatory once budget >= 50,000 AED.
4. Conversion objectives always keep at least one conversion channel.
5. Every number that leaves this script carries a stated assumption.

Usage
-----
    python bin/uae_plan.py --budget 300000 --objective awareness \
        --audience core --sector beauty --market uae_wide

    python bin/uae_plan.py --budget 300000 --objective conversion \
        --audience expand --sector ecommerce --format json

Exit codes: 0 ok, 2 invalid input, 4 data problem.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "skills" / "uae-market-intel" / "data" / "channel_catalog.json"

OBJECTIVES = ("awareness", "consideration", "conversion", "retention")
AUDIENCES = ("core", "expand", "opportunity", "mixed")
MARKETS = ("dubai", "abu_dhabi", "sharjah", "uae_wide")

# Role weight per objective: how the budget splits across trust / discovery / conversion.
ROLE_WEIGHTS = {
    "awareness":     {"trust": 0.20, "discovery": 0.65, "conversion": 0.15},
    "consideration": {"trust": 0.25, "discovery": 0.50, "conversion": 0.25},
    "conversion":    {"trust": 0.15, "discovery": 0.30, "conversion": 0.55},
    "retention":     {"trust": 0.50, "discovery": 0.15, "conversion": 0.35},
}

# Which channels each audience tier leans on.
AUDIENCE_PREFERENCE = {
    "core":        {"snapchat", "instagram_reels", "kol_koc", "whatsapp_business", "google_search_brand"},
    "expand":      {"tiktok", "meta_conversion", "retail_media", "google_search_performance", "youtube"},
    "opportunity": {"instagram_reels", "tiktok", "google_search_brand", "kol_koc", "ooh"},
    "mixed":       set(),
}

# Market adjustments. Dubai and Abu Dhabi carry the premium inventory.
MARKET_MULTIPLIER = {
    "dubai":     {"ooh": 1.15, "kol_koc": 1.10, "retail_media": 1.05},
    "abu_dhabi": {"ooh": 1.05, "local_media_pr": 1.10, "linkedin": 1.10},
    "sharjah":   {"ooh": 0.85, "retail_media": 0.90},
    "uae_wide":  {},
}

FREQUENCY_ASSUMPTION = 3.2
CTR_ASSUMPTION = 0.02
TEST_RESERVE_DEFAULT = 0.10


def budget_tier(budget: float) -> int:
    """Max number of channels the budget can realistically sustain."""
    if budget < 50000:
        return 2
    if budget <= 300000:
        return 4
    return 6


def load_channels() -> list[dict]:
    if not CATALOG.exists():
        print(f"[FAIL] channel catalog missing: {CATALOG}", file=sys.stderr)
        raise SystemExit(4)
    try:
        return json.loads(CATALOG.read_text(encoding="utf-8"))["channels"]
    except (json.JSONDecodeError, KeyError) as exc:
        print(f"[FAIL] channel catalog unreadable: {exc}", file=sys.stderr)
        raise SystemExit(4)


def load_sector_bias(sector: str) -> tuple[set, set]:
    """Return (preferred, avoided) channel ids for a sector. Unknown sector -> empty."""
    path = ROOT / "skills" / "uae-market-intel" / "data" / "sector_notes.json"
    try:
        sectors = json.loads(path.read_text(encoding="utf-8"))["sectors"]
    except (OSError, json.JSONDecodeError, KeyError):
        return set(), set()
    hit = next((s for s in sectors if s["id"] == sector), None)
    if not hit:
        return set(), set()
    return set(hit.get("channel_bias", [])), set(hit.get("avoid", []))


def score_channel(ch: dict, objective: str, audience: str, sector: str,
                  market: str, preferred: set, avoided: set) -> float:
    if ch["id"] in avoided:
        return 0.0
    role_weight = ROLE_WEIGHTS[objective][ch["role"]]
    fit = 3.0
    if sector in ch.get("best_for_sectors", []):
        fit += 2.0
    if sector in ch.get("weak_for_sectors", []):
        fit -= 2.0
    if ch["id"] in preferred:
        fit += 1.0

    audience_mult = 1.30 if ch["id"] in AUDIENCE_PREFERENCE[audience] else 1.0
    market_mult = MARKET_MULTIPLIER.get(market, {}).get(ch["id"], 1.0)

    return max(0.0, role_weight * fit * audience_mult * market_mult)


def required_roles(budget: float, objective: str) -> list[str]:
    """Roles that must be covered, in priority order."""
    roles = []
    if objective in ("awareness", "consideration"):
        roles.append("discovery")
    if budget >= 50000:
        roles.append("trust")
    if objective == "conversion":
        roles.append("conversion")
    if objective == "retention":
        roles.append("trust")
    if objective == "awareness":
        roles.append("conversion")
    return roles


def select_channels(scored: list[tuple[float, dict]], budget: float,
                    tier: int, objective: str) -> list[tuple[float, dict]]:
    """Pick channels: required roles first, then fill by score. Never exceeds tier."""
    affordable = [(s, ch) for s, ch in scored if s > 0 and ch["min_budget"] <= budget]
    affordable.sort(key=lambda pair: (-pair[0], pair[1]["min_budget"]))
    if not affordable:
        return []

    picked: list[tuple[float, dict]] = []
    picked_ids: set[str] = set()

    for role in required_roles(budget, objective):
        if len(picked) >= tier:
            break
        if any(ch["role"] == role for _, ch in picked):
            continue
        best = next((p for p in affordable if p[1]["role"] == role
                     and p[1]["id"] not in picked_ids), None)
        if best:
            picked.append(best)
            picked_ids.add(best[1]["id"])

    for candidate in affordable:
        if len(picked) >= tier:
            break
        if candidate[1]["id"] not in picked_ids:
            picked.append(candidate)
            picked_ids.add(candidate[1]["id"])

    picked.sort(key=lambda pair: (-pair[0], pair[1]["min_budget"]))
    return picked


def allocate(picked: list[tuple[float, dict]], total: int, objective: str) -> list[tuple[dict, int]]:
    """Two-level allocation: budget follows ROLE_WEIGHTS, then channel score within role.

    The integer sum always equals `total` exactly (largest-remainder rounding).
    """
    if not picked or total <= 0:
        return []

    by_role: dict[str, list[tuple[float, dict]]] = {}
    for score, ch in picked:
        by_role.setdefault(ch["role"], []).append((score, ch))

    weights = ROLE_WEIGHTS[objective]
    present_weight = sum(weights[role] for role in by_role)
    if present_weight <= 0:
        present_weight = len(by_role)

    raw: list[tuple[dict, float]] = []
    for role, items in by_role.items():
        role_budget = total * (weights[role] / present_weight)
        role_score = sum(s for s, _ in items)
        for score, ch in items:
            raw.append((ch, role_budget * score / role_score if role_score else role_budget / len(items)))

    floors = [(ch, int(math.floor(amount))) for ch, amount in raw]
    remainder = total - sum(amount for _, amount in floors)
    order = sorted(range(len(raw)), key=lambda i: raw[i][1] - math.floor(raw[i][1]), reverse=True)
    result = [[ch, amount] for ch, amount in floors]
    for i in order[:remainder]:
        result[i][1] += 1

    result.sort(key=lambda pair: -pair[1])
    return [(ch, amount) for ch, amount in result]


def estimate(ch: dict, spend: int) -> dict:
    """Impression / click ranges from the channel's own CPM/CPC band."""
    cpm = ch.get("cpm_band")
    cpc = ch.get("cpc_band")

    if cpm:
        low = int(spend / cpm[1] * 1000)   # expensive end -> fewer impressions
        high = int(spend / cpm[0] * 1000)
        impressions = (low, high)
        clicks = (int(low * CTR_ASSUMPTION), int(high * CTR_ASSUMPTION))
        basis = f"CPM {cpm[0]}–{cpm[1]} AED"
    elif cpc:
        low_clicks = int(spend / cpc[1])
        high_clicks = int(spend / cpc[0])
        clicks = (low_clicks, high_clicks)
        impressions = (int(low_clicks / CTR_ASSUMPTION), int(high_clicks / CTR_ASSUMPTION))
        basis = f"CPC {cpc[0]}–{cpc[1]} AED, CTR 假设 {CTR_ASSUMPTION:.0%}"
    else:
        return {"impressions": None, "clicks": None, "reach": None, "basis": "无公开采买区间"}

    reach_low = int(impressions[0] / FREQUENCY_ASSUMPTION)
    reach_high = int(impressions[1] / FREQUENCY_ASSUMPTION)
    return {"impressions": impressions, "clicks": clicks,
            "reach": (reach_low, reach_high), "basis": basis}


def allocate_with_floor(picked: list[tuple[float, dict]], total: int,
                        objective: str) -> list[tuple[dict, int]]:
    """Allocate, then drop any channel that falls below its own minimum spend.

    A channel can survive selection (its minimum fits the total budget) yet still
    end up under-funded once the split is proportional. Rather than emit a plan
    that cannot be bought, we remove the offender and redistribute.
    """
    current = list(picked)
    for _ in range(len(picked) + 1):
        rows = allocate(current, total, objective)
        if not rows:
            return []
        floors = {ch["id"]: ch["min_budget"] for _, ch in current}
        under = [(ch, amount) for ch, amount in rows if amount < floors[ch["id"]]]
        if not under:
            return rows
        drop_ids = {ch["id"] for ch, _ in under}
        remaining = [(s, ch) for s, ch in current if ch["id"] not in drop_ids]
        if not remaining:
            return []
        current = remaining
    return allocate(current, total, objective)


def build_plan(budget: int, objective: str, audience: str, sector: str,
               market: str, reserve: float) -> dict:
    channels = load_channels()
    preferred, avoided = load_sector_bias(sector)
    tier = budget_tier(budget)

    scored = [(score_channel(ch, objective, audience, sector, market, preferred, avoided), ch)
              for ch in channels]
    picked = select_channels(scored, budget, tier, objective)
    if not picked:
        return {"error": "no channel fits this budget", "budget": budget, "tier": tier}

    test_reserve = int(round(budget * reserve))
    working = budget - test_reserve

    rows = []
    for ch, spend in allocate_with_floor(picked, working, objective):
        est = estimate(ch, spend)
        rows.append({
            "id": ch["id"],
            "name_zh": ch["name_zh"],
            "role": ch["role"],
            "spend": spend,
            "share": round(spend / working * 100, 1) if working else 0.0,
            "kpi_shape": ch["kpi_shape"],
            "creative_requirements": ch["creative_requirements"],
            "estimate": est,
        })

    if not rows:
        return {"error": "no channel can be funded above its minimum spend",
                "budget": budget, "tier": tier}

    total_imp_low = sum(r["estimate"]["impressions"][0] for r in rows if r["estimate"]["impressions"])
    total_imp_high = sum(r["estimate"]["impressions"][1] for r in rows if r["estimate"]["impressions"])
    total_reach_low = sum(r["estimate"]["reach"][0] for r in rows if r["estimate"]["reach"])
    total_reach_high = sum(r["estimate"]["reach"][1] for r in rows if r["estimate"]["reach"])

    return {
        "input": {"budget": budget, "objective": objective, "audience": audience,
                  "sector": sector, "market": market, "reserve_ratio": reserve},
        "tier": tier,
        "test_reserve": test_reserve,
        "working_budget": working,
        "channels": rows,
        "totals": {
            "spend": sum(r["spend"] for r in rows),
            "impressions": (total_imp_low, total_imp_high),
            "reach": (total_reach_low, total_reach_high),
            "frequency_assumption": FREQUENCY_ASSUMPTION,
        },
        "assumptions": [
            "CPM/CPC 取自本地知识库采买区间，属建模假设，须以平台实时报价校准。",
            f"频次假设 {FREQUENCY_ASSUMPTION}，用于由曝光推导触达。",
            f"点击率假设 {CTR_ASSUMPTION:.0%}，仅用于仅有 CPC 数据的渠道。",
            "触达为各渠道简单加总，未去重；真实跨渠道去重触达低于此值。",
        ],
    }


def to_markdown(plan: dict) -> str:
    if "error" in plan:
        return f"## 无法建模\n\n{plan['error']}（预算 {plan['budget']} AED，渠道上限 {plan['tier']}）"

    i = plan["input"]
    lines = []
    lines.append(f"## 渠道配比（预算 {i['budget']:,} AED · 目标 {i['objective']} · 人群 {i['audience']}）\n")
    lines.append(f"可投放 {plan['working_budget']:,} AED，测试预留 {plan['test_reserve']:,} AED"
                 f"（{i['reserve_ratio']:.0%}），渠道上限 {plan['tier']} 个。\n")
    lines.append("| 渠道 | 角色 | 预算 AED | 占可投放 | 预估曝光 | 预估触达 | 采买口径 |")
    lines.append("|------|------|---------:|-----:|---------|---------|---------|")
    for r in plan["channels"]:
        est = r["estimate"]
        imp = f"{est['impressions'][0]:,}–{est['impressions'][1]:,}" if est["impressions"] else "—"
        reach = f"{est['reach'][0]:,}–{est['reach'][1]:,}" if est["reach"] else "—"
        lines.append(f"| {r['name_zh']} `{r['id']}` | {r['role']} | {r['spend']:,} | {r['share']}% | {imp} | {reach} | {est['basis']} |")

    t = plan["totals"]
    lines.append(f"\n**合计**：{t['spend']:,} AED · 曝光 {t['impressions'][0]:,}–{t['impressions'][1]:,}"
                 f" · 触达 {t['reach'][0]:,}–{t['reach'][1]:,}（频次 {t['frequency_assumption']}）\n")

    lines.append("### 素材与 KPI 要求\n")
    lines.append("| 渠道 | KPI 形态 | 素材要求 |")
    lines.append("|------|---------|---------|")
    for r in plan["channels"]:
        lines.append(f"| {r['name_zh']} | {r['kpi_shape']} | {'；'.join(r['creative_requirements'])} |")

    lines.append("\n### 建模假设（对外交付时必须保留）\n")
    for a in plan["assumptions"]:
        lines.append(f"- {a}")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="UAE channel budget model.")
    parser.add_argument("--budget", type=int, required=True, help="total budget in AED")
    parser.add_argument("--objective", required=True, choices=OBJECTIVES)
    parser.add_argument("--audience", required=True, choices=AUDIENCES)
    parser.add_argument("--sector", required=True, help="sector id, see intel_query.py list-sectors")
    parser.add_argument("--market", default="uae_wide", choices=MARKETS)
    parser.add_argument("--reserve", type=float, default=TEST_RESERVE_DEFAULT,
                        help="share of budget held back for testing (0-1)")
    parser.add_argument("--format", default="markdown", choices=["markdown", "json"])
    args = parser.parse_args(argv)

    if args.budget <= 0:
        print("[FAIL] --budget must be positive", file=sys.stderr)
        return 2
    if not 0 <= args.reserve < 1:
        print("[FAIL] --reserve must be in [0, 1)", file=sys.stderr)
        return 2
    if args.budget < 10000:
        print("[WARN] budget below 10,000 AED: expect a single-channel plan", file=sys.stderr)

    plan = build_plan(args.budget, args.objective, args.audience,
                      args.sector, args.market, args.reserve)

    if "error" in plan:
        print(f"[FAIL] {plan['error']}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print(to_markdown(plan))

    # Self-check: the allocation must be exact. A silent drift here would corrupt
    # every downstream deliverable, so we fail loudly instead.
    if plan["totals"]["spend"] != plan["working_budget"]:
        print("[FAIL] allocation drift detected", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
