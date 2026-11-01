#!/usr/bin/env python3
"""图表检查：编号重复与跳号、正文引用悬挂、题注过短、编号风格混用、出现顺序。

用法：
    python figtable.py 正文.md
    python figtable.py 正文.md --json

退出码：0 正常；1 有悬挂引用；2 参数或文件错误。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import Issue, finish, read_text, setup_stdout  # noqa: E402

CAPTION_RE = re.compile(
    r"^\s*(图|表|Figure|Fig\.?|Table)\s*([0-9]+(?:\s*[-–—－.]\s*[0-9]+)?)\s*[:：.、．]?\s*(.*)$"
)
REF_RE = re.compile(r"(?:如|见|参见|详见|由|据|配合)?\s*(图|表|Figure|Fig\.?|Table)\s*([0-9]+(?:\s*[-–—－.]\s*[0-9]+)?)")
KIND_MAP = {"图": "图", "Figure": "图", "Fig.": "图", "Fig": "图", "表": "表", "Table": "表"}
SENTENCE_TAILS = ("。", "，", "；", "：")
VERB_STARTS = ("显示", "表明", "说明", "所列", "中所", "中可", "为", "是", "给出", "列出", "和", "与", "及", "可见")


def normalize_number(raw: str) -> str:
    num = re.sub(r"\s+", "", raw)
    return re.sub(r"[-–—－.]", "-", num)


def _looks_like_caption(stripped: str, number_end: int) -> bool:
    if len(stripped) > 100 or stripped.endswith(SENTENCE_TAILS):
        return False
    sep = stripped[number_end:number_end + 1]
    if sep and sep in " \u3000:：.、．-–—":
        return True
    rest = stripped[number_end:].strip()
    if not rest:
        return True
    if rest.startswith(VERB_STARTS):
        return False
    return len(stripped) <= 60


def scan(text: str):
    captions, refs = [], []
    for idx, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        m = CAPTION_RE.match(stripped)
        if m and _looks_like_caption(stripped, m.end(2)):
            kind = KIND_MAP.get(m.group(1), m.group(1))
            captions.append({"kind": kind, "number": normalize_number(m.group(2)), "title": m.group(3).strip(), "line": idx})
            refs.extend(_scan_refs(stripped[m.end(2):], idx))
            continue
        refs.extend(_scan_refs(stripped, idx))
    return captions, refs


def _scan_refs(text: str, line: int):
    return [
        {"kind": KIND_MAP.get(m.group(1), m.group(1)), "number": normalize_number(m.group(2)), "line": line}
        for m in REF_RE.finditer(text)
    ]


def analyze(captions, refs):
    issues: list[Issue] = []
    seen, by_kind = {}, {}

    for cap in captions:
        key = (cap["kind"], cap["number"])
        by_kind.setdefault(cap["kind"], []).append(cap["number"])
        if key in seen:
            issues.append(
                Issue(
                    "FT001",
                    "MAJOR",
                    f"{cap['kind']} {cap['number']} 编号重复（另一处第 {seen[key]} 行）",
                    f"第{cap['line']}行",
                    "同一编号只能出现一次；重排后同步修正正文引用。",
                )
            )
        else:
            seen[key] = cap["line"]
        if len(cap["title"]) < 2:
            issues.append(
                Issue("FT002", "MINOR", f"{cap['kind']} {cap['number']} 题注为空或过短", f"第{cap['line']}行", "题注要能被单独读懂。")
            )

    for kind, numbers in by_kind.items():
        styles = {"章序" if "-" in n else "全文序" for n in numbers}
        if len(styles) > 1:
            issues.append(
                Issue("FT003", "MINOR", f"{kind}的编号风格混用（{'、'.join(sorted(numbers))}）", hint="全文只用一种编号制。")
            )
        groups = {}
        for n in numbers:
            groups.setdefault(n.split("-")[0], []).append(n)
        for group, items in groups.items():
            seq = sorted({int(n.split("-")[-1]) for n in items})
            if seq != list(range(1, len(seq) + 1)):
                issues.append(
                    Issue(
                        "FT004",
                        "MINOR",
                        f"{kind} 编号不连续（{group} 族：{'、'.join(map(str, seq))}）",
                        hint="跳号通常是删了图表没重排，或漏了一张。",
                    )
                )

    caption_keys = {(c["kind"], c["number"]) for c in captions}
    referenced = {(r["kind"], r["number"]) for r in refs}

    for cap in captions:
        if (cap["kind"], cap["number"]) not in referenced:
            issues.append(
                Issue(
                    "FT005",
                    "MAJOR",
                    f"{cap['kind']} {cap['number']} 在正文中未被引用",
                    f"第{cap['line']}行",
                    "正文至少一处“如图 X 所示”或“见表 X”，否则读者不知道它为什么在这里。",
                )
            )

    for ref in refs:
        if (ref["kind"], ref["number"]) not in caption_keys:
            issues.append(
                Issue(
                    "FT006",
                    "BLOCKER",
                    f"正文引用 {ref['kind']} {ref['number']}，但不存在该编号的题注",
                    f"第{ref['line']}行",
                    "悬挂引用会被直接质疑数据可靠性，必须修。",
                )
            )

    for kind in by_kind:
        caps = [c for c in captions if c["kind"] == kind]
        order = [c["number"] for c in caps]
        sorted_order = sorted(order, key=lambda n: (n.split("-")[0], int(n.split("-")[-1])))
        if order != sorted_order:
            issues.append(
                Issue("FT007", "MINOR", f"{kind}的出现顺序与编号不一致：{' → '.join(order)}", hint="按出现顺序重排编号。")
            )

    return issues


def main(argv=None) -> int:
    setup_stdout()
    parser = argparse.ArgumentParser(description="图表编号与引用检查")
    parser.add_argument("file")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    path = Path(args.file)
    if not path.exists():
        print(f"文件不存在：{path}", file=sys.stderr)
        return 2

    captions, refs = scan(read_text(path))
    issues = analyze(captions, refs)
    figures = sum(1 for c in captions if c["kind"] == "图")
    tables = sum(1 for c in captions if c["kind"] == "表")

    listing = [f"{c['kind']}{c['number']}（第{c['line']}行）{c['title'][:18]}" for c in captions]
    human = [
        f"文件：{path.name}",
        f"图 {figures} 个｜表 {tables} 个｜正文引用 {len(refs)} 处",
        "识别到的题注：" + ("；".join(listing) if listing else "无"),
        "提示：题注识别为启发式，模板写法特殊时请人工复核清单。",
    ]
    return finish("figtable", {"file": str(path), "captions": captions, "reference_count": len(refs)}, issues, human, args.json)


if __name__ == "__main__":
    sys.exit(main())
