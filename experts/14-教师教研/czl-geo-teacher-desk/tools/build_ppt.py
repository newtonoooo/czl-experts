#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按 JSON 大纲生成 16:9 授课课件（.pptx）。

用法:
    python build_ppt.py 大纲.json [输出.pptx]

JSON 格式:
{
  "title": "大气受热过程和大气运动",
  "subtitle": "人教版 必修一 · 高一 · 1 课时",
  "slides": [
    {"title": "学习目标", "bullets": ["能说出……", "能标注……"], "note": "口头强调"}
  ]
}

依赖 python-pptx；缺失时导出同名 .md 大纲并以退出码 2 结束。
"""

import json
import sys
from pathlib import Path


def _require_pptx():
    try:
        from pptx import Presentation
        return Presentation
    except Exception:
        print("[错误] 未安装 python-pptx，已改为导出 Markdown 大纲。", file=sys.stderr)
        print("      安装：pip install python-pptx", file=sys.stderr)
        return None


def fallback_markdown(data, src_path):
    lines = [f"# {data.get('title', '未命名课件')}", "", data.get("subtitle", ""), ""]
    for idx, slide in enumerate(data.get("slides", []), start=1):
        lines.append(f"## P{idx} {slide.get('title', '')}")
        for b in slide.get("bullets", []):
            lines.append(f"- {b}")
        if slide.get("note"):
            lines.append(f"\n> 备注：{slide['note']}")
        lines.append("")
    out = src_path.with_suffix(".md")
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"[降级] 已导出大纲：{out}")
    return out


def build(data, out_path):
    Presentation = _require_pptx()
    if Presentation is None:
        return None

    from pptx.util import Emu, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN

    prs = Presentation()
    prs.slide_width = Emu(12192000)   # 16:9
    prs.slide_height = Emu(6858000)

    blank = prs.slide_layouts[6]
    W, H = prs.slide_width, prs.slide_height
    margin = Emu(640080)  # 约 1.7cm

    def add_textbox(slide, left, top, width, height):
        return slide.shapes.add_textbox(left, top, width, height)

    # 封面
    s = prs.slides.add_slide(blank)
    tb = add_textbox(s, margin, Emu(2100000), W - 2 * margin, Emu(1400000))
    p = tb.text_frame.paragraphs[0]
    p.text = data.get("title", "未命名课件")
    p.font.size = Pt(40)
    p.font.bold = True
    p.font.color.rgb = RGBColor(0x1F, 0x36, 0x4D)
    sub = add_textbox(s, margin, Emu(3450000), W - 2 * margin, Emu(700000))
    sp = sub.text_frame.paragraphs[0]
    sp.text = data.get("subtitle", "")
    sp.font.size = Pt(20)
    sp.font.color.rgb = RGBColor(0x4A, 0x5A, 0x6A)
    line = s.shapes.add_shape(1, margin, Emu(3300000), Emu(1200000), Emu(42000))
    line.fill.solid()
    line.fill.fore_color.rgb = RGBColor(0x0E, 0x7C, 0x86)
    line.line.fill.background()

    # 内容页
    for slide in data.get("slides", []):
        s = prs.slides.add_slide(blank)
        head = add_textbox(s, margin, Emu(520000), W - 2 * margin, Emu(800000))
        hp = head.text_frame.paragraphs[0]
        hp.text = slide.get("title", "")
        hp.font.size = Pt(30)
        hp.font.bold = True
        hp.font.color.rgb = RGBColor(0x1F, 0x36, 0x4D)

        bar = s.shapes.add_shape(1, margin, Emu(1300000), Emu(1000000), Emu(36000))
        bar.fill.solid()
        bar.fill.fore_color.rgb = RGBColor(0x0E, 0x7C, 0x86)
        bar.line.fill.background()

        body = add_textbox(s, margin, Emu(1550000), W - 2 * margin, Emu(4400000))
        tf = body.text_frame
        tf.word_wrap = True
        bullets = slide.get("bullets", []) or [""]
        for i, b in enumerate(bullets):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.text = f"· {b}"
            p.font.size = Pt(22)
            p.alignment = PP_ALIGN.LEFT
            p.space_after = Pt(14)

        note = slide.get("note")
        if note:
            s.notes_slide.notes_text_frame.text = note

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out_path))
    return out_path


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    src = Path(sys.argv[1])
    if not src.exists():
        print(f"[错误] 找不到大纲文件：{src}", file=sys.stderr)
        sys.exit(1)
    data = json.loads(src.read_text(encoding="utf-8"))
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".pptx")
    out = build(data, dst)
    if out is None:
        fallback_markdown(data, src)
        sys.exit(2)
    print(f"[完成] {out}  ({out.stat().st_size / 1024:.1f} KB, {len(data.get('slides', [])) + 1} 页)")


if __name__ == "__main__":
    main()
