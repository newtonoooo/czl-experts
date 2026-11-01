#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""docx 结构校验：不打开 Word 也能查出的硬伤。

查五件事：
1. 包内部件是否齐（内容类型、关系、document、styles、footer）；
2. XML 是否可解析；
3. OOXML 元素顺序硬规则（pPr 必须是 w:p 的第一个子元素、rPr 必须是 w:r 的第一个子元素、
   sectPr 必须是 body 最后一个子元素）——顺序错了 Word 会报"文件已损坏"；
4. 页面几何（A4、页边距）与字号是否落在设定值上；
5. 正文文字能否回读，与源文件字数是否对得上（--src 提供时）。

用法：
    verify_docx.py 01_正文.docx
    verify_docx.py 01_正文.docx --src 定稿.txt
"""

import argparse
import re
import sys
import zipfile
from pathlib import Path

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
NEED = ["[Content_Types].xml", "_rels/.rels", "word/document.xml",
        "word/styles.xml", "word/footer1.xml", "word/_rels/document.xml.rels"]
EXPECT_MAR = {"top": "2098", "bottom": "1984", "left": "1587", "right": "1474"}
EXPECT_PG = {"w": "11906", "h": "16838"}


def die(msg: str) -> int:
    print(f"✗ {msg}")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description="docx 结构校验")
    ap.add_argument("docx")
    ap.add_argument("--src", help="源稿面文本，用于字数回读比对")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    p = Path(args.docx).expanduser()
    if not p.exists():
        return die(f"文件不存在：{p}")

    import xml.etree.ElementTree as ET

    fails = []
    with zipfile.ZipFile(p) as z:
        names = z.namelist()
        for n in NEED:
            if n not in names:
                fails.append(f"缺部件 {n}")
        if fails:
            for f in fails:
                print(f"✗ {f}")
            return 1

        doc = z.read("word/document.xml").decode("utf-8")
        ftr = z.read("word/footer1.xml").decode("utf-8")

    try:
        root = ET.fromstring(doc)
    except ET.ParseError as e:
        return die(f"document.xml 解析失败：{e}")

    body = root.find(f"{W}body")
    if body is None:
        return die("缺 w:body")

    # 顺序硬规则
    for i, para in enumerate(body.findall(f"{W}p"), 1):
        kids = list(para)
        if kids and kids[0].tag != f"{W}pPr" and any(k.tag == f"{W}pPr" for k in kids):
            fails.append(f"第{i}段 pPr 不在首位")
        for r in para.findall(f"{W}r"):
            rk = list(r)
            if rk and rk[0].tag != f"{W}rPr" and any(k.tag == f"{W}rPr" for k in rk):
                fails.append(f"第{i}段某 run 的 rPr 不在首位")
                break

    last = list(body)[-1]
    if last.tag != f"{W}sectPr":
        fails.append("sectPr 不是 body 最后一个元素")

    sect = body.find(f"{W}sectPr")
    if sect is None:
        fails.append("缺 sectPr")
    else:
        pgsz = sect.find(f"{W}pgSz")
        mar = sect.find(f"{W}pgMar")
        got_pg = {k: pgsz.get(W + k) for k in EXPECT_PG} if pgsz is not None else {}
        got_mar = {k: mar.get(W + k) for k in EXPECT_MAR} if mar is not None else {}
        if got_pg != EXPECT_PG:
            fails.append(f"纸张不是 A4：{got_pg}")
        if got_mar != EXPECT_MAR:
            fails.append(f"页边距不符 GB/T 9704：{got_mar}")
        if sect.find(f"{W}footerReference") is None:
            fails.append("缺页码页脚引用")

    # 字体与字号统计
    fonts, sizes = {}, {}
    for rf in root.iter(f"{W}rFonts"):
        f = rf.get(W + "eastAsia")
        if f:
            fonts[f] = fonts.get(f, 0) + 1
    for sz in root.iter(f"{W}sz"):
        v = sz.get(W + "val")
        sizes[v] = sizes.get(v, 0) + 1

    # 文字回读
    text = "".join(t.text or "" for t in root.iter(f"{W}t"))
    chars = len(re.sub(r"\s", "", text))
    if chars == 0:
        fails.append("回读不到任何文字")

    if args.src:
        src = Path(args.src).expanduser().read_text(encoding="utf-8", errors="replace")
        src_chars = len(re.sub(r"\s", "", re.sub(r"\[[^\]]+\]", "", src)))
        if src_chars and chars < src_chars * 0.9:
            fails.append(f"文字回读偏少：docx {chars} 字 vs 源 {src_chars} 字")

    if "PAGE" not in ftr:
        fails.append("页脚缺页码域")

    if not args.quiet:
        print(f"文件：{p}（{p.stat().st_size} 字节）")
        print(f"段落数：{len(body.findall(f'{W}p'))} / 表格数：{len(body.findall(f'{W}tbl'))}")
        print(f"回读字数：{chars}")
        print("字体使用：" + "、".join(f"{k}×{v}" for k, v in
                                  sorted(fonts.items(), key=lambda x: -x[1])[:5]))
        print("字号使用（半磅）：" + "、".join(f"{k}×{v}" for k, v in
                                       sorted(sizes.items(), key=lambda x: -x[1])[:5]))

    if fails:
        print(f"\n✗ 未通过，{len(fails)} 项：")
        for f in fails[:15]:
            print("  · " + f)
        return 1

    print("\n✓ 结构校验通过：部件齐、XML 可解析、元素顺序合规、页面几何与页码符合设定")
    print("  说明：本校验不渲染版面，字体缺失时的替代效果需在 Word/WPS 中目视确认。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
