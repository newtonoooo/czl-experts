#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""专家包自检器（纯标准库）。

用法:
    python tools/selfcheck.py [专家包目录]

检查项与 WorkBuddy 客户端实际生效的规则对齐：
  - plugin.json 必填字段与 i18n
  - agentName / 文件名 / frontmatter name 三者一致
  - 展示名只含中英文、数字、连字符
  - 头像：路径在包内、文件存在、格式为 PNG/JPG、尺寸与体积
  - skills 路径含 SKILL.md，SKILL.md 中引用的文件确实存在
  - 工作流文件齐全
  - 无被禁止的目录/文件
  - 全包占位符扫描（模板目录除外）

退出码 0 = 全部通过，1 = 有错误。
"""

import json
import re
import struct
import sys
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
DISPLAY_RE = re.compile(r"^[\u4e00-\u9fa5A-Za-z0-9\-—]+$")
PLACEHOLDER = re.compile(r"\{\{[^}]{0,60}\}\}")

REQUIRED_I18N = ["displayName", "profession", "displayDescription", "defaultInitPrompt"]

errors, warns, oks = [], [], []


def ok(msg):
    oks.append(msg)


def err(msg):
    errors.append(msg)


def warn(msg):
    warns.append(msg)


def png_size(data):
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    w, h = struct.unpack(">II", data[16:24])
    return w, h


def jpeg_size(data):
    if data[:2] != b"\xff\xd8":
        return None
    i = 2
    while i < len(data) - 9:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h
        seg_len = struct.unpack(">H", data[i + 2:i + 4])[0]
        i += 2 + seg_len
    return None


def check_plugin(root, pj):
    for f in ("name", "version", "description", "expertType", "agentName", "agents"):
        if not pj.get(f):
            err(f"plugin.json 缺少必填字段：{f}")

    name = pj.get("name", "")
    if name and not NAME_RE.match(name):
        err(f"name 不符合 kebab-case：{name}")
    if name and not name.startswith("czl-"):
        warn(f"name 未以 czl- 开头：{name}")
    if pj.get("plugin") and pj["plugin"] != name:
        err("plugin 字段与 name 不一致")

    for f in REQUIRED_I18N:
        v = pj.get(f)
        if not isinstance(v, dict) or not v.get("zh") or not v.get("en"):
            err(f"{f} 必须是含 en/zh 的对象且都不为空")

    dn = (pj.get("displayName") or {}).get("zh", "")
    if dn:
        if not DISPLAY_RE.match(dn):
            err(f"displayName.zh 含不允许字符（只允许中英文、数字、-、—，不能有空格）：{dn}")
        ok(f"displayName.zh 命名合规：{dn}")

    dd = (pj.get("displayDescription") or {}).get("zh", "")
    if dd:
        n = len(dd)
        if 40 <= n <= 50:
            ok(f"displayDescription.zh 长度 {n} 字（40—50 区间）")
        else:
            warn(f"displayDescription.zh 长度 {n} 字，建议 40—50")

    tags = pj.get("tags") or []
    if len(tags) != 3:
        err(f"tags 必须正好 3 个，当前 {len(tags)}")
    for t in tags:
        if not (t.get("zh") and t.get("en")):
            err("tags 每项必须含 en/zh")

    qp = pj.get("quickPrompts") or []
    if len(qp) != 3:
        err(f"quickPrompts 必须正好 3 个，当前 {len(qp)}")
    dip = (pj.get("defaultInitPrompt") or {}).get("zh")
    if qp and dip and qp[0].get("zh") != dip:
        err("defaultInitPrompt.zh 与 quickPrompts[0].zh 不一致")
    elif qp and dip:
        ok("defaultInitPrompt 与 quickPrompts[0] 一致")

    cat = pj.get("categoryId", "")
    known = {
        "01-ProductDesign", "02-Engineering", "03-GameSpatial", "04-DataAI",
        "05-MarketingGrowth", "06-ContentCreative", "07-SalesCommerce",
        "08-FinanceInvestment", "09-OperationsHR", "10-ProjectQuality",
        "11-SecurityCompliance", "12-IndustryConsultant", "15-Education",
    }
    if cat not in known:
        err(f"categoryId 不在已知分类内：{cat}")
    else:
        ok(f"categoryId：{cat}")

    # agents
    agent_name = pj.get("agentName", "")
    agents = pj.get("agents") or []
    md = root / "agents" / f"{agent_name}.md"
    if not md.exists():
        err(f"agents/{agent_name}.md 不存在")
    else:
        head = md.read_text(encoding="utf-8")[:400]
        m = re.search(r"^name:\s*(.+)$", head, re.M)
        if not m:
            err("Agent MD 缺少 frontmatter name")
        elif m.group(1).strip().strip('"') != agent_name:
            err(f"frontmatter name（{m.group(1).strip()}）与 agentName（{agent_name}）不一致")
        else:
            ok("agentName = MD 文件名 = frontmatter name")
        if "tools:" in head:
            err("Agent MD frontmatter 不得包含 tools 字段")
    for a in agents:
        p = root / a.lstrip("./")
        if not p.exists():
            err(f"agents 声明文件不存在：{a}")

    # skills
    for s in pj.get("skills") or []:
        d = root / s.lstrip("./")
        if not (d / "SKILL.md").exists():
            err(f"skill 缺少 SKILL.md：{s}")
        else:
            ok(f"skill 就绪：{s}")


def check_avatar(root, pj):
    rel = pj.get("avatar", "")
    if not rel:
        err("未声明 avatar")
        return
    p = (root / rel).resolve()
    try:
        p.relative_to(root.resolve())
    except ValueError:
        err(f"avatar 路径逃出专家目录：{rel}")
        return
    if not p.exists():
        err(f"avatar 文件不存在：{rel}")
        return
    data = p.read_bytes()
    size = len(data)
    dim = png_size(data) or jpeg_size(data)
    if dim is None:
        err("avatar 不是有效的 PNG/JPG")
        return
    w, h = dim
    if w != h:
        warn(f"avatar 非正方形：{w}×{h}")
    if w < 200 or w > 2048:
        warn(f"avatar 尺寸 {w}×{h}，建议 512×512（客户端上限 5MB）")
    if size > 5 * 1024 * 1024:
        err(f"avatar {size/1024:.0f}KB 超过客户端 5MB 上限，头像会渲染成文字")
    elif size > 500 * 1024:
        warn(f"avatar {size/1024:.0f}KB 超过规范建议的 500KB")
    else:
        ok(f"avatar 可被客户端解析：{w}×{h}，{size/1024:.1f}KB")


def check_structure(root, pj):
    for forbidden in ("hooks", "commands"):
        if (root / forbidden).exists():
            err(f"存在被禁止的目录：{forbidden}/")
    if (root / ".lsp.json").exists():
        err("存在被禁止的文件：.lsp.json")
    for sub in ("agents", "skills", "bin", "avatars"):
        if (root / ".codebuddy-plugin" / sub).exists():
            err(f"{sub}/ 不能放在 .codebuddy-plugin/ 内")

    for f in ("README.md", "CHANGELOG.md", "LICENSE"):
        if not (root / f).exists():
            warn(f"缺少 {f}")

    wf = root / "workflows"
    expect = [f"W{i}-" for i in range(1, 9)]
    if not wf.exists():
        err("缺少 workflows/ 目录")
    else:
        names = [p.name for p in wf.glob("*.md")]
        for pre in expect:
            if not any(n.startswith(pre) for n in names):
                err(f"缺少工作流文件：{pre}*.md")
        if all(any(n.startswith(pre) for n in names) for pre in expect):
            ok("八条工作流齐全（W1—W8）")


def check_skill_refs(root):
    skill_dir = None
    for p in (root / "skills").glob("*/SKILL.md"):
        skill_dir = p.parent
        break
    if not skill_dir:
        return
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    tokens = set(re.findall(r"`([A-Za-z0-9_\-/]+\.(?:md|py))`", text))
    missing, checked = [], 0
    for t in sorted(tokens):
        if t.startswith("http"):
            continue
        checked += 1
        if "/" in t:
            if t.startswith(("agents/", "workflows/", "docs/", "tools/")):
                exists = (root / t).exists()
            else:
                exists = (skill_dir / t).exists()
        else:
            exists = any((skill_dir / d / t).exists() for d in ("references", "templates", "scripts"))
        if not exists:
            missing.append(t)
    if missing:
        for m in missing:
            err(f"SKILL.md 引用的文件不存在：{m}")
    else:
        ok(f"SKILL.md 引用的 {checked} 个文件全部存在")


def strip_code(text):
    """去掉围栏代码块与行内代码，避免把模板占位符误判为残留。"""
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`[^`\n]*`", "", text)
    return text


def check_placeholders(root):
    bad = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in (".md", ".json", ".py"):
            continue
        if "templates" in p.parts or "testdata" in p.parts:
            continue
        try:
            t = p.read_text(encoding="utf-8")
        except Exception:
            continue
        if PLACEHOLDER.search(strip_code(t)):
            bad.append(str(p.relative_to(root)))
    if bad:
        for b in bad:
            err(f"残留占位符（代码块外）：{b}")
    else:
        ok("非模板文件无占位符残留（代码块内的模板示例除外）")


def main():
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
    print(f"自检目录：{root}\n")

    pj_path = root / ".codebuddy-plugin" / "plugin.json"
    if not pj_path.exists():
        print("[FAIL] 找不到 .codebuddy-plugin/plugin.json")
        return 1
    try:
        pj = json.loads(pj_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[FAIL] plugin.json 不是合法 JSON：{e}")
        return 1
    ok("plugin.json 可解析")

    check_plugin(root, pj)
    check_avatar(root, pj)
    check_structure(root, pj)
    check_skill_refs(root)
    check_placeholders(root)

    for m in oks:
        print(f"[OK]   {m}")
    for m in warns:
        print(f"[WARN] {m}")
    for m in errors:
        print(f"[FAIL] {m}")

    print(f"\n通过 {len(oks)} 项，告警 {len(warns)} 项，错误 {len(errors)} 项")
    if errors:
        print("结论：未通过，请先修复 FAIL 项再打包。")
        return 1
    print("结论：自检通过（内容专业性仍需人工复核）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
