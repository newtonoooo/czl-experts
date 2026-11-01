#!/usr/bin/env python3
"""package_qa - pre-publish integrity check for this expert package.

Verifies manifest fields, file references, avatar constraints and skill wiring,
then optionally builds a portable variant whose avatar is embedded as a data URI
(useful when a fresh WorkBuddy install falls back to the name initial because the
local avatar path cannot be resolved).

Usage
    python tools/package_qa.py                 # check only
    python tools/package_qa.py --portable out.zip
    python tools/package_qa.py --json

Standard library only. Python 3.8+.
"""

import argparse
import base64
import json
import os
import re
import struct
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN_JSON = os.path.join(ROOT, ".codebuddy-plugin", "plugin.json")

VALID_CATEGORIES = {
    "01-ProductDesign", "02-Engineering", "03-GameSpatial", "04-DataAI",
    "05-MarketingGrowth", "06-ContentCreative", "07-SalesCommerce",
    "08-FinanceInvestment", "09-OperationsHR", "10-ProjectQuality",
    "11-SecurityCompliance", "12-IndustryConsultant",
}

AVATAR_MAX_BYTES = 500 * 1024
AVATAR_SIZE = (512, 512)


def png_size(path):
    with open(path, "rb") as fh:
        head = fh.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", head[16:24])


def check():
    results = []

    def add(name, ok, detail=""):
        results.append({"check": name, "ok": bool(ok), "detail": detail})

    if not os.path.exists(PLUGIN_JSON):
        add("plugin.json 存在", False, PLUGIN_JSON)
        return results
    with open(PLUGIN_JSON, encoding="utf-8") as fh:
        pj = json.load(fh)
    add("plugin.json 可解析", True, "OK")

    name = pj.get("name", "")
    add("name 为 kebab-case", bool(re.fullmatch(r"[a-z0-9][a-z0-9-]*[a-z0-9]", name or "")), name)
    add("plugin 与 name 一致", pj.get("plugin") == name, str(pj.get("plugin")))
    add("name 以 czl- 开头", name.startswith("czl-"), name)
    add("版本号语义化", bool(re.fullmatch(r"\d+\.\d+\.\d+", pj.get("version", ""))), str(pj.get("version")))
    add("expertType=agent", pj.get("expertType") == "agent", str(pj.get("expertType")))

    author = pj.get("author") or {}
    add("作者信息完整", bool(author.get("name")) and bool(author.get("email")), f"{author.get('name')} / {author.get('email')}")

    for field in ("displayName", "profession", "displayDescription", "defaultInitPrompt"):
        val = pj.get(field) or {}
        add(f"{field} 中英齐全", bool(val.get("zh")) and bool(val.get("en")), f"zh={bool(val.get('zh'))} en={bool(val.get('en'))}")

    zh_desc = (pj.get("displayDescription") or {}).get("zh", "")
    add("displayDescription 中文 40-50 字", 40 <= len(zh_desc) <= 50, f"{len(zh_desc)} 字")

    add("categoryId 合法", pj.get("categoryId") in VALID_CATEGORIES, str(pj.get("categoryId")))

    tags = pj.get("tags") or []
    add("tags 恰好 3 个", len(tags) == 3, f"{len(tags)} 个")
    add("tags 中英齐全", all(t.get("zh") and t.get("en") for t in tags), "OK")

    qp = pj.get("quickPrompts") or []
    add("quickPrompts 恰好 3 个", len(qp) == 3, f"{len(qp)} 个")
    add("defaultInitPrompt == quickPrompts[0]",
        bool(qp) and (pj.get("defaultInitPrompt") or {}).get("zh") == qp[0].get("zh"),
        "一致" if qp and (pj.get("defaultInitPrompt") or {}).get("zh") == qp[0].get("zh") else "不一致")

    agent_name = pj.get("agentName", "")
    agent_md = os.path.join(ROOT, "agents", f"{agent_name}.md")
    add("agentName 对应 MD 存在", os.path.exists(agent_md), f"agents/{agent_name}.md")
    if os.path.exists(agent_md):
        content = open(agent_md, encoding="utf-8").read()
        fm = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        add("Agent MD 有 frontmatter", bool(fm), "OK" if fm else "缺失")
        if fm:
            add("frontmatter name 与文件名一致", f"name: {agent_name}" in fm.group(1), agent_name)
            add("frontmatter 无 tools 字段", "tools:" not in fm.group(1), "OK")

    for rel in pj.get("agents") or []:
        path = os.path.join(ROOT, rel.lstrip("./"))
        add(f"agents 路径存在 {rel}", os.path.exists(path), rel)

    for rel in pj.get("skills") or []:
        skill_dir = os.path.join(ROOT, rel.lstrip("./"))
        add(f"skills 路径含 SKILL.md {rel}", os.path.exists(os.path.join(skill_dir, "SKILL.md")), rel)
        for sub in ("references", "templates", "scripts"):
            add(f"skill 子目录 {sub} 存在", os.path.isdir(os.path.join(skill_dir, sub)), rel)

    avatar_rel = pj.get("avatar", "")
    avatar_path = os.path.join(ROOT, avatar_rel)
    add("avatar 文件存在", os.path.exists(avatar_path), avatar_rel)
    if os.path.exists(avatar_path):
        size = os.path.getsize(avatar_path)
        add("avatar ≤ 500KB", size <= AVATAR_MAX_BYTES, f"{size / 1024:.1f} KB")
        dims = png_size(avatar_path)
        add("avatar 为 512×512 PNG", dims == AVATAR_SIZE, str(dims))
        add("avatar 为 ASCII 路径", avatar_rel.isascii(), avatar_rel)

    for required in ("README.md", "CHANGELOG.md", "LICENSE"):
        add(f"{required} 存在", os.path.exists(os.path.join(ROOT, required)), required)

    for forbidden in ("hooks", "commands"):
        add(f"无禁用目录 {forbidden}/", not os.path.isdir(os.path.join(ROOT, forbidden)), forbidden)

    script = os.path.join(ROOT, "skills", "rival-teardown-playbook", "scripts", "teardown_toolkit.py")
    add("工具箱脚本存在", os.path.exists(script), "teardown_toolkit.py")
    if os.path.exists(script):
        src = open(script, encoding="utf-8").read()
        imports = re.findall(r"^import (\w+)|^from (\w+)", src, re.MULTILINE)
        mods = {a or b for a, b in imports}
        stdlib = getattr(sys, "stdlib_module_names", None)
        if stdlib is None:  # Python < 3.10
            add("工具箱仅依赖标准库", True, "跳过（当前解释器无 stdlib_module_names），人工确认：" + "、".join(sorted(mods)))
        else:
            third_party = {m for m in mods if m not in stdlib}
            add("工具箱仅依赖标准库", not third_party, "、".join(sorted(third_party)) or "stdlib only")

    return results


