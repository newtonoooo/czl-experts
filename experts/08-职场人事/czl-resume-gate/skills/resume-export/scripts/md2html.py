#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""md2html.py - render a markdown resume as a print-ready A4 HTML file.

Supports the markdown subset a resume actually uses: headings, bullets,
ordered lists, bold, inline code, links, rules, blockquotes. Tables are
flattened to single-column text on purpose (ATS parsers mangle tables).

Print to PDF with Ctrl+P in any browser -> A4, margins already set by @page.

Standard library only. Usage:
    python md2html.py resume.md -o resume.html [--theme plain|ink|navy] [--title NAME]
"""

import argparse
import html
import re
import sys
from pathlib import Path

THEMES = {
    "plain": {"accent": "#1f2937", "rule": "#d1d5db", "muted": "#4b5563"},
    "ink": {"accent": "#111827", "rule": "#9ca3af", "muted": "#374151"},
    "navy": {"accent": "#1e3a5f", "rule": "#c7d2de", "muted": "#334155"},
}

CSS_TMPL = """
@page { size: A4; margin: 14mm 16mm 14mm 16mm; }
* { box-sizing: border-box; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body {
  margin: 0 auto; padding: 0; max-width: 178mm;
  font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans SC", "Source Han Sans SC",
               "Hiragino Sans GB", "Calibri", Arial, sans-serif;
  font-size: 10.5pt; line-height: 1.62; color: #1a1a1a;
  font-kerning: normal; text-rendering: optimizeLegibility;
}
header.doc-head { margin-bottom: 6pt; }
h1 {
  font-size: 19pt; line-height: 1.25; margin: 0 0 3pt 0;
  color: %(accent)s; letter-spacing: 0.02em; font-weight: 700;
}
h2 {
  font-size: 11.6pt; margin: 13pt 0 5pt 0; padding-bottom: 2.5pt;
  color: %(accent)s; letter-spacing: 0.08em; font-weight: 700;
  border-bottom: 0.9pt solid %(rule)s;
}
h3 { font-size: 10.6pt; margin: 8pt 0 3pt 0; font-weight: 700; color: #111827; }
h4 { font-size: 10.2pt; margin: 6pt 0 2pt 0; font-weight: 700; color: %(muted)s; }
p { margin: 3pt 0; }
ul, ol { margin: 3pt 0 3pt 0; padding-left: 1.15em; }
li { margin: 3.2pt 0; padding-left: 0.15em; }
li::marker { color: %(muted)s; }
strong { font-weight: 700; }
code {
  font-family: "Cascadia Mono", Consolas, "Courier New", monospace;
  font-size: 9.6pt; background: #f3f4f6; padding: 0 2px; border-radius: 2px;
}
a { color: %(accent)s; text-decoration: none; border-bottom: 0.5pt dotted %(rule)s; }
hr { border: 0; border-top: 0.7pt solid %(rule)s; margin: 8pt 0; }
blockquote {
  margin: 5pt 0; padding: 2pt 0 2pt 8pt; border-left: 2pt solid %(rule)s;
  color: %(muted)s; font-size: 9.8pt;
}
.flat-table { margin: 4pt 0; font-size: 10pt; }
.flat-table div { margin: 1.5pt 0; }
.contact-line { color: %(muted)s; font-size: 10pt; margin: 0 0 4pt 0; }
.avoid-break { break-inside: avoid; page-break-inside: avoid; }
@media print {
  body { max-width: none; }
  h1, h2, h3 { break-after: avoid; page-break-after: avoid; }
  li, p { orphans: 2; widows: 2; }
}
"""


def parse_inline(text):
    """Escape then re-apply inline markup."""
    t = html.escape(text, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"__([^_]+)__", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', t)
    return t


def is_table_sep(line):
    s = line.strip()
    return bool(re.match(r"^\|?[\s:\-|]+\|[\s:\-|]+$", s)) and "-" in s


def parse_blocks(text):
    lines = text.splitlines()
    blocks = []
    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip()
        if not line.strip():
            i += 1
            continue

        m = re.match(r"^(#{1,4})\s+(.*)$", line.strip())
        if m:
            blocks.append(("h%d" % len(m.group(1)), m.group(2).strip()))
            i += 1
            continue

        if re.match(r"^\s{0,3}(?:---+|\*\*\*+|___+)\s*$", line):
            blocks.append(("hr", ""))
            i += 1
            continue

        if line.lstrip().startswith(">"):
            buf = []
            while i < len(lines) and lines[i].lstrip().startswith(">"):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            blocks.append(("quote", " ".join(buf).strip()))
            continue

        if line.lstrip().startswith("|") and i + 1 < len(lines) and is_table_sep(lines[i + 1]):
            rows = []
            header = [c.strip() for c in line.strip().strip("|").split("|")]
            i += 2
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            blocks.append(("table", (header, rows)))
            continue

        if re.match(r"^\s{0,3}[-*+]\s+", line):
            items = []
            while i < len(lines) and re.match(r"^\s{0,3}[-*+]\s+", lines[i]):
                items.append(re.sub(r"^\s{0,3}[-*+]\s+", "", lines[i]).strip())
                i += 1
            blocks.append(("ul", items))
            continue

        if re.match(r"^\s{0,3}\d+[.)]\s+", line):
            items = []
            while i < len(lines) and re.match(r"^\s{0,3}\d+[.)]\s+", lines[i]):
                items.append(re.sub(r"^\s{0,3}\d+[.)]\s+", "", lines[i]).strip())
                i += 1
            blocks.append(("ol", items))
            continue

        buf = []
        while i < len(lines) and lines[i].strip() and not re.match(
                r"^\s{0,3}(?:#{1,4}\s|[-*+]\s|\d+[.)]\s|>|\|)", lines[i]):
            buf.append(lines[i].strip())
            i += 1
        if buf:
            blocks.append(("p", " ".join(buf)))
    return blocks


def render(blocks):
    out = []
    for kind, val in blocks:
        if kind == "h1":
            out.append('<h1>%s</h1>' % parse_inline(val))
        elif kind == "h2":
            out.append('<h2 class="avoid-break">%s</h2>' % parse_inline(val))
        elif kind == "h3":
            out.append('<h3 class="avoid-break">%s</h3>' % parse_inline(val))
        elif kind == "h4":
            out.append("<h4>%s</h4>" % parse_inline(val))
        elif kind == "p":
            out.append("<p>%s</p>" % parse_inline(val))
        elif kind == "quote":
            out.append("<blockquote>%s</blockquote>" % parse_inline(val))
        elif kind == "hr":
            out.append("<hr/>")
        elif kind == "ul":
            out.append("<ul>%s</ul>" % "".join("<li>%s</li>" % parse_inline(x) for x in val))
        elif kind == "ol":
            out.append("<ol>%s</ol>" % "".join("<li>%s</li>" % parse_inline(x) for x in val))
        elif kind == "table":
            header, rows = val
            parts = ["<div><strong>%s</strong></div>" % parse_inline(" ｜ ".join(header))]
            for r in rows:
                parts.append("<div>%s</div>" % parse_inline(" ｜ ".join(r)))
            out.append('<div class="flat-table">%s</div>' % "".join(parts))
    return "\n".join(out)


def build(text, title, theme):
    colors = THEMES.get(theme, THEMES["plain"])
    body = render(parse_blocks(text))
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>%(title)s</title>
<style>%(css)s</style>
</head>
<body>
%(body)s
</body>
</html>
""" % {"title": html.escape(title), "css": CSS_TMPL % colors, "body": body}


def main():
    ap = argparse.ArgumentParser(description="markdown resume -> print-ready A4 HTML")
    ap.add_argument("source")
    ap.add_argument("-o", "--out", help="output html path")
    ap.add_argument("--theme", default="plain", choices=sorted(THEMES))
    ap.add_argument("--title", default=None)
    args = ap.parse_args()

    src = Path(args.source)
    try:
        text = src.read_text(encoding="utf-8-sig")
    except OSError as e:
        print("ERROR: cannot read %s (%s)" % (src, e), file=sys.stderr)
        return 2

    title = args.title or src.stem
    out = Path(args.out) if args.out else src.with_suffix(".html")
    out.write_text(build(text, title, args.theme), encoding="utf-8")
    print("written: %s" % out)
    print("print to PDF: open the file in a browser, Ctrl+P, paper A4, margins Default, scale 100%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
