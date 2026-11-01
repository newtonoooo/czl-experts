#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""funnel.py — 追读漏斗核算（纯标准库，离线）

把后台的"每章阅读数"变成"从第几章开始掉、掉了多少、该往哪儿查"。

用法：
    python funnel.py --csv data.csv
    python funnel.py --json data.json
    python funnel.py --csv data.csv --json-out report.json --chapter-words 3000

输入格式（CSV，首行表头，缺列可省）：
    chapter,reads,finish
    1,12480,7310
    2,9021,5120
    ...
    reads  = 该章阅读人数（或阅读次数，全书统一口径即可）
    finish = 该章读完人数（可选；有它才能算完读率）

口径说明：
    追读率 = 下一章阅读 / 本章阅读。这是"看完这章还愿意点下一章"的最直接代理指标。
    首章留存 = 第 N 章阅读 / 第 1 章阅读。用来判断"整本书的漏斗宽不宽"。
    掉点   = 相邻两章追读率低于中位数的章节，按跌幅排序。

作者：虫志龙 <47190078@qq.com>
许可：随本专家包发布的原创代码，MIT。
"""

import argparse
import csv
import json
import os
import statistics
import sys


def load_csv(path):
    rows = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                ch = int(float(str(row.get("chapter", "")).strip()))
                reads = float(str(row.get("reads", "")).strip())
            except (TypeError, ValueError):
                continue
            fin = row.get("finish")
            try:
                fin = float(str(fin).strip()) if fin not in (None, "", "-") else None
            except ValueError:
                fin = None
            rows.append({"chapter": ch, "reads": reads, "finish": fin})
    rows.sort(key=lambda x: x["chapter"])
    return rows


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    if isinstance(d, dict):
        d = d.get("chapters") or d.get("data") or []
    rows = []
    for it in d:
        try:
            rows.append({
                "chapter": int(it["chapter"]),
                "reads": float(it["reads"]),
                "finish": float(it["finish"]) if it.get("finish") not in (None, "") else None,
            })
        except (KeyError, TypeError, ValueError):
            continue
    rows.sort(key=lambda x: x["chapter"])
    return rows


def analyze(rows):
    if len(rows) < 3:
        return {"ok": False, "error": "至少需要 3 章数据才能看出趋势"}

    ch1 = rows[0]["reads"] or 1
    out = []
    for i, r in enumerate(rows):
        prev = rows[i - 1] if i > 0 else None
        nxt = rows[i + 1] if i + 1 < len(rows) else None
        ret_prev = (r["reads"] / prev["reads"]) if prev and prev["reads"] else None
        ret_next = (nxt["reads"] / r["reads"]) if nxt and r["reads"] else None
        first_keep = r["reads"] / ch1
        comp = (r["finish"] / r["reads"]) if r["finish"] is not None and r["reads"] else None
        out.append({
            "chapter": r["chapter"],
            "reads": int(r["reads"]),
            "ret_from_prev": None if ret_prev is None else round(ret_prev, 4),
            "ret_to_next": None if ret_next is None else round(ret_next, 4),
            "first_keep": round(first_keep, 4),
            "complete": None if comp is None else round(comp, 4),
        })

    rets = [o["ret_to_next"] for o in out if o["ret_to_next"] is not None]
    med = statistics.median(rets) if rets else 0

    # 掉点：追读率低于中位数，按缺口排序
    drops = [o for o in out if o["ret_to_next"] is not None and o["ret_to_next"] < med]
    drops.sort(key=lambda o: o["ret_to_next"])
    for d in drops:
        d["gap"] = round(med - d["ret_to_next"], 4)

    # 阶段归因（只给方向，不给结论）
    def stage(ch):
        if ch <= 3:
            return "开篇三章", "读者在这里还没决定要不要留下，看第一章有没有具体异常、第二章规则是否兑现、第三章主角有没有主动选择"
        if ch <= 10:
            return "定档段", "读者已经接受设定，掉在这里通常是爽点兑现太慢或重复同一种打脸"
        if ch <= 30:
            return "单卷中段", "掉在这里多为支线跑偏、矛盾没有升级、配角戏压过主角"
        return "长线段", "掉在这里多为压力失效、主角失去目标、伏笔迟迟不收"

    for d in drops:
        name, hint = stage(d["chapter"])
        d["stage"] = name
        d["hint"] = hint

    total_drop = rows[-1]["reads"] / ch1 if ch1 else 0
    comp_all = None
    if all(r["finish"] is not None for r in rows):
        comp_all = sum(r["finish"] for r in rows) / sum(r["reads"] for r in rows)

    return {
        "ok": True,
        "chapters": len(rows),
        "from_chapter": rows[0]["chapter"],
        "to_chapter": rows[-1]["chapter"],
        "reads_head": int(rows[0]["reads"]),
        "reads_tail": int(rows[-1]["reads"]),
        "retention_median": round(med, 4),
        "retention_total": round(total_drop, 4),
        "complete_avg": None if comp_all is None else round(comp_all, 4),
        "rows": out,
        "drops": drops[:6],
    }


def render(r):
    if not r.get("ok"):
        return "算不出来：" + r.get("error", "")
    L = []
    L.append("=" * 62)
    L.append("追读漏斗  第 %d—%d 章 ｜ 阅读 %d → %d ｜ 整体留存 %.1f%%"
             % (r["from_chapter"], r["to_chapter"], r["reads_head"],
                r["reads_tail"], r["retention_total"] * 100))
    L.append("相邻章追读率中位数 %.1f%%%s"
             % (r["retention_median"] * 100,
                "" if r["complete_avg"] is None else " ｜ 平均完读率 %.1f%%" % (r["complete_avg"] * 100)))
    L.append("=" * 62)
    L.append("%-6s %-9s %-9s %-8s %s" % ("章", "阅读", "追读率", "首章留存", "完读率"))
    for o in r["rows"]:
        L.append("%-6d %-9d %-9s %-8s %s"
                 % (o["chapter"], o["reads"],
                    "-" if o["ret_to_next"] is None else "%.1f%%" % (o["ret_to_next"] * 100),
                    "%.1f%%" % (o["first_keep"] * 100),
                    "-" if o["complete"] is None else "%.1f%%" % (o["complete"] * 100)))
    if r["drops"]:
        L.append("-" * 62)
        L.append("掉点排序（追读率低于中位数，按缺口从大到小）：")
        for d in r["drops"]:
            L.append("  第 %d 章 → 第 %d 章：%.1f%%（低于中位数 %.1f 个点）｜ %s"
                     % (d["chapter"], d["chapter"] + 1, d["ret_to_next"] * 100,
                        d["gap"] * 100, d["stage"]))
            L.append("     往这儿查：%s" % d["hint"])
    else:
        L.append("-" * 62)
        L.append("没有明显掉点。")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="追读漏斗核算")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--csv")
    g.add_argument("--json")
    ap.add_argument("--json-out", dest="json_out", default=None)
    ap.add_argument("--chapter-words", type=int, default=None,
                    help="单章字数，仅用于在报告里提示篇幅影响")
    a = ap.parse_args()

    path = a.csv or a.json
    if not os.path.exists(path):
        print("找不到数据文件：%s" % path)
        return 2
    rows = load_csv(a.csv) if a.csv else load_json(a.json)
    if not rows:
        print("没有解析到有效数据。检查表头是否为 chapter,reads[,finish]")
        return 2

    r = analyze(rows)
    print(render(r))
    if a.chapter_words and r.get("ok"):
        print("\n单章约 %d 字。若单章明显长于同赛道平均，追读率会被篇幅拉低，"
              "先排除这个因素再改稿。" % a.chapter_words)
    if a.json_out:
        d = os.path.dirname(os.path.abspath(a.json_out))
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        with open(a.json_out, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2)
        print("已写入：%s" % a.json_out)
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
