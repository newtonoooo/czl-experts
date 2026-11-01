#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_calendar.py - 把选题或笔记卡排成发布日历

做三件事：按产能铺日期、同素材自动拉开间隔、留出空白位。

用法：
    python build_calendar.py 选题.csv --start 2026-11-01 --per-week 3 --days 30 --out 日历.csv
    python build_calendar.py 选题.csv --start 2026-11-01 --per-week 3 --md 日历.md
    python build_calendar.py 选题.csv --start 2026-11-01 --per-week 5 --rest-day 6

输入 CSV 至少要有「选题」列（或「标题」列）。可识别列：
    选题 / 标题 / 角度 / 骨架 / 素材来源 / 优先级 / 时段 / 备注

退出码：0 = 成功；1 = 没有任何可排内容；2 = 输入错误
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
from collections import defaultdict
from pathlib import Path

VERSION = "1.0.0"

SLOT_OFFSETS = {
    1: [2],
    2: [1, 4],
    3: [1, 3, 5],
    4: [1, 2, 4, 5],
    5: [1, 2, 3, 4, 5],
    6: [0, 1, 2, 3, 4, 5],
    7: [0, 1, 2, 3, 4, 5, 6],
}

WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}
SOURCE_GAP_DAYS = 5


def read_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = [dict(r) for r in reader]
        fieldnames = reader.fieldnames or []
    return rows, fieldnames


def pick(record, *keys):
    for key in keys:
        value = (record.get(key) or "").strip()
        if value:
            return value
    return ""


def priority_key(record):
    value = pick(record, "优先级", "priority").upper()
    return PRIORITY_ORDER.get(value, 9)


def build_slots(start, days, per_week, rest_day):
    """按周铺发布位。周一为一周起点。"""
    offsets = SLOT_OFFSETS[per_week]
    first_monday = start - dt.timedelta(days=start.weekday())
    end = start + dt.timedelta(days=days)
    slots = []
    week = 0
    while True:
        week_monday = first_monday + dt.timedelta(weeks=week)
        for offset in offsets:
            day = week_monday + dt.timedelta(days=offset)
            if day < start or day >= end:
                continue
            if rest_day is not None and day.weekday() == rest_day:
                continue
            slots.append(day)
        if week_monday >= end:
            break
        week += 1
    return sorted(set(slots))


def time_slot_for(day):
    return "10:00-11:30" if day.weekday() >= 5 else "19:30-21:30"


def schedule(rows, slots):
    pool = list(rows)
    last_date = {}
    placed = []
    warnings = []

    for slot in slots:
        if not pool:
            break
        chosen_index = None
        for idx, record in enumerate(pool):
            source = pick(record, "素材来源", "素材命中", "source")
            if not source:
                chosen_index = idx
                break
            last = last_date.get(source)
            if last is None or (slot - last).days >= SOURCE_GAP_DAYS:
                chosen_index = idx
                break
        if chosen_index is None:
            chosen_index = 0
            source = pick(pool[0], "素材来源", "素材命中", "source")
            warnings.append(
                f"{slot.isoformat()} 素材 {source} 与上一篇间隔不足 {SOURCE_GAP_DAYS} 天，已硬排，建议换角度或补素材"
            )

        record = pool.pop(chosen_index)
        source = pick(record, "素材来源", "素材命中", "source")
        if source:
            last_date[source] = slot
        placed.append((slot, record))

    for record in pool:
        warnings.append(f"未排入：{pick(record, '选题', '标题') or '（无标题）'}")
    return placed, warnings


def source_stats(placed):
    counter = defaultdict(int)
    for _, record in placed:
        source = pick(record, "素材来源", "素材命中", "source")
        if source:
            counter[source] += 1
    return counter


def write_csv(path, placed):
    header = ["日期", "星期", "时段", "标题", "选题", "角度", "骨架", "素材来源", "状态", "备注"]
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        for day, record in placed:
            writer.writerow([
                day.isoformat(),
                WEEKDAY_CN[day.weekday()],
                pick(record, "时段") or time_slot_for(day),
                pick(record, "标题"),
                pick(record, "选题"),
                pick(record, "角度"),
                pick(record, "骨架"),
                pick(record, "素材来源", "素材命中", "source"),
                "待发",
                pick(record, "备注"),
            ])


