#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_wechat.py — 公众号图文 HTML 渲染器（朱笔 / publish-kit 技能）

按《微信公众号图文 HTML 排版规范》生成可直接粘贴到公众号后台的单文件 HTML：
全内联样式、无 JS、无外链；布局只用 table + 块级 + inline-block；容器 680px。

用法:
    python render_wechat.py draft.md                      # 配色随机抽一套
    python render_wechat.py draft.md --theme b-navy        # 指定配色
    python render_wechat.py draft.md --seed 7              # 随机但可复现
    python render_wechat.py draft.md --list-themes         # 看五套配色
    python render_wechat.py draft.md --no-footer           # 不输出落款
    python render_wechat.py draft.md --embed               # 图片转 base64 内嵌

配色优先级：--theme 指定 > frontmatter 的 theme: > 随机。

输入格式（Markdown + frontmatter），详见 references/markdown-dialect.md：

    ---
    tag: 小店观察
    tag2: 城市样本
    title: 开了九年的文具店，最赚钱的不是文具
    subtitle: 一本账翻出来的三件事
    footer_name: 你的公众号名          # 必须是用户自己的账号名，不许编
    footer_slogan: 一句话说清你写什么
    theme: c-dai                        # 可选，锁定配色
    ---

    ## 一年里的两个高峰
    正文段落，==这里是重点==，其余照常。

    ::: stats
    7 条|今年新增
    3 个|需要提前准备
    :::

    ::: quote
    一句必须被看见的话，==最关键的半句用点缀色==。
    :::
