#!/usr/bin/env python3
"""论文字数与结构统计：按章统计中英文字数、段落数、图表数，对比目标字数。

用法：
    python wordstat.py 正文.md
    python wordstat.py 正文.md --target 12000
    python wordstat.py 正文.md --target 12000 --json

退出码：0 正常；1 有明显偏差；2 参数或文件错误。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    Issue,
    body_words,
    count_cjk,
    count_words,
    finish,
    read_text,
    setup_stdout,
)

HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*#*$")
CN_CHAPTER_RE = re.compile(r"^#{0,6}\s*第\s*[一二三四五六七八九十百0-9]+\s*[章节]\s*\S")
CAPTION_RE = re.compile(r"^\s*(图|表|Figure|Table)\s*[0-9]+(?:[-–—－.][0-9]+)?\s*[:：.、]?\s*\S")


def find_chapters(text: str):
    """优先按"第X章"切章；没有则按一级标题切；都没有则整篇算一章。"""
    lines = text.splitlines()
    cn_marks = [
        (idx, re.sub(r"^#{0,6}\s*", "", line.strip()))
        for idx, line in enumerate(lines, start=1)
        if CN_CHAPTER_RE.match(line)
    ]
    if cn_marks:
        marks = cn_marks
    else:
        marks = []
        for idx, line in enumerate(lines, start=1):
            m = HEADING_RE.match(line.strip())
            if m and len(m.group(1)) == 1:
                marks.append((idx, m.group(2).strip()))
    if not marks:
        return [{"title": "（全文）", "start": 1, "end": len(lines)}]
    chapters = []
    if marks[0][0] > 1:
        chapters.append({"title": "（前置：题目/摘要）", "start": 1, "end": marks[0][0] - 1})
    for i, (line_no, title) in enumerate(marks):
        end = marks[i + 1][0] - 1 if i + 1 < len(marks) else len(lines)
        chapters.append({"title": title, "start": line_no, "end": end})
    return chapters


def chapter_stats(lines, chapter):
    body = lines[chapter["start"]:chapter["end"]]
    text = "\n".join(body)
    figures = sum(1 for ln in body if re.match(r"^\s*(图|Figure)\s*[0-9]", ln))
    tables = sum(1 for ln in body if re.match(r"^\s*(表|Table)\s*[0-9]", ln))
    paras = [p for p in text.split("\n") if p.strip() and not p.strip().startswith("#")]
    return {
        "title": chapter["title"],
        "line": chapter["start"],
        "cjk": count_cjk(text),
        "words": count_words(text),
        "total": body_words(text),
        "paragraphs": len(paras),
        "figures": figures,
        "tables": tables,
    }


def analyze(text: str, target: int = 0, tolerance: float = 0.3):
    lines = text.splitlines()
    chapters = find_chapters(text)
    stats = [chapter_stats(lines, ch) for ch in chapters]
    total = sum(s["total"] for s in stats)
    issues: list[Issue] = []

    for s in stats:
        s["share"] = round(s["total"] / total * 100, 1) if total else 0.0
        s["target"] = round(target * s["total"] / total) if (target and total) else 0
        s["deviation"] = (
            round((s["total"] - target * s["total"] / total) / (target * s["total"] / total) * 100, 1)
            if (target and total)
            else 0.0
        )

    if len(stats) <= 1 and total > 3000:
        issues.append(
            Issue(
                "WS004",
                "MINOR",
                "未识别到章级标题，无法分章统计",
                hint="用 `# 第 1 章 ……` 或 `## 1 ……` 作章标题，工具才能按章核对字数。",
            )
        )

    if target:
        diff = (total - target) / target
        if diff < -0.15:
            issues.append(
                Issue(
                    "WS002",
                    "MAJOR",
                    f"总字数 {total}，比目标 {target} 少 {abs(diff) * 100:.0f}%",
                    hint="补内容而不是补修饰：优先补证据、讨论与限制，不用套话凑字数。",
                )
            )
        elif diff > 0.30:
            issues.append(
                Issue(
                    "WS002",
                    "MINOR",
                    f"总字数 {total}，比目标 {target} 多 {diff * 100:.0f}%",
                    hint="超三成通常是越界写了别章内容，回提纲查章节职责。",
                )
            )

    if len(stats) >= 2 and total:
        mean = total / len(stats)
        for s in stats:
            if s["total"] < mean * 0.2:
                issues.append(
                    Issue(
                        "WS003",
                        "MINOR",
                        f"「{s['title']}」仅 {s['total']} 字（全文章均 {mean:.0f} 字）",
                        location=f"第{s['line']}行",
                        hint="要么合并到相邻章节，要么补足内容；空章会拉低整体印象。",
                    )
                )

    return {
        "total": total,
        "cjk": sum(s["cjk"] for s in stats),
        "words": sum(s["words"] for s in stats),
        "chapters": stats,
        "target": target,
    }, issues


def main(argv=None) -> int:
    setup_stdout()
    parser = argparse.ArgumentParser(description="论文字数与结构统计")
    parser.add_argument("file", help="正文文件")
    parser.add_argument("--target", type=int, default=0, help="目标总字数")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    path = Path(args.file)
    if not path.exists():
        print(f"文件不存在：{path}", file=sys.stderr)
        return 2

    text = read_text(path)
    data, issues = analyze(text, args.target)

    table = ["| 章 | 字数 | 占比 | 段数 | 图 | 表 |", "|---|---|---|---|---|---|"]
    for s in data["chapters"]:
        table.append(
            f"| {s['title']} | {s['total']} | {s['share']}% | {s['paragraphs']} | {s['figures']} | {s['tables']} |"
        )
    table.append(f"| **合计** | **{data['total']}** | 100% | — | — | — |")

    human = [
        f"文件：{path.name}",
        f"字数：中文 {data['cjk']} 字 + 西文 {data['words']} 词 = {data['total']}",
        f"章数：{len(data['chapters'])}" + (f"｜目标 {args.target} 字" if args.target else ""),
        "",
        *table,
    ]
    return finish("wordstat", data, issues, human, args.json)


if __name__ == "__main__":
    sys.exit(main())
