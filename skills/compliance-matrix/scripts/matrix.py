#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合规矩阵生成器：等保（分级别）/ 密评 / 信创。

子命令：
    dengbao --level 3     生成等保控制项矩阵（默认三级）
    miping                生成商用密码应用检查表
    xinchuang             生成信创适配清单
    all --level 3         三张表一起出

输出 markdown 或 csv，状态列留空供项目填写。
"""

import argparse
import csv
import io
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

CATALOG = Path(__file__).parent / "catalog.json"


def load():
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def dengbao_rows(level):
    out = []
    for item in load()["dengbao"]:
        if level in item["levels"]:
            out.append(
                {
                    "域": item["domain"],
                    "控制点": item["control"],
                    "落地要求": item["require"],
                    "常见产品/组件": item["product"],
                    "证据材料": item["evidence"],
                    "状态": "",
                    "责任人": "",
                }
            )
    return out


def miping_rows():
    return [
        {
            "层面": i["area"],
            "检查点": i["point"],
            "要求": i["require"],
            "证据材料": i["evidence"],
            "常见产品/组件": i["product"],
            "状态": "",
        }
        for i in load()["miping"]
    ]


def xinchuang_rows():
    return [
        {
            "层次": i["layer"],
            "组件": i["component"],
            "现用": i["baseline"],
            "信创替代": i["alternative"],
            "验证要点": i["check"],
            "优先级": i["priority"],
            "状态": "",
        }
        for i in load()["xinchuang"]
    ]


def to_md(title, rows, note=""):
    if not rows:
        return f"# {title}\n\n（无数据）\n"
    keys = list(rows[0].keys())
    lines = [f"# {title}", ""]
    if note:
        lines += [f"> {note}", ""]
    lines.append("| " + " | ".join(keys) + " |")
    lines.append("|" + "|".join(["---"] * len(keys)) + "|")
    for r in rows:
        lines.append("| " + " | ".join(str(r[k]) for k in keys) + " |")
    lines.append("")
    return "\n".join(lines)


def to_csv(rows):
    buf = io.StringIO()
    if not rows:
        return ""
    w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def counts_by_domain(rows, key):
    tally = {}
    for r in rows:
        tally[r[key]] = tally.get(r[key], 0) + 1
    return tally


def main():
    ap = argparse.ArgumentParser(description="等保/密评/信创合规矩阵")
    sub = ap.add_subparsers(dest="cmd", required=True)

    for name in ("dengbao", "all"):
        p = sub.add_parser(name)
        p.add_argument("--level", type=int, default=3, choices=[2, 3, 4])
        p.add_argument("--format", default="md", choices=["md", "csv"])
        p.add_argument("--out")
        p.set_defaults(name=name)

    for name in ("miping", "xinchuang"):
        p = sub.add_parser(name)
        p.add_argument("--format", default="md", choices=["md", "csv"])
        p.add_argument("--out")
        p.set_defaults(name=name)

    args = ap.parse_args()
    meta = load()
    note = meta["disclaimer"]

    blocks = []
    if args.name in ("dengbao", "all"):
        rows = dengbao_rows(args.level)
        title = f"等保 {args.level} 级控制项对照表（{len(rows)} 项）"
        body = to_csv(rows) if args.format == "csv" else to_md(title, rows, note)
        if args.format == "md":
            tally = counts_by_domain(rows, "域")
            summary = "\n".join(f"- {k}：{v} 项" for k, v in tally.items())
            body += f"\n## 分布\n\n{summary}\n"
        blocks.append(body)
        if not args.format == "csv":
            print(f"[等保 {args.level} 级] {len(rows)} 项控制点", file=sys.stderr)

    if args.name in ("miping", "all"):
        rows = miping_rows()
        body = to_csv(rows) if args.format == "csv" else to_md(
            f"商用密码应用安全性评估检查表（{len(rows)} 项）", rows, note
        )
        blocks.append(body)
        if not args.format == "csv":
            print(f"[密评] {len(rows)} 项检查点", file=sys.stderr)

    if args.name in ("xinchuang", "all"):
        rows = xinchuang_rows()
        body = to_csv(rows) if args.format == "csv" else to_md(
            f"信创适配清单（{len(rows)} 项）", rows, "优先级 P0 必须在投标前完成验证，P1 可在合同中承诺迁移计划，P2 可分期。"
        )
        blocks.append(body)
        if not args.format == "csv":
            print(f"[信创] {len(rows)} 项适配点", file=sys.stderr)

    text = ("\n\n".join(blocks)).strip() + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"已写出：{args.out}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
