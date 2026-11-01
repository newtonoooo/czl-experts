#!/usr/bin/env python3
"""teardown_toolkit - dependency-free helper CLI for the rival teardown playbook.

Subcommands
    parse     <raw input>                     -> normalised input facts (JSON)
    ledger    --asin A --out FILE             -> evidence ledger CSV skeleton
    score     --positioning N --message N ... -> weighted strength score
    scaffold  --asin A --date D --out FILE    -> report skeleton (15 sections)
    check     <report.md>                     -> structure QA, exit 1 on failure
    selftest                                  -> built-in regression tests

Standard library only. Python 3.8+.
"""

import argparse
import csv
import json
import os
import re
import sys

VERSION = "1.0.0"

WEIGHTS = {
    "positioning": 0.20,
    "message": 0.20,
    "visual": 0.20,
    "voice": 0.25,
    "arena": 0.15,
}

LAYER_LABELS = {
    "positioning": "L1 需求定位",
    "message": "L2 表达",
    "visual": "L3 视觉",
    "voice": "L4 口碑",
    "arena": "L5 格局",
}

SITES = {
    "amazon.com": "US",
    "amazon.co.uk": "UK",
    "amazon.de": "DE",
    "amazon.fr": "FR",
    "amazon.it": "IT",
    "amazon.es": "ES",
    "amazon.ca": "CA",
    "amazon.co.jp": "JP",
    "amazon.in": "IN",
    "amazon.com.mx": "MX",
    "amazon.com.au": "AU",
    "amazon.ae": "AE",
    "amazon.sa": "SA",
    "amazon.sg": "SG",
    "amazon.nl": "NL",
    "amazon.se": "SE",
    "amazon.pl": "PL",
    "amazon.com.br": "BR",
    "amazon.com.tr": "TR",
    "amazon.eg": "EG",
}

LEDGER_FIELDS = [
    "标题", "五点1", "五点2", "五点3", "五点4", "五点5",
    "A+首屏", "主图", "副图1", "副图2", "副图3", "副图4", "副图5", "副图6",
    "视频", "价格", "评分", "评论数", "类目排名", "变体数", "优惠形式",
    "QA", "评论样本",
]

REPORT_SECTIONS = [
    (0, "一页速览"),
    (1, "分析概览"),
    (2, "竞品基本信息"),
    (3, "证据台账摘要"),
    (4, "L1 需求定位层"),
    (5, "L2 表达层"),
    (6, "L3 视觉层"),
    (7, "L4 口碑层"),
    (8, "L5 竞争格局层"),
    (9, "强度评分卡"),
    (10, "差异化打法"),
    (11, "行动清单"),
    (12, "数据缺口"),
    (13, "本报告不能回答什么"),
    (14, "合规红线"),
    (15, "证据索引"),
]

ABSOLUTE_CLAIMS = ["最好", "最低价", "第一名", "唯一", "永久", "顶级", "100%有效", "绝对"]
PLACEHOLDER_MARKERS = ["<!-- FILL", "[TODO", "{{"]


# --------------------------------------------------------------------------
# parse
# --------------------------------------------------------------------------

ASIN_PATH_RE = re.compile(r"/(?:dp|gp/product|gp/aw/d|product|exec/obidos/asin)/([A-Za-z0-9]{10})")
ASIN_PARAM_RE = re.compile(r"[?&](?:asin|ASIN)=([A-Za-z0-9]{10})")
ASIN_LOOSE_RE = re.compile(r"\b(B0[A-Za-z0-9]{8})\b")
ASIN_BARE_RE = re.compile(r"^[A-Za-z0-9]{10}$")
SHORT_HOSTS = ("amzn.to", "a.co", "amzn.eu", "bit.ly")


def detect_site(text):
    low = text.lower()
    best = None
    for host, code in SITES.items():
        if host in low:
            if best is None or len(host) > len(best[0]):
                best = (host, code)
    return best


