#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""卓识化学 · 发布包构建

产出 dist/czl-chem-teaching-suite-<version>.zip，zip 内部保留顶层目录
（客户端导入时依赖"单一顶层目录 + 其中的 .codebuddy-plugin/plugin.json"）。

用法：
    python tools/build_release.py
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import zipfile
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.basename(ROOT)
EXCLUDE_DIRS = {"dist", "__pycache__", ".git", ".idea", ".vscode", "node_modules"}
EXCLUDE_FILES = {".DS_Store", "Thumbs.db"}
EXCLUDE_SUFFIX = (".pyc", ".pyo")
# 不进包的过程文件（原始大图、水印图等）
EXCLUDE_PATTERNS = ("正方形应用头像插画",)

def should_skip(path: str, name: str) -> bool:
    if name in EXCLUDE_FILES or name.endswith(EXCLUDE_SUFFIX):
        return True
    if any(p in name for p in EXCLUDE_PATTERNS):
        return True
    return False


def collect(root: str):
    entries = []
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in sorted(files):
            if should_skip(base, f):
                continue
            full = os.path.join(base, f)
            rel = os.path.relpath(full, root).replace("\\", "/")
            entries.append((rel, full))
    entries.sort(key=lambda x: x[0])
    return entries


def main() -> int:
    with open(os.path.join(ROOT, "VERSION"), encoding="utf-8") as f:
        version = f.read().strip()
    out_dir = os.path.join(ROOT, "dist")
    os.makedirs(out_dir, exist_ok=True)
    zip_path = os.path.join(out_dir, f"{PKG}-{version}.zip")

    entries = collect(ROOT)
    if not any(rel == ".codebuddy-plugin/plugin.json" for rel, _ in entries):
        print("构建失败：找不到 .codebuddy-plugin/plugin.json")
        return 1

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel, full in entries:
            z.write(full, f"{PKG}/{rel}")

    # 校验：回读
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        bad = z.testzip()
    problems = []
    if bad:
        problems.append(f"zip 校验失败于：{bad}")
    if f"{PKG}/.codebuddy-plugin/plugin.json" not in names:
        problems.append("zip 内缺少顶层 .codebuddy-plugin/plugin.json")
    if any(n.startswith(f"{PKG}/dist/") for n in names):
        problems.append("zip 内混入了 dist/ 目录")
    tops = {n.split("/")[0] for n in names}
    if tops != {PKG}:
        problems.append(f"zip 顶层目录不唯一：{sorted(tops)}")

    sha = hashlib.sha256()
    with open(zip_path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            sha.update(chunk)
    digest = sha.hexdigest()
    size = os.path.getsize(zip_path)

    info = {
        "package": PKG,
        "version": version,
        "built_at": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S%z"),
        "zip": os.path.basename(zip_path),
        "zip_bytes": size,
        "file_count": len(names),
        "sha256": digest,
        "top_level_dir": PKG,
        "self_check": "passed" if not problems else problems,
    }
    with open(os.path.join(out_dir, f"{PKG}-{version}.manifest.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)

    print("=" * 60)
    print(f"发布包：{zip_path}")
    print(f"文件数：{len(names)}　体积：{size/1024:.0f} KB")
    print(f"SHA-256：{digest}")
    if problems:
        print("自检未通过：")
        for p in problems:
            print("  -", p)
        return 1
    print("自检：通过（顶层目录唯一、清单在根、无 dist 混入）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
