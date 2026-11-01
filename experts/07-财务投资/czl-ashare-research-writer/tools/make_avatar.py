#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""原创头像生成器（零第三方依赖）。

产物：avatars/avatar.png 及 1024 / 512 / 256 三个尺寸（正方形，带 alpha）

设计说明（v1.0.1 起改为折线符号）
--------------------------------
符号：一条带两次回撤的上升折线，压在一条带刻度的基线上，末端结点用朱红收口。

- 折线：股市最不可替代的识别符号。刻意保留两次回撤——真实行情不会一路直线向上，
  一路向上的图是宣传图，不是行情图。
- 基线 + 刻度点：事实底座。结论压在证据上，这是本产品与"看图说话"的分界。
- 朱红结点：A 股「涨为红」的约定，同时当作一个句号——结论到此为止，不再多说。
- 墨绿底色：研究室的颜色。不用黑（像交易终端），不用蓝（像券商研报）。

为什么不用生成模型出图
--------------------
1. 生成模型会在角落加水印，商业包不能带第三方水印；
2. 几何图形用代码画，边缘精准、可复现、可举证为自主创作；
3. 同一脚本任意机器重跑结果一致，便于版本管理与审核。

技术：2 倍超采样后降采样得到抗锯齿边缘；PNG 用标准库 zlib 手写编码。
"""
import math
import os
import struct
import sys
import zlib

BG = (0x12, 0x3A, 0x32)         # 墨绿
CREAM = (0xF3, 0xED, 0xDD)      # 米白
VERMILION = (0xC0, 0x39, 0x2B)  # 朱红

SS = 2  # 超采样倍数

# 折线结点（1024 设计坐标系）。上升—小回—上升—回撤—上升—收高，
# 两次回撤是刻意保留的，让图形读起来像行情而不像宣传插画。
POINTS = [
    (228, 606),
    (318, 552),
    (404, 582),
    (496, 472),
    (588, 508),
    (680, 388),
    (766, 332),
]


def new_canvas(size, color):
    r, g, b = color
    return bytearray(bytes((r, g, b, 255)) * (size * size))


def fill_rect(buf, size, x0, y0, x1, y1, color):
    r, g, b = color
    x0, y0 = max(0, int(x0)), max(0, int(y0))
    x1, y1 = min(size, int(x1)), min(size, int(y1))
    if x1 <= x0 or y1 <= y0:
        return
    row = bytes((r, g, b, 255)) * (x1 - x0)
    for y in range(y0, y1):
        off = (y * size + x0) * 4
        buf[off:off + len(row)] = row


def fill_disc(buf, size, cx, cy, r, color):
    """实心圆：只遍历包围盒。"""
    rr, gg, bb = color
    r2 = r * r
    y0, y1 = int(cy - r), int(cy + r) + 1
    for y in range(max(0, y0), min(size, y1)):
        dy = y - cy
        span = r2 - dy * dy
        if span < 0:
            continue
        half = math.sqrt(span)
        sx = max(0, int(cx - half))
        ex = min(size, int(cx + half) + 1)
        if ex <= sx:
            continue
        off = (y * size + sx) * 4
        buf[off:off + (ex - sx) * 4] = bytes((rr, gg, bb, 255)) * (ex - sx)


def stroke_segment(buf, size, x0, y0, x1, y1, width, color):
    """粗线段：按点到线段的距离填充，端点自然呈圆头。只遍历包围盒。"""
    rr, gg, bb = color
    half = width / 2.0
    vx, vy = x1 - x0, y1 - y0
    seg_len2 = vx * vx + vy * vy
    bx0 = int(min(x0, x1) - half) - 1
    bx1 = int(max(x0, x1) + half) + 2
    by0 = int(min(y0, y1) - half) - 1
    by1 = int(max(y0, y1) + half) + 2
    for y in range(max(0, by0), min(size, by1)):
        for x in range(max(0, bx0), min(size, bx1)):
            px, py = x + 0.5, y + 0.5
            if seg_len2 == 0:
                t = 0.0
            else:
                t = ((px - x0) * vx + (py - y0) * vy) / seg_len2
                t = 0.0 if t < 0 else (1.0 if t > 1 else t)
            dx = px - (x0 + t * vx)
            dy = py - (y0 + t * vy)
            if dx * dx + dy * dy <= half * half:
                off = (y * size + x) * 4
                buf[off] = rr
                buf[off + 1] = gg
                buf[off + 2] = bb
                buf[off + 3] = 255


def draw_polyline(buf, size, pts, width, color):
    for i in range(len(pts) - 1):
        stroke_segment(buf, size, pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                       width, color)
    for (x, y) in (pts[0], pts[-1]):
        fill_disc(buf, size, x, y, width / 2.0, color)


def downsample(buf, size, factor):
    out_size = size // factor
    out = bytearray(out_size * out_size * 4)
    area = factor * factor
    for y in range(out_size):
        for x in range(out_size):
            rs = gs = bs = as_ = 0
            for dy in range(factor):
                base = ((y * factor + dy) * size + x * factor) * 4
                for dx in range(factor):
                    o = base + dx * 4
                    rs += buf[o]
                    gs += buf[o + 1]
                    bs += buf[o + 2]
                    as_ += buf[o + 3]
            o = (y * out_size + x) * 4
            out[o] = rs // area
            out[o + 1] = gs // area
            out[o + 2] = bs // area
            out[o + 3] = as_ // area
    return out


def write_png(path, size, rgba):
    raw = bytearray()
    stride = size * 4
    for y in range(size):
        raw.append(0)
        raw.extend(rgba[y * stride:(y + 1) * stride])

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
           chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))
    with open(path, "wb") as fh:
        fh.write(png)
    return len(png)


def render(size=1024):
    big = size * SS
    s = big / 1024.0
    buf = new_canvas(big, BG)

    # 基线（事实底座）：左右略收，避免像一条边框
    fill_rect(buf, big, 236 * s, 676 * s, 790 * s, 692 * s, CREAM)

    pts = [(x * s, y * s) for (x, y) in POINTS]
    draw_polyline(buf, big, pts, 26 * s, CREAM)

    # 末端结点：朱红实心收口
    fill_disc(buf, big, pts[-1][0], pts[-1][1], 33 * s, VERMILION)

    return downsample(buf, big, SS)


def verify(path, size):
    with open(path, "rb") as fh:
        data = fh.read()
    checks = [("PNG 签名正确", data[:8] == b"\x89PNG\r\n\x1a\n")]
    w, h = struct.unpack(">II", data[16:24])
    checks.append(("尺寸 %dx%d" % (w, h), w == size and h == size))
    checks.append(("文件非空", len(data) > 4000))

    raw = zlib.decompress(data[data.index(b"IDAT") + 4:data.index(b"IEND") - 8])
    stride = w * 4 + 1

    def px(x, y):
        o = y * stride + 1 + x * 4
        return tuple(raw[o:o + 3])

    checks.append(("四角为墨绿背景", px(8, 8) == BG))

    # 折线：沿第一段中点附近应命中米白笔画
    mid_x = int((POINTS[0][0] + POINTS[1][0]) / 2)
    mid_y = int((POINTS[0][1] + POINTS[1][1]) / 2)
    near = [(mid_x + dx, mid_y + dy) for dx in range(-16, 17) for dy in range(-16, 17)]
    checks.append(("折线中段有米白笔画", any(px(x, y) == CREAM for x, y in near)))

    checks.append(("折线整体向上", POINTS[-1][1] < POINTS[0][1] - 100))
    checks.append(("含回撤（非单调上行）",
                   any(POINTS[i + 1][1] > POINTS[i][1] for i in range(1, len(POINTS) - 1))))

    lx, ly = POINTS[-1]
    reds = [(lx + dx, ly + dy) for dx in range(-26, 27, 2) for dy in range(-26, 27, 2)]
    checks.append(("末端为朱红结点", any(px(x, y) == VERMILION for x, y in reds)))

    margin_ok = True
    for i in range(0, 1024, 64):
        for (x, y) in ((i, 20), (i, 1004), (20, i), (1004, i)):
            if px(x, y) != BG:
                margin_ok = False
                break
    checks.append(("外圈留白 ≥180px", margin_ok))

    ok = all(v for _, v in checks)
    for name, val in checks:
        print(("  PASS  " if val else "  FAIL  ") + name)
    return ok


def main():
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "avatars")
    os.makedirs(out_dir, exist_ok=True)
    for size, name in [(1024, "avatar-1024.png"), (512, "avatar-512.png"), (256, "avatar-256.png")]:
        rgba = render(size)
        path = os.path.join(out_dir, name)
        n = write_png(path, size, rgba)
        print("%s  %dx%d  %d 字节" % (path, size, size, n))

    src = os.path.join(out_dir, "avatar-1024.png")
    dst = os.path.join(out_dir, "avatar.png")
    with open(src, "rb") as fh:
        blob = fh.read()
    with open(dst, "wb") as fh:
        fh.write(blob)
    print("%s  1024x1024  (与 avatar-1024.png 同图)" % dst)

    print("\n校验 1024 主图：")
    ok = verify(src, 1024)
    print("结果：%s" % ("通过" if ok else "未通过"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
