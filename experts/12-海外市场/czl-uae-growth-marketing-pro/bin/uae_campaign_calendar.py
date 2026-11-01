#!/usr/bin/env python3
"""
uae_campaign_calendar.py - Build a UAE campaign timeline around real local dates.

Ramadan and the two Eids follow the Islamic (Hijri) calendar and are confirmed
by official moon sighting, so every Hijri-derived date here is an ESTIMATE.
The script prints that caveat every time, and accepts --ramadan-start so an
announced date always overrides the estimate.

Usage
-----
    python bin/uae_campaign_calendar.py --year 2027
    python bin/uae_campaign_calendar.py --year 2027 --ramadan-start 2027-02-08
    python bin/uae_campaign_calendar.py --year 2027 --format ics --out campaign.ics

Exit codes: 0 ok, 2 bad input.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

# Estimated Gregorian anchors. Subject to official announcement.
KNOWN = {
    2026: {"ramadan_start": "2026-02-18", "eid_fitr": "2026-03-20", "eid_adha": "2026-05-27",
           "hijri_new_year": "2026-06-17", "mawlid": "2026-08-26"},
    2027: {"ramadan_start": "2027-02-08", "eid_fitr": "2027-03-10", "eid_adha": "2027-05-17",
           "hijri_new_year": "2027-06-07", "mawlid": "2027-08-15"},
    2028: {"ramadan_start": "2028-01-28", "eid_fitr": "2028-02-27", "eid_adha": "2028-05-05",
           "hijri_new_year": "2028-05-26", "mawlid": "2028-08-04"},
    2029: {"ramadan_start": "2029-01-16", "eid_fitr": "2029-02-15", "eid_adha": "2029-04-24",
           "hijri_new_year": "2029-05-15", "mawlid": "2029-07-24"},
    2030: {"ramadan_start": "2030-01-06", "eid_fitr": "2030-02-05", "eid_adha": "2030-04-14",
           "hijri_new_year": "2030-05-04", "mawlid": "2030-07-13"},
}

HIJRI_DRIFT_DAYS = 10.9  # average annual backward drift of the Islamic year


def estimate_for(year: int) -> dict:
    """Anchor on the nearest known year and drift backwards/forwards."""
    if year in KNOWN:
        return {k: dt.date.fromisoformat(v) for k, v in KNOWN[year].items()}
    base_year = min(KNOWN, key=lambda y: abs(y - year))
    delta_days = int(round((base_year - year) * HIJRI_DRIFT_DAYS))
    base = {k: dt.date.fromisoformat(v) for k, v in KNOWN[base_year].items()}
    return {k: v + dt.timedelta(days=delta_days) for k, v in base.items()}


def shift_to_workday(day: dt.date) -> dt.date:
    """Move a deadline back to the nearest Monday-Thursday working day.

    The UAE weekend is Saturday-Sunday and Friday is a half day for government,
    so a Friday deadline is not a safe cut-off for a media lock. Deadlines move
    earlier, never later.
    """
    while day.weekday() >= 4:  # 4 = Friday, 5 = Saturday, 6 = Sunday
        day -= dt.timedelta(days=1)
    return day


def build(year: int, ramadan_start: dt.date | None) -> dict:
    anchors = estimate_for(year)
    if ramadan_start:
        shift = ramadan_start - anchors["ramadan_start"]
        anchors = {k: v + shift for k, v in anchors.items()}

    ramadan_end = anchors["ramadan_start"] + dt.timedelta(days=29)
    national_day = dt.date(year, 12, 2)
    new_year = dt.date(year, 1, 1)
    school_return = dt.date(year, 8, 31)
    dsf_start = dt.date(year, 12, 15)  # typical window, confirmed annually

    windows = []

    def add(name: str, start: dt.date, end: dt.date, kind: str, action: str, tilt: str) -> None:
        windows.append({
            "name": name, "start": start.isoformat(), "end": end.isoformat(),
            "kind": kind, "action": action, "budget_tilt": tilt,
        })

    # Pre-Ramadan stocking window: the most expensive buying period of the year.
    add("斋月前备货窗口", anchors["ramadan_start"] - dt.timedelta(days=21),
        anchors["ramadan_start"] - dt.timedelta(days=1), "commerce",
        "锁量、备货、素材上线；这是全年竞价最激烈的窗口", "高（占全年 15~25%）")
    add("斋月期（夜间模式）", anchors["ramadan_start"], ramadan_end, "cultural",
        "排期重心移到 Iftar 后到 Suhoor；内容转向家庭、分享、克制", "中高")
    add("开斋节 Eid al-Fitr", anchors["eid_fitr"], anchors["eid_fitr"] + dt.timedelta(days=2),
        "commerce", "节前一周是转化峰值，节中做品牌不做硬卖", "高（峰值）")
    add("宰牲节 Eid al-Adha", anchors["eid_adha"], anchors["eid_adha"] + dt.timedelta(days=3),
        "cultural", "礼品与食品强，旅游分流；避免硬促销", "中")
    add("伊斯兰新年", anchors["hijri_new_year"], anchors["hijri_new_year"], "cultural",
        "低调问候即可，不宜做促销", "低")
    add("先知诞辰 Mawlid", anchors["mawlid"], anchors["mawlid"], "cultural",
        "仅品牌问候，禁止任何促销绑定", "极低")
    add("阿联酋国庆日", national_day, national_day + dt.timedelta(days=1), "national",
        "爱国表达需真诚；蹭热点风险极高，必须过合规审查", "中")
    add("开学季", school_return - dt.timedelta(days=14), school_return + dt.timedelta(days=14),
        "commerce", "教育、3C、家居受益；家庭支出转移", "中")
    add("迪拜购物节 DSF（预估窗口）", dsf_start, dt.date(year + 1, 1, 15), "commerce",
        "零售与旅游双高峰；需提前 6~8 周备货与素材", "高")
    add("新年", new_year, new_year, "commerce", "跨年内容 + 年度规划发布", "低")

    windows.sort(key=lambda w: w["start"])

    # Backward milestones for the highest-priority commerce window in the year.
    milestones = []
    anchor_window = (next((w for w in windows if w["kind"] == "commerce" and w["budget_tilt"].startswith("高")), None)
                     or next((w for w in windows if w["kind"] == "commerce"), windows[0]))
    anchor_start = dt.date.fromisoformat(anchor_window["start"])
    for label, days_before in (("素材锁定", 42), ("预算与媒体锁定", 28), ("上线预热", 14)):
        milestones.append({
            "label": label,
            "date": shift_to_workday(anchor_start - dt.timedelta(days=days_before)).isoformat(),
            "anchor": anchor_window["name"],
        })

    return {
        "year": year,
        "hijri_basis": "estimated",
        "ramadan_start": anchors["ramadan_start"].isoformat(),
        "ramadan_end": ramadan_end.isoformat(),
        "windows": windows,
        "milestones": milestones,
        "caveats": [
            "斋月、开斋节、宰牲节、伊斯兰新年、先知诞辰均为估算值，以官方观月公告为准。",
            "获得官方日期后，用 --ramadan-start 覆盖，全部节点会自动平移。",
            "DSF 与开学季为典型窗口，每年实际日期以官方公布为准。",
            "阿联酋周末为周六至周日，且周五为政府半日，截止日已回退至最近的周一至周四。",
        ],
    }


def to_markdown(cal: dict) -> str:
    lines = [f"## {cal['year']} 年阿联酋投放节点\n"]
    lines.append(f"斋月估算：{cal['ramadan_start']} → {cal['ramadan_end']}（以官方观月为准）\n")
    lines.append("| 窗口 | 起 | 止 | 类型 | 动作 | 预算倾斜 |")
    lines.append("|------|----|----|------|------|---------|")
    for w in cal["windows"]:
        lines.append(f"| {w['name']} | {w['start']} | {w['end']} | {w['kind']} | {w['action']} | {w['budget_tilt']} |")

    lines.append("\n### 倒推里程碑\n")
    lines.append("| 节点 | 日期 | 锚定窗口 |")
    lines.append("|------|------|---------|")
    for m in cal["milestones"]:
        lines.append(f"| {m['label']} | {m['date']} | {m['anchor']} |")

    lines.append("\n### 口径说明\n")
    for c in cal["caveats"]:
        lines.append(f"- {c}")
    return "\n".join(lines)


def to_ics(cal: dict) -> str:
    stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    out = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//czl-uae-growth-marketing-pro//EN", "CALSCALE:GREGORIAN"]
    for i, w in enumerate(cal["windows"]):
        start = dt.date.fromisoformat(w["start"])
        end = dt.date.fromisoformat(w["end"]) + dt.timedelta(days=1)
        out += [
            "BEGIN:VEVENT",
            f"UID:uae-{cal['year']}-{i}@czl-uae-growth-marketing-pro",
            f"DTSTAMP:{stamp}Z",
            f"DTSTART;VALUE=DATE:{start.strftime('%Y%m%d')}",
            f"DTEND;VALUE=DATE:{end.strftime('%Y%m%d')}",
            f"SUMMARY:{w['name']}",
            f"DESCRIPTION:{w['action']} / 预算倾斜：{w['budget_tilt']}",
            "END:VEVENT",
        ]
    out.append("END:VCALENDAR")
    return "\r\n".join(out)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="UAE campaign calendar builder.")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--ramadan-start", help="official Ramadan start, YYYY-MM-DD; overrides the estimate")
    parser.add_argument("--format", default="markdown", choices=["markdown", "json", "ics"])
    parser.add_argument("--out", help="write output to this file instead of stdout")
    args = parser.parse_args(argv)

    if not 2024 <= args.year <= 2035:
        print("[FAIL] --year must be between 2024 and 2035", file=sys.stderr)
        return 2

    override = None
    if args.ramadan_start:
        try:
            override = dt.date.fromisoformat(args.ramadan_start)
        except ValueError:
            print("[FAIL] --ramadan-start must be YYYY-MM-DD", file=sys.stderr)
            return 2
        if override.year != args.year:
            print("[WARN] --ramadan-start year differs from --year; nodes will shift", file=sys.stderr)

    cal = build(args.year, override)

    if args.format == "json":
        payload = json.dumps(cal, ensure_ascii=False, indent=2)
    elif args.format == "ics":
        payload = to_ics(cal)
    else:
        payload = to_markdown(cal)

    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
        print(f"[OK] written to {args.out}")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
