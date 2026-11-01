#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""专家包体检 — 结构、元数据、头像与「zip 导入解析」模拟。

用法:
    python pack_check.py <expert-dir>

检查项:
  1. 目录结构（plugin.json、agents、skills、avatars 位置）
  2. 元数据（kebab-case、字段完整、tags=3、quickPrompts=3、描述字数）
  3. 提示词（frontmatter name 与文件名一致、不含 tools 字段、无 [TODO]）
  4. 头像（路径规范、格式、体积、正方形、真实图片头）
  5. zip 导入模拟（按平台算法逐条解析 zip 内头像条目）

退出码: 0 通过; 1 有错误; 2 参数错误。
"""

import json
import os
import re
import struct
import sys
import zipfile
from io import BytesIO
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MAX_AVATAR_BYTES = 5242880  # 平台 resolveAvatarUrl 上限 5MB
SUPPORTED_IMG = {".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif"}
SKIP_NAMES = {".DS_Store", ".created-by-session", ".pending-preview-session",
              "node_modules", ".git", ".cache", "cache", "storage", "history",
              "logs", "tmp", "temp", "__pycache__"}
SKIP_SUFFIX = (".log", ".tmp", ".zip")


def is_kebab(s):
    return bool(re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", s or ""))


def image_info(path):
    """返回 (格式, 宽, 高) 或 (None, None, None)。"""
    try:
        data = path.read_bytes()
    except OSError:
        return None, None, None
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        w, h = struct.unpack(">II", data[16:24])
        return "png", w, h
    if data[:2] == b"\xff\xd8":
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return "jpeg", w, h
            seg_len = struct.unpack(">H", data[i + 2:i + 4])[0]
            i += 2 + seg_len
        return "jpeg", None, None
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp", None, None
    head = data[:400].lstrip().lower()
    if head.startswith(b"<svg") or b"<svg" in head:
        return "svg", None, None
    return None, None, None


def collect_entries(root: Path, zip_root: str):
    """按与 build_zip.py 相同的规则收集条目（路径统一为正斜杠）。"""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_NAMES)
        for name in sorted(filenames):
            if name in SKIP_NAMES or name.lower().endswith(SKIP_SUFFIX):
                continue
            full = Path(dirpath) / name
            rel = full.relative_to(root).as_posix()
            out.append(("%s/%s" % (zip_root, rel), full))
    return out


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    root = Path(argv[1]).resolve()
    if not root.is_dir():
        print("错误: 目录不存在 -> %s" % root)
        return 2

    errors, warnings, passed = [], [], []

    def ok(msg):
        passed.append(msg)

    def err(msg):
        errors.append(msg)

    def warn(msg):
        warnings.append(msg)

    # ---------- 1. 结构 ----------
    pj_path = root / ".codebuddy-plugin" / "plugin.json"
    if not pj_path.exists():
        err("缺少 .codebuddy-plugin/plugin.json")
        print_report(root, passed, warnings, errors)
        return 1
    try:
        pj = json.loads(pj_path.read_text(encoding="utf-8"))
        ok("plugin.json 可解析")
    except json.JSONDecodeError as e:
        err("plugin.json 不是合法 JSON: %s" % e)
        print_report(root, passed, warnings, errors)
        return 1

    for forbidden in ("hooks", "commands"):
        if (root / forbidden).exists():
            err("存在平台禁止的目录: %s/" % forbidden)
    if (root / ".lsp.json").exists():
        err("存在平台禁止的文件: .lsp.json")
    for sub in ("agents", "skills", "bin", "avatars"):
        if (root / ".codebuddy-plugin" / sub).exists():
            err("%s/ 必须在包根目录，不能放在 .codebuddy-plugin/ 内" % sub)

    # ---------- 2. 元数据 ----------
    name = pj.get("name", "")
    if not is_kebab(name):
        err("name 必须为 kebab-case: '%s'" % name)
    elif not name.startswith("czl-"):
        warn("name 未以 czl- 开头: '%s'" % name)
    else:
        ok("name 合规: %s" % name)

    if pj.get("plugin") and pj["plugin"] != name:
        err("plugin 字段(%s)必须等于 name(%s)" % (pj["plugin"], name))
    if pj.get("version") and not re.match(r"^\d+\.\d+\.\d+", str(pj["version"])):
        err("version 应为语义化版本: %s" % pj["version"])
    if pj.get("expertType") not in ("agent", "team"):
        err("expertType 必须为 agent 或 team")

    for field in ("displayName", "profession", "displayDescription", "defaultInitPrompt"):
        node = pj.get(field)
        if not isinstance(node, dict) or not node.get("zh") or not node.get("en"):
            err("字段 %s 必须同时含 zh 与 en" % field)

    dd_zh = (pj.get("displayDescription") or {}).get("zh", "")
    if dd_zh:
        if 40 <= len(dd_zh) <= 50:
            ok("displayDescription.zh 长度 %d（要求 40-50）" % len(dd_zh))
        else:
            err("displayDescription.zh 长度 %d，要求 40-50" % len(dd_zh))

    tags = pj.get("tags") or []
    if len(tags) != 3:
        err("tags 必须为 3 个，当前 %d" % len(tags))
    else:
        ok("tags 数量 3")

    qp = pj.get("quickPrompts") or []
    if len(qp) != 3:
        err("quickPrompts 必须为 3 个，当前 %d" % len(qp))
    else:
        ok("quickPrompts 数量 3")
    dip = pj.get("defaultInitPrompt") or {}
    if qp and isinstance(qp[0], dict) and dip.get("zh") != qp[0].get("zh"):
        err("defaultInitPrompt.zh 必须与 quickPrompts[0].zh 一致")

    cat = pj.get("categoryId", "")
    if not re.match(r"^\d{2}-[A-Za-z]+$", cat or ""):
        err("categoryId 格式异常: %s" % cat)

    author = pj.get("author") or {}
    if not author.get("name"):
        warn("author.name 为空")
    if author.get("email") and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", author["email"]):
        err("author.email 格式异常")

    # ---------- 3. agents / skills / TODO ----------
    agent_name = pj.get("agentName", "")
    agent_md = root / "agents" / ("%s.md" % agent_name)
    if not agent_md.exists():
        err("agentName 对应文件不存在: agents/%s.md" % agent_name)
    else:
        text = agent_md.read_text(encoding="utf-8")
        fm = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
        if not fm:
            err("agents/%s.md 缺少 YAML frontmatter" % agent_name)
        else:
            block = fm.group(1)
            if "tools:" in block:
                err("Agent frontmatter 不得声明 tools 字段")
            m = re.search(r"^name:\s*(.+)$", block, re.MULTILINE)
            if not m or m.group(1).strip().strip('"').strip("'") != agent_name:
                err("Agent frontmatter name 必须等于文件名 %s" % agent_name)
            if "description:" not in block:
                warn("Agent frontmatter 缺少 description")
        if len(text) < 1500:
            warn("Agent 提示词偏短（%d 字符），可能内容不足" % len(text))
        else:
            ok("Agent 提示词长度 %d 字符" % len(text))

    for skill_path in pj.get("skills") or []:
        rel = skill_path[2:] if skill_path.startswith("./") else skill_path
        skill_md = root / rel / "SKILL.md"
        if not skill_md.exists():
            err("skill 缺少 SKILL.md: %s" % skill_path)
        else:
            ok("skill 就绪: %s" % rel)

    todo_files = []
    self_path = Path(__file__).resolve()
    for p in root.rglob("*"):
        if p.is_file() and p.suffix in (".md", ".json", ".csv", ".py") and ".git" not in p.parts:
            if p.resolve() == self_path:
                continue
            try:
                if "[TODO" in p.read_text(encoding="utf-8", errors="ignore"):
                    todo_files.append(str(p.relative_to(root)))
            except OSError:
                pass
    if todo_files:
        err("存在未填写的 [TODO]: %s" % ", ".join(todo_files[:5]))
    else:
        ok("无 [TODO] 残留")

    # ---------- 4. 头像 ----------
    avatar = pj.get("avatar", "")
    if not avatar:
        err("plugin.json 缺少 avatar 字段（平台将回退为文字头像）")
    else:
        if "\\" in avatar:
            err("avatar 路径含反斜杠（Windows 分隔符），导入时无法匹配 zip 条目: %s" % avatar)
        if avatar.startswith("/") or avatar.startswith("./"):
            warn("avatar 建议写为相对路径（不带 ./ 或 /）: %s" % avatar)
        norm = avatar.replace("\\", "/").lstrip("./").lstrip("/")
        target = (root / norm).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            err("avatar 指向包外路径: %s" % avatar)
        if not target.exists():
            err("avatar 文件不存在: %s" % avatar)
        else:
            size = target.stat().st_size
            fmt, w, h = image_info(target)
            if target.suffix.lower() not in SUPPORTED_IMG:
                err("头像扩展名不受支持: %s" % target.suffix)
            if fmt is None:
                err("头像不是有效图片（文件头无法识别）: %s" % avatar)
            if size > MAX_AVATAR_BYTES:
                err("头像 %.1f KB 超过平台 5MB 上限" % (size / 1024))
            elif size > 500 * 1024:
                warn("头像 %.1f KB，建议压缩到 500KB 以内以加快加载" % (size / 1024))
            if w and h and w != h:
                err("头像非正方形: %dx%d" % (w, h))
            if fmt:
                ok("头像有效: %s %dx%d %.1f KB" % (fmt.upper(), w or 0, h or 0, size / 1024))

    # ---------- 5. zip 导入模拟 ----------
    entries = collect_entries(root, name)
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for arc, full in entries:
            zf.write(full, arc)
    buf.seek(0)
    with zipfile.ZipFile(buf) as zf:
        names = zf.namelist()
        bad_sep = [n for n in names if "\\" in n or n.startswith("/")]
        if bad_sep:
            err("zip 条目含反斜杠或绝对路径: %s" % bad_sep[:3])
        else:
            ok("zip 条目路径规范（%d 条，均为正斜杠）" % len(names))

        manifest = [n for n in names if n.endswith(".codebuddy-plugin/plugin.json")]
        if not manifest:
            err("zip 内未找到 .codebuddy-plugin/plugin.json，导入将失败")
            zip_root = None
        else:
            entry = manifest[0]
            zip_root = entry[: -len(".codebuddy-plugin/plugin.json")].rstrip("/")
            ok("zip 根目录: %s" % (zip_root or "(无根目录)"))
            if zip_root != name:
                warn("zip 根目录(%s)与 name(%s)不一致，建议一致以免安装目录与标识错位" % (zip_root, name))

        if avatar:
            rel = avatar.replace("\\", "/").lstrip("./").lstrip("/")
            cands = (["%s/%s" % (zip_root, rel), rel] if zip_root else [rel])
            hit = next((c for c in cands if c in names), None)
            if hit:
                data = zf.read(hit)
                fmt, w, h = None, None, None
                try:
                    tmp_fmt = "png" if data[:8] == b"\x89PNG\r\n\x1a\n" else None
                    fmt = tmp_fmt or "?"
                    if tmp_fmt:
                        w, h = struct.unpack(">II", data[16:24])
                except Exception:
                    pass
                ok("导入模拟：头像可解析 -> %s（%s %sx%s，base64 约 %.0f KB）"
                   % (hit, fmt, w or "?", h or "?", len(data) * 4 / 3 / 1024))
            else:
                err("导入模拟：zip 内找不到头像条目 %s（尝试过 %s），"
                    "平台会退回原始相对路径并显示文字头像" % (rel, cands))

        # 大小写一致性检查
        lower = {}
        for n in names:
            lower.setdefault(n.lower(), []).append(n)
        if avatar:
            want = "%s/%s" % (zip_root, avatar.replace("\\", "/").lstrip("./")) if zip_root else avatar
            if want not in names and want.lower() in lower:
                err("头像条目大小写不一致：期望 %s，实际 %s（zip 匹配区分大小写）"
                    % (want, lower[want.lower()][0]))

    print_report(root, passed, warnings, errors)
    return 0 if not errors else 1


def print_report(root, passed, warnings, errors):
    print("专家包体检: %s" % root.name)
    print("=" * 60)
    for p in passed:
        print("  ✓ %s" % p)
    for w in warnings:
        print("  ! %s" % w)
    for e in errors:
        print("  ✗ %s" % e)
    print("-" * 60)
    print("通过 %d 项｜警告 %d 项｜错误 %d 项 -> %s"
          % (len(passed), len(warnings), len(errors), "PASS" if not errors else "FAIL"))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
