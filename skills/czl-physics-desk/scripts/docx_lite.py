#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Markdown -> A4 打印版 .docx（纯标准库，不依赖 python-docx）。

支持：标题(#/##/###)、段落、无序列表(-)、有序列表(1.)、引用(>)、
      pipe 表格、分页符(<!--pagebreak--> 或 ---page---)、加粗(**x**)、行内代码(`x`)。

版面：A4（210×297mm）、页边距 18mm、正文 10.5pt、行距 1.5、页眉标题+元信息、页脚页码。

用法：
  python docx_lite.py --in 教案.md --out 教案.docx --title "牛顿第二定律" --meta "高二·人教2019·2课时"
  python docx_lite.py --self-check
"""

import argparse
import datetime as _dt
import os
import re
import sys
import zipfile
from xml.sax.saxutils import escape

A4_W, A4_H = 11906, 16838
MARGIN = 1020  # 18mm
CONTENT_W = A4_W - 2 * MARGIN

FONT_BODY = "宋体"
FONT_HEAD = "黑体"
FONT_ASCII = "Times New Roman"


def _p(text, style=None, align=None, keep_next=False, spacing_after=120,
       line=360, ind_left=0, bold=False, size=None, color=None, border_bottom=False):
    ppr = []
    if keep_next:
        ppr.append("<w:keepNext/>")
    ppr.append(f'<w:spacing w:before="0" w:after="{spacing_after}" w:line="{line}" w:lineRule="auto"/>')
    if ind_left:
        ppr.append(f'<w:ind w:left="{ind_left}"/>')
    if align:
        ppr.append(f'<w:jc w:val="{align}"/>')
    if border_bottom:
        ppr.append('<w:pBdr><w:bottom w:val="single" w:sz="4" w:space="1" w:color="BFBFBF"/></w:pBdr>')
    return f"<w:p><w:pPr>{''.join(ppr)}</w:pPr>{text}</w:p>"


def _run(text, bold=False, size=21, color=None, font=None, mono=False):
    rpr = [f'<w:rFonts w:ascii="{FONT_ASCII}" w:hAnsi="{FONT_ASCII}" w:eastAsia="{font or FONT_BODY}"/>']
    if bold:
        rpr.append("<w:b/>")
    if mono:
        rpr.append('<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/>')
        color = color or "444444"
    if color:
        rpr.append(f'<w:color w:val="{color}"/>')
    rpr.append(f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>')
    return f'<w:r><w:rPr>{"".join(rpr)}</w:rPr><w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


INLINE_RE = re.compile(r"(\*\*.+?\*\*|`.+?`)")


def inline_runs(text, size=21, base_bold=False, font=None):
    out = []
    for part in INLINE_RE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            out.append(_run(part[2:-2], bold=True, size=size, font=font))
        elif part.startswith("`") and part.endswith("`") and len(part) > 2:
            out.append(_run(part[1:-1], size=size, mono=True))
        else:
            out.append(_run(part, bold=base_bold, size=size, font=font))
    return "".join(out)


def table_xml(rows):
    if not rows:
        return ""
    ncol = max(len(r) for r in rows)
    col_w = CONTENT_W // max(ncol, 1)
    grid = "".join(f'<w:gridCol w:w="{col_w}"/>' for _ in range(ncol))
    out = [
        "<w:tbl><w:tblPr>",
        f'<w:tblW w:w="{CONTENT_W}" w:type="dxa"/>',
        '<w:tblBorders>'
        '<w:top w:val="single" w:sz="6" w:space="0" w:color="808080"/>'
        '<w:left w:val="single" w:sz="6" w:space="0" w:color="808080"/>'
        '<w:bottom w:val="single" w:sz="6" w:space="0" w:color="808080"/>'
        '<w:right w:val="single" w:sz="6" w:space="0" w:color="808080"/>'
        '<w:insideH w:val="single" w:sz="2" w:space="0" w:color="BFBFBF"/>'
        '<w:insideV w:val="single" w:sz="2" w:space="0" w:color="BFBFBF"/>'
        '</w:tblBorders>',
        '<w:tblLayout w:type="fixed"/>',
        '<w:tblCellMar><w:top w:w="40" w:type="dxa"/><w:left w:w="80" w:type="dxa"/>'
        '<w:bottom w:w="40" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tblCellMar>',
        "</w:tblPr><w:tblGrid>",
        grid,
        "</w:tblGrid>",
    ]
    for i, row in enumerate(rows):
        header = i == 0
        cells = list(row) + [""] * (ncol - len(row))
        out.append('<w:tr><w:trPr><w:cantSplit/>' + ("<w:tblHeader/>" if header else "") + "</w:trPr>")
        for c in cells:
            shade = '<w:shd w:val="clear" w:color="auto" w:fill="F2F2F2"/>' if header else ""
            out.append(
                f'<w:tc><w:tcPr><w:tcW w:w="{col_w}" w:type="dxa"/>{shade}'
                '<w:vAlign w:val="center"/></w:tcPr>'
                + _p(inline_runs(c.strip(), size=19, base_bold=header), spacing_after=0, line=280)
                + "</w:tc>"
            )
        out.append("</w:tr>")
    out.append("</w:tbl>")
    out.append(_p("", spacing_after=60, line=120))
    return "".join(out)


def parse_blocks(md):
    lines = md.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks, i = [], 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if not s:
            i += 1
            continue
        if s in ("<!--pagebreak-->", "---page---", "\\pagebreak"):
            blocks.append(("pagebreak", None))
            i += 1
            continue
        if s in ("---", "***", "___"):
            blocks.append(("hr", None))
            i += 1
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", s)
        if m:
            blocks.append(("h%d" % len(m.group(1)), m.group(2).strip()))
            i += 1
            continue
        if s.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                raw = lines[i].strip()
                if re.match(r"^\|[\s:\-|]+\|$", raw):
                    i += 1
                    continue
                cells = [c for c in raw.strip("|").split("|")]
                rows.append([c.strip() for c in cells])
                i += 1
            blocks.append(("table", rows))
            continue
        if re.match(r"^[-*+]\s+", s):
            items = []
            while i < len(lines) and re.match(r"^[-*+]\s+", lines[i].strip()):
                items.append(re.sub(r"^[-*+]\s+", "", lines[i].strip()))
                i += 1
            blocks.append(("ul", items))
            continue
        if re.match(r"^\d+[.)]\s+", s):
            items = []
            while i < len(lines) and re.match(r"^\d+[.)]\s+", lines[i].strip()):
                items.append(re.sub(r"^\d+[.)]\s+", "", lines[i].strip()))
                i += 1
            blocks.append(("ol", items))
            continue
        if s.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            blocks.append(("quote", " ".join(x for x in buf if x)))
            continue
        buf = [s]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if (not nxt or nxt.startswith(("#", "|", ">", "- ", "* ", "+ "))
                    or re.match(r"^\d+[.)]\s+", nxt) or nxt in ("---page---", "<!--pagebreak-->")):
                break
            buf.append(nxt)
            i += 1
        blocks.append(("p", " ".join(buf)))
    return blocks


def render_body(blocks, h1_size=32, h2_size=28, h3_size=24, body_size=21):
    out = []
    for kind, payload in blocks:
        if kind == "h1":
            out.append(_p(inline_runs(payload, size=h1_size, base_bold=True, font=FONT_HEAD),
                          align="center", keep_next=True, spacing_after=200, line=300))
        elif kind == "h2":
            out.append(_p(inline_runs(payload, size=h2_size, base_bold=True, font=FONT_HEAD),
                          keep_next=True, spacing_after=140, line=320))
        elif kind == "h3":
            out.append(_p(inline_runs(payload, size=h3_size, base_bold=True, font=FONT_HEAD),
                          keep_next=True, spacing_after=120, line=320))
        elif kind == "h4":
            out.append(_p(inline_runs(payload, size=body_size, base_bold=True),
                          keep_next=True, spacing_after=100))
        elif kind == "p":
            out.append(_p(inline_runs(payload, size=body_size), spacing_after=100))
        elif kind == "ul":
            for it in payload:
                out.append(_p("<w:r><w:t xml:space=\"preserve\">· </w:t></w:r>" + inline_runs(it, size=body_size),
                              ind_left=340, spacing_after=60))
        elif kind == "ol":
            for n, it in enumerate(payload, 1):
                out.append(_p(
                    f'<w:r><w:t xml:space="preserve">{n}. </w:t></w:r>' + inline_runs(it, size=body_size),
                    ind_left=340, spacing_after=60))
        elif kind == "quote":
            out.append(_p(inline_runs(payload, size=body_size, font=FONT_BODY),
                          ind_left=340, spacing_after=100, color=None, border_bottom=False))
        elif kind == "table":
            out.append(table_xml(payload))
        elif kind == "pagebreak":
            out.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
        elif kind == "hr":
            out.append(_p("", spacing_after=80, line=120, border_bottom=True))
    return "".join(out)


def build_docx(md_text, out_path, title="", meta="", footer_note="卓识教育·高中物理老师助手"):
    body = render_body(parse_blocks(md_text))
    sect = (
        "<w:sectPr>"
        f'<w:headerReference w:type="default" r:id="rId2"/>'
        f'<w:footerReference w:type="default" r:id="rId3"/>'
        f'<w:pgSz w:w="{A4_W}" w:h="{A4_H}"/>'
        f'<w:pgMar w:top="{MARGIN}" w:right="{MARGIN}" w:bottom="{MARGIN}" w:left="{MARGIN}" '
        'w:header="567" w:footer="567" w:gutter="0"/>'
        '<w:cols w:space="425"/><w:docGrid w:linePitch="312"/>'
        "</w:sectPr>"
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<w:body>{body}{sect}</w:body></w:document>"
    )

    head_left = _run(title or "文档", bold=True, size=18, color="595959")
    head_right = _run(meta, size=16, color="8C8C8C") if meta else ""
    header = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:p><w:pPr><w:pBdr><w:bottom w:val="single" w:sz="4" w:space="1" w:color="D9D9D9"/></w:pBdr>'
        '<w:tabs><w:tab w:val="right" w:pos="9866"/></w:tabs>'
        '<w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
        + head_left + '<w:r><w:tab/></w:r>' + head_right +
        "</w:p></w:hdr>"
    )
    footer = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
        + _run(footer_note + "    第 ", size=16, color="8C8C8C")
        + '<w:r><w:rPr><w:sz w:val="16"/><w:color w:val="8C8C8C"/></w:rPr><w:fldChar w:fldCharType="begin"/></w:r>'
        '<w:r><w:rPr><w:sz w:val="16"/><w:color w:val="8C8C8C"/></w:rPr><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
        '<w:r><w:rPr><w:sz w:val="16"/><w:color w:val="8C8C8C"/></w:rPr><w:fldChar w:fldCharType="separate"/></w:r>'
        '<w:r><w:rPr><w:sz w:val="16"/><w:color w:val="8C8C8C"/></w:rPr><w:t>1</w:t></w:r>'
        '<w:r><w:rPr><w:sz w:val="16"/><w:color w:val="8C8C8C"/></w:rPr><w:fldChar w:fldCharType="end"/></w:r>'
        + _run(" 页", size=16, color="8C8C8C") +
        "</w:p></w:ftr>"
    )

    styles = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:docDefaults><w:rPrDefault><w:rPr>"
        f'<w:rFonts w:ascii="{FONT_ASCII}" w:hAnsi="{FONT_ASCII}" w:eastAsia="{FONT_BODY}" w:cs="{FONT_ASCII}"/>'
        '<w:sz w:val="21"/><w:szCs w:val="21"/></w:rPr></w:rPrDefault>'
        '<w:pPrDefault><w:pPr><w:spacing w:after="100" w:line="360" w:lineRule="auto"/></w:pPr></w:pPrDefault>'
        "</w:docDefaults>"
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/>'
        '<w:qFormat/></w:style>'
        '<w:style w:type="table" w:styleId="TableNormal"><w:name w:val="Normal Table"/>'
        '<w:tblPr><w:tblCellMar><w:left w:w="80" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tblCellMar></w:tblPr></w:style>'
        "</w:styles>"
    )

    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        '<Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>'
        '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>'
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        '<Relationship Id="rId4" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        '<Relationship Id="rId5" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
        "</Relationships>"
    )
    doc_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>'
        "</Relationships>"
    )
    now = _dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    core = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f"<dc:title>{escape(title)}</dc:title>"
        "<dc:creator>卓识教育-高中物理老师助手</dc:creator>"
        f"<dcterms:created xsi:type=\"dcterms:W3CDTF\">{now}</dcterms:created>"
        f"<dcterms:modified xsi:type=\"dcterms:W3CDTF\">{now}</dcterms:modified>"
        "</cp:coreProperties>"
    )
    app = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
        "<Application>docx_lite</Application></Properties>"
    )

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", document)
        z.writestr("word/_rels/document.xml.rels", doc_rels)
        z.writestr("word/styles.xml", styles)
        z.writestr("word/header1.xml", header)
        z.writestr("word/footer1.xml", footer)
        z.writestr("docProps/core.xml", core)
        z.writestr("docProps/app.xml", app)
    return out_path


SAMPLE = """# 牛顿第二定律（第 1 课时）

> 高二 · 人教 2019 版 · 新授课

## 一、教学目标

1. 能说出加速度与合力、质量的定量关系。
2. 能用 **F=ma** 解决单过程问题。

## 二、教学过程

| 环节 | 时间 | 教师活动 |
|---|---|---|
| 导入 | 3′ | 播放电梯称重视频 |
| 探究 | 22′ | 控制变量实验 |

- 强调公式条件：惯性系、宏观低速
- 强调单位：N = kg·m/s²

<!--pagebreak-->

## 三、板书

公式区：F=ma；条件：合外力、惯性系。单位：N = kg·m/s²。
"""


def self_check():
    import tempfile
    tmp = os.path.join(tempfile.gettempdir(), "docx_lite_selftest.docx")
    build_docx(SAMPLE, tmp, title="自检文档", meta="高二·人教2019")
    ok = False
    with zipfile.ZipFile(tmp) as z:
        names = z.namelist()
        doc = z.read("word/document.xml").decode("utf-8")
        ok = ("word/document.xml" in names and "word/header1.xml" in names
              and "<w:tbl>" in doc and "pagebreak" not in doc and "sectPr" in doc)
    print("自检：", "通过" if ok else "失败", "->", tmp)
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="Markdown -> A4 docx")
    ap.add_argument("--in", dest="inp")
    ap.add_argument("--out", dest="out")
    ap.add_argument("--title", default="")
    ap.add_argument("--meta", default="")
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if a.self_check:
        return self_check()
    if not a.inp or not a.out:
        ap.print_help()
        return 2
    with open(a.inp, "r", encoding="utf-8") as f:
        md = f.read()
    title = a.title or os.path.splitext(os.path.basename(a.inp))[0]
    build_docx(md, a.out, title=title, meta=a.meta)
    print(f"已生成：{a.out}（{os.path.getsize(a.out) / 1024:.1f} KB）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
