#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
doc_export.py — 把 Markdown 报告导出为 docx / html。

用法：
    python doc_export.py 报告.md --to docx,html
    python doc_export.py 报告.md --to docx --outdir 交付 --title "六月复盘"

支持的元素：标题(1–4级)、段落、无序/有序列表、表格、代码块、引用、分隔线。
支持的强调：**加粗**、`行内代码`。
docx 为真实 OOXML，Word / WPS 可直接打开。
"""

import argparse
import os
import re
import sys
import zipfile
from datetime import datetime

import czl_core as C

# ---------------------------------------------------------------- Markdown 解析


def parse_md(text: str):
    lines = text.replace("\r\n", "\n").split("\n")
    blocks, i = [], 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()

        if not s:
            i += 1
            continue

        if s.startswith("```"):
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            blocks.append(("code", "\n".join(buf)))
            continue

        m = re.match(r"^(#{1,4})\s+(.*)$", s)
        if m:
            blocks.append(("h", len(m.group(1)), m.group(2).strip()))
            i += 1
            continue

        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", s):
            blocks.append(("hr",))
            i += 1
            continue

        if s.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:\-|]+\|?$", lines[i + 1].strip()):
            head = [c.strip() for c in s.strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            blocks.append(("table", head, rows))
            continue

        if re.match(r"^[-*]\s+", s):
            items = []
            while i < len(lines) and re.match(r"^[-*]\s+", lines[i].strip()):
                items.append(re.sub(r"^[-*]\s+", "", lines[i].strip()))
                i += 1
            blocks.append(("ul", items))
            continue

        if re.match(r"^\d+\.\s+", s):
            items = []
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i].strip()):
                items.append(re.sub(r"^\d+\.\s+", "", lines[i].strip()))
                i += 1
            blocks.append(("ol", items))
            continue

        if s.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(re.sub(r"^>\s?", "", lines[i].strip()))
                i += 1
            blocks.append(("quote", " ".join(buf).strip()))
            continue

        buf = []
        while i < len(lines) and lines[i].strip() and not re.match(
                r"^(#{1,4}\s|```|\||[-*]\s|\d+\.\s|>)", lines[i].strip()):
            buf.append(lines[i].strip())
            i += 1
        blocks.append(("p", " ".join(buf)))
    return blocks


def inline_runs(text: str):
    """把行内标记拆成 [(文本, 是否加粗, 是否等宽)]。"""
    out, pos = [], 0
    pattern = re.compile(r"(\*\*.+?\*\*|`[^`]+`)")
    for m in pattern.finditer(text):
        if m.start() > pos:
            out.append((text[pos:m.start()], False, False))
        tok = m.group(0)
        if tok.startswith("**"):
            out.append((tok[2:-2], True, False))
        else:
            out.append((tok[1:-1], False, True))
        pos = m.end()
    if pos < len(text):
        out.append((text[pos:], False, False))
    return out or [(text, False, False)]


def strip_marks(text: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"\1", re.sub(r"`([^`]+)`", r"\1", text))


# ---------------------------------------------------------------- HTML

HTML_CSS = """
:root{--ink:#1c2430;--muted:#5b6672;--line:#dfe4ea;--accent:#1f6f78;--bg:#fff}
*{box-sizing:border-box}
body{margin:0;background:#f4f6f8;color:var(--ink);
 font:16px/1.75 "Microsoft YaHei","PingFang SC","Hiragino Sans GB",system-ui,sans-serif}
.page{max-width:860px;margin:0 auto;background:var(--bg);padding:48px 56px 64px;
 box-shadow:0 1px 3px rgba(0,0,0,.06)}
h1{font-size:28px;margin:0 0 8px;letter-spacing:.5px}
h2{font-size:21px;margin:32px 0 10px;padding-left:10px;border-left:4px solid var(--accent)}
h3{font-size:17px;margin:24px 0 8px;color:var(--accent)}
h4{font-size:15px;margin:18px 0 6px;color:var(--muted)}
p{margin:10px 0}
hr{border:0;border-top:1px solid var(--line);margin:28px 0}
blockquote{margin:14px 0;padding:10px 14px;background:#f2f7f7;border-left:3px solid var(--accent);color:var(--muted)}
code{font-family:Consolas,"Courier New",monospace;background:#f2f4f6;padding:1px 5px;border-radius:3px;font-size:14px}
pre{background:#1c2430;color:#e8edf2;padding:14px 16px;border-radius:6px;overflow-x:auto}
pre code{background:none;color:inherit;padding:0}
table{border-collapse:collapse;width:100%;margin:14px 0;font-size:14px}
th,td{border:1px solid var(--line);padding:7px 10px;text-align:left;vertical-align:top}
th{background:#eef3f4;font-weight:600}
tr:nth-child(even) td{background:#fafbfc}
ul,ol{margin:10px 0;padding-left:26px}
li{margin:4px 0}
.meta{color:var(--muted);font-size:13px;margin-bottom:26px}
@media print{body{background:#fff}.page{box-shadow:none;padding:0;max-width:none}}
"""


def to_html(blocks, title: str) -> str:
    out = ['<!DOCTYPE html>', '<html lang="zh-CN">', '<head>', '<meta charset="utf-8">',
           '<meta name="viewport" content="width=device-width,initial-scale=1">',
           '<title>%s</title>' % esc_html(title), '<style>%s</style>' % HTML_CSS,
           '</head>', '<body>', '<div class="page">']
    for b in blocks:
        kind = b[0]
        if kind == "h":
            lvl, txt = b[1], b[2]
            if lvl == 1:
                out.append("<h1>%s</h1>" % html_inline(txt))
                out.append('<div class="meta">导出于 %s</div>' %
                           datetime.now().strftime("%Y-%m-%d %H:%M"))
            else:
                out.append("<h%d>%s</h%d>" % (lvl, html_inline(txt), lvl))
        elif kind == "p":
            out.append("<p>%s</p>" % html_inline(b[1]))
        elif kind == "ul":
            out.append("<ul>" + "".join("<li>%s</li>" % html_inline(x) for x in b[1]) + "</ul>")
        elif kind == "ol":
            out.append("<ol>" + "".join("<li>%s</li>" % html_inline(x) for x in b[1]) + "</ol>")
        elif kind == "table":
            head, rows = b[1], b[2]
            out.append("<table><thead><tr>" +
                       "".join("<th>%s</th>" % html_inline(h) for h in head) + "</tr></thead><tbody>")
            for r in rows:
                out.append("<tr>" + "".join("<td>%s</td>" % html_inline(c) for c in r) + "</tr>")
            out.append("</tbody></table>")
        elif kind == "code":
            out.append("<pre><code>%s</code></pre>" % esc_html(b[1]))
        elif kind == "quote":
            out.append("<blockquote>%s</blockquote>" % html_inline(b[1]))
        elif kind == "hr":
            out.append("<hr>")
    out += ["</div>", "</body>", "</html>"]
    return "\n".join(out)


def esc_html(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def html_inline(s: str) -> str:
    out = []
    for txt, bold, mono in inline_runs(s):
        h = esc_html(txt)
        if mono:
            h = "<code>%s</code>" % h
        if bold:
            h = "<strong>%s</strong>" % h
        out.append(h)
    return "".join(out)


# ---------------------------------------------------------------- DOCX

def esc_xml(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("\u0000", ""))


def run_xml(text: str, bold=False, mono=False, size=None, color=None) -> str:
    props = []
    if mono:
        props.append('<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:eastAsia="等线"/>')
    else:
        props.append('<w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="等线"/>')
    if bold:
        props.append("<w:b/>")
    if size:
        props.append('<w:sz w:val="%d"/><w:szCs w:val="%d"/>' % (size, size))
    if color:
        props.append('<w:color w:val="%s"/>' % color)
    rpr = "<w:rPr>%s</w:rPr>" % "".join(props)
    return ('<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>'
            % (rpr, esc_xml(text)))


def para_xml(runs: str, style=None, align=None, before=0, after=120, indent=None,
             shading=None, border_left=None) -> str:
    ppr = ['<w:spacing w:before="%d" w:after="%d"/>' % (before, after)]
    if style:
        ppr.insert(0, '<w:pStyle w:val="%s"/>' % style)
    if align:
        ppr.append('<w:jc w:val="%s"/>' % align)
    if indent:
        ppr.append('<w:ind w:left="%d"/>' % indent)
    if shading:
        ppr.append('<w:shd w:val="clear" w:fill="%s"/>' % shading)
    if border_left:
        ppr.append('<w:pBdr><w:left w:val="single" w:sz="18" w:space="6" w:color="%s"/></w:pBdr>' % border_left)
    return "<w:p><w:pPr>%s</w:pPr>%s</w:p>" % ("".join(ppr), runs)


def table_xml(head, rows) -> str:
    ncol = max([len(head)] + [len(r) for r in rows]) if rows else len(head)
    grid = "".join('<w:gridCol w:w="%d"/>' % int(9000 / max(ncol, 1)) for _ in range(ncol))
    bd = ('<w:tblBorders>' + "".join(
        '<w:%s w:val="single" w:sz="4" w:space="0" w:color="D5DBE1"/>' % side
        for side in ("top", "left", "bottom", "right", "insideH", "insideV")) + '</w:tblBorders>')
    out = ['<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/>%s'
           '<w:tblLayout w:type="fixed"/></w:tblPr><w:tblGrid>%s</w:tblGrid>' % (bd, grid)]

    def cell(text, bold=False, shade=None):
        ppr = '<w:spacing w:before="40" w:after="40"/>'
        shd = '<w:shd w:val="clear" w:fill="%s"/>' % shade if shade else ""
        return ('<w:tc><w:tcPr>%s<w:vAlign w:val="center"/></w:tcPr>'
                '<w:p><w:pPr>%s</w:pPr>%s</w:p></w:tc>'
                % (shd, ppr, run_xml(text, bold=bold, size=19)))

    out.append("<w:tr>" + "".join(cell(h, bold=True, shade="EEF3F4") for h in head) + "</w:tr>")
    for r in rows:
        cells = (r + [""] * ncol)[:ncol]
        out.append("<w:tr>" + "".join(cell(c) for c in cells) + "</w:tr>")
    out.append("</w:tbl>")
    return "".join(out)


def to_docx_body(blocks) -> str:
    out = []
    for b in blocks:
        kind = b[0]
        if kind == "h":
            lvl, txt = b[1], b[2]
            size = {1: 40, 2: 30, 3: 25, 4: 22}.get(lvl, 22)
            color = {1: "1C2430", 2: "1F6F78", 3: "1F6F78", 4: "5B6672"}.get(lvl)
            out.append(para_xml(run_xml(strip_marks(txt), bold=True, size=size, color=color),
                                before=240 if lvl <= 2 else 180, after=100,
                                border_left="1F6F78" if lvl == 2 else None))
        elif kind == "p":
            runs = "".join(run_xml(t, bold=bd, mono=mo, size=21)
                           for t, bd, mo in inline_runs(b[1]))
            out.append(para_xml(runs, after=100))
        elif kind == "ul":
            for x in b[1]:
                runs = run_xml("· ", size=21) + "".join(
                    run_xml(t, bold=bd, mono=mo, size=21) for t, bd, mo in inline_runs(x))
                out.append(para_xml(runs, indent=360, after=60))
        elif kind == "ol":
            for n, x in enumerate(b[1], 1):
                runs = run_xml("%d. " % n, size=21) + "".join(
                    run_xml(t, bold=bd, mono=mo, size=21) for t, bd, mo in inline_runs(x))
                out.append(para_xml(runs, indent=360, after=60))
        elif kind == "table":
            out.append(table_xml(b[1], b[2]))
            out.append(para_xml("", after=80))
        elif kind == "code":
            for line in b[1].split("\n"):
                out.append(para_xml(run_xml(line if line else " ", mono=True, size=18),
                                    shading="F2F4F6", after=0))
            out.append(para_xml("", after=80))
        elif kind == "quote":
            runs = "".join(run_xml(t, bold=bd, mono=mo, size=20)
                           for t, bd, mo in inline_runs(b[1]))
            out.append(para_xml(runs, indent=240, after=100, shading="F2F7F7",
                                border_left="1F6F78"))
        elif kind == "hr":
            out.append('<w:p><w:pPr><w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" '
                       'w:color="DFE4EA"/></w:pBdr></w:pPr></w:p>')

    sect = ('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
            '<w:pgMar w:top="1440" w:right="1247" w:bottom="1440" w:left="1247" '
            'w:header="851" w:footer="992" w:gutter="0"/></w:sectPr>')
    return "".join(out) + sect


DOCX_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults><w:rPrDefault><w:rPr>
<w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="等线" w:cs="Calibri"/>
<w:sz w:val="21"/><w:szCs w:val="21"/><w:lang w:val="en-US" w:eastAsia="zh-CN"/>
</w:rPr></w:rPrDefault><w:pPrDefault><w:pPr>
<w:spacing w:line="300" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
</w:styles>"""

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>"""

RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""

DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""


def write_docx(blocks, path: str, title: str) -> None:
    body = to_docx_body(blocks)
    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                "<w:body>%s</w:body></w:document>" % body)
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    core = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            "<dc:title>%s</dc:title><dc:creator>数证台</dc:creator>"
            '<dcterms:created xsi:type="dcterms:W3CDTF">%s</dcterms:created>'
            '<dcterms:modified xsi:type="dcterms:W3CDTF">%s</dcterms:modified>'
            "</cp:coreProperties>" % (esc_xml(title), now, now))
    app = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
           "<Application>czl-data-evidence</Application></Properties>")

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/document.xml", document)
        z.writestr("word/styles.xml", DOCX_STYLES)
        z.writestr("word/_rels/document.xml.rels", DOC_RELS)
        z.writestr("docProps/core.xml", core)
        z.writestr("docProps/app.xml", app)


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser(description="数证台 · Markdown 导出 docx / html")
    ap.add_argument("path", help="Markdown 文件")
    ap.add_argument("--to", default="docx,html", help="目标格式，逗号分隔：docx,html（默认两个都出）")
    ap.add_argument("--outdir", help="输出目录，默认 Markdown 同级下的「导出」")
    ap.add_argument("--title", help="文档标题，默认取第一个一级标题或文件名")
    args = ap.parse_args()

    if not os.path.exists(args.path):
        C.die("文件不存在：%s" % args.path)
    text = open(args.path, encoding="utf-8").read()
    if not text.strip():
        C.die("Markdown 文件是空的：%s" % args.path)

    blocks = parse_md(text)
    if not blocks:
        C.die("没有解析出任何内容，请检查文件格式")

    h1 = next((b[2] for b in blocks if b[0] == "h" and b[1] == 1), None)
    title = args.title or h1 or os.path.splitext(os.path.basename(args.path))[0]

    outdir = args.outdir or os.path.join(os.path.dirname(os.path.abspath(args.path)), "导出")
    os.makedirs(outdir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(args.path))[0]

    made = []
    for fmt in [f.strip().lower() for f in args.to.split(",") if f.strip()]:
        if fmt == "html":
            p = os.path.join(outdir, stem + ".html")
            with open(p, "w", encoding="utf-8", newline="\n") as f:
                f.write(to_html(blocks, title))
            made.append(p)
        elif fmt == "docx":
            p = os.path.join(outdir, stem + ".docx")
            write_docx(blocks, p, title)
            made.append(p)
        else:
            C.warn("不支持的格式：%s（只支持 docx、html）" % fmt)

    if not made:
        C.die("没有生成任何文件")
    for p in made:
        print("已导出：%s（%.1f KB）" % (p, os.path.getsize(p) / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
