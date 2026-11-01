#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布包构建器（纯标准库）。

用法:
    python tools/build_release.py [专家包目录] [输出目录]

做的事：
  1. 先跑 selfcheck，未通过直接中止
  2. 打 zip：包内只有一个顶层目录（与客户端 resolveSingleTopLevelDir 的要求一致）
  3. 生成 SHA256 与文件清单

产物：
  <输出目录>/<包名>.zip
  <输出目录>/<包名>.zip.sha256
  <输出目录>/<包名>.manifest.json
"""

import hashlib
import json
import sys
import zipfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import selfcheck  # noqa: E402

SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".pytest_cache"}
SKIP_FILES = {".DS_Store", "Thumbs.db", ".gitkeep"}


def collect(root):
    files = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if p.name in SKIP_FILES or p.suffix == ".pyc":
            continue
        # 以点开头的机器相关文件（会话标记、下载标记等）不进发布包
        if p.name.startswith(".") and ".codebuddy-plugin" not in rel.parts:
            continue
        files.append(rel)
    return files


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
    out = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else root / "dist"
    out.mkdir(parents=True, exist_ok=True)

    print("== 第一步：自检 ==")
    code = run_selfcheck(root)
    if code != 0:
        print("\n自检未通过，已中止打包。")
        return 1

    pkg_name = root.name
    zip_path = out / f"{pkg_name}.zip"
    files = collect(root)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in files:
            z.write(root / rel, f"{pkg_name}/{rel.as_posix()}")

    digest = sha256_of(zip_path)
    (out / f"{pkg_name}.zip.sha256").write_text(f"{digest}  {pkg_name}.zip\n", encoding="utf-8")

    manifest = {
        "package": pkg_name,
        "built_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "zip_sha256": digest,
        "zip_size_bytes": zip_path.stat().st_size,
        "file_count": len(files),
        "files": [{"path": f"{pkg_name}/{r.as_posix()}", "size": (root / r).stat().st_size} for r in files],
    }
    (out / f"{pkg_name}.manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\n== 第二步：打包 ==")
    print(f"包名：{pkg_name}")
    print(f"文件数：{len(files)}")
    print(f"zip：{zip_path}")
    print(f"体积：{zip_path.stat().st_size / 1024:.1f} KB")
    print(f"SHA256：{digest}")
    print(f"清单：{out / (pkg_name + '.manifest.json')}")

    # 结构复核：顶层目录必须唯一
    with zipfile.ZipFile(zip_path) as z:
        tops = {n.split("/")[0] for n in z.namelist()}
    if len(tops) != 1 or tops.pop() != pkg_name:
        print("[FAIL] zip 顶层目录不唯一或名称不符，客户端可能导入失败")
        return 1
    print("顶层目录校验：通过（单一顶层目录，与客户端导入规则一致）")
    return 0


def run_selfcheck(root):
    import io
    import contextlib
    buf = io.StringIO()
    argv = sys.argv[:]
    sys.argv = ["selfcheck", str(root)]
    try:
        with contextlib.redirect_stdout(buf):
            code = selfcheck.main()
    finally:
        sys.argv = argv
    print(buf.getvalue())
    return code


if __name__ == "__main__":
    sys.exit(main())
