#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2026 虫志龙. All rights reserved.
"""稿件导出：Markdown -> HTML / TXT。

用法：
    python draft_exporter.py --file draft.md --to html
    python draft_exporter.py --file draft.md --to txt --out draft.txt

只做轻量转换（标题、段落、列表、引用、代码块），不依赖任何第三方库。
"""
import argparse
import html
import os
import re
import sys

HTML_HEAD = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  body {{ max-width: 760px; margin: 40px auto; padding: 0 20px;
         font-family: -apple-system, "Microsoft YaHei", "PingFang SC", sans-serif;
         font-size: 16px; line-height: 1.85; color: #222; background: #fff; }}
  h1 {{ font-size: 26px; border-bottom: 2px solid #b23a2f; padding-bottom: 10px; }}
  h2 {{ font-size: 21px; margin-top: 34px; border-left: 4px solid #b23a2f; padding-left: 10px; }}
  h3 {{ font-size: 18px; margin-top: 26px; }}
  blockquote {{ margin: 16px 0; padding: 10px 16px; background: #faf6f4;
                border-left: 3px solid #d8b9b3; color: #555; }}
  code {{ background: #f4f4f4; padding: 1px 5px; border-radius: 3px; font-size: 14px; }}
  pre {{ background: #f7f7f7; padding: 14px; overflow-x: auto; border-radius: 4px; }}
  pre code {{ background: none; padding: 0; }}
  table {{ border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 15px; }}
  th, td {{ border: 1px solid #ddd; padding: 8px 10px; text-align: left; }}
  th {{ background: #f7f2f0; }}
  hr {{ border: none; border-top: 1px solid #e5e5e5; margin: 30px 0; }}
  @media print {{ body {{ margin: 0; max-width: none; }} }}
</style>
</head>
<body>
"""


def md_to_html(md):
    out = []
    in_code = False
    in_table = False

    for raw in md.split("\n"):
        line = raw.rstrip()

        if line.startswith("```"):
            if in_code:
                out.append("</code></pre>")
                in_code = False
            else:
                out.append("<pre><code>")
                in_code = True
            continue
        if in_code:
            out.append(html.escape(line))
            continue

        if re.match(r"^\s*\|.*\|\s*$", line):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(re.match(r"^:?-{2,}:?$", c) for c in cells if c):
                continue
            if not in_table:
                out.append("<table>")
                in_table = True
                out.append("<tr>" + "".join("<th>%s</th>" % html.escape(c) for c in cells) + "</tr>")
            else:
                out.append("<tr>" + "".join("<td>%s</td>" % html.escape(c) for c in cells) + "</tr>")
            continue
        elif in_table:
            out.append("</table>")
            in_table = False

        if not line.strip():
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            lvl = len(m.group(1))
            out.append("<h%d>%s</h%d>" % (lvl, html.escape(m.group(2)), lvl))
            continue
        if line.strip() == "---":
            out.append("<hr>")
            continue
        if line.startswith(">"):
            out.append("<blockquote>%s</blockquote>" % html.escape(line.lstrip("> ").strip()))
            continue
        if re.match(r"^[-*]\s+", line):
            out.append("<li>%s</li>" % html.escape(re.sub(r"^[-*]\s+", "", line)))
            continue
        if re.match(r"^\d+\.\s+", line):
            out.append("<li>%s</li>" % html.escape(re.sub(r"^\d+\.\s+", "", line)))
            continue
        txt = html.escape(line)
        txt = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", txt)
        txt = re.sub(r"`([^`]+)`", r"<code>\1</code>", txt)
        out.append("<p>%s</p>" % txt)

    if in_code:
        out.append("</code></pre>")
    if in_table:
        out.append("</table>")
    return "\n".join(out)


def main():
    p = argparse.ArgumentParser(description="Markdown 导出为 HTML / TXT")
    p.add_argument("--file", required=True, help="Markdown 源文件")
    p.add_argument("--to", choices=["html", "txt"], default="html")
    p.add_argument("--out", help="输出路径（默认同名换扩展名）")
    a = p.parse_args()

    try:
        with open(a.file, encoding="utf-8") as f:
            md = f.read()
    except OSError as e:
        print("读取失败：%s" % e, file=sys.stderr)
        return 2

    base = os.path.splitext(a.file)[0]
    out = a.out or (base + "." + a.to)
    title = os.path.basename(base)

    if a.to == "txt":
        txt = re.sub(r"^#{1,6}\s*", "", md, flags=re.M)
        txt = re.sub(r"\*\*(.+?)\*\*", r"\1", txt)
        txt = re.sub(r"`([^`]+)`", r"\1", txt)
        content = txt
    else:
        content = HTML_HEAD.format(title=html.escape(title)) + md_to_html(md) + "\n</body>\n</html>\n"

    try:
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
    except OSError as e:
        print("写入失败：%s" % e, file=sys.stderr)
        return 2

    print("已导出：%s（%d 字节）" % (out, len(content.encode("utf-8"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
