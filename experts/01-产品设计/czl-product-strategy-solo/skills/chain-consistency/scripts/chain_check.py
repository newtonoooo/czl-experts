#!/usr/bin/env python3
"""Cross-document chain checker.

Reads a deliverable folder, pulls every GOAL / EVD / REQ / AC / MET / RM / RSK
identifier out of the Markdown and CSV files, and reports the breaks that no
single document can reveal: a requirement with no acceptance criterion, a
committed roadmap item nobody wrote a stop-loss for, a metric referenced three
times but defined nowhere, the same target quoted as two different numbers.

Standard library only. Exit code 0 = no error-level break, 1 = at least one.

Usage:
    python chain_check.py <deliverable_dir> [--json]
"""
import argparse
import csv
import json
import os
import re
import sys

PATTERNS = {
    "GOAL": re.compile(r"\bGOAL-(\d{1,3})\b"),
    "EVD": re.compile(r"\bEVD-(\d{1,3})\b"),
    "REQ": re.compile(r"\bREQ-(\d{1,3})\b"),
    "AC": re.compile(r"\bAC-(\d{1,3})\.(\d{1,3})\b"),
    "MET": re.compile(r"\bMET-(\d{1,3})\b"),
    "RM": re.compile(r"\bRM-(\d{1,3})\b"),
    "RSK": re.compile(r"\bRSK-(\d{1,3})\b"),
    "DEC": re.compile(r"\bDEC-(\d{1,3})\b"),
}
MET_VALUE = re.compile(r"\bMET-(\d{1,3})\b[^\n]{0,60}?(\d+(?:\.\d+)?)\s*%")
DEFERRED = re.compile(r"deferred|cut|已砍|延后", re.I)
MITIGATION = ("缓解", "应对", "措施", "预案", "止损")


def read_text(path):
    try:
        return open(path, "r", encoding="utf-8-sig").read()
    except (UnicodeDecodeError, OSError):
        return ""


def collect_files(root):
    out = []
    for name in sorted(os.listdir(root)):
        path = os.path.join(root, name)
        if os.path.isfile(path) and name.lower().endswith((".md", ".csv")):
            out.append(path)
    return out


def csv_rows(path):
    text = read_text(path)
    if not text.strip():
        return []
    try:
        return [r for r in csv.DictReader(text.splitlines()) if any((v or "").strip() for v in r.values())]
    except csv.Error:
        return []


