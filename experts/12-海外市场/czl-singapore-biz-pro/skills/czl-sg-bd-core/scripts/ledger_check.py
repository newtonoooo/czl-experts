#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""证据台账校验器 — 检查等级、日期、URL、陈旧度与 D 级误用。

用法:
    python ledger_check.py ledger.csv
    python ledger_check.py ledger.csv --max-age-months 12

退出码: 0 全部通过（可有警告）; 1 存在错误; 2 参数或读取失败。
"""

import csv
import sys
from datetime import date

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REQUIRED = ["claim_id", "claim", "grade", "source_name",
            "published_or_accessed", "url", "status", "note"]
VALID_GRADE = {"A", "B", "C", "D"}
VALID_STATUS = {"已确认", "部分确认", "待确认", "已失效"}


def months_between(d1, d2):
    return (d2.year - d1.year) * 12 + (d2.month - d1.month) - (1 if d2.day < d1.day else 0)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    path = argv[1]
    max_age = 18
    if "--max-age-months" in argv:
        try:
            max_age = int(argv[argv.index("--max-age-months") + 1])
        except (IndexError, ValueError):
            print("错误: --max-age-months 需要整数")
            return 2

    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            rows = [r for r in reader if any((v or "").strip() for v in r.values())]
            header = reader.fieldnames or []
    except FileNotFoundError:
        print("错误: 找不到文件 %s" % path)
        return 2
    except Exception as e:
        print("错误: 读取失败 -> %s" % e)
        return 2

    errors, warnings = [], []
    missing_cols = [c for c in REQUIRED if c not in header]
    if missing_cols:
        errors.append("缺少列: %s" % ", ".join(missing_cols))

    seen = set()
    today = date.today()
    for i, row in enumerate(rows, start=2):
        cid = (row.get("claim_id") or "").strip()
        claim = (row.get("claim") or "").strip()
        grade = (row.get("grade") or "").strip().upper()
        source = (row.get("source_name") or "").strip()
        when = (row.get("published_or_accessed") or "").strip()
        url = (row.get("url") or "").strip()
        status = (row.get("status") or "").strip()
        note = (row.get("note") or "").strip()

        if not cid:
            errors.append("第 %d 行: claim_id 为空" % i)
        elif cid in seen:
            errors.append("第 %d 行: claim_id 重复 (%s)" % (i, cid))
        else:
            seen.add(cid)

        if not claim:
            errors.append("第 %d 行: claim 为空" % i)
        if grade not in VALID_GRADE:
            errors.append("第 %d 行: grade 必须为 A/B/C/D，当前 '%s'" % (i, grade))
        if grade == "D":
            errors.append("第 %d 行: D 级证据不得作为正文事实，请删除或改由 A/B/C 级支撑" % i)
        if not source:
            errors.append("第 %d 行: source_name 为空" % i)
        if status not in VALID_STATUS:
            warnings.append("第 %d 行: status '%s' 不在建议取值内" % (i, status))

        if not when:
            errors.append("第 %d 行: 日期为空" % i)
        else:
            try:
                d = date.fromisoformat(when)
                age = months_between(d, today)
                if age > max_age:
                    warnings.append("第 %d 行: 证据已 %d 个月，超过 %d 个月有效期（%s）" % (i, age, max_age, cid))
            except ValueError:
                errors.append("第 %d 行: 日期格式应为 YYYY-MM-DD，当前 '%s'" % (i, when))

        if url.upper() == "N/A":
            if not note:
                errors.append("第 %d 行: url 为 N/A 时必须在 note 说明获取方式" % i)
            elif grade == "A":
                warnings.append("第 %d 行: 无公开链接的证据不宜标 A 级" % i)
        elif not url.startswith(("http://", "https://")):
            errors.append("第 %d 行: url 需为 http(s) 链接或 N/A，当前 '%s'" % (i, url))
        elif grade == "C":
            warnings.append("第 %d 行: C 级证据（目录类）不得单独支撑结论（%s）" % (i, cid))

    print("台账: %s" % path)
    print("条目: %d 条｜错误: %d｜警告: %d" % (len(rows), len(errors), len(warnings)))
    print("=" * 52)
    for e in errors:
        print("  ✗ %s" % e)
    for w in warnings:
        print("  ! %s" % w)
    if not errors:
        print("  ✓ 结构与必填项通过")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
