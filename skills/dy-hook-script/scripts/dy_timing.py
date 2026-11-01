#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dy_timing.py — 口播稿时长核算与钩子落点检查

归属：czl-douyin-growth-ops / skills/dy-hook-script
作者：虫志龙 <47190078@qq.com>

解决的问题
----------
写脚本的人习惯凭感觉写"30 秒左右"，实际念出来 47 秒，导致：
1. 完播被时长拖死；2. 钩子没落在前 3 秒；3. 拍摄时临时砍词，结构崩掉。

本工具做三件事：
1. 按语速把稿子切成真实时间轴，给每一句起止秒数；
2. 检查钩子是否在 3 秒内落地，并用 5 项信号给出钩子强度分；
3. 与目标时长比对，给出"要砍多少字"的具体数字。

用法
----
    python dy_timing.py --demo
    python dy_timing.py --file script.txt --rate 270 --target 45
    python dy_timing.py --file script.json --format json
"""

import argparse
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

VERSION = "1.0.0"

# 中断符与对应停顿（秒）。口播里逗号的停顿是真实存在的，不能只按字数算。
PAUSES = {
    "。": 0.45, "！": 0.45, "？": 0.45, ".": 0.45, "!": 0.45, "?": 0.45,
    "；": 0.30, ";": 0.30, "…": 0.30,
    "，": 0.20, ",": 0.20, "、": 0.15, "：": 0.20, ":": 0.20,
    "\n": 0.30,
}
SENTENCE_END = "。！？!?；;…\n"

RATE_MIN, RATE_MAX = 180, 340   # 中文口播常见区间（字/分钟）
HOOK_WINDOW = 3.0               # 钩子必须在 3 秒内落地


def split_sentences(text):
    """按句末标点切句，保留标点用于算停顿。"""
    text = text.replace("\r\n", "\n").strip()
    parts, buf = [], ""
    for ch in text:
        buf += ch
        if ch in SENTENCE_END:
            if buf.strip():
                parts.append(buf.strip())
            buf = ""
    if buf.strip():
        parts.append(buf.strip())
    return parts


def count_chars(sentence):
    """只数要念出来的字，标点、空白不计入语速。"""
    return len(re.sub(r"[\s，。！？；：、…,.!?;:—\-—\"'“”‘’()（）\[\]【】]", "", sentence))


def pause_of(sentence):
    total = 0.0
    for ch in sentence:
        total += PAUSES.get(ch, 0.0)
    # 最后一句也留一点收尾气口
    return total


def hook_signals(first):
    """钩子强度启发式评分：5 项信号，命中越多越强。"""
    signals = []
    if re.search(r"\d", first):
        signals.append("含具体数字")
    if re.search(r"[？?]", first):
        signals.append("提问句")
    if re.search(r"你|你们|咱|我们", first):
        signals.append("直接对人说话")
    if re.match(r"^(别|不要|千万别|为什么|凭什么|如果|有没有|是不是|我劝|说个)", first.strip()):
        signals.append("起手即冲突/劝阻")
    if count_chars(first) <= 25:
        signals.append("首句够短")
    score = len(signals)
    level = "强" if score >= 4 else ("中" if score >= 2 else "弱")
    return signals, score, level


def build_timeline(segments, rate):
    """segments: [{'text':..., 'shot':..., 'note':...}] -> 带时间轴的列表"""
    cps = rate / 60.0
    t = 0.0
    rows = []
    for seg in segments:
        text = seg["text"]
        chars = count_chars(text)
        speak = chars / cps if cps > 0 else 0
        dur = speak + pause_of(text)
        rows.append({
            "text": text,
            "shot": seg.get("shot", ""),
            "note": seg.get("note", ""),
            "chars": chars,
            "start": round(t, 2),
            "end": round(t + dur, 2),
            "dur": round(dur, 2),
        })
        t += dur
    return rows, round(t, 2)


def analyze(text_or_segments, rate=270, target=None):
    if isinstance(text_or_segments, str):
        segments = [{"text": s} for s in split_sentences(text_or_segments)]
    else:
        segments = text_or_segments
    if not segments:
        raise ValueError("稿子为空，没有可计算的句子")

    rows, total = build_timeline(segments, rate)
    first = rows[0]
    signals, score, level = hook_signals(first["text"])

    warnings = []
    if first["end"] > HOOK_WINDOW:
        warnings.append(
            f"首句念完要 {first['end']} 秒，超过 {HOOK_WINDOW:g} 秒窗口，钩子来不及落地，砍到 20 字以内"
        )
    if level == "弱":
        warnings.append("钩子强度弱（命中信号不足 2 项），前 3 秒大概率被划走")
    if rate > RATE_MAX:
        warnings.append(f"语速 {rate} 字/分偏快，超过 {RATE_MAX}，听着像赶时间")
    if rate < RATE_MIN:
        warnings.append(f"语速 {rate} 字/分偏慢，低于 {RATE_MIN}，观众会先失去耐心")

    total_chars = sum(r["chars"] for r in rows)
    cut_hint = None
    if target:
        delta = total - target
        if abs(delta) / target > 0.15:
            cps = rate / 60.0
            cut_chars = int(abs(delta) * cps)
            if delta > 0:
                cut_hint = f"超出目标 {delta:.1f} 秒，约需删掉 {cut_chars} 个字（按 {rate} 字/分）"
            else:
                cut_hint = f"短于目标 {abs(delta):.1f} 秒，约需补 {cut_chars} 个字"
            warnings.append(cut_hint)

    return {
        "version": VERSION,
        "rate": rate,
        "target_sec": target,
        "total_sec": total,
        "total_chars": total_chars,
        "avg_cps": round(total_chars / total, 2) if total else 0,
        "hook": {
            "first_sentence": first["text"],
            "landed_at": first["end"],
            "landed": first["end"] <= HOOK_WINDOW,
            "signals": signals,
            "score": score,
            "level": level,
        },
        "rows": rows,
        "warnings": warnings,
    }


def fmt_tc(sec):
    m, s = divmod(sec, 60)
    return f"{int(m):02d}:{s:05.2f}"


def render_md(rep):
    lines = ["# 口播稿时间轴", ""]
    hook = rep["hook"]
    lines.append("## 一、先看两个数")
    lines.append("")
    lines.append(f"- 预计总时长：**{rep['total_sec']} 秒**（{rep['total_chars']} 字，语速 {rep['rate']} 字/分）")
    lines.append(f"- 钩子落点：**第 {hook['landed_at']} 秒念完首句**，"
                 f"{'在窗口内' if hook['landed'] else '已超出 3 秒窗口'}，强度 **{hook['level']}**")
    if hook["signals"]:
        lines.append(f"- 命中信号：{'、'.join(hook['signals'])}")
    lines.append("")

    if rep["warnings"]:
        lines.append("## 二、要改的地方")
        lines.append("")
        for w in rep["warnings"]:
            lines.append(f"- {w}")
        lines.append("")

    lines.append("## 三、逐句时间轴")
    lines.append("")
    lines.append("| # | 起 | 止 | 时长 | 字数 | 口播原文 | 画面/分镜 |")
    lines.append("|---|---|---|---|---|---|---|")
    for i, r in enumerate(rep["rows"], 1):
        text = r["text"].replace("|", "／")
        shot = (r["shot"] or "—").replace("|", "／")
        lines.append(f"| {i} | {fmt_tc(r['start'])} | {fmt_tc(r['end'])} | {r['dur']}s | {r['chars']} | {text} | {shot} |")
    lines.append("")
    lines.append("> 语速按 {0} 字/分估算，实际以你自己念一遍的秒表为准；误差通常在 ±10%。".format(rep["rate"]))
    return "\n".join(lines)


DEMO_TEXT = (
    "你是不是也这样：工资到账第三天，钱就没了。"
    "我月薪五千的时候，用三个账户把钱分开，两年存下第一个十万。"
    "第一个账户发工资当天自动转走两千，这笔钱不许动，也不许看。"
    "第二个账户只放固定开销，房租水电吃饭，花完就没了，超了就从别处省。"
    "第三个账户是乱花钱的，每月五百，爱怎么花怎么花。"
    "关键不是省，是让钱在你看见之前就已经不在了。"
    "你现在几个账户？评论区说个数，我看看谁跟我一样。"
)


def main():
    ap = argparse.ArgumentParser(description="口播稿时长核算与钩子落点检查")
    ap.add_argument("--file", help="稿件路径（.txt 纯文本，或 .json 含 segments 数组）")
    ap.add_argument("--rate", type=int, default=270, help="语速，字/分钟，默认 270")
    ap.add_argument("--target", type=float, help="目标时长（秒）")
    ap.add_argument("--format", choices=("md", "json"), default="md")
    ap.add_argument("--out", help="输出文件路径")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--version", action="version", version=f"dy_timing {VERSION}")
    args = ap.parse_args()

    if args.demo:
        payload = DEMO_TEXT
    elif args.file:
        path = Path(args.file)
        if not path.exists():
            print(f"错误：找不到稿件 {path}", file=sys.stderr)
            return 2
        raw = path.read_text(encoding="utf-8-sig")
        if path.suffix.lower() == ".json":
            try:
                obj = json.loads(raw)
                payload = obj.get("segments") if isinstance(obj, dict) else obj
                if not payload:
                    print("错误：JSON 里没有 segments 数组", file=sys.stderr)
                    return 2
            except json.JSONDecodeError as exc:
                print(f"错误：JSON 解析失败 {exc}", file=sys.stderr)
                return 2
        else:
            payload = raw
    else:
        ap.print_help()
        return 2

    try:
        rep = analyze(payload, rate=args.rate, target=args.target)
    except (ValueError, KeyError, TypeError) as exc:
        print(f"输入有误：{exc}", file=sys.stderr)
        return 2

    out = render_md(rep) if args.format == "md" else json.dumps(rep, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"已写入 {args.out}")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
