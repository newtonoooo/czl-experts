#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""头像体检：在打包前判断"导入到别的 WorkBuddy 后会不会变成首字色块"。

为什么要这个脚本
----------------
WorkBuddy 客户端解析自定义专家头像的规则（主进程 resolveAvatarUrl）是：
    1. 空值 -> 空字符串
    2. 以 http(s)/data: 开头 -> 直接使用
    3. 其余去掉开头的 "./" 后，相对**专家包根目录**解析
    4. 解析结果越出包根 -> 空字符串
    5. 文件不存在 -> 空字符串
    6. 文件存在 -> 转成 local-file:// 地址

拿到空字符串后，前端不报错，直接用"名字第一个字 + 色块"顶上。
也就是说：路径写错、文件缺失、大小写不一致，界面上只会安静地变成一个汉字，
没有任何提示。本脚本把这六条逐条验一遍，把"安静失败"变成"打包前报错"。

用法:
    python tools/verify_avatar.py .
退出码: 0 通过；1 存在问题。
"""

import json
import struct
import sys
from pathlib import Path

PNG_SIG = b"\x89PNG\r\n\x1a\n"
JPEG_SIG = b"\xff\xd8\xff"
MAX_BYTES = 500 * 1024
REQUIRED_SIDE = 512


def png_size(data):
    if len(data) < 33 or not data.startswith(PNG_SIG):
        return None
    # IHDR 紧跟签名，宽高在第 16..24 字节
    width, height = struct.unpack(">II", data[16:24])
    depth, color = data[24], data[25]
    return width, height, depth, color


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    problems, notes = [], []

    manifest = root / ".codebuddy-plugin" / "plugin.json"
    if not manifest.exists():
        print(f"❌ 找不到 {manifest}")
        return 1

    data = json.loads(manifest.read_text(encoding="utf-8"))
    avatar = data.get("avatar", "")

    # 规则 1：字段非空
    if not avatar:
        problems.append("plugin.json 的 avatar 字段为空 —— 界面必然显示首字色块")
        avatar = ""

    # 规则 2：协议地址（换机器也能用，但需要联网或内嵌）
    if avatar.startswith(("http://", "https://", "data:")):
        notes.append(f"avatar 使用外部地址（{avatar[:40]}…），换网络环境可能加载失败，建议改为包内相对路径")

    # 规则 3/4：越界检查
    target = None
    if avatar and not avatar.startswith(("http://", "https://", "data:")):
        if avatar.startswith(("./", ".\\")):
            problems.append("avatar 不应以 './' 开头（客户端虽然会剥掉，但部分解析路径会失败）")
        if avatar.startswith(("file:", "local-file:")):
            problems.append("avatar 不能写 file:// 或 local-file:// —— 换机器必挂")
        if len(avatar) > 1 and avatar[1] == ":":
            problems.append("avatar 不能写绝对路径（盘符）—— 换机器必挂")
        if "\\" in avatar:
            problems.append("avatar 路径请用正斜杠 '/'，反斜杠在非 Windows 端会解析失败")
        if any(ord(c) > 127 for c in avatar):
            problems.append("avatar 路径含非 ASCII 字符，URL 编码不一致时可能解析失败")
        if avatar != avatar.lower():
            notes.append("avatar 路径含大写字母；Windows 能读、Linux/macOS 读不到，建议全小写")

        target = (root / avatar.lstrip("./")).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            problems.append(f"avatar 路径越出专家包根目录：{target}")
            target = None

    # 规则 5：文件存在
    if avatar and not avatar.startswith(("http://", "https://", "data:")):
        if target and not target.exists():
            problems.append(f"avatar 指向的文件不存在：{avatar} —— 这是最常见的'变字'原因")
            siblings = sorted(p.name for p in (root / "avatars").glob("*")) if (root / "avatars").exists() else []
            if siblings:
                problems.append(f"avatars/ 目录里实际有：{siblings}（名字要和 avatar 字段完全一致）")
            else:
                problems.append("avatars/ 目录为空或不存在 —— zip 不会保存空目录，导入后头像必然丢失")
        elif target and target.exists():
            blob = target.read_bytes()
            size_kb = len(blob) / 1024
            if blob.startswith(PNG_SIG):
                info = png_size(blob)
                w, h, depth, color = info
                if (w, h) != (REQUIRED_SIDE, REQUIRED_SIDE):
                    problems.append(f"头像尺寸 {w}x{h}，规范要求 {REQUIRED_SIDE}x{REQUIRED_SIDE}")
                if depth != 8:
                    problems.append(f"位深 {depth}，建议 8 位，避免部分解码器不支持")
                if color not in (2, 6):
                    notes.append(f"PNG 色彩类型 {color}（调色板/灰度），多数端可解码，但 RGB(2) 最稳")
            elif blob.startswith(JPEG_SIG):
                notes.append("头像是 JPG；规范推荐 PNG，JPG 在圆角裁剪时边缘会有压缩噪点")
            else:
                problems.append("头像文件既不是 PNG 也不是 JPG，客户端可能无法解码")
            if len(blob) > MAX_BYTES:
                problems.append(f"头像 {size_kb:.0f}KB，超过 {MAX_BYTES // 1024}KB 上限")

    # 额外：检查是否有残留的大图或占位文件会被一起打包
    extra = [p.name for p in (root / "avatars").glob("*")
             if p.is_file() and p.name != Path(avatar).name and not p.name.startswith(".")]
    if extra:
        notes.append(f"avatars/ 里还有多余文件会被一起打包：{extra}")

    print(f"🔍 头像体检：{root.name}")
    print(f"   avatar 字段：{avatar!r}")
    for n in notes:
        print(f"   ⚠️  {n}")
    if problems:
        for p in problems:
            print(f"   ❌ {p}")
        print("\n结论：导入到其他 WorkBuddy 后，头像很可能显示成「名字首字」，请先修复。")
        return 1

    print("   ✅ 通过：路径合法、文件存在、尺寸与体积合规")
    return 0


if __name__ == "__main__":
    sys.exit(main())