"""

import argparse
import html
import os
import random
import re
import sys

# ---------------------------------------------------------------- 视觉 Token
# 与 references/typography-spec.md 的 §4「配色方案库（5 套）」严格对应。
# 改配色必须同步改文档，反之亦然。
EMBED_IMAGES = [False]   # --embed 时置 True
IMAGE_BASE = [""]        # 图片相对路径的基准目录

SERIF = "'Noto Serif SC','Songti SC','SimSun',serif"
SANS = "'Noto Sans SC','PingFang SC','Microsoft YaHei',sans-serif"

# 五套配色。每套只用 1 主色 + 1 强调色 + 1 点缀色，不再加别的彩色。
SCHEMES = {
    "a-ink": {
        "name": "墨绿书卷",
        "mood": "中式、书卷、沉稳；适合硬新闻、盘点、深度",
        "primary": "#1F5A50", "accent": "#9E3B2E", "spot": "#C29A4B",
        "page_bg": "#EDEAE3", "container_bg": "#FBF9F5",
        "text": "#2b2b26", "muted": "#6a6a62",
        "line": "#E8E2D6", "line_soft": "#EEE9E0",
        "soft_bg": "#F7F0E3", "soft_line": "#E8DEC8",
    },
    "b-navy": {
        "name": "藏青学术",
        "mood": "学术、理性、权威；适合政策、规则、数据图表",
        "primary": "#23395B", "accent": "#C5673F", "spot": "#B8924E",
        "page_bg": "#E9ECEF", "container_bg": "#FAF8F4",
        "text": "#262A30", "muted": "#67707A",
        "line": "#E2E6EA", "line_soft": "#EAEDF0",
        "soft_bg": "#F1EEE7", "soft_line": "#E4DFD4",
    },
    "c-dai": {
        "name": "黛蓝烟雨",
        "mood": "清雅、温柔、留白感；适合随笔、教育理念、慢话题",
        "primary": "#2F5D62", "accent": "#A85A6A", "spot": "#C9A86A",
        "page_bg": "#EAEAE5", "container_bg": "#F8F6F2",
        "text": "#2A2E2E", "muted": "#656E6C",
        "line": "#E3E6E0", "line_soft": "#EBEEE8",
        "soft_bg": "#F0EDE6", "soft_line": "#E3DED2",
    },
    "d-chestnut": {
        "name": "栗棕暖陶",
        "mood": "温暖、接地气、像家里的灯光；适合亲子、情感、成长故事",
        "primary": "#7A5230", "accent": "#B5573D", "spot": "#C9A24B",
        "page_bg": "#ECE6DD", "container_bg": "#FAF6EF",
        "text": "#2E2A25", "muted": "#6E655B",
        "line": "#E7E0D5", "line_soft": "#EFE9DF",
        "soft_bg": "#F4EBDD", "soft_line": "#E7DCC7",
    },
    "e-graphite": {
        "name": "石墨青",
        "mood": "现代、干净、有力量；适合观点、评论、年轻化表达",
        "primary": "#264653", "accent": "#E76F51", "spot": "#E9C46A",
        "page_bg": "#EDEFEF", "container_bg": "#FFFFFF",
        "text": "#23282A", "muted": "#5F6A6E",
        "line": "#E4E8E9", "line_soft": "#EDF0F0",
        "soft_bg": "#F2F5F4", "soft_line": "#DFE6E5",
    },
}

# 旧主题名映射，保证老稿件与老命令不报错
THEME_ALIASES = {"ink": "a-ink", "plain": "a-ink", "navy": "b-navy",
                 "dai": "c-dai", "chestnut": "d-chestnut", "graphite": "e-graphite"}

FM_KEYS = ("tag", "tag2", "title", "subtitle",
           "footer_name", "footer_slogan", "theme")
TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$")
# 图片块： ![说明](路径 "图注")  —— 图注可选
IMG_RE = re.compile(r'^!\[([^\]]*)\]\(([^)\s]+)(?:\s+"([^"]*)")?\)$')
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif")
OL_RE = re.compile(r"^\s*\d+[.)]\s+(.*)$")
UL_RE = re.compile(r"^\s*[-*+]\s+(.*)$")


# ---------------------------------------------------------------- 配色选择
def resolve_scheme(key):
    """取一套配色的完整 token。会把语义名同时挂上旧 key，兼容老代码。"""
    k = THEME_ALIASES.get(key, key)
    if k not in SCHEMES:
        raise KeyError(k)
    base = dict(SCHEMES[k])
    base["key"] = k
    base["card_bg"] = "#FFFFFF"
    base["serif"] = SERIF
    base["sans"] = SANS
    # 旧 key 别名（inline / tip / footer 等处仍可能引用）
    base["green"] = base["primary"]
    base["red"] = base["accent"]
    base["gold"] = base["spot"]
    base["mark_bg"] = base["soft_bg"]
    base["tip_bg"] = base["soft_bg"]
    return base


def pick_scheme(requested=None, seed=None):
    """决定用哪套：显式指定优先，否则随机。返回 (key, 来源说明)。"""
    if requested and requested not in ("random", "auto"):
        return THEME_ALIASES.get(requested, requested), "指定"
    rnd = random.Random(seed) if seed is not None else random.SystemRandom()
    return rnd.choice(list(SCHEMES)), ("随机·可复现" if seed is not None else "随机")


# ---------------------------------------------------------------- 解析
def split_frontmatter(text):
    text = text.replace("\r\n", "\n")
    fm = {}
    body = text
    if text.startswith("---"):
        m = re.match(r"^---\n(.*?)\n---\n?", text, re.S)
        if m:
            for line in m.group(1).split("\n"):
                if ":" in line:
                    k, _, v = line.partition(":")
                    k = k.strip()
                    if k in FM_KEYS:
                        fm[k] = v.strip().strip('"').strip("'")
            body = text[m.end():]
    return fm, body


def inline(text, t):
    """行内处理：先转义，再按标记替换。"""
    text = html.escape(text, quote=False)
    text = re.sub(r"==([^=]+)==",
                  lambda m: (f'<span style="background:{t["soft_bg"]};color:{t["accent"]};'
                             f'font-weight:700;padding:1px 4px;border-radius:3px;">'
                             f'{m.group(1)}</span>'), text)
    text = re.sub(r"\*\*([^*]+)\*\*",
                  lambda m: f'<strong style="color:{t["primary"]};font-weight:700;">{m.group(1)}</strong>',
                  text)
    text = re.sub(r"`([^`]+)`",
                  lambda m: (f'<span style="background:{t["soft_bg"]};padding:1px 4px;'
                             f'border-radius:3px;font-size:0.92em;">{m.group(1)}</span>'), text)
    return text


def inline_dark(text, t):
    """深色底（金句卡）里的行内标记：文字用容器底色，重点用点缀色。"""
    text = html.escape(text, quote=False)
    text = re.sub(r"==([^=]+)==",
                  lambda m: f'<span style="font-weight:700;color:{t["spot"]};">{m.group(1)}</span>',
                  text)
    text = re.sub(r"\*\*([^*]+)\*\*",
                  lambda m: f'<strong style="color:{t["spot"]};font-weight:700;">{m.group(1)}</strong>',
                  text)
    return text


def parse_table(rows):
    out = []
    for r in rows:
        r = r.strip()
        if r.startswith("|"):
            r = r[1:]
        if r.endswith("|"):
            r = r[:-1]
        out.append([c.strip() for c in r.split("|")])
    return out


def parse_sections(body):
    """按 ## 切章节；每章内识别段落/列表/表格/提示块/时间轴/金句/数据卡/来源。"""
    lines = body.split("\n")
    sections = [{"title": None, "blocks": []}]
    i, n = 0, len(lines)

    while i < n:
        line = lines[i]
        s = line.strip()

        if not s:
            i += 1
            continue

        if s.startswith("## "):
            sections.append({"title": s[3:].strip(), "blocks": []})
            i += 1
            continue

        if s.startswith("# "):
            # 一级标题在正文中不重复渲染（已由 frontmatter 的 title 承担）
            i += 1
            continue

        if re.match(r"^---+$", s):
            i += 1
            continue

        # 图片独占一行： ![说明](路径 "图注")
        m = IMG_RE.match(s)
        if m:
            sections[-1]["blocks"].append({
                "type": "img", "alt": m.group(1), "src": m.group(2), "caption": m.group(3) or ""
            })
            i += 1
            continue

        if s.startswith("::: timeline"):
            i += 1
            rows = []
            while i < n and lines[i].strip() != ":::":
                r = lines[i].strip()
                if r and not r.startswith("#"):
                    cells = [c.strip() for c in r.split("|")]
                    if len(cells) >= 2:
                        rows.append(cells)
                i += 1
            i += 1
            sections[-1]["blocks"].append({"type": "timeline", "rows": rows})
            continue

        if s.startswith("::: stats"):
            i += 1
            cells = []
            while i < n and lines[i].strip() != ":::":
                r = lines[i].strip()
                if r:
                    parts = [c.strip() for c in r.split("|")]
                    cells.append({"value": parts[0],
                                  "label": parts[1] if len(parts) > 1 else ""})
                i += 1
            i += 1
            sections[-1]["blocks"].append({"type": "stats", "cells": cells})
            continue

        if s.startswith("::: quote"):
            i += 1
            buf = []
            while i < n and lines[i].strip() != ":::":
                if lines[i].strip():
                    buf.append(lines[i].strip())
                i += 1
            i += 1
            sections[-1]["blocks"].append({"type": "quote", "text": " ".join(buf)})
            continue

        if s.startswith("::: source"):
            i += 1
            buf = []
            while i < n and lines[i].strip() != ":::":
                if lines[i].strip():
                    buf.append(lines[i].strip())
                i += 1
            i += 1
            sections[-1]["blocks"].append({
                "type": "source",
                "head": buf[0] if buf else "素材来源",
                "body": buf[1:],
            })
            continue

        if s.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            sections[-1]["blocks"].append({"type": "tip", "text": " ".join(buf)})
            continue

        # 表格：当前行是 |...|，且下一行是分隔行
        if s.startswith("|") and i + 1 < n and TABLE_SEP.match(lines[i + 1]):
            head = lines[i]
            i += 2
            body_rows = []
            while i < n and lines[i].strip().startswith("|"):
                body_rows.append(lines[i])
                i += 1
            grid = parse_table([head] + body_rows)
            sections[-1]["blocks"].append({
                "type": "table", "head": grid[0], "rows": grid[1:]
            })
            continue

        if OL_RE.match(line):
            items = []
            while i < n and OL_RE.match(lines[i]):
                items.append(OL_RE.match(lines[i]).group(1).strip())
                i += 1
            sections[-1]["blocks"].append({"type": "ol", "items": items})
            continue

        if UL_RE.match(line):
            items = []
            while i < n and UL_RE.match(lines[i]):
                items.append(UL_RE.match(lines[i]).group(1).strip())
                i += 1
            sections[-1]["blocks"].append({"type": "ul", "items": items})
            continue

        # 普通段落：连续非空行合并
        buf = [s]
        i += 1
        while i < n:
            nxt = lines[i].strip()
            if (not nxt or nxt.startswith("#") or nxt.startswith(">")
                    or nxt.startswith("|") or nxt.startswith(":::")
                    or nxt.startswith("!") or OL_RE.match(lines[i])
                    or UL_RE.match(lines[i]) or re.match(r"^---+$", nxt)):
                break
            buf.append(nxt)
            i += 1
        sections[-1]["blocks"].append({"type": "p", "text": "".join(buf)})

    return [s for s in sections if s["title"] or s["blocks"]]


