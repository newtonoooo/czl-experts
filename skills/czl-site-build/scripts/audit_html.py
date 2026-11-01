#!/usr/bin/env python3
"""audit_html.py - static accessibility / structure / metadata audit for HTML files.

Pure stdlib. Parses real HTML (not regex), reports findings with rule ids,
severity and line numbers. What it cannot judge (contrast, focus order, real
devices) is listed as unverified rather than silently passed.

Usage:
    python audit_html.py <dir|file> [--fail-on low|medium|high|blocker] [--json]

Exit codes: 0 = nothing at or above the threshold, 2 = findings at/above threshold,
            1 = usage error.
"""

import argparse
import json
import os
import sys
from html.parser import HTMLParser
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SEV_ORDER = {"low": 1, "medium": 2, "high": 3, "blocker": 4}
SEV_LABEL = {"blocker": "阻塞", "high": "高", "medium": "中", "low": "低"}
SKIP_DIRS = {"node_modules", ".git", ".svn", ".idea", ".vscode", "__pycache__"}

RULES = {
    "H001": ("blocker", "文档缺 <!DOCTYPE html>，浏览器会进入混杂模式"),
    "H002": ("high", "<html> 缺 lang 属性，读屏器无法选择语言"),
    "H003": ("high", "缺 viewport 元信息，手机端会按桌面宽度缩放"),
    "H004": ("medium", "缺 charset 声明，非英文字符可能乱码"),
    "H005": ("blocker", "title 缺失或长度不当（应 10–60 字符）"),
    "H006": ("high", "meta description 缺失或长度不当（应 50–160 字符）"),
    "H007": ("medium", "缺 canonical，多个地址指向同一内容时权重分散"),
    "H008": ("low", "缺 Open Graph 标签，分享出去没有卡片"),
    "H009": ("high", "h1 数量不是恰好 1 个"),
    "H010": ("medium", "标题层级跳号"),
    "H011": ("blocker", "<img> 缺 alt 属性"),
    "H012": ("medium", "<img> 缺 width/height，加载时会跳版"),
    "H013": ("blocker", "表单字段没有可访问名称（无 label / aria-label）"),
    "H014": ("high", "页面内 id 重复"),
    "H015": ("medium", "新窗口链接缺 rel=noopener"),
    "H016": ("high", "资源用 http:// 引用，HTTPS 站点会被浏览器拦截"),
    "H017": ("medium", "<head> 里的脚本没有 defer/async，阻塞首屏"),
    "H018": ("medium", "<iframe> 缺 title，读屏器只能念“框架”"),
    "H019": ("high", "按钮没有文字也没有 aria-label，读屏器读不出用途"),
    "H020": ("low", "缺 favicon 声明"),
    "H021": ("low", "内联 style 过多，样式难以统一维护"),
    "H022": ("low", "页面没有 <main> 地标，跳读困难"),
    "H023": ("low", "没有结构化数据（JSON-LD）"),
}

FIXES = {
    "H001": "文件第一行写 <!DOCTYPE html>",
    "H002": "改成 <html lang=\"zh-CN\">（中文站）",
    "H003": "加 <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
    "H004": "首行加 <meta charset=\"utf-8\">",
    "H005": "每页写唯一标题，10–60 字符，含页面主题",
    "H006": "加 50–160 字符的描述，写清这页解决什么问题",
    "H007": "加 <link rel=\"canonical\" href=\"https://正式域名/当前路径\">，用绝对地址",
    "H008": "补 og:title / og:description / og:image（1200×630）",
    "H009": "保留一个 h1 作页面主标题，其余降为 h2",
    "H010": "按 h1→h2→h3 顺序使用，不要从 h2 直接跳到 h4",
    "H011": "写清图片内容；纯装饰图写 alt=\"\"",
    "H012": "按原始像素写 width/height，或配合 aspect-ratio",
    "H013": "给字段加 <label for>，或加 aria-label",
    "H014": "改成唯一 id，重复的多半是复制粘贴留下的",
    "H015": "加 rel=\"noopener noreferrer\"",
    "H016": "把 http:// 改成 https://，外链也一样",
    "H017": "加 defer（或 type=\"module\"），只在必要时用 async",
    "H018": "加 title=\"这段嵌入是什么\"",
    "H019": "加 aria-label，或补可见文字",
    "H020": "加 <link rel=\"icon\" href=\"/favicon.ico\" sizes=\"32x32\">",
    "H021": "抽到 CSS 文件或改类名",
    "H022": "用 <main> 包住主内容",
    "H023": "按页面类型加 Organization / Article / Product 的 JSON-LD",
}

