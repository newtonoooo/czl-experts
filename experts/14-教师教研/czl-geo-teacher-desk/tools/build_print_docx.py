#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 Markdown 打印稿转成 A4 排版的 .docx。

用法:
    python build_print_docx.py 输入.md [输出.docx]

依赖 python-docx（缺失时给出明确提示并以退出码 2 结束，不伪造成功）。
支持的 Markdown 子集：# ~ #### 标题、段落、- 列表、1. 编号、| 表格 |、
> 引用、``` 代码块、--- 分隔线、**加粗**（行内）。
"""

import re
import sys
from pathlib import Path

FONT_CN = "宋体"
FONT_HEAD = "黑体"
FONT_EN = "Times New Roman"


def _require_docx():
    try:
        import docx  # noqa: F401
        from docx import Document
        return Document
    except Exception:
        print("[错误] 未安装 python-docx，无法生成 docx。", file=sys.stderr)
        print("      安装：pip install python-docx", file=sys.stderr)
        print("      或改用 Markdown 版本打印。", file=sys.stderr)
        sys.exit(2)


def set_run_font(run, cn=FONT_CN, en=FONT_EN, size=None, bold=None):
    from docx.shared import Pt
    from docx.oxml.ns import qn

    run.font.name = en
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = rpr.makeelement(qn("w:rFonts"), {})
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), cn)
    rfonts.set(qn("w:ascii"), en)
    rfonts.set(qn("w:hAnsi"), en)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold


def add_rich_text(par, text, cn=FONT_CN, size=12, bold=False):
    """处理 **加粗** 与 `代码` 两种行内标记。"""
    tokens = re.split(r"(\*\*.+?\*\*|`.+?`)", text)
    for tok in tokens:
        if not tok:
            continue
        if tok.startswith("**") and tok.endswith("**") and len(tok) > 4:
            r = par.add_run(tok[2:-2])
            set_run_font(r, cn=cn, size=size, bold=True)
        elif tok.startswith("`") and tok.endswith("`") and len(tok) > 2:
            r = par.add_run(tok[1:-1])
            set_run_font(r, cn="Consolas", en="Consolas", size=size - 1, bold=bold)
        else:
            r = par.add_run(tok)
            set_run_font(r, cn=cn, size=size, bold=bold)


def add_page_number_footer(section):
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    par = section.footer.paragraphs[0]
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = par.add_run()
    set_run_font(run, size=9)
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_end)


def is_table_sep(line):
    s = line.strip()
    if not s.startswith("|"):
        return False
    cells = [c.strip() for c in s.strip("|").split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{2,}:?", c or "") for c in cells)


def split_row(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def convert(md_text, out_path):
    Document = _require_docx()
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
    from docx.shared import Cm, Pt

    doc = Document()

    # 页面与正文样式
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.top_margin = sec.bottom_margin = Cm(2.54)
    sec.left_margin = sec.right_margin = Cm(3.17)
    add_page_number_footer(sec)

    normal = doc.styles["Normal"]
    normal.font.name = FONT_EN
    normal.font.size = Pt(12)
    normal.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    normal.paragraph_format.space_after = Pt(6)

    lines = md_text.splitlines()
    i = 0
    in_code = False
    code_buf = []

    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip()
        stripped = line.strip()

        # 代码块
        if stripped.startswith("```"):
            if in_code:
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Cm(0.6)
                r = p.add_run("\n".join(code_buf))
                set_run_font(r, cn="Consolas", en="Consolas", size=9)
                code_buf, in_code = [], False
            else:
                in_code = True
            i += 1
            continue
        if in_code:
            code_buf.append(raw)
            i += 1
            continue

        if not stripped:
            i += 1
            continue

        # 表格
        if stripped.startswith("|") and i + 1 < len(lines) and is_table_sep(lines[i + 1]):
            header = split_row(stripped)
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            ncol = len(header)
            table = doc.add_table(rows=1, cols=ncol)
            table.style = "Table Grid"
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            for idx, cell_text in enumerate(header):
                cell = table.rows[0].cells[idx]
                cell.text = ""
                par = cell.paragraphs[0]
                par.alignment = WD_ALIGN_PARAGRAPH.CENTER
                add_rich_text(par, cell_text, cn=FONT_HEAD, size=10.5, bold=True)
            for row in rows:
                cells = table.add_row().cells
                for idx in range(ncol):
                    val = row[idx] if idx < len(row) else ""
                    cells[idx].text = ""
                    add_rich_text(cells[idx].paragraphs[0], val, size=10.5)
            doc.add_paragraph()
            continue

        # 分隔线
        if re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", stripped):
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(2)
            pbdr = p._p.get_or_add_pPr()
            from docx.oxml.ns import qn
            from docx.oxml import OxmlElement
            bottom = OxmlElement("w:pBdr")
            bottom_border = OxmlElement("w:bottom")
            bottom_border.set(qn("w:val"), "single")
            bottom_border.set(qn("w:sz"), "6")
            bottom_border.set(qn("w:color"), "999999")
            bottom.append(bottom_border)
            pbdr.append(bottom)
            i += 1
            continue

        # 标题
        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            size = {1: 16, 2: 14, 3: 12, 4: 12}[level]
            par = doc.add_paragraph()
            par.paragraph_format.space_before = Pt(10 if level <= 2 else 6)
            par.paragraph_format.space_after = Pt(6)
            if level == 1:
                par.alignment = WD_ALIGN_PARAGRAPH.CENTER
            add_rich_text(par, text, cn=FONT_HEAD, size=size, bold=True)
            i += 1
            continue

        # 引用
        if stripped.startswith(">"):
            par = doc.add_paragraph()
            par.paragraph_format.left_indent = Cm(0.8)
            add_rich_text(par, stripped.lstrip("> ").strip(), size=10.5)
            for r in par.runs:
                r.font.italic = True
            i += 1
            continue

        # 列表
        m = re.match(r"^([-*+])\s+(.*)$", stripped)
        if m:
            par = doc.add_paragraph(style="List Bullet")
            add_rich_text(par, m.group(2))
            i += 1
            continue
        m = re.match(r"^(\d+[.)])\s+(.*)$", stripped)
        if m:
            par = doc.add_paragraph()
            par.paragraph_format.left_indent = Cm(0.8)
            add_rich_text(par, f"{m.group(1)} {m.group(2)}")
            i += 1
            continue

        # 普通段落
        par = doc.add_paragraph()
        par.paragraph_format.first_line_indent = Cm(0.74)
        add_rich_text(par, stripped)
        i += 1

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    return out_path


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    src = Path(sys.argv[1])
    if not src.exists():
        print(f"[错误] 找不到输入文件：{src}", file=sys.stderr)
        sys.exit(1)
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".docx")
    text = src.read_text(encoding="utf-8")
    out = convert(text, dst)
    size_kb = out.stat().st_size / 1024
    print(f"[完成] {out}  ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
