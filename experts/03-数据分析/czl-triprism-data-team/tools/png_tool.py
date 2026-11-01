# -*- coding: utf-8 -*-
"""三棱镜 · PNG 处理工具（纯标准库）

用途：把生成的头像裁掉边缘水印、缩放成平台要求的正方形尺寸。
只支持 8 位、非隔行的 RGB / RGBA PNG——足够处理本项目的视觉资源。

用法：
  python png_tool.py --src raw.png --dst avatars/lead.png --size 512 \
      --crop-right 110 --crop-bottom 110
"""

from __future__ import annotations

import argparse
import struct
import zlib

SIG = b"\x89PNG\r\n\x1a\n"


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def decode(path):
    with open(path, "rb") as fh:
        data = fh.read()
    if not data.startswith(SIG):
        raise ValueError("不是 PNG 文件")
    pos = 8
    idat = bytearray()
    w = h = depth = ctype = interlace = None
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        ctag = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if ctag == b"IHDR":
            w, h, depth, ctype, _comp, _filt, interlace = struct.unpack(">IIBBBBB", chunk)
        elif ctag == b"IDAT":
            idat += chunk
        elif ctag == b"IEND":
            break
    if depth != 8:
        raise ValueError(f"仅支持 8 位色深，当前 {depth}")
    if ctype not in (2, 6):
        raise ValueError(f"仅支持 RGB/RGBA，当前 color type {ctype}")
    if interlace:
        raise ValueError("不支持隔行扫描 PNG")
    ch = 3 if ctype == 2 else 4
    raw = zlib.decompress(bytes(idat))
    stride = w * ch
    out = bytearray(h * stride)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        ft = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if ft == 1:
            for i in range(ch, stride):
                line[i] = (line[i] + line[i - ch]) & 0xFF
        elif ft == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ft == 3:
            for i in range(stride):
                left = line[i - ch] if i >= ch else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ft == 4:
            for i in range(stride):
                left = line[i - ch] if i >= ch else 0
                ul = prev[i - ch] if i >= ch else 0
                line[i] = (line[i] + _paeth(left, prev[i], ul)) & 0xFF
        elif ft != 0:
            raise ValueError(f"未知过滤器类型 {ft}")
        out[y * stride:(y + 1) * stride] = line
        prev = line
    return w, h, ch, out


def encode(path, w, h, ch, pixels):
    ctype = 2 if ch == 3 else 6
    stride = w * ch
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw += pixels[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, payload):
        return (struct.pack(">I", len(payload)) + tag + payload +
                struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", w, h, 8, ctype, 0, 0, 0)
    with open(path, "wb") as fh:
        fh.write(SIG)
        fh.write(chunk(b"IHDR", ihdr))
        fh.write(chunk(b"IDAT", comp))
        fh.write(chunk(b"IEND", b""))
    return path


def crop(w, h, ch, pixels, left=0, top=0, right=0, bottom=0):
    nw, nh = w - left - right, h - top - bottom
    if nw <= 0 or nh <= 0:
        raise ValueError("裁剪参数超出图像范围")
    out = bytearray(nw * nh * ch)
    for y in range(nh):
        src = ((y + top) * w + left) * ch
        out[y * nw * ch:(y + 1) * nw * ch] = pixels[src:src + nw * ch]
    return nw, nh, ch, out


def resize(w, h, ch, pixels, nw, nh):
    """双线性插值缩放。"""
    out = bytearray(nw * nh * ch)
    x_ratio = (w - 1) / max(1, nw - 1) if nw > 1 else 0
    y_ratio = (h - 1) / max(1, nh - 1) if nh > 1 else 0
    for y in range(nh):
        sy = y * y_ratio
        y0 = int(sy)
        y1 = min(y0 + 1, h - 1)
        wy = sy - y0
        for x in range(nw):
            sx = x * x_ratio
            x0 = int(sx)
            x1 = min(x0 + 1, w - 1)
            wx = sx - x0
            i00 = (y0 * w + x0) * ch
            i01 = (y0 * w + x1) * ch
            i10 = (y1 * w + x0) * ch
            i11 = (y1 * w + x1) * ch
            base = (y * nw + x) * ch
            for c in range(ch):
                top_v = pixels[i00 + c] * (1 - wx) + pixels[i01 + c] * wx
                bot_v = pixels[i10 + c] * (1 - wx) + pixels[i11 + c] * wx
                out[base + c] = int(top_v * (1 - wy) + bot_v * wy + 0.5)
    return nw, nh, ch, out


def process(src, dst, size=None, crop_left=0, crop_top=0, crop_right=0, crop_bottom=0):
    w, h, ch, px = decode(src)
    if crop_left or crop_top or crop_right or crop_bottom:
        w, h, ch, px = crop(w, h, ch, px, crop_left, crop_top, crop_right, crop_bottom)
    if size:
        if w != h:
            side = min(w, h)
            w, h, ch, px = crop(w, h, ch, px, (w - side) // 2, (h - side) // 2,
                                (w - side) // 2, (h - side) // 2)
        w, h, ch, px = resize(w, h, ch, px, size, size)
    encode(dst, w, h, ch, px)
    return w, h


def main(argv=None):
    ap = argparse.ArgumentParser(description="PNG 裁剪与缩放")
    ap.add_argument("--src", required=True)
    ap.add_argument("--dst", required=True)
    ap.add_argument("--size", type=int, default=None)
    ap.add_argument("--crop-left", type=int, default=0)
    ap.add_argument("--crop-top", type=int, default=0)
    ap.add_argument("--crop-right", type=int, default=0)
    ap.add_argument("--crop-bottom", type=int, default=0)
    a = ap.parse_args(argv)
    w, h = process(a.src, a.dst, a.size, a.crop_left, a.crop_top, a.crop_right, a.crop_bottom)
    print(f"{a.dst}  {w}x{h}")


if __name__ == "__main__":
    main()