def analyse(root):
    files = collect_files(root)
    defs = {"GOAL": set(), "EVD": set(), "REQ": set(), "AC": set(),
            "MET": set(), "RM": set(), "RSK": set(), "DEC": set()}
    refs = {k: {} for k in defs}          # id -> set(file names)
    met_values = {}                        # MET id -> {value: [files]}
    deferred_reqs = set()
    committed_without_stop = []
    roadmap_reqs = set()
    rsk_lines = {}

    for path in files:
        base = os.path.basename(path)
        text = read_text(path)
        is_ledger = base.startswith("01")
        is_spec = base.startswith("02")
        is_capacity = base.startswith("03")
        is_metric = base.startswith("04")

        for kind, pat in PATTERNS.items():
            for m in pat.finditer(text):
                rid = "%s-%s" % (kind, m.group(1)) if kind != "AC" else "AC-%s.%s" % (m.group(1), m.group(2))
                refs[kind].setdefault(rid, set()).add(base)

        if is_spec:
            for m in PATTERNS["GOAL"].finditer(text):
                defs["GOAL"].add("GOAL-%s" % m.group(1))
            for m in PATTERNS["REQ"].finditer(text):
                defs["REQ"].add("REQ-%s" % m.group(1))
            for m in PATTERNS["AC"].finditer(text):
                defs["AC"].add("AC-%s.%s" % (m.group(1), m.group(2)))
            for line in text.splitlines():
                if DEFERRED.search(line):
                    for m in PATTERNS["REQ"].finditer(line):
                        deferred_reqs.add("REQ-%s" % m.group(1))

        if is_ledger:
            for m in PATTERNS["EVD"].finditer(text):
                defs["EVD"].add("EVD-%s" % m.group(1))

        if is_metric:
            for m in PATTERNS["MET"].finditer(text):
                defs["MET"].add("MET-%s" % m.group(1))

        for m in MET_VALUE.finditer(text):
            met_values.setdefault("MET-%s" % m.group(1), {}).setdefault(m.group(2), []).append(base)

        for line in text.splitlines():
            if "RSK-" in line:
                for m in PATTERNS["RSK"].finditer(line):
                    rsk_lines.setdefault("RSK-%s" % m.group(1), []).append((base, line))

        if path.lower().endswith(".csv") and is_capacity:
            for row in csv_rows(path):
                rid = (row.get("id") or "").strip()
                if not rid:
                    continue
                defs["RM"].add(rid)
                req = (row.get("req_id") or "").strip()
                if req:
                    refs["REQ"].setdefault(req, set()).add(base)
                    roadmap_reqs.add(req)
                if (row.get("status") or "").strip() == "committed" and not (row.get("stop_loss") or "").strip():
                    committed_without_stop.append(rid)

    for rid, entries in refs.items():
        if rid == "RSK":
            defs["RSK"] = set(rsk_lines)

    errors, warnings = [], []

    for rid in sorted(refs["REQ"]):
        if rid not in defs["REQ"]:
            errors.append("[C5] %s 被引用但规格里没有定义（见 %s）" % (rid, ",".join(sorted(refs["REQ"][rid]))))
    for rid in sorted(refs["MET"]):
        if rid not in defs["MET"]:
            errors.append("[C5] %s 被引用但口径表里没有定义（见 %s）" % (rid, ",".join(sorted(refs["MET"][rid]))))
    for rid in sorted(refs["EVD"]):
        if rid not in defs["EVD"]:
            errors.append("[C5] %s 被引用但证据台账里没有定义（见 %s）" % (rid, ",".join(sorted(refs["EVD"][rid]))))
    for rid in sorted(refs["RM"]):
        if rid not in defs["RM"]:
            errors.append("[C5] %s 被引用但排产表里没有定义" % rid)

    ac_parents = {rid.split(".")[0].replace("AC-", "REQ-") for rid in defs["AC"]}
    for rid in sorted(defs["REQ"]):
        if rid not in ac_parents:
            errors.append("[C1] %s 没有任何验收标准" % rid)
    for rid in sorted(defs["AC"]):
        parent = rid.split(".")[0].replace("AC-", "REQ-")
        if parent not in defs["REQ"]:
            errors.append("[C2] %s 挂在不存在的 %s 上" % (rid, parent))

    for rid in sorted(defs["REQ"]):
        if rid in deferred_reqs:
            continue
        if rid not in roadmap_reqs:
            errors.append("[C3] %s 既没进排产表，也没标 deferred" % rid)

    for rid in sorted(defs["MET"]):
        if rid not in refs["MET"] or len(refs["MET"][rid]) <= 1:
            warnings.append("[C4] %s 只在口径表出现，没有需求引用它（孤儿指标）" % rid)

    for rid, entries in sorted(rsk_lines.items()):
        joined = " ".join(line for _, line in entries)
        if not any(w in joined for w in MITIGATION):
            warnings.append("[C6] %s 没有写缓解/应对措施" % rid)

    for rid in committed_without_stop:
        errors.append("[C7] %s 已承诺但没有止损线" % rid)

    for met, values in sorted(met_values.items()):
        if len(values) > 1:
            detail = "；".join("%s%% 见 %s" % (v, ",".join(sorted(f))) for v, f in values.items())
            errors.append("[C8] %s 目标值在不同文档中不一致：%s" % (met, detail))

    stats = {
        "files": len(files),
        "defined": {k: len(v) for k, v in defs.items()},
        "errors": len(errors),
        "warnings": len(warnings),
    }
    return errors, warnings, stats


def main(argv=None):
    ap = argparse.ArgumentParser(description="Cross-document chain checker")
    ap.add_argument("directory")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if not os.path.isdir(args.directory):
        print("[ERR] 不是目录：%s" % args.directory)
        return 1

    errors, warnings, stats = analyse(args.directory)
    if args.json:
        print(json.dumps({"errors": errors, "warnings": warnings, "stats": stats},
                         ensure_ascii=False, indent=2))
    else:
        print("一致性校验  %s" % args.directory)
        print("  扫描 %d 个文件；定义 REQ=%d AC=%d MET=%d RM=%d EVD=%d RSK=%d"
              % (stats["files"], stats["defined"]["REQ"], stats["defined"]["AC"],
                 stats["defined"]["MET"], stats["defined"]["RM"],
                 stats["defined"]["EVD"], stats["defined"]["RSK"]))
        for w in warnings:
            print("[WARN] %s" % w)
        for e in errors:
            print("[ERR] %s" % e)
        print("结果：%s" % ("通过" if not errors else "存在 %d 个断链" % len(errors)))

    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
