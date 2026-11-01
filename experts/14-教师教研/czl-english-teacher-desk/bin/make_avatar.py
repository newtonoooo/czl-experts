#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_avatar.py — 纯标准库 PNG 裁剪与缩放（构建头像用）

用途：把生成的 1024×1024 头像裁成正方形、缩放到 512×512，输出无依赖的 PNG。
不依赖 Pillow / ImageMagick；仅用 zlib + struct。

用法：
    python bin/make_avatar.py --src avatars/raw.png --out avatars/expert.png \
        --crop-bottom 124 --size 512

参数：
    --crop-bottom 从底部裁掉的像素数（用于避开生成图右下角的平台水印带）
    --crop-side   从左右各裁掉的像素数（默认自动按正方形计算）
    --size        输出边长，默认 512
"""
import argparse
import struct
import sys
import zlib
from pathlib import Path


def read_png(path):
    data = Path(path).read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("不是 PNG 文件")
    pos = 8
    idat = b""
    width = height = depth = ctype = interlace = None
    palette = None
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        ctype_chunk = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if ctype_chunk == b"IHDR":
            width, height, depth, ctype, _comp, _filt, interlace = struct.unpack(">IIBBBBB", chunk)
        elif ctype_chunk == b"PLTE":
            palette = chunk
        elif ctype_chunk == b"IDAT":
            idat += chunk
        elif ctype_chunk == b"IEND":
            break
    if depth != 8:
        raise ValueError(f"仅支持 8 位色深，当前 {depth}")
    if interlace != 0:
        raise ValueError("不支持隔行扫描 PNG")
    if ctype not in (0, 2, 3, 4, 6):
        raise ValueError(f"不支持的颜色类型 {ctype}")

    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    raw = zlib.decompress(idat)
    stride = width * channels
    out = bytearray(width * height * 3)
    prev = bytearray(stride)
    p = 0
    for y in range(height):
        f = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if f == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif f == 3:
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif f == 4:
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                b = prev[i]
                c = prev[i - channels] if i >= channels else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        elif f != 0:
            raise ValueError(f"未知过滤类型 {f}")

        base = y * width * 3
        if ctype == 2:
            out[base:base + width * 3] = line
        elif ctype == 6:
            for x in range(width):
                i = x * 4
                out[base + x * 3: base + x * 3 + 3] = line[i:i + 3]
        elif ctype == 0:
            for x in range(width):
                v = line[x]
                out[base + x * 3: base + x * 3 + 3] = bytes((v, v, v))
        elif ctype == 4:
            for x in range(width):
                v = line[x * 2]
                out[base + x * 3: base + x * 3 + 3] = bytes((v, v, v))
        elif ctype == 3:
            if palette is None:
                raise ValueError("调色板 PNG 缺少 PLTE")
            for x in range(width):
                idx = line[x] * 3
                out[base + x * 3: base + x * 3 + 3] = palette[idx:idx + 3]
        prev = line
    return width, height, out


def crop_square(width, height, rgb, crop_bottom, crop_side=None):
    h2 = height - crop_bottom
    if crop_side is None:
        side = min(width, h2)
    else:
        side = min(width - 2 * crop_side, h2)
    x0 = (width - side) // 2
    y0 = 0
    out = bytearray(side * side * 3)
    for y in range(side):
        src = ((y0 + y) * width + x0) * 3
        out[y * side * 3:(y + 1) * side * 3] = rgb[src:src + side * 3]
    return side, out


def box_resize(side, rgb, size):
    out = bytearray(size * size * 3)
    scale = side / size
    for dy in range(size):
        sy0 = int(dy * scale)
        sy1 = max(sy0 + 1, int((dy + 1) * scale))
        for dx in range(size):
            sx0 = int(dx * scale)
            sx1 = max(sx0 + 1, int((dx + 1) * scale))
            r = g = b = n = 0
            for sy in range(sy0, sy1):
                row = sy * side * 3
                for sx in range(sx0, sx1):
                    i = row + sx * 3
                    r += rgb[i]
                    g += rgb[i + 1]
                    b += rgb[i + 2]
                    n += 1
            o = (dy * size + dx) * 3
            out[o] = r // n
            out[o + 1] = g // n
            out[o + 2] = b // n
    return out


def write_png(path, size, rgb):
    raw = bytearray()
    stride = size * 3
    for y in range(size):
        raw.append(0)
        raw += rgb[y * stride:(y + 1) * stride]

    def chunk(tag, payload):
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))
    Path(path).write_bytes(png)


def main(argv=None):
    ap = argparse.ArgumentParser(description="PNG 裁剪与缩放（无第三方依赖）")
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--crop-bottom", type=int, default=0)
    ap.add_argument("--crop-side", type=int, default=None)
    ap.add_argument("--size", type=int, default=512)
    args = ap.parse_args(argv)

    try:
        w, h, rgb = read_png(args.src)
        side, cropped = crop_square(w, h, rgb, args.crop_bottom, args.crop_side)
        resized = box_resize(side, cropped, args.size)
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        write_png(args.out, args.size, resized)
    except (OSError, ValueError) as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1

    kb = Path(args.out).stat().st_size / 1024
    print(f"[OK] {args.src} ({w}x{h}) -> 裁剪 {side}x{side} -> {args.out} ({args.size}x{args.size}, {kb:.1f} KB)")
    if kb > 500:
        print("[WARN] 超过 500 KB 建议压缩或改用 JPG")
    return 0


if __name__ == "__main__":
    sys.exit(main())
