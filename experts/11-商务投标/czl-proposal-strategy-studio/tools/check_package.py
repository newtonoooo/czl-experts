#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Package integrity check for a WorkBuddy expert, with an avatar-first focus.

Why this exists: a package can pass structural validation and still show a plain
letter instead of the avatar in the expert list. The UI silently falls back to a
text avatar whenever the declared image cannot be loaded, which happens when

  * plugin.json declares an avatar path but no file sits at that exact path,
  * the file name carries a stray backslash (e.g. "expert\\.png" on Windows shells),
  * the image is over 500 KB, not square, or not actually PNG/JPEG bytes,
  * the image was generated but never copied into avatars/.

This script checks those conditions directly.

Usage:
    python tools/check_package.py [expert-dir] [--verbose]

Exit: 0 all pass, 1 at least one FAIL, 2 bad arguments.
"""
import json
import os
import struct
import sys

MAX_AVATAR_BYTES = 500 * 1024
EXPECT_SIZE = (512, 512)


def out(text=""):
    sys.stdout.write(text + "\n")


def image_info(path):
    """Return (kind, width, height) or (None, 0, 0) if unrecognised."""
    with open(path, "rb") as f:
        head = f.read(32)
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", head[16:24])
        return "png", w, h
    if head[:3] == b"\xff\xd8\xff":
        # JPEG: walk markers to SOF
        with open(path, "rb") as f:
            data = f.read()
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return "jpeg", w, h
            if marker in (0xD8, 0xD9):
                i += 2
                continue
            seg_len = struct.unpack(">H", data[i + 2:i + 4])[0]
            i += 2 + seg_len
        return "jpeg", 0, 0
    return None, 0, 0


class Report:
    def __init__(self):
        self.rows = []

    def add(self, level, area, msg):
        self.rows.append((level, area, msg))

    def fail(self, area, msg):
        self.add("FAIL", area, msg)

    def warn(self, area, msg):
        self.add("WARN", area, msg)

    def ok(self, area, msg):
        self.add("PASS", area, msg)

    def render(self):
        lines = ["# 专家包完整体检", ""]
        lines.append("| 结果 | 检查域 | 说明 |")
        lines.append("|---|---|---|")
        for level, area, msg in self.rows:
            lines.append("| %s | %s | %s |" % (level, area, msg))
        fails = [r for r in self.rows if r[0] == "FAIL"]
        warns = [r for r in self.rows if r[0] == "WARN"]
        lines.append("")
        lines.append("**FAIL %d 项 / WARN %d 项 / 共 %d 项检查**" % (
            len(fails), len(warns), len(self.rows)))
        lines.append("")
        if fails:
            lines.append("存在 FAIL 的项，不要打包上架：这些项会让专家在平台里显示异常或加载失败。")
        elif warns:
            lines.append("可以打包，但建议先处理 WARN 项。")
        else:
            lines.append("全部通过。可以进入打包与注册流程。")
        return "\n".join(lines), len(fails)


def check(root):
    r = Report()
    pj_path = os.path.join(root, ".codebuddy-plugin", "plugin.json")
    if not os.path.isfile(pj_path):
        r.fail("plugin.json", "缺少 .codebuddy-plugin/plugin.json，专家无法被平台识别")
        return r
    try:
        with open(pj_path, "r", encoding="utf-8") as f:
            pj = json.load(f)
        r.ok("plugin.json", "JSON 可解析")
    except json.JSONDecodeError as e:
        r.fail("plugin.json", "JSON 解析失败：%s" % e)
        return r

    name = pj.get("name", "")
    if not name:
        r.fail("plugin.json", "缺少 name")
    if pj.get("plugin") and pj.get("plugin") != name:
        r.fail("plugin.json", "plugin 字段（%s）与 name（%s）不一致" % (pj.get("plugin"), name))
    if os.path.basename(root.rstrip("/\\")) != name:
        r.warn("目录", "目录名与 name 不一致：目录=%s，name=%s" % (
            os.path.basename(root.rstrip("/\\")), name))

    # agents
    agent_name = pj.get("agentName", "")
    md = os.path.join(root, "agents", "%s.md" % agent_name)
    if agent_name and os.path.isfile(md):
        r.ok("agents", "agentName 对应的 MD 存在：agents/%s.md" % agent_name)
    else:
        r.fail("agents", "agentName「%s」找不到对应文件 agents/%s.md" % (agent_name, agent_name))

    # skills
    skills = pj.get("skills") or []
    missing_skill = []
    for s in skills:
        rel = s[2:] if s.startswith("./") else s
        if not os.path.isfile(os.path.join(root, rel, "SKILL.md")):
            missing_skill.append(s)
    if missing_skill:
        r.fail("skills", "以下技能目录缺 SKILL.md：%s" % "、".join(missing_skill))
    elif skills:
        r.ok("skills", "%d 个技能目录均含 SKILL.md" % len(skills))

    # display fields
    tags = pj.get("tags") or []
    qp = pj.get("quickPrompts") or []
    if len(tags) == 3:
        r.ok("展示字段", "tags 为 3 个")
    else:
        r.fail("展示字段", "tags 必须是 3 个，当前 %d 个" % len(tags))
    if len(qp) == 3:
        r.ok("展示字段", "quickPrompts 为 3 个")
    else:
        r.fail("展示字段", "quickPrompts 必须是 3 个，当前 %d 个" % len(qp))
    dip = (pj.get("defaultInitPrompt") or {}).get("zh", "")
    if qp and dip and dip != (qp[0] or {}).get("zh", ""):
        r.warn("展示字段", "defaultInitPrompt 与 quickPrompts[0] 不一致")
    desc = (pj.get("displayDescription") or {}).get("zh", "")
    if desc and not 40 <= len(desc) <= 50:
        r.warn("展示字段", "displayDescription.zh 为 %d 字（建议 40–50）" % len(desc))

    # avatar: the part that decides whether the list shows an image or a letter
    avatar = pj.get("avatar")
    if not avatar:
        r.fail("头像", "plugin.json 未声明 avatar —— 平台会退化为文字头像")
    else:
        if avatar != avatar.strip():
            r.fail("头像", "avatar 字段首尾有空格：%r" % avatar)
        if "\\" in avatar:
            r.fail("头像", "avatar 字段含反斜杠：%r，应使用正斜杠" % avatar)
        path = os.path.join(root, avatar.replace("/", os.sep))
        if not os.path.isfile(path):
            r.fail("头像", "声明的头像文件不存在：%s（这就是列表显示成文字的典型原因）" % avatar)
        else:
            size = os.path.getsize(path)
            kind, w, h = image_info(path)
            if kind is None:
                r.fail("头像", "文件不是可识别的 PNG/JPEG（扩展名与实际格式不符）")
            else:
                if size > MAX_AVATAR_BYTES:
                    r.fail("头像", "体积 %.0f KB 超过 500 KB 上限" % (size / 1024.0))
                else:
                    r.ok("头像", "体积 %.0f KB，在 500 KB 以内" % (size / 1024.0))
                if (w, h) != EXPECT_SIZE:
                    r.warn("头像", "尺寸 %dx%d，建议 512x512 正方形" % (w, h))
                else:
                    r.ok("头像", "尺寸 512x512")
                if kind == "jpeg" and avatar.lower().endswith(".png"):
                    r.fail("头像", "扩展名为 .png 但实际是 JPEG，部分环境会加载失败")
                # odd characters in the real file name
                base = os.path.basename(path)
                if "\\" in base or base.count(".") > 1:
                    r.fail("头像", "文件名异常：%r" % base)

        avatar_dir = os.path.join(root, "avatars")
        if os.path.isdir(avatar_dir):
            files = [f for f in os.listdir(avatar_dir) if not f.startswith(".")]
            declared = os.path.basename(avatar)
            extra = [f for f in files if f != declared]
            if extra:
                r.warn("头像", "avatars/ 下还有未声明的文件：%s（建议清理，避免误引用）" % "、".join(extra))
            bad = [f for f in files if "\\" in f]
            if bad:
                r.fail("头像", "文件名含反斜杠（Windows 转义残留）：%s" % "、".join(bad))

    # stray build artefacts that should not ship
    for junk in ("__pycache__", ".DS_Store", "node_modules"):
        for dirpath, dirnames, filenames in os.walk(root):
            if junk in dirnames:
                r.warn("清理", "发现应排除的目录：%s" % os.path.join(
                    os.path.relpath(dirpath, root), junk))
    return r


def main():
    argv = sys.argv[1:]
    if argv and argv[0] in ("-h", "--help"):
        out(__doc__)
        sys.exit(2)
    root = argv[0] if argv else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if not os.path.isdir(root):
        out("ERROR: 目录不存在: %s" % root)
        sys.exit(2)
    report = check(root)
    text, fails = report.render()
    out(text)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
