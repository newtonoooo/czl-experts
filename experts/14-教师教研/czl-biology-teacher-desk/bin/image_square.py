#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""image_square.py — 纯标准库 PNG 裁剪与缩放（正方形头像预处理）

用途：把一张大图裁成正方形并缩放到 512×512，用于专家头像或课件配图。
支持 8 位 RGB / RGBA / 灰度 的非隔行 PNG；不依赖 Pillow。

用法：
    python image_square.py -i source.png -o expert.png --size 512
    python image_square.py -i source.png -o expert.png --size 512 --box 240,70,560,560
"""

import argparse
import struct
import sys
import zlib
from typing import List, Tuple

PNG_SIG = b"\x89PNG\r\n\x1a\n"


def read_chunks(data: bytes):
    if not data.startswith(PNG_SIG):
        raise ValueError("不是 PNG 文件")
    pos = 8
    out = []
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        ctype = data[pos + 4:pos + 8]
        payload = data[pos + 8:pos + 8 + length]
        out.append((ctype, payload))
        pos += 12 + length
        if ctype == b"IEND":
            break
    return out


def paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def decode(png: bytes):
    chunks = read_chunks(png)
    ihdr = dict(chunks).get(b"IHDR")
    if ihdr is None:
        raise ValueError("缺少 IHDR")
    w, h, depth, color, comp, filt, interlace = struct.unpack(">IIBBBBB", ihdr)
    if depth != 8 or comp != 0 or filt != 0 or interlace != 0:
        raise ValueError(f"仅支持 8 位非隔行 PNG（当前 depth={depth}, interlace={interlace}）")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color)
    if channels is None:
        raise ValueError(f"不支持的色彩类型 {color}")
    raw = zlib.decompress(b"".join(p for t, p in chunks if t == b"IDAT"))
    stride = w * channels
    rows: List[bytearray] = []
    prev = bytearray(stride)
    pos = 0
    for _ in range(h):
        ftype = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
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
                left = line[i - channels] if i >= channels else 0
                upleft = prev[i - channels] if i >= channels else 0
                line[i] = (line[i] + paeth(left, prev[i], upleft)) & 0xFF
        elif ftype != 0:
            raise ValueError(f"未知过滤类型 {ftype}")
        rows.append(line)
        prev = line
    return w, h, channels, color, rows


def crop(rows, w, h, ch, box: Tuple[int, int, int, int]):
    x, y, cw, chh = box
    x = max(0, min(x, w - 1))
    y = max(0, min(y, h - 1))
    cw = min(cw, w - x)
    chh = min(chh, h - y)
    out = []
    for yy in range(y, y + chh):
        line = rows[yy]
        out.append(bytearray(line[x * ch:(x + cw) * ch]))
    return cw, chh, out


def resize(rows, w, h, ch, size: int):
    out_rows = []
    for ty in range(size):
        sy = (ty + 0.5) * h / size - 0.5
        y0 = max(0, min(h - 1, int(sy)))
        y1 = min(h - 1, y0 + 1)
        wy = sy - y0 if sy >= 0 else 0.0
        ty_line = bytearray(size * ch)
        for tx in range(size):
            sx = (tx + 0.5) * w / size - 0.5
            x0 = max(0, min(w - 1, int(sx)))
            x1 = min(w - 1, x0 + 1)
            wx = sx - x0 if sx >= 0 else 0.0
            for c in range(ch):
                p00 = rows[y0][x0 * ch + c]
                p01 = rows[y0][x1 * ch + c]
                p10 = rows[y1][x0 * ch + c]
                p11 = rows[y1][x1 * ch + c]
                top = p00 * (1 - wx) + p01 * wx
                bot = p10 * (1 - wx) + p11 * wx
                ty_line[tx * ch + c] = int(round(top * (1 - wy) + bot * wy))
        out_rows.append(ty_line)
    return out_rows


def chunk(ctype: bytes, payload: bytes) -> bytes:
    return (struct.pack(">I", len(payload)) + ctype + payload
            + struct.pack(">I", zlib.crc32(ctype + payload) & 0xFFFFFFFF))


def _filter_row(line: bytes, prev: bytes, ftype: int) -> bytes:
    if ftype == 0:
        return bytes(line)
    out = bytearray(len(line))
    if ftype == 1:  # Sub
        for i in range(len(line)):
            left = line[i - 3] if i >= 3 else 0
            out[i] = (line[i] - left) & 0xFF
    elif ftype == 2:  # Up
        for i in range(len(line)):
            out[i] = (line[i] - prev[i]) & 0xFF
    else:  # Paeth
        for i in range(len(line)):
            left = line[i - 3] if i >= 3 else 0
            up = prev[i]
            upleft = prev[i - 3] if i >= 3 else 0
            out[i] = (line[i] - paeth(left, up, upleft)) & 0xFF
    return bytes(out)


def encode(w: int, h: int, color: int, rows, posterize_bits: int = 0) -> bytes:
    if posterize_bits and 0 < posterize_bits < 8:
        step = 1 << (8 - posterize_bits)
        rows = [bytearray((v // step) * step + step // 2 for v in r) for r in rows]
    ihdr = struct.pack(">IIBBBBB", w, h, 8, color, 0, 0, 0)
    prev = bytes(len(rows[0])) if rows else b""
    chosen = []
    for r in rows:
        best = None
        for ft in (0, 1, 2, 4):
            cand = _filter_row(bytes(r), prev, ft)
            score = sum(min(v, 256 - v) for v in cand)
            if best is None or score < best[0]:
                best = (score, ft, cand)
        chosen.append(bytes([best[1]]) + best[2])
        prev = bytes(r)
    raw = b"".join(chosen)
    idat = zlib.compress(raw, 9)
    return PNG_SIG + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="PNG 正方形裁剪与缩放")
    ap.add_argument("-i", "--input", required=True)
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--box", help="裁剪框 x,y,w,h；不给则按短边居中裁剪")
    ap.add_argument("--posterize", type=int, default=0, help="色彩位数压缩（如 6），0 表示不压缩")
    args = ap.parse_args(argv)

    try:
        with open(args.input, "rb") as fh:
            png = fh.read()
        w, h, ch, color, rows = decode(png)
        if args.box:
            box = tuple(int(v) for v in args.box.split(","))
            if len(box) != 4:
                raise ValueError("--box 需要四个整数 x,y,w,h")
        else:
            side = min(w, h)
            box = ((w - side) // 2, (h - side) // 2, side, side)
        cw, chh, cropped = crop(rows, w, h, ch, box)
        resized = resize(cropped, cw, chh, ch, args.size)
        data = encode(args.size, args.size, color, resized, args.posterize)
        with open(args.output, "wb") as fh:
            fh.write(data)
    except Exception as exc:  # noqa: BLE001
        print(f"[错误] {exc}", file=sys.stderr)
        return 1
    print(f"已生成 {args.output}（{args.size}x{args.size}，{len(data)/1024:.1f} KB）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
