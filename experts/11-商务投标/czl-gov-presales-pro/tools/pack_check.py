#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""专家包自检工具（发布前必跑）。

检查三件事：
1. 结构：plugin.json 位置、禁止目录、命名规范。
2. 引用：agents / skills / avatar 声明的路径是不是真的存在。
3. 打包：zip 内是否包含全部被引用文件、路径是否用正斜杠、有没有多套一层目录。

第 3 项是专门为"导入后头像变成文字"这类问题准备的：导入端按 plugin.json 的
avatar 相对路径去 zip 里找文件，找不到就回退成名字首字。这里提前把路径对上。

用法：
    python tools/pack_check.py <专家目录>
    python tools/pack_check.py <专家目录> --zip dist/xxx.zip
    python tools/pack_check.py <专家目录> --json
"""

import argparse
import json
import struct
import sys
import zipfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

META_DIRS = (".codebuddy-plugin", ".workbuddy-plugin")
FORBIDDEN = ("hooks", "commands", ".lsp.json")
AVATAR_MAX_BYTES = 500 * 1024
AVATAR_MIN_PX = 256
AVATAR_MAX_PX = 2048


class Report:
    def __init__(self):
        self.errors = []
        self.warns = []
        self.oks = []

    def error(self, m):
        self.errors.append(m)

    def warn(self, m):
        self.warns.append(m)

    def ok(self, m):
        self.oks.append(m)

    @property
    def passed(self):
        return not self.errors

    def dump(self):
        for m in self.oks:
            print(f"  [OK]   {m}")
        for m in self.warns:
            print(f"  [警告] {m}")
        for m in self.errors:
            print(f"  [错误] {m}")
        print()
        print(f"结果：{len(self.oks)} 通过 / {len(self.warns)} 警告 / {len(self.errors)} 错误")
        return 0 if self.passed else 1


def image_info(path: Path):
    """读 PNG/JPEG 头，返回 (格式, 宽, 高)。不依赖 Pillow。"""
    b = path.read_bytes()
    if b[:8] == b"\x89PNG\r\n\x1a\n" and len(b) >= 24:
        w, h = struct.unpack(">II", b[16:24])
        return "PNG", w, h
    if b[:2] == b"\xff\xd8":
        i = 2
        while i < len(b) - 9:
            if b[i] != 0xFF:
                i += 1
                continue
            marker = b[i + 1]
            seg_len = struct.unpack(">H", b[i + 2 : i + 4])[0]
            if marker in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", b[i + 5 : i + 9])
                return "JPEG", w, h
            i += 2 + seg_len
        return "JPEG", 0, 0
    return "未知", 0, 0


def check_json(plugin, report):
    for field in ("name", "version", "description", "expertType", "agentName"):
        if not plugin.get(field):
            report.error(f"plugin.json 缺字段 {field}")
    name = plugin.get("name", "")
    if name and not (name.replace("-", "").isalnum() and name == name.lower()):
        report.error(f"name 必须是 kebab-case：{name}")
    if plugin.get("plugin") and plugin["plugin"] != name:
        report.error("plugin 字段必须等于 name")
    for field in ("displayName", "profession", "displayDescription", "defaultInitPrompt"):
        val = plugin.get(field)
        if not isinstance(val, dict) or not val.get("zh") or not val.get("en"):
            report.error(f"{field} 必须同时有 zh 与 en")
    desc = (plugin.get("displayDescription") or {}).get("zh", "")
    if desc:
        n = len(desc)
        if 40 <= n <= 50:
            report.ok(f"displayDescription.zh 长度 {n} 字（建议 40–50）")
        else:
            report.warn(f"displayDescription.zh 长度 {n} 字，建议 40–50")
    tags = plugin.get("tags") or []
    if len(tags) != 3:
        report.error(f"tags 必须恰好 3 个，当前 {len(tags)}")
    qp = plugin.get("quickPrompts") or []
    if len(qp) != 3:
        report.error(f"quickPrompts 必须恰好 3 个，当前 {len(qp)}")
    dip = plugin.get("defaultInitPrompt") or {}
    if qp and isinstance(qp[0], dict) and dip.get("zh") and dip["zh"] != qp[0].get("zh"):
        report.error("defaultInitPrompt 必须等于 quickPrompts[0]")
    if not plugin.get("author", {}).get("name"):
        report.warn("缺 author.name（发布版建议填开发者）")
    if not plugin.get("license"):
        report.warn("缺 license 字段")


def check_avatar(plugin, root, report):
    avatar = plugin.get("avatar")
    if not avatar:
        report.error("plugin.json 未声明 avatar，导入后头像会回退成名字首字")
        return None
    if avatar.startswith(("./", "/")):
        report.warn(f"avatar 建议写相对路径且不带 ./ 前缀：{avatar}")
    rel = avatar.lstrip("./").lstrip("/")
    path = root / rel
    if not path.exists():
        report.error(f"avatar 文件不存在：{rel}（导入端找不到就会退回首字）")
        return None
    size = path.stat().st_size
    kind, w, h = image_info(path)
    if kind == "未知":
        report.error(f"avatar 不是 PNG/JPEG：{rel}")
        return rel
    report.ok(f"avatar 存在：{rel}（{kind} {w}×{h}, {size/1024:.0f} KB）")
    if size > AVATAR_MAX_BYTES:
        report.warn(f"avatar 超过 500 KB（{size/1024:.0f} KB），建议压缩")
    if w == h and AVATAR_MIN_PX <= w <= AVATAR_MAX_PX:
        report.ok(f"avatar 为正方形 {w}×{h}")
    elif w != h:
        report.error(f"avatar 不是正方形：{w}×{h}，列表展示会被裁切")
    else:
        report.warn(f"avatar 尺寸 {w}×{h} 超出建议区间 256–2048")
    return rel


def collect_refs(plugin):
    refs = []
    for p in plugin.get("agents") or []:
        refs.append(p)
    for p in plugin.get("skills") or []:
        refs.append(p + "/SKILL.md")
    for m in plugin.get("members") or []:
        if isinstance(m, dict) and m.get("avatar"):
            refs.append(m["avatar"])
    if plugin.get("avatar"):
        refs.append(plugin["avatar"])
    return [r.lstrip("./").lstrip("/") if r.startswith("./") else r for r in refs]


def check_refs(plugin, root, report):
    for r in collect_refs(plugin):
        r = r.lstrip("./")
        if not (root / r).exists():
            report.error(f"声明的路径不存在：{r}")
    for p in plugin.get("skills") or []:
        rel = p.lstrip("./")
        if not (root / rel / "SKILL.md").exists():
            report.error(f"skills 路径缺 SKILL.md：{rel}")
        else:
            report.ok(f"skill 完整：{rel}")


def check_zip(plugin, root, zip_path, report):
    refs = collect_refs(plugin)
    meta_dir = next((d for d in META_DIRS if (root / d / "plugin.json").exists()), None)
    if meta_dir:
        refs.append(f"{meta_dir}/plugin.json")

    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        if any("\\" in n for n in names):
            report.error("zip 内存在反斜杠路径，部分解压器会当成文件名，导入端会找不到资源")
        if any(n.startswith("/") or ":" in n.split("/")[0] for n in names):
            report.error("zip 内存在绝对路径")
        top = {n.split("/")[0] for n in names}
        if len(top) > 1:
            report.warn(f"zip 根目录下有多个顶层项：{sorted(top)}，导入端可能识别不到专家")
        elif top:
            report.ok(f"zip 顶层目录唯一：{top.pop()}")

        manifest = [n for n in names if n.endswith(f"{meta_dir}/plugin.json")]
        if not manifest:
            report.error("zip 内找不到 plugin.json")
            return
        prefix = manifest[0][: -len(f"{meta_dir}/plugin.json")]
        report.ok(f"plugin.json 在包内路径：{manifest[0]}")

        missing = []
        for r in refs:
            if f"{prefix}{r}" not in names and r not in names:
                missing.append(r)
        if missing:
            for m in missing:
                report.error(f"zip 缺少被引用文件：{m}")
        else:
            report.ok(f"zip 内 {len(refs)} 个被引用文件全部存在")
        report.ok(f"zip 共 {len(names)} 个条目，{zip_path.stat().st_size/1024:.0f} KB")


def main():
    ap = argparse.ArgumentParser(description="专家包发布前自检")
    ap.add_argument("expert_dir")
    ap.add_argument("--zip", dest="zip_path")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    root = Path(args.expert_dir).expanduser().resolve()
    report = Report()

    if not root.is_dir():
        print(f"[错误] 目录不存在：{root}")
        return 2

    meta_dir = next((d for d in META_DIRS if (root / d / "plugin.json").exists()), None)
    if not meta_dir:
        print("[错误] 找不到 .codebuddy-plugin/plugin.json 或 .workbuddy-plugin/plugin.json")
        return 2
    report.ok(f"元数据目录：{meta_dir}")

    plugin = json.loads((root / meta_dir / "plugin.json").read_text(encoding="utf-8"))

    for bad in FORBIDDEN:
        if (root / bad).exists():
            report.error(f"存在禁止项：{bad}")
    for sub in ("agents", "skills", "bin", "avatars"):
        if (root / meta_dir / sub).exists():
            report.error(f"{sub}/ 不能放在 {meta_dir}/ 里面，必须在专家目录根下")

    agent_name = plugin.get("agentName", "")
    if agent_name and not (root / "agents" / f"{agent_name}.md").exists():
        report.error(f"agentName 与文件名不匹配：agents/{agent_name}.md 不存在")
    elif agent_name:
        report.ok(f"主 Agent 文件：agents/{agent_name}.md")

    check_json(plugin, report)
    avatar_rel = check_avatar(plugin, root, report)
    check_refs(plugin, root, report)

    if args.zip_path:
        zp = Path(args.zip_path)
        if zp.exists():
            check_zip(plugin, root, zp, report)
        else:
            report.error(f"zip 不存在：{zp}")

    if args.json:
        print(
            json.dumps(
                {
                    "ok": report.oks,
                    "warnings": report.warns,
                    "errors": report.errors,
                    "passed": report.passed,
                    "avatar": avatar_rel,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if report.passed else 1

    print(f"自检：{root.name}")
    print("-" * 60)
    return report.dump()


if __name__ == "__main__":
    sys.exit(main())