# ---------------------------------------------------------------- 渲染：基础件
def row(top, inner, bottom=0, align=""):
    """一个区块 = 一个 tr>td。左右统一 32px 内边距。"""
    a = f' align="{align}"' if align else ""
    return f'<tr><td{a} style="padding:{top}px 32px {bottom}px 32px;">{inner}</td></tr>'


def full_table(rows_html, extra_style=""):
    """完整的 table（含闭合标签），rows_html 只放 tr 串。
    规范要求每个 table 都写全 cellpadding/cellspacing/border —— 少一个，粘贴后列宽就飘。"""
    return (f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'style="border-collapse:collapse;{extra_style}">{rows_html}</table>')


def hr(t):
    return row(24, full_table(
        f'<tr><td style="border-bottom:1px solid {t["line"]};font-size:0;line-height:0;">'
        f'&nbsp;</td></tr>'))


# ---------------------------------------------------------------- 渲染：组件
def render_paragraphs(texts, t):
    out = []
    last = len(texts) - 1
    for idx, txt in enumerate(texts):
        mb = "0" if idx == last else "14px"
        out.append(f'<p style="margin:0 0 {mb} 0;font-size:17px;line-height:1.95;'
                   f'color:{t["text"]};font-family:{t["sans"]};">{inline(txt, t)}</p>')
    return row(20, "".join(out))