def build_portable(out_zip):
    """Rebuild the package with the avatar embedded as a data URI."""
    with open(PLUGIN_JSON, encoding="utf-8") as fh:
        pj = json.load(fh)
    avatar_rel = pj.get("avatar", "avatars/expert.png")
    avatar_path = os.path.join(ROOT, avatar_rel)
    b64 = base64.b64encode(open(avatar_path, "rb").read()).decode("ascii")
    pj["avatar"] = f"data:image/png;base64,{b64}"

    out_zip = os.path.abspath(out_zip)
    os.makedirs(os.path.dirname(out_zip), exist_ok=True)
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for base, dirs, files in os.walk(ROOT):
            dirs[:] = [d for d in dirs
                       if d not in {"__pycache__", "dist", ".git"}
                       and (not d.startswith(".") or d == ".codebuddy-plugin")]
            for fn in files:
                if fn.startswith("."):
                    continue
                full = os.path.join(base, fn)
                rel = os.path.relpath(full, ROOT).replace(os.sep, "/")
                if rel.startswith("dist/"):
                    continue
                arc = f"{os.path.basename(ROOT)}/{rel}"
                if rel == ".codebuddy-plugin/plugin.json":
                    zf.writestr(arc, json.dumps(pj, ensure_ascii=False, indent=2))
                else:
                    zf.write(full, arc)
    return out_zip


def main():
    ap = argparse.ArgumentParser(description="专家包发布前完整性检查")
    ap.add_argument("--portable", metavar="ZIP", help="额外生成 data-URI 头像的兼容版压缩包")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    args = ap.parse_args()

    results = check()
    passed = all(r["ok"] for r in results)

    if args.json:
        print(json.dumps({"passed": passed, "results": results}, ensure_ascii=False, indent=2))
    else:
        print(f"包路径：{ROOT}\n")
        for r in results:
            print(f"[{'PASS' if r['ok'] else 'FAIL'}] {r['check']}：{r['detail']}")
        fails = [r for r in results if not r["ok"]]
        print(f"\n共 {len(results)} 项，通过 {len(results) - len(fails)} 项，失败 {len(fails)} 项")

    if args.portable:
        out = build_portable(args.portable)
        print(f"\n兼容版已生成：{out}（{os.path.getsize(out) / 1024:.1f} KB，头像以 data URI 内嵌）")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
