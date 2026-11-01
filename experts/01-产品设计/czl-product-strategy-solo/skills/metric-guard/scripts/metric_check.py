#!/usr/bin/env python3
"""Metric definition and segment auditor.

Two jobs:
  1. --cards    audit metric definition cards: a rate with no denominator, a
                metric with no guardrail, a definition nobody could compute.
  2. --segments detect a Simpson reversal: every segment moves one way while the
                aggregate moves the other.

Standard library only. Exit code 0 = clean, 1 = blocking issue.

Usage:
    python metric_check.py --cards metric_cards.csv [--json]
    python metric_check.py --segments segments.csv [--json]
"""
import argparse
import csv
import json
import os
import sys

CARD_REQUIRED = ("metric", "definition", "population", "window", "source", "owner", "cadence")
RATE_HINTS = ("率", "占比", "比例", "%", "rate", "ratio", "share")
VAGUE = ("提升", "优化", "增长", "更好", "改善")


def check_cards(path):
    errors, warnings = [], []
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if (r.get("metric") or "").strip()]
    if not rows:
        return ["口径卡为空"], []

    for idx, row in enumerate(rows, start=2):
        name = row["metric"].strip()
        missing = [k for k in CARD_REQUIRED if not (row.get(k) or "").strip()]
        if missing:
            errors.append("%s（第 %d 行）缺少字段：%s" % (name, idx, ",".join(missing)))
        is_rate = any(h in name for h in RATE_HINTS)
        if is_rate:
            for field in ("numerator", "denominator"):
                if not (row.get(field) or "").strip():
                    errors.append("%s 是比率类指标但缺少 %s" % (name, field))
        if not (row.get("guardrail") or "").strip():
            errors.append("%s 没有护栏指标" % name)
        if not (row.get("threshold") or "").strip():
            warnings.append("%s 护栏没有阈值，护栏形同虚设" % name)
        if not (row.get("exclusions") or "").strip():
            errors.append("%s 没有排除项（内部号/测试号/机器人流量）" % name)
        definition = (row.get("definition") or "").strip()
        if any(w in definition for w in VAGUE) and not any(ch.isdigit() for ch in definition):
            warnings.append("%s 的定义含「提升/优化」类措辞且无数值，可能无法计算" % name)
        if len(definition) > 120:
            warnings.append("%s 的定义超过 120 字，可能混入了口径之外的说明" % name)
        if is_rate and (row.get("denominator") or "").strip() in ("用户数", "总数", "全部"):
            warnings.append("%s 分母定义过粗（%s），需写明活跃口径" % (name, row["denominator"].strip()))

    names = [r["metric"].strip() for r in rows]
    dupes = {n for n in names if names.count(n) > 1}
    for d in sorted(dupes):
        errors.append("指标重复定义：%s" % d)
    return errors, warnings


def _rate(k, n):
    return (float(k) / float(n)) if n else 0.0


def check_segments(path):
    errors, warnings = [], []
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if (r.get("segment") or "").strip()]
    if not rows:
        return ["分层数据为空"], []

    en = ek = cn = ck = 0.0
    per_segment = []
    for idx, row in enumerate(rows, start=2):
        try:
            a_n = float(row["exposed_n"]); a_k = float(row["exposed_k"])
            b_n = float(row["control_n"]); b_k = float(row["control_k"])
        except (KeyError, TypeError, ValueError):
            errors.append("第 %d 行数值无法解析，需要 exposed_n/exposed_k/control_n/control_k" % idx)
            continue
        if a_k > a_n or b_k > b_n:
            errors.append("第 %d 行事件数大于样本数" % idx)
        if a_n < 30 or b_n < 30:
            warnings.append("%s 样本过小（n=%d/%d），分层结论不可靠"
                            % (row["segment"].strip(), int(a_n), int(b_n)))
        en += a_n; ek += a_k; cn += b_n; ck += b_k
        per_segment.append((row["segment"].strip(), _rate(a_k, a_n), _rate(b_k, b_n)))

    if not per_segment:
        return errors or ["没有可用的分层行"], warnings

    overall_exp, overall_ctl = _rate(ek, en), _rate(ck, cn)
    overall_dir = 1 if overall_exp > overall_ctl else (-1 if overall_exp < overall_ctl else 0)
    dirs = [1 if e > c else (-1 if e < c else 0) for _, e, c in per_segment]

    print("整体：实验 %.2f%% vs 对照 %.2f%%（差 %+.2f 个百分点）"
          % (overall_exp * 100, overall_ctl * 100, (overall_exp - overall_ctl) * 100))
    for name, e, c in per_segment:
        print("  %-16s 实验 %.2f%%  对照 %.2f%%  差 %+.2f 个百分点"
              % (name, e * 100, c * 100, (e - c) * 100))

    non_zero = [d for d in dirs if d != 0]
    if overall_dir != 0 and non_zero and all(d == -overall_dir for d in non_zero):
        errors.append("辛普森反转：整体方向与全部分层方向相反，必须分层报告，不得只报整体")
    elif overall_dir != 0 and non_zero and any(d != overall_dir for d in non_zero):
        warnings.append("部分分层方向与整体不一致，报告中需说明结构变化")

    return errors, warnings


def main(argv=None):
    ap = argparse.ArgumentParser(description="Metric definition and segment auditor")
    ap.add_argument("--cards")
    ap.add_argument("--segments")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if not args.cards and not args.segments:
        print("[ERR] 需要 --cards 或 --segments")
        return 1

    errors, warnings, mode = [], [], ""
    if args.cards:
        if not os.path.exists(args.cards):
            print("[ERR] 找不到口径卡：%s" % args.cards)
            return 1
        mode = "cards"
        e, w = check_cards(args.cards)
        errors += e; warnings += w
    if args.segments:
        if not os.path.exists(args.segments):
            print("[ERR] 找不到分层数据：%s" % args.segments)
            return 1
        mode = (mode + "+segments") if mode else "segments"
        if not args.json:
            print("分层体检：%s" % os.path.basename(args.segments))
        e, w = check_segments(args.segments)
        errors += e; warnings += w

    if args.json:
        print(json.dumps({"mode": mode, "errors": errors, "warnings": warnings},
                         ensure_ascii=False, indent=2))
    else:
        if args.cards:
            print("口径卡校验：%s" % os.path.basename(args.cards))
        for w in warnings:
            print("[WARN] %s" % w)
        for e in errors:
            print("[ERR] %s" % e)
        print("结果：%s" % ("通过" if not errors else "存在 %d 个阻断项" % len(errors)))

    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