def render_ul(block, t):
    lis = "".join(
        f'<li style="margin:0 0 9px 0;font-size:16.5px;line-height:1.9;'
        f'color:{t["text"]};font-family:{t["sans"]};">{inline(x, t)}</li>'
        for x in block["items"])
    return row(16, f'<ul style="margin:0;padding-left:22px;">{lis}</ul>')


def render_ol(block, t):
    rows = []
    for idx, item in enumerate(block["items"], 1):
        rows.append(
            f'<tr><td style="width:34px;vertical-align:top;padding:0 0 12px 0;">'
            f'<span style="display:inline-block;width:24px;height:24px;line-height:24px;'
            f'border-radius:50%;background:{t["primary"]};color:#fff;font-size:13px;'
            f'font-weight:700;text-align:center;font-family:{t["sans"]};">{idx}</span></td>'
            f'<td style="vertical-align:top;padding:0 0 12px 6px;">'
            f'<p style="margin:0;font-size:16.5px;line-height:1.85;color:{t["text"]};'
            f'font-family:{t["sans"]};">{inline(item, t)}</p></td></tr>')
    return row(20, full_table("".join(rows)))


def render_table(block, t):
    head, rows = block["head"], block["rows"]
    ncol = max(len(head), max((len(r) for r in rows), default=0))
    if ncol == 0:
        return ""
    # 列宽：首列略窄，其余按列数均分；总和必须 100%
    if ncol == 1:
        widths = [100]
    elif ncol == 2:
        widths = [32, 68]
    else:
        first = 22
        rest = (100 - first) // (ncol - 1)
        widths = [first] + [rest] * (ncol - 1)
        widths[-1] = 100 - sum(widths[:-1])

    cols = "".join(f'<col style="width:{w}%">' for w in widths)
    inner = [f'<colgroup>{cols}</colgroup>',
             f'<tr style="background:{t["primary"]};">'
             + "".join(f'<td style="padding:10px 9px;font-size:13.5px;text-align:left;'
                       f'font-weight:700;color:#fff;font-family:{t["sans"]};">{inline(c, t)}</td>'
                       for c in (head + [""] * (ncol - len(head))))
             + "</tr>"]

    for r in rows:
        cells = []
        for idx in range(ncol):
            cell = r[idx] if idx < len(r) else ""
            # 从第二列起用次要色，主信息留深色
            color = t["text"] if idx == 0 else t["muted"]
            size = "14px" if idx == 0 else "13.5px"
            bold = "700" if idx == 0 else "400"
            cells.append(f'<td style="padding:10px 9px;font-size:{size};color:{color};'
                         f'font-weight:{bold};border-bottom:1px solid {t["line_soft"]};'
                         f'line-height:1.7;font-family:{t["sans"]};">{inline(cell, t)}</td>')
        inner.append("<tr>" + "".join(cells) + "</tr>")
    return row(20, full_table("".join(inner), "table-layout:fixed;"))


def render_timeline(block, t):
    """三列 table（时间 | 圆点 | 标题+说明），不画贯穿线、不定位。"""
    rows = block["rows"]
    if not rows:
        return ""
    out = []
    last = len(rows) - 1
    for idx, cells in enumerate(rows):
        when = cells[0]
        title = cells[1] if len(cells) > 1 else ""
        desc = cells[2] if len(cells) > 2 else ""
        # 时间字段以 ! 结尾 → 点缀色圆点（关键节点）；!! → 强调色大圆点（大考）
        color, size = t["primary"], 12
        if when.endswith("!!"):
            when = when[:-2].strip()
            color, size = t["accent"], 13
        elif when.endswith("!"):
            when = when[:-1].strip()
            color, size = t["spot"], 12
        pad = "8px" if idx == last else "16px"
        out.append("<tr>")
        out.append(f'<td style="width:54px;vertical-align:top;text-align:right;'
                   f'padding:14px 8px {pad} 0;">'
                   f'<span style="font-size:13px;color:{t["accent"]};font-weight:700;'
                   f'font-family:{t["sans"]};">{inline(when, t)}</span></td>')
        out.append(f'<td style="width:16px;vertical-align:top;text-align:center;'
                   f'padding:15px 0 {pad} 0;">'
                   f'<span style="display:inline-block;width:{size}px;height:{size}px;'
                   f'border-radius:50%;background:{color};"></span></td>')
        out.append(f'<td style="vertical-align:top;padding:14px 0 {pad} 7px;">'
                   f'<p style="margin:0;font-size:15px;font-weight:700;color:{t["text"]};'
                   f'line-height:1.5;font-family:{t["sans"]};">{inline(title, t)}</p>')
        if desc:
            out.append(f'<p style="margin:3px 0 0 0;font-size:13px;color:{t["muted"]};'
                       f'line-height:1.8;font-family:{t["sans"]};">{inline(desc, t)}</p>')
        out.append("</td></tr>")
    return row(20, full_table("".join(out),
                              f'background:{t["card_bg"]};border:1px solid {t["line"]};'
                              f'border-radius:8px;'))


