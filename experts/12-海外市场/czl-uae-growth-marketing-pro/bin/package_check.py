#!/usr/bin/env python3
"""
package_check.py - Self-check the expert package before packaging or upload.

Covers three layers:
  1. WorkBuddy package spec (plugin.json fields, agent frontmatter, skills, structure)
  2. Asset rules (avatar format, squareness, size budget)
  3. Internal integrity (JSON validity, Python syntax, declared paths exist)

Usage:
    python bin/package_check.py            # checks the package this script lives in
    python bin/package_check.py --path .   # explicit path

Exit codes: 0 all pass (warnings allowed), 1 at least one FAIL.
"""

from __future__ import annotations

import argparse
import json
import py_compile
import re
import struct
import sys
import tempfile
from pathlib import Path

VALID_CATEGORY_IDS = {
    "01-ProductDesign", "02-Engineering", "03-GameSpatial", "04-DataAI",
    "05-MarketingGrowth", "06-ContentCreative", "07-SalesCommerce",
    "08-FinanceInvestment", "09-OperationsHR", "10-ProjectQuality",
    "11-SecurityCompliance", "12-IndustryConsultant",
}

RESULTS: list[tuple[str, str, str]] = []  # (level, check, detail)


def ok(check: str, detail: str = "") -> None:
    RESULTS.append(("PASS", check, detail))


def warn(check: str, detail: str = "") -> None:
    RESULTS.append(("WARN", check, detail))


def fail(check: str, detail: str = "") -> None:
    RESULTS.append(("FAIL", check, detail))


def png_info(path: Path):
    with path.open("rb") as fh:
        head = fh.read(33)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    width, height = struct.unpack(">II", head[16:24])
    return width, height, head[24], head[25]


