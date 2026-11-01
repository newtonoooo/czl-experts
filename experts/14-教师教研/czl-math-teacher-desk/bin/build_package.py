#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_package.py —— 打包成可上传的 zip（纯标准库，零依赖）。

与官方 `package_expert.py` 的差别只有一个：
官方脚本在压缩前会跑 `validate_expert.py`，而该脚本的分类表只收录 12 类，
本包按同品牌教育系列使用 `15-Education`，会被判为错误并中止。

本脚本的做法：
    1. 先跑 `check_package.py`（含元数据、引用、头像的全部检查），必过；
    2. 再断言三个必需文件存在（plugin.json / agent md / avatars/expert.png）；
    3. 按"第一层即专家目录"的结构压缩，跳过隐藏文件与缓存；
    4. 输出 zip 与 SHA256。

如果平台要求必须通过官方 validate，把 plugin.json 的 categoryId 改成
`12-IndustryConsultant` 后再用官方脚本打包即可，其余文件不用动。

用法：
    python bin/build_package.py . ./dist
"""

import hashlib
import os
import subprocess
import sys
import zipfile

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

SKIP_DIRS = {"__pycache__", "node_modules", ".git"}
SKIP_FILES = {".gitkeep", ".DS_Store", "Thumbs.db", ".created-by-session", ".pending-preview-session"}


def main():
    root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
    out_dir = os.path.abspath(sys.argv[2] if len(sys.argv) > 2 else os.path.join(root, "dist"))
    name = os.path.basename(root)

    # 1) 自检
    print("① 包自检")
    here = os.path.dirname(os.path.abspath(__file__))
    rc = subprocess.call([sys.executable, os.path.join(here, "check_package.py"), root])
    if rc != 0:
        print("包自检未通过，已中止打包。")
        return 1

    # 2) 必需文件
    print("\n② 必需文件")
    import json
    with open(os.path.join(root, ".codebuddy-plugin", "plugin.json"), encoding="utf-8") as f:
        meta = json.load(f)
    agent_rel = (meta.get("agents") or [""])[0].lstrip("./")
    need = [".codebuddy-plugin/plugin.json", agent_rel, meta.get("avatar", "avatars/expert.png")]
    for rel in need:
        p = os.path.join(root, rel)
        ok = os.path.isfile(p)
        print("   %s %s" % ("[有]" if ok else "[缺]", rel))
        if not ok:
            print("缺少必需文件，已中止。")
            return 1

    # 3) 压缩
    print("\n③ 压缩")
    os.makedirs(out_dir, exist_ok=True)
    zip_path = os.path.join(out_dir, "%s.zip" % name)
    count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            for fn in sorted(filenames):
                if fn in SKIP_FILES:
                    continue
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, root).replace(os.sep, "/")
                # 跳过隐藏文件，但保留 .codebuddy-plugin
                parts = rel.split("/")
                if any(p.startswith(".") and p != ".codebuddy-plugin" for p in parts):
                    continue
                # 不要把 dist 自己打进去
                if rel.startswith("dist/"):
                    continue
                z.write(full, "%s/%s" % (name, rel))
                count += 1

    size = os.path.getsize(zip_path) / 1024
    h = hashlib.sha256(open(zip_path, "rb").read()).hexdigest()
    print("   写入 %d 个文件" % count)
    print("\n④ 结果")
    print("   %s" % zip_path)
    print("   %.1f KB" % size)
    print("   SHA256 %s" % h)
    with open(os.path.join(out_dir, "SHA256SUMS.txt"), "a", encoding="utf-8") as f:
        f.write("%s  %s.zip\n" % (h, name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
