#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按 GB/T 9704-2012 常用版式把稿面格式的纯文本排成 .docx。

只用标准库（zipfile + 手写 OOXML），不依赖 python-docx，装到哪台机器都能跑。

用法：
    build_docx.py 定稿.txt --out 01_正文.docx --genre 请示
    build_docx.py 阅读资料.md --out 02_阅读资料.docx --kind brief
    build_docx.py 定稿.txt --out 正文.docx --title-font 宋体 --line 578

版式要点（详见 references/版式参数.md）：
    A4；页边距 上37 下35 左28 右26 毫米；正文三号仿宋_GB2312；固定行距 28.9 磅；
    标题二号小标宋居中；一级标题三号黑体；二级三号楷体；三级三号仿宋。
"""

import argparse
import datetime
import re
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

# ---------- 单位换算 ----------
def mm2tw(mm: float) -> int:
    return int(round(mm * 56.6929))


PG_W, PG_H = mm2tw(210), mm2tw(297)
MAR = {"top": mm2tw(37), "bottom": mm2tw(35), "left": mm2tw(28), "right": mm2tw(26)}
TEXT_W = PG_W - MAR["left"] - MAR["right"]

# ---------- 字体与字号 ----------
SZ_TITLE = 44   # 二号 22pt
SZ_BODY = 32    # 三号 16pt
SZ_4 = 28       # 四号 14pt
SZ_5 = 21       # 五号 10.5pt
LATIN_FONT = "Times New Roman"

MARKERS = ("文号", "标题", "主送", "正文", "附件", "署名", "日期", "抄送", "印发机关", "印发日期")
MARKER_RE = re.compile(r"^\[(" + "|".join(MARKERS) + r")\]\s*(.*)$")


def run_xml(text: str, font: str, size_hp: int, bold: bool = False) -> str:
    b = "<w:b/><w:bCs/>" if bold else ""
    return (
        "<w:r><w:rPr>"
        f'<w:rFonts w:ascii="{LATIN_FONT}" w:hAnsi="{LATIN_FONT}" w:eastAsia="{font}" w:cs="{LATIN_FONT}"/>'
        f"{b}"
        f'<w:sz w:val="{size_hp}"/><w:szCs w:val="{size_hp}"/>'
        "</w:rPr>"
        f'<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'
    )


def para_xml(runs, jc="left", first_chars=0, left_chars=0, right_chars=0,
             line=578, before=0, after=0, bottom_border=False, keep_next=False) -> str:
    ppr = ["<w:pPr>"]
    if keep_next:
        ppr.append("<w:keepNext/>")
    if bottom_border:
        ppr.append('<w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="000000"/></w:pBdr>')
    ppr.append(f'<w:spacing w:before="{before}" w:after="{after}" w:line="{line}" w:lineRule="exact"/>')
    ind = []
    if first_chars:
        ind.append(f'w:firstLineChars="{int(first_chars * 100)}" w:firstLine="{int(first_chars * 320)}"')
    if left_chars:
        ind.append(f'w:leftChars="{int(left_chars * 100)}" w:left="{int(left_chars * 320)}"')
    if right_chars:
        ind.append(f'w:rightChars="{int(right_chars * 100)}" w:right="{int(right_chars * 320)}"')
    if ind:
        ppr.append("<w:ind " + " ".join(ind) + "/>")
    ppr.append(f'<w:jc w:val="{jc}"/>')
    ppr.append("</w:pPr>")
    return "<w:p>" + "".join(ppr) + "".join(runs) + "</w:p>"


def empty_para(line=578) -> str:
    return para_xml([], line=line)


def table_xml(rows, font="仿宋_GB2312", size_hp=SZ_5) -> str:
    cols = max(len(r) for r in rows)
    col_w = TEXT_W // cols
    grid = "".join(f'<w:gridCol w:w="{col_w}"/>' for _ in range(cols))
    borders = (
        "<w:tblBorders>"
        + "".join(
            f'<w:{s} w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
            for s in ("top", "left", "bottom", "right", "insideH", "insideV")
        )
        + "</w:tblBorders>"
    )
    out = [
        "<w:tbl><w:tblPr>"
        '<w:tblW w:w="5000" w:type="pct"/>'
        + borders
        + '<w:tblLayout w:type="fixed"/>'
        '<w:tblCellMar><w:left w:w="85" w:type="dxa"/><w:right w:w="85" w:type="dxa"/></w:tblCellMar>'
        "</w:tblPr>",
        f"<w:tblGrid>{grid}</w:tblGrid>",
    ]
    for ri, row in enumerate(rows):
        out.append("<w:tr>")
        for ci in range(cols):
            cell = row[ci] if ci < len(row) else ""
            out.append(
                "<w:tc><w:tcPr>"
                f'<w:tcW w:w="{col_w}" w:type="dxa"/>'
                '<w:vAlign w:val="center"/>'
                "</w:tcPr>"
            )
            out.append(para_xml([run_xml(cell, font, size_hp, bold=(ri == 0))], line=340))
            out.append("</w:tc>")
        out.append("</w:tr>")
    out.append("</w:tbl>")
    return "".join(out)


SECT_PR = (
    "<w:sectPr>"
    '<w:footerReference w:type="default" r:id="rId2"/>'
    f'<w:pgSz w:w="{PG_W}" w:h="{PG_H}"/>'
    f'<w:pgMar w:top="{MAR["top"]}" w:right="{MAR["right"]}" w:bottom="{MAR["bottom"]}" '
    f'w:left="{MAR["left"]}" w:header="851" w:footer="992" w:gutter="0"/>'
    '<w:cols w:space="425"/>'
    '<w:docGrid w:type="lines" w:linePitch="578"/>'
    "</w:sectPr>"
)


def footer_xml(size_hp=SZ_4, font="宋体") -> str:
    """页码：— 1 — 居中，四号宋体（GB/T 9704-2012 用一字线夹页码）。"""
    r = lambda t: run_xml(t, font, size_hp)
    p = (
        '<w:p><w:pPr><w:spacing w:line="400" w:lineRule="exact"/><w:jc w:val="center"/></w:pPr>'
        + r("— ")
        + '<w:fldSimple w:instr=" PAGE ">' + r("1") + "</w:fldSimple>"
        + r(" —")
        + "</w:p>"
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        + p + "</w:ftr>"
    )


def styles_xml(font="仿宋_GB2312", size_hp=SZ_BODY) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:docDefaults><w:rPrDefault><w:rPr>"
        f'<w:rFonts w:ascii="{LATIN_FONT}" w:hAnsi="{LATIN_FONT}" w:eastAsia="{font}" w:cs="{LATIN_FONT}"/>'
        f'<w:sz w:val="{size_hp}"/><w:szCs w:val="{size_hp}"/>'
        "</w:rPr></w:rPrDefault>"
        "<w:pPrDefault><w:pPr>"
        '<w:spacing w:line="578" w:lineRule="exact"/>'
        "</w:pPr></w:pPrDefault></w:docDefaults>"
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
        '<w:name w:val="Normal"/><w:qFormat/></w:style>'
        "</w:styles>"
    )


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
    "</Types>"
)

ROOT_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
    '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
    '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
    "</Relationships>"
)

DOC_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>'
    "</Relationships>"
)


def core_xml(title: str, author: str) -> str:
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f"<dc:title>{escape(title)}</dc:title>"
        f"<dc:creator>{escape(author)}</dc:creator>"
        f"<cp:lastModifiedBy>{escape(author)}</cp:lastModifiedBy>"
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>'
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>'
        "</cp:coreProperties>"
    )


APP_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
    'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
    "<Application>Antou docx-delivery</Application></Properties>"
)


# ---------- 解析稿面 ----------
def parse(text: str):
    """稿面格式：一行一段。空行只作分隔，不并入段落。"""
    fields, paras = {}, []
    in_body = False
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.startswith("#") or s.startswith("<!--"):
            continue
        m = MARKER_RE.match(s)
        if m:
            name, val = m.group(1), m.group(2).strip()
            if name == "正文":
                in_body = True
            else:
                in_body = False
                if name in fields:  # 重复标记：后者并入（如多个[附件]）
                    fields[name] = fields[name] + " " + val
                else:
                    fields[name] = val
            continue
        if not in_body and s.startswith("> "):
            continue
        if in_body:
            paras.append(s)

    if not paras:
        paras = [s.strip() for s in text.splitlines()
                 if s.strip() and not MARKER_RE.match(s.strip()) and not s.strip().startswith("#")]
    return fields, paras


def is_h1(p: str) -> bool:
    return bool(re.match(r"^[一二三四五六七八九十]+、", p))


def is_h2(p: str) -> bool:
    return bool(re.match(r"^（[一二三四五六七八九十]+）", p))


def is_h3(p: str) -> bool:
    return bool(re.match(r"^\d+[.．](?!\d)", p))


def is_h4(p: str) -> bool:
    return bool(re.match(r"^（\d+）", p))


# ---------- 主文档 ----------
def build_main(fields, paras, opt) -> str:
    body = []
    title_font = opt.title_font
    line = opt.line

    if fields.get("文号"):
        body.append(para_xml([run_xml(fields["文号"], "仿宋_GB2312", SZ_BODY)], jc="center", line=line))
        body.append(empty_para(line))

    title = fields.get("标题", "")
    if title:
        body.append(para_xml([run_xml(title, title_font, SZ_TITLE)], jc="center", line=700))
        body.append(empty_para(line))

    if fields.get("主送"):
        body.append(para_xml([run_xml(fields["主送"], "仿宋_GB2312", SZ_BODY)], jc="left", line=line))

    for p in paras:
        if is_h1(p):
            body.append(para_xml([run_xml(p, "黑体", SZ_BODY)], first_chars=2, line=line))
        elif is_h2(p):
            body.append(para_xml([run_xml(p, "楷体_GB2312", SZ_BODY)], first_chars=2, line=line))
        elif is_h3(p) or is_h4(p):
            body.append(para_xml([run_xml(p, "仿宋_GB2312", SZ_BODY)], first_chars=2, line=line))
        else:
            body.append(para_xml([run_xml(p, "仿宋_GB2312", SZ_BODY)], first_chars=2, line=line))

    attach = fields.get("附件", "")
    if attach:
        items = re.findall(r"\d+[.．][^0-9]+?(?=(?:\s+\d+[.．])|$)", attach)
        if items:
            for i, it in enumerate(items):
                txt = ("附件： " if i == 0 else "") + it.strip()
                body.append(para_xml([run_xml(txt, "仿宋_GB2312", SZ_BODY)],
                                     left_chars=2 if i == 0 else 5, line=line))
        else:
            body.append(para_xml([run_xml("附件：" + attach, "仿宋_GB2312", SZ_BODY)],
                                 left_chars=2, line=line))

    signer, date = fields.get("署名", ""), fields.get("日期", "")
    if signer or date:
        body.append(empty_para(line))
        if signer:
            right = 2 + max(0, len(date) - len(signer))
            body.append(para_xml([run_xml(signer, "仿宋_GB2312", SZ_BODY)],
                                 jc="right", right_chars=right, line=line))
        if date:
            body.append(para_xml([run_xml(date, "仿宋_GB2312", SZ_BODY)],
                                 jc="right", right_chars=2, line=line))

    if fields.get("抄送") or fields.get("印发机关") or fields.get("印发日期"):
        body.append(empty_para(line))
        if fields.get("抄送"):
            body.append(para_xml([run_xml("抄送：" + fields["抄送"], "仿宋_GB2312", SZ_4)],
                                 left_chars=1, right_chars=1, line=400, bottom_border=True))
        else:
            body.append(para_xml([], line=400, bottom_border=True))
        if fields.get("印发机关") or fields.get("印发日期"):
            left = "印发机关：" + fields.get("印发机关", "")
            right = "印发日期：" + fields.get("印发日期", "")
            body.append(table_like_row(left, right, line=400))

    body.append(empty_para(line))
    return "".join(body) + SECT_PR


def table_like_row(left: str, right: str, line=400) -> str:
    """版记里的印发机关/印发日期：一行两端对齐。"""
    return (
        "<w:p><w:pPr>"
        f'<w:tabs><w:tab w:val="right" w:pos="{TEXT_W}"/></w:tabs>'
        f'<w:spacing w:line="{line}" w:lineRule="exact"/>'
        '<w:jc w:val="both"/>'
        "</w:pPr>"
        + run_xml(left, "仿宋_GB2312", SZ_4)
        + '<w:r><w:tab/></w:r>'
        + run_xml(right, "仿宋_GB2312", SZ_4)
        + "</w:p>"
    )


# ---------- 阅读资料 ----------
def strip_md(s: str) -> str:
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"`(.+?)`", r"\1", s)
    s = re.sub(r"^[-*]\s+", "· ", s)
    return s.strip()


def build_brief(text: str, opt) -> str:
    lines = text.splitlines()
    body = []
    first_heading = True
    i = 0
    while i < len(lines):
        raw = lines[i]
        s = raw.strip()
        i += 1
        if not s:
            continue
        if s.startswith("```"):
            continue
        # 表格
        if s.startswith("|") and i < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i].strip()):
            rows = []
            head = [c.strip() for c in s.strip("|").split("|")]
            rows.append(head)
            i += 1
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            body.append(table_xml(rows))
            body.append(empty_para(400))
            continue
        if s.startswith("# "):
            txt = strip_md(s[2:])
            body.append(para_xml([run_xml(txt, opt.title_font, SZ_TITLE)], jc="center", line=700))
            body.append(empty_para(400))
            first_heading = False
            continue
        if s.startswith("## ") or s.startswith("### ") or s.startswith("#### "):
            txt = strip_md(re.sub(r"^#+\s*", "", s))
            font = "黑体" if s.startswith("## ") else "楷体_GB2312"
            body.append(para_xml([run_xml(txt, font, SZ_4)],
                                 first_chars=2, line=360, before=120, after=60, keep_next=True))
            continue
        if is_h1(strip_md(s)):
            body.append(para_xml([run_xml(strip_md(s), "黑体", SZ_4)],
                                 first_chars=2, line=360, before=120, after=60, keep_next=True))
            continue
        if is_h2(strip_md(s)):
            body.append(para_xml([run_xml(strip_md(s), "楷体_GB2312", SZ_4)],
                                 first_chars=2, line=360, before=60, after=40, keep_next=True))
            continue
        txt = strip_md(s)
        body.append(para_xml([run_xml(txt, "仿宋_GB2312", SZ_4)], first_chars=2, line=360))

    body.append(empty_para(360))
    return "".join(body) + SECT_PR


def write_docx(out: Path, document_body: str, title: str, author: str, opt):
    doc = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<w:body>{document_body}</w:body></w:document>"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", ROOT_RELS)
        z.writestr("word/document.xml", doc)
        z.writestr("word/_rels/document.xml.rels", DOC_RELS)
        z.writestr("word/styles.xml", styles_xml())
        z.writestr("word/footer1.xml", footer_xml())
        z.writestr("docProps/core.xml", core_xml(title, author))
        z.writestr("docProps/app.xml", APP_XML)


def self_check(out: Path, expect_paras: int) -> bool:
    """结构自检：包内必需部件齐、XML 可解析、页边距与段落数对得上。"""
    import xml.etree.ElementTree as ET

    ok = True
    need = ["[Content_Types].xml", "_rels/.rels", "word/document.xml",
            "word/styles.xml", "word/footer1.xml", "word/_rels/document.xml.rels"]
    with zipfile.ZipFile(out) as z:
        names = set(z.namelist())
        for n in need:
            if n not in names:
                print(f"  ✗ 缺部件：{n}")
                ok = False
        doc = z.read("word/document.xml").decode("utf-8")
    try:
        root = ET.fromstring(doc)
    except ET.ParseError as e:
        print(f"  ✗ document.xml 解析失败：{e}")
        return False
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    pars = root.findall(".//w:body/w:p", ns)
    sect = root.find(".//w:sectPr", ns)
    if sect is None:
        print("  ✗ 缺 sectPr")
        ok = False
    else:
        mar = sect.find("w:pgMar", ns)
        got = {k: mar.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}" + k)
               for k in ("top", "bottom", "left", "right")}
        want = {"top": str(MAR["top"]), "bottom": str(MAR["bottom"]),
                "left": str(MAR["left"]), "right": str(MAR["right"])}
        if got != want:
            print(f"  ✗ 页边距不符：{got} != {want}")
            ok = False
    if expect_paras and len(pars) < expect_paras:
        print(f"  ✗ 段落数偏少：{len(pars)} < {expect_paras}")
        ok = False
    size = out.stat().st_size
    if size < 1500:
        print(f"  ✗ 文件过小：{size} 字节")
        ok = False
    print(f"  段落 {len(pars)} 个 / {size} 字节 / 页边距 {got if sect is not None else '—'}")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description="稿面文本 → GB/T 9704 版式 docx")
    ap.add_argument("src", help="稿面格式纯文本 (.txt/.md)")
    ap.add_argument("--out", required=True, help="输出 .docx 路径")
    ap.add_argument("--kind", choices=["main", "brief"], default="main",
                    help="main=正式文稿；brief=阅读资料")
    ap.add_argument("--genre", default="", help="文种，仅用于记录")
    ap.add_argument("--title-font", default="方正小标宋简体",
                    help="标题字体，缺字体时可改 宋体")
    ap.add_argument("--line", type=int, default=578, help="正文行距（twips），默认 578 = 28.9 磅")
    ap.add_argument("--author", default="案头", help="文档作者（写入属性）")
    ap.add_argument("--no-check", action="store_true", help="跳过结构自检")
    ap.add_argument("--force", action="store_true", help="缺 [标题] 也强排（默认拒绝）")
    args = ap.parse_args()

    src = Path(args.src).expanduser()
    if not src.exists():
        print(f"文件不存在：{src}", file=sys.stderr)
        return 2
    text = src.read_text(encoding="utf-8", errors="replace")

    if args.kind == "brief":
        body = build_brief(text, args)
        title = next((re.sub(r"^#+\s*", "", l).strip() for l in text.splitlines()
                      if l.strip().startswith("# ")), src.stem)
        expect = 5
    else:
        fields, paras = parse(text)
        if not paras:
            print("正文为空：检查是否为稿面格式（见 references/稿面格式.md）", file=sys.stderr)
            return 2
        if not fields.get("标题") and not args.force:
            print("缺 [标题] 标记：这份文件不是稿面格式，直接排会排成没有标题的稿子。", file=sys.stderr)
            print("先按 references/稿面格式.md 加标记（[标题] [主送] [正文] [署名] [日期]）；确要强排加 --force。",
                  file=sys.stderr)
            return 2
        body = build_main(fields, paras, args)
        title = fields.get("标题", src.stem)
        expect = len(paras)

    out = Path(args.out).expanduser()
    write_docx(out, body, title, args.author, args)

    print(f"已生成：{out}")
    print(f"  类型：{'阅读资料' if args.kind == 'brief' else '正式文稿'}"
          + (f"（{args.genre}）" if args.genre else ""))
    print(f"  标题：{title}")
    if not args.no_check:
        print("结构自检：")
        if not self_check(out, expect):
            print("自检未通过：文件结构有问题，不要直接交付。")
            return 1
        print("自检通过（结构级；字体渲染与分页请在 Word/WPS 里再看一眼）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
