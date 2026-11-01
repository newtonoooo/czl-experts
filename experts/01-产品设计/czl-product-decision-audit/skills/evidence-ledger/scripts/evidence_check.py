#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""evidence_check.py - mechanical review of an evidence ledger.

Part of the Setpoint / 产品决策审校专家 package (czl-product-decision-audit).

Reads a CSV evidence ledger and reports problems that a human reviewer tends to
miss when the table gets long:

  1. illegal grade values
  2. overclaiming - quantifying / absolute wording backed only by D or X
  3. small-sample percentages
  4. missing counter-example search
  5. single-source dependency - one reference carrying too many claims
  6. conclusion grade above the strongest evidence (overreach)
  7. purpose threshold - invest / cut / public / price need A-D gates

Pure standard library. No network. No writes.

Usage
-----
    python evidence_check.py ledger.csv
    python evidence_check.py ledger.csv --conclusion-grade D --purpose invest
    python evidence_check.py ledger.csv --json

Exit codes
----------
    0  no errors (warnings allowed)
    1  at least one error
    2  usage / file problem
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys

GRADES = ["A", "B", "C", "D", "X"]

# Strength order for comparisons: higher is stronger.
STRENGTH = {"A": 5, "B": 4, "C": 3, "D": 2, "X": 1}

# Wording that requires stronger evidence than hearsay.
OVERCLAIM_WORDS = [
    "多数",
    "大部分",
    "大多数",
    "普遍",
    "绝大多数",
    "几乎所有",
    "所有用户",
    "全部用户",
    "显著",
    "明显",
    "大幅",
    "远超",
    "证明了",
    "充分说明",
    "一致认为",
    "公认",
    "毫无疑问",
]

# Minimum evidence strength for a given purpose.
PURPOSE_MIN = {
    "invest": "B",   # spend money / staff / a release
    "cut": "B",      # remove an existing capability
    "public": "C",   # say it outside the company (plus a date)
    "price": "B",    # change pricing
    "explore": "X",  # internal hypothesis only
}

REQUIRED_COLUMNS = ["id", "claim", "evidence_grade"]

SINGLE_SOURCE_LIMIT = 3  # one reference may carry at most this many claims


class Report:
    def __init__(self) -> None:
        self.errors = []
        self.warnings = []
        self.rows = 0
        self.grade_counts = {g: 0 for g in GRADES}

    def error(self, row_id, code, message):
        self.errors.append({"row": row_id, "code": code, "message": message})

    def warn(self, row_id, code, message):
        self.warnings.append({"row": row_id, "code": code, "message": message})

    @property
    def ok(self):
        return not self.errors

    def strongest_grade(self):
        best = None
        for g, n in self.grade_counts.items():
            if n and (best is None or STRENGTH[g] > STRENGTH[best]):
                best = g
        return best


def read_ledger(path):
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
        rows = [r for r in reader]
        fields = reader.fieldnames or []
    return rows, [f.strip() for f in fields]


def check_columns(fields, report):
    lower = [f.lower() for f in fields]
    missing = [c for c in REQUIRED_COLUMNS if c not in lower]
    if missing:
        report.error("-", "E_COLUMNS", "缺少必需列: " + ", ".join(missing))
        return False
    return True


def normalize(row):
    return {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}


def check_row(idx, row, report, source_use):
    rid = row.get("id") or f"row{idx}"
    claim = row.get("claim", "")
    grade = row.get("evidence_grade", "").upper()
    counter = row.get("counter_searched", "").lower()
    source = row.get("source_ref", "")
    sample_raw = row.get("sample_size", "")

    if not claim:
        report.error(rid, "E_EMPTY_CLAIM", "断言为空")
        return

    if grade not in GRADES:
        report.error(
            rid,
            "E_GRADE",
            f"证据等级 '{grade}' 不合法，只能是 A/B/C/D/X",
        )
        return

    report.grade_counts[grade] += 1

    # overclaim wording vs weak evidence
    if grade in ("D", "X"):
        hits = [w for w in OVERCLAIM_WORDS if w in claim]
        if hits:
            report.error(
                rid,
                "E_OVERCLAIM",
                f"{grade} 级证据却使用了量化/绝对化措辞: {'、'.join(hits)}",
            )

    # percentages need a sample
    if "%" in claim or "％" in claim:
        if not sample_raw:
            report.warn(rid, "W_PCT_NO_N", "断言含百分比但未填 sample_size")
        else:
            try:
                n = int(float(sample_raw))
            except ValueError:
                report.warn(rid, "W_SAMPLE_PARSE", f"sample_size 无法解析: {sample_raw}")
            else:
                if n < 30:
                    report.error(
                        rid,
                        "E_SMALL_N_PCT",
                        f"样本仅 {n}，不足以给出百分比结论，改写为人数",
                    )

    # counter-example discipline
    if counter not in ("yes", "no"):
        report.warn(rid, "W_COUNTER_BLANK", "counter_searched 未填写（应填 yes/no）")
    elif counter == "no" and grade in ("A", "B", "C"):
        report.warn(
            rid,
            "W_NO_COUNTER",
            "未做反例检索却给出 A/B/C 级结论，需注明检索范围",
        )

    # single-source dependency
    if source:
        source_use.setdefault(source, []).append(rid)


