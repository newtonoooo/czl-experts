#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""纯 Python 头像处理工具：裁剪去水印 + 面积重采样到 512x512 + 输出 RGB PNG。

为什么不用 Pillow：部分环境无法安装第三方库。本脚本只依赖标准库 zlib/struct。
支持的输入：8 位、非隔行的 PNG（色彩类型 0/2/4/6，即灰度/RGB/灰度+alpha/RGBA）。

用法：
    python prepare_avatar.py <输入.png> <输出.png> [--crop L,T,W,H] [--size 512] [--max-kb 500]

示例（去掉右下角水印，再居中裁方）：
    python prepare_avatar.py raw.png avatars/expert.png --crop 42,0,940,940 --size 512

输出说明：统一转为 8 位 RGB（无 alpha），便于各端稳定解码；
若结果超过 --max-kb，会依序尝试更强的行滤波重新压缩。
"""

import argparse
import struct
import sys
import zlib

PNG_SIG = b"\x89PNG\r\n\x1a\n"
CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


def read_png(path):
    data = open(path, "rb").read()
    if data[:8] != PNG_SIG:
        raise ValueError("不是 PNG 文件")
    pos = 8
    idat = bytearray()
    ihdr = None
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        ctype = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if ctype == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", chunk)
        elif ctype == b"IDAT":
            idat.extend(chunk)
        elif ctype == b"IEND":
            break
    if ihdr is None:
        raise ValueError("缺少 IHDR")
    width, height, depth, color, comp, filt, interlace = ihdr
    if depth != 8:
        raise ValueError("仅支持 8 位色深，当前 %d" % depth)
    if interlace != 0:
        raise ValueError("不支持隔行 PNG")
    if color not in CHANNELS:
        raise ValueError("不支持的色彩类型 %d" % color)
    raw = zlib.decompress(bytes(idat))
    return width, height, color, raw


def unfilter(width, height, color, raw):
    """还原扫描线，返回按行存放的像素字节。"""
    ch = CHANNELS[color]
    stride = width * ch
    out = bytearray(height * stride)
    prev = bytearray(stride)
    pos = 0
    for y in range(height):
        ftype = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
        if ftype == 1:  # Sub
            for i in range(ch, stride):
                line[i] = (line[i] + line[i - ch]) & 0xFF
        elif ftype == 2:  # Up
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ftype == 3:  # Average
            for i in range(stride):
                left = line[i - ch] if i >= ch else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:  # Paeth
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                b = prev[i]
                c = prev[i - ch] if i >= ch else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        elif ftype != 0:
            raise ValueError("未知行滤波类型 %d" % ftype)
        out[y * stride:(y + 1) * stride] = line
        prev = line
    return out, stride


def to_rgb_rows(width, height, color, pixels, stride):
    """把任意支持格式转为逐行 RGB 字节。"""
    rows = []
    for y in range(height):
        line = pixels[y * stride:(y + 1) * stride]
        if color == 2:
            rows.append(bytes(line))
        elif color == 6:
            rows.append(bytes(b for i in range(0, len(line), 4) for b in line[i:i + 3]))
        elif color == 0:
            rows.append(bytes(b for v in line for b in (v, v, v)))
        elif color == 4:
            rows.append(bytes(b for i in range(0, len(line), 2) for b in (line[i], line[i], line[i])))
        else:
            raise ValueError("调色板 PNG 请先转为 RGB")
    return rows


def crop_rows(rows, box):
    left, top, w, h = box
    return [row[left * 3:(left + w) * 3] for row in rows[top:top + h]]


def area_resize(rows, src_w, src_h, dst_w, dst_h):
    """面积重采样：缩小图像时比双线性更少丢细节。"""
    out = []
    x_ratio = src_w / dst_w
    y_ratio = src_h / dst_h
    for dy in range(dst_h):
        y0 = dy * y_ratio
        y1 = (dy + 1) * y_ratio
        y_start = int(y0)
        y_end = min(int(y1 + 0.999999), src_h)
        acc = [0.0] * (dst_w * 3)
        for sy in range(y_start, y_end):
            wy = min(y1, sy + 1) - max(y0, sy)
            if wy <= 0:
                continue
            row = rows[sy]
            for dx in range(dst_w):
                x0 = dx * x_ratio
                x1 = (dx + 1) * x_ratio
                x_start = int(x0)
                x_end = min(int(x1 + 0.999999), src_w)
                r = g = b = 0.0
                wsum = 0.0
                for sx in range(x_start, x_end):
                    wx = min(x1, sx + 1) - max(x0, sx)
                    if wx <= 0:
                        continue
                    i = sx * 3
                    r += row[i] * wx
                    g += row[i + 1] * wx
                    b += row[i + 2] * wx
                    wsum += wx
                if wsum:
                    j = dx * 3
                    acc[j] += (r / wsum) * wy
                    acc[j + 1] += (g / wsum) * wy
                    acc[j + 2] += (b / wsum) * wy
        line = bytearray(dst_w * 3)
        for dx in range(dst_w):
            j = dx * 3
            line[j] = max(0, min(255, int(acc[j] / y_ratio + 0.5)))
            line[j + 1] = max(0, min(255, int(acc[j + 1] / y_ratio + 0.5)))
            line[j + 2] = max(0, min(255, int(acc[j + 2] / y_ratio + 0.5)))
        out.append(bytes(line))
    return out


def encode_png(rows, width, height, filter_type=0):
    raw = bytearray()
    prev = bytes(width * 3)
    for row in rows:
        raw.append(filter_type)
        if filter_type == 0:
            raw.extend(row)
        elif filter_type == 2:  # Up
            raw.extend(bytes((row[i] - prev[i]) & 0xFF for i in range(width * 3)))
        else:
            raise ValueError("仅实现 0/2 两种行滤波")
        prev = row

    def chunk(tag, payload):
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (PNG_SIG + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--crop", default=None, help="裁剪矩形 左,上,宽,高")
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--max-kb", type=int, default=500)
    args = ap.parse_args()

    width, height, color, raw = read_png(args.src)
    pixels, stride = unfilter(width, height, color, raw)
    rows = to_rgb_rows(width, height, color, pixels, stride)

    if args.crop:
        left, top, w, h = [int(v) for v in args.crop.split(",")]
        if left + w > width or top + h > height:
            raise SystemExit("裁剪框超出图像范围：图像 %dx%d" % (width, height))
        rows = crop_rows(rows, (left, top, w, h))
        width, height = w, h

    rows = area_resize(rows, width, height, args.size, args.size)
    for ftype in (0, 2):
        data = encode_png(rows, args.size, args.size, ftype)
        if len(data) <= args.max_kb * 1024:
            break
    with open(args.dst, "wb") as f:
        f.write(data)
    print("输出 %s：%d×%d，%d 字节（%.0f KB），行滤波 %d"
          % (args.dst, args.size, args.size, len(data), len(data) / 1024, ftype))
    if len(data) > args.max_kb * 1024:
        print("警告：仍超过 %d KB 上限，请换更简洁的图或降低细节" % args.max_kb)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
