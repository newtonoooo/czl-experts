#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""头像规范化：纯标准库实现的 PNG 裁切 / 缩放 / 方图输出。

为什么不用 Pillow：发布环境不一定装得上第三方库，而头像处理只需要
"裁一块、缩到 512"。这里直接读写 PNG（8 位、非隔行），零依赖。

用法：
    python tools/avatar_norm.py <输入.png> <输出.png> --size 512
    python tools/avatar_norm.py in.png out.png --crop 40,0,944,944
    python tools/avatar_norm.py in.png out.png --trim 56   # 四周各裁 56px 去水印

支持 colortype 0/2/4/6（灰度、RGB、灰度+Alpha、RGBA），位深 8。
"""

import argparse
import struct
import sys
import zlib
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PNG_SIG = b"\x89PNG\r\n\x1a\n"


def read_png(path):
    data = Path(path).read_bytes()
    if data[:8] != PNG_SIG:
        raise ValueError("不是 PNG 文件")
    pos = 8
    header = None
    idat = bytearray()
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        ctype = data[pos + 4 : pos + 8]
        chunk = data[pos + 8 : pos + 8 + length]
        if ctype == b"IHDR":
            w, h, depth, color, comp, filt, inter = struct.unpack(">IIBBBBB", chunk)
            header = (w, h, depth, color, inter)
        elif ctype == b"IDAT":
            idat += chunk
        elif ctype == b"IEND":
            break
        pos += 12 + length
    if not header:
        raise ValueError("缺 IHDR")
    w, h, depth, color, inter = header
    if depth != 8 or inter != 0:
        raise ValueError(f"仅支持 8 位非隔行 PNG，当前 depth={depth} interlace={inter}")
    channels = {0: 1, 2: 3, 4: 2, 6: 4}[color]
    raw = zlib.decompress(bytes(idat))
    stride = w * channels
    out = bytearray(h * stride)
    prev = bytearray(stride)
    pos = 0
    for y in range(h):
        ftype = raw[pos]
        pos += 1
        line = bytearray(raw[pos : pos + stride])
        pos += stride
        if ftype == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif ftype == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ftype == 3:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                b = prev[i]
                c = prev[i - channels] if i >= channels else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        elif ftype != 0:
            raise ValueError(f"未知行过滤器 {ftype}")
        out[y * stride : (y + 1) * stride] = line
        prev = line
    return w, h, channels, bytes(out)


def write_png(path, w, h, channels, pixels):
    color = {1: 0, 3: 2, 2: 4, 4: 6}[channels]
    stride = w * channels
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw += pixels[y * stride : (y + 1) * stride]

    def chunk(tag, payload):
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", w, h, 8, color, 0, 0, 0)
    data = PNG_SIG + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")
    Path(path).write_bytes(data)


def crop(w, h, channels, pixels, box):
    x0, y0, x1, y1 = box
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(w, x1), min(h, y1)
    if x1 <= x0 or y1 <= y0:
        raise ValueError("裁切区域无效")
    stride = w * channels
    cw, ch = x1 - x0, y1 - y0
    out = bytearray(cw * ch * channels)
    for y in range(ch):
        src = (y0 + y) * stride + x0 * channels
        out[y * cw * channels : (y + 1) * cw * channels] = pixels[src : src + cw * channels]
    return cw, ch, bytes(out)


def resize(w, h, channels, pixels, size):
    """双线性缩放，用于头像这种中小尺寸足够。"""
    out = bytearray(size * size * channels)
    sw = size / w
    sh = size / h
    stride = w * channels
    for y in range(size):
        fy = (y + 0.5) / sh - 0.5
        y0 = int(max(0, min(h - 1, fy)))
        y1 = min(h - 1, y0 + 1)
        wy = max(0.0, min(1.0, fy - y0))
        for x in range(size):
            fx = (x + 0.5) / sw - 0.5
            x0 = int(max(0, min(w - 1, fx)))
            x1 = min(w - 1, x0 + 1)
            wx = max(0.0, min(1.0, fx - x0))
            base = (y * size + x) * channels
            for c in range(channels):
                p00 = pixels[y0 * stride + x0 * channels + c]
                p10 = pixels[y0 * stride + x1 * channels + c]
                p01 = pixels[y1 * stride + x0 * channels + c]
                p11 = pixels[y1 * stride + x1 * channels + c]
                top = p00 + (p10 - p00) * wx
                bot = p01 + (p11 - p01) * wx
                out[base + c] = int(round(top + (bot - top) * wy))
    return size, size, bytes(out)


def main():
    ap = argparse.ArgumentParser(description="PNG 头像裁切与缩放（零依赖）")
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--crop", help="x0,y0,x1,y1")
    ap.add_argument("--trim", type=int, help="四周各裁掉多少像素，用于去角标")
    args = ap.parse_args()

    w, h, ch, px = read_png(args.src)
    print(f"读入：{w}×{h}，{ch} 通道")

    box = (0, 0, w, h)
    if args.crop:
        box = tuple(int(v) for v in args.crop.split(","))
    elif args.trim:
        t = args.trim
        box = (t, t, w - t, h - t)

    w, h, px = crop(w, h, ch, px, box)
    print(f"裁切：{box} → {w}×{h}")

    w, h, px = resize(w, h, ch, px, args.size)
    write_png(args.dst, w, h, ch, px)
    print(f"写出：{args.dst}（{w}×{h}，{Path(args.dst).stat().st_size/1024:.0f} KB）")


if __name__ == "__main__":
    sys.exit(main())