def check_conclusion(rows, report, conclusion_grade, purpose):
    if not conclusion_grade:
        return
    cg = conclusion_grade.upper()
    if cg not in GRADES:
        report.error("-", "E_CONCL_GRADE", f"结论等级 '{cg}' 不合法")
        return

    best = report.strongest_grade()
    if best and STRENGTH[cg] > STRENGTH[best]:
        report.error(
            "-",
            "E_OVERREACH",
            f"结论等级 {cg} 高于台账中最强证据 {best}，属于越级结论",
        )

    if purpose:
        need = PURPOSE_MIN.get(purpose)
        if need is None:
            report.error("-", "E_PURPOSE", f"未知用途 '{purpose}'")
        elif STRENGTH[cg] < STRENGTH[need]:
            report.error(
                "-",
                "E_THRESHOLD",
                f"用途 '{purpose}' 要求最低等级 {need}，当前结论等级 {cg} 不足",
            )


def summarize(report, strongest):
    lines = []
    total = report.rows
    lines.append(f"台账条目: {total}")
    dist = " / ".join(f"{g}:{n}" for g, n in report.grade_counts.items())
    lines.append(f"等级分布: {dist}")
    if strongest:
        lines.append(f"最强证据: {strongest}")
    weak_share = 0
    if total:
        weak = report.grade_counts["D"] + report.grade_counts["X"]
        weak_share = round(weak * 100.0 / total)
    lines.append(f"D+X 占比: {weak_share}%")
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Check an evidence ledger for overclaiming and overreach."
    )
    parser.add_argument("ledger", help="CSV 台账路径")
    parser.add_argument(
        "--conclusion-grade",
        default="",
        help="可选：本决策的结论等级（A/B/C/D/X），用于越级检查",
    )
    parser.add_argument(
        "--purpose",
        default="",
        choices=["", "invest", "cut", "public", "price", "explore"],
        help="可选：结论用途，用于等级门槛检查",
    )
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    parser.add_argument(
        "--strict", action="store_true", help="把警告也视为失败"
    )
    args = parser.parse_args(argv)

    report = Report()
    try:
        rows, fields = read_ledger(args.ledger)
    except FileNotFoundError:
        print(f"错误：找不到文件 {args.ledger}", file=sys.stderr)
        return 2
    except UnicodeDecodeError:
        print("错误：文件编码无法识别，请另存为 UTF-8", file=sys.stderr)
        return 2

    if not check_columns(fields, report):
        print("\n".join(e["message"] for e in report.errors), file=sys.stderr)
        return 2

    source_use = {}
    for i, raw in enumerate(rows, start=1):
        row = normalize(raw)
        if not any(row.values()):
            continue
        report.rows += 1
        check_row(i, row, report, source_use)

    for source, ids in source_use.items():
        if len(ids) > SINGLE_SOURCE_LIMIT:
            report.warn(
                "-",
                "W_SINGLE_SOURCE",
                f"来源 '{source}' 支撑了 {len(ids)} 条断言（{', '.join(ids)}），"
                f"存在单一来源依赖",
            )

    check_conclusion(rows, report, args.conclusion_grade, args.purpose)
    strongest = report.strongest_grade()

    if args.json:
        payload = {
            "ok": report.ok,
            "rows": report.rows,
            "grade_counts": report.grade_counts,
            "strongest": strongest,
            "errors": report.errors,
            "warnings": report.warnings,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("证据台账体检")
        print("=" * 40)
        for line in summarize(report, strongest):
            print(line)
        if report.errors:
            print(f"\n错误 {len(report.errors)} 条：")
            for e in report.errors:
                print(f"  [{e['row']}] {e['code']} {e['message']}")
        if report.warnings:
            print(f"\n提示 {len(report.warnings)} 条：")
            for w in report.warnings:
                print(f"  [{w['row']}] {w['code']} {w['message']}")
        if report.ok and not report.warnings:
            print("\n通过：未发现越级或越权表述。")
        elif report.ok:
            print("\n通过（有提示）：结论可以交付，建议处理提示项。")

    if not report.ok:
        return 1
    if args.strict and report.warnings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
