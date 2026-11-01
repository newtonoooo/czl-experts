#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""卓识化学 · 头像显示诊断器（"导入后图标变成文字"专用）

用它可以判断某个专家包的头像为什么没显示。诊断依据来自 WorkBuddy 桌面端
（app.asar）里四条不同的头像解析路径，本脚本复刻了这些判定条件。

用法：
    python tools/doctor_avatar.py <专家包目录>
    python tools/doctor_avatar.py <专家包目录> --installed

退出码：0 头像可正常显示；1 存在会导致"变文字"的问题。
"""

from __future__ import annotations

import base64
import json
import os
import struct
import sys

MAX_AVATAR_BYTES = 5 * 1024 * 1024  # 客户端上限：5 MB
ABS_SCHEME = ("http://", "https://", "file:", "data:", "local-file:", "blob:")


def png_size(data: bytes):
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", data[16:24])


def load_manifest(root: str):
    for meta in (".codebuddy-plugin", ".workbuddy-plugin"):
        p = os.path.join(root, meta, "plugin.json")
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                return p, json.load(f)
    return None, None


def is_inside(child: str, parent: str) -> bool:
    child, parent = os.path.abspath(child), os.path.abspath(parent)
    return child == parent or child.startswith(parent + os.sep)


def find_installed_experts(config_dir: str):
    """扫描所有已安装专家的 displayName，用于查重。"""
    base = os.path.join(config_dir, "plugins", "marketplaces")
    out = []
    if not os.path.isdir(base):
        return out
    for mp in os.listdir(base):
        pdir = os.path.join(base, mp, "plugins")
        if not os.path.isdir(pdir):
            continue
        for pid in os.listdir(pdir):
            mp_path, man = load_manifest(os.path.join(pdir, pid))
            if man:
                dn = man.get("displayName")
                zh = dn.get("zh") if isinstance(dn, dict) else str(dn or "")
                out.append((mp, pid, zh, os.path.join(pdir, pid)))
    return out


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    installed_mode = "--installed" in sys.argv
    if not args:
        print(__doc__)
        return 2
    root = os.path.abspath(args[0])
    if not os.path.isdir(root):
        print(f"目录不存在：{root}")
        return 2

    print("=" * 70)
    print(f"头像诊断：{root}")
    print("=" * 70)

    manifest_path, m = load_manifest(root)
    if not m:
        print("[FAIL] 找不到 .codebuddy-plugin/plugin.json —— 包结构不对，客户端根本不会注册这个专家。")
        return 1
    print(f"[OK]   清单：{os.path.relpath(manifest_path, root)}")

    avatar = m.get("avatar", "")
    problems = []
    print(f"[INFO] avatar 字段类型：{'data URL' if str(avatar).startswith('data:') else ('URL' if str(avatar).lower().startswith(ABS_SCHEME) else '相对路径')}")
    print(f"[INFO] avatar 字段长度：{len(str(avatar))} 字符")

    if not avatar:
        problems.append("avatar 字段为空 —— 客户端会直接用名字首字作为占位图标（就是'成字'）。")
        verdict = "成文字"
    elif str(avatar).startswith("data:image/"):
        try:
            b64 = str(avatar).split(",", 1)[1]
            blob = base64.b64decode(b64, validate=True)
        except Exception as e:  # noqa: BLE001
            problems.append(f"data URL 的 base64 解不开：{e}")
            blob = b""
        size = png_size(blob) if blob else None
        if size:
            w, h = size
            print(f"[OK]   内嵌 PNG：{w}x{h}，{len(blob)/1024:.1f} KB")
            if w != h:
                problems.append(f"头像不是正方形（{w}x{h}），部分界面会裁切变形")
            if len(blob) > MAX_AVATAR_BYTES:
                problems.append("头像字节数超过 5 MB，客户端 resolveAvatarUrl 会返回空字符串 → 成文字")
        else:
            problems.append("data URL 解码后不是有效 PNG（可能被截断）")
        verdict = "可显示（data URL 在所有渲染路径都被直接采用）"
    elif str(avatar).lower().startswith(("http://", "https://")):
        print("[INFO] 使用远程 URL。本地诊断无法验证该 URL 是否可访问。")
        problems.append("远程 URL 需确认可公开访问且无防盗链，否则同样会回退成文字。")
        verdict = "取决于远程可达性"
    elif str(avatar).lower().startswith(("file:", "local-file:", "blob:")):
        print("[INFO] 使用本地绝对路径。换机器/换盘符后会失效。")
        verdict = "本机可用，跨机不可用"
    else:
        rel = str(avatar).lstrip("./").replace("\\", "/")
        target = os.path.abspath(os.path.join(root, rel))
        print(f"[INFO] 相对路径解析为：{target}")
        if not is_inside(target, root):
            problems.append("头像路径跑到专家目录之外（客户端 isPathWithin 会判空）→ 成文字")
        if not os.path.isfile(target):
            problems.append("头像文件不存在。zip 打包时漏了 avatars/ 目录、或路径大小写不一致，都会导致这一条。")
            verdict = "成文字"
        else:
            sz = os.path.getsize(target)
            print(f"[OK]   文件存在：{sz/1024:.1f} KB")
            with open(target, "rb") as f:
                head = f.read(33)
            size = png_size(head)
            if size:
                print(f"[OK]   PNG 尺寸：{size[0]}x{size[1]}")
                if size[0] != size[1]:
                    problems.append("头像不是正方形")
                if size[0] < 128:
                    problems.append("头像小于 128px，列表里会糊")
            else:
                print("[WARN] 不是 PNG（若为 JPG/WebP，需确认客户端 MIME 判断是否放行）")
            if sz > MAX_AVATAR_BYTES:
                problems.append("文件超过 5 MB → 客户端直接返回空 → 成文字")
            verdict = "相对路径：仅在'我的专家'目录下会被后端转成 data URL；在市场/插件列表里会被当成 CDN 路径"

    # 安装位置判断
    print("-" * 70)
    cfg = os.path.expanduser("~/.workbuddy")
    mp_root = os.path.join(cfg, "plugins", "marketplaces")
    location = "未知"
    if is_inside(root, mp_root):
        rel = os.path.relpath(root, mp_root).replace("\\", "/")
        location = rel.split("/")[0]
    print(f"[INFO] 安装位置 marketplace：{location}")
    if location == "my-experts":
        print("[OK]   位于 my-experts：客户端读取时会先把相对路径头像转成 data URL，通常能显示。")
    elif location not in ("未知",):
        print("[WARN] 不在 my-experts 下：市场/插件列表渲染会把相对路径拼成 CDN 地址，")
        print("       私有包没有对应的 CDN 对象，图片 404 → 回退成名字首字。")
        if not str(avatar).startswith("data:"):
            problems.append("安装在非 my-experts 目录且使用的是相对路径头像 → 列表小图标会变成文字。")
    else:
        print("[NOTE] 该目录不在已安装位置（打包/开发目录），无法判断最终安装到哪个 marketplace。")
        if not str(avatar).startswith("data:") and not str(avatar).lower().startswith(ABS_SCHEME):
            print("[NOTE] 当前为相对路径：这是市场提交的合规写法（平台认扩展名），上架后头像由平台传到 CDN，正常显示。")
            print("       只有在本地用 zip 私有导入、且客户端把它当 CDN 路径处理时，才会回退成名字首字。")
            verdict = "提交态合规（本地私有导入可能显示为文字，可临时切 embed 验证）"

    # 名字查重（同名会导致列表里难分辨，也是"看起来没图标"的常见误判）
    experts = find_installed_experts(cfg)
    dn = m.get("displayName")
    zh = dn.get("zh") if isinstance(dn, dict) else str(dn or "")
    same = [e for e in experts if e[2] == zh and os.path.abspath(e[3]) != root]
    print("-" * 70)
    if same:
        print(f"[WARN] 显示名「{zh}」与另外 {len(same)} 个已安装专家重复：")
        for mp, pid, _zh, path in same[:8]:
            print(f"       - {pid}  ({mp})")
        problems.append("显示名重复，列表/会话里容易认错，也是'图标不对'的常见来源。")
    else:
        print(f"[OK]   显示名「{zh}」在本机已安装专家中唯一。")

    # 结论
    print("=" * 70)
    print(f"判定：{verdict}")
    if problems:
        print("发现的问题：")
        for i, p in enumerate(problems, 1):
            print(f"  {i}. {p}")
        print()
        print("修复建议：")
        print("  A. 要提交市场上架：必须用相对路径 + png/jpg/webp 扩展名")
        print("     python tools/avatar_mode.py --mode relative")
        print("     （平台校验只认扩展名，data URL 会被判为『（无扩展名）』）")
        print("  B. 只在本地看图标：可临时内嵌")
        print("     python tools/avatar_mode.py --mode embed（提交前记得切回 relative）")
        print("  C. 检查 zip：必须包含 avatars/ 目录，且 .codebuddy-plugin/plugin.json 在顶层目录内。")
        return 1
    print("未发现会导致图标消失的问题。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
