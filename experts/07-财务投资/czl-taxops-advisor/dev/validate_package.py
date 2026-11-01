#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
专家包自检脚本（纯标准库）

用途：在打包上传之前，把"平台会拒绝"或"导入后图标变成文字"这类问题提前查出来。

检查项
  A 清单完整性与格式（名称、版本、必填字段、ASCII 包名）
  B 引用完整性（agents / skills / references / avatar 全部真实存在，大小写一致）
  C 头像可解析性（按平台 resolveAvatarFromExpertZip 的规则模拟解析）
  D 提示词结构（frontmatter 字段、skills 声明与实际目录一致）
  E 编码（全部文本文件 UTF-8，无非法字符）
  F 独立性扫描（不含他方品牌、商标、原包名）

用法：
  python dev/validate_package.py <专家包目录>
"""

import json
import os
import re
import struct
import sys

REQUIRED_KEYS = ["name", "version", "description", "author", "agents", "skills",
                 "expertType", "agentName", "displayName", "profession", "avatar"]

ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif"}
CONTAINER_DIRS = [".codebuddy-plugin", ".workbuddy-plugin"]

# 独立性扫描：不得出现的他方标识（含其品牌名、登录推广链接、原包名与技能名）
FORBIDDEN = [
    "qingflow", "轻流", "finance-tax-expert", "finance-tax-advisor",
    "finance-tax-core-skills", "utl_source=workbuddy",
]

results = []


def add(ok, code, label, detail=""):
    results.append((ok, code, label, detail))


def read_text(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def png_size(path):
    with open(path, "rb") as fh:
        head = fh.read(33)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", head[16:24])


def jpeg_size(path):
    with open(path, "rb") as fh:
        data = fh.read()
    i = 2
    while i < len(data) - 9:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h
        seg_len = struct.unpack(">H", data[i + 2:i + 4])[0]
        i += 2 + seg_len
    return None


def image_size(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".png":
        return png_size(path)
    if ext in (".jpg", ".jpeg"):
        return jpeg_size(path)
    return None


def parse_frontmatter(text):
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    data = {}
    current = None
    for line in parts[1].splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- ") and current:
            data[current] = (data.get(current, "") + " " + stripped[2:].strip()).strip()
            continue
        if line.startswith((" ", "\t")):
            continue
        if ":" in line:
            key, val = line.split(":", 1)
            current = key.strip()
            data[current] = val.strip()
    return data


def scan_files(root, skip_dirs=(".git", "node_modules", "__pycache__")):
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for name in files:
            yield os.path.join(base, name)


def main(pkg_dir):
    pkg_dir = os.path.abspath(pkg_dir)
    pkg_name = os.path.basename(pkg_dir)

    # ---------- A 清单
    manifest_path = None
    for container in CONTAINER_DIRS:
        cand = os.path.join(pkg_dir, container, "plugin.json")
        if os.path.isfile(cand):
            manifest_path = cand
            break
    if not manifest_path:
        add(False, "A0", "找到 .codebuddy-plugin/plugin.json", "缺失，平台会拒绝导入")
        report(pkg_dir, [])
        return 1

    add(True, "A0", "清单文件存在", os.path.relpath(manifest_path, pkg_dir))
    try:
        manifest = json.loads(read_text(manifest_path))
    except json.JSONDecodeError as exc:
        add(False, "A1", "plugin.json 是合法 JSON", str(exc))
        report(pkg_dir, [])
        return 1
    add(True, "A1", "plugin.json 是合法 JSON")

    missing = [k for k in REQUIRED_KEYS if k not in manifest]
    add(not missing, "A2", "必填字段齐全", "缺：" + ", ".join(missing) if missing else "")

    name = str(manifest.get("name", ""))
    add(bool(re.match(r"^[a-zA-Z0-9._-]+$", name)), "A3",
        "包名为 ASCII 且符合 [a-zA-Z0-9._-]+", name)
    add(name.startswith("czl-"), "A4", "包名以 czl- 开头", name)
    add(name == pkg_name, "A5", "包名与目录名一致（安装路径依赖此一致性）",
        "{} vs {}".format(name, pkg_name))
    add(bool(re.match(r"^\d+\.\d+\.\d+$", str(manifest.get("version", "")))), "A6",
        "版本号为 x.y.z", str(manifest.get("version")))

    author = manifest.get("author") or {}
    add(isinstance(author, dict) and author.get("name") and author.get("email"), "A7",
        "作者信息完整", json.dumps(author, ensure_ascii=False))

    for field in ("displayName", "profession", "displayDescription"):
        val = manifest.get(field)
        ok = isinstance(val, dict) and bool(val.get("zh"))
        add(ok, "A8", "{} 含中文".format(field), "" if ok else "缺失或为空")

    qp = manifest.get("quickPrompts") or []
    add(isinstance(qp, list) and 2 <= len(qp) <= 6, "A9", "推荐提问 2—6 条", str(len(qp)))

    # ---------- B 引用完整性
    agents = manifest.get("agents") or []
    add(bool(agents), "B1", "声明了 agents", str(len(agents)))
    for rel in agents:
        target = os.path.join(pkg_dir, rel.replace("./", "", 1))
        add(os.path.isfile(target), "B2", "agent 文件存在", rel)

    skills = manifest.get("skills") or []
    add(bool(skills), "B3", "声明了 skills", str(len(skills)))
    skill_names = []
    for rel in skills:
        sdir = os.path.join(pkg_dir, rel.replace("./", "", 1))
        smd = os.path.join(sdir, "SKILL.md")
        ok = os.path.isfile(smd)
        add(ok, "B4", "SKILL.md 存在", rel)
        if ok:
            fm = parse_frontmatter(read_text(smd))
            skill_names.append(os.path.basename(sdir))
            add(bool(fm) and bool(fm.get("description")), "B5",
                "SKILL.md frontmatter 含 description", os.path.basename(sdir))

    # references 引用核对（@references/xxx.md 与 references/xxx.md 两种写法）
    for rel in skills:
        sdir = os.path.join(pkg_dir, rel.replace("./", "", 1))
        for path in scan_files(sdir):
            if not path.endswith(".md"):
                continue
            text = read_text(path)
            for ref in set(re.findall(r"references/([^\s\)`，。、；]+\.md)", text)):
                target = os.path.join(sdir, "references", ref)
                add(os.path.isfile(target), "B6", "被引用的参考文件存在",
                    "{} -> references/{}".format(os.path.basename(path), ref))

    # ---------- C 头像
    avatar = str(manifest.get("avatar", ""))
    resolved = avatar
    if resolved.startswith(("./", "/")):
        resolved = resolved.lstrip("./").lstrip("/")
    av_path = os.path.join(pkg_dir, resolved.replace("/", os.sep))

    # 平台解析顺序：先 <prefix>/<avatar>，再 <avatar>
    add(bool(avatar), "C1", "声明了 avatar 字段", avatar)
    add(os.path.isfile(av_path), "C2", "头像文件按声明路径存在（大小写敏感）", resolved)
    if os.path.isfile(av_path):
        ext = os.path.splitext(av_path)[1].lower()
        add(ext in ALLOWED_IMAGE_EXT, "C3", "头像扩展名受支持", ext)
        size = image_size(av_path)
        if size:
            w, h = size
            add(w == h, "C4", "头像为正方形", "{}x{}".format(w, h))
            add(min(w, h) >= 256, "C5", "头像分辨率不低于 256", "{}x{}".format(w, h))
        else:
            add(ext == ".svg", "C4", "非位图头像仅支持 svg", ext)
        kb = os.path.getsize(av_path) / 1024.0
        add(kb < 1024, "C6", "头像小于 1MB", "{:.1f} KB".format(kb))

    # 目录内是否存在多个头像文件（易导致引用错位）
    av_dir = os.path.dirname(av_path)
    if os.path.isdir(av_dir):
        files = [f for f in os.listdir(av_dir) if not f.startswith(".")]
        add(len(files) == 1, "C7", "头像目录只有一个文件（避免引用歧义）", str(files))

    # ---------- D 提示词结构
    for rel in agents:
        target = os.path.join(pkg_dir, rel.replace("./", "", 1))
        if not os.path.isfile(target):
            continue
        text = read_text(target)
        fm = parse_frontmatter(text)
        add(bool(fm), "D1", "agent 文件含 frontmatter", rel)
        if fm:
            add(fm.get("name") == name, "D2", "agent frontmatter.name 与包名一致", str(fm.get("name")))
            add(bool(fm.get("description")), "D3", "agent 含 description")
            fm_skills = fm.get("skills", "")
            for sn in skill_names:
                add(sn in fm_skills, "D4", "agent 声明的 skill 与目录一致", sn)
        add(len(text) > 1500, "D5", "agent 提示词有实质内容（>1500 字符）", str(len(text)))

    # ---------- E 编码
    bad = []
    for path in scan_files(pkg_dir):
        if os.path.splitext(path)[1].lower() in (".png", ".jpg", ".jpeg", ".zip", ".pyc"):
            continue
        try:
            read_text(path)
        except UnicodeDecodeError:
            bad.append(os.path.relpath(path, pkg_dir))
    add(not bad, "E1", "所有文本文件为 UTF-8", ", ".join(bad))

    # ---------- F 独立性
    # dev/ 为本地开发工具、docs/ 为交付文档（均不进发布包）：前者含扫描用关键字清单，后者含法律分析所引用的他方名称，故跳过
    hits = []
    for path in scan_files(pkg_dir, skip_dirs=(".git", "node_modules", "__pycache__", "dev", "docs")):
        if os.path.splitext(path)[1].lower() in (".png", ".jpg", ".jpeg", ".zip", ".pyc"):
            continue
        try:
            text = read_text(path).lower()
        except UnicodeDecodeError:
            continue
        for token in FORBIDDEN:
            if token.lower() in text:
                hits.append("{}: {}".format(os.path.relpath(path, pkg_dir), token))
    add(not hits, "F1", "不含他方品牌/原包标识", "; ".join(hits[:5]))

    return report(pkg_dir, results)


def report(pkg_dir, items):
    passed = sum(1 for ok, *_ in items if ok)
    total = len(items)
    print("=" * 72)
    print("专家包自检  {}".format(pkg_dir))
    print("=" * 72)
    for ok, code, label, detail in items:
        if not ok:
            print("[FAIL] {:<4}{:<38}{}".format(code, label, detail))
    if passed == total:
        print("全部 {} 项通过。".format(total))
    else:
        print("-" * 72)
        print("通过 {}/{}，失败 {} 项。失败项已列出，请逐项修复后重跑。".format(
            passed, total, total - passed))
    return 0 if passed == total else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python dev/validate_package.py <package_dir>")
        raise SystemExit(1)
    raise SystemExit(main(sys.argv[1]))
