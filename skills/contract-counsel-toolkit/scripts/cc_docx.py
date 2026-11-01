#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
契约守门人 · DOCX 生成器（零依赖）

为什么自己写：
    生成合同只要“标题 + 段落 + 表格 + 签署栏”这几样，引入 python-docx 会带来
    第三方依赖与再分发授权问题。这里按 ECMA-376 / OOXML 最小可用子集手写包结构，
    只用 zipfile + 字符串拼装，产出的 .docx 可被 Word / WPS / LibreOffice 正常打开。

包结构：
    [Content_Types].xml
    _rels/.rels
    docProps/core.xml, docProps/app.xml
    word/document.xml, word/styles.xml, word/settings.xml
    word/_rels/document.xml.rels

文档模型（dict）：
    {
      "meta": {"title": "...", "creator": "...", "subject": "..."},
      "blocks": [ {...}, ... ]
    }
块类型：
    {"t": "title",    "text": "采购合同"}
    {"t": "subtitle", "text": "合同编号：CC-2026-001"}
    {"t": "h1",       "text": "第一条  合同标的与价款"}
    {"t": "para",     "text": "...", "indent": true}
    {"t": "item",     "text": "（1）...", "no": "1."}
    {"t": "table",    "rows": [[...]], "widths": [2000, 4000], "header": true}
    {"t": "sign",     "left": ["甲方（盖章）：", "授权代表：", "日期："], "right": [...]}
    {"t": "note",     "text": "..."}
    {"t": "pagebreak"}
