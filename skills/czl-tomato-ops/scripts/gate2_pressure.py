#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2026 虫志龙. All rights reserved.
"""首屏 200 字压强测试（关键词启发式，仅作辅助判断）。

用法：
    python gate2_pressure.py --file chapter1.txt
    python gate2_pressure.py --file chapter1.txt --chars 200 --json

注意：本脚本用关键词规则做初筛，不能替代人读。结论需人工复核。
"""
import argparse
import json
import sys

SIGNALS = {
    "异常": ["突然", "竟然", "居然", "不该", "死的", "血", "消失", "凭空", "醒了", "变了"],
    "冲突": ["滚", "住手", "闭嘴", "敢", "威胁", "动手", "拦住", "抢", "吵", "骂"],
    "缺口": ["为什么", "谁", "秘密", "不知道", "只有他", "那封信", "门后", "名单"],
    "危机": ["完了", "来不及", "撑不住", "最后", "只剩", "要死", "救", "逃", "崩塌"],
}
ATMOS = ["天气", "阳光", "微风", "云", "街道", "心情", "回忆", "风景", "夜色"]


def main():
    p = argparse.ArgumentParser(description="首屏 200 字压强测试")
    p.add_argument("--file", required=True, help="第一章正文文件")
    p.add_argument("--chars", type=int, default=200, help="取前 N 字，默认 200")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()

    try:
        with open(a.file, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print("读取失败：%s" % e, file=sys.stderr)
        return 2

    head = text[:a.chars]
    if not head.strip():
        print("文件为空或前 %d 字为空。" % a.chars, file=sys.stderr)
        return 2

    hits = {}
    for name, words in SIGNALS.items():
        c = sum(head.count(w) for w in words)
        if c:
            hits[name] = c
    atmos = sum(head.count(w) for w in ATMOS)

    strong = [k for k in ("异常", "冲突", "危机") if k in hits]
    mid = [k for k in ("缺口",) if k in hits]
    if strong:
        verdict = "达标"
    elif mid:
        verdict = "勉强"
    else:
        verdict = "不足"

    if a.json:
        print(json.dumps({
            "chars": len(head),
            "hits": hits, "atmosphere_hits": atmos,
            "verdict": verdict,
            "note": "关键词启发式初筛，需人工复核",
        }, ensure_ascii=False, indent=2))
        return 0

    print("首屏 %d 字压强测试" % len(head))
    print("-" * 34)
    if hits:
        for k, v in hits.items():
            print("命中 %-4s %d 处" % (k, v))
    else:
        print("命中 无")
    print("氛围词      %d 处" % atmos)
    print("-" * 34)
    print("判定        %s" % verdict)
    if verdict == "不足":
        print("建议        把第 3 章才出现的异常提到第一段；删掉开头的环境描写")
    elif verdict == "勉强":
        print("建议        补一个明确的危机或冲突，别只靠悬念")
    else:
        print("建议        进 G2-02 检查第一章目标可见性")
    print()
    print("注：本脚本为关键词初筛，不构成最终判断。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
