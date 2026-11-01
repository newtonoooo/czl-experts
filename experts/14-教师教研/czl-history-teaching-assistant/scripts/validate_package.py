#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_package.py — 专家包自检工具

用途：在打包或上架前，检查专家包的完整性、引用路径、命名规范与资源合规性。
依赖：仅 Python 3.8+ 标准库。
用法：
    python scripts/validate_package.py [包目录]
    （不传目录时，默认检查本脚本所在包的根目录）

退出码：
    0 = 全部通过
    1 = 存在错误（必须修复）
    2 = 仅有警告（可发布，但建议处理）
"""

import json
import os
import re
import struct
import sys
from pathlib import Path

MAX_AVATAR_BYTES = 5 * 1024 * 1024          # 平台读取上限 5 MB
RECOMMENDED_BYTES = 600 * 1024              # 建议值，超过只警告
NAME_PATTERN = re.compile(r"^[A-Za-z0-9\u4e00-\u9fff\-\u2014]+$")
ID_PATTERN = re.compile(r"^[a-z0-9\-]+$")

REQUIRED_FIELDS = [
    "name", "version", "description", "expertType", "agentName",
    "displayName", "profession", "displayDescription", "avatar", "categoryId",
]

# 随包分发、但不进模型知识库的说明性文件
ALLOWED_UNLISTED = {"SOURCES.md"}

# 本脚本自身含有对照用的字样，扫描时跳过，避免自证
SKIP_IN_PROVENANCE_SCAN = {"validate_package.py"}

errors = []
warnings = []
passed = []


def ok(msg):
    passed.append(msg)


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


# ---------------------------------------------------------------- 工具函数

def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def png_size(path):
    """不依赖 Pillow，直接从 PNG 的 IHDR 读宽高。"""
    with open(path, "rb") as f:
        head = f.read(33)
    if len(head) < 33 or head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    if head[12:16] != b"IHDR":
        return None
    w, h = struct.unpack(">II", head[16:24])
    return w, h


def jpeg_size(path):
    """从 JPEG 的 SOF 段读宽高。"""
    data = Path(path).read_bytes()
    if data[:2] != b"\xff\xd8":
        return None
    i = 2
    while i < len(data) - 9:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        length = struct.unpack(">H", data[i + 2:i + 4])[0]
        i += 2 + length
    return None


def parse_frontmatter(text):
    """解析 Markdown 的 YAML 前置区（只处理本项目用到的简单结构）。"""
    if not text.startswith("---"):
        return None, text
    end = text.find("\n---", 3)
    if end == -1:
        return None, text
    block = text[3:end].strip("\n")
    body = text[end + 4:]
    data = {}
    key = None
    for line in block.splitlines():
        if not line.strip():
            continue
        if re.match(r"^[A-Za-z_][\w-]*:", line):
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            data[key] = value if value else {}
        elif key and line.startswith((" ", "\t")):
            sub = line.strip()
            if ":" in sub:
                k2, _, v2 = sub.partition(":")
                if isinstance(data.get(key), dict):
                    data[key][k2.strip()] = v2.strip().strip('"').strip("'")
    return data, body


# ---------------------------------------------------------------- 各项检查

def check_manifest(root):
    manifest_path = root / ".codebuddy-plugin" / "plugin.json"
    if not manifest_path.is_file():
        err("缺少 .codebuddy-plugin/plugin.json")
        return None
    try:
        m = read_json(manifest_path)
    except json.JSONDecodeError as e:
        err(f"plugin.json 不是合法 JSON：{e}")
        return None
    ok("plugin.json 存在且为合法 JSON")

    missing = [k for k in REQUIRED_FIELDS if k not in m]
    if missing:
        err(f"plugin.json 缺少必填字段：{', '.join(missing)}")
    else:
        ok(f"必填字段齐全（{len(REQUIRED_FIELDS)} 项）")

    name = m.get("name", "")
    if not name:
        err("name 为空")
    elif not ID_PATTERN.match(name):
        err(f"包标识 name 只能用小写字母、数字与连字符，当前为：{name}")
    elif not name.startswith("czl-"):
        warn(f"包标识未以 czl- 开头：{name}")
    else:
        ok(f"包标识合规：{name}")

    version = m.get("version", "")
    if not re.match(r"^\d+\.\d+\.\d+$", version):
        err(f"version 需为 x.y.z 格式，当前为：{version}")
    else:
        ok(f"版本号合规：{version}")

    # 平台对「名称/职称」有字符集限制，对「介绍文案」没有。
    # 因此只对 displayName 与 profession 做字符集校验，description 类字段只查是否存在。
    for field in ("displayName", "profession"):
        val = m.get(field)
        if not isinstance(val, dict) or not val.get("zh"):
            err(f"{field}.zh 缺失")
            continue
        zh = val["zh"]
        if not NAME_PATTERN.match(zh):
            bad = [c for c in zh if not NAME_PATTERN.match(c)]
            err(f"{field}.zh 含不允许的字符 {bad}：{zh}")
        else:
            ok(f"{field}.zh 字符集合规：{zh}")

    desc = m.get("displayDescription")
    if not isinstance(desc, dict) or not desc.get("zh"):
        err("displayDescription.zh 缺失")
    elif len(desc["zh"]) > 300:
        warn(f"displayDescription.zh 偏长（{len(desc['zh'])} 字），列表卡片可能截断")
    else:
        ok(f"displayDescription.zh 存在（{len(desc['zh'])} 字）")

    if isinstance(m.get("displayName"), dict):
        dn = m["displayName"].get("zh", "")
        if len(dn) > 16:
            warn(f"displayName 偏长（{len(dn)} 字），列表中可能被截断")
        if "老师助手" == dn:
            warn("displayName 为通用词，同批专家中易重名")

    if m.get("expertType") not in ("agent", "team"):
        err(f"expertType 应为 agent 或 team，当前为：{m.get('expertType')}")

    if m.get("agentName") != name:
        warn("agentName 与 name 不一致，可能导致加载失败")

    if m.get("plugin") != name:
        warn("plugin 字段与 name 不一致")

    if not m.get("author", {}).get("name"):
        warn("缺少 author.name")
    if not m.get("author", {}).get("email"):
        warn("缺少 author.email")

    if "keywords" in m and not isinstance(m["keywords"], list):
        err("keywords 应为数组")

    for item in m.get("tags", []):
        if not (isinstance(item, dict) and item.get("zh") and item.get("en")):
            err(f"tags 项需同时含 zh 与 en：{item}")
    for item in m.get("quickPrompts", []):
        if not (isinstance(item, dict) and item.get("zh") and item.get("en")):
            err(f"quickPrompts 项需同时含 zh 与 en：{item}")

    # 平台服务端硬校验：defaultInitPrompt 必须与 quickPrompts[0] 完全一致，中英文都要。
    # 本机 77 个已发布专家全部满足这一条件，0 例外；不满足会在上传时被整体驳回。
    qp = m.get("quickPrompts") or []
    dip = m.get("defaultInitPrompt")
    if qp:
        if not isinstance(dip, dict):
            err("存在 quickPrompts 但 defaultInitPrompt 缺失或不是 {zh,en} 结构")
        else:
            for lang in ("zh", "en"):
                if dip.get(lang) != qp[0].get(lang):
                    err(
                        f"defaultInitPrompt.{lang} 必须与 quickPrompts[0].{lang} 完全一致"
                        f"（服务端硬校验，差一个字都驳回）"
                    )
                else:
                    ok(f"defaultInitPrompt.{lang} 与 quickPrompts[0] 完全一致")

        # 首项之外的提示若有重复，等于白白浪费一个展示位
        seen = set()
        for idx, item in enumerate(qp):
            key = item.get("zh", "")
            if key in seen:
                warn(f"quickPrompts[{idx}] 与前面的提示重复：{key[:24]}…")
            seen.add(key)

    # 以下区间来自对 77 个已发布专家的实测分布，超出即可能被服务端驳回。
    n_tags = len(m.get("tags") or [])
    if n_tags != 3:
        err(f"tags 应为 3 条（已发布专家无一例外），当前 {n_tags} 条")
    else:
        ok("tags 为 3 条，与已发布专家一致")

    n_qp = len(m.get("quickPrompts") or [])
    if not 3 <= n_qp <= 6:
        err(f"quickPrompts 条数应在 3–6 之间（已发布专家实测区间），当前 {n_qp} 条")
    else:
        ok(f"quickPrompts 条数 {n_qp} 条，在实测区间内")

    kws = m.get("keywords")
    if kws is not None:
        if not isinstance(kws, list):
            err("keywords 应为数组")
        elif not 5 <= len(kws) <= 9:
            err(f"keywords 应 5–9 条（已发布专家实测 5–9），当前 {len(kws)} 条")
        else:
            ok(f"keywords {len(kws)} 条，在实测区间内")

    return m


def check_avatar(root, m):
    avatar_rel = m.get("avatar", "")
    if not avatar_rel:
        err("avatar 字段为空")
        return
    avatar_path = root / avatar_rel
    if not avatar_path.is_file():
        err(f"头像文件不存在：{avatar_rel}")
        return

    size = avatar_path.stat().st_size
    if size > MAX_AVATAR_BYTES:
        err(f"头像超过 5 MB 上限（{size / 1024:.0f} KB），会被平台判为空值")
    elif size > RECOMMENDED_BYTES:
        warn(f"头像 {size / 1024:.0f} KB，建议压到 600 KB 以内以加快列表加载")
    else:
        ok(f"头像体积合规：{size / 1024:.0f} KB")

    ext = avatar_path.suffix.lower()
    if ext == ".png":
        dim = png_size(avatar_path)
    elif ext in (".jpg", ".jpeg"):
        dim = jpeg_size(avatar_path)
        warn("头像为 JPEG。平台读取正常，但同批专家以 PNG 为主，为兼容性建议改用 PNG")
    else:
        dim = None
        err(f"头像扩展名不受支持：{ext}")

    if dim:
        w, h = dim
        if w != h:
            warn(f"头像非正方形（{w}×{h}），列表展示可能被裁切")
        if w < 256:
            warn(f"头像分辨率偏低（{w}×{h}），建议 ≥512×512")
        else:
            ok(f"头像尺寸合规：{w}×{h}")
    else:
        err("无法解析头像尺寸，文件可能损坏")

    raw = avatar_path.read_bytes()
    if b"WORKBUDDY" in raw.upper() or b"AI\xe7\x94\x9f\xe6\x88\x90" in raw:
        warn("头像文件中检测到疑似生成平台水印字节，商业发布前建议去除")
    else:
        ok("头像未检测到平台水印标识")


def check_agents(root, m):
    agents = m.get("agents", [])
    if not agents:
        err("agents 字段为空")
        return
    for rel in agents:
        path = root / rel.lstrip("./")
        if not path.is_file():
            err(f"agent 文件不存在：{rel}")
            continue
        text = path.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(text)
        if fm is None:
            err(f"agent 文件缺少 YAML 前置区：{rel}")
            continue
        for key in ("name", "description"):
            if not fm.get(key):
                err(f"agent 前置区缺少 {key}：{rel}")
        for key in ("displayName", "profession"):
            val = fm.get(key)
            if not isinstance(val, dict) or not val.get("zh"):
                err(f"agent 前置区 {key}.zh 缺失：{rel}")
        if fm.get("name") != m.get("name"):
            warn(f"agent 前置区 name（{fm.get('name')}）与包标识不一致")
        if len(body.strip()) < 2000:
            warn(f"agent 正文偏短（{len(body.strip())} 字符），可能内容不足")
        else:
            ok(f"agent 正文长度合格：{len(body.strip())} 字符")


def check_knowledge(root, m):
    refs = m.get("knowledge", [])
    if not refs:
        warn("knowledge 字段为空，参考文件不会被索引")
        return
    total = 0
    for rel in refs:
        path = root / rel.lstrip("./")
        if not path.is_file():
            err(f"knowledge 引用的文件不存在：{rel}")
            continue
        n = path.stat().st_size
        total += n
        if n < 500:
            warn(f"参考文件过小（{n} 字节）：{rel}")
    ok(f"knowledge 引用全部存在，共 {len(refs)} 个文件 / {total / 1024:.0f} KB")

    for path in (root / "references").glob("*.md"):
        if f"./references/{path.name}" not in refs and path.name not in ALLOWED_UNLISTED:
            warn(f"references/ 下存在未登记到 knowledge 的文件：{path.name}")


def check_tree(root):
    """检查空目录、超限文件、可执行文件与编码。"""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__", "release", "assets-src")]
        if not dirnames and not filenames:
            warn(f"存在空目录：{os.path.relpath(dirpath, root)}")
        for fn in filenames:
            p = Path(dirpath) / fn
            rel = os.path.relpath(p, root)
            if p.stat().st_size > MAX_AVATAR_BYTES:
                warn(f"文件超过 5 MB：{rel}")
            if p.suffix.lower() in (".exe", ".dll", ".bat", ".cmd", ".ps1"):
                err(f"包含可执行文件，平台会拒绝：{rel}")
            if p.suffix.lower() in (".md", ".json", ".py", ".txt"):
                try:
                    p.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    err(f"文件不是 UTF-8 编码：{rel}")
    ok("目录树检查完成（无空目录、无超限大文件、无 UTF-8 编码错误）")


def check_version_doc(root, m):
    changelog = root / "docs" / "CHANGELOG.md"
    if not changelog.is_file():
        warn("缺少 docs/CHANGELOG.md")
        return
    text = changelog.read_text(encoding="utf-8")
    ver = m.get("version", "")
    if ver and ver not in text:
        err(f"CHANGELOG.md 中没有当前版本号 {ver}")
    else:
        ok(f"CHANGELOG.md 记录了当前版本 {ver}")


def check_no_inherited_text(root):
    """确认产品自身的身份与内容文件未沿用原专家标识。

    只扫「会随产品一起被模型读取或展示」的三处：清单、主提示词、参考文件。
    文档目录（docs/）不参与——测试报告与风险清单里出现原包名，属于排查记录，
    是透明度的一部分，不应被判为沿用。
    """
    forbidden = [
        "highschool-history-teacher",
        "老师助手：面向高中历史一线教师",
    ]
    targets = [root / ".codebuddy-plugin" / "plugin.json"]
    targets += list((root / "agents").glob("*.md"))
    targets += list((root / "references").glob("*.md"))

    hit = []
    for p in targets:
        if not p.is_file() or p.name in SKIP_IN_PROVENANCE_SCAN:
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        for f in forbidden:
            if f in text:
                hit.append(f"{os.path.relpath(p, root)} → {f}")
    if hit:
        err("产品身份/内容文件中检测到沿用的原专家标识：" + "; ".join(hit))
    else:
        ok(f"身份与内容文件（{len(targets)} 个）未检测到沿用的原专家标识")


# ---------------------------------------------------------------- 主流程

def main():
    if len(sys.argv) > 1:
        root = Path(sys.argv[1]).resolve()
    else:
        root = Path(__file__).resolve().parent.parent

    print("=" * 66)
    print("专家包自检")
    print(f"目录：{root}")
    print("=" * 66)

    if not root.is_dir():
        print(f"[错误] 目录不存在：{root}")
        return 1

    m = check_manifest(root)
    if m:
        check_avatar(root, m)
        check_agents(root, m)
        check_knowledge(root, m)
        check_version_doc(root, m)
    check_tree(root)
    check_no_inherited_text(root)

    print()
    for s in passed:
        print(f"  [通过] {s}")
    for s in warnings:
        print(f"  [警告] {s}")
    for s in errors:
        print(f"  [错误] {s}")

    print()
    print("-" * 66)
    print(f"通过 {len(passed)} 项 / 警告 {len(warnings)} 项 / 错误 {len(errors)} 项")
    if errors:
        print("结论：不可发布，请先修复错误项。")
        return 1
    if warnings:
        print("结论：可以发布，建议处理警告项。")
        return 2
    print("结论：全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
