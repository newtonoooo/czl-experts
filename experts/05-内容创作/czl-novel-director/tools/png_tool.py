#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""png_tool.py — 纯标准库 PNG 裁剪、缩放、重编码

用途：把生成图处理成平台要求的头像规格（512×512、RGB、体积受控），
      并裁掉生成工具加在右下角的角标。

支持：位深 8、非隔行、色彩类型 2(RGB) / 6(RGBA) / 0(灰度)。
不支持：位深 16、隔行、调色板（遇到直接报错，不静默降级）。

用法：
    python png_tool.py info  <in.png>
    python png_tool.py crop  <in.png> <out.png> --box 0,0,945,945
    python png_tool.py resize <in.png> <out.png> --size 512 [--box 0,0,945,945]

作者：虫志龙 <47190078@qq.com>
许可：MIT
"""

import argparse
import struct
import sys
import zlib


# ---------------- 解码 ----------------

def read_chunks(data):
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("不是 PNG 文件")
    pos = 8
    out = []
    while pos < len(data):
        ln = struct.unpack(">I", data[pos:pos + 4])[0]
        tag = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + ln]
        out.append((tag, body))
        pos += 12 + ln
        if tag == b"IEND":
            break
    return out


def paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def decode(path):
    with open(path, "rb") as f:
        data = f.read()
    chunks = read_chunks(data)
    ihdr = None
    idat = b""
    for tag, body in chunks:
        if tag == b"IHDR":
            ihdr = body
        elif tag == b"IDAT":
            idat += body
    if ihdr is None:
        raise ValueError("缺 IHDR")
    w, h, bd, ct, comp, filt, inter = struct.unpack(">IIBBBBB", ihdr[:13])
    if bd != 8:
        raise ValueError("只支持位深 8，实际 %d" % bd)
    if inter != 0:
        raise ValueError("不支持隔行扫描")
    if ct == 2:
        ch = 3
    elif ct == 6:
        ch = 4
    elif ct == 0:
        ch = 1
    else:
        raise ValueError("不支持的色彩类型 %d" % ct)

    raw = zlib.decompress(idat)
    stride = w * ch
    rows = []
    prev = bytearray(stride)
    pos = 0
    for _ in range(h):
        ft = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
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
                line[i] = (line[i] + paeth(left, prev[i], ul)) & 0xFF
        elif ft != 0:
            raise ValueError("未知过滤类型 %d" % ft)
        rows.append(line)
        prev = line
    return {"w": w, "h": h, "ch": ch, "rows": rows}


# ---------------- 处理 ----------------

def crop(img, box):
    x0, y0, x1, y1 = box
    ch = img["ch"]
    rows = [r[x0 * ch:x1 * ch] for r in img["rows"][y0:y1]]
    return {"w": x1 - x0, "h": y1 - y0, "ch": ch, "rows": rows}


def resize(img, size):
    """面积平均缩放（先纵向后横向），对平涂插画比最近邻干净得多。"""
    sw, sh, ch = img["w"], img["h"], img["ch"]
    dyd = sh / size
    # 纵向
    tmp = []
    for dy in range(size):
        y0 = int(dy * dyd)
        y1 = max(y0 + 1, int((dy + 1) * dyd))
        y1 = min(y1, sh)
        acc = [0] * (sw * ch)
        n = y1 - y0
        for y in range(y0, y1):
            row = img["rows"][y]
            for i in range(sw * ch):
                acc[i] += row[i]
        tmp.append(bytearray(v // n for v in acc))
    # 横向
    dxd = sw / size
    out = []
    for row in tmp:
        line = bytearray(size * ch)
        for dx in range(size):
            x0 = int(dx * dxd)
            x1 = max(x0 + 1, int((dx + 1) * dxd))
            x1 = min(x1, sw)
            n = x1 - x0
            for c in range(ch):
                s = 0
                for x in range(x0, x1):
                    s += row[x * ch + c]
                line[dx * ch + c] = s // n
        out.append(line)
    return {"w": size, "h": size, "ch": ch, "rows": out}


def to_rgb(img, bg=(255, 255, 255)):
    """转 RGB；有 Alpha 时按背景色合成（头像不需要透明）。"""
    if img["ch"] == 3:
        return img
    rows = []
    for r in img["rows"]:
        line = bytearray(img["w"] * 3)
        for x in range(img["w"]):
            if img["ch"] == 1:
                g = r[x]
                line[x * 3:x * 3 + 3] = bytes((g, g, g))
            else:
                a = r[x * 4 + 3]
                for c in range(3):
                    v = r[x * 4 + c] * a + bg[c] * (255 - a)
                    line[x * 3 + c] = min(255, v // 255)
        rows.append(line)
    return {"w": img["w"], "h": img["h"], "ch": 3, "rows": rows}


def posterize(img, bits):
    """每通道保留高 bits 位，降低熵以提高压缩率。对纯色插画几乎无损。"""
    if bits >= 8:
        return img
    step = 1 << (8 - bits)
    lut = bytearray(256)
    for v in range(256):
        q = (v // step) * step + step // 2
        lut[v] = min(255, q)
    rows = [bytearray(lut[v] for v in r) for r in img["rows"]]
    return {"w": img["w"], "h": img["h"], "ch": img["ch"], "rows": rows}


def encode(img, level=9):
    ch = img["ch"]
    ct = {1: 0, 3: 2, 4: 6}[ch]
    raw = bytearray()
    for r in img["rows"]:
        raw.append(0)
        raw.extend(r)

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", img["w"], img["h"], 8, ct, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
            chunk(b"sRGB", b"\x00") +
            chunk(b"IDAT", zlib.compress(bytes(raw), level)) +
            chunk(b"IEND", b""))


def parse_box(s):
    parts = [int(x) for x in s.split(",")]
    if len(parts) != 4:
        raise ValueError("--box 需要 x0,y0,x1,y1")
    return tuple(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["info", "crop", "resize"])
    ap.add_argument("src")
    ap.add_argument("dst", nargs="?")
    ap.add_argument("--box", default=None)
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--posterize", type=int, default=8,
                    help="每通道保留位数，8=不处理；6 或 5 可显著减小体积")
    a = ap.parse_args()

    img = decode(a.src)
    if a.cmd == "info":
        print("尺寸 %dx%d  通道 %d" % (img["w"], img["h"], img["ch"]))
        return 0

    box = parse_box(a.box) if a.box else (0, 0, img["w"], img["h"])
    if box[2] > img["w"] or box[3] > img["h"]:
        print("裁剪框超出图像范围：%s vs %dx%d" % (box, img["w"], img["h"]))
        return 2
    img = crop(img, box)
    if a.cmd == "resize":
        img = resize(img, a.size)
    img = to_rgb(img)
    img = posterize(img, a.posterize)

    data = encode(img)
    with open(a.dst, "wb") as f:
        f.write(data)
    print("已写出 %s  %dx%d  通道 %d  %.1f KB"
          % (a.dst, img["w"], img["h"], img["ch"], len(data) / 1024.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
