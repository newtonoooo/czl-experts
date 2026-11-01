#!/usr/bin/env python3
"""project_scan.py - identify what a site project is before touching it.

Reads only: no network, no writes. Outputs a human report or JSON.

Usage:
    python project_scan.py <project-dir> [--json]
Exit codes: 0 = scanned, 1 = usage error.
"""

import argparse
import json
import os
import sys
from pathlib import Path

try:  # keep Chinese output readable on legacy Windows consoles
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SKIP_DIRS = {"node_modules", ".git", ".hg", ".svn", ".idea", ".vscode", "__pycache__", ".venv", "venv"}
BUILD_CANDIDATES = ("dist", "build", "out", "_site", "public", ".next", ".output", "www")
TEXT_EXT = {".html", ".htm", ".css", ".js", ".mjs", ".json", ".xml", ".txt", ".svg", ".md", ".ts", ".tsx", ".jsx", ".vue", ".astro"}
IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".avif", ".gif", ".svg", ".ico", ".bmp"}
FONT_EXT = {".woff", ".woff2", ".ttf", ".otf", ".eot"}

FRAMEWORK_HINTS = [
    ("next", ("next",)),
    ("nuxt", ("nuxt", "nuxt3")),
    ("astro", ("astro",)),
    ("svelte", ("svelte", "@sveltejs/kit")),
    ("vue", ("vue",)),
    ("react", ("react",)),
    ("gatsby", ("gatsby",)),
    ("remix", ("@remix-run/react", "@remix-run/node")),
    ("eleventy", ("@11ty/eleventy",)),
    ("vite", ("vite",)),
    ("parcel", ("parcel",)),
]

CONFIG_FILES = ("vercel.json", "netlify.toml", "_headers", "staticwebapp.config.json", "wrangler.toml",
                "next.config.js", "next.config.mjs", "vite.config.js", "vite.config.ts", "astro.config.mjs",
                "tsconfig.json", "tailwind.config.js")


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024.0


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def detect_kind(root, pkg):
    evidence = []
    deps = {}
    if isinstance(pkg, dict):
        for key in ("dependencies", "devDependencies"):
            block = pkg.get(key)
            if isinstance(block, dict):
                deps.update(block)
        evidence.append("package.json")
    for kind, markers in FRAMEWORK_HINTS:
        hit = [m for m in markers if m in deps]
        if hit:
            evidence.append("package.json:" + hit[0] + "@" + str(deps.get(hit[0], "?")))
            return kind, deps, evidence
    for name in ("vercel.json",):
        if (root / name).exists():
            evidence.append(name)
    html_at_root = list(root.glob("*.html"))
    if html_at_root:
        evidence.append(f"{len(html_at_root)} 个根目录 HTML")
        return "static", deps, evidence
    if (root / "src").is_dir() and list((root / "src").glob("*.html")):
        evidence.append("src/*.html")
        return "static", deps, evidence
    if isinstance(pkg, dict):
        return "node-other", deps, evidence
    return "unknown", deps, evidence


def scan_counts(root):
    counts = {}
    total = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            path = Path(dirpath) / name
            try:
                size = path.stat().st_size
            except OSError:
                continue
            ext = path.suffix.lower()
            if ext in IMG_EXT:
                key = "img"
            elif ext in FONT_EXT:
                key = "font"
            elif ext in {".html", ".htm"}:
                key = "html"
            elif ext == ".css":
                key = "css"
            elif ext in {".js", ".mjs", ".jsx", ".ts", ".tsx"}:
                key = "js"
            else:
                key = "other"
            bucket = counts.setdefault(key, {"files": 0, "bytes": 0})
            bucket["files"] += 1
            bucket["bytes"] += size
            total += size
    counts["total_bytes"] = total
    return counts


def scan_build(root):
    out = []
    for name in BUILD_CANDIDATES:
        d = root / name
        if not d.is_dir():
            continue
        files = 0
        size = 0
        for dirpath, dirnames, filenames in os.walk(d):
            dirnames[:] = [x for x in dirnames if x != "node_modules"]
            for f in filenames:
                try:
                    size += (Path(dirpath) / f).stat().st_size
                    files += 1
                except OSError:
                    pass
        out.append({"dir": name, "files": files, "bytes": size})
    return out


def find_entries(root):
    entries = []
    for name in ("index.html", "index.htm"):
        if (root / name).exists():
            entries.append(name)
    for pattern in ("src/pages/*.html", "pages/*.html", "app/page.tsx", "src/App.vue", "src/main.js", "src/main.ts"):
        for hit in root.glob(pattern):
            entries.append(str(hit.relative_to(root)).replace("\\", "/"))
    return sorted(set(entries))[:12]


