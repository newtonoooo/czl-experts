#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
blueprint_lint.py — 单文件工作台合规体检

© 2026 虫志龙 · 版权所有 ｜ 授权范围见包内 LICENSE
纯标准库实现：不联网、不装依赖、不上传任何数据。

检查项：
  1 外部资源引用（http/https/协议相对 //）—— error
  2 emoji 充当图标（图标上下文）—— error；正文 emoji —— warning
  3 输入框字号 < 16px 或未声明 —— error
  4 可点元素高度 < 44px —— error
  5 localStorage 键名缺统一前缀 —— error
  6 模块数 > 上限（默认 4）—— error
  7 文件体积超限 —— error（>600KB）/ warning（>300KB）
  8 缺 viewport meta —— error
  9 缺底部安全区 padding —— warning
 10 TODO / 占位文案残留 —— warning

用法：
  python blueprint_lint.py --file 台子.html
  python blueprint_lint.py --file 台子.html --prefix czl_desk_ --max-modules 4
  python blueprint_lint.py --file 台子.html --json
  python blueprint_lint.py --file 台子.html --strict      # warning 也算不通过

退出码：0 通过 ｜ 1 有 warning ｜ 2 有 error
"""

import argparse
import json
import re
import sys
from pathlib import Path

LEVEL_ORDER = {"error": 2, "warning": 1, "info": 0}

EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u2049\u203C]"
)

EXT_PATTERNS = [
    (re.compile(r"""(?:src|href|poster|data)\s*=\s*["']\s*(?:https?:)?//""", re.I), "标签属性引用外部资源"),
    (re.compile(r"""url\(\s*["']?\s*(?:https?:)?//""", re.I), "CSS url() 引用外部资源"),
    (re.compile(r"""@import\s+(?:url\()?\s*["']?\s*(?:https?:)?//""", re.I), "CSS @import 外部资源"),
    (re.compile(r"""<link[^>]+rel\s*=\s*["']stylesheet["']""", re.I), "<link rel=stylesheet>"),
    (re.compile(r"""<script[^>]+src\s*=""", re.I), "<script src=...>"),
]

TODO_RE = re.compile(r"TODO|FIXME|\[待补\]|待补充|占位文案|Lorem ipsum", re.I)


class Report:
    def __init__(self):
        self.items = []

    def add(self, level, code, msg, line=None, detail=None):
        self.items.append({"level": level, "code": code, "msg": msg, "line": line, "detail": detail})

    def count(self, level):
        return sum(1 for i in self.items if i["level"] == level)

    @property
    def exit_code(self):
        if self.count("error"):
            return 2
        if self.count("warning"):
            return 1
        return 0


def line_of(text, idx):
    return text.count("\n", 0, idx) + 1


def strip_blocks(text, tags=("script", "style")):
    """把 <script>/<style> 内容替换为等长空白，保留偏移量，便于行号定位。"""
    out = list(text)
    for tag in tags:
        for m in re.finditer(r"<%s\b[^>]*>(.*?)</%s>" % (tag, tag), text, re.S | re.I):
            for i in range(m.start(1), m.end(1)):
                if out[i] != "\n":
                    out[i] = " "
    return "".join(out)


def style_text(text):
    return "\n".join(m.group(1) for m in re.finditer(r"<style\b[^>]*>(.*?)</style>", text, re.S | re.I))


def script_text(text):
    return "\n".join(m.group(1) for m in re.finditer(r"<script\b[^>]*>(.*?)</script>", text, re.S | re.I))


def check_external(text, rep):
    for pat, label in EXT_PATTERNS:
        for m in pat.finditer(text):
            snippet = text[max(0, m.start() - 20): m.end() + 40].replace("\n", " ")
            rep.add("error", "EXT-REF", f"发现{label}，本产品要求零外链", line_of(text, m.start()), snippet.strip())