"""

import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

FONT_BODY_EA = "宋体"
FONT_HEAD_EA = "黑体"
FONT_ASCII = "Times New Roman"
FONT_ASCII_HEAD = "Arial"

CONTENT_W = 8306  # A4 宽 11906 - 左右边距 1800*2


def _x(text):
    return escape(str(text), {'"': "&quot;"})


# ---------------------------------------------------------------- run / para


def _rpr(bold=False, size=24, ea=FONT_BODY_EA, ascii_font=FONT_ASCII, color=None, underline=False):
    x = (
        '<w:rPr><w:rFonts w:ascii="%s" w:hAnsi="%s" w:eastAsia="%s" w:cs="%s"/>'
        % (ascii_font, ascii_font, ea, ascii_font)
    )
    if bold:
        x += "<w:b/><w:bCs/>"
    x += '<w:sz w:val="%d"/><w:szCs w:val="%d"/>' % (size, size)
    if underline:
        x += '<w:u w:val="single"/>'
    if color:
        x += '<w:color w:val="%s"/>' % color
    x += "</w:rPr>"
    return x


def _runs(text, **kw):
    """一段文本 -> 一个或多个 run；支持 \n 转软换行。"""
    parts = str(text).split("\n")
    out = []
    for i, part in enumerate(parts):
        if i:
            out.append('<w:r><w:br/></w:r>')
        if part == "":
            continue
        out.append('<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % (_rpr(**kw), _x(part)))
    if not out:
        out.append('<w:r>%s<w:t xml:space="preserve"> </w:t></w:r>' % _rpr(**kw))
    return "".join(out)


def _para(
    text="",
    align=None,
    indent_chars=0,
    left=0,
    hanging=0,
    size=24,
    bold=False,
    ea=FONT_BODY_EA,
    ascii_font=FONT_ASCII,
    before=0,
    after=0,
    line=360,
    keep_next=False,
    color=None,
):
    ppr = ["<w:pPr>"]
    if keep_next:
        ppr.append("<w:keepNext/>")
    ppr.append(
        '<w:spacing w:before="%d" w:after="%d" w:line="%d" w:lineRule="auto"/>' % (before, after, line)
    )
    if indent_chars or left or hanging:
        first_tw = int(indent_chars / 100.0 * 240)
        ppr.append(
            '<w:ind w:left="%d" w:firstLine="%d" w:firstLineChars="%d" w:hanging="%d"/>'
            % (left, first_tw, indent_chars, hanging)
        )
    if align:
        ppr.append('<w:jc w:val="%s"/>' % align)
    ppr.append("</w:pPr>")
    return "<w:p>%s%s</w:p>" % ("".join(ppr), _runs(text, bold=bold, size=size, ea=ea, ascii_font=ascii_font, color=color))


# -------------------------------------------------------------------- table


def _cell(text, width, bold=False, align="left", size=21):
    inner = _para(text, align=align, size=size, bold=bold, line=260, before=20, after=20)
    return (
        '<w:tc><w:tcPr><w:tcW w:w="%d" w:type="dxa"/><w:vAlign w:val="center"/></w:tcPr>%s</w:tc>'
        % (width, inner)
    )


def _table(rows, widths=None, header=True, align=None):
    ncol = max(len(r) for r in rows) if rows else 1
    if not widths:
        widths = [CONTENT_W // ncol] * ncol
    if len(widths) != ncol:
        widths = [CONTENT_W // ncol] * ncol
    borders = "".join(
        '<w:%s w:val="single" w:sz="6" w:space="0" w:color="000000"/>' % side
        for side in ("top", "left", "bottom", "right", "insideH", "insideV")
    )
    xml = [
        "<w:tbl><w:tblPr>",
        '<w:tblW w:w="%d" w:type="dxa"/>' % sum(widths),
        '<w:jc w:val="%s"/>' % (align or "center"),
        "<w:tblBorders>%s</w:tblBorders>" % borders,
        '<w:tblCellMar><w:top w:w="40" w:type="dxa"/><w:left w:w="80" w:type="dxa"/>'
        '<w:bottom w:w="40" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tblCellMar>',
        '<w:tblLayout w:type="fixed"/>',
        "</w:tblPr><w:tblGrid>",
    ]
    xml.extend('<w:gridCol w:w="%d"/>' % w for w in widths)
    xml.append("</w:tblGrid>")
    for i, row in enumerate(rows):
        is_head = header and i == 0
        xml.append("<w:tr><w:trPr>")
        if is_head:
            xml.append("<w:tblHeader/>")
        xml.append('<w:cantSplit/></w:trPr>')
        cells = list(row) + [""] * (ncol - len(row))
        for c, w in zip(cells, widths):
            xml.append(_cell(c, w, bold=is_head))
        xml.append("</w:tr>")
    xml.append("</w:tbl>")
    # 表后补一个空段，避免与下一段粘连
    xml.append(_para("", size=6, line=120))
    return "".join(xml)


def _sign_block(left, right):
    """无框线的两栏签署区。"""
    left_cells = "<w:tc><w:tcPr><w:tcW w:w=\"%d\" w:type=\"dxa\"/></w:tcPr>%s</w:tc>" % (
        CONTENT_W // 2,
        "".join(_para(t, size=24, line=400) for t in left),
    )
    right_cells = "<w:tc><w:tcPr><w:tcW w:w=\"%d\" w:type=\"dxa\"/></w:tcPr>%s</w:tc>" % (
        CONTENT_W // 2,
        "".join(_para(t, size=24, line=400) for t in right),
    )
    tbl_pr = (
        "<w:tblPr>"
        '<w:tblW w:w="%d" w:type="dxa"/><w:jc w:val="left"/>'
        '<w:tblBorders><w:top w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        '<w:left w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        '<w:bottom w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        '<w:right w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        '<w:insideH w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        '<w:insideV w:val="none" w:sz="0" w:space="0" w:color="auto"/></w:tblBorders>'
        '<w:tblLayout w:type="fixed"/>'
        "</w:tblPr><w:tblGrid><w:gridCol w:w=\"%d\"/><w:gridCol w:w=\"%d\"/></w:tblGrid>"
        % (CONTENT_W, CONTENT_W // 2, CONTENT_W // 2)
    )
    return "<w:tbl>%s<w:tr>%s%s</w:tr></w:tbl>" % (tbl_pr, left_cells, right_cells)


def _block(b):
    t = b.get("t", "para")
    if t == "title":
        return _para(
            b.get("text", ""), align="center", size=36, bold=True, ea=FONT_HEAD_EA,
            ascii_font=FONT_ASCII_HEAD, before=240, after=120, line=400, keep_next=True,
        )
    if t == "subtitle":
        return _para(b.get("text", ""), align="center", size=21, before=0, after=240, line=300)
    if t == "h1":
        return _para(
            b.get("text", ""), size=24, bold=True, ea=FONT_HEAD_EA, ascii_font=FONT_ASCII_HEAD,
            before=180, after=60, line=360, keep_next=True,
        )
    if t == "h2":
        return _para(
            b.get("text", ""), size=24, bold=True, before=120, after=40, line=360, keep_next=True,
        )
    if t == "para":
        return _para(
            b.get("text", ""), indent_chars=200 if b.get("indent", True) else 0,
            align=b.get("align"), size=24, line=360, before=b.get("before", 0), after=b.get("after", 0),
        )
    if t == "item":
        prefix = b.get("no", "")
        text = (prefix + " " + b.get("text", "")).strip()
        return _para(text, indent_chars=200, size=24, line=340)
    if t == "table":
        return _table(b.get("rows", []), b.get("widths"), b.get("header", True))
    if t == "sign":
        return _sign_block(b.get("left", []), b.get("right", []))
    if t == "note":
        return _para(b.get("text", ""), size=18, color="595959", before=60, after=60, line=280, indent_chars=0)
    if t == "pagebreak":
        return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
    return _para(b.get("text", ""))


# ---------------------------------------------------------------- package IO

SECT_PR = (
    "<w:sectPr>"
    '<w:pgSz w:w="11906" w:h="16838"/>'
    '<w:pgMar w:top="1440" w:right="1800" w:bottom="1440" w:left="1800" '
    'w:header="851" w:footer="992" w:gutter="0"/>'
    '<w:cols w:space="425"/>'
    '<w:docGrid w:type="lines" w:linePitch="312"/>'
    "</w:sectPr>"
)

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>"""

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""

DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>
</Relationships>"""

STYLES_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="%s">
<w:docDefaults>
<w:rPrDefault><w:rPr>
<w:rFonts w:ascii="%s" w:hAnsi="%s" w:eastAsia="%s" w:cs="%s"/>
<w:sz w:val="24"/><w:szCs w:val="24"/>
<w:spacing w:line="360" w:lineRule="auto"/>
</w:rPr></w:rPrDefault>
<w:pPrDefault><w:pPr><w:spacing w:line="360" w:lineRule="auto"/></w:pPr></w:pPrDefault>
</w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal">
<w:name w:val="Normal"/><w:qFormat/>
<w:pPr><w:spacing w:line="360" w:lineRule="auto"/></w:pPr>
<w:rPr><w:rFonts w:ascii="%s" w:hAnsi="%s" w:eastAsia="%s"/><w:sz w:val="24"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="Heading1">
<w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:qFormat/>
<w:pPr><w:outlineLvl w:val="0"/><w:spacing w:before="180" w:after="60"/></w:pPr>
<w:rPr><w:rFonts w:ascii="%s" w:hAnsi="%s" w:eastAsia="%s"/><w:b/><w:sz w:val="24"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="Heading2">
<w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:qFormat/>
<w:pPr><w:outlineLvl w:val="1"/><w:spacing w:before="120" w:after="40"/></w:pPr>
<w:rPr><w:rFonts w:ascii="%s" w:hAnsi="%s" w:eastAsia="%s"/><w:b/><w:sz w:val="24"/></w:rPr>
</w:style>
<w:style w:type="table" w:styleId="TableGrid">
<w:name w:val="Table Grid"/><w:basedOn w:val="TableNormal"/>
<w:pPr><w:spacing w:line="260" w:lineRule="auto"/></w:pPr>
</w:style>
</w:styles>""" % (W_NS, FONT_ASCII, FONT_ASCII, FONT_BODY_EA, FONT_ASCII,
                  FONT_ASCII, FONT_ASCII, FONT_BODY_EA,
                  FONT_ASCII_HEAD, FONT_ASCII_HEAD, FONT_HEAD_EA,
                  FONT_ASCII_HEAD, FONT_ASCII_HEAD, FONT_HEAD_EA)

