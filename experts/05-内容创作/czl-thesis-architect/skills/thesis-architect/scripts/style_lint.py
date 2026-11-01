#!/usr/bin/env python3
"""语言体检：套话密度、长句、连续短句、连接词连用、段首雷同、被动比例、高频重复词。

用法：
    python style_lint.py 正文.md
    python style_lint.py 正文.md --json

退出码：0 正常；1 有严重问题；2 参数或文件错误。
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import Issue, count_cjk, finish, read_text, setup_stdout, split_paragraphs, split_sentences  # noqa: E402

FORMULAIC_ZH = [
    (r"随着[^。；\n]{0,20}的(?:不断)?发展", "万能开头"),
    (r"在当今社会", "万能开头"),
    (r"近年来[，,][^。\n]{0,12}(?:越来越|日益)", "无据的'越来越'"),
    (r"具有(?:重要|深远)的(?:理论|现实|实践)意义", "空意义"),
    (r"起到了?[^。\n]{0,6}(?:积极|重要|推动)作用", "空转动词"),
    (r"奠定了[^。\n]{0,8}基础", "空话"),
    (r"综上所述", "套话收束"),
    (r"总而言之", "套话收束"),
    (r"众所周知", "无信息"),
    (r"值得注意的是", "无信息"),
    (r"在一定程度上", "模糊限定"),
    (r"不仅[^。\n]{0,40}而且", "排比掩盖"),
    (r"提供了[^。\n]{0,8}参考", "空话"),
    (r"有待(?:进一步|深入)", "套话收尾"),
    (r"越来越多的", "无据"),
    (r"引起了?广泛的?关注", "无信息"),
    (r"是不可忽视的", "空评价"),
    (r"具有不可替代的作用", "空评价"),
    (r"进行了?(?:深入的?)?(?:分析|研究|探讨)", "动词名词化"),
    (r"此问题需要引起.{0,4}高度重视", "呼吁腔"),
]
FORMULAIC_EN = [
    (r"It is worth noting that", "空转开头"),
    (r"With the (?:continuous )?development of", "万能开头"),
    (r"plays? an important role in", "空转动词"),
    (r"more and more", "无据"),
    (r"obviously|clearly|of course", "过度断言"),
    (r"in a certain extent", "错误搭配"),
    (r"further research is needed", "套话收尾"),
    (r"very important", "口语化强调"),
]
CONNECTIVES_ZH = ["首先", "其次", "再次", "最后", "另外", "此外"]
PASSIVE_EN = re.compile(r"\b(?:is|are|was|were|be|been|being)\s+[a-z]+ed\b", re.IGNORECASE)
EN_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
LISTLIKE_RE = re.compile(r"关键词|Keywords?|^\||^#")


def _is_listlike(sentence: str) -> bool:
    """关键词行、表格行、标题行不参与"连续短句"判定。"""
    return bool(LISTLIKE_RE.search(sentence)) or len(sentence) <= 4
STOPWORDS = {"的", "了", "是", "在", "和", "与", "也", "就", "都", "而", "及", "对", "为", "有", "不", "这", "那", "中", "上", "下"}


def lint(text: str, long_threshold=60, short_threshold=12):
    issues: list[Issue] = []
    sentences = split_sentences(text)
    lens = [max(count_cjk(s), len(s.split())) for s in sentences]
    paragraphs = split_paragraphs(text)

    long_ratio = (sum(1 for n in lens if n >= long_threshold) / len(lens)) if lens else 0
    avg_len = (sum(lens) / len(lens)) if lens else 0

    hits = []
    for pat, label in FORMULAIC_ZH + FORMULAIC_EN:
        for m in re.finditer(pat, text):
            line = text[: m.start()].count("\n") + 1
            hits.append((line, m.group(0)[:24], label))
    total = count_cjk(text) + len(re.findall(r"[A-Za-z][A-Za-z'\-]*", text))
    density = len(hits) / (total / 1000) if total else 0

    # 连续短句（跳过关键词行、表格行、标题行）
    runs, run = [], []
    for s, n in zip(sentences, lens):
        if n and n < short_threshold and not _is_listlike(s):
            run.append(s)
        else:
            if len(run) >= 4:
                runs.append(list(run))
            run = []
    if len(run) >= 4:
        runs.append(run)

    # 连接词连用（同一段出现 3 个以上序列词）
    connective_para = []
    for line_no, para in paragraphs:
        found = [w for w in CONNECTIVES_ZH if w in para]
        if len(found) >= 3:
            connective_para.append((line_no, found))

    # 段首雷同（连续三段以同两字开头）
    same_start = []
    heads = [p[:2] for _, p in paragraphs if p and not p.startswith("#")]
    for i in range(len(heads) - 2):
        if heads[i] and heads[i] == heads[i + 1] == heads[i + 2]:
            same_start.append(heads[i])

    # 高频重复词（中文二字词，排除停用词）
    cjk_only = "".join(re.findall(r"[\u4e00-\u9fff]", text))
    bigrams = Counter(cjk_only[i:i + 2] for i in range(len(cjk_only) - 1))
    repeated = [(w, c) for w, c in bigrams.most_common(30) if c >= 10 and w not in STOPWORDS][:5]

    # 英文被动比例（英文按句号切句，中文句号切分不适用于英文）
    en_sentences = [s for s in EN_SENT_SPLIT.split(text) if len(re.findall(r"[A-Za-z]{3,}", s)) >= 3]
    passive_ratio = (
        sum(1 for s in en_sentences if PASSIVE_EN.search(s)) / len(en_sentences) if en_sentences else 0
    )

    metrics = {
        "sentences": len(sentences),
        "avg_sentence_len": round(avg_len, 1),
        "long_sentence_ratio": round(long_ratio, 3),
        "formulaic_hits": len(hits),
        "formulaic_per_1000": round(density, 2),
        "short_runs": len(runs),
        "connective_paragraphs": len(connective_para),
        "passive_ratio": round(passive_ratio, 3),
        "repeated_words": repeated,
    }

    if long_ratio > 0.25 and len(lens) >= 20:
        issues.append(
            Issue(
                "SL001",
                "MINOR",
                f"{long_threshold} 字以上长句占 {long_ratio * 100:.0f}%（阈值 25%）",
                hint="长句多为多论点叠加，拆成两句：一句判断、一句说明。",
            )
        )

    if runs:
        sample = " / ".join(runs[0])[:60]
        issues.append(
            Issue(
                "SL002",
                "MINOR",
                f"出现 {len(runs)} 处连续四个以上短句（示例：{sample}）",
                hint="连排短句读起来像口号，把其中两三句合成一句带从句的长句。",
            )
        )

    if total >= 300 and len(hits) >= 4 and density >= 2.0:
        sample = "；".join(f"第{ln}行「{txt}」" for ln, txt, _ in hits[:5])
        issues.append(
            Issue(
                "SL003",
                "MAJOR" if density >= 5 else "MINOR",
                f"套话/空转表达 {len(hits)} 处（{metrics['formulaic_per_1000']}/千字，阈值 2.0）",
                location=f"第{hits[0][0]}行",
                hint=f"命中：{sample}。逐句换成带数据或机制的具体表述。",
            )
        )

    if connective_para:
        ln, found = connective_para[0]
        issues.append(
            Issue(
                "SL004",
                "MINOR",
                f"{len(connective_para)} 个段落连用三个以上序列连接词（如 {'、'.join(found)}）",
                location=f"第{ln}行",
                hint="改成实质过渡：用内容衔接，而不是'首先/其次/最后'。",
            )
        )

    if len(same_start) >= 2:
        issues.append(
            Issue(
                "SL005",
                "MINOR",
                f"连续三段以「{same_start[0]}」开头（共 {len(same_start)} 处）",
                hint="段首雷同说明段落不是按论证推进，而是按同一种句式排下去。",
            )
        )

    if passive_ratio > 0.5 and len(en_sentences) >= 15:
        issues.append(
            Issue(
                "SL006",
                "MINOR",
                f"英文句被动语态占 {passive_ratio * 100:.0f}%",
                hint="方法与结果以外的内容优先用主动语态，句子更短更有力。",
            )
        )

    if repeated and repeated[0][1] >= 15:
        words = "、".join(f"{w}（{c} 次）" for w, c in repeated[:3])
        issues.append(
            Issue("SL007", "MINOR", f"高频重复词：{words}", hint="同义替换或改写句子结构，避免同一词反复出现。")
        )

    return metrics, issues


def main(argv=None) -> int:
    setup_stdout()
    parser = argparse.ArgumentParser(description="语言体检")
    parser.add_argument("file")
    parser.add_argument("--long", type=int, default=60, help="长句阈值（字）")
    parser.add_argument("--short", type=int, default=12, help="短句阈值（字）")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    path = Path(args.file)
    if not path.exists():
        print(f"文件不存在：{path}", file=sys.stderr)
        return 2

    metrics, issues = lint(read_text(path), args.long, args.short)
    human = [
        f"文件：{path.name}",
        f"句子：{metrics['sentences']} 句，平均 {metrics['avg_sentence_len']} 字，"
        f"长句占 {metrics['long_sentence_ratio'] * 100:.0f}%",
        f"套话/空转：{metrics['formulaic_hits']} 处（{metrics['formulaic_per_1000']}/千字）",
        f"连续短句：{metrics['short_runs']} 处｜连接词连用段：{metrics['connective_paragraphs']} 处｜"
        f"英文被动：{metrics['passive_ratio'] * 100:.0f}%",
    ]
    return finish("style_lint", metrics, issues, human, args.json)


if __name__ == "__main__":
    sys.exit(main())
