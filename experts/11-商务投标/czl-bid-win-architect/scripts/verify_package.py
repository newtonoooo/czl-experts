#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布前自检：按 WorkBuddy 专家包规范逐项核，重点是「图标为什么变成字」这类问题。

包含一项别的校验器不做的检查：**头像能否被客户端解析**。
客户端的取图逻辑是：avatar 字段 → 相对专家目录解析 → 必须落在目录内 → 文件必须存在
→ 转成本地文件 URL 交给 <img>。任何一步失败，avatar 变成空字符串，
界面上就退化成名字首字的色块。本脚本按这条链路逐步核。

用法：
    python verify_package.py <expert-dir>
    python verify_package.py <expert-dir> --zip ../dist/xxx.zip
"""

import argparse
import json
import re
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

MAX_AVATAR_BYTES = 500 * 1024
NEEDED_I18N = ("displayName", "profession", "displayDescription", "defaultInitPrompt")


class Report:
    def __init__(self):
        self.block, self.warn, self.ok = [], [], []

    def b(self, m):
        self.block.append(m)

    def w(self, m):
        self.warn.append(m)

    def g(self, m):
        self.ok.append(m)

    def dump(self):
        print("# 发布前自检\n")
        print(f"通过 {len(self.ok)} 项，警告 {len(self.warn)} 项，阻断 {len(self.block)} 项\n")
        if self.block:
            print("## 阻断（不修就不能发）")
            for x in self.block:
                print(f"- {x}")
            print()
        if self.warn:
            print("## 警告")
            for x in self.warn:
                print(f"- {x}")
            print()
        print("## 通过")
        for x in self.ok:
            print(f"- {x}")


def image_info(p: Path):
    """返回 (格式, 宽, 高)，读不出来返回 (None, 0, 0)。"""
    try:
        data = p.read_bytes()[:256 * 1024]
    except OSError:
        return None, 0, 0
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        try:
            w, h = struct.unpack(">II", data[16:24])
            return "PNG", w, h
        except struct.error:
            return None, 0, 0
    if data[:2] == b"\xff\xd8":
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return "JPEG", w, h
            seg = struct.unpack(">H", data[i + 2:i + 4])[0]
            i += 2 + seg
        return "JPEG", 0, 0
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "WEBP", 0, 0
    return None, 0, 0


def check_avatar(expert: Path, pj: dict, r: Report):
    """按客户端解析链路逐步核。"""
    av = pj.get("avatar")
    if not av:
        r.b("plugin.json 没有 avatar 字段 → 界面会退化成名字首字色块")
        return
    if re.match(r"^(https?|data):", av):
        r.w(f"avatar 是外链（{av[:40]}），离线或断网时会加载失败，建议用包内相对路径")
        return
    if "\\" in av:
        r.w("avatar 里用了反斜杠，统一成正斜杠更稳")
    rel = av[2:] if av.startswith("./") else av
    target = (expert / rel).resolve()
    root = expert.resolve()

    if not str(target).startswith(str(root)):
        r.b(f"avatar 路径逃出了专家目录：{av}")
        return
    if not target.exists():
        r.b(f"avatar 指向的文件不存在：{av} → 解析为空 → 图标变成字")
        return

    size = target.stat().st_size
    if size > MAX_AVATAR_BYTES:
        r.b(f"头像 {size / 1024:.0f}KB，超过 500KB 上限")
    else:
        r.g(f"头像体积 {size / 1024:.0f}KB（上限 500KB）")

    fmt, w, h = image_info(target)
    if fmt is None:
        r.b(f"头像不是可识别的图片（PNG/JPEG），魔数不对：{target.name}")
    else:
        if fmt == "WEBP":
            r.w("头像是 WEBP，部分版本缩略图不支持，建议转 PNG")
        if (w, h) != (512, 512):
            r.w(f"头像尺寸 {w}×{h}，规范要求 512×512；非方图在圆形裁切里会被切边")
        else:
            r.g(f"头像 {fmt} 512×512，格式与尺寸合规")

    if any(ord(c) > 127 for c in target.name):
        r.w(f"头像文件名含非 ASCII 字符（{target.name}），跨系统拷贝有编码风险")
    if " " in target.name:
        r.w("头像文件名含空格，建议改成 expert.png")

    # 包里是否带了 avatars/（有的打包工具会漏掉）
    if not (expert / "avatars").is_dir():
        r.b("avatars/ 目录不存在，打包后客户端找不到头像")

    # 顺手看看别处声明的头像是否存在（team 型的 members）
    for m in pj.get("members") or []:
        mv = m.get("avatar")
        if mv and not (expert / mv.lstrip("./")).exists():
            r.b(f"members 里 {m.get('id')} 的头像不存在：{mv}")


def check_plugin(expert: Path, pj: dict, r: Report):
    name = pj.get("name", "")
    if not name:
        r.b("缺 name")
    elif not re.fullmatch(r"[a-z0-9][a-z0-9-]*[a-z0-9]", name):
        r.b(f"name 必须是 kebab-case：{name}")
    else:
        r.g(f"name={name}（kebab-case）")
    if pj.get("plugin") != name:
        r.b("plugin 字段必须等于 name")
    if expert.name != name:
        r.w(f"目录名（{expert.name}）与 name（{name}）不一致；注册表以 name 为准，"
            f"但打包后的顶层目录建议同名，避免导入时路径对不上")

    ver = pj.get("version", "")
    if not re.fullmatch(r"\d+\.\d+\.\d+", ver or ""):
        r.b(f"version 需为 x.y.z：{ver}")
    else:
        r.g(f"version={ver}")

    for f in NEEDED_I18N:
        v = pj.get(f)
        if not isinstance(v, dict) or not v.get("zh") or not v.get("en"):
            r.b(f"{f} 必须同时有 zh 和 en")
    dd = (pj.get("displayDescription") or {}).get("zh", "")
    n = len(dd)
    if 40 <= n <= 50:
        r.g(f"displayDescription.zh {n} 字（规范 40-50）")
    elif dd:
        r.w(f"displayDescription.zh {n} 字，规范建议 40-50 字")

    tags = pj.get("tags") or []
    if len(tags) != 3:
        r.b(f"tags 必须 3 个，当前 {len(tags)}")
    else:
        r.g("tags 3 个")
    qp = pj.get("quickPrompts") or []
    if len(qp) != 3:
        r.b(f"quickPrompts 必须 3 个，当前 {len(qp)}")
    if qp and isinstance(qp[0], dict):
        if (pj.get("defaultInitPrompt") or {}).get("zh") != qp[0].get("zh"):
            r.w("defaultInitPrompt.zh 应等于 quickPrompts[0].zh")
        else:
            r.g("defaultInitPrompt 与首条 quickPrompt 一致")

    cat = pj.get("categoryId", "")
    valid = {"01-ProductDesign", "02-Engineering", "03-GameSpatial", "04-DataAI",
             "05-MarketingGrowth", "06-ContentCreative", "07-SalesCommerce",
             "08-FinanceInvestment", "09-OperationsHR", "10-ProjectQuality",
             "11-SecurityCompliance", "12-IndustryConsultant"}
    if cat not in valid:
        r.b(f"categoryId 不合法：{cat}")
    else:
        r.g(f"categoryId={cat}")

    if pj.get("expertType") not in ("agent", "team"):
        r.b("expertType 必须是 agent 或 team")
    an = pj.get("agentName", "")
    if not (expert / "agents" / f"{an}.md").exists():
        r.b(f"agentName={an} 找不到 agents/{an}.md")
    else:
        r.g(f"agentName={an} 对应文件存在")


def check_agents(expert: Path, r: Report):
    d = expert / "agents"
    mds = sorted(d.glob("*.md")) if d.is_dir() else []
    if not mds:
        r.b("agents/ 下没有 .md")
        return
    for md in mds:
        txt = md.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---", txt, re.DOTALL)
        if not m:
            r.b(f"{md.name} 缺 frontmatter")
            continue
        fm = m.group(1)
        nm = re.search(r"^name:\s*(\S+)", fm, re.M)
        if not nm or nm.group(1).strip("\"'") != md.stem:
            r.b(f"{md.name} frontmatter 的 name 与文件名不一致")
        if re.search(r"^tools:", fm, re.M):
            r.b(f"{md.name} frontmatter 不能有 tools 字段")
        r.g(f"{md.name} frontmatter 合规")


def check_skills(expert: Path, pj: dict, r: Report):
    for sp in pj.get("skills") or []:
        rel = sp[2:] if sp.startswith("./") else sp
        d = expert / rel
        if not (d / "SKILL.md").exists():
            r.b(f"skill 缺 SKILL.md：{sp}")
            continue
        r.g(f"skill 存在：{rel}")
        for py in d.rglob("*.py"):
            try:
                subprocess.run([sys.executable, "-m", "py_compile", str(py)],
                               check=True, capture_output=True)
            except subprocess.CalledProcessError as e:
                r.b(f"脚本语法错误：{py} → {e.stderr.decode('utf-8', 'ignore')[:120]}")
            else:
                r.g(f"脚本可编译：{py.relative_to(expert)}")


def check_zip(zpath: Path, name: str, r: Report):
    if not zpath.exists():
        r.b(f"zip 不存在：{zpath}")
        return
    with zipfile.ZipFile(zpath) as z:
        names = z.namelist()
    tops = {n.split("/")[0] for n in names}
    if len(tops) != 1:
        r.b(f"zip 顶层有 {len(tops)} 个目录：{sorted(tops)[:4]}；必须只有一个")
    elif tops.pop() != name:
        r.b(f"zip 顶层目录与 name 不一致；导入时可能找不到 plugin.json")
    else:
        r.g(f"zip 顶层目录 {name}/，结构正确")
    if not any(n.startswith(f"{name}/.codebuddy-plugin/plugin.json") for n in names):
        r.b("zip 里缺 .codebuddy-plugin/plugin.json")
    if not any("/avatars/" in n for n in names):
        r.b("zip 里没有 avatars/，导入后图标会变成字")
    else:
        r.g("zip 内含 avatars/")
    if any("/__pycache__/" in n or n.endswith(".pyc") for n in names):
        r.w("zip 里带了 __pycache__/.pyc，建议清掉")


def main():
    ap = argparse.ArgumentParser(description="专家包发布前自检")
    ap.add_argument("expert", help="专家目录")
    ap.add_argument("--zip", default=None, help="同时检查打包产物")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    expert = Path(args.expert).resolve()
    r = Report()
    pj_path = expert / ".codebuddy-plugin" / "plugin.json"
    if not pj_path.exists():
        raise SystemExit("找不到 .codebuddy-plugin/plugin.json")
    pj = json.loads(pj_path.read_text(encoding="utf-8"))

    check_plugin(expert, pj, r)
    check_avatar(expert, pj, r)
    check_agents(expert, r)
    check_skills(expert, pj, r)
    if args.zip:
        check_zip(Path(args.zip), pj.get("name", expert.name), r)

    r.dump()
    print()
    print("结论：" + ("有阻断项，不要发布" if r.block else "可以发布"))
    return 1 if r.block else 0


if __name__ == "__main__":
    sys.exit(main())
