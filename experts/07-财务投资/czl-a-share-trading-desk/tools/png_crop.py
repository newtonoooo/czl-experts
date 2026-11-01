#!/usr/bin/env python3
"""零依赖 PNG 裁剪与缩放工具（仅用标准库 zlib / struct）。

用途：把图像生成模型输出的 1024×1024 原图裁掉右下角水印，
并缩到平台要求的 512×512 方图。

    python png_crop.py <输入.png> <输出.png> --crop x,y,w,h --resize 512

支持 8 位 RGB / RGBA、非隔行 PNG（生成模型的输出属于这一类）。
遇到不支持的格式会明确报错，不会静默产出坏图。
"""

import argparse
import struct
import sys
import zlib


def _read_chunks(data):
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("不是 PNG 文件")
    pos = 8
    chunks = []
    while pos < len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        ctype = data[pos + 4 : pos + 8]
        body = data[pos + 8 : pos + 8 + length]
        chunks.append((ctype, body))
        pos += 12 + length
        if ctype == b"IEND":
            break
    return chunks


def decode(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    chunks = _read_chunks(raw)

    ihdr = None
    idat = b""
    for ctype, body in chunks:
        if ctype == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", body)
        elif ctype == b"IDAT":
            idat += body
    if ihdr is None:
        raise ValueError("缺少 IHDR")
    width, height, depth, color_type, compression, filt, interlace = ihdr
    if depth != 8:
        raise ValueError("只支持 8 位深度，当前 %d" % depth)
    if interlace != 0:
        raise ValueError("不支持隔行扫描 PNG")
    channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(color_type)
    if channels is None:
        raise ValueError("不支持的颜色类型 %d" % color_type)

    buf = zlib.decompress(idat)
    stride = width * channels
    out = bytearray(height * stride)
    prev = bytearray(stride)
    pos = 0
    for y in range(height):
        ftype = buf[pos]
        pos += 1
        line = bytearray(buf[pos : pos + stride])
        pos += stride
        if ftype == 0:
            pass
        elif ftype == 1:  # Sub
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif ftype == 2:  # Up
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ftype == 3:  # Average
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:  # Paeth
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                b = prev[i]
                c = prev[i - channels] if i >= channels else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        else:
            raise ValueError("未知的行过滤类型 %d" % ftype)
        out[y * stride : (y + 1) * stride] = line
        prev = line
    return {"width": width, "height": height, "channels": channels, "pixels": out}


def crop(img, x, y, w, h):
    c = img["channels"]
    stride = img["width"] * c
    out = bytearray(w * h * c)
    for row in range(h):
        src = (y + row) * stride + x * c
        out[row * w * c : (row + 1) * w * c] = img["pixels"][src : src + w * c]
    return {"width": w, "height": h, "channels": c, "pixels": out}


def resize(img, nw, nh):
    """区域平均（box filter）：缩小图像时比最近邻更干净。"""
    c = img["channels"]
    sw, sh = img["width"], img["height"]
    out = bytearray(nw * nh * c)
    for dy in range(nh):
        y0 = dy * sh // nh
        y1 = max(y0 + 1, (dy + 1) * sh // nh)
        for dx in range(nw):
            x0 = dx * sw // nw
            x1 = max(x0 + 1, (dx + 1) * sw // nw)
            acc = [0] * c
            count = 0
            for sy in range(y0, y1):
                base = sy * sw * c
                for sx in range(x0, x1):
                    off = base + sx * c
                    for ch in range(c):
                        acc[ch] += img["pixels"][off + ch]
                    count += 1
            off = (dy * nw + dx) * c
            for ch in range(c):
                out[off + ch] = acc[ch] // count
    return {"width": nw, "height": nh, "channels": c, "pixels": out}


def posterize(img, bits):
    """把每个颜色通道压到 bits 位，用于压小文件体积（对插画肉眼几乎无差）。"""
    if bits >= 8:
        return img
    shift = 8 - bits
    step = 1 << shift
    table = bytes(min(255, ((v >> shift) << shift) + step // 2) for v in range(256))
    px = img["pixels"].translate(table)
    return {"width": img["width"], "height": img["height"], "channels": img["channels"], "pixels": px}


def encode(img, path):
    c = img["channels"]
    color_type = {1: 0, 3: 2, 4: 6}[c]
    width, height = img["width"], img["height"]
    stride = width * c
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw += img["pixels"][y * stride : (y + 1) * stride]

    def chunk(ctype, body):
        return (
            struct.pack(">I", len(body))
            + ctype
            + body
            + struct.pack(">I", zlib.crc32(ctype + body) & 0xFFFFFFFF)
        )

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(png)


def main():
    ap = argparse.ArgumentParser(description="零依赖 PNG 裁剪缩图")
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--crop", help="x,y,w,h")
    ap.add_argument("--resize", type=int, help="输出正方形边长")
    ap.add_argument("--posterize", type=int, default=8, help="每通道位数（8=不处理，6/5 可显著减小体积）")
    args = ap.parse_args()

    img = decode(args.src)
    print("输入 %dx%d，%d 通道" % (img["width"], img["height"], img["channels"]))
    if args.crop:
        x, y, w, h = (int(v) for v in args.crop.split(","))
        if x < 0 or y < 0 or x + w > img["width"] or y + h > img["height"]:
            print("裁剪区域超出图像边界")
            sys.exit(1)
        img = crop(img, x, y, w, h)
        print("裁剪为 %dx%d" % (img["width"], img["height"]))
    if args.resize:
        img = resize(img, args.resize, args.resize)
        print("缩放为 %dx%d" % (img["width"], img["height"]))
    if args.posterize < 8:
        img = posterize(img, args.posterize)
        print("颜色量化到每通道 %d 位" % args.posterize)
    encode(img, args.dst)
    print("已写出 %s" % args.dst)


if __name__ == "__main__":
    main()
