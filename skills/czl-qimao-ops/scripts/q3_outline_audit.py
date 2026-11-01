#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q3 结构站：七猫投稿大纲体检。纯标准库，离线运行。"""

import argparse
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

CHECKS = [
    ("结局方向", ["结局", "终局", "收尾", "最后他", "最后她", "大结局"]),
    ("核心冲突", ["冲突", "对手", "反派", "挡", "争夺", "复仇", "要什么"]),
    ("三幕结构", ["第一幕", "第二幕", "第三幕", "三幕", "起承转合"]),
    ("卷级节拍", ["第一卷", "卷二", "第2卷", "分卷", "卷末"]),
    ("伏笔表", ["伏笔", "埋", "回收"]),
    ("人物表", ["主角", "人物", "配角", "反派", "感情线"]),
    ("金手指规则", ["系统", "金手指", "能力", "规则", "限制", "代价"]),
    ("升级体系", ["等级", "境界", "阶", "体系", "战力"]),
]

WEAK_TURN = ["遇到更强", "更强的敌人", "更强的对手", "来了一个更强", "出现更强"]
REAL_TURN = ["失去", "代价", "失效", "反目", "背叛", "死", "误会", "失败", "崩塌", "被发现"]


def read_text(path):
    for enc in ("utf-8", "utf-8-sig", "gbk"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    raise SystemExit("[错误] 文件编码无法识别，请另存为 UTF-8。")


def count_volumes(text):
    names = set(re.findall(r"第([一二三四五六七八九十百0-9]+)卷", text))
    return len(names)


def count_hooks(text):
    """数伏笔条目。优先在“伏笔”小节里数编号条目，数不到再退回数“回收”出现次数。"""
    m = re.search(r"#+\s*伏笔[^\n]*\n(.*?)(?=\n#+\s|\Z)", text, re.S)
    if m:
        items = re.findall(r"^\s*\d+\s*[\.、)]", m.group(1), re.M)
        if items:
            return len(items)
        bullets = re.findall(r"^\s*[-*]\s+\S", m.group(1), re.M)
        if bullets:
            return len(bullets)
    return len(re.findall(r"回收", text))


def main():
    ap = argparse.ArgumentParser(description="Q3 七猫投稿大纲体检")
    ap.add_argument("--file", required=True, help="大纲 Markdown 或 txt 路径")
    ap.add_argument("--words", type=int, default=0, help="计划总字数，用于估章数与卷数")
    args = ap.parse_args()

    if not os.path.exists(args.file):
        print("[错误] 文件不存在：%s" % args.file)
        return 2
    text = read_text(args.file)
    body_len = len(re.sub(r"\s", "", text))

    print("=" * 66)
    print("Q3 结构站 · 大纲体检")
    print("=" * 66)
    print("文件：%s" % os.path.basename(args.file))
    print("正文规模：%d 字（不含空白）" % body_len)
    if args.words:
        print("计划总字数：%d    估算章数：%d 章（按 2500 字/章）"
              % (args.words, round(args.words / 2500)))
        print("估算卷数：%d 卷（按 20 万字/卷）" % max(1, round(args.words / 200000)))
    print()

    missing = []
    for name, keys in CHECKS:
        hit = [k for k in keys if k in text]
        status = "OK  " if hit else "缺失"
        if not hit:
            missing.append(name)
        print("  [%s] %-8s %s" % (status, name, ("命中：" + "、".join(hit[:4])) if hit else ""))

    vols = count_volumes(text)
    hooks = count_hooks(text)
    print()
    print("  卷数（识别）：%d" % vols)
    print("  伏笔提及次数：%d" % hooks)

    print()
    problems = []
    if "结局方向" in missing:
        problems.append("没写结局方向——编辑最怕故事写不完")
    if "三幕结构" in missing:
        problems.append("没有三幕，节奏没有骨架")
    if vols < 2 and args.words >= 400000:
        problems.append("计划 %d 字却只有 %d 卷，分卷节拍缺失" % (args.words, vols))
    if hooks < 8:
        problems.append("伏笔提及只有 %d 处，低于 8 条底线" % hooks)
    if "跨卷" not in text:
        problems.append("没有跨卷伏笔，长线会空")

    weak = [w for w in WEAK_TURN if w in text]
    strong = [w for w in REAL_TURN if w in text]
    if weak and len(strong) < 2:
        problems.append("第二幕转折疑似只有“难度升级”（命中：%s），不是结构转折" % "、".join(weak))

    if problems:
        print("[判定] 返工")
        print("[依据]")
        for p in problems:
            print("  - %s" % p)
        print("[动作] 按上面顺序改，先补结局方向，再改第二幕转折，最后补伏笔表。")
        print("[下一站进入条件] 结局方向 + 三幕 + 伏笔 >= 8 条且含跨卷，重过 Q3。")
    else:
        print("[判定] 放行")
        print("[依据] 八项结构要素齐全，卷级节拍与伏笔密度达标。")
        print("[下一站进入条件] 进 Q4 样章站，先写前三章。")

    print()
    print("[口径] 本脚本只测“有没有”，不测“好不好”。大纲能不能过编辑，还要看故事本身。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
