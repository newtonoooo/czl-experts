#!/usr/bin/env python3
"""重复自查：与给定源文本做重合比对，定位疑似未标注重复的段落。

用法：
    python dup_scan.py 正文.md --sources 文献/
    python dup_scan.py 正文.md --sources a.md b.md --min-len 13 --json

说明：按字符级 n-gram 比对（默认 13 字）。纯英文片段短于 40 字符的不报，避免常见搭配误报。
工具只做比对；判断"是否正当引用"要看上下文（有规范标注的引用不算问题）。

退出码：0 未发现明显重合；1 发现较长重合；2 参数或文件错误。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import Issue, finish, read_text, setup_stdout  # noqa: E402

CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def normalize_with_map(text: str):
    """保留字母数字与汉字，其余丢弃；返回 (归一化串, 每个字符对应的原行号)。"""
    chars, lines = [], []
    line = 1
    for ch in text:
        if ch == "\n":
            line += 1
            continue
        if ch.isalnum():
            chars.append(ch.lower())
            lines.append(line)
    return "".join(chars), lines


def collect_sources(paths):
    files = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            files.extend(sorted(x for x in path.rglob("*") if x.is_file() and x.suffix.lower() in (".md", ".txt")))
        elif path.is_file():
            files.append(path)
    return [(f.name, read_text(f)) for f in files]


def find_segments(target: str, sources, n: int):
    norm, line_map = normalize_with_map(target)
    if len(norm) < n:
        return norm, line_map, [], 0.0

    index = {}
    for name, text in sources:
        src_norm, _ = normalize_with_map(text)
        for i in range(len(src_norm) - n + 1):
            gram = src_norm[i:i + n]
            if gram not in index:
                index[gram] = name

    matched = [False] * len(norm)
    origin = {}
    for i in range(len(norm) - n + 1):
        gram = norm[i:i + n]
        name = index.get(gram)
        if name:
            for k in range(i, i + n):
                matched[k] = True
                origin.setdefault(k, name)

    segments = []
    i = 0
    while i < len(norm):
        if not matched[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(norm) and matched[j + 1]:
            j += 1
        text_seg = norm[i:j + 1]
        if CJK_RE.search(text_seg) or len(text_seg) >= 40:
            segments.append(
                {
                    "start_line": line_map[i],
                    "end_line": line_map[j],
                    "length": j - i + 1,
                    "source": origin.get(i, "?"),
                    "snippet": text_seg[:60],
                }
            )
        i = j + 1

    coverage = sum(s["length"] for s in segments) / len(norm) if norm else 0.0
    return norm, line_map, segments, coverage


def main(argv=None) -> int:
    setup_stdout()
    parser = argparse.ArgumentParser(description="重复自查（与源文本比对）")
    parser.add_argument("file", help="待查文本")
    parser.add_argument("--sources", nargs="+", required=True, help="源文本文件或目录")
    parser.add_argument("--min-len", type=int, default=13, help="最小比对长度（字符）")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    target_path = Path(args.file)
    if not target_path.exists():
        print(f"文件不存在：{target_path}", file=sys.stderr)
        return 2

    sources = collect_sources(args.sources)
    if not sources:
        print("未找到可用的源文本：请检查 --sources 路径。", file=sys.stderr)
        return 2

    norm, line_map, segments, coverage = find_segments(read_text(target_path), sources, args.min_len)
    segments.sort(key=lambda s: s["length"], reverse=True)

    issues: list[Issue] = []
    long_ones = [s for s in segments if s["length"] >= 200]
    mid_ones = [s for s in segments if 40 <= s["length"] < 200]

    if long_ones:
        s = long_ones[0]
        issues.append(
            Issue(
                "DS001",
                "MAJOR",
                f"{len(long_ones)} 处超过 200 字的整段重合（最长 {s['length']} 字，第 {s['start_line']}—{s['end_line']} 行，命中 {s['source']}）",
                location=f"第{s['start_line']}行",
                hint="整段重合要么补规范引用，要么按 W10 的改写四步换骨架重写。",
            )
        )
    if mid_ones:
        s = mid_ones[0]
        issues.append(
            Issue(
                "DS002",
                "MAJOR",
                f"{len(mid_ones)} 处 40—200 字的重合（最长 {s['length']} 字，第 {s['start_line']} 行，命中 {s['source']}）",
                location=f"第{s['start_line']}行",
                hint="逐段判断：政策原文/定义属正当重复（补标注），其余需改写。",
            )
        )
    if coverage > 0.15:
        issues.append(
            Issue(
                "DS003",
                "MINOR",
                f"与源文本的字符重合覆盖率 {coverage * 100:.1f}%（阈值 15%）",
                hint="覆盖率只作参考，重点是看下面的重合清单里有没有未标注的段落。",
            )
        )

    table = ["| 行号 | 长度 | 命中来源 | 片段开头 |", "|---|---|---|---|"]
    for s in segments[:12]:
        table.append(f"| {s['start_line']}—{s['end_line']} | {s['length']} | {s['source']} | {s['snippet']}… |")
    table_lines = table if segments else ["未发现明显重合。"]

    payload = {
        "file": str(target_path),
        "source_count": len(sources),
        "min_len": args.min_len,
        "segments": segments[:50],
        "coverage": round(coverage, 4),
        "normalized_length": len(norm),
    }
    human = [
        f"文件：{target_path.name}｜源文本 {len(sources)} 份｜比对长度 {args.min_len} 字",
        f"重合段：{len(segments)} 处｜覆盖率 {coverage * 100:.1f}%",
        "",
        *table_lines,
        "",
        "提示：有规范标注的引用不算问题；本工具不判断引用是否正当，需看上下文。",
    ]
    return finish("dup_scan", payload, issues, human, args.json)


if __name__ == "__main__":
    sys.exit(main())
