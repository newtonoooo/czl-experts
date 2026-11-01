#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""纯标准库 PNG 处理：裁切补片 + 等比缩放，用于头像后期。

为什么自己写：本机没有 Pillow，装机环境不允许 pip 安装，也不能用 Add-Type 编译 .NET。
PNG 的 8 位 RGB/RGBA 解码与缩放用 zlib + struct 就够了，不值得为一张头像引依赖。

用法：
    python png_tool.py in.png --patch 870,900,1024,1024 --from 0,900,154,1024 --out tmp.png
    python png_tool.py tmp.png --resize 512 --out expert.png
    python png_tool.py in.png --info
"""

import argparse
import struct
import sys
import zlib
from pathlib import Path

SIG = b"\x89PNG\r\n\x1a\n"


def read_png(path):
    data = Path(path).read_bytes()
    if data[:8] != SIG:
        raise SystemExit(f"不是 PNG：{path}")
    pos = 8
    idat = b""
    plte = None
    trns = None
    w = h = depth = ctype = interlace = None
    while pos < len(data):
        (ln,) = struct.unpack(">I", data[pos:pos + 4])
        typ = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + ln]
        pos += 12 + ln
        if typ == b"IHDR":
            w, h, depth, ctype, _comp, _filt, interlace = struct.unpack(">IIBBBBB", body)
        elif typ == b"PLTE":
            plte = body
        elif typ == b"tRNS":
            trns = body
        elif typ == b"IDAT":
            idat += body
        elif typ == b"IEND":
            break
    if depth != 8:
        raise SystemExit(f"只支持 8 位深度，当前 {depth}")
    if interlace:
        raise SystemExit("不支持隔行扫描 PNG")
    if ctype not in (0, 2, 3, 4, 6):
        raise SystemExit(f"不支持的颜色类型 {ctype}")

    ch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    raw = zlib.decompress(idat)
    stride = w * ch
    out = bytearray(h * stride)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        f = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if f == 1:
            for i in range(ch, stride):
                line[i] = (line[i] + line[i - ch]) & 0xFF
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif f == 3:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif f == 4:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                b = prev[i]
                c = prev[i - ch] if i >= ch else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        elif f != 0:
            raise SystemExit(f"未知过滤类型 {f}")
        out[y * stride:(y + 1) * stride] = line
        prev = line

    # 统一转成 RGB / RGBA 便于后续处理
    if ctype == 3:
        if plte is None:
            raise SystemExit("调色板 PNG 缺 PLTE")
        rgb = bytearray(w * h * 3)
        for i in range(w * h):
            idx = out[i] * 3
            rgb[i * 3:i * 3 + 3] = plte[idx:idx + 3]
        out, ch = rgb, 3
    elif ctype == 0:
        rgb = bytearray(w * h * 3)
        for i in range(w * h):
            v = out[i]
            rgb[i * 3:i * 3 + 3] = bytes((v, v, v))
        out, ch = rgb, 3
    elif ctype == 4:
        rgba = bytearray(w * h * 4)
        for i in range(w * h):
            v = out[i * 2]
            rgba[i * 4:i * 4 + 4] = bytes((v, v, v, out[i * 2 + 1]))
        out, ch = rgba, 4
    return w, h, ch, out


def write_png(path, w, h, ch, buf):
    ctype = {3: 2, 4: 6, 1: 0}[ch]
    stride = w * ch
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw += buf[y * stride:(y + 1) * stride]
    def chunk(typ, body):
        return (struct.pack(">I", len(body)) + typ + body
                + struct.pack(">I", zlib.crc32(typ + body) & 0xFFFFFFFF))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, ctype, 0, 0, 0)
    png = SIG + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")
    Path(path).write_bytes(png)


def patch(w, h, ch, buf, dst, src):
    """把源矩形里的像素整块搬到目标矩形（同尺寸），用于清掉角落水印。"""
    dx, dy, dw, dh = dst
    sx, sy, sw, sh = src
    if (dw - dx) != (sw - sx) or (dh - dy) != (sh - sy):
        raise SystemExit("补片：源与目标尺寸必须一致")
    stride = w * ch
    for row in range(dh - dy):
        s = (sy + row) * stride + sx * ch
        d = (dy + row) * stride + dx * ch
        n = (dw - dx) * ch
        buf[d:d + n] = buf[s:s + n]


def crop(w, h, ch, buf, box):
    """裁切：返回新缓冲。"""
    x1, y1, x2, y2 = box
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    stride = w * ch
    nw, nh = x2 - x1, y2 - y1
    out = bytearray(nw * nh * ch)
    for y in range(nh):
        s = (y1 + y) * stride + x1 * ch
        out[y * nw * ch:(y + 1) * nw * ch] = buf[s:s + nw * ch]
    return nw, nh, out


def resize(w, h, ch, buf, nw, nh):
    """面积平均缩放（整数倍时等于箱式平均，边缘干净）。"""
    out = bytearray(nw * nh * ch)
    xr = w / nw
    yr = h / nh
    for y in range(nh):
        y0, y1 = int(y * yr), max(int(y * yr) + 1, int((y + 1) * yr))
        for x in range(nw):
            x0, x1 = int(x * xr), max(int(x * xr) + 1, int((x + 1) * xr))
            acc = [0] * ch
            n = 0
            for yy in range(y0, min(y1, h)):
                base = yy * w * ch
                for xx in range(x0, min(x1, w)):
                    o = base + xx * ch
                    for c in range(ch):
                        acc[c] += buf[o + c]
                    n += 1
            o = (y * nw + x) * ch
            for c in range(ch):
                out[o + c] = acc[c] // n
    return out


def rect(s):
    parts = [int(v) for v in s.split(",")]
    if len(parts) != 4:
        raise SystemExit("矩形格式：x1,y1,x2,y2")
    return tuple(parts)


def main():
    ap = argparse.ArgumentParser(description="PNG 补片与缩放")
    ap.add_argument("src")
    ap.add_argument("--info", action="store_true")
    ap.add_argument("--patch", default=None, help="目标矩形 x1,y1,x2,y2")
    ap.add_argument("--from-rect", dest="from_rect", default=None, help="源矩形 x1,y1,x2,y2")
    ap.add_argument("--crop", default=None, help="裁切矩形 x1,y1,x2,y2（在缩放之前执行）")
    ap.add_argument("--resize", type=int, default=None, help="目标边长（正方形）")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    w, h, ch, buf = read_png(args.src)
    print(f"读入 {args.src}: {w}x{h}, {ch} 通道")

    if args.info:
        return 0

    if args.patch:
        if not args.from_rect:
            raise SystemExit("--patch 需要同时给 --from-rect")
        patch(w, h, ch, buf, rect(args.patch), rect(args.from_rect))
        print(f"补片完成：{args.from_rect} → {args.patch}")

    if args.crop:
        w, h, buf = crop(w, h, ch, buf, rect(args.crop))
        print(f"裁切到 {w}x{h}")

    if args.resize:
        buf = resize(w, h, ch, buf, args.resize, args.resize)
        print(f"缩放到 {args.resize}x{args.resize}")
        w = h = args.resize

    if not args.out:
        raise SystemExit("需要 --out")
    write_png(args.out, w, h, ch, buf)
    size = Path(args.out).stat().st_size
    print(f"写出 {args.out}: {w}x{h}, {size / 1024:.1f}KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
