#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打包专家目录为可导入的 zip。

为什么不用官方 package_expert.py：它先调用 validate_expert.py，而该脚本的
categoryId 枚举只有 01—12，未收录平台在架教育类专家实际使用的 15-Education
（市场内已有 11 个专家在用），会产生误报并中止打包。本脚本保持同样的打包
结构约定，并额外做三件事：排除 dist/ 与缓存、校验路径分隔符、打包后自检。

用法：
    python build_package.py <专家目录> [输出目录]

结构约定：
    zip 顶层只有一个目录，名为专家目录名；
    清单位于 <顶层>/.codebuddy-plugin/plugin.json；
    头像位于 <顶层>/avatars/expert.png；
    条目统一使用正斜杠。
"""

import os
import sys
import zipfile

SKIP_DIRS = {"dist", "__pycache__", "node_modules", ".git"}
SKIP_FILES = {".DS_Store", "Thumbs.db", ".gitkeep"}
SKIP_EXT = {".pyc", ".pyo", ".zip", ".log", ".tmp"}


def collect(root, name):
    out = []
    for cur, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for f in sorted(files):
            if f in SKIP_FILES or os.path.splitext(f)[1].lower() in SKIP_EXT:
                continue
            full = os.path.join(cur, f)
            rel = os.path.relpath(full, root).replace("\\", "/")
            parts = rel.split("/")
            if any(p.startswith(".") and p not in (".codebuddy-plugin", ".workbuddy-plugin")
                   for p in parts):
                continue
            out.append((full, "%s/%s" % (name, rel)))
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    root = os.path.abspath(os.path.expanduser(sys.argv[1]))
    if not os.path.isdir(root):
        print("不是目录：%s" % root)
        return 1
    name = os.path.basename(root)

    out_dir = os.path.abspath(os.path.expanduser(sys.argv[2])) if len(sys.argv) > 2 else os.path.dirname(root)
    os.makedirs(out_dir, exist_ok=True)
    zpath = os.path.join(out_dir, name + ".zip")

    items = collect(root, name)
    if not items:
        print("没有可打包的文件")
        return 1

    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for full, arc in items:
            z.write(full, arc)

    size = os.path.getsize(zpath) / 1024.0
    print("已打包 %d 个文件 → %s（%.0f KB）" % (len(items), zpath, size))

    # 打包后立即自检结构
    with zipfile.ZipFile(zpath) as z:
        names = z.namelist()
    tops = {n.split("/")[0] for n in names}
    ok = True
    if tops != {name}:
        print("✗ 顶层目录异常：%s" % sorted(tops))
        ok = False
    if any("\\" in n for n in names):
        print("✗ 存在反斜杠路径")
        ok = False
    if "%s/.codebuddy-plugin/plugin.json" % name not in names:
        print("✗ 清单不在约定位置")
        ok = False
    if "%s/avatars/expert.png" % name not in names:
        print("✗ 头像不在约定位置（会导致导入后图标变文字）")
        ok = False
    print("结构自检：%s" % ("通过" if ok else "未通过"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
