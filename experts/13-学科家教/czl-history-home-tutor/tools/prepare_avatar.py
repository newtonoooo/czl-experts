#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""头像规范化工具（纯标准库，零第三方依赖）。

为什么自己写：发布要求头像为 512x512、PNG、单张 ≤500KB；但很多运行环境装不上
Pillow。本脚本只用 zlib + struct 完成 PNG 解码、面积平均缩放（box filter）、
自适应行滤波与重编码，保证在裸 Python 环境也能跑通。

支持的输入：8 位色深、非隔行 PNG，色彩类型 0(灰度)/2(RGB)/4(灰度+A)/6(RGBA)。
输出：8 位 RGB PNG（丢弃 alpha，头像不需要透明通道，且能显著减小体积）。

用法:
    python prepare_avatar.py <in.png> <out.png> [--size 512] [--max-kb 500]
    python prepare_avatar.py <in.png> <out.png> --crop 0.04   # 四周各裁掉 4%

退出码:
    0 成功；1 参数或解码错误；2 压缩后仍超限。
"""

import argparse
import struct
import sys
import zlib
from pathlib import Path

SIG = b"\x89PNG\r\n\x1a\n"
CHANNELS = {0: 1, 2: 3, 4: 2, 6: 4}


def decode_png(path):
    """返回 (width, height, channels, pixels)，pixels 为逐行 RGB(A) 字节串拼接。"""
    data = Path(path).read_bytes()
    if data[:8] != SIG:
        raise ValueError("不是 PNG 文件（签名不匹配）")

    pos, idat, ihdr = 8, bytearray(), None
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
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
        raise ValueError("缺少 IHDR 块")
    width, height, depth, color, _comp, _filt, interlace = ihdr
    if depth != 8:
        raise ValueError(f"仅支持 8 位色深，当前 {depth}")
    if interlace != 0:
        raise ValueError("不支持隔行（Adam7）PNG")
    if color not in CHANNELS:
        raise ValueError(f"不支持的色彩类型 {color}")

    ch = CHANNELS[color]
    raw = zlib.decompress(bytes(idat))
    stride = width * ch
    out = bytearray(height * stride)
    prev = bytearray(stride)

    for y in range(height):
        base = y * (stride + 1)
        ftype = raw[base]
        line = bytearray(raw[base + 1:base + 1 + stride])
        if ftype == 1:      # Sub
            for i in range(ch, stride):
                line[i] = (line[i] + line[i - ch]) & 0xFF
        elif ftype == 2:    # Up
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ftype == 3:    # Average
            for i in range(stride):
                left = line[i - ch] if i >= ch else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:    # Paeth
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                b = prev[i]
                c = prev[i - ch] if i >= ch else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        elif ftype != 0:
            raise ValueError(f"未知行滤波类型 {ftype}")
        out[y * stride:(y + 1) * stride] = line
        prev = line

    return width, height, ch, bytes(out)


def to_rgb(width, height, ch, buf):
    """统一转 RGB，去掉 alpha（按不透明处理）。"""
    if ch == 3:
        return buf
    rgb = bytearray(width * height * 3)
    if ch == 1:
        for i in range(width * height):
            v = buf[i]
            rgb[i * 3] = rgb[i * 3 + 1] = rgb[i * 3 + 2] = v
    elif ch == 2:
        for i in range(width * height):
            v = buf[i * 2]
            rgb[i * 3] = rgb[i * 3 + 1] = rgb[i * 3 + 2] = v
    else:  # ch == 4
        for i in range(width * height):
            j, k = i * 4, i * 3
            rgb[k] = buf[j]
            rgb[k + 1] = buf[j + 1]
            rgb[k + 2] = buf[j + 2]
    return bytes(rgb)


def crop_center(width, height, rgb, ratio):
    """按比例从四周向内裁切，返回新尺寸与像素。"""
    if ratio <= 0:
        return width, height, rgb
    side_x, side_y = int(width * ratio), int(height * ratio)
    nw, nh = width - side_x * 2, height - side_y * 2
    if nw <= 8 or nh <= 8:
        raise ValueError("裁切比例过大")
    out = bytearray(nw * nh * 3)
    for y in range(nh):
        src = ((y + side_y) * width + side_x) * 3
        out[y * nw * 3:(y + 1) * nw * 3] = rgb[src:src + nw * 3]
    return nw, nh, bytes(out)


def resize_box(width, height, rgb, size):
    """面积平均缩放：每个目标像素取源区域的平均色，避免锯齿。"""
    if width == size and height == size:
        return rgb
    out = bytearray(size * size * 3)
    x_ratio, y_ratio = width / size, height / size
    for ty in range(size):
        y0, y1 = int(ty * y_ratio), max(int(ty * y_ratio) + 1, int((ty + 1) * y_ratio))
        for tx in range(size):
            x0, x1 = int(tx * x_ratio), max(int(tx * x_ratio) + 1, int((tx + 1) * x_ratio))
            r = g = b = n = 0
            for sy in range(y0, min(y1, height)):
                row = sy * width
                for sx in range(x0, min(x1, width)):
                    p = (row + sx) * 3
                    r += rgb[p]
                    g += rgb[p + 1]
                    b += rgb[p + 2]
                    n += 1
            q = (ty * size + tx) * 3
            out[q] = r // n
            out[q + 1] = g // n
            out[q + 2] = b // n
    return bytes(out)


def _filter_row(line, prev, bpp, ftype):
    out = bytearray(len(line))
    if ftype == 0:
        out[:] = line
    elif ftype == 1:
        for i in range(len(line)):
            left = line[i - bpp] if i >= bpp else 0
            out[i] = (line[i] - left) & 0xFF
    elif ftype == 2:
        for i in range(len(line)):
            out[i] = (line[i] - prev[i]) & 0xFF
    elif ftype == 3:
        for i in range(len(line)):
            left = line[i - bpp] if i >= bpp else 0
            out[i] = (line[i] - ((left + prev[i]) >> 1)) & 0xFF
    else:
        for i in range(len(line)):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            p = a + b - c
            pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
            pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
            out[i] = (line[i] - pr) & 0xFF
    return out


def encode_png(width, height, rgb, level=9):
    """逐行选最优滤波（最小绝对值和），再 zlib 压缩。"""
    stride = width * 3
    raw = bytearray()
    prev = bytes(stride)
    for y in range(height):
        line = rgb[y * stride:(y + 1) * stride]
        best, best_score = None, None
        for ftype in (0, 1, 2, 3, 4):
            cand = _filter_row(line, prev, 3, ftype)
            score = sum(v if v < 128 else 256 - v for v in cand)
            if best_score is None or score < best_score:
                best, best_score = (ftype, cand), score
        raw.append(best[0])
        raw.extend(best[1])
        prev = line

    def chunk(tag, payload):
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (SIG + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), level))
            + chunk(b"IEND", b""))


def main():
    ap = argparse.ArgumentParser(description="把任意 PNG 规范化为 512x512 的 RGB PNG 头像")
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--max-kb", type=int, default=500)
    ap.add_argument("--crop", type=float, default=0.0, help="四周各裁掉的比例，如 0.04")
    args = ap.parse_args()

    try:
        w, h, ch, buf = decode_png(args.src)
        rgb = to_rgb(w, h, ch, buf)
        w, h, rgb = crop_center(w, h, rgb, args.crop)
        rgb = resize_box(w, h, rgb, args.size)
    except Exception as exc:
        print(f"❌ 处理失败：{exc}")
        return 1

    data = encode_png(args.size, args.size, rgb)
    if len(data) > args.max_kb * 1024:
        for lvl in (9, 6):
            data = encode_png(args.size, args.size, rgb, level=lvl)
            if len(data) <= args.max_kb * 1024:
                break
    if len(data) > args.max_kb * 1024:
        print(f"❌ 压缩后仍为 {len(data)/1024:.1f}KB，超过 {args.max_kb}KB")
        return 2

    Path(args.dst).parent.mkdir(parents=True, exist_ok=True)
    Path(args.dst).write_bytes(data)
    print(f"✅ {args.dst}  {args.size}x{args.size}  {len(data)/1024:.1f}KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
