#!/usr/bin/env python3
"""ledger.py - a wrong-answer ledger with spaced review, kept in one CSV.

The point of an error ledger is not to look at wrong answers again. It is to
make sure you meet the same idea again *after you have started to forget it*.
Copying a question and its answer into a notebook achieves neither. So each
entry stores two things a notebook usually drops:

    entry  - the line you should have started from ("从判别式入手"),
             not the final answer
    stage  - where the item sits in the 1 / 3 / 7 / 21 / 45 day ladder

Commands
--------
    # start a ledger and add items
    python ledger.py add --csv err.csv --knowledge 导数单调性 --code M \\
        --source 周测三 --prompt "已知 f(x)=x^3-3ax …" --entry "先分离参数再讨论"

    # what is due today (or on a given date)
    python ledger.py due --csv err.csv
    python ledger.py due --csv err.csv --today 2026-11-07

    # after the student redoes it
    python ledger.py review --csv err.csv --id 3 --result wrong
    python ledger.py review --csv err.csv --id 4 --result right

    # weekly report material
    python ledger.py stats --csv err.csv

Scheduling: an item is due 1, 3, 7, 21, then 45 days after each successful
review. A wrong answer drops it back to stage 0 (due tomorrow) and increments
`lapses` - an item that lapses three times is not a memory problem, it is a
concept problem, and `stats` says so.

Exit code: 0 ok, 2 bad input, 3 item not found.
"""

import argparse
import csv
import datetime as dt
import io
import os
import sys

FIELDS = ["id", "added", "knowledge", "code", "source", "prompt", "entry",
          "stage", "due", "lapses", "status"]
LADDER = [1, 3, 7, 21, 45]
CODE_NAMES = {"C": "概念", "M": "方法", "A": "运算", "W": "书写", "R": "读题"}


def today(override=None):
    if override:
        return dt.date.fromisoformat(override)
    return dt.date.today()


def read_rows(path):
    if not os.path.exists(path):
        return []
    with io.open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_rows(path, rows):
    with io.open(path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in FIELDS})


def next_id(rows):
    nums = [int(str(r.get("id", ""))) for r in rows if str(r.get("id", "")).isdigit()]
    return max(nums) + 1 if nums else 1


def cmd_add(args):
    rows = read_rows(args.csv)
    base = today(args.today)
    added = []
    for chunk in args.items or []:
        # format: knowledge|code|prompt|entry
        parts = [p.strip() for p in chunk.split("|")]
        if len(parts) < 4:
            print("ERROR: --item needs knowledge|code|prompt|entry (got %r)" % chunk,
                  file=sys.stderr)
            return 2
        knowledge, code, prompt, entry = parts[0], parts[1].upper()[:1], parts[2], parts[3]
        if code not in CODE_NAMES:
            print("ERROR: code must be one of C/M/A/W/R (got %r)" % parts[1],
                  file=sys.stderr)
            return 2
        rows.append({
            "id": str(next_id(rows)), "added": base.isoformat(), "knowledge": knowledge,
            "code": code, "source": args.source or "", "prompt": prompt,
            "entry": entry, "stage": 0,
            "due": (base + dt.timedelta(days=LADDER[0])).isoformat(),
            "lapses": 0, "status": "open",
        })
        added.append(rows[-1])
    write_rows(args.csv, rows)
    for r in added:
        print("added #%s  %s [%s]  下次复现 %s"
              % (r["id"], r["knowledge"], r["code"], r["due"]))
    print("共 %d 条，台账：%s" % (len(rows), args.csv))
    return 0


def cmd_due(args):
    rows = read_rows(args.csv)
    base = today(args.today)
    due = [r for r in rows
           if r.get("status") == "open" and r.get("due") and
           dt.date.fromisoformat(r["due"]) <= base]
    if not due:
        print("%s 没有到期项。" % base.isoformat())
        return 0
    print("%s 到期 %d 条（按逾期天数排序）\n" % (base.isoformat(), len(due)))
    due.sort(key=lambda r: r["due"])
    print("| id | 逾期 | 知识点 | 码 | 该从哪里切入 |")
    print("|---|---|---|---|---|")
    for r in due:
        late = (base - dt.date.fromisoformat(r["due"])).days
        print("| %s | %d 天 | %s | %s | %s |"
              % (r["id"], late, r["knowledge"], r["code"], r["entry"]))
    print("\n复现规则：先自己做一遍，不看答案。做完再 review。")
    return 0