def check_emoji(text, rep):
    body = strip_blocks(text)
    for m in EMOJI_RE.finditer(body):
        ctx = body[max(0, m.start() - 60): m.end() + 60]
        in_icon = bool(re.search(r"<(button|a|i|span|li)\b[^>]*(class\s*=\s*[\"'][^\"']*icon[^\"']*[\"'])?[^>]*>[^<]{0,4}$", body[max(0, m.start() - 60): m.start()], re.I))
        snippet = body[max(0, m.start() - 25): m.end() + 25].replace("\n", " ")
        if in_icon:
            rep.add("error", "EMOJI-ICON", "用 emoji 充当图标，改为内联 SVG path", line_of(body, m.start()), snippet.strip())
        else:
            rep.add("warning", "EMOJI-TEXT", "正文出现 emoji，确认非功能图标即可保留", line_of(body, m.start()), snippet.strip())


def check_input_font(css, text, rep):
    if not css.strip():
        rep.add("error", "FONT-NO-STYLE", "没有 <style> 块，无法确认输入框字号（应 ≥16px）")
        return
    selectors = re.findall(r"([^{}]*)\{([^{}]*)\}", css, re.S)
    found = []
    for sel, body in selectors:
        if not re.search(r"\b(input|select|textarea)\b", sel, re.I):
            continue
        m = re.search(r"font-size\s*:\s*([\d.]+)\s*(px|rem|em)", body, re.I)
        if m:
            val, unit = float(m.group(1)), m.group(2).lower()
            px = val * 16 if unit != "px" else val
            found.append(px)
    if not found:
        rep.add("error", "FONT-MISSING", "未为 input/select/textarea 声明 font-size（需 ≥16px，否则 iOS 自动放大）")
    else:
        low = min(found)
        if low < 16:
            rep.add("error", "FONT-SMALL", f"输入框字号 {low:g}px < 16px，iOS 会放大整页")


def check_hit_target(css, rep):
    if not css.strip():
        rep.add("error", "HIT-NO-STYLE", "没有 <style> 块，无法确认可点元素尺寸（应 ≥44px）")
        return
    sizes = [int(x) for x in re.findall(r"min-height\s*:\s*(\d+)\s*px", css, re.I)]
    sizes += [int(x) for x in re.findall(r"(?<![\w-])height\s*:\s*(\d+)\s*px", css, re.I)]
    pads = [int(x) for x in re.findall(r"padding\s*:\s*(\d+)\s*px", css, re.I)]
    best = max(sizes) if sizes else 0
    best_pad = max(pads) if pads else 0
    if best < 44 and best_pad * 2 + 16 < 44:
        rep.add("error", "HIT-SMALL", f"未发现 ≥44px 的可点元素尺寸（最大 height/min-height = {best}px），手指点不中")


def check_storage(text, prefix, rep):
    """解析 localStorage 键：支持字面量与同文件内的常量变量（如 var KEY='x'; setItem(KEY,...)）。"""
    consts = dict(re.findall(r"""(?:var|const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*['"]([^'"]+)['"]""", text))
    args = re.findall(
        r"""localStorage\s*\.\s*(?:getItem|setItem|removeItem)\s*\(\s*([^,)\n]+)""", text
    )
    if not args:
        rep.add("warning", "STORE-NONE", "未发现 localStorage 调用，确认是否使用了其他持久化方式")
        return

    keys, dynamic = [], 0
    for raw in args:
        a = raw.strip()
        if a[:1] in ("'", '"'):
            keys.append(a.strip("'\" "))
        elif a in consts:
            keys.append(consts[a])
        else:
            dynamic += 1

    for k in sorted(set(keys)):
        if not k.startswith(prefix):
            rep.add("error", "STORE-PREFIX", f"存储键 “{k}” 缺少前缀 “{prefix}”（会与其他台子撞车）")
    if dynamic:
        rep.add("warning", "STORE-DYNAMIC", f"{dynamic} 处存储键为变量/拼接，无法静态核对前缀，请人工确认")
    if keys and all(k.startswith(prefix) for k in keys) and not dynamic:
        rep.add("info", "STORE-OK", f"{len(set(keys))} 个存储键均符合前缀约定")


def check_modules(text, max_modules, rep):
    n = len(re.findall(r"""data-module\s*=\s*["']""", text, re.I))
    if n == 0:
        rep.add("warning", "MODULE-NONE", '未找到 data-module 标记，无法核对模块数（约定每块卡片带 data-module="n"）')
    elif n > max_modules:
        rep.add("error", "MODULE-OVER", f"模块数 {n} 超过上限 {max_modules}，先出分期方案")
    else:
        rep.add("info", "MODULE-OK", f"模块数 {n}（上限 {max_modules}）")


