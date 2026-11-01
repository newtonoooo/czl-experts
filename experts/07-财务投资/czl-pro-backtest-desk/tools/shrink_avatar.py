#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""shrink_avatar.py — 纯标准库 PNG 缩放/压缩（用于把生成图压到头像规格）

为什么不用 PIL：专家包要能在任何只装了 Python 的环境里自检，所以工具本身也不带第三方依赖。
支持：8bit 的灰度(0)/RGB(2)/调色板(3)/RGBA(6) PNG；面积平均重采样；输出始终为 RGB PNG。

用法：
    python tools/shrink_avatar.py in.png avatars/avatar.png --size 512 --max-kb 480
"""
import argparse
import os
import struct
import sys
import zlib


def read_png(path):
    data = open(path, "rb").read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("不是 PNG 文件：%s" % path)
    pos, idat, w = 8, [], None
    h = depth = ctype = None
    palette = None
    trns = None
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        ctype_chunk = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if ctype_chunk == b"IHDR":
            w, h, depth, ctype = struct.unpack(">IIBB", body[:10])
        elif ctype_chunk == b"PLTE":
            palette = body
        elif ctype_chunk == b"tRNS":
            trns = body
        elif ctype_chunk == b"IDAT":
            idat.append(body)
        elif ctype_chunk == b"IEND":
            break
    if depth != 8:
        raise ValueError("只支持 8bit PNG，实际 %s" % depth)
    if ctype not in (0, 2, 3, 6):
        raise ValueError("不支持的颜色类型 %s" % ctype)
    raw = zlib.decompress(b"".join(idat))
    ch = {0: 1, 2: 3, 3: 1, 6: 4}[ctype]
    stride = w * ch
    out = bytearray(h * stride)
    prev = bytearray(stride)
    pos = 0
    for y in range(h):
        f = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
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
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        elif f != 0:
            raise ValueError("未知的过滤类型 %s" % f)
        out[y * stride:(y + 1) * stride] = line
        prev = line

    # 统一转成 RGB
    rgb = bytearray(w * h * 3)
    for y in range(h):
        for x in range(w):
            i = y * stride + x * ch
            if ctype == 2:
                r, g, b = out[i], out[i + 1], out[i + 2]
            elif ctype == 6:
                r, g, b = out[i], out[i + 1], out[i + 2]
            elif ctype == 0:
                r = g = b = out[i]
            else:
                idx = out[i] * 3
                r, g, b = palette[idx], palette[idx + 1], palette[idx + 2]
            o = (y * w + x) * 3
            rgb[o], rgb[o + 1], rgb[o + 2] = r, g, b
    return w, h, rgb


def resize(w, h, rgb, tw, th):
    out = bytearray(tw * th * 3)
    for ty in range(th):
        y0 = ty * h / th
        y1 = (ty + 1) * h / th
        for tx in range(tw):
            x0 = tx * w / tw
            x1 = (tx + 1) * w / tw
            sr = sg = sb = 0.0
            area = 0.0
            for yy in range(int(y0), min(h, int(y1) + 1)):
                wy = min(y1, yy + 1) - max(y0, yy)
                if wy <= 0:
                    continue
                for xx in range(int(x0), min(w, int(x1) + 1)):
                    wx = min(x1, xx + 1) - max(x0, xx)
                    if wx <= 0:
                        continue
                    wt = wy * wx
                    o = (yy * w + xx) * 3
                    sr += rgb[o] * wt
                    sg += rgb[o + 1] * wt
                    sb += rgb[o + 2] * wt
                    area += wt
            o = (ty * tw + tx) * 3
            if area <= 0:
                out[o] = out[o + 1] = out[o + 2] = 255
            else:
                out[o] = int(sr / area + 0.5)
                out[o + 1] = int(sg / area + 0.5)
                out[o + 2] = int(sb / area + 0.5)
    return out


def write_png(path, w, h, rgb):
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw += rgb[y * w * 3:(y + 1) * w * 3]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, body):
        return (struct.pack(">I", len(body)) + tag + body +
                struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF))

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(png)
    return len(png)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--max-kb", type=int, default=480)
    ap.add_argument("--crop", default="", help="先裁剪：x,y,w,h（像素），再居中成正方形")
    args = ap.parse_args()

    w, h, rgb = read_png(args.src)
    if args.crop:
        cx, cy, cw, ch = [int(v) for v in args.crop.split(",")]
        cw, ch = min(cw, w - cx), min(ch, h - cy)
        cut = bytearray(cw * ch * 3)
        for y in range(ch):
            src0 = ((cy + y) * w + cx) * 3
            cut[y * cw * 3:(y + 1) * cw * 3] = rgb[src0:src0 + cw * 3]
        w, h, rgb = cw, ch, cut
    side = min(w, h)
    if w != h:  # 居中裁成正方形
        ox, oy = (w - side) // 2, (h - side) // 2
        sq = bytearray(side * side * 3)
        for y in range(side):
            src0 = ((oy + y) * w + ox) * 3
            sq[y * side * 3:(y + 1) * side * 3] = rgb[src0:src0 + side * 3]
        w, h, rgb = side, side, sq
    rgb2 = resize(w, h, rgb, args.size, args.size) if w != args.size else rgb
    size = write_png(args.dst, args.size, args.size, rgb2)
    print("源 %dx%d → 目标 %dx%d，写入 %s（%.1f KB）"
          % (w, h, args.size, args.size, args.dst, size / 1024.0))
    if size / 1024.0 > args.max_kb:
        print("⚠️ 超过 %d KB，考虑降尺寸或改进压缩" % args.max_kb)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
