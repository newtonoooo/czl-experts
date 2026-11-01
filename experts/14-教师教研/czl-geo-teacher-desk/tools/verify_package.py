#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""专家包自检：模拟 WorkBuddy 的导入与头像解析规则，提前发现"图标变文字"这类问题。

用法:
    python verify_package.py <专家目录 或 .zip>

检查项:
  1. zip 内是否为单一顶层目录，且含 .codebuddy-plugin/plugin.json
  2. plugin.json 可解析、必填字段齐全、name/plugin/agentName 一致
  3. agentName 对应的 agents/*.md 存在，且 frontmatter name 与文件名一致、无 tools 字段
  4. 头像文件存在、是合法 PNG/JPG、尺寸为正方形、体积 < 5MB（WorkBuddy 超过直接丢弃）
  5. tags / quickPrompts 各 3 条，defaultInitPrompt 与第一条一致
  6. 文档中引用的包内相对路径（references/ workflows/ materials/ tools/）全部存在
  7. manifest.yaml 存在（官方导出会附带）
退出码 0 全部通过；1 有失败项。
"""

import json
import re
import struct
import sys
import tempfile
import zipfile
from pathlib import Path

AVATAR_MAX_BYTES = 5 * 1024 * 1024  # WorkBuddy resolveAvatarUrl 的硬上限
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    flag = "PASS" if ok else "FAIL"
    print(f"[{flag}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def image_info(path: Path):
    """返回 (格式, 宽, 高) 或 (None, 0, 0)。"""
    head = path.read_bytes()[:32]
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", head[16:24])
        return "PNG", w, h
    if head[:2] == b"\xff\xd8":
        data = path.read_bytes()
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return "JPEG", w, h
            if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            seg_len = struct.unpack(">H", data[i + 2:i + 4])[0]
            i += 2 + seg_len
        return "JPEG", 0, 0
    return None, 0, 0


def gather_md_links(root: Path):
    """收集 md 中出现的包内相对路径。"""
    pat = re.compile(r"(?:\(|`|\s)(\.?/?(?:references|workflows|materials|tools|agents|avatars)/[\w\-.\u4e00-\u9fa5]+)")
    missing, seen = [], set()
    for md in root.rglob("*.md"):
        text = md.read_text(encoding="utf-8", errors="ignore")
        for m in pat.finditer(text):
            rel = m.group(1).lstrip("./")
            if rel in seen:
                continue
            seen.add(rel)
            if not (root / rel).exists():
                missing.append(f"{md.relative_to(root)} -> {rel}")
    return missing, len(seen)


def verify_dir(root: Path):
    print(f"\n=== 校验目录：{root} ===\n")

    pj_path = root / ".codebuddy-plugin" / "plugin.json"
    if not check("plugin.json 存在", pj_path.exists(), str(pj_path)):
        return
    try:
        pj = json.loads(pj_path.read_text(encoding="utf-8"))
        check("plugin.json 是合法 JSON", True)
    except Exception as e:
        check("plugin.json 是合法 JSON", False, str(e))
        return

    for f in ("name", "version", "description", "author", "avatar", "agentName", "expertType"):
        check(f"必填字段 {f}", bool(pj.get(f)), str(pj.get(f, ""))[:60])

    name = pj.get("name", "")
    check("name 为 kebab-case", bool(re.fullmatch(r"[a-z0-9][a-z0-9-]*[a-z0-9]", name)), name)
    check("plugin 与 name 一致", pj.get("plugin") == name, f"{pj.get('plugin')} vs {name}")
    check("expertType 合法", pj.get("expertType") in ("agent", "team"), pj.get("expertType", ""))

    agent_name = pj.get("agentName", "")
    md = root / "agents" / f"{agent_name}.md"
    if check("agentName 对应 MD 存在", md.exists(), f"agents/{agent_name}.md"):
        text = md.read_text(encoding="utf-8", errors="ignore")
        fm = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
        if check("Agent MD 有 frontmatter", bool(fm)):
            body = fm.group(1)
            m_name = re.search(r"^name:\s*(.+)$", body, re.MULTILINE)
            check("frontmatter name 与文件名一致",
                  bool(m_name) and m_name.group(1).strip().strip('"') == agent_name,
                  m_name.group(1).strip() if m_name else "缺失")
            check("frontmatter 未含 tools 字段", "tools:" not in body)

    # 头像 —— 这是"图标变文字"最常见的根因
    avatar = pj.get("avatar", "")
    ap = root / avatar if avatar else None
    if check("avatar 文件存在", bool(ap and ap.exists()), avatar or "avatar 字段为空"):
        size = ap.stat().st_size
        fmt, w, h = image_info(ap)
        check("头像为 PNG/JPEG", fmt is not None, f"识别为 {fmt}")
        check("头像为正方形", w == h and w > 0, f"{w}x{h}")
        check("头像体积 < 5MB", size < AVATAR_MAX_BYTES, f"{size / 1024:.0f} KB")
        check("头像体积 ≤ 500KB（规范建议）", size <= 500 * 1024, f"{size / 1024:.0f} KB")
        check("头像尺寸 ≥ 256px", w >= 256, f"{w}px")
        # 路径必须在包内，不允许跳出根目录
        try:
            ap.resolve().relative_to(root.resolve())
            check("avatar 路径在包内", True)
        except ValueError:
            check("avatar 路径在包内", False, "路径越界")

    # 头像目录只应保留被声明的文件，避免原图/预览图把包撑大
    avatar_dir = root / "avatars"
    if avatar_dir.exists():
        extra = [p.name for p in avatar_dir.iterdir() if p.is_file() and p.name not in (Path(avatar).name, ".gitkeep")]
        check("avatars/ 无多余文件", not extra, ", ".join(extra) or "仅头像")

    tags = pj.get("tags", [])
    check("tags 恰好 3 条", isinstance(tags, list) and len(tags) == 3, str(len(tags)))
    qp = pj.get("quickPrompts", [])
    check("quickPrompts 恰好 3 条", isinstance(qp, list) and len(qp) == 3, str(len(qp)))
    dip = pj.get("defaultInitPrompt", {})
    if qp and isinstance(qp[0], dict):
        check("defaultInitPrompt 与 quickPrompts[0] 一致",
              dip.get("zh") == qp[0].get("zh"), "zh 文本一致" if dip.get("zh") == qp[0].get("zh") else "不一致")

    for i18n in ("displayName", "profession", "displayDescription"):
        v = pj.get(i18n, {})
        check(f"{i18n} 中英文齐全", isinstance(v, dict) and bool(v.get("en")) and bool(v.get("zh")))

    check("categoryId 已填", bool(pj.get("categoryId")), pj.get("categoryId", ""))

    for forbidden in ("hooks", "commands"):
        check(f"无禁用目录 {forbidden}/", not (root / forbidden).exists())
    check("无 .lsp.json", not (root / ".lsp.json").exists())
    check("manifest.yaml 存在（官方导出附带）", (root / "manifest.yaml").exists())

    missing, total = gather_md_links(root)
    check(f"文档内相对引用可解析（共 {total} 条）", not missing,
          "全部存在" if not missing else "; ".join(missing[:6]))

    print("\n--- 汇总 ---")
    fail = [r for r in results if not r[1]]
    print(f"共 {len(results)} 项，通过 {len(results) - len(fail)} 项，失败 {len(fail)} 项")
    if fail:
        print("失败项：")
        for n, _, d in fail:
            print(f"  - {n} {d}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    target = Path(sys.argv[1]).resolve()
    if not target.exists():
        print(f"[错误] 路径不存在：{target}", file=sys.stderr)
        sys.exit(1)

    if target.is_dir():
        verify_dir(target)
    else:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            with zipfile.ZipFile(target) as zf:
                names = zf.namelist()
                tops = {n.split("/")[0] for n in names if n.strip("/")}
                check("zip 为单一顶层目录", len(tops) == 1, ", ".join(sorted(tops))[:120])
                zf.extractall(tmp)
            root = tmp / next(iter(tops))
            verify_dir(root)

    sys.exit(0 if all(r[1] for r in results) else 1)


if __name__ == "__main__":
    main()
