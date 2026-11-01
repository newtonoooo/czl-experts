#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""专家发布包构建器 — 生成符合 WorkBuddy 导入规范的 zip。

与通用打包脚本的差异（也是本脚本存在的理由）：
  1. zip 内所有路径使用正斜杠（Windows 上用 Path 拼接会写成反斜杠，
     平台按精确字符串匹配条目，反斜杠会导致 plugin.json 与头像都找不到）；
  2. 单一顶层目录，目录名等于 plugin.json 的 name；
  3. 排除会话标记、缓存、日志等平台会跳过的条目；
  4. 打包后立即回读校验：manifest 可定位、头像条目可解析。

用法:
    python build_zip.py <expert-dir> [output-dir]
"""

import json
import os
import sys
import zipfile
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SKIP_NAMES = {".DS_Store", ".created-by-session", ".pending-preview-session",
              "node_modules", ".git", ".cache", "cache", "storage", "history",
              "logs", "tmp", "temp", "__pycache__"}
SKIP_SUFFIX = (".log", ".tmp", ".zip")
FIXED_TIME = (2020, 1, 1, 0, 0, 0)


def collect(root: Path, zip_root: str):
    items = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_NAMES)
        for name in sorted(filenames):
            if name in SKIP_NAMES or name.lower().endswith(SKIP_SUFFIX):
                continue
            full = Path(dirpath) / name
            rel = full.relative_to(root).as_posix()
            items.append(("%s/%s" % (zip_root, rel), full))
    return items


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    root = Path(argv[1]).resolve()
    pj_path = root / ".codebuddy-plugin" / "plugin.json"
    if not pj_path.exists():
        print("错误: 找不到 %s" % pj_path)
        return 2
    pj = json.loads(pj_path.read_text(encoding="utf-8"))
    name = pj.get("name") or root.name
    version = pj.get("version", "0.0.0")

    out_dir = Path(argv[2]).resolve() if len(argv) > 2 else root.parent / "_dist"
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / ("%s-v%s.zip" % (name, version))

    items = collect(root, name)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for arc, full in items:
            info = zipfile.ZipInfo(arc, date_time=FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, full.read_bytes())

    # ---- 回读校验 ----
    problems = []
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        if any("\\" in n or n.startswith("/") for n in names):
            problems.append("条目路径不规范（反斜杠或绝对路径）")
        manifest = [n for n in names if n.endswith(".codebuddy-plugin/plugin.json")]
        if not manifest:
            problems.append("未找到 .codebuddy-plugin/plugin.json")
            zip_root = None
        else:
            zip_root = manifest[0][: -len(".codebuddy-plugin/plugin.json")].rstrip("/")
            if zip_root != name:
                problems.append("zip 根目录(%s) != name(%s)" % (zip_root, name))
        avatar = (pj.get("avatar") or "").replace("\\", "/").lstrip("./")
        if avatar:
            cands = (["%s/%s" % (zip_root, avatar), avatar] if zip_root else [avatar])
            if not any(c in names for c in cands):
                problems.append("头像条目缺失: %s" % cands)

    size_kb = zip_path.stat().st_size / 1024
    print("发布包: %s" % zip_path)
    print("条目数: %d｜体积: %.1f KB｜版本: %s" % (len(items), size_kb, version))
    print("根目录: %s" % (zip_root or "(无)"))
    if problems:
        for p in problems:
            print("  ✗ %s" % p)
        print("结果: FAIL")
        return 1
    print("  ✓ 路径规范（正斜杠）")
    print("  ✓ manifest 可定位")
    print("  ✓ 头像条目可解析")
    print("结果: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
