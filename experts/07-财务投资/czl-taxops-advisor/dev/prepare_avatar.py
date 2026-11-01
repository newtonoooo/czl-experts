#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
头像后处理脚本（本项目原创资产的处理链路，可选执行）

输入：AI 生成的原图（dev/avatar-raw/*.png，1024x1024）
处理：
  1. 用背景色覆盖右下角平台水印区域
  2. 居中裁切为正方形（保留徽章完整 + 少量留白）
  3. 等比缩放至 512x512 并输出 PNG
输出：avatars/avatar-512.png

依赖：Pillow（仅处理图片时需要，专家运行时不依赖）
用法：python dev/prepare_avatar.py <原图路径>
"""

import os
import sys

from PIL import Image, ImageDraw

CANVAS = 512
CROP = 880          # 居中裁切边长
WM_BOX = (850, 895, 1024, 1024)   # 水印区域，稍微放大留余量


def main(src):
    img = Image.open(src).convert("RGB")
    w, h = img.size

    bg = img.getpixel((4, 4))
    draw = ImageDraw.Draw(img)
    draw.rectangle(WM_BOX, fill=bg)

    left = (w - CROP) // 2
    top = (h - CROP) // 2
    img = img.crop((left, top, left + CROP, top + CROP))
    img = img.resize((CANVAS, CANVAS), Image.LANCZOS)

    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "avatars")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "avatar-512.png")
    img.save(out, "PNG", optimize=True)

    print("source :", src)
    print("bg     :", bg)
    print("crop   :", CROP, "@", (left, top))
    print("output :", out, img.size, os.path.getsize(out), "bytes")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python dev/prepare_avatar.py <raw.png>")
        raise SystemExit(1)
    main(sys.argv[1])
