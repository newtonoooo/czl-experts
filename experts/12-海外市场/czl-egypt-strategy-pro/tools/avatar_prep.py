#!/usr/bin/env python3
"""头像后处理：裁剪、降采样、编码，并可导出 data URI。

用途
----
1. 把生成的大图裁成正方形并降采样到 512x512，控制在 500KB 以内；
2. 用 `--data-uri` 输出一份 base64 文本，便于把 plugin.json 的 avatar
   临时切成内联值（某些导入通道会把相对路径当 CDN 地址拼接，导致图片
   404 后回退成首字）。

只依赖 Python 标准库（struct / zlib / base64）。

示例
----
    python avatar_prep.py in.png -o out.png --size 512 --inset 140
    python avatar_prep.py in.png --data-uri avatar.txt --size 256
"""

from __future__ import annotations

import argparse
import base64
import struct
import sys
import zlib
from pathlib import Path

PNG_SIG = b"\x89PNG\r\n\x1a\n"
CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


class PngImage:
    def __init__(self, width: int, height: int, pixels: bytes, channels: int):
        self.width = width
        self.height = height
        self.pixels = pixels  # 每像素 channels 字节，行优先
        self.channels = channels


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def read_png(path: Path) -> PngImage:
    data = path.read_bytes()
    if data[:8] != PNG_SIG:
        raise SystemExit(f"不是 PNG：{path}")
    pos = 8
    width = height = depth = color = None
    interlace = 0
    idat = bytearray()
    palette = b""
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        tag = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        if tag == b"IHDR":
            width, height, depth, color, _, _, interlace = struct.unpack(">IIBBBBB", body)
        elif tag == b"PLTE":
            palette = body
        elif tag == b"IDAT":
            idat += body
        elif tag == b"IEND":
            break
        pos += 12 + length
    if depth != 8 or interlace != 0:
        raise SystemExit("仅支持 8 位非隔行 PNG")
    ch = CHANNELS[color]
    raw = zlib.decompress(bytes(idat))
    stride = width * ch
    out = bytearray(height * stride)
    prev = bytearray(stride)
    p = 0
    for y in range(height):
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
                left = line[i - ch] if i >= ch else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif f == 4:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                b = prev[i]
                c = prev[i - ch] if i >= ch else 0
                line[i] = (line[i] + _paeth(a, b, c)) & 0xFF
        out[y * stride:(y + 1) * stride] = line
        prev = line

    if color == 2:
        return PngImage(width, height, bytes(out), 3)
    if color == 6:
        return PngImage(width, height, bytes(out), 4)
    if color == 0:
        rgb = bytearray(width * height * 3)
        for i in range(width * height):
            v = out[i]
            rgb[i * 3:i * 3 + 3] = bytes((v, v, v))
        return PngImage(width, height, bytes(rgb), 3)
    if color == 3:
        rgb = bytearray(width * height * 3)
        for i in range(width * height):
            idx = out[i] * 3
            rgb[i * 3:i * 3 + 3] = palette[idx:idx + 3]
        return PngImage(width, height, bytes(rgb), 3)
    raise SystemExit(f"不支持的 PNG 颜色类型：{color}")


def to_rgb(img: PngImage) -> PngImage:
    if img.channels == 3:
        return img
    n = img.width * img.height
    rgb = bytearray(n * 3)
    if img.channels == 4:
        for i in range(n):
            rgb[i * 3:i * 3 + 3] = img.pixels[i * 4:i * 4 + 3]
    else:
        raise SystemExit("仅支持 RGB / RGBA 转换")
    return PngImage(img.width, img.height, bytes(rgb), 3)


def crop_square(img: PngImage, inset: int) -> PngImage:
    side = min(img.width, img.height) - inset * 2
    if side <= 16:
        raise SystemExit("inset 过大，裁剪后无有效区域")
    x0 = (img.width - side) // 2
    y0 = (img.height - side) // 2
    stride = img.width * 3
    out = bytearray(side * side * 3)
    for y in range(side):
        src = (y0 + y) * stride + x0 * 3
        out[y * side * 3:(y + 1) * side * 3] = img.pixels[src:src + side * 3]
    return PngImage(side, side, bytes(out), 3)


def box_resize(img: PngImage, size: int) -> PngImage:
    """面积平均降采样；放大时退化为最近邻。"""
    out = bytearray(size * size * 3)
    for y in range(size):
        y0 = y * img.height // size
        y1 = max(y0 + 1, (y + 1) * img.height // size)
        for x in range(size):
            x0 = x * img.width // size
            x1 = max(x0 + 1, (x + 1) * img.width // size)
            r = g = b = 0
            n = 0
            for yy in range(y0, y1):
                base = (yy * img.width + x0) * 3
                for xx in range(x0, x1):
                    o = base + (xx - x0) * 3
                    r += img.pixels[o]
                    g += img.pixels[o + 1]
                    b += img.pixels[o + 2]
                    n += 1
            o = (y * size + x) * 3
            out[o] = r // n
            out[o + 1] = g // n
            out[o + 2] = b // n
    return PngImage(size, size, bytes(out), 3)


def posterize(img: PngImage, step: int) -> PngImage:
    """把每个通道量化到 step 的倍数，降低熵以缩小 PNG。

    对扁平插画几乎无视觉差异，但能把文件压小 20%–40%。
    """
    if step <= 1:
        return img
    table = bytes(min(255, (v // step) * step + step // 2) for v in range(256))
    return PngImage(img.width, img.height, img.pixels.translate(table), img.channels)


def write_png(img: PngImage, path: Path) -> int:
    stride = img.width * 3
    raw = bytearray()
    for y in range(img.height):
        raw.append(0)
        raw += img.pixels[y * stride:(y + 1) * stride]

    def chunk(tag: bytes, body: bytes) -> bytes:
        return (struct.pack(">I", len(body)) + tag + body
                + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", img.width, img.height, 8, 2, 0, 0, 0)
    blob = PNG_SIG + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")
    path.write_bytes(blob)
    return len(blob)


def main() -> int:
    ap = argparse.ArgumentParser(description="头像裁剪 / 降采样 / data URI 导出")
    ap.add_argument("input")
    ap.add_argument("-o", "--output", help="输出 PNG 路径")
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--inset", type=int, default=0, help="四周各裁掉的像素数")
    ap.add_argument("--posterize", type=int, default=1, help="通道量化步长，>1 可显著缩小文件")
    ap.add_argument("--data-uri", dest="data_uri", help="把 data URI 写到该文本文件")
    args = ap.parse_args()

    img = to_rgb(read_png(Path(args.input)))
    if args.inset:
        img = crop_square(img, args.inset)
    if img.width != args.size or img.height != args.size:
        img = box_resize(img, args.size)
    if args.posterize > 1:
        img = posterize(img, args.posterize)

    if args.output:
        n = write_png(img, Path(args.output))
        print(f"输出 {args.output}  {img.width}x{img.height}  {n/1024:.1f} KB")

    if args.data_uri:
        tmp = Path(args.data_uri).with_suffix(".png")
        write_png(img, tmp)
        uri = "data:image/png;base64," + base64.b64encode(tmp.read_bytes()).decode("ascii")
        Path(args.data_uri).write_text(uri, encoding="utf-8")
        tmp.unlink(missing_ok=True)
        print(f"data URI  {len(uri)/1024:.1f} KB 文本 -> {args.data_uri}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
