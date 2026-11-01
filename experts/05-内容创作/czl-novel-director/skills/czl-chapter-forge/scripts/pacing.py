#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pacing.py — 章级节奏、钩子强度与爽点密度（纯标准库，离线）

补的是"整本书好不好看"里唯一能算的那部分：
    每章一个张力估值、一个章末钩子星级、一个爽点密度，并列红线。

用法：
    python pacing.py chapters/            # 目录（按文件名排序，取 ch-*.md）
    python pacing.py chapters/ch-001.md chapters/ch-002.md
    python pacing.py chapters/ --json qc/pacing.json
    python pacing.py chapters/ --min-hook 3 --window 3

三条红线（可调）：
    H1 章末钩子 < 指定星级
    H2 连续 N 章爽点密度为 0
    H3 整章没有对话

**口径说明**：张力是启发式估算，不是文学评价。它衡量的是"这段文字的
事件密度、对话密度与句长起伏"，不等于"好看"。有数字只说明可比较，
不说明可当判决书。

作者：虫志龙 <47190078@qq.com>
许可：MIT
"""

import argparse
import json
import os
import re
import statistics
import sys

HANZI = re.compile(r"[\u4e00-\u9fff]")
SENT_RE = re.compile(r"[^。！？!?…\n]+[。！？!?…]+[」』”’）)]*|[^。！？!?…\n]+$")

CONFLICT = ["打", "杀", "撞", "摔", "夺", "逼", "挡", "拦", "撕", "砸", "抢",
            "骂", "吼", "质问", "威胁", "拒绝", "翻脸", "对峙", "追", "逃",
            "血", "伤", "痛", "死", "断", "裂", "塌", "炸", "火"]

TENSION = ["必须", "只能", "来不及", "倒计时", "最后一", "再也", "否则", "不然",
           "时间不多", "只剩", "期限", "来不及了", "现在就走", "马上"]

PAYOFF = ["终于", "果然", "原来", "却不知", "没想到", "反手", "一击", "翻盘",
          "逆转", "压制", "打脸", "拿下", "通过", "升级", "突破", "到手",
          "赢了", "赢了", "解开", "揭穿", "承认", "认输", "低头", "跪下"]

HOOK_SIGNAL = {
    "未完成动作": ["伸手", "抬手", "抬起", "正要", "刚要走", "迈出", "按下", "推开门"],
    "新信息": ["原来是", "名字是", "落款", "写着", "照片上", "名单", "备注", "最后一页"],
    "时间压力": ["三天", "今晚", "明天", "只剩", "倒计时", "来不及", "最后一"],
    "关系反转": ["不是", "并不是", "竟然是", "其实是", "真名", "身份", "马甲"],
    "威胁逼近": ["脚步", "敲门", "越来越近", "背后", "门外", "回头", "盯着"],
    "提问": ["？", "?"],
}


def hanzi(s):
    return len(HANZI.findall(s))


def sentences(p):
    out = []
    for s in SENT_RE.findall(p):
        s = s.strip()
        if s and (hanzi(s) or len(s) > 3):
            out.append(s)
    return out


def paragraphs(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    out = []
    for b in re.split(r"\n\s*\n", text):
        b = b.strip()
        if b and not b.startswith("#"):
            out.append(b)
    return out


def analyze_chapter(text, name):
    paras = paragraphs(text)
    total = hanzi(text)
    if total == 0:
        return None

    plens = [hanzi(p) for p in paras] or [0]
    dlg = [p for p in paras if re.search(r"[「“\"]", p)]
    dlg_ratio = len(dlg) / len(paras) if paras else 0

    sents = []
    for p in paras:
        sents.extend(sentences(p))
    slens = [hanzi(s) for s in sents if hanzi(s) > 0] or [0]
    cv = (statistics.pstdev(slens) / statistics.fmean(slens)) if len(slens) > 3 and statistics.fmean(slens) else 0

    def density(words):
        return sum(text.count(w) for w in words) * 1000.0 / total

    conflict = min(density(CONFLICT), 40) / 40.0
    tension_w = min(density(TENSION), 12) / 12.0
    payoff_n = sum(text.count(w) for w in PAYOFF)
    payoff_d = payoff_n * 1000.0 / total

    # 段长起伏：相邻段长变化的中位数 / 平均段长，越高越不平
    if len(plens) > 2:
        jumps = [abs(plens[i] - plens[i - 1]) for i in range(1, len(plens))]
        wave = statistics.median(jumps) / max(1, statistics.fmean(plens))
    else:
        wave = 0
    wave = min(wave, 1.0)

    # 张力估值 0—100：冲突 40 + 时间压力 20 + 对话 20 + 段长起伏 10 + 句长参差 10
    score = (conflict * 40 + tension_w * 20 + min(dlg_ratio / 0.45, 1) * 20
             + wave * 10 + min(cv / 0.75, 1) * 10)

    # 章末钩子：取最后 200 个汉字
    tail = text[-400:]
    hits = {}
    for kind, words in HOOK_SIGNAL.items():
        c = sum(tail.count(w) for w in words)
        if c:
            hits[kind] = c
    hook_n = sum(hits.values())
    if hook_n == 0:
        stars = 1
    elif hook_n == 1:
        stars = 2
    elif hook_n == 2:
        stars = 3
    elif hook_n <= 4:
        stars = 4
    else:
        stars = 5

    return {
        "chapter": name,
        "hanzi": total,
        "paragraphs": len(paras),
        "avg_para": round(statistics.fmean(plens), 1),
        "dialogue_ratio": round(dlg_ratio, 3),
        "sentence_cv": round(cv, 3),
        "conflict_per_1k": round(density(CONFLICT), 2),
        "payoff_per_1k": round(payoff_d, 2),
        "tension": round(score),
        "hook_stars": stars,
        "hook_kinds": hits,
    }


def chapter_files(paths):
    files = []
    for p in paths:
        if os.path.isdir(p):
            for fn in sorted(os.listdir(p)):
                if re.match(r"ch-\d+\.md$", fn):
                    files.append(os.path.join(p, fn))
        elif os.path.exists(p):
            files.append(p)
    return files


def curve(values, width=48):
    """把张力序列画成一行 ASCII。"""
    if not values:
        return ""
    lo, hi = min(values), max(values)
    span = max(1, hi - lo)
    blocks = "▁▂▃▄▅▆▇█"
    return "".join(blocks[min(7, int((v - lo) / span * 7))] for v in values)


def render(rows, min_hook, window, reds, notices=None):
    L = []
    L.append("=" * 74)
    L.append("节奏体检 ｜ %d 章 ｜ 张力 %d—%d ｜ 钩子中位 ★%d"
             % (len(rows), min(r["tension"] for r in rows),
                max(r["tension"] for r in rows),
                int(statistics.median([r["hook_stars"] for r in rows]))))
    L.append("=" * 74)
    L.append("%-12s %-6s %-6s %-8s %-7s %-7s %s"
             % ("章", "字数", "张力", "钩子", "对话", "爽点", "钩子信号"))
    for r in rows:
        L.append("%-12s %-6d %-6d %-8s %-7s %-7s %s"
                 % (r["chapter"][:12], r["hanzi"], r["tension"],
                    "★" * r["hook_stars"] + "☆" * (5 - r["hook_stars"]),
                    "%.0f%%" % (r["dialogue_ratio"] * 100),
                    "%.1f" % r["payoff_per_1k"],
                    "/".join(r["hook_kinds"].keys()) or "无"))
    L.append("-" * 74)
    L.append("张力曲线：" + curve([r["tension"] for r in rows]))
    if reds:
        L.append("-" * 74)
        for x in reds:
            L.append("✗ [%s] %s" % (x["code"], x["msg"]))
        L.append("红线项须处理：钩子不足的章重写结尾，无爽点的章补一次兑现。")
    else:
        L.append("无红线。注意：张力是启发式估算，不等于好看。")
    for n in (notices or []):
        L.append("（提示）" + n)
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="章级节奏与钩子体检")
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--json", dest="json_out", default=None)
    ap.add_argument("--min-hook", type=int, default=3, help="章末钩子最低星级")
    ap.add_argument("--window", type=int, default=2, help="连续几章无爽点算红线")
    a = ap.parse_args()

    files = chapter_files(a.paths)
    if not files:
        print("没找到 ch-XXX.md。目录下文件名需形如 ch-001.md，或直接给文件路径。")
        return 2

    rows = []
    for f in files:
        with open(f, "r", encoding="utf-8", errors="replace") as fh:
            r = analyze_chapter(fh.read(), os.path.basename(f))
        if r:
            rows.append(r)
    if not rows:
        print("没有解析到正文。")
        return 2

    reds = []
    for r in rows:
        if r["hook_stars"] < a.min_hook:
            reds.append({"code": "H1",
                         "msg": "%s 章末钩子只有 ★%d（要求 ≥★%d）" % (r["chapter"], r["hook_stars"], a.min_hook)})
        if r["dialogue_ratio"] == 0:
            reds.append({"code": "H3", "msg": "%s 整章没有对话" % r["chapter"]})

    # 爽点检查只在"这本书里确实有爽点信号"时才有意义；
    # 全部为 0 更可能是题材不是爽点型（或词表未覆盖），此时给提示不给红线。
    payoff_total = sum(r["payoff_per_1k"] for r in rows)
    notices = []
    if payoff_total == 0:
        notices.append("全书没有检出爽点信号：可能是纯生活流/文学向，或题材不在词表覆盖内。"
                       "不作红线处理。")
    else:
        run = 0
        for r in rows:
            if r["payoff_per_1k"] == 0:
                run += 1
            else:
                if run >= a.window:
                    reds.append({"code": "H2",
                                 "msg": "连续 %d 章没有爽点信号，止于前一段（%s 起好转）" % (run, r["chapter"])})
                run = 0
        if run >= a.window:
            reds.append({"code": "H2", "msg": "末尾连续 %d 章没有爽点信号" % run})

    print(render(rows, a.min_hook, a.window, reds, notices))
    if a.json_out:
        d = os.path.dirname(os.path.abspath(a.json_out))
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        with open(a.json_out, "w", encoding="utf-8") as f:
            json.dump({"chapters": rows, "redlines": reds}, f, ensure_ascii=False, indent=2)
        print("已写入：%s" % a.json_out)
    return 0 if not reds else 1


if __name__ == "__main__":
    sys.exit(main())
