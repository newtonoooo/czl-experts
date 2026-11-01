#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""md_to_docx.py —— Markdown 转 Word（.docx），纯标准库，零依赖。

为什么要有这个脚本：
    教案、试卷、学情报告最终都要打印。让模型"写一个 docx"不可靠，
    让老师装 python-docx 也不现实。docx 本质是一个装着 XML 的 zip，
    用标准库就能生成，任何一台装了 Python 的电脑都能跑。

支持的 Markdown 子集（够用于教案/试卷/报告）：
    # / ## / ### / ####     标题
    普通段落                正文（宋体小四，1.5 倍行距）
    **粗体**                行内加粗
    `代码`                  行内等宽
    - 项 / * 项             无序列表
    1. 项                   有序列表（保留序号文本）
    > 引用                  灰底缩进段
    | a | b |               表格（第二行必须是对齐行 |---|）
    ``` 围栏 ```            代码块（等宽，浅底）
    ---                     分隔线
    \\newpage                分页

用法：
    python bin/md_to_docx.py 教案.md -o 教案.docx
    python bin/md_to_docx.py 试卷.md -o 试卷.docx --footer "高二 · 人教A版 · 第一次月考"
    python bin/md_to_docx.py 报告.md -o 报告.docx --check   # 只检查，不生成