def render_tip(block, t):
    return row(20, f'<div style="background:{t["soft_bg"]};border-left:3px solid {t["spot"]};'
                   f'border-radius:6px;padding:12px 14px;font-size:14.5px;color:{t["text"]};'
                   f'line-height:1.85;font-family:{t["sans"]};">{inline(block["text"], t)}</div>')


def render_quote(block, t):
    """6.7 金句卡片：主色底 + 容器底色文字 + 点缀色标重点。"""
    return row(6, full_table(
        f'<tr><td style="padding:18px 22px;">'
        f'<p style="margin:0;font-size:16.5px;line-height:1.9;color:{t["container_bg"]};'
        f'font-family:{t["sans"]};">{inline_dark(block["text"], t)}</p>'
        f'</td></tr>',
        f'background:{t["primary"]};border-radius:8px;'))


def render_stats(block, t):
    """6.8 数据卡片：2—4 列，浅底 + 细边，大数字用强调色。"""
    cells = block["cells"][:4]
    if not cells:
        return ""
    n = len(cells)
    w = 100 // n
    cols = "".join(f'<col style="width:{w}%">' for _ in cells)
    tds = []
    for idx, c in enumerate(cells):
        right = "" if idx == n - 1 else f'border-right:1px solid {t["soft_line"]};'
        tds.append(
            f'<td style="background:{t["soft_bg"]};border:1px solid {t["soft_line"]};'
            f'{right}padding:14px 8px;text-align:center;">'
            f'<p style="margin:0;font-family:{t["serif"]};font-size:26px;font-weight:900;'
            f'color:{t["accent"]};line-height:1.1;">{html.escape(c["value"])}</p>'
            + (f'<p style="margin:8px 0 0 0;font-size:13px;color:{t["muted"]};line-height:1.5;'
               f'font-family:{t["sans"]};">{html.escape(c["label"])}</p>' if c["label"] else "")
            + "</td>")
    return row(6, full_table(f'<colgroup>{cols}</colgroup><tr>{"".join(tds)}</tr>',
                             "table-layout:fixed;"))


def render_source(block, t):
    """6.10 白底来源框。"""
    body = "".join(
        f'<p style="margin:0 0 4px 0;font-size:12.5px;line-height:1.85;color:{t["muted"]};'
        f'font-family:{t["sans"]};">{inline(x, t)}</p>' for x in block["body"])
    return row(28, full_table(
        f'<tr><td style="padding:14px 18px;">'
        f'<p style="margin:0 0 8px 0;font-size:13px;font-weight:700;color:{t["muted"]};'
        f'font-family:{t["sans"]};">{inline(block["head"], t)}</p>'
        f'{body}</td></tr>',
        f'background:{t["card_bg"]};border:1px solid {t["line"]};border-radius:6px;'))


def load_as_data_uri(path):
    """把本地图片转成 base64 data URI。找不到文件时返回 None。"""
    import base64
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError:
        return None
    ext = os.path.splitext(path)[1].lower()
    mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
            ".webp": "image/webp", ".gif": "image/gif"}.get(ext, "image/jpeg")
    return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")


def render_image(block, t, embed=False, base_dir=None):
    """规范 §7：图片必须下载到本地，用相对路径；这里不接受外链直出。"""
    src = block["src"]
    alt = block["alt"] or ""
    caption = block.get("caption", "")
    note = ""

    if src.startswith(("http://", "https://")):
        note = "外链图片，粘到公众号后台会失效，需先下载到本地"
    elif embed:
        path = src if os.path.isabs(src) else os.path.join(base_dir or "", src)
        uri = load_as_data_uri(path)
        if uri:
            src = uri
        else:
            note = f"图片文件不存在：{src}"

    img = (f'<img src="{html.escape(src, quote=True)}" alt="{html.escape(alt, quote=True)}" '
           f'width="100%" style="display:block;width:100%;height:auto;border-radius:4px;" />')
    cap = ""
    if caption:
        cap = (f'<p style="margin:8px 0 0 0;font-size:13px;color:{t["muted"]};line-height:1.7;'
               f'text-align:center;font-family:{t["sans"]};">{inline(caption, t)}</p>')
    warn = ""
    if note:
        warn = (f'<p style="margin:6px 0 0 0;font-size:12px;color:{t["accent"]};'
                f'line-height:1.6;text-align:center;font-family:{t["sans"]};">'
                f'⚠ {html.escape(note)}</p>')
    return row(20, f'{full_table("<tr><td>" + img + "</td></tr>")}{cap}{warn}')


