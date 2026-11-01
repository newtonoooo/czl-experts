# -*- coding: utf-8 -*-
"""三棱镜 · 发布包构建

把专家包打成可上传的 zip，并生成校验和与文件清单。

排除：out/（运行产物）、dist/（输出目录）、__pycache__、.pyc、.git

用法：
  python tools/build_release.py [--out dist]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import zipfile

EXCLUDE_DIRS = {"out", "dist", "__pycache__", ".git", ".idea", ".vscode"}
EXCLUDE_EXT = {".pyc", ".pyo", ".log", ".png.tmp"}


def collect(root):
    items = []
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDE_DIRS)
        for f in sorted(files):
            if os.path.splitext(f)[1].lower() in EXCLUDE_EXT:
                continue
            p = os.path.join(base, f)
            items.append(os.path.relpath(p, root).replace("\\", "/"))
    return items


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    name = os.path.basename(root)
    manifest = json.load(open(os.path.join(root, ".codebuddy-plugin", "plugin.json"), encoding="utf-8"))
    version = manifest.get("version", "0.0.0")
    outdir = a.out or os.path.join(root, "dist")
    os.makedirs(outdir, exist_ok=True)
    zip_path = os.path.join(outdir, f"{name}-v{version}.zip")

    files = collect(root)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel in files:
            zf.write(os.path.join(root, rel), f"{name}/{rel}")

    size = os.path.getsize(zip_path)
    digest = sha256(zip_path)
    index = {
        "package": name,
        "version": version,
        "built_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
        "file_count": len(files),
        "zip_bytes": size,
        "sha256": digest,
        "files": files,
    }
    with open(os.path.join(outdir, f"{name}-v{version}.manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False, indent=2)
    with open(os.path.join(outdir, f"{name}-v{version}.sha256"), "w", encoding="utf-8") as fh:
        fh.write(f"{digest}  {os.path.basename(zip_path)}\n")

    print(json.dumps({"zip": zip_path, "files": len(files),
                      "bytes": size, "kb": round(size / 1024, 1),
                      "sha256": digest[:16] + "..."}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
