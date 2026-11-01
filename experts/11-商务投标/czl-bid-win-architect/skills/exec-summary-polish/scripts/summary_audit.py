#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""执行摘要体检：只回答一个问题——评委读完前三行，会不会想继续读。

检查项：
  1. 开头是不是客户（而不是公司简介）
  2. 五段结构齐不齐：处境 / 代价 / 判断 / 证据 / 结果
  3. 空洞形容词有多少个、在哪
  4. 句子是不是太长（评委在手机上看标书）
  5. 有没有可核的数字

用法：
    python summary_audit.py 摘要.md --client 蜀通
    python summary_audit.py 摘要.md --client 蜀通 --json out.json
"""

import argparse
import json
import re
import sys
from pathlib import Path

EMPTY_WORDS = [
    "强大", "领先", "一流", "尖端", "先进", "卓越", "优质", "赋能",
    "全方位", "一站式", "丰富的经验", "致力于", "专业的团队", "优秀的",
    "完善的", "高效的", "贴心", "行业领先", "国内领先", "国际领先",
    "顶尖", "资深", "实力雄厚", "多年经验", "精益求精", "深度融合",
]

MOVES = [
    ("处境", ["面临", "当前", "正在", "目前在", "过程中", "随着", "由于", "受制于",
              "现在", "目前", "现有", "现状", "今年", "去年", "纳入", "被考核",
              "考核", "要求", "规定"]),
    ("代价", ["代价", "风险", "若不", "一旦", "延误", "损失", "返工", "罚款",
              "考核", "投诉", "缺口", "隐患", "影响", "压力"]),
    ("判断", ["我们将", "本方案", "我们的做法", "我们提出", "通过", "采取",
              "以…方式", "分阶段", "第一步", "核心是"]),
    ("证据", ["案例", "项目", "验收", "上线", "%", "％", "个月", "年", "家",
              "份", "次", "人", "台", "套"]),
    ("结果", ["个月后", "周后", "达成", "实现", "届时", "交付后", "上线后",
              "可验收", "降至", "提升到", "稳定在"]),
]

BAD_START = ["我司", "本公司", "公司成立", "我们成立", "成立于", "公司简介",
             "感谢", "首先", "随着信息技术的", "在当今"]

SENT_SPLIT = re.compile(r"[。！？；\n]+")


def load(path: str) -> str:
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"文件不存在: {p}")
    return p.read_text(encoding="utf-8")


def analyze(text: str, client: str) -> dict:
    # 去掉标题行，否则“执行摘要”四个字会占掉前 100 字的名额
    body = "\n".join(l for l in text.splitlines() if not l.strip().startswith("#")).strip()
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    plain = re.sub(r"[#>*`\-\|]", "", body)
    chars = len(re.sub(r"\s", "", plain))

    head = re.sub(r"\s", "", plain)[:100]

    issues, fixes = [], []
    score = 0

    # 1. 开头
    start_hit = next((w for w in BAD_START if head.startswith(w)), None)
    if start_hit:
        issues.append(f"开头是公司视角（“{start_hit}”），评委在这里会翻页")
        fixes.append("第一句改成客户处境：他们的系统、期限、被考核的指标")
    elif client and client not in head:
        issues.append(f"前 100 字没有出现客户名“{client}”")
        fixes.append("把客户名或其项目名放进第一句，证明这份是给他写的")
        score += 10
    else:
        score += 20

    # 2. 五段
    hits = {}
    for name, keys in MOVES:
        k = [w for w in keys if w in plain]
        hits[name] = {"hit": bool(k), "keys": k[:4], "count": len(k)}
        if k:
            score += 14
        else:
            issues.append(f"缺“{name}”这一段：{hint_for(name)}")
            fixes.append(fix_for(name))
    if re.search(r"\d", plain):
        score += 10
    else:
        issues.append("全文没有一个数字，“可衡量”在这一稿里是空的")
        fixes.append("至少给三个数：客户现状值、目标值、你的证据里的值")

    # 3. 空洞词
    empties = []
    for w in EMPTY_WORDS:
        for m in re.finditer(re.escape(w), plain):
            empties.append({"word": w, "at": m.start()})
    if empties:
        pen = min(len(empties) * 4, 28)
        score -= pen
        words = "、".join(sorted({e["word"] for e in empties}))
        issues.append(f"空洞形容词/套话 {len(empties)} 处：{words}")
        fixes.append("逐个删掉。删完读一遍，语义没变就说明它们本来就不承担信息")

    # 4. 句长
    sents = [s.strip() for s in SENT_SPLIT.split(plain) if len(s.strip()) > 1]
    lens = [len(s) for s in sents]
    avg = sum(lens) / len(lens) if lens else 0
    longs = [s for s in sents if len(s) > 60]
    if avg > 50:
        score -= 5
        issues.append(f"平均句长 {avg:.0f} 字，偏长")
        fixes.append("拆句：一句话只说一件事，超过 50 字就断")
    if longs:
        score -= min(len(longs) * 2, 8)
        issues.append(f"{len(longs)} 句超过 60 字，评委在手机上会跳读")
        fixes.append(f"第一句超长句是：{longs[0][:40]}…——从这里开始拆")

    # 5. 篇幅
    if chars > 900:
        score -= 5
        issues.append(f"全文 {chars} 字，超过一页（约 800 字）")
        fixes.append("砍到 700 字以内：只留能改变判断的句子")
    elif chars < 200:
        score -= 8
        issues.append(f"全文只有 {chars} 字，撑不起一份结案陈词")
        fixes.append("至少写到 400 字：处境、代价、判断、证据、结果各一句以上")

    score = max(0, min(100, score))
    grade = "可用" if score >= 75 else ("要改" if score >= 50 else "重写")

    return {
        "score": score, "grade": grade, "chars": chars,
        "paragraphs": len(paras), "avg_sentence_len": round(avg, 1),
        "long_sentences": len(longs), "empty_words": len(empties),
        "moves": hits, "issues": issues, "fixes": fixes,
    }


def hint_for(name):
    return {
        "处境": "客户现在卡在哪，用他的语言说",
        "代价": "不做会怎样，尽量带数",
        "判断": "我们打算怎么做，一句话说清",
        "证据": "凭什么信你，一个硬案例",
        "结果": "做完之后他拿到什么，可验收",
    }[name]


def fix_for(name):
    return {
        "处境": "补 2 句：客户的组织现状 + 本次被考核的具体指标",
        "代价": "补一句：不解决的量化损失，或合规/工期上的硬约束",
        "判断": "补一句：本方案的核心动作（不是“我们提供”，是“我们怎么干”）",
        "证据": "补一句：一个同类项目的可核结果，带数字",
        "结果": "补一句：3/6/12 个月后客户能验收到的状态",
    }[name]


def to_md(r, client) -> str:
    lines = [f"# 执行摘要体检：{r['score']}/100　{r['grade']}", ""]
    lines.append(f"- 字数 {r['chars']}，段落 {r['paragraphs']}，平均句长 {r['avg_sentence_len']} 字，"
                 f"超长句 {r['long_sentences']} 句，空洞词 {r['empty_words']} 处")
    if client:
        lines.append(f"- 客户名基准：{client}")
    lines += ["", "## 五段结构", "", "| 段落 | 是否出现 | 命中词 |", "|---|---|---|"]
    for name, v in r["moves"].items():
        lines.append(f"| {name} | {'有' if v['hit'] else '缺'} | {'、'.join(v['keys']) or '—'} |")
    if r["issues"]:
        lines += ["", "## 问题", ""]
        for i in r["issues"]:
            lines.append(f"- {i}")
    if r["fixes"]:
        lines += ["", "## 改法", ""]
        for f in r["fixes"]:
            lines.append(f"- {f}")
    lines += ["", "> 分数只是体检指标，不代表评审得分。真正的判断标准是："
              "把这份摘要单独发给一个不了解项目的人，他能不能复述出你要干什么。"]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="执行摘要体检")
    ap.add_argument("file", help="摘要文件（md/txt）")
    ap.add_argument("--client", default="", help="客户名称，用于检查前 100 字是否点名")
    ap.add_argument("--json", default=None, help="JSON 输出路径")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    text = load(args.file)
    r = analyze(text, args.client)
    md = to_md(r, args.client)
    print(md)
    if args.json:
        Path(args.json).write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n已写出：{args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
