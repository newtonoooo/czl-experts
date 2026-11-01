#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
embed_avatar.py — 生成「头像内联版」专家清单

解决什么问题：
    部分导入方式（例如只复制文本与配置文件的导入器）可能不会带走 avatars/
    目录下的二进制文件。头像文件缺失时，平台的解析逻辑会返回空字符串，
    列表里就退化成显示名称首字，看起来像"头像没了，成了一个字"。
    把图片直接以 data URI 内联进 plugin.json，可以不依赖任何外部文件。

用法：
    python scripts/embed_avatar.py                 # 生成 plugin.inline-avatar.json
    python scripts/embed_avatar.py --apply        # 直接覆盖 plugin.json（会先备份）
    python scripts/embed_avatar.py --max-kb 200   # 内联前压缩到指定大小（需 Pillow）

注意：
    - 内联后 plugin.json 体积会增大（约为图片大小的 1.37 倍），仍在平台可接受范围内。
    - 默认只生成旁路文件，不覆盖原文件，避免误操作。
"""

import argparse
import base64
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / ".codebuddy-plugin" / "plugin.json"


def human(n):
    return f"{n / 1024:.0f} KB"


def maybe_compress(path, max_kb):
    """可选：借助 Pillow 压到指定大小。没有 Pillow 就原样返回。"""
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        print(f"[提示] 未安装 Pillow，跳过压缩，直接内联 {human(path.stat().st_size)}")
        return path

    from PIL import Image

    target = max_kb * 1024
    if path.stat().st_size <= target:
        return path

    src = Image.open(path).convert("RGB")
    out = ROOT / "avatars" / "_inline_tmp.png"
    side = src.width
    while side >= 256:
        canvas = src.resize((side, side), Image.LANCZOS)
        canvas.save(out, format="PNG", optimize=True)
        if out.stat().st_size <= target:
            print(f"[提示] 已压缩到 {side}×{side}，{human(out.stat().st_size)}")
            return out
        side = int(side * 0.85)
    print(f"[警告] 压缩后仍超过 {max_kb} KB，使用最小尺寸版本")
    return out


def main():
    parser = argparse.ArgumentParser(description="生成头像内联版专家清单")
    parser.add_argument("--apply", action="store_true", help="直接写入 plugin.json（先备份）")
    parser.add_argument("--max-kb", type=int, default=0, help="内联前压缩目标（KB），0 表示不压缩")
    args = parser.parse_args()

    if not MANIFEST.is_file():
        print(f"[错误] 找不到 {MANIFEST}")
        return 1

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    avatar_rel = manifest.get("avatar", "")
    if not avatar_rel:
        print("[错误] plugin.json 中没有 avatar 字段")
        return 1
    if avatar_rel.startswith("data:"):
        print("[提示] 当前 avatar 已是内联格式，无需处理")
        return 0

    avatar_path = ROOT / avatar_rel
    if not avatar_path.is_file():
        print(f"[错误] 头像文件不存在：{avatar_rel}")
        return 1

    used = avatar_path
    if args.max_kb > 0:
        used = maybe_compress(avatar_path, args.max_kb)

    raw = used.read_bytes()
    mime = "image/png" if used.suffix.lower() == ".png" else "image/jpeg"
    data_uri = f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")

    out_manifest = dict(manifest)
    out_manifest["avatar"] = data_uri

    side_file = ROOT / ".codebuddy-plugin" / "plugin.inline-avatar.json"
    side_file.write_text(
        json.dumps(out_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"[完成] 已生成 {side_file.relative_to(ROOT)}")
    print(f"       图片 {human(raw.__len__())} → 清单 {human(side_file.stat().st_size)}")

    if args.apply:
        backup = ROOT / ".codebuddy-plugin" / "plugin.json.bak"
        shutil.copy2(MANIFEST, backup)
        MANIFEST.write_text(
            json.dumps(out_manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"[完成] 已覆盖 plugin.json，原文件备份为 {backup.name}")
    else:
        print("       如需直接启用：python scripts/embed_avatar.py --apply")

    if used != avatar_path and used.exists():
        used.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
