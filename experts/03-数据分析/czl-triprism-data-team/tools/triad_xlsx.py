# -*- coding: utf-8 -*-
"""三棱镜 · 极简 XLSX 写出器（纯标准库）

为什么自己写：商用发布包不想绑定 openpyxl 这类第三方库的许可证与版本风险，
而本产品只需要「多工作表 + 表头样式 + 数字格式 + 冻结首行」这几件事。

实现方式：直接拼 OOXML，用 zipfile 打包。字符串统一用 inlineStr，
避免共享字符串表的额外状态，Excel / WPS / LibreOffice 均可正常打开。
"""

from __future__ import annotations

import re
import zipfile
from xml.sax.saxutils import escape

INVALID_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

CT = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
{sheets}
</Types>"""

RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

WB_HEAD = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets>"""

WB_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
{rels}
<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<numFmts count="2">
<numFmt numFmtId="164" formatCode="#,##0.00"/>
<numFmt numFmtId="165" formatCode="0.00&quot;%&quot;"/>
</numFmts>
<fonts count="4">
<font><sz val="11"/><name val="Microsoft YaHei"/></font>
<font><b/><sz val="11"/><name val="Microsoft YaHei"/></font>
<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Microsoft YaHei"/></font>
<font><sz val="9"/><color rgb="FF667085"/><name val="Microsoft YaHei"/></font>
</fonts>
<fills count="4">
<fill><patternFill patternType="none"/></fill>
<fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF1F3A5F"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFF2F5F9"/><bgColor indexed="64"/></patternFill></fill>
</fills>
<borders count="2">
<border><left/><right/><top/><bottom/><diagonal/></border>
<border><left style="thin"><color rgb="FFD0D7E2"/></left><right style="thin"><color rgb="FFD0D7E2"/></right><top style="thin"><color rgb="FFD0D7E2"/></top><bottom style="thin"><color rgb="FFD0D7E2"/></bottom><diagonal/></border>
</borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="5">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>
<xf numFmtId="0" fontId="2" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"><alignment horizontal="left" vertical="center"/></xf>
<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
<xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
</cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>"""

S_DEFAULT, S_BOLD, S_HEADER, S_NUM2, S_PCT = 0, 1, 2, 3, 4


def _clean(v):
    if v is None:
        return ""
    s = str(v)
    return INVALID_XML.sub("", s)


def _col_letter(i):
    letters = ""
    i += 1
    while i:
        i, rem = divmod(i - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def _cell(ref, value, style=0):
    if value is None or (isinstance(value, str) and value == ""):
        return f'<c r="{ref}" s="{style}"/>' if style else ""
    if isinstance(value, bool):
        return f'<c r="{ref}" t="b" s="{style}"><v>{1 if value else 0}</v></c>'
    if isinstance(value, (int, float)):
        if value != value or value in (float("inf"), float("-inf")):
            return f'<c r="{ref}" s="{style}" t="inlineStr"><is><t>n/a</t></is></c>'
        return f'<c r="{ref}" s="{style}"><v>{value}</v></c>'
    return f'<c r="{ref}" t="inlineStr" s="{style}"><is><t xml:space="preserve">{escape(_clean(value))}</t></is></c>'


class Sheet:
    def __init__(self, name, header=None, rows=None, widths=None, freeze=True,
                 number_cols=None, pct_cols=None):
        self.name = name
        self.header = header or []
        self.rows = rows or []
        self.widths = widths or []
        self.freeze = freeze
        self.number_cols = set(number_cols or [])
        self.pct_cols = set(pct_cols or [])

    def to_xml(self):
        n_cols = max([len(self.header)] + [len(r) for r in self.rows] + [1])
        cols_xml = ""
        if self.widths:
            parts = []
            for i in range(n_cols):
                w = self.widths[i] if i < len(self.widths) else 16
                parts.append(f'<col min="{i+1}" max="{i+1}" width="{w}" customWidth="1"/>')
            cols_xml = "<cols>" + "".join(parts) + "</cols>"
        sheet_views = ('<sheetViews><sheetView workbookViewId="0">'
                       + ('<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>' if self.freeze and self.header else "")
                       + "</sheetView></sheetViews>")
        out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
               '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
               sheet_views, cols_xml, "<sheetData>"]
        r_no = 1
        if self.header:
            cells = "".join(_cell(f"{_col_letter(i)}{r_no}", h, S_HEADER) for i, h in enumerate(self.header))
            out.append(f'<row r="{r_no}" ht="22" customHeight="1">{cells}</row>')
            r_no += 1
        for row in self.rows:
            cells = []
            for i, v in enumerate(row):
                style = S_DEFAULT
                if i in self.number_cols and isinstance(v, (int, float)):
                    style = S_NUM2
                if i in self.pct_cols and isinstance(v, (int, float)):
                    style = S_PCT
                cells.append(_cell(f"{_col_letter(i)}{r_no}", v, style))
            out.append(f'<row r="{r_no}">{"".join(cells)}</row>')
            r_no += 1
        out.append("</sheetData></worksheet>")
        return "".join(out)


def write_workbook(path, sheets):
    names = []
    for i, sh in enumerate(sheets, 1):
        base = re.sub(r"[\\/*?:\[\]]", "-", sh.name)[:31] or f"Sheet{i}"
        name, k = base, 2
        while name in names:
            name = f"{base[:28]}_{k}"
            k += 1
        names.append(name)
        sh.name = name

    overrides = "\n".join(
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
        f'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(1, len(sheets) + 1))
    wb_sheets = "".join(f'<sheet name="{escape(s.name)}" sheetId="{i}" r:id="rId{i}"/>'
                        for i, s in enumerate(sheets, 1))
    rels = "\n".join(
        f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{i}.xml"/>' for i in range(1, len(sheets) + 1))
    workbook = (WB_HEAD + wb_sheets + "</sheets></workbook>")

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", CT.format(sheets=overrides))
        zf.writestr("_rels/.rels", RELS)
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/_rels/workbook.xml.rels", WB_RELS.format(rels=rels))
        zf.writestr("xl/styles.xml", STYLES)
        for i, sh in enumerate(sheets, 1):
            zf.writestr(f"xl/worksheets/sheet{i}.xml", sh.to_xml())
    return path
