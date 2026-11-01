#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""prepare_avatar.py —— 头像规格化工具（开发者用，需要 Pillow，可不装）。

作用：把任意尺寸的图片裁成正方形、缩到 512×512、压到 500KB 以内，
     并去掉可能存在的边角水印区。

注意：本脚本是**打包前的准备工具**，不是老师日常使用的功能，
     所以允许依赖 Pillow。其余 bin/ 脚本一律零依赖。

用法：
    python bin/prepare_avatar.py 原图.png -o avatars/expert.png
    python bin/prepare_avatar.py 原图.png -o avatars/expert.png --trim 70
    python bin/prepare_avatar.py 原图.png -o avatars/expert.png --trim 70 --colors 256

参数：
    --trim N     从四边各裁掉 N 像素（用于去水印），默认 0
    --colors N   量化到 N 色以压体积（不填则不量化，保持真彩色）
    --size N     输出边长，默认 512

退出码：0 成功；2 缺 Pillow；1 其他错误。
"""

import argparse
import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    from PIL import Image
except ImportError:
    print("本脚本需要 Pillow。安装：python -m pip install pillow")
    print("（其余 bin/ 脚本不需要 Pillow，纯标准库即可运行。）")
    sys.exit(2)


def main():
    ap = argparse.ArgumentParser(description="头像规格化：裁方、缩放、压体积")
    ap.add_argument("src")
    ap.add_argument("-o", "--out", default="avatars/expert.png")
    ap.add_argument("--trim", type=int, default=0, help="四边各裁掉的像素")
    ap.add_argument("--colors", type=int, default=0, help="量化为 N 色，0 表示不量化")
    ap.add_argument("--size", type=int, default=512)
    args = ap.parse_args()

    if not os.path.isfile(args.src):
        raise SystemExit("错误：找不到 %s" % args.src)

    im = Image.open(args.src).convert("RGB")
    w, h = im.size

    if args.trim:
        t = args.trim
        if 2 * t >= min(w, h):
            raise SystemExit("错误：--trim 太大")
        im = im.crop((t, t, w - t, h - t))
        w, h = im.size

    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    im = im.crop((left, top, left + side, top + side))
    im = im.resize((args.size, args.size), Image.LANCZOS)

    if args.colors and args.colors >= 8:
        im = im.quantize(colors=args.colors, method=Image.MEDIANCUT,
                         dither=Image.FLOYDSTEINBERG)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    im.save(args.out, optimize=True)

    size = os.path.getsize(args.out)
    print("已生成：%s（%d×%d，%.1f KB）" % (args.out, args.size, args.size, size / 1024))
    if size > 500 * 1024:
        print("⚠️ 超过 500KB，建议加 --colors 256 再压一次")
    else:
        print("✅ 体积合规（≤500KB）")


if __name__ == "__main__":
    main()