退出码：0 成功；1 失败（含 XML 自检不通过）。
"""

import argparse
import datetime
import os
import re
import sys
import zipfile
from xml.dom import minidom
from xml.sax.saxutils import escape

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
XML_DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'

PAGE_W, PAGE_H = 11906, 16838          # A4，单位 twip
MARGIN_TB, MARGIN_LR = 1440, 1800      # 上下 2.54cm，左右 3.18cm
USABLE_W = PAGE_W - 2 * MARGIN_LR      # 8306

FONT_BODY_EA = "宋体"
FONT_BODY_ASCII = "Times New Roman"
FONT_HEAD_EA = "黑体"
FONT_MONO = "Consolas"


def esc(t):
    return escape(t, {'"': "&quot;"})


# ---------------------------------------------------------------- styles

def styles_xml():
    return XML_DECL + (
        '<w:styles xmlns:w="%s">'
        '<w:docDefaults><w:rPrDefault><w:rPr>'
        '<w:rFonts w:ascii="%s" w:hAnsi="%s" w:eastAsia="%s" w:cs="%s"/>'
        '<w:sz w:val="24"/><w:szCs w:val="24"/>'
        '</w:rPr></w:rPrDefault>'
        '<w:pPrDefault><w:pPr>'
        '<w:spacing w:line="360" w:lineRule="auto" w:before="0" w:after="80"/>'
        '<w:jc w:val="both"/>'
        '</w:pPr></w:pPrDefault></w:docDefaults>'
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
        '<w:name w:val="Normal"/><w:qFormat/></w:style>'
        '%s%s%s%s'
        '<w:style w:type="paragraph" w:styleId="ListParagraph">'
        '<w:name w:val="List Paragraph"/><w:basedOn w:val="Normal"/>'
        '<w:pPr><w:ind w:left="420" w:hanging="210"/><w:jc w:val="left"/></w:pPr></w:style>'
        '<w:style w:type="table" w:styleId="TableGrid">'
        '<w:name w:val="Table Grid"/><w:tblPr>'
        '<w:tblBorders>'
        '<w:top w:val="single" w:sz="4" w:space="0" w:color="808080"/>'
        '<w:left w:val="single" w:sz="4" w:space="0" w:color="808080"/>'
        '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="808080"/>'
        '<w:right w:val="single" w:sz="4" w:space="0" w:color="808080"/>'
        '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="808080"/>'
        '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="808080"/>'
        '</w:tblBorders></w:tblPr></w:style>'
        '</w:styles>'
    ) % (W_NS, FONT_BODY_ASCII, FONT_BODY_ASCII, FONT_BODY_EA, FONT_BODY_ASCII,
         *(_heading_style(i) for i in (1, 2, 3, 4)))


def _heading_style(level):
    sizes = {1: 36, 2: 32, 3: 28, 4: 26}
    before = {1: 240, 2: 240, 3: 200, 4: 180}
    after = {1: 180, 2: 140, 3: 120, 4: 100}
    return (
        '<w:style w:type="paragraph" w:styleId="Heading{lv}">'
        '<w:name w:val="heading {lv}"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/>'
        '<w:qFormat/>'
        '<w:pPr><w:keepNext/><w:spacing w:before="{bf}" w:after="{af}" w:line="300" w:lineRule="auto"/>'
        '<w:outlineLvl w:val="{lvl}"/><w:jc w:val="left"/></w:pPr>'
        '<w:rPr><w:rFonts w:ascii="{fa}" w:hAnsi="{fa}" w:eastAsia="{fe}"/>'
        '<w:b/><w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/></w:rPr>'
        '</w:style>'
    ).format(lv=level, lvl=level - 1, bf=before[level], af=after[level],
             fa=FONT_BODY_ASCII, fe=FONT_HEAD_EA, sz=sizes[level])


# ---------------------------------------------------------------- runs

TOKEN_RE = re.compile(r"(\*\*.+?\*\*|`[^`]+`)")


def runs_xml(text, bold=False, mono=False, color=None, size=None):
    """把一行文本转成若干 w:r，处理 **粗体** 与 `代码`。"""
    out = []
    for part in TOKEN_RE.split(text):
        if not part:
            continue
        b, m = bold, mono
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            part = part[2:-2]
            b = True
        elif part.startswith("`") and part.endswith("`") and len(part) > 2:
            part = part[1:-1]
            m = True
        rpr = []
        if m:
            rpr.append('<w:rFonts w:ascii="%s" w:hAnsi="%s" w:eastAsia="%s"/>'
                       % (FONT_MONO, FONT_MONO, FONT_BODY_EA))
        if b:
            rpr.append("<w:b/>")
        if color:
            rpr.append('<w:color w:val="%s"/>' % color)
        if size:
            rpr.append('<w:sz w:val="%d"/><w:szCs w:val="%d"/>' % (size, size))
        rpr_xml = "<w:rPr>%s</w:rPr>" % "".join(rpr) if rpr else ""
        out.append('<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % (rpr_xml, esc(part)))
    return "".join(out)


def para(text="", style=None, indent=0, align=None, shade=None,
         color=None, size=None, bold=False, mono=False, border_bottom=False,
         spacing_before=None, spacing_after=None, keep_next=False):
    ppr = []
    if style:
        ppr.append('<w:pStyle w:val="%s"/>' % style)
    if keep_next:
        ppr.append("<w:keepNext/>")
    spacing = []
    if spacing_before is not None:
        spacing.append('w:before="%d"' % spacing_before)
    if spacing_after is not None:
        spacing.append('w:after="%d"' % spacing_after)
    if spacing:
        ppr.append("<w:spacing %s/>" % " ".join(spacing))
    if indent:
        ppr.append('<w:ind w:left="%d"/>' % indent)
    if align:
        ppr.append('<w:jc w:val="%s"/>' % align)
    if shade:
        ppr.append('<w:shd w:val="clear" w:color="auto" w:fill="%s"/>' % shade)
    if border_bottom:
        ppr.append('<w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="BFBFBF"/></w:pBdr>')
    ppr_xml = "<w:pPr>%s</w:pPr>" % "".join(ppr) if ppr else ""
    body = runs_xml(text, bold=bold, mono=mono, color=color, size=size) if text else ""
    return "<w:p>%s%s</w:p>" % (ppr_xml, body)


def table_xml(rows):
    ncol = max(len(r) for r in rows)
    if ncol == 0:
        return ""
    col_w = int(USABLE_W / ncol)
    grid = "".join('<w:gridCol w:w="%d"/>' % col_w for _ in range(ncol))
    out = ['<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/>'
           '<w:tblW w:w="%d" w:type="dxa"/><w:jc w:val="center"/>'
           '<w:tblLayout w:type="fixed"/></w:tblPr><w:tblGrid>%s</w:tblGrid>'
           % (USABLE_W, grid)]
    for ri, row in enumerate(rows):
        cells = []
        for ci in range(ncol):
            txt = row[ci] if ci < len(row) else ""
            is_head = ri == 0
            p = para(txt, align="center" if is_head or ci == 0 else "left",
                     bold=is_head, size=21, spacing_after=0)
            shade = '<w:shd w:val="clear" w:color="auto" w:fill="F2F2F2"/>' if is_head else ""
            cells.append('<w:tc><w:tcPr><w:tcW w:w="%d" w:type="dxa"/>%s'
                         '<w:vAlign w:val="center"/></w:tcPr>%s</w:tc>' % (col_w, shade, p))
        trpr = "<w:trPr><w:tblHeader/></w:trPr>" if ri == 0 else ""
        out.append("<w:tr>%s%s</w:tr>" % (trpr, "".join(cells)))
    out.append("</w:tbl>")
    return "".join(out)


# ---------------------------------------------------------------- md → body

def split_row(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
    # 去掉末尾的竖线
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def is_align_row(line):
    s = line.strip().strip("|").replace(" ", "")
    return bool(s) and all(ch in "-:|" for ch in s) and "-" in s


def convert(md, footer=None):
    lines = md.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    body = []
    i = 0
    in_code = False
    code_buf = []
    first_h1 = True

    while i < len(lines):
        line = lines[i]

        # 代码围栏
        if line.strip().startswith("```"):
            if in_code:
                for cl in code_buf:
                    body.append(para(cl if cl else " ", style=None, mono=True,
                                     size=20, indent=120, shade="F4F4F4",
                                     align="left", spacing_after=0))
                body.append(para("", spacing_after=60))
                code_buf = []
                in_code = False
            else:
                in_code = True
            i += 1
            continue
        if in_code:
            code_buf.append(line)
            i += 1
            continue

        stripped = line.strip()

        if stripped == "":
            i += 1
            continue

        if stripped in ("\\newpage", "\\pagebreak"):
            body.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
            i += 1
            continue

        # 分隔线
        if re.fullmatch(r"-{3,}", stripped):
            body.append(para("", border_bottom=True, spacing_before=60, spacing_after=60))
            i += 1
            continue

        # 标题
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            level = min(len(m.group(1)), 4)
            text = m.group(2).strip()
            if level == 1 and first_h1:
                body.append(para(text, style="Heading1", align="center"))
                first_h1 = False
            else:
                body.append(para(text, style="Heading%d" % level))
            i += 1
            continue

        # 表格
        if stripped.startswith("|") and i + 1 < len(lines) and is_align_row(lines[i + 1]):
            rows = [split_row(stripped)]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            body.append(table_xml(rows))
            body.append(para("", spacing_after=60))
            continue

        # 引用
        if stripped.startswith(">"):
            text = stripped.lstrip(">").strip()
            body.append(para(text, indent=280, color="595959", size=21,
                             spacing_before=40, spacing_after=40))
            i += 1
            continue

        # 无序列表
        m = re.match(r"^[-*+]\s+(.*)$", stripped)
        if m:
            body.append(para("•  " + m.group(1), style="ListParagraph"))
            i += 1
            continue

        # 有序列表
        m = re.match(r"^(\d+)[.)]\s+(.*)$", stripped)
        if m:
            body.append(para("%s.  %s" % (m.group(1), m.group(2)), style="ListParagraph"))
            i += 1
            continue

        # 普通段落
        body.append(para(stripped))
        i += 1

    if in_code and code_buf:
        for cl in code_buf:
            body.append(para(cl if cl else " ", mono=True, size=20, indent=120, shade="F4F4F4"))

    sect = (
        '<w:sectPr>'
        + ('<w:footerReference w:type="default" r:id="rId1"/>' if footer is not None else "")
        + '<w:pgSz w:w="%d" w:h="%d"/>' % (PAGE_W, PAGE_H)
        + '<w:pgMar w:top="%d" w:right="%d" w:bottom="%d" w:left="%d" w:header="851" w:footer="992" w:gutter="0"/>'
          % (MARGIN_TB, MARGIN_LR, MARGIN_TB, MARGIN_LR)
        + '<w:cols w:space="425"/><w:docGrid w:linePitch="312"/>'
        + "</w:sectPr>"
    )
    document = XML_DECL + (
        '<w:document xmlns:w="%s" xmlns:r="%s"><w:body>%s%s</w:body></w:document>'
        % (W_NS, R_NS, "".join(body), sect)
    )
    return document


def footer_xml(text):
    return XML_DECL + (
        '<w:ftr xmlns:w="%s" xmlns:r="%s"><w:p><w:pPr><w:jc w:val="center"/>'
        '<w:rPr><w:rFonts w:ascii="%s" w:hAnsi="%s" w:eastAsia="%s"/>'
        '<w:sz w:val="18"/><w:color w:val="808080"/></w:rPr></w:pPr>'
        '<w:r><w:rPr><w:rFonts w:ascii="%s" w:hAnsi="%s" w:eastAsia="%s"/>'
        '<w:sz w:val="18"/><w:color w:val="808080"/></w:rPr>'
        '<w:t xml:space="preserve">%s　·　第 </w:t></w:r>'
        '<w:fldSimple w:instr=" PAGE "><w:r><w:rPr><w:sz w:val="18"/>'
        '<w:color w:val="808080"/></w:rPr><w:t>1</w:t></w:r></w:fldSimple>'
        '<w:r><w:rPr><w:rFonts w:ascii="%s" w:hAnsi="%s" w:eastAsia="%s"/>'
        '<w:sz w:val="18"/><w:color w:val="808080"/></w:rPr>'
        '<w:t xml:space="preserve"> 页</w:t></w:r></w:p></w:ftr>'
    ) % (W_NS, R_NS, FONT_BODY_ASCII, FONT_BODY_ASCII, FONT_BODY_EA,
         FONT_BODY_ASCII, FONT_BODY_ASCII, FONT_BODY_EA, esc(text),
         FONT_BODY_ASCII, FONT_BODY_ASCII, FONT_BODY_EA)


CONTENT_TYPES = XML_DECL + (
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

ROOT_RELS = XML_DECL + (
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
    '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
    '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
    '</Relationships>'
)


def doc_rels(with_footer):
    rels = [
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    ]
    if with_footer:
        rels.append('<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>')
    return XML_DECL + (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">%s</Relationships>'
        % "".join(rels)
    )


def core_xml(title):
    now = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    return XML_DECL + (
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        '<dc:title>%s</dc:title><dc:creator>czl-math-teacher-desk</dc:creator>'
        '<cp:lastModifiedBy>czl-math-teacher-desk</cp:lastModifiedBy>'
        '<dcterms:created xsi:type="dcterms:W3CDTF">%s</dcterms:created>'
        '<dcterms:modified xsi:type="dcterms:W3CDTF">%s</dcterms:modified>'
        '</cp:coreProperties>'
    ) % (esc(title), now, now)


APP_XML = XML_DECL + (
    '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
    'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
    '<Application>czl-math-teacher-desk</Application></Properties>'
)


def build(md_path, out_path, title=None, footer_text=None):
    with open(md_path, "r", encoding="utf-8-sig") as f:
        md = f.read()
    if title is None:
        m = re.search(r"^#\s+(.+)$", md, re.M)
        title = m.group(1).strip() if m else os.path.splitext(os.path.basename(md_path))[0]
    if footer_text is None:
        footer_text = title
        with_footer = True
    else:
        with_footer = True

    document = convert(md, footer_text)
    parts = {
        "[Content_Types].xml": CONTENT_TYPES,
        "_rels/.rels": ROOT_RELS,
        "word/document.xml": document,
        "word/styles.xml": styles_xml(),
        "word/_rels/document.xml.rels": doc_rels(with_footer),
        "word/footer1.xml": footer_xml(footer_text),
        "docProps/core.xml": core_xml(title),
        "docProps/app.xml": APP_XML,
    }

    # 写盘前先自检：每份 XML 必须能被解析
    for name, xml in parts.items():
        try:
            minidom.parseString(xml.encode("utf-8"))
        except Exception as e:
            raise SystemExit("XML 自检失败：%s → %s" % (name, e))

    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, xml in parts.items():
            z.writestr(name, xml.encode("utf-8"))
    return parts


def verify(out_path):
    """回读校验：必需部件齐全、XML 可解析、正文非空。"""
    need = ["[Content_Types].xml", "_rels/.rels", "word/document.xml",
            "word/styles.xml", "word/_rels/document.xml.rels"]
    problems = []
    with zipfile.ZipFile(out_path) as z:
        names = set(z.namelist())
        for p in need:
            if p not in names:
                problems.append("缺少部件 %s" % p)
        for p in names:
            if p.endswith(".xml") or p.endswith(".rels"):
                try:
                    minidom.parseString(z.read(p))
                except Exception as e:
                    problems.append("%s 无法解析：%s" % (p, e))
        doc = z.read("word/document.xml").decode("utf-8") if "word/document.xml" in names else ""
        if "<w:p>" not in doc and "<w:p " not in doc:
            problems.append("正文为空（没有段落）")
    return problems


def main():
    ap = argparse.ArgumentParser(description="Markdown → Word(.docx)，零依赖")
    ap.add_argument("md", help="输入 Markdown 文件")
    ap.add_argument("-o", "--out", help="输出 .docx 路径")
    ap.add_argument("--title", default=None, help="文档标题（写入属性）")
    ap.add_argument("--footer", default=None, help="页脚文字，默认用标题")
    args = ap.parse_args()

    if not os.path.isfile(args.md):
        raise SystemExit("错误：找不到文件 %s" % args.md)
    out = args.out or (os.path.splitext(args.md)[0] + ".docx")

    build(args.md, out, args.title, args.footer)
    problems = verify(out)
    size = os.path.getsize(out)
    if problems:
        print("❌ 生成后自检不通过：")
        for p in problems:
            print("   • %s" % p)
        sys.exit(1)
    print("✅ 已生成：%s（%.1f KB，自检通过）" % (out, size / 1024))


if __name__ == "__main__":
    main()
