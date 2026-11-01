#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""头像加工：裁掉边角水印 + 面积平均缩放到 512x512 + 输出 8 位 RGB PNG。

只用标准库（zlib / struct / argparse），不依赖 Pillow。
处理的目的是避开客户端的三类退化：非正方形、超过 500KB、带 alpha 或 16 位色深
——这三类在部分端上会让头像解码失败，退化成名称首字。

用法：
    python make_avatar.py <源图.png> <输出.png> [--box 左,上,宽,高] [--size 512] [--max-kb 500]

示例（1024 方图，去掉右下角水印后居中裁方）：
    python make_avatar.py raw.png avatars/expert.png --box 42,0,940,940 --size 512
"""

import argparse
import struct
import sys
import zlib

SIG = b"\x89PNG\r\n\x1a\n"
CH = {0: 1, 2: 3, 4: 2, 6: 4}


def load(path):
    """读取 8 位、非隔行 PNG，返回 (宽, 高, 色彩类型, 反滤波后的像素字节)。"""
    blob = open(path, "rb").read()
    if blob[:8] != SIG:
        raise SystemExit("不是 PNG 文件：%s" % path)
    pos, ihdr, idat = 8, None, []
    while pos < len(blob):
        (ln,) = struct.unpack(">I", blob[pos:pos + 4])
        tag = blob[pos + 4:pos + 8]
        body = blob[pos + 8:pos + 8 + ln]
        pos += 12 + ln
        if tag == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", body)
        elif tag == b"IDAT":
            idat.append(body)
        elif tag == b"IEND":
            break
    if ihdr is None:
        raise SystemExit("缺少 IHDR")
    w, h, depth, ctype, _, _, interlace = ihdr
    if depth != 8:
        raise SystemExit("只支持 8 位色深，当前 %d 位" % depth)
    if interlace:
        raise SystemExit("不支持隔行 PNG，请另存为非隔行")
    if ctype not in CH:
        raise SystemExit("不支持的色彩类型 %d" % ctype)

    raw = zlib.decompress(b"".join(idat))
    n = CH[ctype]
    stride = w * n
    out = bytearray(h * stride)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        ft = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if ft == 1:
            for i in range(n, stride):
                line[i] = (line[i] + line[i - n]) & 0xFF
        elif ft == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ft == 3:
            for i in range(stride):
                left = line[i - n] if i >= n else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ft == 4:
            for i in range(stride):
                a = line[i - n] if i >= n else 0
                b = prev[i]
                c = prev[i - n] if i >= n else 0
                q = a + b - c
                pa, pb, pc = abs(q - a), abs(q - b), abs(q - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        elif ft != 0:
            raise SystemExit("未知行滤波类型 %d" % ft)
        out[y * stride:(y + 1) * stride] = line
        prev = line
    return w, h, ctype, out


def to_rgb(w, h, ctype, buf):
    """统一转成每像素 3 字节的 RGB 行列表。"""
    stride = w * CH[ctype]
    rows = []
    for y in range(h):
        line = buf[y * stride:(y + 1) * stride]
        if ctype == 2:
            rows.append(bytes(line))
        elif ctype == 6:
            rows.append(bytes(v for i in range(0, len(line), 4) for v in line[i:i + 3]))
        elif ctype == 0:
            rows.append(bytes(v for g in line for v in (g, g, g)))
        else:  # 4: 灰度 + alpha
            rows.append(bytes(v for i in range(0, len(line), 2) for v in (line[i],) * 3))
    return rows


def crop(rows, box):
    left, top, cw, chh = box
    return [r[left * 3:(left + cw) * 3] for r in rows[top:top + chh]], cw, chh


def box_down(rows, sw, sh, dw, dh):
    """面积平均缩小。

    每个输出像素实际覆盖的源像素个数在非整数倍缩放时不相等（1 个或 2 个），
    必须逐像素记数后再除，否则除数偏大会让部分列周期性偏暗，出现竖条纹。
    """
    out = []
    for dy in range(dh):
        y0, y1 = dy * sh // dh, (dy + 1) * sh // dh
        acc = [0] * (dw * 3)
        n = [0] * dw
        for sy in range(y0, y1):
            row = rows[sy]
            for dx in range(dw):
                x0, x1 = dx * sw // dw, (dx + 1) * sw // dw
                i = x0 * 3
                k = dx * 3
                r = g = b = 0
                for _ in range(x0, x1):
                    r += row[i]
                    g += row[i + 1]
                    b += row[i + 2]
                    i += 3
                acc[k] += r
                acc[k + 1] += g
                acc[k + 2] += b
                n[dx] += x1 - x0
        line = bytearray(dw * 3)
        for dx in range(dw):
            c = n[dx] or 1
            k = dx * 3
            line[k] = min(255, acc[k] // c)
            line[k + 1] = min(255, acc[k + 1] // c)
            line[k + 2] = min(255, acc[k + 2] // c)
        out.append(bytes(line))
    return out


def encode(rows, w, h, mode):
    """mode 0: 无滤波；mode 2: Up 滤波（画面平缓时更省体积）。"""
    raw = bytearray()
    prev = bytes(w * 3)
    for row in rows:
        raw.append(mode)
        if mode == 0:
            raw.extend(row)
        else:
            raw.extend(bytes((row[i] - prev[i]) & 0xFF for i in range(w * 3)))
        prev = row

    def chunk(tag, body):
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)

    return (SIG
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--box", default=None, help="裁剪框 左,上,宽,高")
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--max-kb", type=int, default=500)
    a = ap.parse_args()

    w, h, ctype, buf = load(a.src)
    rows = to_rgb(w, h, ctype, buf)

    if a.box:
        box = tuple(int(v) for v in a.box.split(","))
        if box[0] + box[2] > w or box[1] + box[3] > h:
            raise SystemExit("裁剪框 %s 超出图像 %dx%d" % (a.box, w, h))
        rows, w, h = crop(rows, box)

    if w != h:
        side = min(w, h)
        rows, w, h = crop(rows, ((w - side) // 2, (h - side) // 2, side, side))

    rows = box_down(rows, w, h, a.size, a.size)

    data = None
    for mode in (0, 2):
        data = encode(rows, a.size, a.size, mode)
        if len(data) <= a.max_kb * 1024:
            break
    open(a.dst, "wb").write(data)

    kb = len(data) / 1024.0
    print("输出 %s：%dx%d，8 位 RGB，%.1f KB，滤波 %d" % (a.dst, a.size, a.size, kb, mode))
    if kb > a.max_kb:
        print("警告：超过 %d KB 上限，请换细节更少的图" % a.max_kb)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
