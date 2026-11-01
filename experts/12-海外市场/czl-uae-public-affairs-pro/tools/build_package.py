#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""专家包构建与体检工具（czl-uae-public-affairs-pro）

做三件事：
1. 结构体检：字段、引用路径、头像规格、TODO 残留、MD frontmatter
2. 打包：生成顶层目录唯一的 zip（顶层目录名 == plugin.name）
3. 回读体检：重新打开 zip，按 WorkBuddy 客户端的解析规则验证头像可命中

用法:
    python build_package.py check  <expert-dir>
    python build_package.py build  <expert-dir> [输出目录]
    python build_package.py verify <zip路径>

退出码: 0 通过; 1 失败。
"""

import json
import os
import re
import struct
import sys
import zipfile

REQUIRED_PLUGIN_FIELDS = ["name", "version", "description", "expertType", "agentName",
                          "displayName", "profession", "displayDescription", "avatar",
                          "categoryId", "tags", "quickPrompts", "plugin"]
VALID_CATEGORY = {
    "01-ProductDesign", "02-Engineering", "03-GameSpatial", "04-DataAI",
    "05-MarketingGrowth", "06-ContentCreative", "07-SalesCommerce",
    "08-FinanceInvestment", "09-OperationsHR", "10-ProjectQuality",
    "11-SecurityCompliance", "12-IndustryConsultant",
}
MAX_AVATAR_BYTES = 500 * 1024


class Report:
    def __init__(self):
        self.errors = []
        self.warns = []
        self.notes = []

    def err(self, m):
        self.errors.append(m)

    def warn(self, m):
        self.warns.append(m)

    def note(self, m):
        self.notes.append(m)

    @property
    def ok(self):
        return not self.errors

    def dump(self):
        for n in self.notes:
            print("  · %s" % n)
        for w in self.warns:
            print("  ⚠ %s" % w)
        for e in self.errors:
            print("  ✗ %s" % e)
        print()
        if self.ok:
            print("  ✅ 结构体检通过（%d 项警告）" % len(self.warns))
        else:
            print("  ❌ 结构体检未通过：%d 个错误 / %d 个警告" % (len(self.errors), len(self.warns)))


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    w, h = struct.unpack(">II", head[16:24])
    return w, h


def check_dir(root):
    r = Report()
    root = os.path.abspath(root)
    pj_path = os.path.join(root, ".codebuddy-plugin", "plugin.json")
    if not os.path.exists(pj_path):
        r.err("缺少 .codebuddy-plugin/plugin.json")
        return r, None

    try:
        with open(pj_path, encoding="utf-8") as f:
            pj = json.load(f)
    except json.JSONDecodeError as e:
        r.err("plugin.json 不是合法 JSON: %s" % e)
        return r, None

    for field in REQUIRED_PLUGIN_FIELDS:
        if field not in pj:
            r.err("plugin.json 缺少字段: %s" % field)
    for field in ("displayName", "profession", "displayDescription", "defaultInitPrompt"):
        v = pj.get(field)
        if not isinstance(v, dict) or not v.get("en") or not v.get("zh"):
            r.err("%s 必须同时有 en/zh" % field)

    name = pj.get("name", "")
    if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", name or ""):
        r.err("name 必须是 kebab-case: %r" % name)
    if pj.get("plugin") and pj["plugin"] != name:
        r.err("plugin 字段必须等于 name")
    if pj.get("categoryId") not in VALID_CATEGORY:
        r.err("categoryId 非法: %r" % pj.get("categoryId"))
    if len(pj.get("tags", [])) != 3:
        r.err("tags 必须正好 3 个，当前 %d" % len(pj.get("tags", [])))
    if len(pj.get("quickPrompts", [])) != 3:
        r.err("quickPrompts 必须正好 3 个，当前 %d" % len(pj.get("quickPrompts", [])))
    dip = pj.get("defaultInitPrompt", {})
    qp = pj.get("quickPrompts", [{}])
    if qp and isinstance(qp[0], dict) and dip.get("zh") != qp[0].get("zh"):
        r.warn("defaultInitPrompt.zh 与 quickPrompts[0].zh 不一致")
    dd = (pj.get("displayDescription") or {}).get("zh", "")
    if not (40 <= len(dd) <= 50):
        r.warn("displayDescription.zh 长度 %d（建议 40-50）" % len(dd))

    # agentName == MD 文件名
    agent_name = pj.get("agentName", "")
    md_rel = os.path.join("agents", agent_name + ".md")
    if not os.path.exists(os.path.join(root, md_rel)):
        r.err("agentName 对应的 MD 不存在: %s" % md_rel)
    else:
        content = open(os.path.join(root, md_rel), encoding="utf-8").read()
        m = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not m:
            r.err("%s 缺少 YAML frontmatter" % md_rel)
        else:
            fm = m.group(1)
            if "tools:" in fm:
                r.err("%s frontmatter 不得包含 tools 字段" % md_rel)
            nm = re.search(r"^name:\s*(\S+)", fm, re.M)
            if nm and nm.group(1).strip('"\'') != agent_name:
                r.err("%s frontmatter name 与文件名不一致" % md_rel)
            if not re.search(r"^description:", fm, re.M):
                r.warn("%s frontmatter 缺少 description" % md_rel)

    # agents / skills 声明路径
    for p in pj.get("agents", []):
        rel = p[2:] if p.startswith("./") else p
        if not os.path.exists(os.path.join(root, rel)):
            r.err("agents 声明路径不存在: %s" % p)
    for p in pj.get("skills", []):
        rel = p[2:] if p.startswith("./") else p
        if not os.path.exists(os.path.join(root, rel, "SKILL.md")):
            r.err("skills 声明路径缺少 SKILL.md: %s" % p)

    # 头像
    avatar = pj.get("avatar", "")
    av_rel = avatar[2:] if avatar.startswith("./") else avatar
    av_abs = os.path.join(root, av_rel)
    if not os.path.exists(av_abs):
        r.err("avatar 文件不存在: %s" % avatar)
    else:
        size = os.path.getsize(av_abs)
        dim = png_size(av_abs)
        if dim is None:
            r.warn("avatar 不是 PNG（平台更稳的是 PNG）: %s" % avatar)
        elif dim != (512, 512):
            r.warn("avatar 尺寸 %dx%d（规范建议 512x512）" % dim)
        if size > MAX_AVATAR_BYTES:
            r.err("avatar 超过 500KB: %.1f KB" % (size / 1024))
        else:
            r.note("avatar: %s, %s, %.1f KB" % (avatar, ("%dx%d" % dim) if dim else "非PNG", size / 1024))

    # TODO 残留
    for dirpath, _dirs, files in os.walk(root):
        for fn in files:
            if fn.endswith((".md", ".json", ".py")):
                fp = os.path.join(dirpath, fn)
                try:
                    txt = open(fp, encoding="utf-8").read()
                except Exception:
                    continue
                if ("[TO" + "DO") in txt:
                    r.err("存在未替换的占位符残留: %s" % os.path.relpath(fp, root))

    # 禁止目录
    for bad in ("hooks", "commands"):
        if os.path.isdir(os.path.join(root, bad)):
            r.err("禁止目录存在: %s/" % bad)

    r.note("包名: %s ｜ 版本: %s" % (name, pj.get("version")))
    return r, pj


def build(root, out_dir=None):
    r, pj = check_dir(root)
    print("【1/3 结构体检】")
    r.dump()
    if not r.ok:
        print("  ❌ 体检未通过，终止打包")
        return None

    root = os.path.abspath(root)
    name = pj["name"]
    out_dir = os.path.abspath(out_dir or os.path.join(os.path.dirname(root), "dist"))
    os.makedirs(out_dir, exist_ok=True)
    zip_path = os.path.join(out_dir, name + ".zip")

    print("\n【2/3 打包】")
    files = []
    for dirpath, dirs, fns in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", "node_modules", ".git", "dist", "_build", ".idea", ".vscode")]
        for fn in fns:
            if fn in (".DS_Store", "Thumbs.db", ".gitkeep"):
                continue
            if fn.startswith(".") and fn not in (".codebuddy-plugin",):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace("\\", "/")
            if rel.startswith(".codebuddy-plugin"):
                pass
            files.append((rel, full))
    files.sort()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel, full in files:
            zf.write(full, "%s/%s" % (name, rel))
    print("  写入 %d 个文件 → %s (%.1f KB)" % (len(files), zip_path, os.path.getsize(zip_path) / 1024))

    print("\n【3/3 回读体检】")
    ok = verify_zip(zip_path)
    return zip_path if ok else None


def verify_zip(zip_path):
    """按客户端解析规则验证：顶层目录唯一、plugin.json 可定位、avatar 可命中。"""
    ok = True
    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist() if not n.endswith("/")]
        tops = {n.split("/")[0] for n in names}
        if len(tops) != 1:
            print("  ✗ 顶层目录不唯一: %s（客户端会无法确定专家根目录）" % sorted(tops))
            return False
        top = tops.pop()
        print("  顶层目录: %s" % top)

        manifest = None
        for d in (".codebuddy-plugin", ".workbuddy-plugin"):
            cand = "%s/%s/plugin.json" % (top, d)
            if cand in names:
                manifest = cand
                break
        if not manifest:
            print("  ✗ 找不到 %s/.codebuddy-plugin/plugin.json" % top)
            return False
        print("  manifest: %s" % manifest)

        pj = json.loads(zf.read(manifest).decode("utf-8"))
        if pj.get("name") != top:
            print("  ⚠ 顶层目录名(%s) 与 plugin.name(%s) 不一致，部分客户端按 name 建目录时会错位" % (top, pj.get("name")))
            ok = False

        avatar = pj.get("avatar", "")
        rel = avatar[2:] if avatar.startswith("./") else avatar
        hit = [c for c in ("%s/%s" % (top, rel), rel) if c in names]
        if hit:
            print("  ✓ avatar 可命中: %s" % hit[0])
        else:
            print("  ✗ avatar 在 zip 内无法命中（客户端会回退成文字头像）: %s" % avatar)
            ok = False

        # 重复嵌套检查
        if any(n.startswith("%s/%s/" % (top, top)) for n in names):
            print("  ✗ 检测到重复嵌套目录 %s/%s/ —— 这是「导入后图标丢失」的典型成因" % (top, top))
            ok = False

        print("  文件数: %d ｜ 压缩包: %.1f KB" % (len(names), os.path.getsize(zip_path) / 1024))
    print()
    print("  ✅ 回读体检通过" if ok else "  ❌ 回读体检未通过")
    return ok


def main(argv=None):
    argv = argv or sys.argv[1:]
    if not argv:
        print(__doc__)
        return 2
    cmd = argv[0]
    if cmd == "check" and len(argv) >= 2:
        r, _ = check_dir(argv[1])
        r.dump()
        return 0 if r.ok else 1
    if cmd == "build" and len(argv) >= 2:
        out = build(argv[1], argv[2] if len(argv) > 2 else None)
        return 0 if out else 1
    if cmd == "verify" and len(argv) >= 2:
        return 0 if verify_zip(argv[1]) else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
