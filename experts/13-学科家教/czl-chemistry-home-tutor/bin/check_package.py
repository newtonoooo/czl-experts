#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布前自检：结构、引用、头像、注册状态。

用法：
    python check_package.py <专家目录>
    python check_package.py <专家目录> --json

检查项与 WorkBuddy 运行时的实际行为对齐：
  · 清单文件位置：.codebuddy-plugin/plugin.json 或 .workbuddy-plugin/plugin.json
  · 头像：清单里的 avatar 必须是专家目录内的相对路径；文件存在且 ≤ 5 MB；
          路径不能跳出专家目录（运行时越界会直接返回空，界面回退成文字头像）
  · Agent：agents 数组里每个文件都要存在，frontmatter 的 name 必须等于文件名
  · Skill：skills 数组里每个目录都要有 SKILL.md
  · 注册：装在 my-experts 下时，还必须出现在同市场 .codebuddy-plugin/marketplace.json 里

退出码：0 全部通过（允许有警告）；1 存在错误。
"""

import json
import os
import re
import struct
import sys
import zlib

PNG_SIG = b"\x89PNG\r\n\x1a\n"
AVATAR_HARD_LIMIT = 5 * 1024 * 1024      # 运行时上限，超过直接判空
AVATAR_SOFT_LIMIT = 500 * 1024           # 产品规范建议上限
KNOWN_CATEGORIES = {
    "01-ProductDesign", "02-Engineering", "03-GameSpatial", "04-DataAI",
    "05-MarketingGrowth", "06-ContentCreative", "07-SalesCommerce",
    "08-FinanceInvestment", "09-OperationsHR", "10-ProjectQuality",
    "11-SecurityCompliance", "12-IndustryConsultant", "15-Education",
}


class Report:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.infos = []

    def error(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)

    def info(self, msg):
        self.infos.append(msg)


def find_plugin_json(root):
    for d in (".codebuddy-plugin", ".workbuddy-plugin"):
        p = os.path.join(root, d, "plugin.json")
        if os.path.isfile(p):
            return p
    return None


def parse_frontmatter(path):
    text = open(path, encoding="utf-8").read()
    if not text.startswith("---"):
        return None
    m = re.match(r"^---\r?\n(.*?)\r?\n---", text, re.S)
    if not m:
        return None
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.strip().startswith("#"):
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm


def check_png(path, report, label="头像"):
    """校验 PNG 可解码性与规格，返回 (宽, 高, 色彩类型) 或 None。"""
    try:
        data = open(path, "rb").read()
    except OSError as e:
        report.error("%s：无法读取（%s）" % (label, e))
        return None
    if data[:8] != PNG_SIG:
        head = data[:4]
        if head[:2] == b"\xff\xd8":
            report.warn("%s：实际是 JPEG，但扩展名写成 .png；建议统一为 PNG 或改扩展名" % label)
        else:
            report.error("%s：不是有效 PNG（文件头不对），运行时会加载失败并回退成文字" % label)
        return None

    pos, ihdr, idat, bad_crc = 8, None, bytearray(), 0
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        tag = data[pos + 4:pos + 8]
        payload = data[pos + 8:pos + 8 + length]
        if pos + 12 + length > len(data):
            report.error("%s：文件被截断（块 %s 不完整）" % (label, tag.decode("latin-1")))
            return None
        crc = struct.unpack(">I", data[pos + 8 + length:pos + 12 + length])[0]
        if zlib.crc32(tag + payload) & 0xFFFFFFFF != crc:
            bad_crc += 1
        if tag == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", payload)
        elif tag == b"IDAT":
            idat.extend(payload)
        elif tag == b"IEND":
            break
        pos += 12 + length

    if ihdr is None:
        report.error("%s：缺少 IHDR" % label)
        return None
    w, h, depth, color, comp, filt, interlace = ihdr
    if bad_crc:
        report.error("%s：有 %d 个数据块 CRC 校验失败，文件可能损坏" % (label, bad_crc))
    if depth != 8:
        report.warn("%s：色深为 %d 位（多数端支持 8 位，建议转 8 位）" % (label, depth))
    if color not in (2, 6, 0, 4):
        report.warn("%s：色彩类型 %d，建议转成 RGB（类型 2）" % (label, color))
    if interlace != 0:
        report.warn("%s：使用了隔行扫描，部分解码器不兼容" % label)
    try:
        zlib.decompress(bytes(idat))
    except Exception as e:
        report.error("%s：像素数据无法解压（%s）" % (label, e))
        return None
    if w != h:
        report.warn("%s：%d×%d 不是正方形，列表页会被裁切" % (label, w, h))
    if (w, h) != (512, 512):
        report.warn("%s：%d×%d，建议 512×512" % (label, w, h))
    return w, h, color


def check_marketplace(root, name, report):
    """装在 my-experts 下时，确认 marketplace.json 里有这条记录。"""
    norm = root.replace("\\", "/")
    marker = "/marketplaces/my-experts/plugins/"
    if marker not in norm:
        return
    market_root = norm.split(marker)[0] + "/marketplaces/my-experts"
    mf = os.path.join(market_root, ".codebuddy-plugin", "marketplace.json")
    if not os.path.isfile(mf):
        report.error("未找到 %s；缺少注册文件时专家不会出现在专家中心" % os.path.relpath(mf, market_root))
        return
    try:
        data = json.load(open(mf, encoding="utf-8"))
    except Exception as e:
        report.error("marketplace.json 解析失败：%s" % e)
        return
    plugins = data.get("plugins") or []
    entry = next((p for p in plugins if p.get("name") == name), None)
    if not entry:
        report.error("marketplace.json 里没有 name=%s 的记录；需重新运行注册脚本" % name)
        return
    src = entry.get("source", "")
    expected = "./plugins/%s" % os.path.basename(root)
    if src != expected:
        report.warn("marketplace.json 中 source=%s，预期 %s" % (src, expected))
    report.info("marketplace.json 已登记：%s" % name)


def main():
    if len(sys.argv) < 2:
        print("用法：python check_package.py <专家目录> [--json]")
        return 1
    root = os.path.abspath(sys.argv[1])
    as_json = "--json" in sys.argv
    report = Report()

    if not os.path.isdir(root):
        print("目录不存在：%s" % root)
        return 1

    pj_path = find_plugin_json(root)
    if not pj_path:
        report.error("缺少清单文件：.codebuddy-plugin/plugin.json（或 .workbuddy-plugin/plugin.json）")
        return emit(report, as_json)
    try:
        pj = json.load(open(pj_path, encoding="utf-8"))
    except Exception as e:
        report.error("plugin.json 解析失败：%s" % e)
        return emit(report, as_json)
    report.info("清单文件：%s" % os.path.relpath(pj_path, root))

    # 基础字段
    name = pj.get("name", "")
    if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", name or ""):
        report.error("name 必须是 kebab-case（小写字母、数字、连字符），当前：%r" % name)
    if not name.startswith("czl-"):
        report.warn("name 未以 czl- 开头（本产品约定）")
    if pj.get("plugin") and pj.get("plugin") != name:
        report.error("plugin 字段必须等于 name")
    ver = pj.get("version", "")
    if not re.match(r"^\d+\.\d+\.\d+", str(ver)):
        report.error("version 需为语义化版本（如 1.0.0），当前：%r" % ver)
    author = pj.get("author") or {}
    if not author.get("name") or not author.get("email"):
        report.warn("author.name / author.email 不完整")

    # 展示字段
    for field in ("displayName", "profession", "displayDescription", "defaultInitPrompt"):
        val = pj.get(field)
        if not isinstance(val, dict) or not val.get("zh") or not val.get("en"):
            report.error("%s 必须同时有 zh 与 en" % field)
    zh_desc = (pj.get("displayDescription") or {}).get("zh", "")
    if zh_desc and not (40 <= len(zh_desc) <= 50):
        report.warn("displayDescription.zh 长度 %d，建议 40—50 字" % len(zh_desc))
    tags = pj.get("tags") or []
    if len(tags) != 3:
        report.error("tags 必须正好 3 个，当前 %d 个" % len(tags))
    qp = pj.get("quickPrompts") or []
    if len(qp) != 3:
        report.error("quickPrompts 必须正好 3 个，当前 %d 个" % len(qp))
    if qp and isinstance(qp[0], dict):
        if (pj.get("defaultInitPrompt") or {}).get("zh") != qp[0].get("zh"):
            report.warn("defaultInitPrompt.zh 应与 quickPrompts[0].zh 一致")
    cat = pj.get("categoryId", "")
    if cat not in KNOWN_CATEGORIES:
        report.warn("categoryId=%s 不在常见分类清单内，请确认平台支持" % cat)

    # Agent 文件
    agents = pj.get("agents") or []
    if not agents:
        report.error("agents 数组为空")
    for rel in agents:
        path = os.path.join(root, rel.lstrip("./").replace("/", os.sep))
        if not os.path.isfile(path):
            report.error("agents 指向的文件不存在：%s" % rel)
            continue
        fm = parse_frontmatter(path)
        if not fm:
            report.error("%s 缺少 YAML frontmatter" % rel)
            continue
        if fm.get("name") != os.path.splitext(os.path.basename(path))[0]:
            report.error("%s 的 frontmatter name 与文件名不一致" % rel)
        if "tools:" in open(path, encoding="utf-8").read().split("---")[1]:
            report.error("%s 的 frontmatter 不应声明 tools" % rel)
    agent_name = pj.get("agentName", "")
    if agent_name and agent_name != os.path.splitext(os.path.basename(agents[0] if agents else ""))[0]:
        report.warn("agentName 与 agents[0] 文件名不一致")

    # Skill 目录
    for rel in (pj.get("skills") or []):
        sk_dir = os.path.join(root, rel.lstrip("./").replace("/", os.sep))
        sk = os.path.join(sk_dir, "SKILL.md")
        if not os.path.isfile(sk):
            report.error("技能缺少 SKILL.md：%s" % rel)
            continue
        fm = parse_frontmatter(sk)
        if not fm:
            report.error("%s 的 SKILL.md 缺少 frontmatter" % rel)
            continue
        if fm.get("name") != os.path.basename(sk_dir):
            report.error("%s：SKILL.md 的 name 应等于目录名" % rel)
        if not fm.get("description"):
            report.warn("%s：SKILL.md 缺 description" % rel)

    # 头像
    avatar = pj.get("avatar", "")
    if not avatar:
        report.error("缺少 avatar 字段；界面会显示文字头像")
    else:
        rel = avatar.replace("\\", "/").lstrip("./")
        abs_path = os.path.abspath(os.path.join(root, rel))
        try:
            inside = os.path.commonpath([abs_path, root]) == root
        except ValueError:
            inside = False
        if not inside:
            report.error("avatar 路径跳出了专家目录：%s（运行时会判空）" % avatar)
        elif not os.path.isfile(abs_path):
            report.error("头像文件不存在：%s（这就是小图标变成文字的直接原因）" % avatar)
        else:
            size = os.path.getsize(abs_path)
            if size > AVATAR_HARD_LIMIT:
                report.error("头像 %.1f MB，超过运行时 5 MB 上限，会被判空"
                             % (size / 1024 / 1024.0))
            elif size > AVATAR_SOFT_LIMIT:
                report.warn("头像 %.0f KB，超过 500 KB 建议值" % (size / 1024.0))
            check_png(abs_path, report)
            if any(ord(c) > 127 for c in abs_path):
                report.warn("头像路径含非 ASCII 字符（中文用户名目录），若图标仍不显示，可先把专家装到纯英文路径下验证")
            report.info("头像：%s（%.0f KB）" % (rel, size / 1024.0))

    # 文档
    for f, level in (("README.md", "warn"), ("CHANGELOG.md", "warn"), ("LICENSE", "warn")):
        if not os.path.isfile(os.path.join(root, f)):
            (report.warn if level == "warn" else report.error)("建议补充 %s" % f)

    # 注册
    if name:
        check_marketplace(root, name, report)

    return emit(report, as_json)


def emit(report, as_json):
    if as_json:
        print(json.dumps({
            "errors": report.errors,
            "warnings": report.warnings,
            "infos": report.infos,
            "pass": not report.errors,
        }, ensure_ascii=False, indent=2))
        return 0 if not report.errors else 1

    print("=" * 60)
    for i in report.infos:
        print("  · %s" % i)
    if report.warnings:
        print("-" * 60)
        for w in report.warnings:
            print("  [警告] %s" % w)
    if report.errors:
        print("-" * 60)
        for e in report.errors:
            print("  [错误] %s" % e)
    print("=" * 60)
    if report.errors:
        print("结论：未通过（%d 个错误，%d 个警告）" % (len(report.errors), len(report.warnings)))
        return 1
    print("结论：通过（%d 个警告）" % len(report.warnings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
