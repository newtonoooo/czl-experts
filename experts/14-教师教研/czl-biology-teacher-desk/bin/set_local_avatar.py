#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""set_local_avatar.py — 让本地导入的专家也能显示头像（离线应急方案）

背景：
    WorkBuddy 渲染专家头像时，若 plugin.json 的 avatar 是相对路径（如 avatars/expert.png），
    会把它拼接成平台 CDN 地址（.../workbuddy/custom-expert/avatars/expert.png）。
    本地导入的专家包没有上传过该资源，CDN 上取不到文件，界面就回落成"首字色块"。
    渲染层对 data:image/... 的写法是直接透传的，因此把头像内嵌成 data URI 可以让本机立刻显示图标。

用法：
    python set_local_avatar.py --expert-dir .              # 内嵌 192px 头像（默认）
    python set_local_avatar.py --expert-dir . --size 256
    python set_local_avatar.py --expert-dir . --restore    # 还原成相对路径

说明：
    - 该方案只解决"本机看得见图标"，不改变上架流程。正式上架请用相对路径版本，由平台上传资源。
    - 内嵌后 plugin.json 会变大（约 20–60 KB），不影响功能。
"""

import argparse
import base64
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_REL = "avatars/expert.png"


def load_manifest(expert_dir: str):
    for meta in (".codebuddy-plugin", ".workbuddy-plugin"):
        p = os.path.join(expert_dir, meta, "plugin.json")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as fh:
                return p, json.load(fh)
    raise FileNotFoundError("未找到 .codebuddy-plugin/plugin.json 或 .workbuddy-plugin/plugin.json")


def make_data_uri(png_path: str, size: int) -> str:
    """用同目录的 image_square.py 生成指定尺寸的小图，再转 base64。"""
    sys.path.insert(0, HERE)
    from image_square import decode, crop, resize, encode  # noqa: E402

    with open(png_path, "rb") as fh:
        raw = fh.read()
    w, h, ch, color, rows = decode(raw)
    side = min(w, h)
    box = ((w - side) // 2, (h - side) // 2, side, side)
    cw, chh, cropped = crop(rows, w, h, ch, box)
    resized = resize(cropped, cw, chh, ch, size)
    data = encode(size, size, color, resized, 6)
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="把专家头像内嵌为 data URI（仅用于本机显示）")
    ap.add_argument("--expert-dir", default=".", help="专家目录")
    ap.add_argument("--size", type=int, default=192, help="内嵌图像边长，默认 192")
    ap.add_argument("--restore", action="store_true", help="还原为相对路径")
    args = ap.parse_args(argv)

    try:
        path, data = load_manifest(args.expert_dir)
    except Exception as exc:  # noqa: BLE001
        print(f"[错误] {exc}", file=sys.stderr)
        return 2

    if args.restore:
        data["avatar"] = DEFAULT_REL
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        print(f"已还原 avatar = {DEFAULT_REL}")
        return 0

    rel = data.get("avatar", DEFAULT_REL)
    if rel.startswith("data:"):
        print("当前已是内嵌头像，无需重复处理。如需还原请加 --restore")
        return 0
    png = os.path.join(args.expert_dir, rel)
    if not os.path.exists(png):
        print(f"[错误] 找不到头像文件: {png}", file=sys.stderr)
        return 2

    backup = os.path.join(os.path.dirname(path), ".plugin.json.orig")
    if not os.path.exists(backup):
        shutil.copy2(path, backup)
    data["avatar"] = make_data_uri(png, args.size)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    print(f"已内嵌 {args.size}px 头像到 {os.path.basename(path)}（原文件备份为同目录的 .plugin.json.orig，打包时会被自动忽略）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
