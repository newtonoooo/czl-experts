#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""专家包自检工具。

用法：
    python check_package.py <专家目录>
    python check_package.py <专家包.zip>
    python check_package.py <专家目录> --marketplace <市场plugins目录>   # 额外做重名检查

检查四类问题：
    A 元数据：必填项、双语字段、标签与推荐提示词数量、description 字数、分类
    B 引用：agents / knowledge / avatar 指向的文件是否真实存在
    C 头像：PNG 是否可解码、是否 512x512、8 位、RGB/RGBA、≤500KB、路径写法
    D 压缩包：清单位置、头像条目、顶层目录层数、系统垃圾文件、路径分隔符

退出码：0 全过；1 有错误；2 只有警告。
"""

import argparse
import json
import os
import struct
import sys
import zipfile

MANIFEST_DIRS = (".codebuddy-plugin", ".workbuddy-plugin")
MANIFEST_NAME = "plugin.json"
AVATAR_LIMIT = 500 * 1024

CATEGORIES = {
    "01-ProductDesign", "02-Engineering", "03-GameSpatial", "04-DataAI",
    "05-MarketingGrowth", "06-ContentCreative", "07-SalesCommerce",
    "08-FinanceInvestment", "09-OperationsHR", "10-ProjectQuality",
    "11-SecurityCompliance", "12-IndustryConsultant", "15-Education",
}

errors, warnings, notes = [], [], []


def err(m):
    errors.append(m)


def warn(m):
    warnings.append(m)


def note(m):
    notes.append(m)


def png_header(data):
    if len(data) < 33 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    try:
        w, h = struct.unpack(">II", data[16:24])
    except struct.error:
        return None
    return w, h, data[24], data[25]


def check_manifest(m, label):
    for f in ("name", "version", "description"):
        if not m.get(f):
            err("%s 缺必填字段 %s" % (label, f))

    name = m.get("name", "")
    if name and not all(c.islower() or c.isdigit() or c == "-" for c in name):
        err("%s 的 name 只能是小写字母/数字/连字符：%s" % (label, name))

    if m.get("plugin") and m["plugin"] != name:
        err("%s 的 plugin 与 name 不一致" % label)

    if m.get("expertType") not in ("agent", "team"):
        err("%s 的 expertType 必须是 agent 或 team" % label)

    for f in ("displayName", "profession", "displayDescription", "defaultInitPrompt"):
        v = m.get(f)
        if not isinstance(v, dict) or not v.get("zh") or not v.get("en"):
            err("%s 的 %s 需要 zh 与 en 同时有值" % (label, f))

    # 名称字段字符集：中英文、数字、- 与 —
    for f in ("displayName", "profession"):
        zh = (m.get(f) or {}).get("zh", "")
        bad = [c for c in zh if not (c.isalnum() or c in "-—" or "\u4e00" <= c <= "\u9fff")]
        if bad:
            err("%s 的 %s.zh 含不允许的字符：%s" % (label, f, "".join(bad)))

    dd = (m.get("displayDescription") or {}).get("zh", "")
    if dd and not 40 <= len(dd) <= 50:
        warn("%s 的 displayDescription.zh 为 %d 字（规范 40—50）" % (label, len(dd)))

    if len(m.get("tags") or []) != 3:
        err("%s 的 tags 必须正好 3 个" % label)
    qp = m.get("quickPrompts") or []
    if len(qp) != 3:
        err("%s 的 quickPrompts 必须正好 3 个" % label)
    if qp and (m.get("defaultInitPrompt") or {}).get("zh") != (qp[0] or {}).get("zh"):
        err("%s 的 defaultInitPrompt.zh 必须与 quickPrompts[0].zh 一致" % label)

    cat = m.get("categoryId", "")
    if cat not in CATEGORIES:
        err("%s 的 categoryId 不在已知分类：%s" % (label, cat))
    elif cat == "15-Education":
        note("categoryId=15-Education（教育类在架专家通用），部分旧版校验器未收录，可能误报")


def check_png(data, label):
    info = png_header(data)
    if not info:
        err("%s 不是可解码的 PNG；客户端会退化成名称首字" % label)
        return
    w, h, depth, ctype = info
    if (w, h) != (512, 512):
        err("%s 尺寸 %dx%d，必须是 512x512（非正方形在列表里会被裁切）" % (label, w, h))
    if depth != 8:
        err("%s 位深 %d，必须是 8 位" % (label, depth))
    if ctype not in (2, 6):
        warn("%s 色彩类型 %d（建议 2=RGB 或 6=RGBA）" % (label, ctype))
    if len(data) > AVATAR_LIMIT:
        err("%s 为 %.0f KB，超过 500KB 上限" % (label, len(data) / 1024.0))


def check_dir(root, market):
    mpath = None
    for d in MANIFEST_DIRS:
        p = os.path.join(root, d, MANIFEST_NAME)
        if os.path.exists(p):
            mpath = p
            break
    if not mpath:
        err("找不到清单文件（%s 下的 plugin.json）" % " 或 ".join(MANIFEST_DIRS))
        return

    m = json.load(open(mpath, encoding="utf-8"))
    check_manifest(m, "plugin.json")

    an = m.get("agentName", "")
    if not os.path.exists(os.path.join(root, "agents", an + ".md")):
        err("agentName 指向的文件不存在：agents/%s.md" % an)

    def rel(p):
        return p[2:] if p.startswith("./") else p

    for p in m.get("agents") or []:
        if not os.path.exists(os.path.join(root, rel(p))):
            err("agents 路径不存在：%s" % p)
    for p in m.get("knowledge") or []:
        if not os.path.exists(os.path.join(root, rel(p))):
            err("knowledge 路径不存在：%s" % p)
    for p in m.get("skills") or []:
        if not os.path.exists(os.path.join(root, rel(p), "SKILL.md")):
            err("skills 缺 SKILL.md：%s" % p)

    av = m.get("avatar", "")
    if not av:
        err("avatar 为空，客户端必然显示首字")
    else:
        if av.startswith("./") or av.startswith("/") or "\\" in av:
            err("avatar 必须写成不带前缀的相对路径，且用正斜杠：%s" % av)
        ap = os.path.join(root, av)
        if not os.path.exists(ap):
            err("avatar 指向的文件不存在：%s" % av)
        else:
            check_png(open(ap, "rb").read(), av)

    # 工序卡是否齐全并在主提示词中被引用
    md = open(os.path.join(root, "agents", an + ".md"), encoding="utf-8").read()
    wf_dir = os.path.join(root, "workflows")
    if os.path.isdir(wf_dir):
        cards = sorted(f for f in os.listdir(wf_dir) if f.endswith(".md"))
        for c in cards:
            if c not in md:
                warn("工序卡 %s 未在主提示词中引用" % c)
        note("工序卡 %d 张：%s" % (len(cards), "、".join(cards)))

    for d in ("docs", "README.md", "CHANGELOG.md", "LICENSE"):
        if not os.path.exists(os.path.join(root, d)):
            warn("缺少 %s" % d)

    if market:
        me = os.path.basename(os.path.abspath(root))
        hits = []
        for other in os.listdir(market):
            if other == me:
                continue
            om = None
            for d in MANIFEST_DIRS:
                p = os.path.join(market, other, d, MANIFEST_NAME)
                if os.path.exists(p):
                    om = p
                    break
            if not om:
                continue
            try:
                o = json.load(open(om, encoding="utf-8"))
            except Exception:
                continue
            if o.get("name") == m.get("name"):
                hits.append(other + "（name 重复）")
            if (o.get("profession") or {}).get("zh") == (m.get("profession") or {}).get("zh"):
                hits.append(other + "（profession 重复）")
        if hits:
            err("与市场内专家重复：%s" % "；".join(hits))
        else:
            note("重名检查通过：name 与 profession 在市场内均无重复")


def check_zip(zp):
    if not zipfile.is_zipfile(zp):
        err("不是有效的 zip")
        return
    z = zipfile.ZipFile(zp)
    names = [n for n in z.namelist() if not n.endswith("/")]

    if any("\\" in n for n in names):
        err("压缩包内含反斜杠路径（Windows 打包常见），客户端解析不到")

    entries = [n for n in names if n.endswith("/" + MANIFEST_NAME) or n == MANIFEST_NAME]
    if not entries:
        err("压缩包内找不到 plugin.json")
        return
    if len(entries) > 1:
        err("压缩包内有多个 plugin.json：%s" % entries)

    entry = entries[0]
    # 顶层目录 = 清单路径去掉末尾的「插件目录/plugin.json」两段
    parts = entry.split("/")
    base = "/".join(parts[:-2]) if len(parts) >= 2 else ""
    m = json.loads(z.read(entry).decode("utf-8"))
    check_manifest(m, "zip/plugin.json")

    tops = {n.split("/")[0] for n in names}
    if base and len(tops) > 1:
        err("压缩包顶层有多个目录，导入后会散落：%s" % sorted(tops))
    note("压缩包顶层目录：%s" % (base or "（无，清单在根）"))

    av = m.get("avatar", "")
    if not av:
        err("zip 内 avatar 为空")
    else:
        rel = av.lstrip("./").lstrip("/")
        cands = [("%s/%s" % (base, rel)) if base else rel, rel]
        hit = next((c for c in cands if c in names), None)
        if not hit:
            err("压缩包内找不到头像 %s —— 客户端取不到文件就显示名称首字，这就是"
                "「导入后小图标变文字」最常见的原因" % cands[0])
        else:
            check_png(z.read(hit), hit)

    junk = [n for n in names if n.startswith("__MACOSX/") or n.endswith(".DS_Store")
            or n.endswith("Thumbs.db") or n.startswith("._") or n.endswith(".pyc")]
    if junk:
        warn("压缩包内有系统/缓存垃圾 %d 个：%s" % (len(junk), junk[:5]))

    if not any(n.startswith((base + "/agents/") if base else "agents/") for n in names):
        err("压缩包内缺少 agents/ 目录")
    if not any(n.startswith((base + "/references/") if base else "references/") for n in names):
        warn("压缩包内缺少 references/ 目录，知识库将不可用")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target")
    ap.add_argument("--marketplace", default=None)
    a = ap.parse_args()

    t = os.path.abspath(os.path.expanduser(a.target))
    if not os.path.exists(t):
        print("路径不存在：%s" % t)
        return 1

    print("检查对象：%s\n" % t)
    if os.path.isdir(t):
        check_dir(t, a.marketplace)
    elif t.lower().endswith(".zip"):
        check_zip(t)
    else:
        print("只接受专家目录或 .zip")
        return 1

    for n in notes:
        print("· " + n)
    for w in warnings:
        print("⚠ " + w)
    for e in errors:
        print("✗ " + e)

    print("")
    if errors:
        print("结论：不通过（%d 错 / %d 警告）" % (len(errors), len(warnings)))
        return 1
    if warnings:
        print("结论：通过（%d 警告）" % len(warnings))
        return 2
    print("结论：全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