def cmd_parse(raw):
    text = (raw or "").strip()
    facts = {
        "input_type": "unknown",
        "asin": None,
        "site": None,
        "domain": None,
        "url": None,
        "needs_expand": False,
        "missing_fields": [],
        "notes": [],
    }

    if not text:
        facts["input_type"] = "empty"
        facts["missing_fields"] = ["竞品 ASIN 或链接", "我方产品信息", "本次分析目标"]
        return facts

    site = detect_site(text)
    if site:
        facts["domain"], facts["site"] = site

    m = ASIN_PATH_RE.search(text) or ASIN_PARAM_RE.search(text)
    asin = m.group(1) if m else None

    if not asin:
        m2 = ASIN_LOOSE_RE.search(text)
        if m2:
            asin = m2.group(1)

    lowered = text.lower()
    is_short = any(h in lowered for h in SHORT_HOSTS)

    if asin:
        facts["asin"] = asin.upper()
        facts["input_type"] = "url" if "http" in lowered else "asin"
        if facts["domain"]:
            facts["url"] = f"https://www.{facts['domain']}/dp/{facts['asin'].upper()}"
        else:
            facts["site"] = "US"
            facts["domain"] = "amazon.com"
            facts["url"] = f"https://www.amazon.com/dp/{facts['asin'].upper()}"
            facts["notes"].append("未识别站点，按 US 处理；如非美国站请补充域名")
    elif is_short:
        facts["input_type"] = "short-link"
        facts["needs_expand"] = True
        facts["notes"].append("短链需先展开再提取 ASIN")
        facts["missing_fields"].append("展开后的商品链接")
    elif "http" in lowered:
        facts["input_type"] = "url"
        facts["missing_fields"].append("可从链接中提取的 ASIN")
        facts["notes"].append("链接中未找到 ASIN，请确认是否为商品详情页")
    elif ASIN_BARE_RE.match(text.upper()):
        facts["asin"] = text.upper()
        facts["input_type"] = "asin"
        facts["site"] = "US"
        facts["domain"] = "amazon.com"
        facts["url"] = f"https://www.amazon.com/dp/{text.upper()}"
        facts["notes"].append("输入疑似 10 位 ASIN，已按 US 站点构造链接，请确认")
    else:
        facts["input_type"] = "text"
        facts["notes"].append("按用户供给文本处理：需要 listing 文案 / 评论 / QA 原文")

    if facts["input_type"] in ("text", "short-link", "url"):
        facts["missing_fields"].extend(["评分与评论数", "价格与优惠形式", "主图与副图内容描述"])

    seen = set()
    facts["missing_fields"] = [x for x in facts["missing_fields"] if not (x in seen or seen.add(x))]
    return facts


# --------------------------------------------------------------------------
# ledger
# --------------------------------------------------------------------------

def cmd_ledger(asin, out_path):
    asin = (asin or "").upper()
    rows = []
    for field in LEDGER_FIELDS:
        rows.append([field, "未获取", "待采集", "U", "", "初始占位，采集后覆盖"])
    header = ["字段", "值", "来源", "等级", "采集时间", "备注"]
    with open(out_path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)
    return {"file": os.path.abspath(out_path), "rows": len(rows), "asin": asin}


# --------------------------------------------------------------------------
# score
# --------------------------------------------------------------------------

def tier_for(total):
    if total >= 80:
        return "强敌", "换战场或侧翼：正面拼资源不划算，找他的结构性弱点切入"
    if total >= 60:
        return "可战", "单点突破：选一层做到明显超过他，其余层跟住不落后"
    return "弱敌", "正面压：在表达与视觉上直接对比，抢他的流量位"


def cmd_score(positioning, message, visual, voice, arena):
    scores = {
        "positioning": positioning,
        "message": message,
        "visual": visual,
        "voice": voice,
        "arena": arena,
    }
    for key, val in scores.items():
        if not isinstance(val, int) or val < 0 or val > 100:
            raise ValueError(f"{key} 必须是 0-100 的整数，收到 {val!r}")
    total = sum(scores[k] * WEIGHTS[k] for k in WEIGHTS)
    total = round(total, 1)
    tier, play = tier_for(total)
    weakest = min(scores, key=lambda k: scores[k])
    strongest = max(scores, key=lambda k: scores[k])
    return {
        "scores": scores,
        "weights": WEIGHTS,
        "total": total,
        "tier": tier,
        "play": play,
        "strongest_layer": LAYER_LABELS[strongest],
        "weakest_layer": LAYER_LABELS[weakest],
        "spread": scores[strongest] - scores[weakest],
    }


