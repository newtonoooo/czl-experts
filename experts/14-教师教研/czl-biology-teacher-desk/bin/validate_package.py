#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate_package.py — 专家包自检（发布前跑一遍）

比平台脚本多查几项，专治"导入后打不开/图标变文字/引用丢失"：
    1. 清单位置与必填字段
    2. agentName 与 agents/*.md 是否对得上
    3. avatar 字段指向的文件是否存在、是否为合法 PNG/JPG、尺寸与体积是否超标
    4. agents / skills / knowledge 里声明的路径是否真实存在
    5. 工作流文件数量与编号连续性
    6. 是否残留 [TODO] 占位符
    7. 是否误打包 .bak / 原始大图 / 缓存目录

用法：
    python validate_package.py <专家目录>
退出码：0 通过（可带警告）；1 有错误。
"""

import json
import os
import struct
import sys
from typing import List, Tuple

REQUIRED_TOP = ["name", "version", "description", "author", "agents", "expertType", "agentName",
                "displayName", "profession", "displayDescription", "avatar", "categoryId",
                "defaultInitPrompt", "plugin", "tags", "quickPrompts"]
KNOWN_CATEGORIES = {
    "01-ProductDesign", "02-Engineering", "03-GameSpatial", "04-DataAI", "05-MarketingGrowth",
    "06-ContentCreative", "07-SalesCommerce", "08-FinanceInvestment", "09-OperationsHR",
    "10-ProjectQuality", "11-SecurityCompliance", "12-IndustryConsultant",
    "13-Lifestyle", "14-Media", "15-Education",
}


def png_size(path: str) -> Tuple[int, int]:
    with open(path, "rb") as fh:
        head = fh.read(33)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("不是 PNG")
    w, h = struct.unpack(">II", head[16:24])
    return w, h


def jpg_size(path: str) -> Tuple[int, int]:
    with open(path, "rb") as fh:
        data = fh.read()
    i = 2
    while i < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h
        seg_len = struct.unpack(">H", data[i + 2:i + 4])[0]
        i += 2 + seg_len
    raise ValueError("不是 JPG")


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python validate_package.py <专家目录>", file=sys.stderr)
        return 2
    root = os.path.abspath(sys.argv[1])
    errors: List[str] = []
    warnings: List[str] = []

    manifest = None
    for meta in (".codebuddy-plugin", ".workbuddy-plugin"):
        p = os.path.join(root, meta, "plugin.json")
        if os.path.exists(p):
            manifest = p
            break
    if not manifest:
        print("[错误] 缺少 .codebuddy-plugin/plugin.json", file=sys.stderr)
        return 1

    with open(manifest, "r", encoding="utf-8") as fh:
        raw = fh.read()
    if "[TODO" in raw:
        errors.append("plugin.json 残留 [TODO] 占位符")
    data = json.loads(raw)

    for f in REQUIRED_TOP:
        if f not in data or data[f] in ("", None, [], {}):
            errors.append(f"缺少必填字段 {f}")

    if data.get("plugin") and data["plugin"] != data.get("name"):
        errors.append("plugin 与 name 不一致")
    if data.get("expertType") not in ("agent", "team"):
        errors.append("expertType 必须为 agent 或 team")

    agent_name = data.get("agentName", "")
    agent_md = os.path.join(root, "agents", f"{agent_name}.md")
    if not os.path.exists(agent_md):
        errors.append(f"agentName 对应文件不存在: agents/{agent_name}.md")
    else:
        with open(agent_md, "r", encoding="utf-8") as fh:
            body = fh.read()
        if not body.startswith("---"):
            errors.append("agent MD 缺少 frontmatter")
        else:
            parts = body.split("---")
            if len(parts) >= 3 and "tools:" in parts[1]:
                errors.append("agent MD frontmatter 不应声明 tools")
        if "[TODO" in body:
            errors.append("agent MD 残留 [TODO] 占位符")

    # 资源声明
    for key in ("agents", "skills", "knowledge"):
        for rel in data.get(key, []) or []:
            target = os.path.normpath(os.path.join(root, rel))
            if not os.path.exists(target):
                errors.append(f"{key} 声明的路径不存在: {rel}")

    # 头像
    avatar = data.get("avatar", "")
    if avatar.startswith("data:image/"):
        warnings.append("avatar 使用 data URI（仅本机可见，上架前请改回相对路径）")
    else:
        path = os.path.join(root, avatar)
        if not os.path.exists(path):
            errors.append(f"头像文件不存在: {avatar}")
        else:
            size_kb = os.path.getsize(path) / 1024
            if size_kb > 500:
                errors.append(f"头像体积 {size_kb:.0f} KB 超过 500 KB")
            try:
                w, h = png_size(path) if path.lower().endswith(".png") else jpg_size(path)
                if abs(w - h) > 2:
                    warnings.append(f"头像不是正方形: {w}x{h}")
                if max(w, h) < 256:
                    warnings.append(f"头像分辨率偏低: {w}x{h}")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"头像文件无法解析: {exc}")

    # 工作流
    wf_dir = os.path.join(root, "workflows")
    if os.path.isdir(wf_dir):
        files = sorted(f for f in os.listdir(wf_dir) if f.endswith(".md"))
        if not files:
            warnings.append("workflows 目录为空")
        for i, f in enumerate(files, start=1):
            if not f.startswith(f"W{i}-"):
                warnings.append(f"工作流编号不连续: {f}")
    else:
        warnings.append("没有 workflows 目录")

    # 垃圾文件
    for dirpath, dirnames, filenames in os.walk(root):
        for f in filenames:
            if f.endswith((".bak", ".tmp")) or f in (".DS_Store", "Thumbs.db"):
                warnings.append(f"疑似临时文件: {os.path.relpath(os.path.join(dirpath, f), root)}")
        for d in list(dirnames):
            if d in ("__pycache__", "node_modules", ".git"):
                warnings.append(f"疑似缓存目录: {os.path.relpath(os.path.join(dirpath, d), root)}")

    cat = data.get("categoryId", "")
    if cat and cat not in KNOWN_CATEGORIES:
        warnings.append(f"categoryId '{cat}' 不在已知分类集合内")

    for t in data.get("tags", []):
        if not isinstance(t, dict) or "zh" not in t:
            errors.append("tags 结构不正确")
            break
    if len(data.get("tags", [])) != 3:
        errors.append(f"tags 必须为 3 个，当前 {len(data.get('tags', []))}")
    if len(data.get("quickPrompts", [])) != 3:
        errors.append(f"quickPrompts 必须为 3 个，当前 {len(data.get('quickPrompts', []))}")
    if data.get("quickPrompts") and data.get("defaultInitPrompt"):
        if data["quickPrompts"][0].get("zh") != data["defaultInitPrompt"].get("zh"):
            warnings.append("defaultInitPrompt 与 quickPrompts 第一条不一致")

    print(f"检查目录: {root}")
    print(f"专家: {data.get('displayName', {}).get('zh')}（{data.get('name')}）v{data.get('version')}")
    for w in warnings:
        print(f"[警告] {w}")
    for e in errors:
        print(f"[错误] {e}")
    print(f"结论：{'通过' if not errors else '不通过'}"
          f"（错误 {len(errors)}，警告 {len(warnings)}）")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