def write_md(path, placed, start, days):
    lines = [f"# 发布日历（{start.isoformat()} 起 {days} 天）", "", "| 日期 | 星期 | 时段 | 标题 / 选题 | 角度 | 素材 |", "|---|---|---|---|---|---|"]
    for day, record in placed:
        title = pick(record, "标题") or pick(record, "选题")
        lines.append(
            "| {d} | {w} | {t} | {title} | {angle} | {src} |".format(
                d=day.isoformat(), w=WEEKDAY_CN[day.weekday()],
                t=pick(record, "时段") or time_slot_for(day),
                title=title, angle=pick(record, "角度"), src=pick(record, "素材来源", "素材命中", "source"),
            )
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="生成小红书发布日历")
    parser.add_argument("csv", help="选题矩阵或笔记索引 CSV")
    parser.add_argument("--start", required=True, help="起始日期 YYYY-MM-DD")
    parser.add_argument("--per-week", type=int, default=3, help="每周产能 1-7（默认 3）")
    parser.add_argument("--days", type=int, default=30, help="周期天数（默认 30）")
    parser.add_argument("--out", help="输出 CSV 路径")
    parser.add_argument("--md", help="同时输出 Markdown 表格")
    parser.add_argument("--rest-day", type=int, default=None, help="固定不发的星期：0=周一 … 6=周日")
    args = parser.parse_args(argv)

    try:
        start = dt.date.fromisoformat(args.start)
    except ValueError:
        print(f"❌ --start 需要 YYYY-MM-DD 格式，收到：{args.start}", file=sys.stderr)
        return 2

    if not 1 <= args.per_week <= 7:
        print("❌ --per-week 需在 1-7 之间", file=sys.stderr)
        return 2

    source_path = Path(args.csv)
    if not source_path.exists():
        print(f"❌ 文件不存在：{source_path}", file=sys.stderr)
        return 2

    try:
        rows, fieldnames = read_rows(source_path)
    except (OSError, csv.Error, UnicodeDecodeError) as exc:
        print(f"❌ 读取 CSV 失败：{exc}", file=sys.stderr)
        return 2

    if not rows:
        print("❌ CSV 里没有数据行", file=sys.stderr)
        return 2
    if not any(key in fieldnames for key in ("选题", "标题")):
        print("❌ CSV 缺少「选题」或「标题」列", file=sys.stderr)
        return 2

    rows = [r for r in rows if pick(r, "选题", "标题")]
    if not rows:
        print("❌ 所有行的选题列都是空的", file=sys.stderr)
        return 1

    rows.sort(key=priority_key)
    slots = build_slots(start, args.days, args.per_week, args.rest_day)
    if not slots:
        print("❌ 周期内没有任何可用发布位，检查 --days 与 --rest-day", file=sys.stderr)
        return 1

    placed, warnings = schedule(rows, slots)
    out_path = Path(args.out) if args.out else source_path.with_name("日历.csv")
    write_csv(out_path, placed)
    if args.md:
        write_md(Path(args.md), placed, start, args.days)

    stats = source_stats(placed)
    total_days = args.days
    blank = total_days - len(placed)
    print(f"发布日历 v{VERSION}")
    print(f"区间：{start.isoformat()} 起 {total_days} 天 · 每周 {args.per_week} 篇 · 发布位 {len(slots)} 个")
    print(f"排入 {len(placed)} 篇 · 未排 {len(rows) - len(placed)} 篇 · 无发布日 {blank} 天")
    if stats:
        reuse = "、".join(f"{k}×{v}" for k, v in sorted(stats.items()))
        print(f"素材复用：{reuse}")
        over = [k for k, v in stats.items() if v > 1]
        if len(over) * 1.0 / max(len(stats), 1) > 0.4:
            print("提示：同素材复用占比超过 40%，账号会显得单薄，建议补料。")
    if warnings:
        print("\n需要处理：")
        for line in warnings:
            print(f"  · {line}")
    print(f"\n已写出：{out_path.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
