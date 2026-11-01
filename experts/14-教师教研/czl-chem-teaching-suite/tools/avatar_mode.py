#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""卓识化学 · 头像模式切换

两种模式：
  relative  相对路径 avatars/expert-512.png —— **提交市场上架必须用这个**（平台只认 png/jpg/webp 扩展名）
  embed     内嵌 data URL —— 仅供本地导入测试（私有包在部分渲染路径下更容易显示）

用法：
    python tools/avatar_mode.py --status
    python tools/avatar_mode.py --mode relative
    python tools/avatar_mode.py --mode embed
"""

from __future__ import annotations

import base64
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, ".codebuddy-plugin", "plugin.json")
EMBED_SRC = os.path.join(ROOT, "avatars", "expert-256.png")
RELATIVE_VAL = "avatars/expert-512.png"


def load() -> dict:
    with open(MANIFEST, encoding="utf-8") as f:
        return json.load(f)


def save(m: dict) -> None:
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=2)


def main() -> int:
    mode = None
    for i, a in enumerate(sys.argv):
        if a == "--mode" and i + 1 < len(sys.argv):
            mode = sys.argv[i + 1]
        elif a.startswith("--mode="):
            mode = a.split("=", 1)[1]

    m = load()
    cur = m.get("avatar", "")
    is_embed = str(cur).startswith("data:image/")

    if mode is None or "--status" in sys.argv:
        print(f"当前模式：{'embed（内嵌 data URL）' if is_embed else 'relative（相对路径）'}")
        print(f"avatar 长度：{len(str(cur))} 字符")
        print(f"清单体积：{os.path.getsize(MANIFEST)/1024:.1f} KB")
        return 0

    if mode == "embed":
        if not os.path.isfile(EMBED_SRC):
            print(f"缺少头像源文件：{EMBED_SRC}")
            return 2
        with open(EMBED_SRC, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        m["avatar"] = "data:image/png;base64," + b64
        save(m)
        print(f"已切换为 embed：{os.path.getsize(EMBED_SRC)/1024:.1f} KB 图片 → 清单 {os.path.getsize(MANIFEST)/1024:.1f} KB")
        print("用途：本地导入测试（私有包在部分渲染路径下更容易显示图标）。")
        print("注意：embed 形态提交市场会被判为『（无扩展名）』，上架前务必切回 relative。")
        return 0

    if mode == "relative":
        if not os.path.isfile(os.path.join(ROOT, RELATIVE_VAL)):
            print(f"缺少头像文件：{RELATIVE_VAL}")
            return 2
        m["avatar"] = RELATIVE_VAL
        save(m)
        print(f"已切换为 relative：{RELATIVE_VAL}；清单 {os.path.getsize(MANIFEST)/1024:.1f} KB")
        print("符合市场上架校验：扩展名 .png，文件随包分发。")
        print("本地导入若显示为文字，可用 --mode embed 临时规避；提交前记得切回。")
        return 0

    print(f"未知模式：{mode}（可用 embed / relative / --status）")
    return 2


if __name__ == "__main__":
    sys.exit(main())
