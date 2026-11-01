"""生成专家头像（原创矢量绘制，无第三方素材）。

设计说明：
- 六边形环 = 六维诊断框架；
- 环内三根递增柱 = 同一标的的多维对照，末根琥珀色 = 需要额外关注的那一维；
- 深蓝绿底 + 薄荷绿线，避免和常见"金币/牛/西装人物"类金融头像撞脸；
- 全部元素用几何图形绘制，1024 绘制、512 输出，保证列表小尺寸下仍可辨识。

运行：
    python tools/make_avatar.py
输出：
    avatars/expert.png（512×512 PNG）
    avatars/expert_1024.png（1024×1024，备用）
    avatars/avatar_data_uri.txt（Base64 data URI，供 plugin.json 内联）

依赖：Pillow（仅生成资源时需要，技能运行时不需要）。
"""

from __future__ import annotations

import base64
import math
import os

from PIL import Image, ImageDraw, ImageFilter

S = 1024          # 绘制尺寸
SS = 2            # 超采样倍数
W = S * SS

BG_TOP = (9, 27, 39)
BG_BOTTOM = (17, 66, 76)
MINT = (63, 224, 176)
AMBER = (255, 197, 92)
WHITE = (240, 250, 250)


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def gradient(size):
    img = Image.new("RGB", (size, size), BG_TOP)
    d = ImageDraw.Draw(img)
    for y in range(size):
        t = y / (size - 1)
        d.line([(0, y), (size, y)], fill=lerp(BG_TOP, BG_BOTTOM, t ** 0.9))
    return img


def hex_points(cx, cy, r, rot=math.pi / 6):
    return [(cx + r * math.cos(rot + i * math.pi / 3), cy + r * math.sin(rot + i * math.pi / 3))
            for i in range(6)]


def rounded_mask(size, radius):
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return m


def build():
    base = gradient(W).convert("RGBA")

    # 背后柔光，让中心主体亮起来（低对比，不抢图形）
    glow = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([W * 0.18, W * 0.16, W * 0.82, W * 0.80], fill=(38, 150, 146, 90))
    glow = glow.filter(ImageFilter.GaussianBlur(W * 0.10))
    base = Image.alpha_composite(base, glow)

    layer = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    cx = cy = W / 2
    r_inner = W * 0.330

    # 主环：单一六边形，够粗，小尺寸下才立得住（双环在 36px 会糊成灰边）
    pts = hex_points(cx, cy, r_inner)
    d.line(pts + [pts[0]], fill=MINT + (238,), width=int(W * 0.023), joint="curve")

    # 六个顶点圆点：强调"六个维度各自有位置"，只有右下角那颗用琥珀色（对应末根柱）
    for i, (x, y) in enumerate(pts):
        rad = W * (0.019 if i != 0 else 0.024)
        fill = AMBER + (255,) if i == 0 else MINT + (255,)
        d.ellipse([x - rad, y - rad, x + rad, y + rad], fill=fill)

    # 环内三根柱：底部对齐，高度递增，占满环内高度的一半以上
    bar_w = W * 0.064
    gap = W * 0.040
    base_y = cy + W * 0.140
    heights = (W * 0.170, W * 0.265, W * 0.370)
    total_w = bar_w * 3 + gap * 2
    x0 = cx - total_w / 2
    colors = (WHITE + (205,), WHITE + (240,), AMBER + (255,))
    for i, h in enumerate(heights):
        x = x0 + i * (bar_w + gap)
        top = base_y - h
        d.rounded_rectangle([x, top, x + bar_w, base_y], radius=bar_w * 0.30, fill=colors[i])

    # 柱底一条基线，收住图形
    d.line([(x0 - W * 0.026, base_y + W * 0.016), (x0 + total_w + W * 0.026, base_y + W * 0.016)],
           fill=(255, 255, 255, 110), width=int(W * 0.007))

    base = Image.alpha_composite(base, layer)

    # 圆角方形裁切（平台列表多为圆角容器，方角在深色底上会露出硬边）
    mask = rounded_mask(W, int(W * 0.215))
    out = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    out.paste(base, (0, 0), mask)
    return out


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    ava = os.path.join(root, "avatars")
    os.makedirs(ava, exist_ok=True)

    img = build()
    big = img.resize((S, S), Image.LANCZOS)
    small = img.resize((512, 512), Image.LANCZOS)

    p_big = os.path.join(ava, "expert_1024.png")
    p_small = os.path.join(ava, "expert.png")
    big.save(p_big, "PNG", optimize=True)
    small.save(p_small, "PNG", optimize=True)

    raw = open(p_small, "rb").read()
    uri = "data:image/png;base64," + base64.b64encode(raw).decode("ascii")
    with open(os.path.join(ava, "avatar_data_uri.txt"), "w", encoding="utf-8") as fh:
        fh.write(uri)

    print("avatar png:", p_small, len(raw), "bytes")
    print("avatar 1024:", p_big, os.path.getsize(p_big), "bytes")
    print("data uri chars:", len(uri))


if __name__ == "__main__":
    main()
