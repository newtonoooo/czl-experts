#!/usr/bin/env python3
"""seo_files.py - read the indexing state of a built site and generate sitemap.xml
and robots.txt from the pages that actually exist.

Usage:
    python seo_files.py <dist-dir> --base-url https://example.com [--write] [--json]
    python seo_files.py <dist-dir> --base-url https://example.com --write --force

Exit codes: 0 = ok, 2 = fatal (bad base url / no pages), 1 = usage error.
"""

import argparse
import json
import os
import re
import sys
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SKIP_DIRS = {"node_modules", ".git", "__pycache__"}
DEFAULT_EXCLUDE = {"404.html", "500.html", "error.html"}


class Head(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = []
        self._in_title = False
        self.meta = []
        self.canonical = ""
        self.robots = ""

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            self.meta.append(a)
            name = a.get("name", "").lower()
            if name == "robots":
                self.robots = a.get("content", "")
        elif tag == "link" and "canonical" in a.get("rel", "").lower():
            self.canonical = a.get("href", "")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title.append(data)


def meta_content(meta, name):
    for a in meta:
        if a.get("name", "").lower() == name:
            return a.get("content", "")
    return ""


def page_url(base, rel):
    if rel.endswith("index.html"):
        rel = rel[: -len("index.html")]
    return urljoin(base + "/", rel.replace("\\", "/"))


def read_page(path):
    p = Head()
    try:
        p.feed(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        pass
    return {
        "title": "".join(p.title).strip(),
        "description": meta_content(p.meta, "description"),
        "canonical": p.canonical.strip(),
        "robots": (p.robots or meta_content(p.meta, "robots")).lower(),
    }


def main():
    ap = argparse.ArgumentParser(description="索引资料体检与生成")
    ap.add_argument("path")
    ap.add_argument("--base-url", required=True, help="站点正式地址，如 https://example.com")
    ap.add_argument("--write", action="store_true", help="写出 sitemap.xml 与 robots.txt")
    ap.add_argument("--force", action="store_true", help="覆盖已存在的 sitemap/robots")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    base = args.base_url.strip().rstrip("/")
    if not re.match(r"^https?://[^/\s]+", base):
        print(f"base-url 不合法: {args.base_url}（需以 http:// 或 https:// 开头）")
        return 2
    if base.startswith("http://"):
        print("提醒：base-url 用了 http://，正式站应统一到 https://，否则 canonical 会自相矛盾。")

    root = Path(args.path).expanduser()
    if not root.exists() or not root.is_dir():
        print(f"目录不存在: {root}")
        return 1
    root = root.resolve()

    pages = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if not name.lower().endswith((".html", ".htm")):
                continue
            path = Path(dirpath) / name
            rel = str(path.relative_to(root)).replace("\\", "/")
            info = read_page(path)
            info["file"] = rel
            info["url"] = page_url(base, rel)
            info["excluded"] = rel in DEFAULT_EXCLUDE or "noindex" in info["robots"]
            pages.append(info)

    if not pages:
        print(f"没有找到页面: {root}")
        return 2

    pages.sort(key=lambda x: x["file"])

    warnings = []
    titles = {}
    for p in pages:
        t = p["title"]
        if not t:
            warnings.append(f"{p['file']}: 缺 title")
        elif not (10 <= len(t) <= 60):
            warnings.append(f"{p['file']}: title {len(t)} 字符，建议 10–60")
        else:
            titles.setdefault(t, []).append(p["file"])
        d = p["description"]
        if not d:
            warnings.append(f"{p['file']}: 缺 meta description")
        elif not (50 <= len(d) <= 160):
            warnings.append(f"{p['file']}: description {len(d)} 字符，建议 50–160")
        if not p["canonical"]:
            warnings.append(f"{p['file']}: 缺 canonical")
        elif p["canonical"].rstrip("/") != p["url"].rstrip("/"):
            warnings.append(f"{p['file']}: canonical 指向 {p['canonical']}，与预期 {p['url']} 不一致")
        if p["excluded"] and "noindex" in p["robots"]:
            warnings.append(f"{p['file']}: 页面为 noindex，已排除在 sitemap 之外")

    for title, files in titles.items():
        if len(files) > 1:
            warnings.append("标题重复：" + " / ".join(files) + f" —— “{title}”")

    indexed = [p for p in pages if not p["excluded"]]
    today = date.today().isoformat()

    sitemap_lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                     '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for p in indexed:
        sitemap_lines.append("  <url>")
        sitemap_lines.append(f"    <loc>{p['url']}</loc>")
        sitemap_lines.append(f"    <lastmod>{today}</lastmod>")
        sitemap_lines.append("  </url>")
    sitemap_lines.append("</urlset>")
    sitemap = "\n".join(sitemap_lines) + "\n"

    robots = "\n".join([
        "User-agent: *",
        "Allow: /",
        "",
        f"Sitemap: {base}/sitemap.xml",
        "",
    ])

    if args.write:
        targets = [("sitemap.xml", sitemap), ("robots.txt", robots)]
        for name, content in targets:
            out = root / name
            if out.exists() and not args.force:
                warnings.append(f"{name} 已存在，未覆盖（要覆盖加 --force）")
                continue
            out.write_text(content, encoding="utf-8")

    if args.json:
        print(json.dumps({
            "base_url": base,
            "pages": pages,
            "indexed_count": len(indexed),
            "warnings": warnings,
            "written": args.write,
        }, ensure_ascii=False, indent=2))
        return 0

    print(f"索引体检 · {len(pages)} 页 · {base}")
    print("-" * 56)
    print(f"{'页面':<26}{'标题':>6}{'描述':>6}  规范链接")
    for p in pages:
        flag = "noindex" if p["excluded"] else ("OK" if p["canonical"].rstrip("/") == p["url"].rstrip("/") else "不一致")
        print(f"{p['file'][:26]:<26}{len(p['title']):>6}{len(p['description']):>6}  {flag}")
    print()
    print(f"进入 sitemap：{len(indexed)} 页（排除 404/500 与 noindex）")
    if warnings:
        print("问题")
        for w in warnings:
            print(f"  - {w}")
    else:
        print("问题：未发现")
    if args.write:
        print()
        print("已生成：sitemap.xml、robots.txt")
        print("预览 sitemap 前 5 行：")
        for line in sitemap.splitlines()[:5]:
            print("  " + line)
    else:
        print()
        print("（只读模式，未写文件。需要落盘加 --write）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
