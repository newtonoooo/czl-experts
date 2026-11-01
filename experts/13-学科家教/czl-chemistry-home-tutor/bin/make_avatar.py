#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""头像规范化工具：裁切 → 面积重采样 → 输出 512×512 RGB PNG（≤ 上限）。

为什么不用 Pillow：部分环境装不上第三方库，本脚本只依赖标准库 zlib / struct。
支持的输入：8 位、非隔行的 PNG（色彩类型 0 灰度 / 2 RGB / 4 灰度+alpha / 6 RGBA）。
输出统一为 8 位 RGB、无 alpha，避免各端解码差异。

用法：
    python make_avatar.py 输入.png 输出.png [--crop 左,上,宽,高] [--size 512] [--max-kb 500]

示例（去掉右下角水印后裁成正方形）：
    python make_avatar.py raw.png avatars/expert.png --crop 42,0,940,940

退出码：0 成功；1 参数或图片不合法；2 输出仍超过大小上限。
"""

import argparse
import struct
import sys
import zlib

PNG_SIG = b"\x89PNG\r\n\x1a\n"
CHANNELS = {0: 1, 2: 3, 4: 2, 6: 4}


def read_png(path):
    """解析 PNG，返回 (宽, 高, 色彩类型, 还原后的像素字节)。"""
    data = open(path, "rb").read()
    if data[:8] != PNG_SIG:
        raise ValueError("不是 PNG 文件（缺少 PNG 文件头）")
    pos = 8
    idat = bytearray()
    ihdr = None
    while pos + 8 <= len(data):
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
        raise ValueError("缺少 IHDR 块")
    width, height, depth, color, comp, filt, interlace = ihdr
    if depth != 8:
        raise ValueError("仅支持 8 位色深，当前 %d 位" % depth)
    if interlace != 0:
        raise ValueError("不支持隔行扫描 PNG，请先另存为非隔行")
    if color not in CHANNELS:
        raise ValueError("不支持的色彩类型 %d（调色板 PNG 请先转成 RGB）" % color)
    raw = zlib.decompress(bytes(idat))
    return width, height, color, raw


def unfilter(width, height, color, raw):
    """按 PNG 规范还原扫描线。"""
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
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        elif ftype != 0:
            raise ValueError("未知的行滤波类型 %d" % ftype)
        out[y * stride:(y + 1) * stride] = line
        prev = line
    return out, stride


def to_rgb_rows(width, height, color, pixels, stride):
    """把灰度 / 带 alpha 的格式统一转成逐行 RGB。"""
    rows = []
    for y in range(height):
        line = pixels[y * stride:(y + 1) * stride]
        if color == 2:
            rows.append(bytes(line))
        elif color == 6:
            rows.append(bytes(b for i in range(0, len(line), 4) for b in line[i:i + 3]))
        elif color == 0:
            rows.append(bytes(v for v in line for _ in range(3)))
        elif color == 4:
            rows.append(bytes(line[i] for i in range(0, len(line), 2) for _ in range(3)))
    return rows


def crop_rows(rows, box):
    left, top, w, h = box
    return [row[left * 3:(left + w) * 3] for row in rows[top:top + h]]


def axis_weights(src, dst):
    """面积法权重：每个目标位置覆盖了哪些源位置、各占多少。"""
    scale = src / float(dst)
    table = []
    for d in range(dst):
        a = d * scale
        b = (d + 1) * scale
        i0 = int(a)
        i1 = min(src, int(b) + (1 if b > int(b) else 0))
        span = b - a
        items = []
        for i in range(i0, i1):
            w = min(b, i + 1) - max(a, i)
            if w > 0:
                items.append((i, w / span))
        table.append(items)
    return table


def area_resize(rows, src_w, src_h, dst_w, dst_h):
    """可分离的面积重采样：先横向，再纵向。缩小图像时比双线性保留更多细节。"""
    xw = axis_weights(src_w, dst_w)
    # 横向
    tmp = []
    for row in rows:
        new_row = bytearray(dst_w * 3)
        for dx, items in enumerate(xw):
            r = g = b = 0.0
            for sx, w in items:
                i = sx * 3
                r += row[i] * w
                g += row[i + 1] * w
                b += row[i + 2] * w
            j = dx * 3
            new_row[j] = min(255, max(0, int(r + 0.5)))
            new_row[j + 1] = min(255, max(0, int(g + 0.5)))
            new_row[j + 2] = min(255, max(0, int(b + 0.5)))
        tmp.append(new_row)

    # 纵向
    yw = axis_weights(src_h, dst_h)
    out = []
    for dy, items in enumerate(yw):
        acc = [0.0] * (dst_w * 3)
        for sy, w in items:
            row = tmp[sy]
            for i in range(dst_w * 3):
                acc[i] += row[i] * w
        line = bytearray(dst_w * 3)
        for i in range(dst_w * 3):
            line[i] = min(255, max(0, int(acc[i] + 0.5)))
        out.append(bytes(line))
    return out


def encode_png(rows, width, height, filter_type=2):
    """编码为 8 位 RGB PNG。filter_type=2 用 Up 滤波，图片类内容压缩率更好。"""
    raw = bytearray()
    prev = bytes(width * 3)
    for row in rows:
        raw.append(filter_type)
        if filter_type == 0:
            raw.extend(row)
        elif filter_type == 2:
            raw.extend(bytes((row[i] - prev[i]) & 0xFF for i in range(width * 3)))
        else:
            raise ValueError("只实现了 0 / 2 两种行滤波")
        prev = row

    def chunk(tag, payload):
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (PNG_SIG + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


def verify_png(path):
    """重新读回输出文件，确认可解码、尺寸与格式正确。返回 (宽, 高, 色彩类型, 字节数)。"""
    w, h, color, raw = read_png(path)
    if color != 2:
        raise ValueError("输出色彩类型应为 2（RGB），实际 %d" % color)
    return w, h, color, len(raw)


def main():
    ap = argparse.ArgumentParser(description="把 PNG 规范化为正方形 RGB 头像")
    ap.add_argument("src", help="输入 PNG 路径")
    ap.add_argument("dst", help="输出 PNG 路径")
    ap.add_argument("--crop", default=None, help="裁剪矩形：左,上,宽,高")
    ap.add_argument("--size", type=int, default=512, help="输出边长，默认 512")
    ap.add_argument("--max-kb", type=int, default=500, help="大小上限（KB），默认 500")
    args = ap.parse_args()

    try:
        width, height, color, raw = read_png(args.src)
        pixels, stride = unfilter(width, height, color, raw)
        rows = to_rgb_rows(width, height, color, pixels, stride)
        print("读入 %s：%d×%d，色彩类型 %d" % (args.src, width, height, color))

        if args.crop:
            box = [int(v) for v in args.crop.split(",")]
            if len(box) != 4:
                raise ValueError("--crop 需要四个整数：左,上,宽,高")
            left, top, w, h = box
            if left < 0 or top < 0 or w <= 0 or h <= 0 or left + w > width or top + h > height:
                raise ValueError("裁剪框超出图像范围（图像 %d×%d）" % (width, height))
            rows = crop_rows(rows, box)
            width, height = w, h
            print("裁剪后：%d×%d" % (width, height))

        rows = area_resize(rows, width, height, args.size, args.size)

        data = b""
        used_filter = 0
        for ftype in (2, 0):
            data = encode_png(rows, args.size, args.size, ftype)
            used_filter = ftype
            if len(data) <= args.max_kb * 1024:
                break

        with open(args.dst, "wb") as f:
            f.write(data)

        w, h, c, rawlen = verify_png(args.dst)
        print("输出 %s：%d×%d，色彩类型 %d，%.1f KB，行滤波 %d，解码校验通过"
              % (args.dst, w, h, c, len(data) / 1024.0, used_filter))

        if len(data) > args.max_kb * 1024:
            print("警告：仍超过 %d KB 上限（当前 %.1f KB），建议换更简洁的底图"
                  % (args.max_kb, len(data) / 1024.0))
            return 2
        return 0
    except Exception as e:
        print("失败：%s" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
