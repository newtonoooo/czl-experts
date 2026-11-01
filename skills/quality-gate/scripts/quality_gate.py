#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
quality_gate.py — 公众号稿件量化体检闸门（朱笔 / quality-gate 技能）

纯标准库实现，不联网、不上传文本。对一篇中文稿件做可复现的量化检测，
输出分项得分、硬伤清单与具体位置，供人工定点修改。

用法:
    python quality_gate.py draft.md
    python quality_gate.py draft.md --json
    cat draft.md | python quality_gate.py -
    python quality_gate.py draft.md --min-score 80

退出码:
    0  通过（无硬伤且总分 >= min-score）
    1  未通过
    2  输入错误
"""

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass, field, asdict

# ---------------------------------------------------------------- 词表
# 说明：词表是启发式检测的信号源，不是"禁词法"。命中不等于必须删除，
# 但每命中一处都必须在人工复查时给出处理理由。

CLICHE = [
    # 公文腔 / 汇报腔
    "赋能", "抓手", "闭环", "颗粒度", "底层逻辑", "深度融合", "持续发力",
    "全方位", "多维度", "极大地", "进一步", "在一定程度上", "形成合力",
    "提质增效", "打通", "生态位", "组合拳", "护城河",
    # 议论文套话
    "总而言之", "综上所述", "众所周知", "不难发现", "值得注意的是",
    "首先", "其次", "最后", "由此可见", "换言之", "换句话说",
    "随着社会的发展", "在这个", "的时代背景下", "让我们一起",
    "可以说", "毋庸置疑", "不可否认",
]

# 元叙述：作者跳出来提示读者该怎么读。这是 AI 稿最典型的痕迹。
META = [
    "这才是全文", "多说一句", "请注意", "值得强调", "下面我们", "本文将",
    "这部分很关键", "读者可能", "划重点", "敲黑板", "不得不说",
    "看到这里", "到这里你会发现", "重点来了", "讲到这里",
]

# 总结句标签：用一个标签代替论证。
SUMMARY_TAG = [
    "一句话概括", "说到底", "归根结底", "简单来说", "简而言之",
    "本质上讲", "核心就是", "用一句话", "概括一下",
]

# 段落首尾的连接词：段落功能被"过渡句"占满的信号。
CONNECT_HEAD = [
    "因此", "所以", "这意味着", "可见", "总之", "综上", "接下来",
    "另外", "同时", "此外", "然而", "但是", "另一方面",
]
CONNECT_TAIL = ["因此", "所以", "可见", "总之", "综上", "这就是", "以上就是"]

# 口语痕迹：真人写作通常带这些，AI 稿往往干净得反常。
ORAL = [
    "其实", "反正", "你看", "说白了", "我猜", "大概", "有点儿", "有点",
    "说白了就是", "话说回来", "倒是", "也就是说", "那就", "这事儿",
    "老实说", "讲真", "不太", "挺", "蛮", "啥", "咋",
]

PUNCT_END = "。！？…"
SENT_SPLIT = re.compile(r"[。！？…]+")

# 分项满分，用于报告展示
MAX_SCORES = {
    "节奏变化": 20, "套话控制": 20, "元叙述": 15, "句式变化": 15,
    "段落功能": 10, "比喻密度": 5, "生活痕迹": 10, "具体信息": 5,
}

# 时间与场景标记：真人写稿几乎一定会落到具体时刻上。
LIFE_MARKER = re.compile(
    r"(第一天|第二天|第三天|那天|早上|上午|中午|下午|晚上|半夜|昨天|前天|"
    r"去年|前年|今年|上周|上个月|后来|临走|有一次|有一回|当时|那天下午)"
)
# 中文数量词：中文写作里数字多为汉字，只统计阿拉伯数字会严重低估。
CN_NUM = re.compile(
    r"[零一二三四五六七八九十百千万亿两]{1,4}"
    r"(?=[个张页元年月日岁块份人天篇次条台本层遍公里米斤])"
)
NOT_BUT = re.compile(r"不是[^。！？\n]{0,30}?而是")
METAPHOR = ["像", "如同", "仿佛", "好似", "宛如"]
DIGIT = re.compile(r"\d")


@dataclass
class Hit:
    kind: str
    word: str
    snippet: str
    index: int  # 句序（1 起）

    def line(self):
        return f"{self.kind}：「{self.word}」→ …{self.snippet}…"


@dataclass
class Report:
    chars: int = 0
    sentences: int = 0
    paragraphs: int = 0
    avg_sent_len: float = 0.0
    sent_len_cv: float = 0.0
    avg_para_len: float = 0.0
    short_ratio: float = 0.0
    long_ratio: float = 0.0
    scores: dict = field(default_factory=dict)
    total: float = 0.0
    verdict: str = ""
    hard_fails: list = field(default_factory=list)
    hits: list = field(default_factory=list)
    advice: list = field(default_factory=list)


def _norm(text):
    text = text.replace("\r\n", "\n").replace("\u3000", " ")
    return text.strip()


def strip_markdown(text):
    """去掉标题符号、加粗、链接语法，保留正文文字。"""
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.replace("**", "").replace("__", "").replace("`", "")
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.M)
    text = re.sub(r"^\s*>\s?", "", text, flags=re.M)
    return text


def split_paragraphs(text):
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return paras


def split_sentences(text):
    raw = SENT_SPLIT.split(text)
    out = []
    for s in raw:
        s = s.strip().strip("「」“”\"'，,：: ")
        if s and re.search(r"[\u4e00-\u9fffA-Za-z0-9]", s):
            out.append(s)
    return out


def char_len(s):
    """中文计字：按非空白字符数计算。"""
    return len(re.sub(r"\s", "", s))


def collect_hits(sentences, words, kind):
    hits = []
    for i, s in enumerate(sentences, 1):
        for w in words:
            if w in s:
                pos = s.find(w)
                start = max(0, pos - 6)
                snippet = s[start:start + 18]
                hits.append(Hit(kind, w, snippet, i))
    return hits


def find_uniform_runs(sentences, min_run=3, tol=4, max_len=30):
    """找连续 min_run 句以上、长度接近且都不长的句串（同构短句症）。"""
    runs = []
    i = 0
    n = len(sentences)
    while i < n:
        j = i
        while j + 1 < n:
            a, b = char_len(sentences[j]), char_len(sentences[j + 1])
            if a <= max_len and b <= max_len and abs(a - b) <= tol:
                j += 1
            else:
                break
        if j - i + 1 >= min_run:
            runs.append((i + 1, j + 1, sentences[i][:14]))
            i = j + 1
        else:
            i += 1
    return runs


def find_parallel_runs(sentences, min_run=3, tol=2):
    """启发式识别三段式对仗：连续短句长度几乎相等（差 <= tol）。"""
    runs = []
    i = 0
    while i < len(sentences) - min_run + 1:
        lens = [char_len(s) for s in sentences[i:i + min_run]]
        if max(lens) - min(lens) <= tol and all(4 <= x <= 26 for x in lens):
            # 需要存在并列标记，否则只是短句，不判对仗
            window = "".join(sentences[i:i + min_run])
            if any(m in window for m in ("是", "在", "要")):
                runs.append((i + 1, sentences[i][:16]))
                i += min_run
                continue
        i += 1
    return runs


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def analyze(raw_text, min_score=75):
    text = _norm(raw_text)
    if not text:
        raise ValueError("输入为空")

    plain = strip_markdown(text)
    paras = split_paragraphs(plain)
    sentences = split_sentences(plain)

    r = Report()
    r.chars = char_len(plain)
    r.sentences = len(sentences)
    r.paragraphs = len(paras)
    if r.sentences == 0 or r.paragraphs == 0:
        raise ValueError("找不到可分析的正文段落")

    lens = [char_len(s) for s in sentences]
    mean = sum(lens) / len(lens)
    var = sum((x - mean) ** 2 for x in lens) / len(lens)
    std = math.sqrt(var)
    r.avg_sent_len = round(mean, 1)
    r.sent_len_cv = round(std / mean, 3) if mean else 0.0
    r.avg_para_len = round(sum(char_len(p) for p in paras) / len(paras), 1)
    r.short_ratio = round(sum(1 for x in lens if x <= 8) / len(lens), 3)
    r.long_ratio = round(sum(1 for x in lens if x >= 45) / len(lens), 3)

    k = max(r.chars, 1) / 1000.0  # 每千字

    # --- 命中统计
    cliche_hits = collect_hits(sentences, CLICHE, "套话")
    meta_hits = collect_hits(sentences, META, "元叙述")
    tag_hits = collect_hits(sentences, SUMMARY_TAG, "总结句标签")
    not_but = [Hit("句式", "不是…而是", s[:18], i)
               for i, s in enumerate(sentences, 1) if NOT_BUT.search(s)]
    metaphor_hits = []
    for i, s in enumerate(sentences, 1):
        found = [m for m in METAPHOR if m in s]
        if found:
            metaphor_hits.append(Hit("比喻", found[0], s[:18], i))
    oral_hits = collect_hits(sentences, ORAL, "口语")
    uniform = find_uniform_runs(sentences)
    parallel = find_parallel_runs(sentences)

    # --- 段落功能密度：首尾被过渡句占用的段落比例
    func_paras = 0
    for p in paras:
        head = p[:6]
        tail = p[-8:]
        if any(head.startswith(w) for w in CONNECT_HEAD) or \
           any(tail.rstrip("。！？… ").endswith(w) for w in CONNECT_TAIL):
            func_paras += 1
    func_ratio = func_paras / len(paras)

    digi = len(DIGIT.findall(plain))
    cn_num = len(CN_NUM.findall(plain))
    quotes = plain.count("「") + plain.count("“") + plain.count("《")
    life = len(LIFE_MARKER.findall(plain))
    quote_pairs = min(plain.count("「"), plain.count("」")) + min(plain.count("“"), plain.count("”"))
    life_evidence = len(oral_hits) + 2 * quote_pairs + 1.5 * life

    # --- 计分（满分 100）
    s_rhythm = clamp((r.sent_len_cv - 0.28) / 0.32 * 20, 0, 20)
    s_cliche = clamp(20 - (len(cliche_hits) / k) * 3.5, 0, 20)
    s_meta = clamp(15 - len(meta_hits) * 7 - len(tag_hits) * 5, 0, 15)
    s_uniform = clamp(15 - len(uniform) * 6 - len(parallel) * 3, 0, 15)
    s_func = clamp(10 - func_ratio * 22, 0, 10)
    s_meta_phor = clamp(5 - max(0, len(metaphor_hits) / max(len(paras), 1) - 0.4) * 12, 0, 5)
    s_life = clamp((life_evidence / k) * 2.4, 0, 10)
    s_concrete = clamp(((digi + cn_num + quotes) / k) * 1.0, 0, 5)

    r.scores = {
        "节奏变化": round(s_rhythm, 1),
        "套话控制": round(s_cliche, 1),
        "元叙述": round(s_meta, 1),
        "句式变化": round(s_uniform, 1),
        "段落功能": round(s_func, 1),
        "比喻密度": round(s_meta_phor, 1),
        "生活痕迹": round(s_life, 1),
        "具体信息": round(s_concrete, 1),
    }
    r.total = round(sum(r.scores.values()), 1)

    # --- 硬伤
    if meta_hits:
        r.hard_fails.append(f"出现 {len(meta_hits)} 处元叙述（作者提示读者该怎么读）")
    if tag_hits:
        r.hard_fails.append(f"出现 {len(tag_hits)} 处总结句标签（用标签代替论证）")
    if len(cliche_hits) > 3:
        r.hard_fails.append(f"套话 {len(cliche_hits)} 处，超过 3 处阈值")
    if uniform:
        r.hard_fails.append(f"出现 {len(uniform)} 处三句以上同构短句")
    if len(not_but) > 2:
        r.hard_fails.append(f"「不是…而是」句式 {len(not_but)} 处，超过 2 处阈值")
    if len(metaphor_hits) / max(len(paras), 1) > 0.6:
        r.hard_fails.append("比喻密度过高（平均每段接近一个）")
    if r.chars < 300:
        r.advice.append(f"全文仅 {r.chars} 字，样本偏小，分数波动大，建议对完整稿再跑一次。")

    r.hits = [h.line() for h in (meta_hits + tag_hits + cliche_hits + not_but + metaphor_hits)]
    if uniform:
        r.hits += [f"同构短句：第 {a}—{b} 句连排且长度接近，起于「{s}」" for a, b, s in uniform]
    if parallel:
        r.hits += [f"疑似对仗排比：第 {a} 句起「{s}」" for a, s in parallel]

    # --- 建议
    if s_rhythm < 12:
        r.advice.append("句长太整齐：把至少 3 处短句合成一句长的，或把一处长句拆开并删掉后半段的解释。")
    if s_cliche < 14:
        r.advice.append("套话偏多：优先删句子而不是换词——套话句多数可以直接整句删掉，上下文不缺信息。")
    if s_func < 6:
        r.advice.append("段落被过渡句占满：删掉段首段尾的连接词，让事实自己接上。")
    if s_life < 4:
        r.advice.append("缺生活痕迹：不用加语气词，补一个具体时刻、地点或一句原话，人味就回来了。")
    if s_concrete < 2:
        r.advice.append("具体信息太少：加一个能被核对的数量、价格、日期或专名，比加形容词有用。")

    if r.hard_fails:
        r.verdict = "需修（有硬伤）"
    elif r.total >= 80:
        r.verdict = "可发"
    elif r.total >= min_score:
        r.verdict = "可发（轻度打磨）"
    elif r.total >= 60:
        r.verdict = "需修"
    else:
        r.verdict = "建议重写"

    return r


def render_text(r):
    L = []
    L.append("=" * 46)
    L.append("朱笔 · 质量闸门报告")
    L.append("=" * 46)
    L.append(f"字数 {r.chars} ｜ 句数 {r.sentences} ｜ 段数 {r.paragraphs}")
    L.append(f"平均句长 {r.avg_sent_len} 字 ｜ 句长变异系数 {r.sent_len_cv}"
             f" ｜ 平均段长 {r.avg_para_len} 字")
    L.append(f"短句占比 {r.short_ratio:.0%} ｜ 长句(≥45字)占比 {r.long_ratio:.0%}")
    L.append("-" * 46)
    L.append("分项得分")
    for k, v in r.scores.items():
        L.append(f"  {k:<8} {v:>5} / {MAX_SCORES[k]}")
    L.append(f"  总分      {r.total:>5} / 100")
    L.append("-" * 46)
    L.append(f"结论：{r.verdict}")
    if r.hard_fails:
        L.append("硬伤：")
        for f in r.hard_fails:
            L.append(f"  ✗ {f}")
    if r.hits:
        L.append("命中位置（前 40 条）：")
        for h in r.hits[:40]:
            L.append(f"  · {h}")
    if r.advice:
        L.append("修改建议：")
        for a in r.advice:
            L.append(f"  → {a}")
    L.append("=" * 46)
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="公众号稿件量化体检")
    ap.add_argument("path", help="稿件文件路径，或 - 表示从标准输入读取")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--min-score", type=float, default=75, help="通过线，默认 75")
    args = ap.parse_args()

    try:
        if args.path == "-":
            raw = sys.stdin.read()
        else:
            with open(args.path, "r", encoding="utf-8") as f:
                raw = f.read()
    except OSError as e:
        print(f"读取失败：{e}", file=sys.stderr)
        sys.exit(2)

    try:
        r = analyze(raw, args.min_score)
    except ValueError as e:
        print(f"分析失败：{e}", file=sys.stderr)
        sys.exit(2)

    if args.json:
        print(json.dumps(asdict(r), ensure_ascii=False, indent=2))
    else:
        print(render_text(r))

    ok = (not r.hard_fails) and r.total >= args.min_score
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
