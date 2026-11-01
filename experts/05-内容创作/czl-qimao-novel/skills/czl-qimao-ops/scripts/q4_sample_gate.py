#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q4 样章站：七猫投稿样章压强体检。纯标准库，离线运行。"""

import argparse
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

CHAPTER_RE = re.compile(r"^\s*(第\s*[0-9一二三四五六七八九十百千零两]+\s*章[^\n]*)$", re.M)
PERSON = ["他", "她", "我", "你", "妈", "爸", "爷", "奶", "姐", "哥", "总", "先生", "太太"]
ACTION = ["说", "问", "喊", "叫", "走", "跑", "推", "拉", "抓", "摔", "砸", "签", "递",
          "打", "踢", "跪", "看", "盯", "笑", "哭", "拿", "抢", "退", "赶", "拦"]
TROUBLE = ["却", "突然", "竟然", "居然", "不对", "不该", "不能", "死", "血", "离婚", "协议",
           "欠", "债", "退婚", "休", "滚", "滚出", "冒充", "顶替", "背叛", "骗", "错", "丢"]
HOOK = ["？", "?", "！", "…", "却", "但", "忽然", "突然", "猛地", "抬头", "竟然", "原来",
        "发现", "知道", "新", "第一次", "没有", "空", "少", "缺", "停", "响", "抖",
        "冷", "笑", "声音", "脚步", "影子", "血", "名单", "照片", "系统", "短信", "电话", "门"]
PAYOFF = ["打脸", "反击", "跪", "道歉", "认输", "傻眼", "脸色", "成交", "签下", "翻身",
          "逆转", "求饶", "后悔", "红了"]


def read_text(path):
    for enc in ("utf-8", "utf-8-sig", "gbk"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    raise SystemExit("[错误] 文件编码无法识别，请另存为 UTF-8。")


def gather(args):
    if args.file:
        if not os.path.exists(args.file):
            print("[错误] 文件不存在：%s" % args.file)
            sys.exit(2)
        return read_text(args.file)
    if args.dir:
        if not os.path.isdir(args.dir):
            print("[错误] 目录不存在：%s" % args.dir)
            sys.exit(2)
        parts = []
        for name in sorted(os.listdir(args.dir)):
            if name.lower().endswith((".md", ".txt")):
                parts.append(read_text(os.path.join(args.dir, name)))
        if not parts:
            print("[错误] 目录里没有 .md / .txt 文件。")
            sys.exit(2)
        return "\n\n".join(parts)
    print("[错误] 需要 --file 或 --dir。")
    sys.exit(2)


def split_chapters(text):
    marks = list(CHAPTER_RE.finditer(text))
    if not marks:
        return [("未识别章标题", text)]
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out.append((m.group(1).strip(), text[m.end():end]))
    return out


def strip_ws(s):
    return re.sub(r"\s", "", s)


def sentences(text):
    return [s for s in re.split(r"[。！？!?；;\n]+", text) if strip_ws(s)]


def main():
    ap = argparse.ArgumentParser(description="Q4 七猫样章体检：首 200 字压强 / 句长 / 对话 / 钩子")
    ap.add_argument("--file", help="单文件（可含多章）")
    ap.add_argument("--dir", help="章节目录，按文件名排序合并")
    args = ap.parse_args()

    text = gather(args)
    chapters = split_chapters(text)
    total = len(strip_ws(text))

    print("=" * 66)
    print("Q4 样章站 · 投稿样章体检")
    print("=" * 66)
    print("识别章节：%d    总字数：%d" % (len(chapters), total))
    print("投稿底线：两万字左右，前三章完整。")
    print()

    # 首 200 字
    head = strip_ws(chapters[0][1] if chapters[0][1] else text)[:200]
    has_person = [w for w in PERSON if w in head]
    has_action = [w for w in ACTION if w in head]
    has_trouble = [w for w in TROUBLE if w in head]
    has_specific = sorted(set(re.findall(r"\d+|[一二三四五六七八九十百千万两]+", head)),
                          key=lambda s: -len(s))[:6]

    print("-" * 66)
    print("前 200 字压强")
    print("-" * 66)
    print("  原文：%s%s" % (head[:120], "……" if len(head) > 120 else ""))
    rows = [
        ("有人", has_person),
        ("有事", has_action),
        ("有不对劲", has_trouble),
        ("有具体物/数字", has_specific),
    ]
    miss = []
    for name, hit in rows:
        mark = "OK  " if hit else "缺失"
        if not hit:
            miss.append(name)
        print("  [%s] %-10s %s" % (mark, name, "、".join(hit[:5]) if hit else ""))

    # 句子
    sents = sentences(text)
    lens = [len(strip_ws(s)) for s in sents] or [0]
    long_sents = [n for n in lens if n > 45]
    avg = sum(lens) / max(1, len(lens))
    dia = sum(len(strip_ws(m)) for m in re.findall(r"[“\"]([^”\"]*)[”\"]", text))
    dia_ratio = dia / max(1, total)

    print()
    print("-" * 66)
    print("文本指标")
    print("-" * 66)
    print("  平均句长：%.1f 字    超长句（>45 字）：%d 句" % (avg, len(long_sents)))
    print("  对话占比：%.1f%%（七猫读者习惯短段对话，低于 15%% 要留意）" % (dia_ratio * 100))

    print()
    print("-" * 66)
    print("章末钩子")
    print("-" * 66)
    hook_ok = 0
    for i, (title, body) in enumerate(chapters[:8], 1):
        tail = strip_ws(body)[-80:]
        hit = [w for w in HOOK if w in tail]
        if hit:
            hook_ok += 1
        print("  %s  %s  %s" % ("钩" if hit else "平", title[:24],
                                "、".join(hit[:3]) if hit else "章末没有留问题也没有留动作"))

    payoffs = [w for w in PAYOFF if w in text]
    print()
    print("-" * 66)
    print("爽点兑现信号")
    print("-" * 66)
    print("  命中：%s" % ("、".join(payoffs[:8]) if payoffs else "无"))
    print("  要求：第一次兑现必须在样章内，最晚不超过第 5 章。")

    print()
    problems = []
    if total < 18000:
        problems.append("样章只有 %d 字，不够两万，编辑不会当完整投稿包看" % total)
    if miss:
        problems.append("前 200 字缺：%s" % "、".join(miss))
    if len(chapters) < 3:
        problems.append("只识别到 %d 章，投稿要前三章" % len(chapters))
    if not payoffs:
        problems.append("全文没有爽点兑现信号，读者没有留下来的理由")
    if hook_ok == 0:
        problems.append("章末全部没有钩子")
    if avg > 32:
        problems.append("平均句长 %.1f 字，手机阅读会累" % avg)
    if dia_ratio < 0.12:
        problems.append("对话占比 %.1f%%，偏低，叙事容易变成说明书" % (dia_ratio * 100))

    if problems:
        print("[判定] 返工")
        for p in problems:
            print("  - %s" % p)
        if miss:
            print("[动作] 只改开头 200 字，别动后面。开头改完重跑一次。")
    else:
        print("[判定] 放行")
        print("[依据] 字数、首 200 字四项、章末钩子、爽点兑现均达标。")
        print("[下一站进入条件] 进 Q5 上架站，先确认分类与标签。")

    print()
    print("[口径] 本脚本测结构与密度，不评价文笔。数值达标但读起来没劲的，仍然要重写。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
