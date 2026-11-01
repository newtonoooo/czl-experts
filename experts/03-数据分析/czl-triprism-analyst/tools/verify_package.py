# -*- coding: utf-8 -*-
"""三棱镜 · 发布包自检

上架前跑一遍，检查：清单字段、引用路径、依赖、语法、头像规格、
以及是否混入了不该出现的第三方品牌词。

用法：
  python tools/verify_package.py [包根目录]
退出码：0 全部通过 / 1 有问题
"""

from __future__ import annotations

import json
import os
import py_compile
import re
import struct
import sys

FORBIDDEN = ["花叔", "huashu", "陈云飞", "Alchain", "alchaincyf", "huasheng.ai"]
MAX_AVATAR = 5242880
REQUIRED_AGENT_KEYS = ("name", "description", "displayName", "profession")


def png_size(path):
    with open(path, "rb") as fh:
        head = fh.read(26)
    if not head.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    return struct.unpack(">II", head[16:24])


def frontmatter(path):
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    block = text[3:end]
    out = {}
    for line in block.splitlines():
        if not line.strip() or line.startswith(" "):
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def main(root=None):
    root = root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    problems, notes = [], []
    add = problems.append

    manifest_path = os.path.join(root, ".codebuddy-plugin", "plugin.json")
    if not os.path.exists(manifest_path):
        add("缺少 .codebuddy-plugin/plugin.json")
        print("\n".join(problems))
        return 1
    try:
        m = json.load(open(manifest_path, encoding="utf-8"))
    except json.JSONDecodeError as exc:
        add(f"plugin.json 不是合法 JSON：{exc}")
        print("\n".join(problems))
        return 1

    etype = m.get("expertType")
    if etype not in ("team", "agent"):
        add(f"expertType 应为 team 或 agent，实际 {etype!r}")
    required = ["name", "version", "description", "author", "expertType",
                "agentName", "displayName", "profession", "displayDescription",
                "avatar", "categoryId", "tags", "agents"]
    if etype == "team":
        required += ["members", "teamInfo"]
    for key in required:
        if key not in m:
            add(f"清单缺少字段 {key}")
    if not str(m.get("name", "")).startswith("czl-"):
        add(f"包名应以 czl- 开头，实际 {m.get('name')}")
    if not (m.get("author") or {}).get("email"):
        add("清单缺少作者邮箱")

    # ---- 平台上传校验规则（依 24 个已通过包的实测规格） ----
    tags = m.get("tags") or []
    if len(tags) != 3:
        add(f"tags 必须固定 3 个（平台上传校验要求），当前 {len(tags)} 个")
    for i, t in enumerate(tags):
        if not isinstance(t, dict) or not t.get("zh") or not t.get("en"):
            add(f"tags[{i}] 必须同时有 zh 与 en")

    qp = m.get("quickPrompts") or []
    dip = m.get("defaultInitPrompt") or {}
    if not (1 <= len(qp) <= 3):
        add(f"quickPrompts 建议 1–3 条，当前 {len(qp)} 条")
    if not qp:
        add("quickPrompts 不能为空")
    else:
        if dip.get("zh") != qp[0].get("zh"):
            add("defaultInitPrompt.zh 必须与 quickPrompts[0].zh 完全一致（含标点）")
        if dip.get("en") != qp[0].get("en"):
            add("defaultInitPrompt.en 必须与 quickPrompts[0].en 完全一致")

    dd = m.get("displayDescription") or {}
    if len(dd.get("zh", "")) > 60:
        notes.append(f"displayDescription.zh 长度 {len(dd['zh'])}，已通过包普遍 ≤60，建议压缩")
    if not dd.get("zh") or not dd.get("en"):
        add("displayDescription 必须同时有 zh 与 en")

    allowed = {"name", "version", "description", "author", "license", "keywords",
               "expertType", "agentName", "teamInfo", "agents", "skills",
               "displayName", "profession", "displayDescription", "avatar",
               "categoryId", "defaultInitPrompt", "tags", "quickPrompts",
               "members", "plugin"}
    unknown = set(m) - allowed
    if unknown:
        notes.append(f"含非标准字段 {sorted(unknown)}（平台通常忽略，但建议删除以减少上传风险）")

    # ---- settings.json：仅 Team 型专家上传时强制要求 ----
    settings_path = os.path.join(root, "settings.json")
    if m.get("expertType") == "team":
        if not os.path.exists(settings_path):
            add("缺少 settings.json（Team 型专家必须在插件根目录提供，内容形如 {\"agent\": \"<主 agent 名>\"}）")
        else:
            try:
                st = json.load(open(settings_path, encoding="utf-8"))
            except json.JSONDecodeError as exc:
                add(f"settings.json 不是合法 JSON：{exc}")
                st = None
            if isinstance(st, dict):
                agent_val = st.get("agent")
                if not isinstance(agent_val, str) or not agent_val.strip():
                    add("settings.json 缺少字符串字段 agent")
                elif m.get("agentName") and agent_val.strip() != m["agentName"]:
                    add(f"settings.json 的 agent({agent_val}) 与 plugin.json 的 agentName({m['agentName']}) 不一致")
                if set(st) != {"agent"}:
                    notes.append(f"settings.json 含额外字段 {sorted(set(st) - {'agent'})}，"
                                 "平台按 {agent} 单字段解析，多余字段可能被忽略")
    elif os.path.exists(settings_path):
        notes.append("agent 型专家通常不需要 settings.json（本机 24 个 agent 型包均无此文件）")

    # ---- agent 型专家的结构约束 ----
    if m.get("expertType") == "agent":
        if len(m.get("agents") or []) != 1:
            add(f"agent 型专家应只有 1 个 agent 文件，当前 {len(m.get('agents') or [])} 个")
        if m.get("members") or m.get("teamInfo"):
            add("agent 型专家不应包含 members / teamInfo（那是 team 型专用字段）")

    ver_file = os.path.join(root, "VERSION")
    if os.path.exists(ver_file):
        v = open(ver_file, encoding="utf-8").read().strip()
        if v != m.get("version"):
            add(f"VERSION({v}) 与 plugin.json({m.get('version')}) 不一致")
    else:
        notes.append("没有 VERSION 文件")

    # 头像
    for label, rel in [("主头像", m.get("avatar"))] + \
            [(f"成员 {x.get('id')}", x.get("avatar")) for x in m.get("members") or []]:
        if not rel:
            add(f"{label} 未配置头像")
            continue
        p = os.path.join(root, rel)
        if not os.path.exists(p):
            add(f"{label} 头像文件不存在：{rel}")
            continue
        size = os.path.getsize(p)
        if size > MAX_AVATAR:
            add(f"{label} 头像超过 5MB：{rel}（{size}）")
        wh = png_size(p)
        if wh is None:
            add(f"{label} 不是合法 PNG：{rel}")
        elif wh[0] != wh[1]:
            add(f"{label} 头像不是正方形：{wh}")
        elif wh[0] < 256:
            notes.append(f"{label} 头像边长 {wh[0]}，建议 ≥512")

    # agents
    agent_names = set()
    for rel in m.get("agents") or []:
        p = os.path.join(root, rel.lstrip("./"))
        if not os.path.exists(p):
            add(f"agent 文件不存在：{rel}")
            continue
        fm = frontmatter(p)
        for k in REQUIRED_AGENT_KEYS:
            if k not in fm:
                add(f"{rel} frontmatter 缺少 {k}")
        if fm.get("name"):
            agent_names.add(fm["name"])

    if m.get("agentName") and m["agentName"] not in agent_names:
        add(f"agentName={m['agentName']} 在 agent 文件里找不到同名 frontmatter")
    if etype == "team":
        for member in m.get("members") or []:
            mid = member.get("id")
            if mid and mid not in agent_names:
                add(f"成员 {mid} 没有对应的 agent 文件")
        leads = [x for x in (m.get("members") or []) if x.get("role") == "lead"]
        if len(leads) != 1:
            add(f"应恰好有 1 个 role=lead 的成员，实际 {len(leads)}")
        elif leads[0].get("id") != m.get("agentName"):
            add("role=lead 的成员 id 与 agentName 不一致")
        team = m.get("teamInfo") or {}
        if team.get("leadAgent") != m.get("agentName"):
            add("teamInfo.leadAgent 与 agentName 不一致")
        if set(team.get("memberAgents") or []) - agent_names:
            add(f"teamInfo.memberAgents 含未定义成员：{set(team['memberAgents']) - agent_names}")

    # skills
    for rel in m.get("skills") or []:
        d = os.path.join(root, rel.lstrip("./"))
        if not os.path.isdir(d):
            add(f"技能目录不存在：{rel}")
        elif not os.path.exists(os.path.join(d, "SKILL.md")):
            add(f"技能目录缺少 SKILL.md：{rel}")

    # 语法
    py_files = []
    for base, _dirs, files in os.walk(os.path.join(root, "tools")):
        for f in files:
            if f.endswith(".py"):
                py_files.append(os.path.join(base, f))
    for base, _dirs, files in os.walk(os.path.join(root, "tests")):
        for f in files:
            if f.endswith(".py"):
                py_files.append(os.path.join(base, f))
    for p in py_files:
        try:
            py_compile.compile(p, doraise=True)
        except py_compile.PyCompileError as exc:
            add(f"语法错误：{os.path.relpath(p, root)} :: {exc}")

    # 品牌词泄漏
    scan_ext = {".md", ".py", ".json", ".txt", ".csv"}
    self_path = os.path.abspath(__file__)
    hits = []
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ("out", "dist", "__pycache__", ".git")]
        for f in files:
            if os.path.splitext(f)[1].lower() not in scan_ext:
                continue
            p = os.path.join(base, f)
            if os.path.abspath(p) == self_path:
                continue          # 黑名单词表本身不算泄漏
            try:
                text = open(p, encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                continue
            for word in FORBIDDEN:
                if word.lower() in text.lower():
                    hits.append(f"{os.path.relpath(p, root)} 含「{word}」")
    problems.extend(hits)

    # 依赖
    third_party = set()
    stdlib_hint = {"argparse", "csv", "datetime", "hashlib", "html", "io", "json", "math",
                   "os", "re", "statistics", "struct", "sys", "tempfile", "time",
                   "traceback", "zipfile", "zlib", "xml", "py_compile", "shutil",
                   "subprocess", "random", "typing", "__future__", "collections",
                   "itertools", "unicodedata", "decimal", "calendar", "textwrap"}
    for p in py_files:
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if line.startswith("import "):
                mod = line.split()[1].split(".")[0].rstrip(",")
                if mod not in stdlib_hint and not mod.startswith("triad") and mod != "png_tool":
                    third_party.add(mod)
            elif line.startswith("from "):
                mod = line.split()[1].split(".")[0]
                if mod not in stdlib_hint and not mod.startswith("triad") and mod != "png_tool":
                    third_party.add(mod)
    if third_party:
        add(f"检测到非标准库导入：{sorted(third_party)}")

    # 报告
    print("=" * 56)
    print(f"包根：{root}")
    print(f"包名：{m.get('name')}  版本：{m.get('version')}  类型：{m.get('expertType')}")
    print(f"agent：{len(agent_names)} 个  成员：{len(m.get('members') or [])} 个  "
          f"技能：{len(m.get('skills') or [])} 个  Python 文件：{len(py_files)} 个")
    print("=" * 56)
    if notes:
        print("提示：")
        for n in notes:
            print(f"  · {n}")
    if problems:
        print(f"\n发现 {len(problems)} 个问题：")
        for p in problems:
            print(f"  ✗ {p}")
        return 1
    print("\n✓ 全部检查通过")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