def check_plugin_json(root: Path) -> dict | None:
    pj_path = root / ".codebuddy-plugin" / "plugin.json"
    if not pj_path.exists():
        fail("plugin.json 存在", str(pj_path))
        return None
    try:
        pj = json.loads(pj_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail("plugin.json 合法 JSON", str(exc))
        return None
    ok("plugin.json 存在且合法")

    for field in ("name", "version", "description", "author", "agents", "expertType", "agentName"):
        if not pj.get(field):
            fail(f"必填字段 {field}", "缺失")
    if pj.get("name") and not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", pj["name"]):
        fail("name 为 kebab-case", pj["name"])
    else:
        ok("name 为 kebab-case", pj.get("name", ""))

    if pj.get("plugin") != pj.get("name"):
        fail("plugin 与 name 一致", f"{pj.get('plugin')} != {pj.get('name')}")
    else:
        ok("plugin 与 name 一致")

    if pj.get("expertType") not in ("agent", "team"):
        fail("expertType 合法", str(pj.get("expertType")))
    else:
        ok("expertType 合法", pj["expertType"])

    agent_name = pj.get("agentName", "")
    agent_md = root / "agents" / f"{agent_name}.md"
    if not agent_md.exists():
        fail("agentName 对应 MD 文件", str(agent_md))
    else:
        ok("agentName 对应 MD 文件", f"agents/{agent_name}.md")

    for field in ("displayName", "profession", "displayDescription", "defaultInitPrompt"):
        val = pj.get(field)
        if not isinstance(val, dict) or not val.get("zh") or not val.get("en"):
            fail(f"{field} 双语齐备", json.dumps(val, ensure_ascii=False)[:60])
        else:
            ok(f"{field} 双语齐备")

    tags = pj.get("tags", [])
    if len(tags) != 3:
        fail("tags 恰好 3 个", f"实际 {len(tags)}")
    else:
        ok("tags 恰好 3 个")

    qp = pj.get("quickPrompts", [])
    if len(qp) != 3:
        fail("quickPrompts 恰好 3 个", f"实际 {len(qp)}")
    else:
        ok("quickPrompts 恰好 3 个")

    dip = pj.get("defaultInitPrompt", {})
    if qp and dip.get("zh") != qp[0].get("zh"):
        warn("defaultInitPrompt 与 quickPrompts[0] 一致", "建议保持一致")
    else:
        ok("defaultInitPrompt 与 quickPrompts[0] 一致")

    if pj.get("categoryId") not in VALID_CATEGORY_IDS:
        fail("categoryId 合法", str(pj.get("categoryId")))
    else:
        ok("categoryId 合法", pj["categoryId"])

    desc_zh = pj.get("displayDescription", {}).get("zh", "")
    if not 38 <= len(desc_zh) <= 55:
        warn("displayDescription.zh 长度 40-50", f"实际 {len(desc_zh)} 字")
    else:
        ok("displayDescription.zh 长度合规", f"{len(desc_zh)} 字")

    return pj


def check_avatar(root: Path, pj: dict) -> None:
    avatar_rel = pj.get("avatar", "")
    if not avatar_rel:
        fail("avatar 字段", "缺失")
        return
    if avatar_rel.startswith("./"):
        warn("avatar 路径写法", "建议写 avatars/expert.png，不带 ./ 前缀")
    elif avatar_rel.startswith("/"):
        warn("avatar 路径写法", "不应以 / 开头")

    avatar_path = root / avatar_rel
    if not avatar_path.exists():
        fail("avatar 文件存在", avatar_rel)
        return
    ok("avatar 文件存在", avatar_rel)

    info = png_info(avatar_path)
    if info is None:
        fail("avatar 为 PNG", avatar_rel)
        return
    width, height, depth, color_type = info
    size_kb = avatar_path.stat().st_size / 1024
    if width != height:
        fail("avatar 为正方形", f"{width}x{height}")
    else:
        ok("avatar 为正方形", f"{width}x{height}")
    if width < 256:
        fail("avatar 尺寸足够", f"{width}px < 256px")
    elif width < 512:
        warn("avatar 建议 512x512", f"实际 {width}px")
    else:
        ok("avatar 尺寸足够", f"{width}px")
    if size_kb > 500:
        fail("avatar 体积 <=500KB", f"{size_kb:.0f}KB")
    elif size_kb > 300:
        warn("avatar 体积建议 <=300KB", f"{size_kb:.0f}KB，接近上限时部分客户端可能不加载")
    else:
        ok("avatar 体积安全", f"{size_kb:.0f}KB")
    if depth != 8:
        warn("avatar 位深", f"{depth} bit")


def check_agents(root: Path, pj: dict) -> None:
    declared = pj.get("agents", [])
    for rel in declared:
        path = root / (rel[2:] if rel.startswith("./") else rel)
        if not path.exists():
            fail("agents 声明路径存在", rel)
            continue
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            fail(f"{path.name} frontmatter", "缺少 YAML frontmatter")
            continue
        block = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
        if not block:
            fail(f"{path.name} frontmatter", "格式不合法")
            continue
        fm = block.group(1)
        name_match = re.search(r"^name:\s*(.+)$", fm, re.MULTILINE)
        if not name_match or name_match.group(1).strip().strip('"') != path.stem:
            fail(f"{path.name} frontmatter name 与文件名一致", str(name_match.group(1) if name_match else "缺失"))
        else:
            ok(f"{path.name} frontmatter name 一致")
        if not re.search(r"^description:", fm, re.MULTILINE):
            fail(f"{path.name} frontmatter description", "缺失")
        else:
            ok(f"{path.name} frontmatter description")
        if re.search(r"^tools:", fm, re.MULTILINE):
            fail(f"{path.name} 不得包含 tools 字段")
        else:
            ok(f"{path.name} 无 tools 字段")


def check_skills(root: Path, pj: dict) -> None:
    for rel in pj.get("skills", []):
        skill_dir = root / (rel[2:] if rel.startswith("./") else rel)
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            fail("skill 存在 SKILL.md", rel)
            continue
        text = skill_md.read_text(encoding="utf-8")
        block = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
        if not block:
            fail(f"{skill_dir.name}/SKILL.md frontmatter", "格式不合法")
            continue
        fm = block.group(1)
        name_match = re.search(r"^name:\s*(.+)$", fm, re.MULTILINE)
        if not name_match or name_match.group(1).strip().strip('"') != skill_dir.name:
            fail(f"{skill_dir.name} skill name 与目录名一致", str(name_match.group(1) if name_match else "缺失"))
        else:
            ok(f"{skill_dir.name} skill name 一致")
        if not re.search(r"^description:", fm, re.MULTILINE):
            fail(f"{skill_dir.name} skill description", "缺失")
        else:
            ok(f"{skill_dir.name} skill description")


def check_structure(root: Path) -> None:
    for forbidden in ("hooks", "commands"):
        if (root / forbidden).exists():
            fail(f"禁止目录 {forbidden}/")
    if (root / ".lsp.json").exists():
        fail("禁止文件 .lsp.json")
    ok("无禁止目录与文件")

    for required in ("README.md", "LICENSE", "CHANGELOG.md"):
        if not (root / required).exists():
            warn(f"{required} 存在", "建议补齐")
        else:
            ok(f"{required} 存在")


def check_integrity(root: Path) -> None:
    bad_json = 0
    for path in root.rglob("*.json"):
        if "__pycache__" in path.parts:
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            fail(f"JSON 合法: {path.relative_to(root)}", str(exc))
            bad_json += 1
    if not bad_json:
        ok("全部 JSON 文件合法")

    bad_py = 0
    with tempfile.TemporaryDirectory() as tmp:
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            # Compile into a temp dir: never write build artifacts into the package,
            # and never race another process for a lock next to the source file.
            cfile = Path(tmp) / (path.stem + "_" + str(abs(hash(str(path)))) + ".pyc")
            try:
                py_compile.compile(str(path), doraise=True, cfile=str(cfile))
            except py_compile.PyCompileError as exc:
                fail(f"Python 语法: {path.relative_to(root)}", str(exc).splitlines()[-1][:100])
                bad_py += 1
    if not bad_py:
        ok("全部 Python 文件语法正确")


def summarize() -> int:
    fails = [r for r in RESULTS if r[0] == "FAIL"]
    warns = [r for r in RESULTS if r[0] == "WARN"]
    passes = [r for r in RESULTS if r[0] == "PASS"]

    print("# 专家包自检报告\n")
    print("| 结果 | 检查项 | 详情 |")
    print("|------|--------|------|")
    for level, check, detail in RESULTS:
        if level == "PASS":
            continue
        print(f"| {level} | {check} | {detail} |")
    if not fails and not warns:
        print("| PASS | 全部检查项 | — |")

    print(f"\n合计：PASS {len(passes)} · WARN {len(warns)} · FAIL {len(fails)}")
    if fails:
        print("\n结论：**不通过**，修复 FAIL 项后再打包。")
        return 1
    print("\n结论：**通过**" + ("（存在 WARN，建议优化后发布）" if warns else "。"))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Expert package self-check.")
    parser.add_argument("--path", default=None, help="package root (default: this script's parent)")
    args = parser.parse_args(argv)

    root = Path(args.path).resolve() if args.path else Path(__file__).resolve().parents[1]
    if not (root / ".codebuddy-plugin").exists():
        print(f"[FAIL] not a package root: {root}", file=sys.stderr)
        return 1

    pj = check_plugin_json(root)
    if pj:
        check_avatar(root, pj)
        check_agents(root, pj)
        check_skills(root, pj)
    check_structure(root)
    check_integrity(root)
    return summarize()


if __name__ == "__main__":
    raise SystemExit(main())