def artifact_flags(root, dist_dir):
    flags = {}
    flags["robots_txt"] = (dist_dir / "robots.txt").exists()
    flags["sitemap_xml"] = (dist_dir / "sitemap.xml").exists()
    flags["page_404"] = (dist_dir / "404.html").exists() or (dist_dir / "404" / "index.html").exists()
    flags["favicon"] = any((dist_dir / n).exists() for n in ("favicon.ico", "favicon.png", "favicon.svg"))
    flags["dotenv_in_repo"] = any((root / n).exists() for n in (".env", ".env.local", ".env.production"))
    flags["dotenv_example"] = any((root / n).exists() for n in (".env.example", ".env.sample", ".env.template"))
    flags["gitignore"] = (root / ".gitignore").exists()
    flags["configs"] = [c for c in CONFIG_FILES if (root / c).exists()]
    return flags


def gitignore_covers_env(root):
    gi = root / ".gitignore"
    if not gi.exists():
        return None
    try:
        text = gi.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return ".env" in text


def build_report(root):
    pkg = read_json(root / "package.json") if (root / "package.json").exists() else None
    kind, deps, evidence = detect_kind(root, pkg)
    version = None
    if isinstance(pkg, dict):
        version = pkg.get("version")
        for marker in ("next", "nuxt", "astro", "vite", "vue", "react"):
            if marker in deps:
                version = f"{marker}@{deps[marker]}"
                break
    counts = scan_counts(root)
    builds = scan_build(root)
    dist_dir = root
    for b in builds:
        if b["dir"] in ("dist", "build", "out", "_site", "public", "www"):
            dist_dir = root / b["dir"]
            break
    flags = artifact_flags(root, dist_dir)
    flags["gitignore_covers_env"] = gitignore_covers_env(root)
    return {
        "root": str(root),
        "kind": kind,
        "evidence": evidence,
        "version": version,
        "dependencies": sorted(deps)[:40],
        "entry_files": find_entries(root),
        "counts": counts,
        "build_outputs": builds,
        "serve_dir": str(dist_dir.relative_to(root)).replace("\\", "/") or ".",
        "artifacts": flags,
    }


def render(rep):
    lines = []
    lines.append("项目扫描")
    lines.append("-" * 46)
    lines.append(f"路径      {rep['root']}")
    lines.append(f"类型      {rep['kind']}   证据: {', '.join(rep['evidence']) or '无'}")
    if rep["version"]:
        lines.append(f"版本      {rep['version']}")
    c = rep["counts"]
    def line_of(key, label):
        b = c.get(key)
        if not b:
            return None
        return f"{label} {b['files']} 个 / {human_size(b['bytes'])}"
    parts = [p for p in (line_of("html", "HTML"), line_of("css", "CSS"), line_of("js", "JS"),
                         line_of("img", "图片"), line_of("font", "字体")) if p]
    lines.append("文件      " + " | ".join(parts) if parts else "文件      无")
    lines.append(f"合计      {c['total_bytes']} 字节 ({human_size(c['total_bytes'])})")

    if rep["build_outputs"]:
        for b in rep["build_outputs"]:
            lines.append(f"产物      {b['dir']}/  {b['files']} 个文件 / {human_size(b['bytes'])}")
    else:
        lines.append("产物      未发现（dist/build/out/_site/public）")
    lines.append(f"服务目录  {rep['serve_dir']}")

    a = rep["artifacts"]
    def mark(v):
        return "有" if v else "缺"
    lines.append("")
    lines.append("上线素材  robots.txt %s | sitemap.xml %s | 404 %s | favicon %s"
                 % (mark(a["robots_txt"]), mark(a["sitemap_xml"]), mark(a["page_404"]), mark(a["favicon"])))
    lines.append("环境文件  .env %s | .env.example %s | .gitignore %s%s"
                 % (mark(a["dotenv_in_repo"]), mark(a["dotenv_example"]), mark(a["gitignore"]),
                    "" if a["gitignore_covers_env"] is None else ("（含 .env）" if a["gitignore_covers_env"] else "（未含 .env，风险）")))
    if a["configs"]:
        lines.append("配置文件  " + ", ".join(a["configs"]))
    if rep["entry_files"]:
        lines.append("入口      " + ", ".join(rep["entry_files"]))

    lines.append("")
    lines.append("建议下一步")
    if rep["kind"] in ("unknown",):
        lines.append("  - 没识别出项目类型：确认目录是否指到了项目根，而不是它的上级目录")
    if rep["kind"] == "static":
        lines.append("  - 静态站：可直接跑 audit_html.py 与 budget_check.py")
    elif rep["kind"] != "unknown":
        lines.append("  - 框架项目：先构建，再对产物目录跑 budget_check.py")
    if not a["page_404"]:
        lines.append("  - 缺 404 页面：静态托管会把错误页交给默认页，上线前补上")
    if a["dotenv_in_repo"] and a["gitignore_covers_env"] is False:
        lines.append("  - .env 在版本库里且 .gitignore 没排除它：先确认有没有真实密钥被提交过")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="扫描站点项目结构")
    ap.add_argument("path")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    root = Path(args.path).expanduser()
    if not root.exists() or not root.is_dir():
        print(f"路径不存在或不是目录: {root}")
        return 1

    rep = build_report(root.resolve())
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print(render(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
