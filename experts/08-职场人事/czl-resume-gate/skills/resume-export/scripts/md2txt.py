#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""md2txt.py - flatten a markdown resume into ATS plain text.

What ATS text extraction effectively produces: no bold, no columns, bullets
as characters. Use this to check reading order and to paste into job boards
that only accept text.

Usage:
    python md2txt.py resume.md [-o resume.txt]
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from md2html import parse_blocks  # noqa: E402


def strip_inline(t):
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)
    t = re.sub(r"__([^_]+)__", r"\1", t)
    t = re.sub(r"`([^`]+)`", r"\1", t)
    t = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", t)
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", t)
    return t.strip()


def to_text(md_text):
    lines = []
    for kind, val in parse_blocks(md_text):
        if kind == "h1":
            lines.append(strip_inline(val).upper())
            lines.append("=" * 40)
        elif kind in ("h2", "h3", "h4"):
            if lines and lines[-1] != "":
                lines.append("")
            lines.append(strip_inline(val).upper())
        elif kind == "p":
            lines.append(strip_inline(val))
        elif kind == "quote":
            lines.append(strip_inline(val))
        elif kind == "ul":
            for item in val:
                lines.append("• " + strip_inline(item))
        elif kind == "ol":
            for n, item in enumerate(val, 1):
                lines.append("%d. %s" % (n, strip_inline(item)))
        elif kind == "hr":
            lines.append("")
        elif kind == "table":
            header, rows = val
            lines.append(" | ".join(strip_inline(c) for c in header))
            for r in rows:
                lines.append(" | ".join(strip_inline(c) for c in r))
    # collapse >2 blank lines
    out, blank = [], 0
    for ln in lines:
        if ln.strip() == "":
            blank += 1
            if blank > 1:
                continue
        else:
            blank = 0
        out.append(ln)
    return "\n".join(out).strip() + "\n"


def main():
    ap = argparse.ArgumentParser(description="markdown resume -> ATS plain text")
    ap.add_argument("source")
    ap.add_argument("-o", "--out")
    args = ap.parse_args()

    src = Path(args.source)
    try:
        md = src.read_text(encoding="utf-8-sig")
    except OSError as e:
        print("ERROR: cannot read %s (%s)" % (src, e), file=sys.stderr)
        return 2

    txt = to_text(md)
    out = Path(args.out) if args.out else src.with_suffix(".txt")
    out.write_text(txt, encoding="utf-8")
    print("written: %s (%d chars)" % (out, len(txt)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
