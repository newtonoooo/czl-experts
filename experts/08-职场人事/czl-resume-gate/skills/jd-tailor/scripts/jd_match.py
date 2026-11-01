#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""jd_match.py - compare a resume against a job description.

Splits JD requirements into must-have and nice-to-have, extracts skill terms
from a built-in bilingual lexicon plus ASCII tokens, then reports coverage as
covered / transferable / missing, with hard-gate checks (degree, years).

Standard library only. Usage:
    python jd_match.py --jd JD.md --resume RESUME.md [--json] [--out report.md]
"""

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------- lexicon

# term -> synonyms that count as "transferable" (adjacent evidence, not the term itself)
LEXICON = {
    # 数据 / 分析
    "数据分析": ["数据", "指标", "报表", "看板", "洞察"],
    "数据建模": ["建模", "模型", "特征"],
    "SQL": ["sql", "数据库", "查询", "hive", "mysql"],
    "Python": ["python", "pandas", "numpy", "脚本"],
    "Excel": ["excel", "表格", "透视表"],
    "Tableau": ["tableau", "bi", "看板", "可视化"],
    "Power BI": ["power bi", "bi", "看板"],
    "A/B测试": ["a/b", "ab test", "实验", "灰度", "分流"],
    "用户增长": ["拉新", "增长", "获客", "留存", "促活"],
    "用户分层": ["分层", "标签", "人群"],
    "漏斗分析": ["漏斗", "转化率", "路径"],
    "归因分析": ["归因", "渠道效果"],
    "指标体系": ["指标", "口径", "字典"],
    "机器学习": ["模型", "算法", "训练", "特征工程"],
    "统计": ["统计", "显著性", "置信"],
    # 产品 / 运营
    "需求分析": ["需求", "用户调研", "访谈"],
    "产品设计": ["原型", "prd", "交互", "方案"],
    "项目管理": ["项目", "推进", "排期", "里程碑"],
    "活动运营": ["活动", "策划", "落地"],
    "内容运营": ["内容", "选题", "编辑"],
    "社群运营": ["社群", "私域", "用户群"],
    "电商运营": ["店铺", "商品", "sku", "大促"],
    "SEO": ["seo", "搜索优化", "关键词"],
    "投放": ["投放", "广告", "信息流", "roi"],
    # 技术
    "Java": ["java", "spring", "jvm"],
    "Go": ["golang", "go "],
    "C++": ["c++", "cpp"],
    "前端": ["前端", "react", "vue", "javascript", "typescript"],
    "后端": ["后端", "服务端", "接口", "api"],
    "微服务": ["微服务", "服务拆分", "rpc", "dubbo"],
    "数据库": ["数据库", "mysql", "postgres", "oracle", "索引"],
    "Linux": ["linux", "shell", "bash"],
    "Docker": ["docker", "容器", "镜像"],
    "Kubernetes": ["kubernetes", "k8s", "集群"],
    "CI/CD": ["ci/cd", "jenkins", "流水线", "持续集成"],
    "云服务": ["阿里云", "aws", "腾讯云", "云平台"],
    "性能优化": ["性能", "压测", "响应时间", "qps"],
    "高并发": ["并发", "qps", "吞吐"],
    "测试": ["测试", "用例", "自动化测试", "回归"],
    "运维": ["运维", "监控", "告警", "故障"],
    "安全": ["安全", "漏洞", "渗透", "加固"],
    # 商务 / 销售
    "客户开发": ["客户", "开拓", "线索", "签单"],
    "大客户": ["大客户", "ka", "重点客户"],
    "商务谈判": ["谈判", "议价", "合同"],
    "渠道": ["渠道", "代理", "分销"],
    "销售管理": ["团队", "业绩", "目标", "回款"],
    # 职能
    "招聘": ["招聘", "面试", "人才", "hc"],
    "培训": ["培训", "课程", "带教"],
    "绩效": ["绩效", "考核", "okr", "kpi"],
    "薪酬": ["薪酬", "薪资", "福利"],
    "财务分析": ["财务", "预算", "成本", "报表"],
    "法务": ["法务", "合同审核", "合规"],
    "行政": ["行政", "采购", "资产"],
    # 通用能力
    "跨部门协作": ["跨部门", "协调", "协同", "对接"],
    "沟通表达": ["沟通", "汇报", "表达", "宣讲"],
    "团队管理": ["管理", "带团队", "下属", "带队"],
    "英语": ["英语", "english", "cet", "雅思", "托福"],
    "文档能力": ["文档", "ppt", "汇报材料", "方案"],
}

GENERIC_STOP = {"jd", "cv", "hr", "ai", "it", "pm", "bg", "ok", "no"}

STOPWORDS = {
    "the", "and", "for", "with", "you", "your", "our", "will", "are", "has", "have",
    "this", "that", "from", "not", "but", "can", "all", "any", "who", "how", "its",
    "job", "team", "work", "role", "company", "description", "requirements", "plus",
    "and/or", "etc", "ability", "strong", "good", "years", "year", "experience",
}

REQUIRED_CUES = ["必须", "要求", "需具备", "需要", "至少", "以上", "熟悉", "精通",
                 "掌握", "负责", "本科", "硕士", "学历", "具备", "能够", "以上学历"]
PLUS_CUES = ["优先", "加分", "更佳", "更好", "了解", "接触过", "有…经验者优先",
             "nice to have", "preferred", "plus"]

DEGREE_ORDER = [("博士", 4), ("硕士", 3), ("本科", 2), ("大专", 1), ("专科", 1), ("高中", 0)]


def read_text(path):
    data = Path(path).read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def norm(s):
    """lowercase, whitespace removed (so 'A/B 测试' matches 'a/b测试')."""
    return re.sub(r"\s+", "", s.lower())


def ascii_tokens(text):
    toks = re.findall(r"\b[A-Za-z][A-Za-z0-9+#./\-]{1,15}\b", text)
    out = {}
    for t in toks:
        key = t.lower().strip(".-/")
        if len(key) < 3 or key in STOPWORDS or key in GENERIC_STOP:
            continue
        out[key] = out.get(key, 0) + 1
    return out


def split_sentences(text):
    parts = re.split(r"[\n。；;！!？?]+", text)
    return [p.strip() for p in parts if p.strip()]


def classify(sentence):
    s = sentence.lower()
    plus = any(c.lower() in s for c in PLUS_CUES)
    req = any(c in s for c in REQUIRED_CUES)
    if plus:
        return "plus"
    if req:
        return "must"
    return None


def extract_terms(text):
    """Return {term_display: {'bucket': ..., 'hits': n}} from lexicon + ascii tokens."""
    found = {}
    low = norm(text)
    for term, _syn in LEXICON.items():
        key = norm(term)
        if key.isascii():
            hit = len(re.findall(r"(?<![a-z0-9])" + re.escape(key) + r"(?![a-z0-9])", low))
        else:
            hit = low.count(key)
        if hit:
            found[term] = {"bucket": None, "hits": hit, "source": "lexicon"}

    lexicon_ascii = " ".join(t.lower() for t in LEXICON if t.isascii() or re.search(r"[A-Za-z]", t))
    lexicon_ascii = lexicon_ascii.replace(" ", "")
    for tok, n in ascii_tokens(text).items():
        if any(tok == t.lower() for t in found):
            continue
        if tok in lexicon_ascii:
            continue
        found[tok.upper() if len(tok) <= 4 else tok] = {"bucket": None, "hits": n, "source": "token"}
    return found


def bucketize(jd_text, terms):
    """Assign terms to must / plus by the sentence they first appear in."""
    result = {}
    sents = split_sentences(jd_text)
    for term in terms:
        key = term
        bucket = "other"
        for s in sents:
            if norm(key) in norm(s):
                b = classify(s)
                if b:
                    bucket = b
                    break
        result[term] = bucket
    return result


def degree_of(text):
    best = None
    for word, rank in DEGREE_ORDER:
        if word in text:
            if best is None or rank > best[1]:
                best = (word, rank)
    return best


def years_required(text):
    m = re.findall(r"(\d+)\s*(?:年|years?)\s*(?:以上|及以上|\+)", text, re.I)
    if not m:
        m = re.findall(r"(?:至少|minimum)\s*(\d+)\s*(?:年|years?)", text, re.I)
    return max((int(x) for x in m), default=None)


def years_in_resume(text):
    """Estimate the date span covered by the resume (years, one decimal)."""
    import datetime
    pts = []
    for m in re.finditer(r"((?:19|20)\d{2})\s*[.\-/年]\s*(\d{1,2})", text):
        pts.append((int(m.group(1)), max(1, min(12, int(m.group(2))))))
    if not pts:
        return None
    if re.search(r"至今|现在|present|now|current", text, re.I):
        today = datetime.date.today()
        pts.append((today.year, today.month))
    ys = [y + (mo - 1) / 12.0 for y, mo in pts]
    span = max(ys) - min(ys)
    return round(span, 1) if span > 0 else None


def coverage(term, resume_norm):
    if norm(term) in resume_norm:
        return "covered"
    for syn in LEXICON.get(term, []):
        if norm(syn) in resume_norm:
            return "transferable"
    return "missing"


def match(resume_text, jd_text):
    rn = norm(resume_text)
    terms = extract_terms(jd_text)
    buckets = bucketize(jd_text, terms)

    rows = []
    for term, meta in terms.items():
        st = coverage(term, rn)
        rows.append({
            "term": term,
            "bucket": buckets.get(term, "other"),
            "status": st,
            "hits_in_jd": meta["hits"],
            "source": meta["source"],
        })

    rows.sort(key=lambda r: ({"must": 0, "plus": 1, "other": 2}[r["bucket"]], r["status"] != "missing", r["term"]))

    def score(bucket):
        subset = [r for r in rows if r["bucket"] == bucket]
        if not subset:
            return None
        val = 0.0
        for r in subset:
            val += 1.0 if r["status"] == "covered" else 0.5 if r["status"] == "transferable" else 0.0
        return round(val / len(subset), 3), len(subset)

    must = score("must")
    plus = score("plus")
    other = score("other")

    if must and plus:
        overall = round(must[0] * 0.75 + plus[0] * 0.25, 3)
    elif must:
        overall = must[0]
    elif plus:
        overall = plus[0]
    else:
        overall = 0.0

    # hard gates
    jd_deg = degree_of(jd_text)
    rs_deg = degree_of(resume_text)
    gates = []
    if jd_deg:
        gates.append({
            "gate": "学历",
            "jd": jd_deg[0],
            "resume": rs_deg[0] if rs_deg else "未识别",
            "verdict": ("满足" if rs_deg and rs_deg[1] >= jd_deg[1]
                        else "需确认" if not rs_deg else "疑似不满足"),
        })
    yreq = years_required(jd_text)
    if yreq:
        gates.append({
            "gate": "工作年限",
            "jd": "%d 年以上" % yreq,
            "resume": ("简历日期跨度约 %.1f 年（含教育/空档）" % years_in_resume(resume_text)) if years_in_resume(resume_text) else "未识别",
            "verdict": "需人工核对起止时间",
        })

    return {
        "overall": overall,
        "must": {"ratio": must[0] if must else None, "count": must[1] if must else 0},
        "plus": {"ratio": plus[0] if plus else None, "count": plus[1] if plus else 0},
        "rows": rows,
        "gates": gates,
    }


# ---------------------------------------------------------------- report

STATUS_LABEL = {"covered": "已覆盖", "transferable": "可迁移", "missing": "缺失"}
BUCKET_LABEL = {"must": "必备", "plus": "加分", "other": "其他提及"}


def render(res, jd_name="JD"):
    out = []
    out.append("# 岗位匹配报告\n")
    out.append("> 词表匹配基于内置技能词典与 JD 中的英文术语，只能发现「写了没写」，"
               "判断不了「写得够不够深」。缺失项要先确认是真缺，还是只是没写。\n")

    def pct(v):
        return "—" if v is None else "%.0f%%" % (v * 100)

    out.append("## 总览\n")
    out.append("| 项目 | 结果 |")
    out.append("|---|---|")
    out.append("| 综合匹配度 | %.0f%% |" % (res["overall"] * 100))
    out.append("| 必备项覆盖率 | %s（%d 项） |" % (pct(res["must"]["ratio"]), res["must"]["count"]))
    out.append("| 加分项覆盖率 | %s（%d 项） |" % (pct(res["plus"]["ratio"]), res["plus"]["count"]))
    out.append("")

    if res["gates"]:
        out.append("## 硬门槛\n")
        out.append("| 门槛 | JD 要求 | 简历现状 | 判定 |")
        out.append("|---|---|---|---|")
        for g in res["gates"]:
            out.append("| %s | %s | %s | %s |" % (g["gate"], g["jd"], g["resume"], g["verdict"]))
        out.append("")

    for bucket in ("must", "plus", "other"):
        subset = [r for r in res["rows"] if r["bucket"] == bucket]
        if not subset:
            continue
        out.append("## %s项匹配\n" % BUCKET_LABEL[bucket])
        out.append("| 术语 | 状态 | JD 出现次数 |")
        out.append("|---|---|---|")
        for r in subset:
            out.append("| %s | %s | %d |" % (r["term"], STATUS_LABEL[r["status"]], r["hits_in_jd"]))
        out.append("")

    missing_must = [r["term"] for r in res["rows"] if r["bucket"] == "must" and r["status"] == "missing"]
    trans = [r["term"] for r in res["rows"] if r["status"] == "transferable"]
    if missing_must:
        out.append("## 必备项缺失（优先处理）\n")
        for t in missing_must:
            out.append("- **%s**：简历里没有任何对应表述。先确认是真没有，还是做过但没写。" % t)
        out.append("")
    if trans:
        out.append("## 可迁移项（写过相近的，需要换成 JD 的说法）\n")
        for t in trans:
            out.append("- **%s**：简历里有相邻经历，改写成本行业的表述即可，不要凭空新增。" % t)
        out.append("")

    out.append("## 使用纪律\n")
    out.append("1. 缺失 ≠ 编造。真没有的项不要硬塞，改为在面试中说明学习路径。")
    out.append("2. 关键词要落在经历行里，不要单独堆一个「关键词」段落，那是明显的应试痕迹。")
    out.append("3. 同义词替换只改说法，不改事实。")
    out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="resume vs JD coverage matcher")
    ap.add_argument("--jd", required=True, help="job description file")
    ap.add_argument("--resume", required=True, help="resume file")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out")
    args = ap.parse_args()

    try:
        jd = read_text(args.jd)
        rv = read_text(args.resume)
    except OSError as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 2

    res = match(rv, jd)
    payload = json.dumps(res, ensure_ascii=False, indent=2) if args.json else render(res)
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
        print("written: %s" % args.out)
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
