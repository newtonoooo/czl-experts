#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""专家包自检：目录版与压缩包版都能查，重点查"导入后头像变成首字"的成因。

用法：
    python check_expert_package.py <专家目录>
    python check_expert_package.py <专家包.zip>

检查内容：
    1. 元数据必填项、双语字段、标签与推荐提示词数量
    2. 头像：字段是否指向真实文件、是否为 512×512 的 PNG、是否 ≤500KB
    3. 压缩包内头像条目是否落在客户端能解析的位置（这是"图标变文字"的主因）
    4. 压缩包是否多套了一层目录、是否混入系统垃圾文件
    5. agents / skills 路径是否有效

退出码：0 全部通过；1 有错误；2 仅有警告。
"""

import json
import os
import struct
import sys
import zipfile
from pathlib import Path

MAX_AVATAR_BYTES = 500 * 1024
MANIFEST_SUFFIX = ".codebuddy-plugin/plugin.json"
# 平台在架的学科类专家使用 15-Education；官方校验脚本的分类枚举较旧，未收录该项
KNOWN_CATEGORIES = {
    "01-ProductDesign", "02-Engineering", "03-GameSpatial", "04-DataAI",
    "05-MarketingGrowth", "06-ContentCreative", "07-SalesCommerce",
    "08-FinanceInvestment", "09-OperationsHR", "10-ProjectQuality",
    "11-SecurityCompliance", "12-IndustryConsultant", "15-Education",
}

errors = []
warnings = []
notes = []


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


def png_info(data):
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    try:
        w, h = struct.unpack(">II", data[16:24])
    except struct.error:
        return None
    return w, h, data[24], data[25]


def check_manifest(manifest, label="plugin.json"):
    for field in ("name", "version", "description"):
        if not manifest.get(field):
            err("%s 缺少必填字段 %s" % (label, field))

    name = manifest.get("name", "")
    if name and not all(c.islower() or c.isdigit() or c == "-" for c in name):
        err("%s 的 name 必须是小写字母/数字/连字符：%s" % (label, name))

    if manifest.get("plugin") and manifest["plugin"] != name:
        err("%s 的 plugin 字段与 name 不一致" % label)

    if manifest.get("expertType") not in ("agent", "team"):
        err("%s 的 expertType 必须是 agent 或 team" % label)

    for field in ("displayName", "profession", "displayDescription", "defaultInitPrompt"):
        val = manifest.get(field)
        if not isinstance(val, dict) or not val.get("zh") or not val.get("en"):
            err("%s 的 %s 需要同时有 zh 与 en" % (label, field))

    dd = (manifest.get("displayDescription") or {}).get("zh", "")
    if dd and not 40 <= len(dd) <= 50:
        warn("displayDescription.zh 为 %d 字（建议 40—50 字）" % len(dd))

    if len(manifest.get("tags") or []) != 3:
        err("%s 的 tags 必须正好 3 个" % label)
    qp = manifest.get("quickPrompts") or []
    if len(qp) != 3:
        err("%s 的 quickPrompts 必须正好 3 个" % label)
    if qp and (manifest.get("defaultInitPrompt") or {}).get("zh") != (qp[0] or {}).get("zh"):
        warn("defaultInitPrompt.zh 应与 quickPrompts[0].zh 一致")

    cat = manifest.get("categoryId", "")
    if cat not in KNOWN_CATEGORIES:
        err("%s 的 categoryId 不在已知分类中：%s" % (label, cat))
    elif cat == "15-Education":
        notes.append("categoryId 使用 15-Education（平台学科类专家通用）；官方 validate_expert.py 的枚举未收录该项，会误报，可忽略。")


def check_avatar_bytes(data, label):
    info = png_info(data)
    if not info:
        err("%s 不是有效 PNG（部分客户端会解码失败，退化为首字占位）" % label)
        return
    w, h, depth, color = info
    if (w, h) != (512, 512):
        warn("%s 尺寸为 %dx%d，建议 512x512" % (label, w, h))
    if depth != 8:
        warn("%s 位深为 %d，建议 8" % (label, depth))
    if color not in (2, 6):
        warn("%s 色彩类型为 %d，建议 RGB(2) 或 RGBA(6)" % (label, color))
    if len(data) > MAX_AVATAR_BYTES:
        err("%s 为 %.0f KB，超过 500KB 上限" % (label, len(data) / 1024))


def check_dir(root):
    manifest_path = root / ".codebuddy-plugin" / "plugin.json"
    if not manifest_path.exists():
        manifest_path = root / ".workbuddy-plugin" / "plugin.json"
    if not manifest_path.exists():
        err("找不到 .codebuddy-plugin/plugin.json")
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    check_manifest(manifest)

    agent_name = manifest.get("agentName", "")
    agent_md = root / "agents" / (agent_name + ".md")
    if not agent_md.exists():
        err("agentName 指向的文件不存在：agents/%s.md" % agent_name)

    def strip_prefix(rel):
        return rel[2:] if rel.startswith("./") else rel

    for rel in manifest.get("agents") or []:
        if not (root / strip_prefix(rel)).exists():
            err("agents 路径不存在：%s" % rel)
    for rel in manifest.get("skills") or []:
        p = root / strip_prefix(rel) / "SKILL.md"
        if not p.exists():
            err("skills 路径缺少 SKILL.md：%s" % rel)

    avatar = manifest.get("avatar", "")
    if not avatar:
        err("avatar 字段为空——客户端会直接显示名称首字")
    else:
        ap = root / avatar
        if not ap.exists():
            err("avatar 指向的文件不存在：%s（导入后必然显示首字）" % avatar)
        else:
            check_avatar_bytes(ap.read_bytes(), avatar)
            if avatar.startswith("./") or avatar.startswith("/"):
                warn("avatar 建议写成相对路径且不带前缀，如 avatars/expert.png")


def check_zip(zpath):
    if not zipfile.is_zipfile(zpath):
        err("不是有效的 zip 文件")
        return
    with zipfile.ZipFile(zpath) as z:
        names = [n for n in z.namelist() if not n.endswith("/")]
        manifests = [n for n in names if n.endswith(MANIFEST_SUFFIX)]
        if not manifests:
            err("压缩包内找不到 .codebuddy-plugin/plugin.json")
            return
        if len(manifests) > 1:
            warn("压缩包内有多个 plugin.json：%s" % manifests)

        entry = manifests[0]
        base = entry[:-len(MANIFEST_SUFFIX)].rstrip("/")
        manifest = json.loads(z.read(entry).decode("utf-8"))
        check_manifest(manifest, "zip 内 plugin.json")

        if base:
            notes.append("压缩包顶层目录为 %s/（一层，正常）" % base)
        top_dirs = {n.split("/")[0] for n in names}
        if base and len(top_dirs) > 1:
            warn("压缩包顶层出现多个目录：%s（多余目录会被一并解出）" % sorted(top_dirs))

        avatar = manifest.get("avatar", "")
        if not avatar:
            err("zip 内 avatar 字段为空，导入后显示首字")
        else:
            rel = avatar.lstrip("./").lstrip("/")
            candidates = [("%s/%s" % (base, rel)) if base else rel, rel]
            hit = next((c for c in candidates if c in names), None)
            if not hit:
                err("压缩包内找不到头像条目 %s——客户端会把 avatar 原样当成相对路径，"
                    "取不到文件就退化为名称首字（这正是“图标变文字”的典型成因）" % candidates[0])
            else:
                check_avatar_bytes(z.read(hit), hit)

        junk = [n for n in names if n.startswith("__MACOSX/") or n.endswith(".DS_Store")
                or n.endswith("Thumbs.db") or n.startswith("._")]
        if junk:
            warn("压缩包内有系统垃圾文件 %d 个，建议清理" % len(junk))

        if not any(n.endswith("/SKILL.md") for n in names):
            warn("压缩包内没有技能文件；若 plugin.json 声明了 skills，导入后调用会失败")
        if not any(n.startswith((base + "/agents/") if base else "agents/") for n in names):
            err("压缩包内缺少 agents/ 目录")


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    target = Path(sys.argv[1]).expanduser().resolve()
    if not target.exists():
        print("路径不存在：%s" % target)
        return 1

    print("检查：%s\n" % target)
    if target.is_dir():
        check_dir(target)
    elif target.suffix.lower() == ".zip":
        check_zip(target)
    else:
        print("只支持专家目录或 .zip")
        return 1

    for n in notes:
        print("· " + n)
    for w in warnings:
        print("⚠ " + w)
    for e in errors:
        print("✗ " + e)

    if errors:
        print("\n结论：%d 项错误，%d 项警告" % (len(errors), len(warnings)))
        return 1
    if warnings:
        print("\n结论：通过，%d 项警告" % len(warnings))
        return 2
    print("\n结论：全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