# --------------------------------------------------------------------------
# scaffold
# --------------------------------------------------------------------------

def build_report_skeleton(asin, date, product_name):
    asin = (asin or "").upper() or "TEXT-0000"
    product_name = product_name or "待填产品简称"
    fill = "<!-- FILL -->"

    parts = []
    parts.append(f"# 竞品拆解报告：{product_name}\n")
    parts.append("## 0 一页速览\n")
    parts.append(f"- 竞品是谁：{fill}")
    parts.append(f"- 最强的一处：{fill}")
    parts.append(f"- 最弱的一处：{fill}")
    parts.append(f"- 主攻方向：{fill}")
    parts.append(f"- 下一步验证：{fill}\n")

    parts.append("## 1 分析概览\n")
    parts.append("| 项 | 内容 |")
    parts.append("|---|---|")
    parts.append(f"| 分析对象 | {asin} |")
    parts.append(f"| 站点 | {fill} |")
    parts.append(f"| 分析日期 | {date} |")
    parts.append(f"| 数据通道 | {fill} |")
    parts.append(f"| 采集覆盖 | {fill} |")
    parts.append("| 分析者 | 拆敌（czl-rival-teardown-pro v1.0.0） |\n")

    parts.append("## 2 竞品基本信息\n")
    parts.append("| 项 | 值 | 采集时间 |")
    parts.append("|---|---|---|")
    for field in ("标题", "价格", "评分 / 评论数", "变体数", "类目 / 排名", "优惠形式"):
        parts.append(f"| {field} | {fill} | {fill} |")
    parts.append("")

    parts.append("## 3 证据台账摘要\n")
    parts.append("| 等级 | 条数 | 覆盖层 |")
    parts.append("|---|---|---|")
    for grade in ("E1 页面原文", "E2 平台可核", "E3 外部推断", "U 待验证"):
        parts.append(f"| {grade} | {fill} | {fill} |")
    parts.append("")
    parts.append(f"台账文件：`证据台账-{asin}-{date}.csv`\n")

    layer_titles = [
        ("4", "L1 需求定位层", "标题主语 / 变体结构 / 首图人物 / QA 提问方式 / 五点第一条"),
        ("5", "L2 表达层", "叙事骨架 / 五点排序 / 关键词位置 / 语言指纹"),
        ("6", "L3 视觉层", "主图构图 / 副图序列 / A+ 分段 / 视频前 3 秒"),
        ("7", "L4 口碑层", "好评聚类 / 差评分类 / QA 心理防线"),
        ("8", "L5 竞争格局层", "价格位置 / 变体位置 / 流量位置 / 促销位置"),
    ]
    for num, title, hint in layer_titles:
        parts.append(f"## {num} {title}\n")
        if num == "7":
            parts.append(f"**样本量**：{fill}（写明实际条数，如「42 条（最新 20 + 最有帮助 12 + 1-3 星 10）」）")
            parts.append("**抽样方式**：非随机定向抽样")
            parts.append("**样本局限**：不代表全量评论分布，比例仅用于定性判断\n")
        parts.append("### 做了什么选择")
        parts.append(f"{fill}（观察点：{hint}）\n")
        parts.append("### 服务谁")
        parts.append(f"{fill}\n")
        parts.append("### 代价与机会")
        parts.append(f"{fill}\n")
        parts.append(f"本层结论：{fill} 置信度：{fill}\n")

    parts.append("## 9 强度评分卡\n")
    parts.append("| 层 | 权重 | 得分（0-100） | 加权 |")
    parts.append("|---|---|---|---|")
    for key in ("positioning", "message", "visual", "voice", "arena"):
        parts.append(f"| {LAYER_LABELS[key]} | {int(WEIGHTS[key] * 100)}% | {fill} | {fill} |")
    parts.append(f"| **加权总分** | 100% | — | {fill} |\n")
    parts.append(f"**强度档位**：{fill}")
    parts.append(f"**建议打法**：{fill}\n")
    parts.append(f"**我方胜率评估**：{fill}\n")

    parts.append("## 10 差异化打法\n")
    parts.append("### 候选切口\n")
    parts.append("| # | 切口 | 模式 | 可验证性(1-5) | 资源匹配(1-5) | 结论 |")
    parts.append("|---|---|---|---|---|---|")
    for tag in ("A", "B", "C"):
        parts.append(f"| {tag} | {fill} | {fill} | {fill} | {fill} | {fill} |")
    parts.append("")
    parts.append("### 主攻切口")
    parts.append(f"{fill}\n")
    parts.append("**为什么成立**：")
    parts.append(f"1. {fill}")
    parts.append(f"2. {fill}")
    parts.append(f"3. {fill}\n")
    parts.append(f"**为什么对手不做**：{fill}\n")
    parts.append(f"**淘汰理由**：{fill}\n")

    parts.append("## 11 行动清单\n")
    parts.append("| # | 动作 | 类型 | 负责角色 | 工作量 | 验证指标 | 验证周期 |")
    parts.append("|---|---|---|---|---|---|---|")
    for i in range(1, 6):
        parts.append(f"| {i} | {fill} | {fill} | {fill} | {fill} | {fill} | {fill} |")
    parts.append("")

    parts.append("## 12 数据缺口\n")
    parts.append("| 缺口项 | 影响哪一层 | 对结论的影响 | 补充方式 |")
    parts.append("|---|---|---|---|")
    parts.append(f"| {fill} | {fill} | {fill} | {fill} |\n")

    parts.append("## 13 本报告不能回答什么\n")
    for i in range(1, 4):
        parts.append(f"{i}. {fill}")
    parts.append("")

    parts.append("## 14 合规红线\n")
    parts.append(f"{fill}\n")

    parts.append("## 15 证据索引\n")
    parts.append("| 编号 | 台账行 | 说明 |")
    parts.append("|---|---|---|")
    parts.append(f"| {fill} | {fill} | {fill} |")
    parts.append("")
    return "\n".join(parts)