TEXT_INPUT_TYPES = {"", "text", "email", "tel", "url", "search", "password", "number", "date",
                    "datetime-local", "month", "week", "time", "color", "range", "file"}


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []          # (tag, attrs, lineno)
        self.title_chunks = []
        self.buttons = []       # (lineno, text)
        self.controls = []      # dict(tag, attrs, lineno, in_label)
        self.label_fors = []
        self._in_title = False
        self._label_depth = 0
        self._in_head = False
        self._button = None     # dict(line, text)
        self.attr_style_count = 0
        self.style_tag_count = 0

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v if v is not None else "") for k, v in attrs}
        line = self.getpos()[0]
        self.tags.append((tag, a, line))
        if "style" in a:
            self.attr_style_count += 1
        if tag == "html":
            self._lang = a.get("lang", "")
        if tag == "head":
            self._in_head = True
        if tag == "title":
            self._in_title = True
        if tag == "style":
            self.style_tag_count += 1
        if tag == "label":
            self._label_depth += 1
            if a.get("for"):
                self.label_fors.append(a["for"])
        if tag == "button":
            self._button = {"line": line, "text": [], "attrs": a}
        if tag in ("input", "select", "textarea"):
            itype = a.get("type", "").lower()
            if tag == "input" and itype not in TEXT_INPUT_TYPES:
                pass  # submit/button/hidden/checkbox etc. handled elsewhere
            else:
                self.controls.append({"tag": tag, "attrs": a, "line": line,
                                      "in_label": self._label_depth > 0})

    def handle_endtag(self, tag):
        if tag == "head":
            self._in_head = False
        if tag == "title":
            self._in_title = False
        if tag == "label" and self._label_depth > 0:
            self._label_depth -= 1
        if tag == "button" and self._button is not None:
            self.buttons.append((self._button["line"], "".join(self._button["text"]).strip(),
                                 self._button["attrs"]))
            self._button = None

    def handle_data(self, data):
        if self._in_title:
            self.title_chunks.append(data)
        if self._button is not None:
            self._button["text"].append(data)


def attr(tags, tag_name, key, default=""):
    for t, a, _ in tags:
        if t == tag_name and key in a:
            return a[key]
    return default


def all_of(tags, tag_name):
    return [(a, line) for t, a, line in tags if t == tag_name]


