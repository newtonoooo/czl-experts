#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q2 包装站：按七猫书名语法给书名打分。纯标准库，离线运行。

五种语法信号：关系冲突、身份反差、数字具体、悬念留白、事件后果。
分数只说明"信息装进去了没有"，不判断好不好听。
"""

import argparse
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

RELATION = ["你", "我", "他", "她", "太太", "先生", "总", "爷", "夫人", "前夫", "前妻",
            "婚", "嫁", "娶", "宠", "追", "婆", "媳", "爸", "妈", "叔", "崽", "宝", "弟", "妹"]
LOW = ["小", "杂役", "保姆", "通房", "弃", "废", "奴", "小厮", "临时", "替身", "私生",
       "村", "厂", "摊", "送", "穷", "丑", "哑", "瘸", "假", "冒牌"]
HIGH = ["总", "爷", "首辅", "太子", "皇", "大佬", "战神", "首长", "京少", "豪门", "将军",
        "侯", "王", "帝", "国手", "神医", "首富", "状元", "厂长"]
SUSPENSE = ["？", "?", "！", "…", "却", "竟", "居然", "原来", "怎么", "为何", "谁", "不成想"]
EVENT = ["出狱", "入狱", "归来", "退婚", "离婚", "重生", "穿越", "开局", "签到", "下山",
         "出山", "娶", "嫁", "怀", "出马", "归隐", "被", "抢", "夺", "替嫁", "换嫁"]
RESULT = ["惊艳", "悔", "疯", "哭", "跪", "爆红", "翻身", "后悔", "傻眼", "失控", "白头",
          "认错", "求饶", "崩溃", "红了", "发了", "后悔了"]
NUM_RE = re.compile(r"(\d+|[一二三四五六七八九十百千万两]+)\s*(宝|个|年|次|胎|章|块|天|岁|万|亿|层|世|代|斤|亩)")

SIGNALS = ["关系冲突", "身份反差", "数字具体", "悬念留白", "事件动作"]


def clean(t):
    return re.sub(r"\s+", "", t)


def analyse(title):
    t = clean(title)
    n = len(t)
    marks = {}
    marks["关系冲突"] = [w for w in RELATION if w in t]
    low_hit = [w for w in LOW if w in t]
    high_hit = [w for w in HIGH if w in t]
    marks["身份反差"] = (low_hit + high_hit) if (low_hit and high_hit) else []
    marks["数字具体"] = ["".join(x) for x in NUM_RE.findall(t)]
    marks["悬念留白"] = [w for w in SUSPENSE if w in t]
    event_hit = [w for w in EVENT if w in t]
    if "后" in t or "之后" in t:
        event_hit += [w for w in RESULT if w in t]
    if not event_hit and ("，" in t or "," in t):
        event_hit = ["二段式"]
    marks["事件动作"] = event_hit

    score = sum(1 for k in SIGNALS if marks[k])
    notes = []
    if n < 8:
        notes.append("太短，信息装不下")
        score = max(0, score - 1)
    elif n < 12:
        notes.append("偏短，可以再加一个身份或数字")
    elif n <= 26:
        pass
    else:
        notes.append("超过 26 字，手机列表页会截断")
        score = max(0, score - 1)

    missing = [k for k in SIGNALS if not marks[k]]
    if len(missing) == len(SIGNALS):
        notes.append("五种语法一个都没用上")
    return n, marks, score, notes, missing


def main():
    ap = argparse.ArgumentParser(description="Q2 七猫书名体检：五类语法命中与字数")
    ap.add_argument("--titles", nargs="+", required=True, help="待评书名，空格分隔")
    args = ap.parse_args()

    print("=" * 68)
    print("Q2 包装站 · 书名语法体检")
    print("=" * 68)
    rows = []
    for title in args.titles:
        n, marks, score, notes, missing = analyse(title)
        rows.append((score, n, title, marks, notes, missing))
        print()
        print("书名：%s" % title)
        print("  字数：%d    命中：%d/5" % (n, score))
        for k in SIGNALS:
            v = marks[k]
            print("  %-6s %s" % (k, "、".join(v) if v else "无"))
        if notes:
            print("  备注：%s" % "；".join(notes))
        if missing:
            print("  可补：%s" % "、".join(missing))

    rows.sort(key=lambda r: (-r[0], r[1]))
    print()
    print("-" * 68)
    print("排序：")
    for i, (score, n, title, marks, notes, missing) in enumerate(rows, 1):
        level = "较好" if score >= 3 else ("可用" if score >= 2 else "偏弱")
        print("  %d. [%d/5 %s %d字] %s" % (i, score, level, n, title))

    print()
    print("[判读] 命中 3 条以上较好，2 条可用，1 条以下基本没把信息装进去。")
    print("       七猫在榜书名多在 8-22 字，长句不等于好句，装进冲突才算数。")
    print("[合规] 与在榜书重名或高度近似必须换，这是硬性风险，不看分数。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
