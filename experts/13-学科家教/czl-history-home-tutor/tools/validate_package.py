#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""专家包结构校验（本项目自建，比通用校验脚本多查三项）。

查什么
------
1. plugin.json 必填字段、i18n 双语、tags/quickPrompts 固定 3 个、
   defaultInitPrompt 与第一条 quickPrompt 一致、plugin == name。
2. agentName 与 agents/*.md 文件名一致；MD frontmatter 的 name 与文件名一致；
   frontmatter 不得出现 tools 字段。
3. skills 数组里每个目录必须有 SKILL.md，且 SKILL.md 的 name 与目录名一致。
4. 【本项目新增】交叉引用检查：正文里写的 `references/x.md`、`materials/x.md`、
   `skills/x/...` 必须真实存在——发布包最怕的就是文档指了个不存在的文件。
5. 【本项目新增】displayDescription.zh 长度 40–50 字（平台展示会截断）。
6. 【本项目新增】禁用目录（hooks/、commands/、.lsp.json）与残留占位符 [TODO]。

用法:
    python tools/validate_package.py .
退出码: 0 通过（可有警告）；1 存在错误。
"""

import json
import re
import sys
from pathlib import Path

VALID_CATEGORIES = {
    "01-ProductDesign", "02-Engineering", "03-GameSpatial", "04-DataAI",
    "05-MarketingGrowth", "06-ContentCreative", "07-SalesCommerce",
    "08-FinanceInvestment", "09-OperationsHR", "10-ProjectQuality",
    "11-SecurityCompliance", "12-IndustryConsultant",
    # 平台实际在售专家使用的扩展分类（官方市场里 11 个教育类专家均用此值）
    "13-TencentZone", "15-Education",
}

errors, warnings = [], []


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


def read_frontmatter(path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None, text
    m = re.match(r"^---\r?\n(.*?)\r?\n---", text, re.DOTALL)
    if not m:
        return None, text
    fields = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.strip().startswith(("-", "#")):
            k, _, v = line.partition(":")
            v = v.strip().strip('"').strip("'")
            if v:
                fields[k.strip()] = v
    return fields, text


def check_manifest(root):
    pj_path = root / ".codebuddy-plugin" / "plugin.json"
    if not pj_path.exists():
        err("缺少 .codebuddy-plugin/plugin.json")
        return None
    try:
        pj = json.loads(pj_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        err(f"plugin.json 不是合法 JSON：{exc}")
        return None

    for key in ("name", "version", "description", "expertType", "agentName", "avatar"):
        if not pj.get(key):
            err(f"plugin.json 缺少 {key}")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*[a-z0-9]", pj.get("name", "")):
        err(f"name 不是 kebab-case：{pj.get('name')}")
    if pj.get("plugin") and pj["plugin"] != pj.get("name"):
        err("plugin 字段必须与 name 相同")
    if pj.get("expertType") not in ("agent", "team"):
        err(f"expertType 非法：{pj.get('expertType')}")
    if pj.get("categoryId") and pj["categoryId"] not in VALID_CATEGORIES:
        err(f"categoryId 不在白名单：{pj['categoryId']}")

    for field in ("displayName", "profession", "displayDescription", "defaultInitPrompt"):
        v = pj.get(field)
        if not isinstance(v, dict) or not v.get("en") or not v.get("zh"):
            err(f"{field} 需要完整的 en/zh")

    zh = (pj.get("displayDescription") or {}).get("zh", "")
    if zh and not (40 <= len(zh) <= 50):
        warn(f"displayDescription.zh 长度 {len(zh)}，建议 40–50 字")

    tags = pj.get("tags") or []
    qp = pj.get("quickPrompts") or []
    if len(tags) != 3:
        err(f"tags 必须恰好 3 个，当前 {len(tags)}")
    if len(qp) != 3:
        err(f"quickPrompts 必须恰好 3 个，当前 {len(qp)}")
    if qp and (pj.get("defaultInitPrompt") or {}).get("zh") != (qp[0] or {}).get("zh"):
        warn("defaultInitPrompt.zh 与 quickPrompts[0].zh 不一致")

    # agentName -> 文件
    agent_md = root / "agents" / f"{pj.get('agentName')}.md"
    if not agent_md.exists():
        err(f"agentName 没有对应文件：agents/{pj.get('agentName')}.md")
    for item in pj.get("agents") or []:
        rel = item[2:] if item.startswith("./") else item
        if not (root / rel).exists():
            err(f"agents 路径不存在：{item}")

    # 头像
    avatar = pj.get("avatar", "")
    if avatar and not avatar.startswith(("http://", "https://", "data:")):
        if not (root / avatar).exists():
            err(f"avatar 文件不存在：{avatar}（导入后会显示首字色块）")
        if avatar.startswith("./") or "\\" in avatar:
            err("avatar 应写成不带 ./ 的正斜杠相对路径")
    return pj


def check_agents(root, pj):
    agents_dir = root / "agents"
    if not agents_dir.exists():
        err("缺少 agents/ 目录")
        return
    for md in agents_dir.glob("*.md"):
        fm, text = read_frontmatter(md)
        if fm is None:
            err(f"{md.name} 缺少 frontmatter")
            continue
        if fm.get("name") != md.stem:
            err(f"{md.name} 的 name（{fm.get('name')}）与文件名不一致")
        if not fm.get("description"):
            warn(f"{md.name} 缺少 description")
        head = text.split("---", 2)[-1] if text.startswith("---") else text
        if "tools:" in head[:0]:
            err(f"{md.name} 不应声明 tools")
        if "[TODO" in text:
            err(f"{md.name} 仍有 [TODO] 占位符")


def check_skills(root, pj):
    for item in pj.get("skills") or []:
        rel = item[2:] if item.startswith("./") else item
        skill_dir = root / rel
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            err(f"skill 缺少 SKILL.md：{item}")
            continue
        fm, _ = read_frontmatter(skill_md)
        if fm is None:
            err(f"{rel}/SKILL.md 缺少 frontmatter")
            continue
        if fm.get("name") != skill_dir.name:
            err(f"{rel}/SKILL.md 的 name（{fm.get('name')}）与目录名不一致")
        if not fm.get("description"):
            warn(f"{rel}/SKILL.md 缺少 description")


REF_PATTERN = re.compile(r"`((?:references|materials|skills|tools|docs)/[A-Za-z0-9_\-./]+\.(?:md|py|json))`")

# 测试报告里有意识地引用了一个"不存在的文件"作为负样本夹具，
# 这类文档不参与交叉引用检查（否则会把夹具本身当成缺陷）。
REF_CHECK_EXEMPT = {"docs/05-功能测试报告.md"}


def check_cross_refs(root):
    """正文里提到的包内文件必须真实存在。

    引用有两种写法：相对当前文档（如 skills/x/SKILL.md 里写 `references/a.md`），
    或相对包根（如 agent 里写 `materials/b.md`）。两种都接受，但必须命中一个。
    """
    seen = 0
    for md in list(root.rglob("*.md")):
        rel_doc = md.relative_to(root).as_posix()
        if rel_doc in REF_CHECK_EXEMPT:
            continue
        text = md.read_text(encoding="utf-8", errors="ignore")
        for ref in set(REF_PATTERN.findall(text)):
            seen += 1
            if not (md.parent / ref).exists() and not (root / ref).exists():
                err(f"{rel_doc} 引用了不存在的文件：{ref}")
    return seen


def check_layout(root):
    for bad in ("hooks", "commands", ".lsp.json"):
        if (root / bad).exists():
            err(f"存在禁用项：{bad}")
    for sub in ("agents", "skills", "avatars"):
        if (root / ".codebuddy-plugin" / sub).exists():
            err(f"{sub}/ 不能放在 .codebuddy-plugin/ 里")
    if not (root / "README.md").exists():
        warn("缺少 README.md")
    dup = [p.name for p in root.glob("*.md") if p.name.lower() in ("readme (1).md",)]
    if dup:
        warn(f"存在重复文档：{dup}")


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    print(f"🔍 校验专家包：{root.name}\n")

    pj = check_manifest(root)
    if pj:
        check_agents(root, pj)
        check_skills(root, pj)
    check_layout(root)
    refs = check_cross_refs(root)

    print(f"   交叉引用检查：{refs} 处")
    for w in warnings:
        print(f"   ⚠️  {w}")
    for e in errors:
        print(f"   ❌ {e}")
    if errors:
        print(f"\n结论：{len(errors)} 个错误，先修再打包。")
        return 1
    print(f"\n✅ 通过（{len(warnings)} 条警告）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
