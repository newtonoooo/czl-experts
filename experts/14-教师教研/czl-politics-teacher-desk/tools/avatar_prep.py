#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""头像预处理（纯标准库，无第三方依赖）。

用途：把生成的头像裁掉边角水印、缩放到 512×512、控制体积在 500KB 以内。
需要 Pillow 时当然更省事，但本工具保证在没有 Pillow 的机器上也能跑。

用法:
    python tools/avatar_prep.py <输入.png> <输出.png> [--size 512] [--crop 42,0,940,940]
"""

import argparse
import struct
import sys
import zlib
from pathlib import Path


# ---------- 解码 ----------

def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def read_png(path):
    data = Path(path).read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("不是 PNG 文件")
    i, idat, w = 8, b"", None
    while i < len(data):
        ln = struct.unpack(">I", data[i:i + 4])[0]
        typ = data[i + 4:i + 8]
        payload = data[i + 8:i + 8 + ln]
        if typ == b"IHDR":
            w, h, bd, ct, comp, filt, inter = struct.unpack(">IIBBBBB", payload)
            if bd != 8 or inter != 0 or ct not in (2, 6):
                raise ValueError(f"仅支持 8 位非隔行的 RGB/RGBA PNG，当前 bd={bd} ct={ct} inter={inter}")
            bpp = 3 if ct == 2 else 4
        elif typ == b"IDAT":
            idat += payload
        elif typ == b"IEND":
            break
        i += 12 + ln

    raw = zlib.decompress(idat)
    stride = w * bpp
    rows, prev = [], bytearray(stride)
    pos = 0
    for _ in range(h):
        f = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
        if f == 1:
            for x in range(bpp, stride):
                line[x] = (line[x] + line[x - bpp]) & 0xFF
        elif f == 2:
            for x in range(stride):
                line[x] = (line[x] + prev[x]) & 0xFF
        elif f == 3:
            for x in range(stride):
                left = line[x - bpp] if x >= bpp else 0
                line[x] = (line[x] + ((left + prev[x]) >> 1)) & 0xFF
        elif f == 4:
            for x in range(stride):
                left = line[x - bpp] if x >= bpp else 0
                upleft = prev[x - bpp] if x >= bpp else 0
                line[x] = (line[x] + _paeth(left, prev[x], upleft)) & 0xFF
        rows.append(bytes(line))
        prev = line
    return w, h, bpp, rows


# ---------- 编码 ----------

def write_png(path, w, h, rows):
    def chunk(typ, payload):
        return (struct.pack(">I", len(payload)) + typ + payload +
                struct.pack(">I", zlib.crc32(typ + payload) & 0xFFFFFFFF))

    raw = b"".join(b"\x00" + r for r in rows)
    out = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9))
           + chunk(b"IEND", b""))
    Path(path).write_bytes(out)
    return len(out)


# ---------- 处理 ----------

def crop(rows, bpp, x0, y0, cw, ch):
    out = []
    for y in range(y0, y0 + ch):
        line = rows[y][x0 * bpp:(x0 + cw) * bpp]
        out.append(line)
    return out


def resize_box(rows, bpp, sw, sh, dw, dh):
    out = []
    xr = sw / dw
    yr = sh / dh
    for dy in range(dh):
        y0 = int(dy * yr)
        y1 = max(y0 + 1, int((dy + 1) * yr))
        line = bytearray(dw * 3)
        for dx in range(dw):
            x0 = int(dx * xr)
            x1 = max(x0 + 1, int((dx + 1) * xr))
            r = g = b = 0
            n = (y1 - y0) * (x1 - x0)
            for y in range(y0, y1):
                row = rows[y]
                for x in range(x0, x1):
                    p = x * bpp
                    r += row[p]
                    g += row[p + 1]
                    b += row[p + 2]
            q = dx * 3
            line[q] = r // n
            line[q + 1] = g // n
            line[q + 2] = b // n
        out.append(bytes(line))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--crop", default="", help="x0,y0,w,h，省略则整图缩放")
    args = ap.parse_args()

    w, h, bpp, rows = read_png(args.src)
    print(f"源图：{w}×{h}，{bpp} 通道")

    if args.crop:
        x0, y0, cw, ch = [int(v) for v in args.crop.split(",")]
        if cw != ch:
            raise SystemExit("裁剪区域必须是正方形")
        if x0 < 0 or y0 < 0 or x0 + cw > w or y0 + ch > h:
            raise SystemExit("裁剪区域超出图片范围")
        rows = crop(rows, bpp, x0, y0, cw, ch)
        w, h = cw, ch
        print(f"裁剪后：{w}×{h}")

    rows = resize_box(rows, bpp, w, h, args.size, args.size)
    n = write_png(args.dst, args.size, args.size, rows)
    print(f"输出：{args.dst}　{args.size}×{args.size}　{n / 1024:.1f} KB")


if __name__ == "__main__":
    sys.exit(main())
