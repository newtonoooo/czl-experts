#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_release.py — 打包为可上传的 zip

产出两种目录结构，覆盖不同的导入方式：

    <name>-<version>.zip         顶层带一个同名文件夹（推荐，符合市场包布局）
    <name>-<version>-flat.zip    顶层直接是 plugin.json 等文件（部分导入器要求）

两者内容完全一致，只是路径前缀不同。上传时先试第一个，不行再试第二个。

用法：
    python scripts/build_release.py
    python scripts/build_release.py --out ../dist
"""

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 不进入发布包的路径（前缀匹配）
EXCLUDE_DIRS = {"assets-src", "release", "__pycache__", ".git", "dist", "node_modules"}
EXCLUDE_FILES = {"plugin.json.bak", "plugin.inline-avatar.json", "_inline_tmp.png", ".DS_Store", "Thumbs.db"}
EXCLUDE_SUFFIX = {".pyc", ".pyo", ".log", ".tmp"}


def collect(root):
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in EXCLUDE_DIRS for part in rel.parts[:-1]):
            continue
        if rel.name in EXCLUDE_FILES or path.suffix.lower() in EXCLUDE_SUFFIX:
            continue
        files.append(rel)
    return files


def write_zip(target, root, files, prefix):
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel in files:
            arcname = f"{prefix}/{rel.as_posix()}" if prefix else rel.as_posix()
            zf.write(root / rel, arcname)
    return target


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description="打包专家包为可上传 zip")
    parser.add_argument("--out", default=None, help="输出目录，默认在包内 release/")
    args = parser.parse_args()

    manifest_path = ROOT / ".codebuddy-plugin" / "plugin.json"
    if not manifest_path.is_file():
        print("[错误] 找不到 plugin.json")
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    name = manifest.get("name", ROOT.name)
    version = manifest.get("version", "0.0.0")

    out_dir = Path(args.out) if args.out else ROOT / "release"
    out_dir.mkdir(parents=True, exist_ok=True)

    files = collect(ROOT)
    if not files:
        print("[错误] 没有可打包的文件")
        return 1

    total = sum((ROOT / f).stat().st_size for f in files)

    z1 = out_dir / f"{name}-{version}.zip"
    write_zip(z1, ROOT, files, prefix=name)

    z2 = out_dir / f"{name}-{version}-flat.zip"
    write_zip(z2, ROOT, files, prefix="")

    print("=" * 66)
    print(f"打包完成：{name} {version}")
    print("=" * 66)
    print(f"  文件数：{len(files)}　原始体积：{total / 1024:.0f} KB")
    print()
    for z in (z1, z2):
        size = z.stat().st_size
        print(f"  {z.name}")
        print(f"    体积：{size / 1024:.0f} KB")
        print(f"    SHA256：{sha256(z)}")
    print()
    print("  上传顺序：先试带文件夹的那个，失败再试 -flat。")
    print()

    # 附一份清单，便于核对内容
    listing = out_dir / f"{name}-{version}-manifest.txt"
    with open(listing, "w", encoding="utf-8") as f:
        f.write(f"{name} {version}\n{'=' * 50}\n")
        for rel in files:
            f.write(f"{(ROOT / rel).stat().st_size:>9}  {rel.as_posix()}\n")
    print(f"  文件清单一并输出：{listing.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