def cmd_review(args):
    rows = read_rows(args.csv)
    target = None
    for r in rows:
        if r.get("id") == str(args.id):
            target = r
            break
    if target is None:
        print("ERROR: no item with id %s" % args.id, file=sys.stderr)
        return 3

    base = today(args.today)
    stage = int(target.get("stage") or 0)
    if args.result == "right":
        stage = min(stage + 1, len(LADDER) - 1)
        gap = LADDER[stage] if stage > 0 else LADDER[0]
        target["stage"] = stage
        target["due"] = (base + dt.timedelta(days=gap)).isoformat()
        if stage == len(LADDER) - 1 and args.close_at_end:
            target["status"] = "closed"
        print("#%s 通过 → 阶段 %d，%d 天后再见（%s）"
              % (target["id"], stage, gap, target["due"]))
    else:
        target["lapses"] = str(int(target.get("lapses") or 0) + 1)
        target["stage"] = 0
        target["due"] = (base + dt.timedelta(days=1)).isoformat()
        print("#%s 未通过 → 回到阶段 0，明天再来；累计卡住 %s 次"
              % (target["id"], target["lapses"]))
        if int(target["lapses"]) >= 3:
            print("  提示：同一条卡三次，多半不是记不住，是概念没立住（C 码）。"
                  "建议转 czl-math-decompose 重新拆一次，别再靠重复记忆。")
    if target.get("status") == "closed":
        print("  已归档（status=closed），不再进入到期列表。")
    write_rows(args.csv, rows)
    return 0


def cmd_stats(args):
    rows = read_rows(args.csv)
    if not rows:
        print("台账为空。")
        return 0
    base = today(args.today)
    open_rows = [r for r in rows if r.get("status") == "open"]
    by_code = {}
    by_know = {}
    lapsed = []
    for r in rows:
        by_code[r["code"]] = by_code.get(r["code"], 0) + 1
        k = r["knowledge"]
        by_know[k] = by_know.get(k, 0) + 1
        if int(r.get("lapses") or 0) >= 3:
            lapsed.append(r)

    overdue = [r for r in open_rows if r.get("due") and
               dt.date.fromisoformat(r["due"]) < base]

    print("# 错题台账周报（%s）\n" % base.isoformat())
    print("- 总条目：%d，未归档：%d，逾期未复现：%d" %
          (len(rows), len(open_rows), len(overdue)))
    print("- 按错因码：" + "，".join(
        "%s(%s) %d" % (c, CODE_NAMES.get(c, "?"), n)
        for c, n in sorted(by_code.items(), key=lambda kv: -kv[1])))
    print("- 按知识点：" + "，".join(
        "%s %d" % (k, n) for k, n in
        sorted(by_know.items(), key=lambda kv: -kv[1])[:6]))
    if lapsed:
        print("\n## 卡三次以上的（这不是记忆问题）\n")
        for r in lapsed:
            print("- #%s %s [%s] 卡住 %s 次 → 回到拆题，不要继续背"
                  % (r["id"], r["knowledge"], r["code"], r["lapses"]))
    if overdue:
        print("\n## 逾期最久的五条\n")
        overdue.sort(key=lambda r: r["due"])
        for r in overdue[:5]:
            late = (base - dt.date.fromisoformat(r["due"])).days
            print("- #%s %s，逾期 %d 天" % (r["id"], r["knowledge"], late))
    print("\n## 这周的动作\n")
    if overdue:
        print("1. 先清逾期的 %d 条，只做不看答案。" % len(overdue))
    if lapsed:
        print("2. 卡三次以上的 %d 条，各拆一次，拆完再入台账。" % len(lapsed))
    if not overdue and not lapsed:
        print("1. 台账干净，按到期日做即可，不加新题。")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Wrong-answer ledger with spaced review.")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("add", help="add one or more items")
    p.add_argument("--csv", required=True)
    p.add_argument("--source", help="where it came from, e.g. 周测三")
    p.add_argument("--item", action="append", dest="items",
                   help="knowledge|code|prompt|entry  (repeatable)")
    p.add_argument("--today", help="override today's date (YYYY-MM-DD)")

    p = sub.add_parser("due", help="list items due today")
    p.add_argument("--csv", required=True)
    p.add_argument("--today")

    p = sub.add_parser("review", help="record the result of a redo")
    p.add_argument("--csv", required=True)
    p.add_argument("--id", required=True)
    p.add_argument("--result", required=True, choices=["right", "wrong"])
    p.add_argument("--today")
    p.add_argument("--close-at-end", action="store_true",
                   help="archive the item once it reaches the last stage")

    p = sub.add_parser("stats", help="weekly report")
    p.add_argument("--csv", required=True)
    p.add_argument("--today")

    args = ap.parse_args(argv)
    if not args.cmd:
        ap.print_help()
        return 2
    handlers = {"add": cmd_add, "due": cmd_due, "review": cmd_review, "stats": cmd_stats}
    return handlers[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