def cmd_scaffold(asin, date, out_path, product_name):
    content = build_report_skeleton(asin, date, product_name)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return {"file": os.path.abspath(out_path), "chars": len(content)}


# --------------------------------------------------------------------------
# check
# --------------------------------------------------------------------------

def read_text(path):
    with open(path, "r", encoding="utf-8-sig") as fh:
        return fh.read()


def section_body(text, num, keyword):
    pattern = re.compile(rf"^##\s*{num}\s+[^\n]*{re.escape(keyword)}[^\n]*$", re.MULTILINE)
    m = pattern.search(text)
    if not m:
        return None
    start = m.end()
    nxt = re.compile(r"^##\s*\d+", re.MULTILINE).search(text, start)
    return text[start:nxt.start()] if nxt else text[start:]


def run_checks(text):
    results = []

    def add(name, ok, detail=""):
        results.append({"check": name, "ok": bool(ok), "detail": detail})

    missing = []
    for num, keyword in REPORT_SECTIONS:
        if section_body(text, num, keyword) is None:
            missing.append(f"{num} {keyword}")
    add("章节完整性", not missing, "缺失: " + "、".join(missing) if missing else f"{len(REPORT_SECTIONS)} 节齐全")

    leftovers = [m for m in PLACEHOLDER_MARKERS if m in text]
    add("无占位符残留", not leftovers, "残留: " + "、".join(leftovers) if leftovers else "无")

    evidence_ids = set(re.findall(r"E[123]-\d{2}", text))
    add("结论带证据编号", len(evidence_ids) >= 3, f"识别到 {len(evidence_ids)} 个编号")

    voice = section_body(text, 7, "L4 口碑层") or ""
    sample_ok = re.search(r"样本量\*{0,2}\s*[：:]\s*(?!<!--)\D*\d+", voice) is not None
    add("口碑层样本量披露", sample_ok, "未在 L4 找到「样本量：N 条」" if not sample_ok else "已披露")

    gap = section_body(text, 12, "数据缺口") or ""
    gap_rows = [ln for ln in gap.splitlines() if ln.strip().startswith("|") and "---" not in ln]
    gap_ok = len(gap_rows) >= 2 and "<!-- FILL" not in gap
    add("数据缺口表", gap_ok, "缺口表为空或未填" if not gap_ok else f"{len(gap_rows) - 1} 行缺口")

    compliance = section_body(text, 14, "合规红线") or ""
    comp_ok = bool(compliance.strip()) and "<!-- FILL" not in compliance
    add("合规红线小节", comp_ok, "缺失或未填" if not comp_ok else "已填写")

    # 合规小节本身会引用违禁词，扫描绝对化用语时排除该节
    scan_text = text.replace(compliance, "") if compliance else text
    hits = [w for w in ABSOLUTE_CLAIMS if w in scan_text]
    add("无绝对化用语", not hits, "命中: " + "、".join(hits) if hits else "未命中")

    return results


