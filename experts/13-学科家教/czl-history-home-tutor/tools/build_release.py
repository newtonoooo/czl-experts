#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键出包：校验 -> 头像体检 -> 打 zip -> 回读 zip 逐项验收。

为什么要"回读验收"
------------------
专家包最常见的两类翻车都不在源目录里，而在 zip 里：
  A. zip 根下多了一个目录级（如 __MACOSX、或者把父目录一起打进去），
     客户端的 resolveSingleTopLevelDir 会判成 invalid_package 或装成错层。
  B. 头像没进包（目录是空的、被过滤规则跳过），导入后小图标变成名字首字。

所以打包不是"压完就算"，必须重新打开 zip，按客户端真正读取的路径再查一遍。

用法:
    python tools/build_release.py . [输出目录]
退出码: 0 成功；1 校验或验收失败。
"""

import hashlib
import subprocess
import sys
import zipfile
from pathlib import Path

SKIP_DIRS = {"__pycache__", "node_modules", ".git", ".idea"}
SKIP_FILES = {".DS_Store", "Thumbs.db", ".gitkeep", ".downloaded_at"}


def run(cmd, cwd):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    print(r.stdout.rstrip())
    if r.returncode != 0:
        if r.stderr.strip():
            print(r.stderr.rstrip())
        raise SystemExit(1)


def collect(root):
    files = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        parts = set(p.relative_to(root).parts)
        if parts & SKIP_DIRS or p.name in SKIP_FILES:
            continue
        if any(part.startswith(".") and part != ".codebuddy-plugin" for part in parts):
            continue
        if p.suffix in {".pyc", ".zip"}:
            continue
        files.append(p)
    return files


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    out_dir = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else root.parent.parent / "dist"
    out_dir.mkdir(parents=True, exist_ok=True)

    py = sys.executable
    print("=" * 60)
    print("步骤 1/4 结构校验")
    print("=" * 60)
    run([py, "tools/validate_package.py", "."], root)

    print("\n" + "=" * 60)
    print("步骤 2/4 头像体检")
    print("=" * 60)
    run([py, "tools/verify_avatar.py", "."], root)

    print("\n" + "=" * 60)
    print("步骤 3/4 打包")
    print("=" * 60)
    files = collect(root)
    zip_path = out_dir / f"{root.name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for f in files:
            arc = f"{root.name}/{f.relative_to(root).as_posix()}"
            zf.write(f, arc)
    size_kb = zip_path.stat().st_size / 1024
    print(f"   写入 {len(files)} 个文件 -> {zip_path}")
    print(f"   体积 {size_kb:.1f} KB")

    print("\n" + "=" * 60)
    print("步骤 4/4 回读验收（按客户端读取路径）")
    print("=" * 60)
    problems = []
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        tops = {n.split("/")[0] for n in names}
        if tops != {root.name}:
            problems.append(f"zip 根下应只有一个目录 {root.name}，实际 {sorted(tops)}")

        manifest = f"{root.name}/.codebuddy-plugin/plugin.json"
        if manifest not in names:
            problems.append("zip 里找不到 .codebuddy-plugin/plugin.json")

        # 头像：从 manifest 里读出来，按包根解析，确认 zip 内确实存在同名条目
        avatar_name, avatar_bytes = None, 0
        import json
        if manifest in names:
            data = json.loads(zf.read(manifest).decode("utf-8"))
            avatar_name = data.get("avatar", "")
            if avatar_name and not avatar_name.startswith(("http://", "https://", "data:")):
                entry = f"{root.name}/{avatar_name.lstrip('./')}"
                if entry not in names:
                    problems.append(f"zip 里缺少头像条目：{entry}（导入后会变成名字首字）")
                else:
                    avatar_bytes = len(zf.read(entry))
                    if avatar_bytes > 500 * 1024:
                        problems.append(f"zip 内头像 {avatar_bytes/1024:.0f}KB 超过 500KB")

        for need in ("agents", "skills"):
            if not any(n.startswith(f"{root.name}/{need}/") for n in names):
                problems.append(f"zip 里缺少 {need}/ 目录")

        bad = [n for n in names if "__pycache__" in n or n.endswith(".pyc")]
        if bad:
            problems.append(f"zip 里混入了缓存文件：{bad[:3]}")

    print(f"   条目总数：{len(names)}")
    print(f"   顶层目录：{sorted(tops)}")
    print(f"   头像条目：{avatar_name}（{avatar_bytes/1024:.1f}KB）")
    print(f"   含 skills/ 与 agents/：{'是' if not problems else '见下'}")
    for p in problems:
        print(f"   ❌ {p}")
    if problems:
        print("\n结论：验收未通过，不要上传这个 zip。")
        return 1

    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    print(f"\n   SHA256：{digest}")
    print(f"\n✅ 出包完成：{zip_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
