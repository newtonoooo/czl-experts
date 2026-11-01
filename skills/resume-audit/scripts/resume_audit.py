#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""resume_audit.py - mechanical screening check for a resume.

Computes the objectively countable half of the three-gate audit:
  Gate A  machine parsing  (contact, headings, date formats, layout hazards)
  Gate B  six-second scan  (bullet density, bullet length, quantification)
  Gate C  interview follow-up proxy (measurable outcomes, weak phrasing, duplicates)

The judgemental half (is this achievement impressive, does the story hold up)
is NOT computed here. Output says so explicitly.

Standard library only. Usage:
    python resume_audit.py RESUME.md [--jd JD.md] [--json] [--out report.md]
"""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

# ---------------------------------------------------------------- lexicons

SECTION_ALIASES = {
    "contact": ["联系方式", "个人信息", "个人资料", "基本信息", "contact", "profile"],
    "summary": ["个人简介", "自我评价", "个人总结", "求职意向", "简介", "summary", "objective", "about me"],
    "experience": ["工作经历", "工作经验", "职业经历", "实习经历", "工作履历", "experience", "employment"],
    "projects": ["项目经历", "项目经验", "代表项目", "projects"],
    "education": ["教育背景", "教育经历", "学历背景", "学历", "education"],
    "skills": ["专业技能", "技能证书", "技能", "技术栈", "skills", "certifications"],
    "awards": ["获奖经历", "荣誉奖项", "荣誉", "证书", "awards", "honors"],
}

REQUIRED_SECTIONS = ["experience", "education", "skills"]

STRONG_VERBS_ZH = [
    "主导", "牵头", "搭建", "建设", "设计", "重构", "迁移", "上线", "交付", "落地",
    "推进", "优化", "提效", "降本", "定位", "排查", "修复", "复盘", "沉淀", "培养",
    "带教", "谈判", "引入", "整合", "拆解", "制定", "打通", "覆盖", "支撑", "验证",
    "建模", "分析", "自动化", "集成", "部署", "监控", "治理", "盘点", "梳理", "建成",
    "推动", "统筹", "复用", "压缩", "拆分", "上线了", "改造", "攻坚", "接手", "救火",
]

WEAK_OPENERS = [
    "负责", "参与", "协助", "配合", "支持", "跟进", "从事", "主要", "完成了", "进行了",
    "帮助", "参加", "对接", "沟通", "学习", "了解",
]

STRONG_VERBS_EN = [
    "led", "built", "designed", "shipped", "launched", "refactored", "reduced",
    "increased", "automated", "migrated", "negotiated", "mentored", "owned", "drove",
    "delivered", "scaled", "cut", "improved", "established", "streamlined", "rebuilt",
    "consolidated", "introduced", "diagnosed", "audited",
]

WEAK_OPENERS_EN = [
    "responsible for", "worked on", "helped", "assisted", "participated", "involved in",
    "supported", "handled", "in charge of", "duties included",
]

EMPTY_PHRASES = [
    "精通", "深度", "显著", "大幅", "有效", "良好", "较强", "优秀", "丰富", "全面",
    "较好", "一定程度", "各方面", "相关工作", "各类", "若干", "具备较强的",
    "注重", "意识强", "团队精神", "抗压能力", "责任心强", "熟练使用", "很好地",
]

OVERCLAIM = ["精通", "专家级", "业内领先", "行业第一", "顶级"]

DATE_PATTERNS = [
    ("YYYY.MM", re.compile(r"(?:19|20)\d{2}\.\d{1,2}")),
    ("YYYY/MM", re.compile(r"(?:19|20)\d{2}/\d{1,2}")),
    ("YYYY-MM", re.compile(r"(?:19|20)\d{2}-\d{1,2}")),
    ("YYYY年M月", re.compile(r"(?:19|20)\d{2}\s*年\s*\d{1,2}\s*月")),
    ("Mon YYYY", re.compile(r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(?:19|20)\d{2}", re.I)),
]

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d(?:[\s\-]?\d){8}(?!\d)")
URL_RE = re.compile(r"(?:https?://|www\.)[^\s)）]+")
MONTH_RANGE_RE = re.compile(r"(?:至今|现在|present|now|current)", re.I)


# ---------------------------------------------------------------- helpers

def read_text(path):
    data = Path(path).read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def strip_markup(s):
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", s)          # images
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)        # links
    s = re.sub(r"(\*\*|__|\*|_|`)", "", s)                # emphasis
    s = re.sub(r"^\s{0,3}#{1,6}\s*", "", s)               # heading marks
    return s.strip()


def char_len(text):
    """Count characters, ignoring whitespace."""
    return len(re.sub(r"\s", "", text))


def section_of(line):
    plain = strip_markup(line)
    plain = re.sub(r"[:：|]", "", plain).strip()
    if char_len(plain) > 16:
        return None
    low = plain.lower()
    for key, aliases in SECTION_ALIASES.items():
        for a in aliases:
            if a in low:
                return key
    return None


BULLET_RE = re.compile(r"^\s{0,3}(?:[-*+•·●▪◦]|\d+[.、)])\s+")


def is_bullet(line):
    return bool(BULLET_RE.match(line))


def bullet_body(line):
    return strip_markup(BULLET_RE.sub("", line, count=1)).strip()


def has_number(s):
    return bool(re.search(r"\d", unicodedata.normalize("NFKC", s)))


OUTCOME_RE = re.compile(
    r"(\d+(?:\.\d+)?\s*(?:%|％|倍|万|亿|元|块|人|家|个|条|次|天|小时|分钟|秒|台|套)"
    r"|从\s*\d+.*?(?:到|至|→)\s*\d+"
    r"|\d+\s*/\s*\d+"
    r"|\d+(?:\.\d+)?\s*(?:倍|个百分点))"
)

MONTH_UNIT_RE = re.compile(r"\d+\s*(?:年|个月|月)")


def starts_with_strong(body):
    b = body.strip()
    low = b.lower()
    for w in WEAK_OPENERS_EN + STRONG_VERBS_EN:
        pass
    for w in WEAK_OPENERS_EN:
        if low.startswith(w):
            return False
    for w in STRONG_VERBS_EN:
        if low.startswith(w + " ") or low.startswith(w):
            if low.startswith(w):
                # require word boundary for english
                idx = len(w)
                if idx < len(low) and low[idx].isalpha():
                    continue
                return True
    for w in WEAK_OPENERS:
        if b.startswith(w):
            return False
    for w in STRONG_VERBS_ZH:
        if b.startswith(w):
            return True
    # 中文动词开头但不在词表内：退一步看前两个字是否是动词性开头
    return False


def count_hits(text, words):
    hits = {}
    low = text.lower()
    for w in words:
        if w.isascii():
            n = len(re.findall(r"\b" + re.escape(w) + r"\b", low))
        else:
            n = text.count(w)
        if n:
            hits[w] = n
    return hits


# ---------------------------------------------------------------- analysis

def analyze(text, jd_text=None):
    raw_lines = text.splitlines()
    text = unicodedata.normalize("NFKC", text)
    lines = text.splitlines()

    bullets = []          # (section, body)
    section = "header"
    sections_found = []
    summary_text = []
    hazard_lines = {"table": 0, "image": 0, "tab": 0, "multispace": 0, "pagemark": 0, "longline": 0}

    for idx, raw in enumerate(lines):
        if not raw.strip():
            continue
        orig = raw_lines[idx] if idx < len(raw_lines) else raw
        sec = section_of(raw)
        if sec:
            section = sec
            if sec not in sections_found:
                sections_found.append(sec)
            continue
        if "|" in orig and orig.count("|") >= 2:
            hazard_lines["table"] += 1
        if "![" in orig:
            hazard_lines["image"] += 1
        if "\t" in orig:
            hazard_lines["tab"] += 1
        if re.search(r"\s{4,}", orig) and not is_bullet(orig):
            hazard_lines["multispace"] += 1
        if re.search(r"(第\s*\d+\s*页|page\s*\d+\s*(of|/)|页眉|页脚)", orig, re.I):
            hazard_lines["pagemark"] += 1
        if char_len(orig) > 150:
            hazard_lines["longline"] += 1

        if is_bullet(raw):
            bullets.append((section, bullet_body(raw)))
        elif section == "summary":
            summary_text.append(strip_markup(raw))

    exp_bullets = [b for s, b in bullets if s in ("experience", "projects")]
    focus = exp_bullets if exp_bullets else [b for _, b in bullets]
    focus = [b for b in focus if char_len(b) > 0]

    # contact
    emails = EMAIL_RE.findall(text)
    phones = sorted({re.sub(r"\D", "", p) for p in PHONE_RE.findall(text)})
    has_link = bool(URL_RE.search(text))

    # dates
    styles = {}
    for label, pat in DATE_PATTERNS:
        n = len(pat.findall(text))
        if n:
            styles[label] = n
    date_style_count = len(styles)
    has_present = bool(MONTH_RANGE_RE.search(text))

    # bullet metrics
    n_focus = len(focus)
    lens = [char_len(b) for b in focus]
    avg_len = round(sum(lens) / n_focus, 1) if n_focus else 0
    quant = sum(1 for b in focus if has_number(b))
    outcome = sum(1 for b in focus if OUTCOME_RE.search(b))
    strong = sum(1 for b in focus if starts_with_strong(b))
    weak_open = sum(1 for b in focus if any(b.startswith(w) for w in WEAK_OPENERS))
    empty_hits = count_hits(" ".join(focus), EMPTY_PHRASES)
    empty_total = sum(empty_hits.values())
    overclaim = count_hits(" ".join(focus), OVERCLAIM)

    # duplicates
    seen = {}
    dup = 0
    for b in focus:
        key = b[:6]
        if len(key) < 4:
            continue
        if key in seen:
            dup += 1
        seen[key] = True

    summary_len = char_len(" ".join(summary_text))

    def ratio(a, b):
        return round(a / b, 3) if b else 0.0

    metrics = {
        "char_count": char_len(text),
        "line_count": len([l for l in lines if l.strip()]),
        "bullet_count": n_focus,
        "bullet_avg_len": avg_len,
        "bullet_short_count": sum(1 for x in lens if x < 20),
        "bullet_long_count": sum(1 for x in lens if x > 100),
        "quantified_bullets": quant,
        "quantified_ratio": ratio(quant, n_focus),
        "outcome_bullets": outcome,
        "outcome_ratio": ratio(outcome, n_focus),
        "strong_verb_bullets": strong,
        "strong_verb_ratio": ratio(strong, n_focus),
        "weak_opener_bullets": weak_open,
        "weak_opener_ratio": ratio(weak_open, n_focus),
        "empty_phrase_hits": empty_total,
        "empty_phrase_detail": empty_hits,
        "overclaim_hits": sum(overclaim.values()),
        "duplicate_openings": dup,
        "summary_chars": summary_len,
        "date_styles": styles,
        "date_style_count": date_style_count,
        "has_current_marker": has_present,
        "email_found": len(emails),
        "phone_found": len(phones),
        "has_link": has_link,
        "sections_found": sections_found,
        "hazard_lines": hazard_lines,
    }

    # ------------------------------------------------------------ scoring
    findings = []

    def add(sev, gate, title, detail, action):
        findings.append({"severity": sev, "gate": gate, "title": title,
                         "detail": detail, "action": action})

    # Gate A
    a = 30
    if not emails:
        a -= 7
        add("BLOCKER", "A", "没有可识别的邮箱",
            "正则扫描全文未找到邮箱地址格式。招聘系统提取不到联系方式，简历会被直接丢弃。",
            "在页首写一行纯文本邮箱，例如 name@example.com，不要放在图片或表格里。")
    if not phones:
        a -= 5
        add("MAJOR", "A", "没有可识别的手机号",
            "未匹配到 11 位中国大陆手机号（分隔符不影响识别）。",
            "补一行手机号，用 138 0000 0000 或 13800000000 均可，避免写成图片。")
    missing_sections = [s for s in REQUIRED_SECTIONS if s not in sections_found]
    if missing_sections:
        a -= min(8, 4 * len(missing_sections))
        zh = {"experience": "工作经历", "education": "教育背景", "skills": "专业技能"}
        add("MAJOR", "A", "缺少标准章节标题",
            "未识别到：" + "、".join(zh[s] for s in missing_sections) + "。系统按关键词定位字段，自造标题会让内容落到错误字段。",
            "用标准词做章节名：「工作经历」「教育背景」「专业技能」，不要用「我的故事」「这些年」这类标题。")
    if date_style_count == 0:
        a -= 6
        add("MAJOR", "A", "没有可识别的日期区间",
            "全文未匹配到 2021.03-2023.08 这类时间段。系统无法计算在职时长，人工也无法判断时间线是否连续。",
            "每段经历右侧统一写 2021.03 - 2023.08，格式全文一致。")
    elif date_style_count > 1:
        a -= 5
        add("MINOR", "A", "日期格式不统一",
            "检测到 %d 种日期写法：%s。混用会让解析字段错位。" % (date_style_count, "、".join(styles)),
            "全文统一为一种写法，建议 YYYY.MM。")
    if not has_present and sections_found:
        pass
    hl = hazard_lines
    if hl["table"]:
        a -= 4
        add("MAJOR", "A", "使用了表格排版",
            "检测到 %d 行表格。多数解析器会把表格拆成碎片文本，字段顺序全乱。" % hl["table"],
            "改成纯段落 + 项目符号，左右分栏的信息合并成一行。")
    if hl["image"]:
        a -= 4
        add("MAJOR", "A", "简历中含图片",
            "检测到 %d 处图片。图片里的文字提取不出来。" % hl["image"],
            "文字一律用文本；头像、公司 logo、技能进度条全部删掉。")
    if hl["tab"]:
        a -= 2
        add("MINOR", "A", "含制表符",
            "制表符在解析时会被当成字段分隔，导致错位。",
            "改空格或直接换行。")
    if hl["multispace"] >= 3:
        a -= 3
        add("MINOR", "A", "疑似用空格做分栏",
            "%d 行出现连续 4 个以上空格，通常是手动对齐的左右分栏。" % hl["multispace"],
            "去掉手动对齐，改成单列信息流。")
    if hl["pagemark"]:
        a -= 3
        add("MINOR", "A", "出现页眉页脚页码",
            "页眉页脚内容在多数系统里会被丢弃或重复插入正文。",
            "删掉页眉页脚；需要页码就在正文外由打印设置生成。")
    a = max(0, a)

    # Gate B
    b = 40
    if n_focus == 0:
        b -= 20
        add("BLOCKER", "B", "没有可分析的经历要点",
            "没有识别到项目符号形式的经历条目。整段叙述会让招聘方六秒内抓不到任何信息。",
            "把每段经历拆成 3-5 条要点，每条一行。")
    else:
        if n_focus < 6:
            b -= 10
            add("MAJOR", "B", "要点太少",
                "经历要点只有 %d 条。信息量不足以支撑一次初筛判断。" % n_focus,
                "每段主要经历至少 3 条，总量控制在 12-20 条。")
        elif n_focus > 40:
            b -= 3
            add("MINOR", "B", "要点过密",
                "共 %d 条要点，读起来会失去重点。" % n_focus,
                "删掉与目标岗位无关的条目，保留 12-20 条。")
        if avg_len and avg_len < 20:
            b -= 6
            add("MAJOR", "B", "要点过短",
                "平均每条 %.0f 字，多数是「负责X」式的短语，看不出结果。" % avg_len,
                "补上做到什么程度、影响多少人/多少钱。")
        elif avg_len and avg_len > 100:
            b -= 5
            add("MINOR", "B", "要点过长",
                "平均每条 %.0f 字，超过两行，扫读时会被跳过。" % avg_len,
                "一条只讲一件事，控制在 40-80 字。")
        if metrics["quantified_ratio"] < 0.2:
            b -= 12
            add("BLOCKER", "B", "几乎没有量化",
                "%d/%d 条要点含数字。初筛时「有没有成果」是唯一硬指标。" % (quant, n_focus),
                "每条至少一个数：规模、周期、金额、人数、比例，任选其一。")
        elif metrics["quantified_ratio"] < 0.4:
            b -= 8
            add("MAJOR", "B", "量化覆盖率偏低",
                "%d/%d 条要点含数字（%.0f%%）。" % (quant, n_focus, metrics["quantified_ratio"] * 100),
                "把「很多」「大幅」换成具体数。")
        elif metrics["quantified_ratio"] < 0.6:
            b -= 4
            add("MINOR", "B", "量化仍可加强",
                "%d/%d 条要点含数字。" % (quant, n_focus),
                "剩下的定性条目里，挑三条补口径。")
        if n_focus and metrics["strong_verb_ratio"] < 0.3:
            b -= 8
            add("MAJOR", "B", "要点多以弱动词开头",
                "仅 %d/%d 条以动作动词开头。" % (strong, n_focus),
                "把「负责/参与/协助」换成「搭建/重构/推动/定位」等具体动作。")
        elif n_focus and metrics["strong_verb_ratio"] < 0.5:
            b -= 5
            add("MINOR", "B", "部分要点开头偏软",
                "%d/%d 条以动作动词开头。" % (strong, n_focus),
                "逐条替换开头动词。")
        if summary_len > 120:
            b -= 4
            add("MINOR", "B", "自我评价占位过多",
                "自我评价/个人简介共 %d 字。这段在初筛时基本不被读，还挤掉了经历的位置。" % summary_len,
                "压到 2 行以内，或者整段删掉，把空间还给经历。")
    b = max(0, b)

    # Gate C
    c = 30
    if n_focus:
        if metrics["outcome_ratio"] < 0.2:
            c -= 10
            add("BLOCKER", "C", "缺可核对的成果口径",
                "只有 %d 条要点写了带单位的成果。面试第一条追问就是「这个数怎么来的」。" % outcome,
                "补口径：基数是多少、统计周期多长、你负责其中哪一段。")
        elif metrics["outcome_ratio"] < 0.4:
            c -= 6
            add("MAJOR", "C", "成果口径不足",
                "%d/%d 条要点有带单位的成果。" % (outcome, n_focus),
                "至少一半要点能量化到单位。")
        avg_empty = empty_total / n_focus
        if avg_empty > 2:
            c -= 8
            add("MAJOR", "C", "空泛评价词过多",
                "平均每条要点出现 %.1f 个空泛词（精通/显著/良好/全面等）。" % avg_empty,
                "逐个删掉，换成事实。")
        elif avg_empty > 0.8:
            c -= 4
            add("MINOR", "C", "存在空泛评价词",
                "共出现 %d 次。" % empty_total,
                "删掉形容词，用数据替代。")
        if dup >= 2:
            c -= 6
            add("MAJOR", "C", "多条要点开头重复",
                "%d 条要点与前面某条前 6 个字相同，读起来像复制粘贴。" % dup,
                "改开头，让每条指向不同的事。")
        elif dup == 1:
            c -= 3
        if metrics["overclaim_hits"]:
            c -= 3
            add("MAJOR", "C", "出现过度自评",
                "出现 %d 处「精通/专家级/行业第一」类表述。面试官会专门挑这类词验证。" % metrics["overclaim_hits"],
                "删掉自我评级，改用可验证的事实：几年、几个项目、什么规模。")
    else:
        c = 0
    c = max(0, c)

    total = a + b + c
    if total >= 90:
        grade, verdict = "A", "可以直接投"
    elif total >= 75:
        grade, verdict = "B", "小修后可投"
    elif total >= 60:
        grade, verdict = "C", "要点需要重写"
    else:
        grade, verdict = "D", "骨架需要重建"

    order = {"BLOCKER": 0, "MAJOR": 1, "MINOR": 2}
    findings.sort(key=lambda f: (order[f["severity"]], f["gate"]))

    return {
        "scores": {"A_machine": a, "B_scan": b, "C_defense": c, "total": total},
        "grade": grade,
        "verdict": verdict,
        "metrics": metrics,
        "findings": findings,
        "jd_provided": bool(jd_text),
    }


# ---------------------------------------------------------------- reporting

SEV_LABEL = {"BLOCKER": "[致命]", "MAJOR": "[重要]", "MINOR": "[次要]"}
GATE_LABEL = {"A": "闸门A 机器解析", "B": "闸门B 六秒扫描", "C": "闸门C 追问耐受"}


def render_markdown(res):
    s = res["scores"]
    m = res["metrics"]
    out = []
    out.append("# 简历机械体检报告\n")
    out.append("> 本报告只覆盖**可计算**的指标。成果是否打动招聘方、职业故事是否自洽，"
               "需要人工判断，不在脚本结论内。\n")
    out.append("## 总览\n")
    out.append("| 项目 | 结果 |")
    out.append("|---|---|")
    out.append("| 总分（机械代理） | %d / 100 |" % s["total"])
    out.append("| 等级 | %s |" % res["grade"])
    out.append("| 结论 | %s |" % res["verdict"])
    out.append("| 闸门A 机器解析 | %d / 30 |" % s["A_machine"])
    out.append("| 闸门B 六秒扫描 | %d / 40 |" % s["B_scan"])
    out.append("| 闸门C 追问耐受（代理） | %d / 30 |" % s["C_defense"])
    out.append("")

    out.append("## 关键指标\n")
    out.append("| 指标 | 数值 | 参考区间 |")
    out.append("|---|---|---|")
    rows = [
        ("字数（不含空格）", m["char_count"], "中文一页 700-1100"),
        ("经历要点数", m["bullet_count"], "12-20"),
        ("要点平均字数", m["bullet_avg_len"], "40-80"),
        ("含量化的要点", "%d（%.0f%%）" % (m["quantified_bullets"], m["quantified_ratio"] * 100), "≥70%"),
        ("含单位成果的要点", "%d（%.0f%%）" % (m["outcome_bullets"], m["outcome_ratio"] * 100), "≥50%"),
        ("动作动词开头的要点", "%d（%.0f%%）" % (m["strong_verb_bullets"], m["strong_verb_ratio"] * 100), "≥70%"),
        ("弱动词开头的要点", m["weak_opener_bullets"], "0"),
        ("空泛评价词出现次数", m["empty_phrase_hits"], "≤3"),
        ("重复开头的要点", m["duplicate_openings"], "0"),
        ("日期写法种类", m["date_style_count"], "1"),
        ("识别到的章节", "、".join(m["sections_found"]) or "无", "含经历/教育/技能"),
        ("邮箱 / 手机", "%d / %d" % (m["email_found"], m["phone_found"]), "各 1"),
    ]
    for k, v, ref in rows:
        out.append("| %s | %s | %s |" % (k, v, ref))
    out.append("")

    if res["findings"]:
        out.append("## 问题清单（按严重度排序）\n")
        for i, f in enumerate(res["findings"], 1):
            out.append("### %d. %s %s · %s" % (i, SEV_LABEL[f["severity"]], GATE_LABEL[f["gate"]], f["title"]))
            out.append("")
            out.append("- 证据：%s" % f["detail"])
            out.append("- 改法：%s" % f["action"])
            out.append("")
    else:
        out.append("## 问题清单\n\n机械指标未发现明显问题。\n")

    if m["empty_phrase_detail"]:
        out.append("## 空泛词明细\n")
        out.append("| 词 | 次数 |")
        out.append("|---|---|")
        for w, n in sorted(m["empty_phrase_detail"].items(), key=lambda x: -x[1]):
            out.append("| %s | %d |" % (w, n))
        out.append("")

    out.append("## 下一步\n")
    if s["total"] < 60:
        out.append("1. 先修致命项：联系方式、章节标题、量化。")
        out.append("2. 再把每段经历拆成 3 条带数字的要点。")
        out.append("3. 改完重跑本脚本，确认致命项清零，再进入重写与岗位定制。")
    elif s["total"] < 75:
        out.append("1. 处理所有 [重要] 项。")
        out.append("2. 逐条把弱动词开头换成具体动作。")
        out.append("3. 有目标 JD 的话，接着做覆盖匹配。")
    else:
        out.append("1. 处理剩余 [次要] 项即可。")
        out.append("2. 确认页数与版式，进入导出环节。")
    out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="resume mechanical audit (three-gate proxy)")
    ap.add_argument("resume", help="resume file (md / txt)")
    ap.add_argument("--jd", help="optional job description file")
    ap.add_argument("--json", action="store_true", help="print JSON instead of markdown")
    ap.add_argument("--out", help="write report to file")
    args = ap.parse_args()

    try:
        text = read_text(args.resume)
    except OSError as e:
        print("ERROR: cannot read %s (%s)" % (args.resume, e), file=sys.stderr)
        return 2

    jd_text = None
    if args.jd:
        try:
            jd_text = read_text(args.jd)
        except OSError as e:
            print("WARN: cannot read jd %s (%s)" % (args.jd, e), file=sys.stderr)

    res = analyze(text, jd_text)
    res["source"] = str(Path(args.resume).name)

    if args.json:
        payload = json.dumps(res, ensure_ascii=False, indent=2)
    else:
        payload = render_markdown(res)

    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
        print("written: %s" % args.out)
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
