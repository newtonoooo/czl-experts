#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""卓识化学 · 专家包结构校验器

用法：
    python tools/validate_package.py [专家包目录]

退出码：0 全部通过；1 存在错误；2 参数/路径问题。

只依赖标准库，不需要第三方包。
"""

from __future__ import annotations

import base64
import json
import os
import re
import struct
import sys

REQUIRED_KEYS = [
    "name", "version", "description", "author", "agents",
    "expertType", "agentName", "displayName", "profession",
    "displayDescription", "avatar", "categoryId", "plugin",
]
REQUIRED_DIRS = ["agents", "playbooks", "knowledge", "materials", "avatars", "tools", "docs"]
PLAYBOOKS = [
    "W0-triage.md", "W1-lesson.md", "W2-assessment.md", "W3-grading.md",
    "W4-diagnosis.md", "W5-explainer.md", "W6-gaokao.md", "W7-chem-lab.md",
    "W8-courseware.md",
]
# 每份 playbook 必须写清的九个要素（用二级标题或编号体现）
PLAYBOOK_ELEMENTS = [
    ("任务职责", ("任务职责",)),
    ("输入参数", ("输入参数",)),
    ("执行步骤", ("执行步骤",)),
    ("判断条件", ("判断条件",)),
    ("输出格式", ("输出格式",)),
    ("异常处理", ("异常处理",)),
    ("必要依赖", ("必要依赖",)),
    ("与其他工作流的关系", ("与其他工作流的关系", "关系")),
]
NAME_ALLOWED = re.compile(r"^[\u4e00-\u9fa5A-Za-z0-9\-—]+$")
BANNED_CLAIMS = ["官方合作", "官方认证", "独家授权", "指定用书", "保过", "必考原题", "100% 提分", "100%提分"]

class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warns: list[str] = []
        self.passed: list[str] = []

    def ok(self, msg: str) -> None:
        self.passed.append(msg)

    def err(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warns.append(msg)

    def dump(self) -> int:
        print("=" * 68)
        print("卓识化学 · 专家包校验")
        print("=" * 68)
        for m in self.passed:
            print(f"  [PASS] {m}")
        for m in self.warns:
            print(f"  [WARN] {m}")
        for m in self.errors:
            print(f"  [FAIL] {m}")
        print("-" * 68)
        print(f"通过 {len(self.passed)} 项 / 警告 {len(self.warns)} 项 / 失败 {len(self.errors)} 项")
        if self.errors:
            print("结论：未通过，修复后再打包。")
            return 1
        print("结论：通过。")
        return 0


def png_size(path: str) -> tuple[int, int] | None:
    with open(path, "rb") as f:
        head = f.read(33)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    w, h = struct.unpack(">II", head[16:24])
    return w, h


def png_size_bytes(blob: bytes) -> tuple[int, int] | None:
    if blob[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    w, h = struct.unpack(">II", blob[16:24])
    return w, h


def read_frontmatter(path: str) -> dict[str, str]:
    """极简 YAML frontmatter 读取：只取顶层 key: value，够用即可。"""
    out: dict[str, str] = {}
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    if not lines or lines[0].strip() != "---":
        return out
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip().strip('"')
    return out


def main() -> int:
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    root = os.path.abspath(root)
    r = Report()

    if not os.path.isdir(root):
        print(f"路径不存在：{root}")
        return 2
    r.ok(f"专家包目录：{root}")

    # 1 目录
    for d in REQUIRED_DIRS:
        p = os.path.join(root, d)
        if os.path.isdir(p):
            r.ok(f"目录存在：{d}/")
        else:
            r.err(f"缺少目录：{d}/")

    # 2 plugin.json
    pj = os.path.join(root, ".codebuddy-plugin", "plugin.json")
    if not os.path.isfile(pj):
        r.err("缺少 .codebuddy-plugin/plugin.json")
        return r.dump()
    try:
        with open(pj, encoding="utf-8") as f:
            m = json.load(f)
        r.ok("plugin.json 可解析为合法 JSON")
    except Exception as e:  # noqa: BLE001
        r.err(f"plugin.json 解析失败：{e}")
        return r.dump()

    for k in REQUIRED_KEYS:
        if k in m:
            r.ok(f"清单字段存在：{k}")
        else:
            r.err(f"清单缺少字段：{k}")

    # 3 标识与命名
    name = m.get("name", "")
    if re.fullmatch(r"[a-z0-9][a-z0-9._-]*", name or ""):
        r.ok(f"专家标识合法：{name}")
    else:
        r.err(f"专家标识不合法（只允许小写字母/数字/.-_）：{name!r}")
    if name.startswith("czl-"):
        r.ok("专家标识以 czl- 开头")
    else:
        r.err("专家标识未以 czl- 开头")
    if name == os.path.basename(root):
        r.ok("专家标识与目录名一致")
    else:
        r.warn(f"专家标识({name}) 与目录名({os.path.basename(root)}) 不一致")

    for field in ("displayName", "profession"):
        v = m.get(field, {})
        zh = v.get("zh", "") if isinstance(v, dict) else str(v)
        if not zh:
            r.err(f"{field}.zh 为空")
        elif NAME_ALLOWED.fullmatch(zh):
            r.ok(f"{field}.zh 字符合规：{zh}")
        else:
            r.err(f"{field}.zh 含空格或特殊字符：{zh!r}")
        if isinstance(v, dict) and not v.get("en"):
            r.warn(f"{field}.en 为空（建议补英文）")

    if m.get("author", {}).get("name") != "虫志龙":
        r.err("作者名不是 虫志龙")
    else:
        r.ok("作者名：虫志龙")
    if m.get("author", {}).get("email") != "47190078@qq.com":
        r.err("作者邮箱不是 47190078@qq.com")
    else:
        r.ok("作者邮箱：47190078@qq.com")

    if m.get("version") and re.fullmatch(r"\d+\.\d+\.\d+", m["version"]):
        r.ok(f"版本号合法：{m['version']}")
    else:
        r.err(f"版本号格式不合法：{m.get('version')!r}")

    # 4 头像
    av = m.get("avatar", "")
    if isinstance(av, str) and av.startswith("data:image/"):
        try:
            b64 = av.split(",", 1)[1]
            blob = base64.b64decode(b64, validate=True)
            size = png_size_bytes(blob)
            if size:
                w, h = size
                if w == h and w >= 128:
                    r.ok(f"头像为内嵌 PNG，{w}x{h}，{len(blob)/1024:.1f} KB")
                else:
                    r.err(f"头像不是正方形或尺寸过小：{w}x{h}")
                if len(blob) > 5 * 1024 * 1024:
                    r.err("头像原始字节超过 5 MB（客户端会拒绝解析）")
            else:
                r.err("头像 data URL 解码后不是有效 PNG")
        except Exception as e:  # noqa: BLE001
            r.err(f"头像 data URL 解码失败：{e}")
        if os.path.isfile(os.path.join(root, "avatars", "expert-512.png")):
            r.ok("保留 512 母版 avatars/expert-512.png（供市场投稿用）")
        else:
            r.warn("缺少 avatars/expert-512.png 母版")
        r.warn("avatar 为 data URL：本地显示更稳，但市场校验会判为『（无扩展名）』而驳回，"
               "提交前请执行 python tools/avatar_mode.py --mode relative")
    elif isinstance(av, str) and av:
        p = os.path.join(root, av.lstrip("./"))
        ext = os.path.splitext(av)[1].lower()
        if ext in (".png", ".jpg", ".jpeg", ".webp"):
            r.ok(f"头像扩展名合规（市场要求 png/jpg/webp）：{ext}")
        else:
            r.err(f"头像扩展名不合规（市场会判为『无扩展名』）：{av}")
        if os.path.isfile(p):
            size = png_size(p)
            if size and size[0] == size[1]:
                r.ok(f"头像文件存在且为正方形 PNG：{av} ({size[0]}x{size[1]})")
            else:
                r.err(f"头像文件不是正方形 PNG：{av}")
        else:
            r.err(f"头像文件不存在：{av}")
    else:
        r.err("avatar 字段为空")

    # 4.1 平台上架展示字段规则（按平台校验报错原文复刻）
    dd = m.get("displayDescription") or {}
    if isinstance(dd, dict):
        zh_dd = dd.get("zh") or ""
        if not zh_dd:
            r.err("displayDescription.zh 为空")
        elif len(zh_dd) <= 100:
            r.ok(f"displayDescription.zh 长度 {len(zh_dd)} / 上限 100 字")
        else:
            r.err(f"displayDescription.zh 长度 {len(zh_dd)}，超过平台上限 100 字（当前会驳回）")
        en_dd = dd.get("en") or ""
        if len(en_dd) > 400:
            r.warn(f"displayDescription.en 长度 {len(en_dd)}，偏长（建议 ≤400 字符）")

    dip = m.get("defaultInitPrompt") or {}
    qp = m.get("quickPrompts") or []
    if not qp:
        r.err("quickPrompts 为空（平台要求至少 1 条）")
    else:
        first = qp[0] if isinstance(qp[0], dict) else {}
        for lang in ("zh", "en"):
            if dip.get(lang) == first.get(lang):
                r.ok(f"defaultInitPrompt.{lang} 与 quickPrompts[0].{lang} 完全一致")
            else:
                r.err(f"defaultInitPrompt.{lang} 必须与 quickPrompts[0].{lang} 完全一致（平台硬规则）")

    # 5 agents 与 frontmatter
    agents = m.get("agents") or []
    if not agents:
        r.err("agents 为空")
    for a in agents:
        p = os.path.join(root, a.lstrip("./"))
        if os.path.isfile(p):
            fm = read_frontmatter(p)
            r.ok(f"智能体文件存在：{a}")
            if fm.get("name") == m.get("agentName"):
                r.ok("智能体 frontmatter name 与 agentName 一致")
            else:
                r.err(f"frontmatter name({fm.get('name')}) 与 agentName({m.get('agentName')}) 不一致")
            body = open(p, encoding="utf-8").read()
            if len(body) < 1500:
                r.warn(f"主提示词偏短（{len(body)} 字符），可能信息不足")
            else:
                r.ok(f"主提示词长度 {len(body)} 字符")
        else:
            r.err(f"智能体文件不存在：{a}")

    # 6 playbooks 九要素
    for pb in PLAYBOOKS:
        p = os.path.join(root, "playbooks", pb)
        if not os.path.isfile(p):
            r.err(f"缺少工作流文件：playbooks/{pb}")
            continue
        text = open(p, encoding="utf-8").read()
        missing = [label for label, keys in PLAYBOOK_ELEMENTS if not any(k in text for k in keys)]
        if not text.lstrip().startswith("# W"):
            r.err(f"playbooks/{pb} 标题不以 '# W' 开头")
        if missing:
            r.err(f"playbooks/{pb} 缺少要素：{'、'.join(missing)}")
        else:
            r.ok(f"playbooks/{pb} 九要素齐全（{len(text)} 字符）")

    # 7 knowledge 引用
    kn = m.get("knowledge") or []
    if not kn:
        r.warn("未声明 knowledge 列表")
    for k in kn:
        p = os.path.join(root, k.lstrip("./"))
        if os.path.isfile(p):
            r.ok(f"知识库文件存在：{k}")
        else:
            r.err(f"知识库文件不存在：{k}")
    for extra in ("knowledge/00-index.md",):
        if not os.path.isfile(os.path.join(root, extra)):
            r.err(f"缺少知识库索引：{extra}")

    # 8 宣传文案不得虚构
    blob = json.dumps(m, ensure_ascii=False)
    hits = [w for w in BANNED_CLAIMS if w in blob]
    if hits:
        r.err(f"宣传文案含不可用的绝对化表述：{hits}")
    else:
        r.ok("宣传文案未出现绝对化/虚构表述")

    # 9 关键文档
    for doc in ("README.md", "CHANGELOG.md", "VERSION", "LICENSE"):
        if os.path.isfile(os.path.join(root, doc)):
            r.ok(f"根文件存在：{doc}")
        else:
            r.err(f"缺少根文件：{doc}")

    # 10 统计
    total = 0
    for base, _dirs, files in os.walk(root):
        for f in files:
            total += os.path.getsize(os.path.join(base, f))
    r.ok(f"包体积约 {total/1024:.0f} KB")

    return r.dump()


if __name__ == "__main__":
    sys.exit(main())
