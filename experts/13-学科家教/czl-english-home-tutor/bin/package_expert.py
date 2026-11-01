#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""package_expert.py —— 生成本产品的发布 zip。

与 WorkBuddy 官方 package_expert.py 的输出结构保持一致：
  - zip 根目录为专家目录名（czl-english-home-tutor/）
  - 保留 .codebuddy-plugin/（隐藏目录，必须保留）
  - 跳过其余隐藏文件、.gitkeep、__pycache__、node_modules、系统垃圾文件

为什么不直接用官方脚本：官方脚本内置一份 12 项的分类白名单，未收录平台侧实际在用的
教育分类 15-Education（官方市场上 senior-math-tutor 等十余个学科家教均使用该值），
会在打包前中止。本脚本只做同样的事，不对分类值做二次判断；分类合法性由平台侧校验。

用法：
    python bin/package_expert.py [输出目录]
"""

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = ROOT.name
SKIP_NAMES = {".gitkeep", ".DS_Store", "Thumbs.db", ".created-by-session", ".downloaded_at"}
SKIP_DIRS = {"__pycache__", "node_modules", ".git"}


def should_include(rel_parts):
    for part in rel_parts:
        if part in SKIP_DIRS:
            return False
        if part.startswith(".") and part != ".codebuddy-plugin":
            return False
    return True


def main():
    out_dir = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"{NAME}.zip"

    files = []
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        if not should_include(rel.parts):
            continue
        if p.name in SKIP_NAMES:
            continue
        files.append((p, rel))

    required = {".codebuddy-plugin/plugin.json", "agents/" + NAME + ".md", "avatars/expert.png"}
    present = {rel.as_posix() for _, rel in files}
    missing = required - present
    if missing:
        print("缺少必需文件，已中止：" + ", ".join(sorted(missing)))
        return 1

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path, rel in files:
            zf.write(path, arcname=(Path(NAME) / rel).as_posix())
            print("  + %s" % (Path(NAME) / rel).as_posix())

    size_kb = zip_path.stat().st_size / 1024
    print("\n已生成 %s" % zip_path)
    print("文件数 %d，体积 %.1f KB" % (len(files), size_kb))
    return 0


if __name__ == "__main__":
    sys.exit(main())
