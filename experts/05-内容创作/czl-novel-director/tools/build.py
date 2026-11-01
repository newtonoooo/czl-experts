#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build.py — 生成可上传的发布包

产物：dist/czl-novel-director-<version>.zip
结构：zip 顶层是插件根目录 czl-novel-director/，其下为 .codebuddy-plugin/、agents/、
      skills/、avatars/、docs/、tools/、README.md、CHANGELOG.md、LICENSE。
      顶层只有一层，头像条目名与 plugin.json 的 avatar 字段逐字符一致。

排除：dist/（产物自身）、src-assets/（设计过程稿）、.DS_Store、__pycache__、*.tmp

用法：
    python tools/build.py [--root .] [--no-clean]

作者：虫志龙 <47190078@qq.com>
许可：MIT
"""

import argparse
import json
import os
import shutil
import sys
import zipfile

EXCLUDE_DIRS = {"dist", "src-assets", "__pycache__", ".git", ".idea", ".vscode"}
EXCLUDE_FILES = {".DS_Store", "Thumbs.db"}
EXCLUDE_EXT = {".pyc", ".tmp", ".bak"}


def collect(root):
    items = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fn in filenames:
            if fn in EXCLUDE_FILES or os.path.splitext(fn)[1].lower() in EXCLUDE_EXT:
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, root).replace("\\", "/")
            items.append((p, rel))
    items.sort(key=lambda x: x[1])
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--no-clean", action="store_true")
    a = ap.parse_args()
    root = os.path.abspath(a.root)

    with open(os.path.join(root, ".codebuddy-plugin", "plugin.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    name = manifest["name"]
    ver = manifest["version"]

    dist = os.path.join(root, "dist")
    if not a.no_clean and os.path.isdir(dist):
        shutil.rmtree(dist)
    os.makedirs(dist, exist_ok=True)

    out = os.path.join(dist, "%s-%s.zip" % (name, ver))
    items = collect(root)

    # 关键前置校验：头像必须在包内，且路径与清单一致
    av = manifest["avatar"]
    if not os.path.exists(os.path.join(root, av)):
        print("打包中止：avatar 指向的文件不存在 → %s" % av)
        return 2

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for p, rel in items:
            # 顶层加一层插件根目录
            zf.write(p, "%s/%s" % (name, rel))

    size = os.path.getsize(out)
    print("已生成：%s" % out)
    print("文件数：%d ｜ 体积：%.1f KB" % (len(items), size / 1024.0))

    # 打包后立即回读校验头像条目
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        want = "%s/%s" % (name, av)
        ok = want in names
        print("头像条目：%s → %s" % (want, "存在" if ok else "缺失！"))
        if not ok:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