def audit_file(path):
    raw = path.read_text(encoding="utf-8", errors="replace")
    parser = PageParser()
    try:
        parser.feed(raw)
        parser.close()
    except Exception:
        pass

    found = {}  # rule -> list of (line, note)

    def hit(rule, line, note=""):
        found.setdefault(rule, []).append((line, note))

    if not raw.lstrip()[:15].lower().startswith("<!doctype"):
        hit("H001", 1)

    if not getattr(parser, "_lang", "").strip():
        hit("H002", 1)

    metas = all_of(parser.tags, "meta")
    has_charset = any("charset" in a for a, _ in metas)
    if not has_charset:
        hit("H004", 1)

    viewport = [a for a, _ in metas if a.get("name", "").lower() == "viewport"]
    if not viewport:
        hit("H003", 1)
    elif "width=device-width" not in viewport[0].get("content", "").replace(" ", "").lower():
        hit("H003", 1, "viewport 未声明 width=device-width")

    title = "".join(parser.title_chunks).strip()
    if not title:
        hit("H005", 1)
    elif not (10 <= len(title) <= 60):
        hit("H005", 1, f"标题 {len(title)} 字符，建议 10–60")

    desc = ""
    for a, _ in metas:
        if a.get("name", "").lower() == "description":
            desc = a.get("content", "").strip()
            break
    if not desc:
        hit("H006", 1)
    elif not (50 <= len(desc) <= 160):
        hit("H006", 1, f"描述 {len(desc)} 字符，建议 50–160")

    links = all_of(parser.tags, "link")
    canonical = [a for a, _ in links if "canonical" in a.get("rel", "").lower()]
    if not canonical:
        hit("H007", 1)
    elif not canonical[0].get("href", "").startswith(("http://", "https://")):
        hit("H007", 1, "canonical 用了相对地址，应为绝对 URL")

    og = [a for a, _ in metas if a.get("property", "").lower().startswith("og:")]
    if len(og) == 0:
        hit("H008", 1)
    elif len(og) < 3:
        hit("H008", 1, f"只找到 {len(og)} 个 og 标签")

    headings = [(int(t[1]), line) for t, a, line in parser.tags if t in ("h1", "h2", "h3", "h4", "h5", "h6")]
    h1s = [h for h in headings if h[0] == 1]
    if len(h1s) != 1:
        hit("H009", h1s[0][1] if h1s else 1, f"共 {len(h1s)} 个 h1")
    prev = None
    for level, line in headings:
        if prev is not None and level > prev + 1:
            hit("H010", line, f"h{prev} 直接跳到 h{level}")
        prev = level

    for a, line in all_of(parser.tags, "img"):
        if "alt" not in a:
            hit("H011", line, a.get("src", "")[:60])
        if not (a.get("width") and a.get("height")):
            hit("H012", line, a.get("src", "")[:60])

    label_for = set(parser.label_fors)
    for c in parser.controls:
        a = c["attrs"]
        named = bool(a.get("aria-label") or a.get("aria-labelledby") or a.get("title"))
        if not named and not c["in_label"] and a.get("id") not in label_for:
            hit("H013", c["line"], f"<{c['tag']}> " + (a.get("name") or a.get("id") or a.get("type", "")))

    seen = {}
    for t, a, line in parser.tags:
        if "id" in a:
            seen.setdefault(a["id"], []).append(line)
    for ident, lines in seen.items():
        if len(lines) > 1:
            hit("H014", lines[1], f"id=\"{ident}\" 出现 {len(lines)} 次")

    for a, line in all_of(parser.tags, "a"):
        if a.get("target", "") == "_blank" and "noopener" not in a.get("rel", "").lower():
            hit("H015", line, a.get("href", "")[:50])

    resource_attrs = []
    for a, line in all_of(parser.tags, "img"):
        resource_attrs.append((a.get("src", ""), line))
    for tag in ("script", "iframe", "source", "video", "audio", "embed", "link"):
        for a, line in all_of(parser.tags, tag):
            for key in ("src", "href", "data"):
                if a.get(key):
                    resource_attrs.append((a.get(key, ""), line))
    for url, line in resource_attrs:
        if url.lower().startswith("http://"):
            hit("H016", line, url[:70])

    for t, a, line in parser.tags:
        if t == "script" and a.get("src"):
            if parser_tag_in_head(parser.tags, line):
                if "defer" not in a and "async" not in a and a.get("type", "") != "module":
                    hit("H017", line, a.get("src", "")[:60])

    for a, line in all_of(parser.tags, "iframe"):
        if not a.get("title"):
            hit("H018", line)

    for line, text, a in parser.buttons:
        if not text and not (a.get("aria-label") or a.get("aria-labelledby") or a.get("title")):
            hit("H019", line)

    if not any("icon" in a.get("rel", "").lower() for a, _ in links):
        hit("H020", 1)

    if parser.attr_style_count > 25:
        hit("H021", 1, f"内联 style {parser.attr_style_count} 处")

    if not any(t == "main" for t, _, _ in parser.tags):
        hit("H022", 1)

    if not any(a.get("type", "").lower() == "application/ld+json"
               for a, _ in all_of(parser.tags, "script")):
        hit("H023", 1)

    return found