def render_section(title, idx, t):
    """6.5 章节编号方块 + 标题。标题以 ! 开头 → 强调色方块（重点/警示章节）。"""
    accent = title.startswith("!")
    if accent:
        title = title.lstrip("!").strip()
    bg = t["accent"] if accent else t["primary"]
    num = f"{idx:02d}"
    inner = (f'<tr>'
             f'<td style="background:{bg};color:#fff;font-family:{t["serif"]};font-size:20px;'
             f'font-weight:700;padding:8px 14px;text-align:center;">{num}</td>'
             f'<td style="padding-left:14px;font-family:{t["serif"]};font-size:22px;'
             f'font-weight:700;color:{t["primary"]};line-height:1.4;">'
             f'{html.escape(title)}</td></tr>')
    return row(40, f'<table cellpadding="0" cellspacing="0" border="0" '
                   f'style="border-collapse:collapse;">{inner}</table>')


# ---------------------------------------------------------------- 组装
def render_blocks(blocks, t):
    """返回 rows 列表。连续段落合并进同一个 td，段间用 margin 拉开。"""
    rows = []
    buf = []

    def flush():
        if buf:
            rows.append(render_paragraphs(buf[:], t))
            buf.clear()

    for b in blocks:
        kind = b["type"]
        if kind == "p":
            buf.append(b["text"])
            continue
        flush()
        if kind == "ul":
            rows.append(render_ul(b, t))
        elif kind == "ol":
            rows.append(render_ol(b, t))
        elif kind == "table":
            rows.append(render_table(b, t))
        elif kind == "timeline":
            rows.append(render_timeline(b, t))
        elif kind == "img":
            rows.append(render_image(b, t, embed=EMBED_IMAGES[0], base_dir=IMAGE_BASE[0]))
        elif kind == "tip":
            rows.append(render_tip(b, t))
        elif kind == "quote":
            rows.append(render_quote(b, t))
        elif kind == "stats":
            rows.append(render_stats(b, t))
        elif kind == "source":
            rows.append(render_source(b, t))
    flush()
    return [r for r in rows if r]


