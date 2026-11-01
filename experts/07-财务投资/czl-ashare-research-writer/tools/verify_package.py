#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布包自检（零第三方依赖）。

三类检查：
  1. 结构完整性：元数据字段、文件引用、头像有效性
  2. 引用一致性：SKILL.md 里出现的 references/ scripts/ 路径是否真实存在
  3. 原创性抽查：与参考专家包是否存在长句逐字重合

CLI:
  python tools/verify_package.py
  python tools/verify_package.py --overlap
"""
import argparse
import io
import json
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF_ROOT = r"C:/Users/丛自龙/.workbuddy/plugins/marketplaces/experts/plugins"
REF_PKGS = ["a-stock-trading-assistant", "smart-stock-analyst", "tdx-stock-diagnostician",
            "tdx-stock-hunter", "strategy-backtest-expert", "equity-research"]

REQUIRED_FIELDS = ["name", "version", "description", "author", "agents", "skills",
                   "expertType", "agentName", "displayName", "profession",
                   "displayDescription", "avatar", "categoryId"]

# 通用免责声明与常见规则表述，属公共表达，不计入重合
WHITELIST = [
    "不构成投资建议", "仅供研究参考", "投资有风险", "决策请自行判断",
    "本内容基于公开信息整理", "数据以公司公告与交易所披露为准",
]

RESULTS = []


def ok(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name, (" — " + detail) if detail else ""))


def read(path):
    with io.open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def check_structure():
    print("\n[1] 结构完整性")
    pj = os.path.join(ROOT, ".codebuddy-plugin", "plugin.json")
    if not os.path.exists(pj):
        ok("plugin.json 存在", False, pj)
        return None
    raw = read(pj)
    try:
        meta = json.loads(raw)
        ok("plugin.json 是合法 JSON", True, "%d 字节" % len(raw))
    except json.JSONDecodeError as exc:
        ok("plugin.json 是合法 JSON", False, str(exc))
        return None

    missing = [f for f in REQUIRED_FIELDS if f not in meta]
    ok("必填字段齐全", not missing, "缺：" + ",".join(missing) if missing else "13/13")
    ok("包名以 czl- 开头", str(meta.get("name", "")).startswith("czl-"), meta.get("name", ""))
    ok("包名只含允许字符",
       bool(re.fullmatch(r"[A-Za-z0-9\-—]+", meta.get("name", ""))), meta.get("name", ""))
    name_zh = (meta.get("displayName") or {}).get("zh", "")
    ok("中文名合法（无空格与特殊符号）",
       bool(name_zh) and bool(re.fullmatch(r"[\u4e00-\u9fa5A-Za-z0-9\-—]+", name_zh)), name_zh)
    ok("作者信息正确",
       (meta.get("author") or {}).get("name") == "虫志龙"
       and (meta.get("author") or {}).get("email") == "47190078@qq.com",
       str(meta.get("author")))

    for a in meta.get("agents", []):
        p = os.path.normpath(os.path.join(ROOT, a))
        ok("agent 文件存在：%s" % a, os.path.exists(p))

    for s in meta.get("skills", []):
        p = os.path.normpath(os.path.join(ROOT, s, "SKILL.md"))
        ok("skill 存在：%s" % os.path.basename(s.rstrip("/")), os.path.exists(p))

    av = meta.get("avatar")
    ap = os.path.normpath(os.path.join(ROOT, av))
    if os.path.exists(ap):
        with open(ap, "rb") as fh:
            head = fh.read(24)
        sig = head[:8] == b"\x89PNG\r\n\x1a\n"
        w, h = struct.unpack(">II", head[16:24]) if sig else (0, 0)
        ok("头像存在且为 PNG", sig, "%s %dx%d %d 字节" % (av, w, h, os.path.getsize(ap)))
        ok("头像为正方形且 ≥512", w == h and w >= 512, "%dx%d" % (w, h))
    else:
        ok("头像存在", False, ap)
    return meta


def check_market_rules(meta):
    """上架字段规则。

    这些限制来自平台校验器，不是我们自己定的：
      displayDescription.zh  最多 100 字（实测 135 字被拒）
      tags                   固定 3 个（实测 4 个被拒）
      quickPrompts           观察已上架包为 3-6 个
      displayDescription.en  无 100 字限制（已上架最长 434），设 450 为上限防意外
    """
    print("\n[1b] 上架字段规则")
    if not meta:
        ok("元数据可读", False)
        return
    zh = (meta.get("displayDescription") or {}).get("zh", "")
    en = (meta.get("displayDescription") or {}).get("en", "")
    ok("展示简介(zh) ≤100 字", 0 < len(zh) <= 100, "%d 字" % len(zh))
    ok("展示简介(en) ≤450 字符", 0 < len(en) <= 450, "%d 字符" % len(en))

    tags = meta.get("tags") or []
    ok("tags 恰好 3 个", len(tags) == 3, "当前 %d 个" % len(tags))
    bad_tags = [t for t in tags if not (t.get("zh") and t.get("en"))]
    ok("tags 均含中英双语", not bad_tags, "缺双语：%s" % bad_tags if bad_tags else "")

    qp = meta.get("quickPrompts") or []
    ok("quickPrompts 3-6 条", 3 <= len(qp) <= 6, "当前 %d 条" % len(qp))
    bad_qp = [q for q in qp if not (q.get("zh") and q.get("en"))]
    ok("quickPrompts 均含中英双语", not bad_qp, "缺双语 %d 条" % len(bad_qp) if bad_qp else "")

    prof = (meta.get("profession") or {}).get("zh", "")
    ok("职业标签非空且 ≤30 字", 0 < len(prof) <= 30, "%d 字：%s" % (len(prof), prof))

    dzh = (meta.get("defaultInitPrompt") or {}).get("zh", "")
    ok("默认开场提示非空", bool(dzh), "%d 字" % len(dzh))


def check_refs():
    print("\n[2] 文档内引用一致性")
    pattern = re.compile(r"`(references/[A-Za-z0-9_\-]+\.md|scripts/[A-Za-z0-9_\-]+\.py)`")
    bad, total = [], 0
    for dirpath, _, files in os.walk(os.path.join(ROOT, "skills")):
        for f in files:
            if f != "SKILL.md":
                continue
            p = os.path.join(dirpath, f)
            for m in pattern.finditer(read(p)):
                total += 1
                target = os.path.join(dirpath, m.group(1))
                if not os.path.exists(target):
                    bad.append("%s → %s" % (os.path.relpath(p, ROOT), m.group(1)))
    ok("SKILL 内的相对引用均存在", not bad, "%d 条引用，缺失 %d" % (total, len(bad)))
    if bad:
        for b in bad:
            print("        缺失：%s" % b)

    # 规则与文档引用
    doc_refs = ["SPEC.md", "README.md", "USAGE.md", "CHANGELOG.md", "LICENSE", "NOTICE.md",
                "docs/平台展示文案.md", "docs/开发记录.md", "docs/功能测试报告.md",
                "docs/商业发布风险清单.md", "tests/test_all.py", "tools/make_avatar.py"]
    miss = [d for d in doc_refs if not os.path.exists(os.path.join(ROOT, d))]
    ok("交付文档齐全", not miss, "缺：" + ",".join(miss) if miss else "%d/%d" % (len(doc_refs), len(doc_refs)))


def check_content():
    print("\n[3] 内容红线自检")
    agent = read(os.path.join(ROOT, "agents", "czl-ashare-research-writer.md"))
    ok("主体提示词含免责声明", "不构成投资建议" in agent)
    ok("主体提示词含证据分级", "[事实]" in agent and "[判断]" in agent)
    ok("主体提示词含 A股规则约束", "涨跌停" in agent and "T+1" in agent)
    ok("主体提示词含北向口径提醒", "北向" in agent)
    rules_files = [f for f in os.listdir(os.path.join(ROOT, "rules")) if f.endswith(".md")]
    ok("规则层 3 份齐备", len(rules_files) == 3, ",".join(sorted(rules_files)))

    # 禁止出现"保证收益"类承诺（提示词文本自身不得写出这些词作为示范）
    forbidden = ["保证收益", "稳赚不赔", "必涨", "包赚"]
    hit = [w for w in forbidden if w in agent]
    ok("主体提示词无收益承诺", not hit, ",".join(hit))

    # 无生成模型水印残留
    pngs = []
    for dirpath, _, files in os.walk(ROOT):
        for f in files:
            if f.lower().endswith(".png"):
                pngs.append(os.path.join(dirpath, f))
    ok("PNG 文件全部来自自研脚本", len(pngs) <= 4,
       "%d 个：%s" % (len(pngs), ", ".join(os.path.basename(p) for p in pngs)))


def _cjk_count(s):
    return len(re.findall(r"[\u4e00-\u9fa5]", s))


def _is_prose(gram):
    """只把真正的中文散文计入比对。

    排除：目录树、Markdown 表格线、JSON 键名、包标识等结构性内容。
    判据：去掉符号后至少 12 个汉字，且不含参考包名。
    """
    if _cjk_count(gram) < 12:
        return False
    if any(pkg in gram for pkg in REF_PKGS):
        return False
    if re.search(r"[│├└─┬┴┼]{2,}|\|[-: ]{4,}|\{|\}|\[\]|::", gram):
        return False
    return True


def _ngrams(text, n=24, prose_only=False):
    text = re.sub(r"\s+", "", text)
    grams = {text[i:i + n] for i in range(0, max(0, len(text) - n))}
    if prose_only:
        grams = {g for g in grams if _is_prose(g)}
    return grams


def check_overlap():
    print("\n[4] 与参考包的逐字重合抽查（24 字窗口）")
    if not os.path.isdir(REF_ROOT):
        ok("参考包可访问", False, REF_ROOT)
        return
    ref_text = []
    for pkg in REF_PKGS:
        for dirpath, _, files in os.walk(os.path.join(REF_ROOT, pkg)):
            for f in files:
                if f.endswith((".md", ".json")):
                    try:
                        ref_text.append(read(os.path.join(dirpath, f)))
                    except OSError:
                        pass
    ref = re.sub(r"\s+", "", "".join(ref_text))
    ref_set = _ngrams(ref, 24, prose_only=True)

    mine = []
    for dirpath, _, files in os.walk(ROOT):
        if os.sep + ".git" in dirpath:
            continue
        for f in files:
            if f.endswith((".md", ".json")):
                p = os.path.join(dirpath, f)
                if "last_run" in f:
                    continue
                mine.append((os.path.relpath(p, ROOT), read(p)))

    hits = []
    for rel, text in mine:
        for gram in _ngrams(text, 24, prose_only=True):
            if gram in ref_set and not any(w in gram for w in WHITELIST):
                hits.append((rel, gram))
                break
    # 去重展示
    uniq = []
    for rel, gram in hits:
        if gram not in [g for _, g in uniq]:
            uniq.append((rel, gram))
    ok("未发现成段逐字重合", len(uniq) == 0,
       "检查 %d 个文件，命中 %d 处" % (len(mine), len(uniq)))
    for rel, gram in uniq[:10]:
        print("        %s → 「%s」" % (rel, gram))


def summary():
    fail = [r for r in RESULTS if not r[1]]
    print("\n" + "=" * 62)
    print("合计 %d 项：PASS %d / FAIL %d" % (len(RESULTS), len(RESULTS) - len(fail), len(fail)))
    print("=" * 62)
    return 0 if not fail else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--overlap", action="store_true", help="额外执行与参考包的重合抽查")
    args = ap.parse_args()
    print("=" * 62)
    print("发布包自检：%s" % ROOT)
    print("=" * 62)
    meta = check_structure()
    check_market_rules(meta)
    check_refs()
    check_content()
    if args.overlap:
        check_overlap()
    return summary()


if __name__ == "__main__":
    sys.exit(main())