def cmd_check(path):
    text = read_text(path)
    results = run_checks(text)
    return {"file": os.path.abspath(path), "results": results,
            "passed": all(r["ok"] for r in results)}


# --------------------------------------------------------------------------
# selftest
# --------------------------------------------------------------------------

def selftest():
    failures = []

    def expect(cond, label):
        if not cond:
            failures.append(label)

    f1 = cmd_parse("https://www.amazon.com/dp/B08N5WRWNW?th=1")
    expect(f1["asin"] == "B08N5WRWNW", "URL 提取 ASIN")
    expect(f1["site"] == "US", "URL 识别站点")

    f2 = cmd_parse("B08N5WRWNW")
    expect(f2["input_type"] == "asin", "裸 ASIN 识别")

    f3 = cmd_parse("看看这个 https://www.amazon.co.uk/gp/product/B07XJ8C8F5 怎么样")
    expect(f3["asin"] == "B07XJ8C8F5" and f3["site"] == "UK", "英站 gp/product 提取")

    f4 = cmd_parse("https://amzn.to/3xyzabc")
    expect(f4["needs_expand"] is True, "短链标记需展开")

    f5 = cmd_parse("标题：可折叠收纳箱 五点：... 评论：很好用")
    expect(f5["input_type"] == "text" and f5["asin"] is None, "纯文本识别")

    f6 = cmd_parse("")
    expect(f6["input_type"] == "empty" and f6["missing_fields"], "空输入")

    s = cmd_score(78, 85, 90, 72, 65)
    expect(abs(s["total"] - 78.3) < 0.05, f"加权总分应为 78.3，实得 {s['total']}")
    expect(s["tier"] == "可战", "档位判定")
    expect(s["weakest_layer"] == "L5 格局", "最弱层识别")

    s2 = cmd_score(95, 95, 95, 95, 95)
    expect(s2["total"] == 95.0 and s2["tier"] == "强敌", "满分边界")

    try:
        cmd_score(101, 50, 50, 50, 50)
        failures.append("越界分数应报错")
    except ValueError:
        pass

    import tempfile
    tmpdir = tempfile.mkdtemp(prefix="teardown-selftest-")
    report_path = os.path.join(tmpdir, "report.md")
    cmd_scaffold("B08N5WRWNW", "2026-10-28", report_path, "测试产品")
    skel = read_text(report_path)
    for num, keyword in REPORT_SECTIONS:
        expect(f"## {num} {keyword}" in skel, f"骨架缺少章节 {num} {keyword}")

    chk = cmd_check(report_path)
    expect(chk["passed"] is False, "骨架应质检失败")
    failed_names = {r["check"] for r in chk["results"] if not r["ok"]}
    expect("章节完整性" not in failed_names, "骨架章节应完整")
    expect("无占位符残留" in failed_names, "骨架应检出占位符")

    filled = skel.replace("<!-- FILL -->", "示例内容")
    for idx in range(1, 6):
        filled = filled.replace(
            "本层结论：示例内容 置信度：示例内容",
            f"本层结论：示例结论 [E1-0{idx}] 置信度：中",
            1,
        )
    filled = filled.replace("**样本量**：示例内容", "**样本量**：42 条（最新 20 + 最有帮助 12 + 1-3 星 10）")
    filled = filled.replace("| 示例内容 | 示例内容 | 示例内容 | 示例内容 |",
                            "| 无评论原文 | L4 口碑 | 口碑层降级为推断 | 用户补 30 条评论 |")
    filled = filled.replace("## 14 合规红线\n\n示例内容",
                            "## 14 合规红线\n\n本报告未发现明显合规风险点（仅基于页面可见内容判断）")
    filled_path = os.path.join(tmpdir, "filled.md")
    with open(filled_path, "w", encoding="utf-8") as fh:
        fh.write(filled)
    chk2 = cmd_check(filled_path)
    expect(chk2["passed"] is True,
           "填充后应质检通过，未通过项: " + str([r["check"] for r in chk2["results"] if not r["ok"]]))

    ledger_path = os.path.join(tmpdir, "ledger.csv")
    info = cmd_ledger("B08N5WRWNW", ledger_path)
    expect(info["rows"] == len(LEDGER_FIELDS), "台账行数")
    with open(ledger_path, encoding="utf-8-sig") as fh:
        rows = list(csv.reader(fh))
    expect(rows[0][0] == "字段" and len(rows) == len(LEDGER_FIELDS) + 1, "台账表头")

    if failures:
        print("SELFTEST FAILED")
        for f in failures:
            print("  -", f)
        return False
    print(f"SELFTEST PASSED  ({len(failures)} failures)  toolkit v{VERSION}")
    print(f"  parse: 6 cases | score: 4 cases | scaffold+check: 2 cases | ledger: 1 case")
    return True


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(prog="teardown_toolkit", description="竞品拆解工具箱")
    parser.add_argument("--version", action="version", version=f"teardown_toolkit {VERSION}")
    sub = parser.add_subparsers(dest="command")

    p_parse = sub.add_parser("parse", help="解析用户输入，输出规范化事实")
    p_parse.add_argument("raw", nargs="*", help="原始输入文本")

    p_ledger = sub.add_parser("ledger", help="生成证据台账 CSV 骨架")
    p_ledger.add_argument("--asin", required=True)
    p_ledger.add_argument("--out", required=True)

    p_score = sub.add_parser("score", help="计算五层加权强度分")
    for key in WEIGHTS:
        p_score.add_argument(f"--{key}", type=int, required=True)

    p_scaffold = sub.add_parser("scaffold", help="生成主报告骨架")
    p_scaffold.add_argument("--asin", required=True)
    p_scaffold.add_argument("--date", required=True)
    p_scaffold.add_argument("--out", required=True)
    p_scaffold.add_argument("--name", default=None, help="产品简称")

    p_check = sub.add_parser("check", help="报告结构质检")
    p_check.add_argument("path")

    sub.add_parser("selftest", help="运行内置回归测试")

    args = parser.parse_args(argv)

    if args.command == "parse":
        print(json.dumps(cmd_parse(" ".join(args.raw)), ensure_ascii=False, indent=2))
        return 0

    if args.command == "ledger":
        info = cmd_ledger(args.asin, args.out)
        print(f"台账已生成：{info['file']}（{info['rows']} 个字段，全部标记为未获取/U）")
        return 0

    if args.command == "score":
        try:
            res = cmd_score(args.positioning, args.message, args.visual, args.voice, args.arena)
        except ValueError as exc:
            print(f"参数错误：{exc}", file=sys.stderr)
            return 2
        print("| 层 | 权重 | 得分 | 加权 |")
        print("|---|---|---|---|")
        for key, label in LAYER_LABELS.items():
            print(f"| {label} | {int(WEIGHTS[key]*100)}% | {res['scores'][key]} | {round(res['scores'][key]*WEIGHTS[key], 1)} |")
        print(f"| **加权总分** | 100% | — | **{res['total']}** |")
        print(f"\n强度档位：{res['tier']}")
        print(f"建议打法：{res['play']}")
        print(f"最强层：{res['strongest_layer']}｜最弱层：{res['weakest_layer']}｜层间极差：{res['spread']}")
        return 0

    if args.command == "scaffold":
        info = cmd_scaffold(args.asin, args.date, args.out, args.name)
        print(f"骨架已生成：{info['file']}（{info['chars']} 字符，待填项用 <!-- FILL --> 标记）")
        return 0

    if args.command == "check":
        res = cmd_check(args.path)
        for r in res["results"]:
            mark = "PASS" if r["ok"] else "FAIL"
            print(f"[{mark}] {r['check']}：{r['detail']}")
        print(f"\n结论：{'通过' if res['passed'] else '未通过，请修复 FAIL 项'}")
        return 0 if res["passed"] else 1

    if args.command == "selftest":
        return 0 if selftest() else 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