def build_html(fm, sections, t, with_footer=True):
    title = fm.get("title", "未命名文章")
    rows = []

    # 6.1 顶部双标签
    if fm.get("tag") or fm.get("tag2"):
        tags = []
        if fm.get("tag"):
            tags.append(f'<td style="background:{t["primary"]};color:#fff;font-size:13px;'
                        f'font-weight:700;padding:5px 12px;letter-spacing:1px;'
                        f'font-family:{t["sans"]};">{html.escape(fm["tag"])}</td>')
        if fm.get("tag2"):
            tags.append(f'<td style="background:{t["card_bg"]};color:{t["primary"]};'
                        f'font-size:13px;font-weight:700;padding:5px 12px;'
                        f'border:1px solid {t["primary"]};letter-spacing:1px;'
                        f'font-family:{t["sans"]};">{html.escape(fm["tag2"])}</td>')
        rows.append(row(30, '<table cellpadding="0" cellspacing="0" border="0" '
                            'style="border-collapse:collapse;"><tr>' + "".join(tags) + "</tr></table>"))

    # 6.2 主标题 + 副标题（左对齐）
    head = [f'<h1 style="margin:0;font-family:{t["serif"]};font-size:28px;font-weight:900;'
            f'line-height:1.42;color:{t["primary"]};">{html.escape(title)}</h1>']
    if fm.get("subtitle"):
        head.append(f'<p style="margin:14px 0 0 0;font-family:{t["serif"]};font-size:18px;'
                    f'font-weight:700;line-height:1.6;color:{t["accent"]};">'
                    f'{html.escape(fm["subtitle"])}</p>')
    rows.append(row(22 if (fm.get("tag") or fm.get("tag2")) else 30, "".join(head)))

    rows.append(hr(t))

    # 章节与正文
    sec_idx = 0
    for sec in sections:
        if sec["title"]:
            sec_idx += 1
            rows.append(render_section(sec["title"], sec_idx, t))
        rows.extend(render_blocks(sec["blocks"], t))

    # 6.9 署名区
    if with_footer and fm.get("footer_name"):
        inner = (f'<tr><td style="border-top:1px solid {t["line"]};padding-top:24px;" align="center">'
                 f'<p style="margin:0 0 6px 0;font-family:{t["serif"]};font-size:20px;'
                 f'font-weight:900;color:{t["primary"]};">{html.escape(fm["footer_name"])}</p>')
        if fm.get("footer_slogan"):
            lines = fm["footer_slogan"].replace("/", "<br>")
            inner += (f'<p style="margin:0;font-size:14px;line-height:1.8;color:{t["muted"]};'
                      f'font-family:{t["sans"]};">{html.escape(lines).replace("&lt;br&gt;", "<br>")}</p>')
        inner += "</td></tr>"
        rows.append(row(36, full_table(inner)))

    # 收尾留白
    rows.append('<tr><td style="padding:0 0 36px 0;font-size:0;line-height:0;">&nbsp;</td></tr>')

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)}</title>
</head>
<!-- theme: {t['key']} {t['name']} · 主色 {t['primary']} / 强调 {t['accent']} / 点缀 {t['spot']} -->
<body style="margin:0;padding:0;background:{t['page_bg']};">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;background:{t['page_bg']};">
<tr><td align="center" style="padding:24px 12px;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;background:{t['container_bg']};max-width:680px;border-radius:6px;">
{chr(10).join(rows)}
</table>
</td></tr>
</table>
</body>
</html>
"""


# ---------------------------------------------------------------- 图片清单
def image_size(path):
    """读 PNG / JPEG 的宽高，读不出返回 (None, None)。纯标准库。"""
    try:
        with open(path, "rb") as f:
            head = f.read(32)
            if head[:8] == b"\x89PNG\r\n\x1a\n":
                import struct
                w, h = struct.unpack(">II", head[16:24])
                return w, h
            if head[:2] == b"\xff\xd8":          # JPEG，扫 SOF 段
                f.seek(2)
                while True:
                    b = f.read(1)
                    if not b:
                        break
                    if b != b"\xff":
                        continue
                    marker = f.read(1)
                    while marker == b"\xff":
                        marker = f.read(1)
                    if marker in (b"\xc0", b"\xc1", b"\xc2", b"\xc3",
                                  b"\xc5", b"\xc6", b"\xc7", b"\xc9",
                                  b"\xca", b"\xcb", b"\xcd", b"\xce", b"\xcf"):
                        f.read(3)
                        import struct
                        h, w = struct.unpack(">HH", f.read(4))
                        return w, h
                    seg = f.read(2)
                    if len(seg) < 2:
                        break
                    import struct
                    (length,) = struct.unpack(">H", seg)
                    f.seek(length - 2, 1)
    except (OSError, Exception):
        pass
    return None, None


def collect_images(sections, base_dir):
    """按出现顺序收集图片，生成上传清单用的数据。"""
    out = []
    for sec in sections:
        for b in sec["blocks"]:
            if b["type"] != "img":
                continue
            src = b["src"]
            path = src if os.path.isabs(src) else os.path.join(base_dir, src)
            exists = os.path.isfile(path)
            w, h = image_size(path) if exists else (None, None)
            size_kb = round(os.path.getsize(path) / 1024, 1) if exists else None
            out.append({
                "src": src, "alt": b["alt"], "caption": b.get("caption", ""),
                "section": sec["title"] or "导语", "exists": exists,
                "w": w, "h": h, "kb": size_kb,
                "external": src.startswith(("http://", "https://")),
            })
    return out


def write_manifest(images, path, title):
    """生成「图片上传清单」：用户在公众号后台按这个顺序传图并插入。"""
    L = [f"# 图片上传清单 · {title}", ""]
    if not images:
        L.append("本篇没有图片。")
        open(path, "w", encoding="utf-8").write("\n".join(L) + "\n")
        return 0

    L.append("粘贴正文后，图片位置会是空的（或显示占位）。按下面顺序在公众号后台")
    L.append("「图片」按钮上传对应文件，插到标注的位置即可。")
    L.append("")
    L.append("| # | 文件 | 尺寸 | 体积 | 插在哪 | 说明（alt） |")
    L.append("|---|---|---|---|---|---|")
    for i, im in enumerate(images, 1):
        size = f"{im['w']}×{im['h']}" if im["w"] else "读不出"
        kb = f"{im['kb']} KB" if im["kb"] else "—"
        flag = ""
        if not im["exists"]:
            flag = " ⚠文件缺失"
        if im["external"]:
            flag = " ⚠外链"
        L.append(f"| {i} | `{im['src']}`{flag} | {size} | {kb} | {im['section']} | {im['alt'] or '—'} |")
    L.append("")

    missing = [im for im in images if not im["exists"] and not im["external"]]
    external = [im for im in images if im["external"]]
    big = [im for im in images if im["kb"] and im["kb"] > 500]

    if missing:
        L.append("## ⚠ 文件缺失")
        for im in missing:
            L.append(f"- `{im['src']}` 找不到，请先补齐或删掉这段图片标记")
        L.append("")
    if external:
        L.append("## ⚠ 外链图片")
        for im in external:
            L.append(f"- `{im['src']}` 是外链，粘到后台必裂。请先下载到本地再引用")
        L.append("")
    if big:
        L.append("## 体积提醒（公众号单图上限 10MB，建议 < 500KB）")
        for im in big:
            L.append(f"- `{im['src']}` {im['kb']} KB，建议压缩")
        L.append("")

    L.append("## 版权提醒")
    L.append("")
    L.append("下载来的图片不等于可以用。发布前确认每张图的授权：自制 / 明确可商用 / 已获授权。")
    L.append("来源不明的图，宁可不用——公众号图片侵权投诉处理得很快。")
    open(path, "w", encoding="utf-8").write("\n".join(L) + "\n")
    return len(images)


# ---------------------------------------------------------------- 入口
def main():
    ap = argparse.ArgumentParser(description="公众号图文 HTML 渲染器")
    ap.add_argument("path", nargs="?", help="Markdown 定稿路径")
    ap.add_argument("--out", default=None, help="输出 HTML 路径，默认同名 .html")
    ap.add_argument("--theme", default=None,
                    help="配色：a-ink/b-navy/c-dai/d-chestnut/e-graphite；默认随机")
    ap.add_argument("--seed", type=int, default=None,
                    help="随机配色的种子，填同一个数可复现同一套")
    ap.add_argument("--list-themes", action="store_true", help="列出五套配色")
    ap.add_argument("--no-footer", action="store_true", help="不输出落款区")
    ap.add_argument("--embed", action="store_true",
                    help="把本地图片转成 base64 内嵌（粘到后台不易裂，但 HTML 会变大）")
    ap.add_argument("--manifest", default=None,
                    help="生成图片上传清单的路径，默认与 HTML 同目录")
    args = ap.parse_args()

    if args.list_themes:
        for k, v in SCHEMES.items():
            print(f"{k:<12} {v['name']}  主色 {v['primary']} / 强调 {v['accent']} / 点缀 {v['spot']}")
            print(f"{'':<12} {v['mood']}")
        return

    if not args.path:
        print("缺少 Markdown 路径。用 --list-themes 可查看配色。", file=sys.stderr)
        sys.exit(2)

    try:
        with open(args.path, "r", encoding="utf-8") as f:
            raw = f.read()
    except OSError as e:
        print(f"读取失败：{e}", file=sys.stderr)
        sys.exit(2)

    fm, body = split_frontmatter(raw)
    sections = parse_sections(body)
    if not sections:
        print("没有可渲染的正文。检查是否用了「## 章节标题」和普通段落。", file=sys.stderr)
        sys.exit(2)

    base_dir = os.path.dirname(os.path.abspath(args.path))
    EMBED_IMAGES[0] = args.embed
    IMAGE_BASE[0] = base_dir

    # 配色优先级：--theme > frontmatter theme > 随机
    requested = args.theme or fm.get("theme")
    try:
        key, source = pick_scheme(requested, args.seed)
        t = resolve_scheme(key)
    except KeyError:
        print(f"未知配色「{requested}」。可选：{', '.join(SCHEMES)}", file=sys.stderr)
        sys.exit(2)

    out_html = build_html(fm, sections, t, with_footer=not args.no_footer)

    out_path = args.out or os.path.splitext(args.path)[0] + ".html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(out_html)

    n_sec = sum(1 for s in sections if s["title"])
    n_tbl = sum(1 for s in sections for b in s["blocks"] if b["type"] == "table")
    n_ol = sum(1 for s in sections for b in s["blocks"] if b["type"] == "ol")
    print(f"已渲染：{out_path}（{os.path.getsize(out_path)/1024:.1f} KB）")
    print(f"标题：{fm.get('title', '（未设置 title）')}")
    print(f"配色：{t['key']} {t['name']}（{source}）｜ 主色 {t['primary']} 强调 {t['accent']} 点缀 {t['spot']}")
    print(f"      {t['mood']}")
    if source.startswith("随机"):
        print("      想固定这套：下次加 --theme " + t["key"] + "，或在 frontmatter 写 theme: " + t["key"])
    print(f"章节 {n_sec} 个 ｜ 数据表 {n_tbl} 个 ｜ 编号清单 {n_ol} 个")

    # 图片与上传清单
    images = collect_images(sections, base_dir)
    if images:
        mpath = args.manifest or os.path.join(os.path.dirname(os.path.abspath(out_path)) or ".",
                                              "图片上传清单.md")
        n = write_manifest(images, mpath, fm.get("title", "未命名文章"))
        ok = sum(1 for im in images if im["exists"])
        print(f"图片 {n} 张（本地可得 {ok} 张）｜ 上传清单：{mpath}")
        print("  提示：粘到后台后图片位置为空，按清单顺序上传后插入即可。")
    print("下一步：python scripts/check_wx_html.py " + out_path)


if __name__ == "__main__":
    main()
