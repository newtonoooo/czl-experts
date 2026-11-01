#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_docx.py — 把 Markdown 成稿转成 A4 打印版 .docx（纯标准库，无需 Word / python-docx）

特点：
    - A4 纵向、上下左右 2.54cm 页边距、正文小四宋体、标题黑体、1.5 倍行距、首行缩进 2 字符
    - 支持 # / ## / ### 标题、段落、无序列表、有序列表、Markdown 表格、**加粗**
    - 页脚居中页码，页眉可留空
    - 生成的是标准 OOXML 包，Word / WPS / LibreOffice 均可打开

用法：
    python make_docx.py -i 教案.md -o 分离定律_教案_20261101.docx --title "分离定律 教案"
"""

import argparse
import datetime as _dt
import os
import re
import sys
import zipfile
from typing import List, Tuple

NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

CONTENT_WIDTH = 11906 - 2 * 1440  # A4 宽减左右边距，单位 twip


def esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def runs(text: str, bold_all: bool = False) -> str:
    """把 **加粗** 拆成多个 run。"""
    parts = re.split(r"(\*\*.+?\*\*)", text)
    out = []
    for p in parts:
        if not p:
            continue
        b = bold_all
        if p.startswith("**") and p.endswith("**") and len(p) > 4:
            p = p[2:-2]
            b = True
        rpr = "<w:rPr><w:b/></w:rPr>" if b else ""
        out.append(f'<w:r>{rpr}<w:t xml:space="preserve">{esc(p)}</w:t></w:r>')
    return "".join(out) if out else "<w:r><w:t xml:space=\"preserve\"></w:t></w:r>"


def para(text: str, style: str = "Normal", extra_ppr: str = "", bold_all: bool = False) -> str:
    return (f'<w:p><w:pPr><w:pStyle w:val="{style}"/>{extra_ppr}</w:pPr>'
            f'{runs(text, bold_all)}</w:p>')


def table_block(rows: List[List[str]]) -> str:
    if not rows:
        return ""
    cols = max(len(r) for r in rows)
    width = CONTENT_WIDTH // max(cols, 1)
    grid = "".join(f'<w:gridCol w:w="{width}"/>' for _ in range(cols))
    trs = []
    for ri, row in enumerate(rows):
        cells = []
        for ci in range(cols):
            txt = row[ci] if ci < len(row) else ""
            bold = (ri == 0)
            cells.append(
                f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>'
                f'<w:vAlign w:val="center"/></w:tcPr>'
                f'<w:p><w:pPr><w:pStyle w:val="TableText"/></w:pPr>{runs(txt, bold)}</w:p></w:tc>'
            )
        trpr = "<w:trPr><w:tblHeader/></w:trPr>" if ri == 0 else ""
        trs.append(f"<w:tr>{trpr}{''.join(cells)}</w:tr>")
    borders = "".join(
        f'<w:{side} w:val="single" w:sz="4" w:space="0" w:color="808080"/>'
        for side in ("top", "left", "bottom", "right", "insideH", "insideV")
    )
    return (f'<w:tbl><w:tblPr><w:tblW w:w="{CONTENT_WIDTH}" w:type="dxa"/>'
            f'<w:jc w:val="center"/><w:tblBorders>{borders}</w:tblBorders>'
            f'<w:tblLayout w:type="fixed"/></w:tblPr>'
            f'<w:tblGrid>{grid}</w:tblGrid>{"".join(trs)}</w:tbl>'
            f'<w:p><w:pPr><w:pStyle w:val="TableGap"/></w:pPr></w:p>')


def split_row(line: str) -> List[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def is_sep_row(line: str) -> bool:
    s = line.strip()
    if not s.startswith("|"):
        return False
    body = s.strip("|")
    return bool(re.fullmatch(r"[\s:\-|]+", body)) and "-" in body


def markdown_to_body(md: str) -> str:
    lines = md.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: List[str] = []
    i = 0
    in_code = False
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            in_code = not in_code
            i += 1
            continue

        if in_code:
            out.append(para(line if line else " ", "Code"))
            i += 1
            continue

        if not stripped:
            i += 1
            continue

        if re.fullmatch(r"[-*_]{3,}", stripped):
            out.append('<w:p><w:pPr><w:pStyle w:val="Hr"/></w:pPr></w:p>')
            i += 1
            continue

        if stripped.startswith("|") and i + 1 < len(lines) and is_sep_row(lines[i + 1]):
            rows = [split_row(stripped)]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(split_row(lines[i].strip()))
                i += 1
            out.append(table_block(rows))
            continue

        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            level = len(m.group(1))
            style = {1: "Heading1", 2: "Heading2", 3: "Heading3", 4: "Heading3"}[level]
            out.append(para(m.group(2).strip(), style))
            i += 1
            continue

        if stripped.startswith(">"):
            out.append(para(stripped.lstrip("> ").strip(), "Quote"))
            i += 1
            continue

        m = re.match(r"^[-*+]\s+(.*)$", stripped)
        if m:
            out.append(para("• " + m.group(1), "ListBullet"))
            i += 1
            continue

        m = re.match(r"^(\d+[.、)])\s+(.*)$", stripped)
        if m:
            out.append(para(f"{m.group(1)} {m.group(2)}", "ListNumber"))
            i += 1
            continue

        out.append(para(stripped))
        i += 1

    if not out:
        out.append(para("（空白文档）"))
    return "".join(out)


def build_document(body: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<w:document xmlns:w="{NS_W}" xmlns:r="{NS_R}"><w:body>{body}'
        '<w:sectPr><w:footerReference w:type="default" r:id="rId2"/>'
        '<w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" '
        'w:header="851" w:footer="992" w:gutter="0"/>'
        '<w:cols w:space="425"/><w:docGrid w:type="lines" w:linePitch="312"/></w:sectPr>'
        "</w:body></w:document>"
    )


def build_styles() -> str:
    def style(sid, name, ppr, rpr, based="Normal", next_="Normal"):
        return (f'<w:style w:type="paragraph" w:styleId="{sid}"><w:name w:val="{name}"/>'
                f'<w:basedOn w:val="{based}"/><w:next w:val="{next_}"/>'
                f'<w:qFormat/><w:pPr>{ppr}</w:pPr><w:rPr>{rpr}</w:rPr></w:style>')

    normal_ppr = '<w:spacing w:line="360" w:lineRule="auto"/><w:ind w:firstLineChars="200" w:firstLine="480"/>'
    normal_rpr = ('<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="宋体"/>'
                  '<w:sz w:val="24"/><w:szCs w:val="24"/>')
    heading_rpr = ('<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="黑体"/>'
                   '<w:b/><w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<w:styles xmlns:w="{NS_W}">'
        '<w:docDefaults><w:rPrDefault><w:rPr>'
        '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="宋体"/>'
        '<w:sz w:val="24"/><w:szCs w:val="24"/><w:lang w:val="en-US" w:eastAsia="zh-CN"/>'
        '</w:rPr></w:rPrDefault><w:pPrDefault><w:pPr>'
        '<w:spacing w:line="360" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>'
        + style("Normal", "Normal", normal_ppr, normal_rpr)
        + style("Heading1", "heading 1",
                '<w:spacing w:before="240" w:after="120" w:line="360" w:lineRule="auto"/><w:jc w:val="center"/>',
                heading_rpr.format(sz="36"))
        + style("Heading2", "heading 2",
                '<w:spacing w:before="200" w:after="100" w:line="360" w:lineRule="auto"/>',
                heading_rpr.format(sz="30"))
        + style("Heading3", "heading 3",
                '<w:spacing w:before="160" w:after="80" w:line="360" w:lineRule="auto"/>',
                heading_rpr.format(sz="26"))
        + style("ListBullet", "List Bullet",
                '<w:spacing w:line="360" w:lineRule="auto"/><w:ind w:left="480" w:hanging="240"/>', normal_rpr)
        + style("ListNumber", "List Number",
                '<w:spacing w:line="360" w:lineRule="auto"/><w:ind w:left="480" w:hanging="240"/>', normal_rpr)
        + style("Quote", "Quote",
                '<w:spacing w:line="360" w:lineRule="auto"/><w:ind w:left="480" w:right="480"/>',
                '<w:rFonts w:eastAsia="楷体"/><w:i/><w:sz w:val="22"/>')
        + style("Code", "Code",
                '<w:spacing w:line="240" w:lineRule="auto"/><w:ind w:left="240"/>',
                '<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:eastAsia="等线"/><w:sz w:val="20"/>')
        + style("TableText", "Table Text",
                '<w:spacing w:line="240" w:lineRule="auto"/><w:jc w:val="left"/>',
                '<w:rFonts w:eastAsia="宋体"/><w:sz w:val="21"/>')
        + style("TableGap", "Table Gap", '<w:spacing w:line="120" w:lineRule="auto"/>', '<w:sz w:val="8"/>')
        + style("Hr", "Hr", '<w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="BFBFBF"/></w:pBdr>',
                '<w:sz w:val="8"/>')
        + "</w:styles>"
    )


def build_footer() -> str:
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            f'<w:ftr xmlns:w="{NS_W}" xmlns:r="{NS_R}">'
            '<w:p><w:pPr><w:jc w:val="center"/></w:pPr>'
            '<w:r><w:t xml:space="preserve">第 </w:t></w:r>'
            '<w:fldSimple w:instr=" PAGE "><w:r><w:t>1</w:t></w:r></w:fldSimple>'
            '<w:r><w:t xml:space="preserve"> 页</w:t></w:r></w:p></w:ftr>')


CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
    '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>'
    '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
    '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
    '</Types>'
)

RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
    '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
    '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
    '</Relationships>'
)

DOC_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>'
    '</Relationships>'
)


def core_xml(title: str, author: str) -> str:
    now = _dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            f'<dc:title>{esc(title)}</dc:title><dc:creator>{esc(author)}</dc:creator>'
            f'<cp:lastModifiedBy>{esc(author)}</cp:lastModifiedBy>'
            f'<dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>'
            f'<dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>'
            '</cp:coreProperties>')


APP_XML = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
           '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
           'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
           '<Application>czl-bio-teacher-kit</Application></Properties>')


def convert(md_path: str, out_path: str, title: str, author: str) -> str:
    with open(md_path, "r", encoding="utf-8-sig") as fh:
        md = fh.read()
    body = markdown_to_body(md)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/document.xml", build_document(body))
        z.writestr("word/styles.xml", build_styles())
        z.writestr("word/footer1.xml", build_footer())
        z.writestr("word/_rels/document.xml.rels", DOC_RELS)
        z.writestr("docProps/core.xml", core_xml(title, author))
        z.writestr("docProps/app.xml", APP_XML)
    return out_path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Markdown 转 A4 打印版 docx")
    ap.add_argument("-i", "--input", required=True, help="Markdown 文件")
    ap.add_argument("-o", "--output", required=True, help="输出 docx 路径")
    ap.add_argument("--title", default="", help="文档标题（写入属性）")
    ap.add_argument("--author", default="卓识教育", help="作者")
    args = ap.parse_args(argv)

    if not os.path.exists(args.input):
        print(f"[错误] 找不到文件: {args.input}", file=sys.stderr)
        return 2
    title = args.title or os.path.splitext(os.path.basename(args.input))[0]
    try:
        out = convert(args.input, args.output, title, args.author)
    except Exception as exc:  # noqa: BLE001
        print(f"[错误] 生成失败: {exc}", file=sys.stderr)
        return 1
    print(f"已生成 {out}（{os.path.getsize(out)/1024:.1f} KB）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
