#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2026 虫志龙. All rights reserved.
"""章末钩子密度体检（规则初筛）。

读取整本稿件，按章切分，取每章最后一段做等级判定。
用法：
    python gate3_hook_audit.py --file draft.md
    python gate3_hook_audit.py --file draft.md --json

注意：等级判定基于关键词规则，属辅助工具，最终等级需人工复核。
"""
import argparse
import json
import re
import sys

CH_PAT = re.compile(r"^\s*(?:#{1,4}\s*)?第\s*[0-9一二三四五六七八九十百]+\s*章")

RULES = [
    (5, ["竟然", "原来", "其实是", "真正的", "居然是", "没想到", "反过来"]),
    (4, ["突然", "出现", "来人", "电话", "名单", "秘密", "出事了", "不见了", "死了"]),
    (3, ["拦住", "拒绝", "失败", "不行", "晚了", "来不及", "挡住"]),
    (2, ["叹了口气", "想起", "心里", "明白", "沉默", "看着", "摇了摇头"]),
    (1, ["睡了", "走了", "关上门", "回到家", "结束", "平静"]),
]


def split_chapters(text):
    lines = text.split("\n")
    chapters, cur, title = [], [], None
    for line in lines:
        if CH_PAT.match(line):
            if cur:
                chapters.append((title, "\n".join(cur).strip()))
            title, cur = line.strip(), []
        else:
            cur.append(line)
    if cur:
        chapters.append((title or "（未命名）", "\n".join(cur).strip()))
    return [(t, b) for t, b in chapters if b]


def last_para(body):
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    return paras[-1] if paras else ""


def rate(para):
    for level, words in RULES:
        if any(w in para for w in words):
            return level
    return 1


def main():
    p = argparse.ArgumentParser(description="章末钩子密度体检")
    p.add_argument("--file", required=True, help="整本或片段稿件路径")
    p.add_argument("--window", type=int, default=30, help="只看最近 N 章，默认 30")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()

    try:
        with open(a.file, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print("读取失败：%s" % e, file=sys.stderr)
        return 2

    chapters = split_chapters(text)
    if not chapters:
        print("未识别到章节（需形如「第一章」或「## 第1章」的标题行）。", file=sys.stderr)
        return 2

    chapters = chapters[-a.window:]
    levels = []
    for i, (title, body) in enumerate(chapters, 1):
        levels.append((i, title, rate(last_para(body))))

    total = len(levels)
    dist = {k: sum(1 for _, _, lv in levels if lv == k) for k in range(1, 6)}
    rate4 = (dist[4] + dist[5]) / total

    low_streak, run = [], 0
    for i, _, lv in levels:
        if lv <= 3:
            run += 1
        else:
            if run >= 3:
                low_streak.append((i - run, i - 1))
            run = 0
    if run >= 3:
        low_streak.append((total - run + 1, total))

    nohook = [i for i, _, lv in levels if lv == 1]

    if a.json:
        print(json.dumps({
            "chapters": total,
            "distribution": dist,
            "hit_rate_4plus": round(rate4, 3),
            "low_streak": low_streak,
            "no_hook": nohook,
            "note": "规则初筛，需人工复核",
        }, ensure_ascii=False, indent=2))
        return 0

    print("章末钩子密度体检（样本 %d 章）" % total)
    print("-" * 40)
    for k in range(5, 0, -1):
        print("%s %2d 章" % ("*" * k, dist[k]))
    print("-" * 40)
    print("达标率（>=4 星） %.0f%%" % (rate4 * 100))
    print("三连低位置       %s" % (str(low_streak) if low_streak else "无"))
    print("无钩章           %s" % (str(nohook) if nohook else "无"))
    print("-" * 40)
    if rate4 >= 0.5 and not low_streak and not nohook:
        print("判定  合格")
    else:
        print("判定  不合格")
        print("改法  只改不达标章的最后 3 行：把「结果」改成「代价」，把「解答」改成「半个解答」")
    print()
    print("注：本判定为关键词规则初筛，等级需按 G2-04 人工复核。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