def parser_tag_in_head(tags, line):
    """True if the tag at `line` appears between <head> and </head> in source order."""
    in_head = False
    for t, a, ln in tags:
        if t == "head":
            in_head = True
        elif t == "body":
            in_head = False
        if ln == line and t == "script":
            return in_head
        if ln > line:
            break
    return False


def collect(target):
    if target.is_file():
        return [target]
    files = []
    for dirpath, dirnames, filenames in os.walk(target):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name.lower().endswith((".html", ".htm")):
                files.append(Path(dirpath) / name)
    return sorted(files)


def main():
    ap = argparse.ArgumentParser(description="HTML 静态体检")
    ap.add_argument("path")
    ap.add_argument("--fail-on", default="high", choices=["low", "medium", "high", "blocker"])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    target = Path(args.path).expanduser()
    if not target.exists():
        print(f"路径不存在: {target}")
        return 1

    files = collect(target.resolve())
    if not files:
        print(f"没有找到 HTML 文件: {target}")
        return 1

    root = target.resolve() if target.is_dir() else target.resolve().parent
    findings = []
    file_stats = {}
    for f in files:
        rel = str(f.relative_to(root)).replace("\\", "/")
        found = audit_file(f)
        file_stats[rel] = len(found)
        for rule, occurrences in found.items():
            severity, message = RULES[rule]
            findings.append({
                "rule": rule,
                "severity": severity,
                "file": rel,
                "count": len(occurrences),
                "lines": [ln for ln, _ in occurrences][:5],
                "first_note": next((n for _, n in occurrences if n), ""),
                "message": message,
                "fix": FIXES.get(rule, ""),
            })

    counts = {k: 0 for k in ("blocker", "high", "medium", "low")}
    for f in findings:
        counts[f["severity"]] += 1

    worst = max([SEV_ORDER[f["severity"]] for f in findings], default=0)
    failed = worst >= SEV_ORDER[args.fail_on]
    verdict = "不通过" if (counts["blocker"] or counts["high"]) else ("有改进项" if findings else "通过")

    if args.json:
        print(json.dumps({
            "root": str(root),
            "files": file_stats,
            "findings": sorted(findings, key=lambda x: (-SEV_ORDER[x["severity"]], x["rule"])),
            "counts": counts,
            "verdict": verdict,
            "failed": failed,
            "unverified": ["对比度（需浏览器实际渲染）", "焦点顺序（需人工 Tab）", "真机字号与点击区域"],
        }, ensure_ascii=False, indent=2))
        return 2 if failed else 0

    print(f"HTML 体检 · {len(files)} 个文件 · 目录 {root}")
    print("-" * 46)
    for f in sorted(findings, key=lambda x: (-SEV_ORDER[x["severity"]], x["rule"])):
        loc = f["file"]
        if f["lines"]:
            loc += f":{f['lines'][0]}"
        more = f"（共 {f['count']} 处）" if f["count"] > 1 else ""
        note = f" — {f['first_note']}" if f["first_note"] else ""
        print(f"[{SEV_LABEL[f['severity']]}] {f['rule']} {loc}  {f['message']}{more}{note}")
        if f["fix"]:
            print(f"        修法：{f['fix']}")
    if not findings:
        print("未发现静态规则问题。")
    print()
    print(f"汇总：阻塞 {counts['blocker']} / 高 {counts['high']} / 中 {counts['medium']} / 低 {counts['low']}")
    print(f"结论：{verdict}（阈值 --fail-on {args.fail_on}）")
    print("未静态判定：对比度、焦点顺序、真机字号——这三项需在浏览器与真机上确认。")
    return 2 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
