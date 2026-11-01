#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_wx_html.py — 公众号 HTML 合规自检（朱笔 / publish-kit 技能）

把《排版规范》的黑名单与交付自检清单变成可执行检查。
粘贴到公众号后台之前跑一遍，能提前发现 90% 的"粘过去就塌"。

用法:
    python check_wx_html.py 预览.html
    python check_wx_html.py 预览.html --json

退出码:
    0  无 FAIL（可能有 WARN）
    1  存在 FAIL
    2  输入错误
"""

import argparse
import json
import os
import re
import sys

# 会直接导致版面崩坏或内容被吞
FATAL = [
    (r"display\s*:\s*grid", "用了 grid 布局（公众号会过滤，多列直接堆叠）"),
    (r"display\s*:\s*flex", "用了 flex 布局（支持极差，手机端尤其不稳）"),
    (r"position\s*:\s*(absolute|relative|fixed)", "用了 position 定位（会被剥，元素回到文档流乱排）"),
    (r"transform\s*:", "用了 transform（位移/居中失效）"),
    (r"::before|::after", "用了伪元素（公众号完全不生成）"),
    (r"<script", "含 <script>（不执行，且会被过滤）"),
    (r"\son[a-z]+\s*=", "含事件属性（onclick 等，不执行）"),
    (r"<link[^>]+stylesheet", "引用了外部 CSS（不加载）"),
    (r"margin(?:-[a-z]+)?\s*:\s*-\s*\d", "用了负 margin（常被过滤，对齐会失效）"),
]

# 可能丢失但不致命
RISKY = [
    (r"box-shadow\s*:", "box-shadow 支持一般，可能丢失；建议改用 border 描边"),
    (r"linear-gradient", "渐变支持差，易变色；建议改纯色"),
    (r"calc\(", "calc() 支持不稳；建议写死数值"),
    (r"var\(\s*--", "CSS 变量支持不稳；建议写死数值"),
    (r"float\s*:", "float 支持不稳；建议用 table"),
]


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def scan_patterns(s, patterns, kind):
    hits = []
    for pat, msg in patterns:
        found = re.findall(pat, s, re.I)
        if found:
            hits.append({"level": kind, "pattern": pat, "message": msg, "count": len(found)})
    return hits


def check_font_fallback(s):
    """每个 font-family 必须以 serif / sans-serif 收尾。

    注意：样式值里普遍是单引号包字体名（style="font-family:'Noto Serif SC',serif"），
    所以正则只能排除双引号，不能排除单引号，否则整条规则会永远匹配不到。
    """
    bad = []
    for m in re.finditer(r"font-family\s*:\s*([^;\"]+)", s, re.I):
        val = m.group(1).strip().rstrip(";")
        if not val:
            continue
        tail = val.split(",")[-1].strip().strip("'\"").lower()
        if tail not in ("serif", "sans-serif", "monospace"):
            bad.append(val[:60])
    return bad


def check_tables(s):
    """含 th 的数据表必须有 table-layout:fixed 与 colgroup。"""
    problems = []
    for m in re.finditer(r"<table\b[^>]*>", s, re.I):
        tag = m.group(0)
        start = m.end()
        end = s.lower().find("</table>", start)
        inner = s[start:end] if end > 0 else ""
        is_data = "<th" in inner.lower()
        if not is_data:
            continue
        if "table-layout" not in tag.lower():
            problems.append("数据表缺少 table-layout:fixed（中文会被逐字折行）")
        if "<colgroup" not in inner.lower():
            problems.append("数据表缺少 <colgroup> 列宽定义（列宽会乱）")
    return problems


def check_dots(s):
    """圆点类元素必须同时有宽高。"""
    problems = []
    for m in re.finditer(r"<(span|div|i)\b[^>]*style=\"([^\"]*)\"[^>]*>", s, re.I):
        style = m.group(2)
        if "border-radius:50%" not in style.replace(" ", ""):
            continue
        if not re.search(r"(?<!max-)\bwidth\s*:", style) or not re.search(r"\bheight\s*:", style):
            problems.append(f"圆点缺宽高：style=\"{style[:50]}…\"")
    return problems


def check_container(s):
    """正文容器应固定宽度居中（600—760px）。"""
    widths = [int(x) for x in re.findall(r"max-width\s*:\s*(\d+)px", s)]
    ok = any(600 <= w <= 760 for w in widths)
    return ok, widths


def check_external(s):
    """外链图片会过期/防盗链。"""
    problems = []
    for m in re.finditer(r"<img[^>]+src=\"([^\"]+)\"", s, re.I):
        src = m.group(1)
        if src.startswith("http"):
            problems.append(f"外链图片：{src[:60]}")
        elif src.startswith("data:"):
            problems.append("base64 内嵌图片：体积大，建议改走素材库")
    return problems


def check_style_tag(s):
    """<style> 里若用了 class 选择器，正文粘贴后不生效。"""
    problems = []
    for m in re.finditer(r"<style[^>]*>(.*?)</style>", s, re.S | re.I):
        css = m.group(1)
        if re.search(r"^\s*\.[a-zA-Z]", css, re.M):
            problems.append("<style> 中含 class 选择器，粘贴后不生效（只可作浏览器预览用）")
    if re.search(r'<body[\s\S]*?\sclass="', s):
        problems.append("正文元素用了 class，公众号粘贴后样式不生效")
    return problems


def run(path):
    s = read(path)
    fatal = scan_patterns(s, FATAL, "FAIL")
    risky = scan_patterns(s, RISKY, "WARN")
    issues = []

    bad_font = check_font_fallback(s)
    if bad_font:
        issues.append({"level": "FAIL", "message": "字体栈缺少系统 fallback，粘贴后字体全变样",
                       "detail": bad_font[:3]})

    tbl = check_tables(s)
    if tbl:
        issues.append({"level": "FAIL", "message": "表格结构不合规", "detail": tbl[:4]})

    dots = check_dots(s)
    if dots:
        issues.append({"level": "FAIL", "message": "圆点元素缺宽高，可能显示成方块", "detail": dots[:3]})

    ok, widths = check_container(s)
    if not ok:
        issues.append({"level": "FAIL", "message": "正文容器未设置 600—760px 的 max-width",
                       "detail": widths[:3]})

    ext = check_external(s)
    if ext:
        issues.append({"level": "WARN", "message": "存在外链/内嵌图片", "detail": ext[:3]})

    st = check_style_tag(s)
    if st:
        issues.append({"level": "WARN", "message": "样式依赖问题", "detail": st})

    all_iss = fatal + risky + issues
    n_fail = sum(1 for x in all_iss if x["level"] == "FAIL")
    n_warn = sum(1 for x in all_iss if x["level"] == "WARN")

    # 统计
    stats = {
        "size_kb": round(os.path.getsize(path) / 1024, 1),
        "tables": len(re.findall(r"<table\b", s, re.I)),
        "cards": len(re.findall(r"border:1px solid", s)),
        "inline_styles": len(re.findall(r'style="', s)),
        "has_script": bool(re.search(r"<script", s, re.I)),
        "container_widths": widths,
    }
    return all_iss, n_fail, n_warn, stats


def main():
    ap = argparse.ArgumentParser(description="公众号 HTML 合规自检")
    ap.add_argument("path")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    try:
        issues, n_fail, n_warn, stats = run(args.path)
    except OSError as e:
        print(f"读取失败：{e}", file=sys.stderr)
        sys.exit(2)

    if args.json:
        print(json.dumps({"issues": issues, "fail": n_fail, "warn": n_warn,
                          "stats": stats}, ensure_ascii=False, indent=2))
    else:
        print("=" * 52)
        print("公众号 HTML 合规自检")
        print("=" * 52)
        print(f"文件：{args.path}（{stats['size_kb']} KB）")
        print(f"内联样式 {stats['inline_styles']} 处 ｜ 表格 {stats['tables']} 个 ｜ "
              f"卡片 {stats['cards']} 个 ｜ 容器宽 {stats['container_widths']}")
        print("-" * 52)
        if not issues:
            print("✅ 全部通过：可以粘贴到公众号后台。")
        else:
            for x in issues:
                mark = "✗" if x["level"] == "FAIL" else "⚠"
                print(f"{mark} [{x['level']}] {x.get('message')}")
                for d in x.get("detail", []) or []:
                    print(f"      · {d}")
                if x.get("pattern"):
                    print(f"      命中 {x['count']} 处：{x['pattern']}")
        print("-" * 52)
        print(f"结果：{n_fail} 项 FAIL ／ {n_warn} 项 WARN")
        if n_fail == 0:
            print("粘到后台后仍需人工核对：章节条底色、表格列宽、圆点对齐、手机预览。")
        print("=" * 52)

    sys.exit(0 if n_fail == 0 else 1)


if __name__ == "__main__":
    main()