SETTINGS_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="%s">
<w:zoom w:percent="100"/>
<w:defaultTabStop w:val="420"/>
<w:characterSpacingControl w:val="compressPunctuation"/>
<w:compat><w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="15"/></w:compat>
</w:settings>""" % W_NS

DOC_PROPS_APP = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
<Application>czl-contract-counsel</Application>
<DocSecurity>0</DocSecurity>
<ScaleCrop>false</ScaleCrop>
<Company>虫志龙</Company>
<LinksUpToDate>false</LinksUpToDate>
<SharedDoc>false</SharedDoc>
<HyperlinksChanged>false</HyperlinksChanged>
<AppVersion>1.0</AppVersion>
</Properties>"""


def _core_xml(title, creator, subject=""):
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        "<dc:title>%s</dc:title><dc:subject>%s</dc:subject><dc:creator>%s</dc:creator>"
        "<cp:lastModifiedBy>%s</cp:lastModifiedBy>"
        '<dcterms:created xsi:type="dcterms:W3CDTF">%s</dcterms:created>'
        '<dcterms:modified xsi:type="dcterms:W3CDTF">%s</dcterms:modified>'
        "</cp:coreProperties>" % (_x(title), _x(subject), _x(creator), _x(creator), now, now)
    )


def build_docx(model, out_path):
    """把文档模型写成 .docx，返回绝对路径。"""
    meta = model.get("meta", {})
    title = meta.get("title", "合同")
    creator = meta.get("creator", "契约守门人")
    subject = meta.get("subject", "合同文本")

    body = "".join(_block(b) for b in model.get("blocks", []))
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<w:document xmlns:w="%s" xmlns:r="%s"><w:body>%s%s</w:body></w:document>'
        % (W_NS, R_NS, body, SECT_PR)
    )

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", CONTENT_TYPES)
        zf.writestr("_rels/.rels", ROOT_RELS)
        zf.writestr("docProps/core.xml", _core_xml(title, creator, subject))
        zf.writestr("docProps/app.xml", DOC_PROPS_APP)
        zf.writestr("word/document.xml", document)
        zf.writestr("word/styles.xml", STYLES_XML)
        zf.writestr("word/settings.xml", SETTINGS_XML)
        zf.writestr("word/_rels/document.xml.rels", DOC_RELS)
    return str(out.resolve())


REQUIRED_PARTS = [
    "[Content_Types].xml",
    "_rels/.rels",
    "word/document.xml",
    "word/styles.xml",
    "word/settings.xml",
    "word/_rels/document.xml.rels",
    "docProps/core.xml",
]


def verify_docx(path):
    """
    结构自检：包内必需部件齐全、XML 可解析、正文非空。
    这不是“用 Word 打开过”，只能证明包结构与 XML 合法；真实打开效果需人工确认。
    """
    from xml.dom import minidom

    result = {"file": str(path), "ok": False, "parts": [], "paragraphs": 0, "tables": 0, "errors": []}
    try:
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            result["parts"] = names
            for part in REQUIRED_PARTS:
                if part not in names:
                    result["errors"].append("缺少部件：" + part)
            for part in names:
                if part.endswith(".xml") or part.endswith(".rels"):
                    try:
                        minidom.parseString(zf.read(part))
                    except Exception as exc:  # noqa: BLE001
                        result["errors"].append("XML 解析失败 %s: %s" % (part, exc))
            if "word/document.xml" in names:
                doc = zf.read("word/document.xml").decode("utf-8")
                result["paragraphs"] = len(re.findall(r"<w:p[ >]", doc))
                result["tables"] = len(re.findall(r"<w:tbl>", doc))
                text = re.sub(r"<[^>]+>", "", doc).strip()
                if len(text) < 20:
                    result["errors"].append("正文内容过短，可能是空文档")
        result["ok"] = not result["errors"]
    except Exception as exc:  # noqa: BLE001
        result["errors"].append("无法读取 docx 包：%s" % exc)
    return result
