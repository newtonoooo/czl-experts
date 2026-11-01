#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dy_lint.py — 抖音内容合规自查（发布前最后一道闸）

归属：czl-douyin-growth-ops / skills/dy-compliance-lint
作者：虫志龙 <47190078@qq.com>

定位
----
不做法律判断，只做**机械扫描 + 替换建议**。把"这句话能不能说"从
凭手感变成可复核的清单，剩下的判断交给人。

做什么
------
1. 按自建词表扫描：绝对化用语、疗效承诺、收益承诺、未成年人、诱导互动、
   站外导流、封建迷信七类；
2. 命中项给等级（高/中/低）、依据、替换建议；
3. 自动识别强监管类目（医疗、保健、美妆、金融、教育、未成年人），提示需资质；
4. 给出可直接复制的改后文本。

用法
----
    python dy_lint.py --demo
    python dy_lint.py --file script.txt
    python dy_lint.py --text "全网最低价，加微信领取"
    python dy_lint.py --file script.txt --format json --min-level 高
"""

import argparse
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

VERSION = "1.0.0"
DEFAULT_WORDS = Path(__file__).resolve().parent.parent / "references" / "banned-words.json"

LEVEL_RANK = {"高": 3, "中": 2, "低": 1}


def load_words(path):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"词表不存在：{path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def mask_exceptions(text, exceptions):
    """把豁免短语替换成等长占位符，保证位置索引不变。"""
    masked = text
    for ph in exceptions:
        if not ph:
            continue
        idx = 0
        while True:
            i = masked.find(ph, idx)
            if i < 0:
                break
            masked = masked[:i] + ("□" * len(ph)) + masked[i + len(ph):]
            idx = i + len(ph)
    return masked


def scan(text, words, min_level="低"):
    hits = []
    cat_meta = {}
    threshold = LEVEL_RANK.get(min_level, 1)

    for cat in words.get("categories", []):
        cat_meta[cat["id"]] = cat
        masked = mask_exceptions(text, cat.get("except", []))
        raw = []
        for item in cat.get("items", []):
            term = item["term"]
            level = item.get("level") or cat.get("level", "中")
            if LEVEL_RANK.get(level, 1) < threshold:
                continue
            start = 0
            while True:
                i = masked.find(term, start)
                if i < 0:
                    break
                raw.append({
                    "term": term,
                    "start": i,
                    "end": i + len(term),
                    "level": level,
                    "category": cat["name"],
                    "category_id": cat["id"],
                    "basis": cat.get("basis", ""),
                    "replacement": item.get("replacement", ""),
                })
                start = i + len(term)

        # 同一位置多个命中（如「加微信」与「微信」）只保留更长的那个
        raw.sort(key=lambda h: (h["start"], -(h["end"] - h["start"])))
        kept = []
        for h in raw:
            if any(not (h["end"] <= k["start"] or h["start"] >= k["end"]) for k in kept):
                continue
            kept.append(h)
        hits.extend(kept)

    # 跨类目的重叠去重：等级高者优先，其次长者优先，最后靠前者优先。
    # 例如「全网最低价」会同时命中「全网最低」和「最低价」，只能留一条，
    # 否则改后稿会留下「价」这种断尾。
    hits.sort(key=lambda h: (-LEVEL_RANK.get(h["level"], 0), -(h["end"] - h["start"]), h["start"]))
    final = []
    for h in hits:
        if any(not (h["end"] <= k["start"] or h["start"] >= k["end"]) for k in final):
            continue
        final.append(h)
    hits = sorted(final, key=lambda h: h["start"])
    for h in hits:
        h["line"] = text.count("\n", 0, h["start"]) + 1
    return hits


def detect_categories(text, words):
    found = []
    for name, kws in (words.get("category_trigger") or {}).items():
        matched = [k for k in kws if k in text]
        if matched:
            found.append({"name": name, "matched": matched})
    return found


def build_clean_text(text, hits):
    out, cursor = [], 0
    for h in hits:
        if h["start"] < cursor:
            continue
        out.append(text[cursor:h["start"]])
        repl = h.get("replacement", "")
        if repl.startswith("（删除"):
            out.append("")
        else:
            out.append(repl)
        cursor = h["end"]
    out.append(text[cursor:])
    return "".join(out)


def analyze(text, words, min_level="低"):
    if not text or not text.strip():
        raise ValueError("待检文本为空")
    hits = scan(text, words, min_level)

    counts = {"高": 0, "中": 0, "低": 0}
    for h in hits:
        counts[h["level"]] = counts.get(h["level"], 0) + 1

    if counts["高"]:
        verdict = "不可发布：先改掉全部高等级项"
    elif counts["中"]:
        verdict = "建议修改后再发：中等级项容易被限流或投诉"
    elif counts["低"]:
        verdict = "基本可发：低等级项留意即可"
    else:
        verdict = "未命中词表：可发（词表不覆盖全部规则，仍需人工过一遍）"

    return {
        "version": VERSION,
        "chars": len(text.strip()),
        "verdict": verdict,
        "counts": counts,
        "hits": hits,
        "categories": detect_categories(text, words),
        "clean_text": build_clean_text(text, hits) if hits else text,
        "disclaimer": words.get("disclaimer", ""),
    }


CN_NUM = ["一", "二", "三", "四", "五", "六", "七", "八"]


def render_md(rep):
    lines = []
    n = 0

    def sec(title):
        nonlocal n
        lines.append(f"## {CN_NUM[n]}、{title}")
        lines.append("")
        n += 1

    lines.append("# 合规自查报告")
    lines.append("")

    sec("结论")
    lines.append(f"**{rep['verdict']}**")
    lines.append("")
    lines.append(f"扫描字数 {rep['chars']}｜命中 高 {rep['counts']['高']} 处 / "
                 f"中 {rep['counts']['中']} 处 / 低 {rep['counts']['低']} 处")
    lines.append("")

    if rep["categories"]:
        sec("强监管类目提示")
        for c in rep["categories"]:
            lines.append(f"- **{c['name']}**（命中词：{'、'.join(c['matched'])}）：这类内容对资质和表述要求更严，成稿前建议由具备资质的主体或法务复核。")
        lines.append("")

    sec("命中明细")
    if rep["hits"]:
        lines.append("| # | 等级 | 类目 | 原文 | 建议改为 | 位置 |")
        lines.append("|---|---|---|---|---|---|")
        for i, h in enumerate(rep["hits"], 1):
            repl = h["replacement"] or "—"
            lines.append(f"| {i} | {h['level']} | {h['category']} | {h['term']} | {repl} | 第 {h['line']} 行 |")
        lines.append("")

        sec("可直接替换的改后稿")
        lines.append("```text")
        lines.append(rep["clean_text"])
        lines.append("```")
        lines.append("")
    else:
        lines.append("无命中。")
        lines.append("")

    sec("依据与边界")
    lines.append(f"- {rep['disclaimer']}")
    lines.append("- 词表是机械匹配，会漏、也会误伤。出现误伤时把词加进对应类目的 `except` 数组即可。")
    lines.append("- 上面的「改后稿」是逐条替换的结果，删词后可能留下不通顺的句子，交稿前必须人工顺一遍语序。")
    return "\n".join(lines)


DEMO_TEXT = (
    "这款保温杯是我们今年最好的产品，全网最低价，医用级不锈钢，"
    "喝热水能养胃，坚持用还能调理身体。最后3件，点赞过万我明天再放一批。"
    "想要的加微信，我私下给你留货。"
)


def main():
    ap = argparse.ArgumentParser(description="抖音内容合规自查")
    ap.add_argument("--file", help="待检文本文件（.txt/.md）")
    ap.add_argument("--text", help="直接传入待检文本")
    ap.add_argument("--words", default=str(DEFAULT_WORDS), help="自定义词表 JSON 路径")
    ap.add_argument("--min-level", choices=("高", "中", "低"), default="低")
    ap.add_argument("--format", choices=("md", "json"), default="md")
    ap.add_argument("--out", help="输出文件路径")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--version", action="version", version=f"dy_lint {VERSION}")
    args = ap.parse_args()

    if args.demo:
        text = DEMO_TEXT
    elif args.text:
        text = args.text
    elif args.file:
        path = Path(args.file)
        if not path.exists():
            print(f"错误：找不到文件 {path}", file=sys.stderr)
            return 2
        text = path.read_text(encoding="utf-8-sig")
    else:
        ap.print_help()
        return 2

    try:
        words = load_words(args.words)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"词表加载失败：{exc}", file=sys.stderr)
        return 2

    try:
        rep = analyze(text, words, args.min_level)
    except ValueError as exc:
        print(f"输入有误：{exc}", file=sys.stderr)
        return 2

    out = render_md(rep) if args.format == "md" else json.dumps(rep, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"已写入 {args.out}")
    else:
        print(out)

    # 有高等级命中时用非零退出码，方便串进自动化流程做"不过不给发"
    return 1 if rep["counts"]["高"] else 0


if __name__ == "__main__":
    sys.exit(main())
