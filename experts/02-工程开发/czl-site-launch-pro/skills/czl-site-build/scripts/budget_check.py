#!/usr/bin/env python3
"""budget_check.py - weigh a built site against a hard performance budget.

Sizes are measured after gzip for text assets (that is what the browser actually
downloads); images are counted raw because they are already compressed.

Usage:
    python budget_check.py <dist-dir> [--budget my-budget.json] [--json]

Exit codes: 0 = within budget, 2 = over budget, 1 = usage error.
"""

import argparse
import gzip
import json
import os
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DEFAULT_BUDGET_KB = {
    "html_gzip_kb": 60,
    "css_gzip_kb": 60,
    "js_gzip_kb": 200,
    "image_total_kb": 1200,
    "single_image_kb": 250,
    "font_total_kb": 300,
    "total_gzip_kb": 500,
    "single_file_kb": 2048,
}

TEXT_EXT = {".html", ".htm", ".css", ".js", ".mjs", ".json", ".xml", ".svg", ".txt", ".map"}
IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".avif", ".gif", ".ico", ".bmp"}
FONT_EXT = {".woff", ".woff2", ".ttf", ".otf", ".eot"}
SKIP_DIRS = {"node_modules", ".git", "__pycache__"}


def gzip_size(path):
    try:
        with open(path, "rb") as fh:
            return len(gzip.compress(fh.read(), 9))
    except OSError:
        return 0


def classify(ext):
    if ext in TEXT_EXT and ext not in (".svg",):
        return "text"
    if ext in IMG_EXT:
        return "image"
    if ext in FONT_EXT:
        return "font"
    return "other"


def scan(target):
    files = []
    for dirpath, dirnames, filenames in os.walk(target):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            path = Path(dirpath) / name
            ext = path.suffix.lower()
            try:
                raw = path.stat().st_size
            except OSError:
                continue
            kind = classify(ext)
            effective = gzip_size(path) if kind == "text" else raw
            files.append({
                "path": str(path.relative_to(target)).replace("\\", "/"),
                "ext": ext,
                "raw": raw,
                "effective": effective,
                "kind": kind,
            })
    return files


def kb(n):
    return round(n / 1024.0, 1)


def main():
    ap = argparse.ArgumentParser(description="按预算体检资源体积")
    ap.add_argument("path")
    ap.add_argument("--budget", help="自定义预算 JSON 文件")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    target = Path(args.path).expanduser()
    if not target.exists() or not target.is_dir():
        print(f"目录不存在: {target}")
        return 1

    budget = dict(DEFAULT_BUDGET_KB)
    if args.budget:
        try:
            custom = json.loads(Path(args.budget).read_text(encoding="utf-8"))
            budget.update({k: v for k, v in custom.items() if k in budget})
        except Exception as exc:
            print(f"预算文件读不了: {exc}")
            return 1

    files = scan(target.resolve())
    if not files:
        print(f"目录里没有文件: {target}")
        return 1

    groups = {"html": 0, "css": 0, "js": 0, "image": 0, "font": 0, "other": 0}
    for f in files:
        ext = f["ext"]
        if ext in (".html", ".htm"):
            groups["html"] += f["effective"]
        elif ext == ".css":
            groups["css"] += f["effective"]
        elif ext in (".js", ".mjs"):
            groups["js"] += f["effective"]
        elif ext in IMG_EXT:
            groups["image"] += f["effective"]
        elif ext in FONT_EXT:
            groups["font"] += f["effective"]
        else:
            groups["other"] += f["effective"]
    total = sum(f["effective"] for f in files)

    checks = [
        ("html", "HTML（gzip）", "html_gzip_kb"),
        ("css", "CSS（gzip）", "css_gzip_kb"),
        ("js", "JS（gzip）", "js_gzip_kb"),
        ("image", "图片（原始）", "image_total_kb"),
        ("font", "字体（原始）", "font_total_kb"),
    ]
    rows = []
    over = []
    for key, label, budget_key in checks:
        used = kb(groups[key])
        cap = float(budget[budget_key])
        state = "通过" if used <= cap else "超预算"
        if used > cap:
            over.append(f"{label} {used}KB / {cap}KB（超 {round(used - cap, 1)}KB）")
        rows.append((label, used, cap, state, round(cap - used, 1)))

    total_kb = kb(total)
    total_cap = float(budget["total_gzip_kb"])
    total_state = "通过" if total_kb <= total_cap else "超预算"
    if total_kb > total_cap:
        over.append(f"全站合计 {total_kb}KB / {total_cap}KB（超 {round(total_kb - total_cap, 1)}KB）")

    heavy_images = [f for f in files if f["ext"] in IMG_EXT and kb(f["effective"]) > float(budget["single_image_kb"])]
    heavy_files = [f for f in files if kb(f["raw"]) > float(budget["single_file_kb"])]
    for f in heavy_images:
        over.append(f"单图超限 {f['path']} {kb(f['effective'])}KB / {budget['single_image_kb']}KB")
    for f in heavy_files:
        over.append(f"单文件超限 {f['path']} {kb(f['raw'])}KB / {budget['single_file_kb']}KB")

    top = sorted(files, key=lambda x: x["effective"], reverse=True)[:8]
    worst = ""

    if args.json:
        print(json.dumps({
            "root": str(target.resolve()),
            "budget": budget,
            "groups_kb": {k: kb(v) for k, v in groups.items()},
            "total_kb": total_kb,
            "over": over,
            "top_files": [{"path": f["path"], "kb": kb(f["effective"])} for f in top],
            "verdict": "超预算" if over else "通过",
            "file_count": len(files),
        }, ensure_ascii=False, indent=2))
        return 2 if over else 0

    print(f"体积体检 · {len(files)} 个文件 · {target.resolve()}")
    print("-" * 52)
    print(f"{'项':<14}{'实测':>10}{'预算':>10}{'余量':>10}  状态")
    for label, used, cap, state, left in rows:
        print(f"{label:<14}{str(used) + 'KB':>10}{str(int(cap)) + 'KB':>10}{str(left) + 'KB':>10}  {state}")
    print(f"{'全站合计':<14}{str(total_kb) + 'KB':>10}{str(int(total_cap)) + 'KB':>10}"
          f"{str(round(total_cap - total_kb, 1)) + 'KB':>10}  {total_state}")
    print()
    print("最大的文件（按实际传输量）")
    for f in top:
        print(f"  {f['path']:<48}{kb(f['effective']):>8}KB")
    if over:
        print()
        print("超预算项")
        for item in over:
            print(f"  - {item}")
        worst = top[0]["path"] if top else ""
        print()
        print(f"结论：不通过。先处理 {worst} 这一类文件，通常前三项就能砍掉一半体积。")
        return 2
    print()
    print("结论：通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
