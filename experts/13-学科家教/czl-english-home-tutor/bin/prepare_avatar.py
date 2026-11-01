#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""prepare_avatar.py —— 把任意尺寸的 PNG 裁方、缩放为 512x512、压到指定体积以内。

只依赖 Python 标准库（zlib / struct），不需要 Pillow。
支持输入：8 位、非隔行、色彩类型 2（RGB）或 6（RGBA）的 PNG。
输出：8 位 RGB PNG，无 alpha。

用法：
    python bin/prepare_avatar.py <输入.png> <输出.png> [--crop L,T,W,H] [--size 512] [--max-kb 400]
"""

import argparse
import struct
import sys
import zlib

PNG_SIG = b"\x89PNG\r\n\x1a\n"
CHANNELS = {2: 3, 6: 4}


def decode_png(path):
    """返回 (width, height, channels, rows)，rows 为每行 bytes。"""
    data = open(path, "rb").read()
    if data[:8] != PNG_SIG:
        raise SystemExit("不是 PNG 文件：%s" % path)

    pos, idat, ihdr = 8, bytearray(), None
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
        raise SystemExit("PNG 缺少 IHDR")

    width, height, depth, color, _, _, interlace = ihdr
    if depth != 8:
        raise SystemExit("只支持 8 位色深，当前 %d 位" % depth)
    if interlace != 0:
        raise SystemExit("不支持隔行 PNG，请另存为非隔行")
    if color not in CHANNELS:
        raise SystemExit("只支持 RGB / RGBA PNG，当前色彩类型 %d" % color)

    ch = CHANNELS[color]
    raw = zlib.decompress(bytes(idat))
    stride = width * ch
    rows, prev, p = [], bytes(stride), 0
    for _ in range(height):
        ftype = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if ftype == 1:
            for i in range(ch, stride):
                line[i] = (line[i] + line[i - ch]) & 0xFF
        elif ftype == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ftype == 3:
            for i in range(stride):
                left = line[i - ch] if i >= ch else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                b = prev[i]
                c = prev[i - ch] if i >= ch else 0
                est = a + b - c
                pa, pb, pc = abs(est - a), abs(est - b), abs(est - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 0xFF
        elif ftype != 0:
            raise SystemExit("未知行滤波类型 %d" % ftype)
        rows.append(bytes(line))
        prev = bytes(line)

    if ch == 4:
        rows = [bytes(b for i in range(0, len(r), 4) for b in r[i:i + 3]) for r in rows]
    return width, height, 3, rows


def crop(rows, left, top, w, h):
    out = []
    for y in range(top, top + h):
        row = rows[y]
        out.append(row[left * 3:(left + w) * 3])
    return out


def resample(rows, sw, sh, dw, dh):
    """面积平均缩放：每个目标像素取对应源矩形的加权平均。"""
    xw = []  # 每个目标列：[ (起始源列, 权重比例), ... ]
    for dx in range(dw):
        x0, x1 = dx * sw / dw, (dx + 1) * sw / dw
        spans = []
        for sx in range(int(x0), min(int(x1 + 0.999999), sw)):
            w = min(x1, sx + 1) - max(x0, sx)
            if w > 0:
                spans.append((sx, w / (x1 - x0)))
        xw.append(spans)

    out = []
    for dy in range(dh):
        y0, y1 = dy * sh / dh, (dy + 1) * sh / dh
        acc = [[0.0, 0.0, 0.0] for _ in range(dw)]
        ysum = 0.0
        for sy in range(int(y0), min(int(y1 + 0.999999), sh)):
            wy = min(y1, sy + 1) - max(y0, sy)
            if wy <= 0:
                continue
            ysum += wy
            row = rows[sy]
            for dx, spans in enumerate(xw):
                r = g = b = 0.0
                for sx, wx in spans:
                    i = sx * 3
                    w = wx * wy
                    r += row[i] * w
                    g += row[i + 1] * w
                    b += row[i + 2] * w
                acc[dx][0] += r
                acc[dx][1] += g
                acc[dx][2] += b
        line = bytearray(dw * 3)
        for dx in range(dw):
            r, g, b = acc[dx]
            line[dx * 3] = max(0, min(255, int(r / ysum + 0.5)))
            line[dx * 3 + 1] = max(0, min(255, int(g / ysum + 0.5)))
            line[dx * 3 + 2] = max(0, min(255, int(b / ysum + 0.5)))
        out.append(bytes(line))
    return out


def _filter_row(ftype, row, prev):
    """按 PNG 规范生成一行滤波数据。"""
    n = len(row)
    if ftype == 0:
        return bytes(row)
    if ftype == 1:  # Sub
        return bytes((row[i] - (row[i - 3] if i >= 3 else 0)) & 0xFF for i in range(n))
    if ftype == 2:  # Up
        return bytes((row[i] - prev[i]) & 0xFF for i in range(n))
    if ftype == 3:  # Average
        out = bytearray(n)
        for i in range(n):
            left = row[i - 3] if i >= 3 else 0
            out[i] = (row[i] - ((left + prev[i]) >> 1)) & 0xFF
        return bytes(out)
    # Paeth
    out = bytearray(n)
    for i in range(n):
        a = row[i - 3] if i >= 3 else 0
        b = prev[i]
        c = prev[i - 3] if i >= 3 else 0
        est = a + b - c
        pa, pb, pc = abs(est - a), abs(est - b), abs(est - c)
        pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
        out[i] = (row[i] - pred) & 0xFF
    return bytes(out)


def encode_png(rows, size):
    """逐行自适应滤波（None/Sub/Up/Paeth 取绝对值最小者），再 zlib 压缩。"""
    def chunk(tag, payload):
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    raw = bytearray()
    prev = bytes(size * 3)
    for row in rows:
        best = None
        for ftype in (0, 1, 2, 4):
            cand = _filter_row(ftype, row, prev)
            score = sum(v if v < 128 else 256 - v for v in cand)
            if best is None or score < best[0]:
                best = (score, ftype, cand)
        raw.append(best[1])
        raw.extend(best[2])
        prev = row
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return PNG_SIG + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--crop", default=None, help="裁剪矩形 左,上,宽,高")
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--max-kb", type=int, default=400)
    args = ap.parse_args()

    width, height, ch, rows = decode_png(args.src)
    print("读入 %dx%d，%d 通道" % (width, height, ch))

    if args.crop:
        left, top, w, h = [int(v) for v in args.crop.split(",")]
        if left + w > width or top + h > height:
            raise SystemExit("裁剪框超出图像范围")
        rows = crop(rows, left, top, w, h)
        width, height = w, h
        print("裁剪为 %dx%d" % (width, height))

    if width != height:
        side = min(width, height)
        left = (width - side) // 2
        top = (height - side) // 2
        rows = crop(rows, left, top, side, side)
        width = height = side
        print("居中裁方为 %dx%d" % (side, side))

    rows = resample(rows, width, height, args.size, args.size)
    data = encode_png(rows, args.size)
    with open(args.dst, "wb") as f:
        f.write(data)

    kb = len(data) / 1024
    print("输出 %s：%d×%d，%.1f KB" % (args.dst, args.size, args.size, kb))
    if kb > args.max_kb:
        print("警告：超过 %d KB，建议换更简洁的构图" % args.max_kb)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
