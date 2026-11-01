#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""纯标准库 PNG 裁切/缩放工具（无第三方依赖）

用于把 ImageGen 生成的原始图处理成平台要求的 512x512 头像：
支持 8bit RGB / RGBA、非隔行 PNG 的解码与重新编码。

用法:
    python png_tool.py crop-resize <src> <dst> --crop x,y,w,h --size 512
    python png_tool.py info <src>
"""

import argparse
import struct
import sys
import zlib

PNG_SIG = b"\x89PNG\r\n\x1a\n"


def _read_chunks(data):
    if not data.startswith(PNG_SIG):
        raise ValueError("not a PNG file")
    off, out = 8, []
    while off < len(data):
        (length,) = struct.unpack(">I", data[off:off + 4])
        ctype = data[off + 4:off + 8]
        payload = data[off + 8:off + 8 + length]
        out.append((ctype, payload))
        off += 12 + length
    return out


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def decode(path):
    data = open(path, "rb").read()
    chunks = _read_chunks(data)
    ihdr = None
    idat = b""
    for ctype, payload in chunks:
        if ctype == b"IHDR":
            ihdr = payload
        elif ctype == b"IDAT":
            idat += payload
    if ihdr is None:
        raise ValueError("missing IHDR")
    w, h, bitdepth, colortype, comp, filt, interlace = struct.unpack(">IIBBBBB", ihdr)
    if bitdepth != 8 or comp != 0 or filt != 0 or interlace != 0:
        raise ValueError("unsupported PNG (need 8-bit, non-interlaced): depth=%d interlace=%d" % (bitdepth, interlace))
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(colortype)
    if channels is None or colortype == 3:
        raise ValueError("unsupported color type: %d" % colortype)

    raw = zlib.decompress(idat)
    stride = w * channels
    rows = []
    prev = bytearray(stride)
    pos = 0
    for _ in range(h):
        ftype = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
        if ftype == 0:
            pass
        elif ftype == 1:
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
                left = line[i - channels] if i >= channels else 0
                upleft = prev[i - channels] if i >= channels else 0
                line[i] = (line[i] + _paeth(left, prev[i], upleft)) & 0xFF
        else:
            raise ValueError("bad filter type %d" % ftype)
        rows.append(line)
        prev = line

    if channels == 4:
        pixels = [[(r[0], r[1], r[2], r[3]) for r in (row[i:i + 4] for i in range(0, stride, 4))] for row in rows]
    elif channels == 3:
        pixels = [[(r[0], r[1], r[2], 255) for r in (row[i:i + 3] for i in range(0, stride, 3))] for row in rows]
    elif channels == 2:
        pixels = [[(row[i], row[i], row[i], row[i + 1]) for i in range(0, stride, 2)] for row in rows]
    else:
        pixels = [[(row[i], row[i], row[i], 255) for i in range(stride)] for row in rows]
    return w, h, pixels


def encode_rgb(path, w, h, pixels):
    raw = bytearray()
    for row in pixels:
        raw.append(0)
        for px in row:
            raw.extend((px[0], px[1], px[2]))

    def chunk(ctype, payload):
        return (struct.pack(">I", len(payload)) + ctype + payload
                + struct.pack(">I", zlib.crc32(ctype + payload) & 0xFFFFFFFF))

    out = bytearray(PNG_SIG)
    out += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    out += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    out += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(bytes(out))


def crop(pixels, x, y, cw, ch):
    return [row[x:x + cw] for row in pixels[y:y + ch]]


def resize_box(pixels, sw, sh, dw, dh):
    """面积平均缩放（适合缩小）。"""
    out = []
    xr = sw / dw
    yr = sh / dh
    for dy in range(dh):
        y0, y1 = int(dy * yr), max(int(dy * yr) + 1, int((dy + 1) * yr))
        y1 = min(y1, sh)
        row_out = []
        for dx in range(dw):
            x0, x1 = int(dx * xr), max(int(dx * xr) + 1, int((dx + 1) * xr))
            x1 = min(x1, sw)
            r = g = b = n = 0
            for yy in range(y0, y1):
                prow = pixels[yy]
                for xx in range(x0, x1):
                    p = prow[xx]
                    r += p[0]; g += p[1]; b += p[2]; n += 1
            n = n or 1
            row_out.append((r // n, g // n, b // n, 255))
        out.append(row_out)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="纯标准库 PNG 裁切缩放")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_info = sub.add_parser("info")
    p_info.add_argument("src")

    p_cr = sub.add_parser("crop-resize")
    p_cr.add_argument("src")
    p_cr.add_argument("dst")
    p_cr.add_argument("--crop", default="", help="x,y,w,h；留空表示整图")
    p_cr.add_argument("--size", type=int, default=512)

    args = ap.parse_args(argv)

    if args.cmd == "info":
        w, h, _ = decode(args.src)
        import os
        print("size: %dx%d  bytes: %d" % (w, h, os.path.getsize(args.src)))
        return 0

    w, h, pixels = decode(args.src)
    if args.crop:
        x, y, cw, ch = [int(v) for v in args.crop.split(",")]
        cw, ch = min(cw, w - x), min(ch, h - y)
        pixels = crop(pixels, x, y, cw, ch)
        w, h = cw, ch
    out = resize_box(pixels, w, h, args.size, args.size)
    encode_rgb(args.dst, args.size, args.size, out)
    import os
    print("wrote %s  %dx%d  %d bytes" % (args.dst, args.size, args.size, os.path.getsize(args.dst)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
