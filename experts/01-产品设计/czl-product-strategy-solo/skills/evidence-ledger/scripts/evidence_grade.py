#!/usr/bin/env python3
"""Evidence ledger grader.

Recomputes an A/B/C/D/X grade for every claim in a ledger CSV, then flags the
ledger problems that turn an opinion into a fake fact:
  - a claim with no locatable source
  - a ratio with no denominator
  - absolute wording riding on weak evidence
  - a source that has gone stale
  - a hand-written grade that does not match the evidence

Standard library only. Exit code 0 = no blocking issue, 1 = blocking issue.

Usage:
    python evidence_grade.py --csv ledger.csv [--today 2026-10-28] [--max-age 180] [--json]
"""
import argparse
import csv
import datetime as dt
import json
import os
import re
import sys

GRADE_ORDER = ["D", "C", "B", "A"]
RATIO_WORDS = ("%", "百分比", "比例", "占比", "率")
ABSOLUTE_WORDS = ("最好", "最强", "第一", "唯一", "必然", "绝对", "所有用户", "全部用户",
                  "百分之百", "100%", "无人能及", "业内首创")
CLAIM_WORDS = ("证明", "数据显示", "事实是", "已经验证", "结论是")
REQUIRED = ("id", "claim", "source_type", "source_ref", "observed_at",
            "scope", "verified", "grade")


def parse_date(text):
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return dt.datetime.strptime(text.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


def base_grade(source_type):
    st = (source_type or "").strip().lower()
    if st == "primary":
        return 3
    if st == "secondary":
        return 1
    if st == "anecdote":
        return 0
    return None


def grade_row(row, today, max_age):
    """Return (grade, reasons) for one ledger row."""
    reasons = []
    st = (row.get("source_type") or "").strip().lower()
    ref = (row.get("source_ref") or "").strip()
    if st == "none" or st == "":
        return "X", ["无来源类型，判 X"]
    if not ref or ref in ("-", "无", "未知", "N/A", "n/a"):
        return "X", ["无来源引用，判 X"]

    level = base_grade(st)
    if level is None:
        return "X", ["未知 source_type：%s" % st]

    if (row.get("verified") or "").strip().lower() != "yes":
        level -= 1
        reasons.append("未复核，降一级")

    observed = parse_date(row.get("observed_at", ""))
    if observed is None:
        level -= 1
        reasons.append("观测日期缺失或无法解析，降一级")
    elif (today - observed).days > max_age:
        level -= 1
        reasons.append("超过 %d 天，降一级" % max_age)

    scope = (row.get("scope") or "").strip()
    if not scope or scope in ("未知", "全部", "unknown", "-"):
        level -= 1
        reasons.append("覆盖范围不明，降一级")

    claim = row.get("claim", "") or ""
    sample = (row.get("sample") or "").strip()
    if any(w in claim for w in RATIO_WORDS) and not sample:
        level -= 1
        reasons.append("比例类主张缺分母/样本，降一级")

    level = max(0, min(3, level))
    return GRADE_ORDER[level], reasons


def check_ledger(rows, today, max_age):
    errors, warnings = [], []
    seen = {}
    computed = {}
    for idx, row in enumerate(rows, start=2):
        missing = [k for k in REQUIRED if not (row.get(k) or "").strip()]
        if missing:
            errors.append("第 %d 行缺少必填字段：%s" % (idx, ",".join(missing)))
        rid = (row.get("id") or "").strip()
        if not rid:
            rid = "第%d行" % idx
        elif rid in seen:
            errors.append("编号重复：%s（第 %d 行与第 %d 行）" % (rid, seen[rid], idx))
        else:
            seen[rid] = idx

        grade, reasons = grade_row(row, today, max_age)
        computed[rid] = grade
        hand = (row.get("grade") or "").strip().upper()
        if hand not in GRADE_ORDER and hand != "X":
            errors.append("%s 手填等级非法：%s" % (rid, hand))
        elif hand != grade:
            warnings.append("%s 手填 %s，复算 %s（%s）" % (rid, hand, grade, "；".join(reasons) or "无降级项"))

        claim = row.get("claim", "")
        if grade in ("D", "X") and any(w in claim for w in CLAIM_WORDS):
            errors.append("%s 用 %s 级证据写出结论式表述" % (rid, grade))
        if grade in ("C", "D", "X") and any(w in claim for w in ABSOLUTE_WORDS):
            errors.append("%s 绝对化措辞配 %s 级证据" % (rid, grade))
        if any(w in claim for w in RATIO_WORDS) and not (row.get("sample") or "").strip():
            errors.append("%s 比例类主张缺样本/分母" % rid)

        observed = parse_date(row.get("observed_at", ""))
        if observed and observed > today:
            errors.append("%s 观测日期晚于今天：%s" % (rid, row["observed_at"]))

    stats = {g: 0 for g in ("A", "B", "C", "D", "X")}
    for g in computed.values():
        stats[g] += 1
    return errors, warnings, stats, computed


def main(argv=None):
    ap = argparse.ArgumentParser(description="Evidence ledger grader")
    ap.add_argument("--csv", required=True, help="ledger csv path")
    ap.add_argument("--today", default=None, help="YYYY-MM-DD, defaults to system date")
    ap.add_argument("--max-age", type=int, default=180, help="staleness threshold in days")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if not os.path.exists(args.csv):
        print("[ERR] 找不到台账文件：%s" % args.csv)
        return 1
    today = parse_date(args.today) if args.today else dt.date.today()

    with open(args.csv, "r", encoding="utf-8-sig", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if any((v or "").strip() for v in r.values())]

    if not rows:
        print("[ERR] 台账为空")
        return 1

    errors, warnings, stats, computed = check_ledger(rows, today, args.max_age)
    total = sum(stats.values())
    usable = stats["A"] + stats["B"]

    if args.json:
        print(json.dumps({
            "total": total,
            "stats": stats,
            "usable_ratio": round(usable / total, 3) if total else 0,
            "grades": computed,
            "errors": errors,
            "warnings": warnings,
        }, ensure_ascii=False, indent=2))
    else:
        print("证据台账校验  total=%d" % total)
        print("  A=%d B=%d C=%d D=%d X=%d" % (stats["A"], stats["B"], stats["C"], stats["D"], stats["X"]))
        print("  可用于结论（A+B）占比：%.1f%%" % (100.0 * usable / total if total else 0))
        for w in warnings:
            print("[WARN] %s" % w)
        for e in errors:
            print("[ERR] %s" % e)
        print("结果：%s" % ("通过" if not errors else "存在 %d 个阻断项" % len(errors)))

    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