def check_size(path, rep):
    kb = path.stat().st_size / 1024.0
    if kb > 600:
        rep.add("error", "SIZE-BIG", f"文件 {kb:.0f} KB 超过硬上限 600 KB")
    elif kb > 300:
        rep.add("warning", "SIZE-WARN", f"文件 {kb:.0f} KB 超过建议值 300 KB")
    else:
        rep.add("info", "SIZE-OK", f"文件 {kb:.0f} KB")


def check_vp(text, rep):
    if not re.search(r"<meta[^>]+name\s*=\s*[\"']viewport[\"']", text, re.I):
        rep.add("error", "VP-MISSING", "缺 viewport meta，手机端会按桌面宽度渲染")
    if not re.search(r"viewport-fit\s*=\s*cover", text, re.I):
        rep.add("warning", "VP-FIT", "viewport 未设置 viewport-fit=cover，刘海屏底部可能被遮")


def check_safe_area(css, rep):
    if "safe-area-inset-bottom" not in css:
        rep.add("warning", "SAFE-AREA", "未设置 env(safe-area-inset-bottom)，iPhone 底部按钮可能贴边")


def check_todo(text, rep):
    body = strip_blocks(text, tags=("script",))
    for m in TODO_RE.finditer(body):
        rep.add("warning", "TODO-LEFT", "存在占位或待办标记", line_of(body, m.start()), body[max(0, m.start()-20): m.end()+20].replace("\n", " "))


def lint(path, prefix, max_modules, strict=False):
    text = path.read_text(encoding="utf-8", errors="replace")
    css = style_text(text)
    rep = Report()

    check_external(text, rep)
    check_emoji(text, rep)
    check_input_font(css, text, rep)
    check_hit_target(css, rep)
    check_storage(text, prefix, rep)
    check_modules(text, max_modules, rep)
    check_size(path, rep)
    check_vp(text, rep)
    check_safe_area(css, rep)
    check_todo(text, rep)

    rep.items.sort(key=lambda i: (-LEVEL_ORDER[i["level"]], i["line"] or 0))
    return rep


ICON = {"error": "[x]", "warning": "[!]", "info": "[·]"}


def render(rep, path):
    lines = [f"# 合规体检 · {path.name}", ""]
    if not rep.items:
        lines.append("未发现问题。")
        return "\n".join(lines)
    for it in rep.items:
        loc = f" L{it['line']}" if it.get("line") else ""
        lines.append(f"{ICON[it['level']]} {it['level'].upper():7s} {it['code']:13s}{loc}  {it['msg']}")
        if it.get("detail"):
            lines.append(f"          └─ {it['detail'][:160]}")
    lines.append("")
    e, w = rep.count("error"), rep.count("warning")
    verdict = "不通过" if e else ("有警告，需逐条说明" if w else "通过")
    lines.append(f"合计：error {e} ｜ warning {w} ｜ info {rep.count('info')}  →  {verdict}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="单文件工作台合规体检（零依赖）")
    ap.add_argument("--file", required=True, help="待检 .html 文件")
    ap.add_argument("--prefix", default="czl_desk_", help="存储键前缀（默认 czl_desk_）")
    ap.add_argument("--max-modules", type=int, default=4, help="模块数上限（默认 4）")
    ap.add_argument("--strict", action="store_true", help="warning 也视为不通过")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    p = Path(args.file)
    if not p.exists():
        print(f"找不到文件：{args.file}", file=sys.stderr)
        return 3
    if p.suffix.lower() not in (".html", ".htm"):
        print(f"不是 HTML 文件：{args.file}", file=sys.stderr)
        return 3

    rep = lint(p, args.prefix, args.max_modules, args.strict)

    if args.json:
        print(json.dumps({
            "file": str(p), "error": rep.count("error"), "warning": rep.count("warning"),
            "info": rep.count("info"), "items": rep.items, "exit": rep.exit_code,
        }, ensure_ascii=False, indent=2))
    else:
        print(render(rep, p))

    code = rep.exit_code
    if args.strict and code == 1:
        code = 2
    return code


if __name__ == "__main__":
    sys.exit(main())
