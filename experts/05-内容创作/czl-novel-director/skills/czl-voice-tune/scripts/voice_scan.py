#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""voice_scan.py — 正文人味体检（确定性文本扫描，不联网、不调模型）

用法：
    python voice_scan.py <正文.md> [--json 输出路径] [--thresholds 配置.json] [--quiet]

设计原则：
  1. 只做能数出来的事。数不出来的（比如"这段有没有必要"）不放进本脚本，交人工判断。
  2. 同一份文本跑两次结果必须完全一致，不引入随机、不引入时间戳。
  3. 每条指标都定位到段号与原文片段，方便直接改。
  4. 指标合格不等于好看；指标不合格一定有问题。顺序不能倒。

作者：虫志龙 <47190078@qq.com>
许可：随本专家包发布的原创代码，MIT。
"""

import argparse
import json
import os
import re
import statistics
import sys

# ---------- 文本工具 ----------

HANZI = re.compile(r"[\u4e00-\u9fff]")
# 整句匹配：句末标点连同其后的收引号、收括号一起归入本句。
# 若按标点直接 split，`“你今天不上学？”老板问` 会被切碎，进而误判为连续短句。
SENT_RE = re.compile(r"[^。！？!?…\n]+[。！？!?…]+[」』”’）)]*|[^。！？!?…\n]+$")
# 以引号开头的句子是对话，长度天然短，不参与"连续短句"判定
DIALOGUE_HEAD = re.compile(r"^\s*[「『“\"']")


def hanzi_count(text):
    return len(HANZI.findall(text))


def split_paragraphs(text):
    """按空行分段，返回 [(段号, 段落文本)]，段号从 1 开始。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", text)
    out = []
    idx = 0
    for b in blocks:
        b = b.strip()
        if not b:
            continue
        idx += 1
        out.append((idx, b))
    return out


def split_sentences(para):
    """切句。句末标点与收引号留在同一句内，丢掉纯标点残片。"""
    out = []
    for s in SENT_RE.findall(para):
        s = s.strip(" \t\n　")
        if not s:
            continue
        if hanzi_count(s) == 0 and len(s) < 4:
            continue
        out.append(s)
    return out


def excerpt(s, n=24):
    s = s.replace("\n", " ")
    return s if len(s) <= n else s[:n] + "…"


# ---------- 检查项 ----------

BLACKLIST = {
    "寂静": "万能氛围词，读者无画面",
    "死寂": "同上，且被用滥",
    "诡异": "直接下判断，抢了读者的感受",
    "阴冷": "万能形容词",
    "猩红": "网文腔调词，已成模板",
    "莫名": "作者替人物偷懒",
    "一丝": "万能量词，几乎不携带信息",
    "不禁": "书面腔，人物不会这样想",
    "空气仿佛凝固": "陈词，出现即出戏",
    "心中一凛": "陈词",
    "瞳孔一缩": "陈词，且物理上不成立",
    "倒吸一口凉气": "陈词",
}

EMOTION_DIRECT = re.compile(
    r"(感到|觉得|心中|心里|心底|内心|心头)(一阵|一股|些许|几分|满满的|无比的)?"
    r"[\u4e00-\u9fff]{0,3}"
    r"(愤怒|悲愤|悲伤|难过|痛苦|绝望|欣喜|狂喜|震惊|疑惑|不安|紧张|失落|委屈|愧疚|恐惧|害怕|开心|高兴|激动|厌恶|羞愧)"
)

SUMMARY_OPEN = re.compile(
    r"^(他知道|她知道|他明白|她明白|他意识到|她意识到|他心里清楚|她心里清楚|"
    r"他清楚|她清楚|从这一刻起|从今天起|从此|这一切|这意味着)"
)

SIMILE_MARK = re.compile(r"(像|好像|仿佛|宛如|好似|如同|恰似)")

WEAK_ADVERB = re.compile(r"(缓缓|淡淡|微微|轻轻|静静|默默|徐徐|悠悠)")

PARALLEL_START = 2  # 取句首几个汉字判断同头


def norm_thresholds(cfg):
    base = {
        "sentence_cv_fail": 0.42,       # 句长变异系数，越低越均匀
        "sentence_cv_warn": 0.55,
        "short_run_len": 8,             # 汉字数不超过此值算短句
        "short_run_warn": 3,            # 连续短句达到此数告警
        "short_run_fail": 4,
        "dash_per_1k_fail": 4.0,
        "dash_per_1k_warn": 2.0,
        "not_but_fail": 3,              # "不是…而是" 出现次数
        "not_but_warn": 2,
        "simile_per_1k_fail": 8.0,
        "emotion_direct_fail": 3,
        "blacklist_fail": 5,
        "summary_open_warn": 2,
        "para_median_min": 25,
        "para_median_max": 190,
        "para_long_len": 260,
        "dialogue_min": 0.12,
        "dialogue_max": 0.78,
        "adverb_per_1k_warn": 5.0,
        "exclaim_per_1k_warn": 8.0,
        "parallel_run_warn": 3,
    }
    base.update(cfg or {})
    return base


def scan(text, cfg=None):
    T = norm_thresholds(cfg)
    paras = split_paragraphs(text)
    full = "\n".join(p for _, p in paras)
    total = hanzi_count(full)
    findings = []

    def add(cid, name, status, value, threshold, hint, where=None):
        findings.append({
            "id": cid, "name": name, "status": status,
            "value": value, "threshold": threshold,
            "hint": hint, "where": where or [],
        })

    if total == 0:
        return {"ok": False, "error": "正文没有汉字，可能读错文件或编码不是 UTF-8", "findings": []}

    # 句级数据
    all_sents = []
    sent_para = {}
    for pidx, p in paras:
        for s in split_sentences(p):
            all_sents.append(s)
            sent_para[len(all_sents) - 1] = pidx
    lens = [hanzi_count(s) for s in all_sents]
    lens_nonzero = [x for x in lens if x > 0]

    # R01 句长离散度
    if len(lens_nonzero) >= 8:
        mean = statistics.fmean(lens_nonzero)
        sd = statistics.pstdev(lens_nonzero)
        cv = sd / mean if mean else 0
        st = "PASS"
        if cv < T["sentence_cv_fail"]:
            st = "FAIL"
        elif cv < T["sentence_cv_warn"]:
            st = "WARN"
        add("R01", "句长离散度（越低越像机器）", st, round(cv, 3),
            f"≥{T['sentence_cv_warn']}",
            "句长太整齐。把三句并成一句，或把一句拆成四个字的短句。",
            [{"para": 1, "excerpt": "全文统计"}])

    # R02 短句连排
    runs = []
    cur = []
    for i, s in enumerate(all_sents):
        if 0 < hanzi_count(s) <= T["short_run_len"] and not DIALOGUE_HEAD.match(s):
            cur.append(i)
        else:
            if len(cur) >= T["short_run_warn"]:
                runs.append(list(cur))
            cur = []
    if len(cur) >= T["short_run_warn"]:
        runs.append(list(cur))
    max_run = max((len(r) for r in runs), default=0)
    st = "PASS"
    if max_run >= T["short_run_fail"]:
        st = "FAIL"
    elif max_run >= T["short_run_warn"]:
        st = "WARN"
    add("R02", "连续短句（碎片化节奏）", st, {"段数": len(runs), "最长连排": max_run},
        f"最长连排 <{T['short_run_warn']}",
        "连续短句是 AI 最明显的指纹。把其中两句合成一句长句，或删掉一句。",
        [{"para": sent_para.get(r[0], 0),
          "excerpt": " / ".join(excerpt(all_sents[i], 12) for i in r[:4])} for r in runs[:3]])

    # R03 破折号密度
    dash = full.count("——")
    per1k = dash * 1000.0 / total
    st = "PASS"
    if per1k > T["dash_per_1k_fail"]:
        st = "FAIL"
    elif per1k > T["dash_per_1k_warn"]:
        st = "WARN"
    add("R03", "破折号密度（每千字）", st, round(per1k, 2), f"≤{T['dash_per_1k_warn']}",
        "破折号是 AI 的节拍器。一章超过两处就该换句号或直接删。")

    # R04 不是…而是
    nb = len(re.findall(r"不是[^。！？\n]{0,20}?而是", full))
    st = "PASS"
    if nb >= T["not_but_fail"]:
        st = "FAIL"
    elif nb >= T["not_but_warn"]:
        st = "WARN"
    add("R04", "「不是…而是」句式", st, nb, "≤1 处",
        "这个句式一章最多一处。多了就是作者在替读者做判断。")

    # R05 比喻标记密度
    sim = len(SIMILE_MARK.findall(full))
    sim_per1k = sim * 1000.0 / total
    st = "PASS"
    if sim_per1k > T["simile_per_1k_fail"]:
        st = "FAIL"
    add("R05", "比喻标记密度（像/仿佛/如同…）", st, round(sim_per1k, 2),
        f"≤{T['simile_per_1k_fail']}",
        "一个场景最多一两个比喻。剩下的删掉，画面反而清楚。")

    # R06 情绪直述
    emo = EMOTION_DIRECT.findall(full)
    st = "PASS"
    if len(emo) >= T["emotion_direct_fail"]:
        st = "FAIL"
    add("R06", "情绪直述（感到/心里+情绪词）", st, len(emo), f"<{T['emotion_direct_fail']}",
        "能拍出来的写，拍不出来的别写。「他感到不安」→「他把手机翻过去扣在桌上」。",
        [{"para": 0, "excerpt": m.group(0)} for m in list(EMOTION_DIRECT.finditer(full))[:5]])

    # R07 万能词黑名单
    hits = []
    for pidx, p in paras:
        for w, why in BLACKLIST.items():
            if w in p:
                hits.append({"para": pidx, "word": w, "why": why,
                             "excerpt": excerpt(p, 30)})
    st = "PASS"
    if len(hits) >= T["blacklist_fail"]:
        st = "FAIL"
    elif hits:
        st = "WARN"
    add("R07", "万能词/陈词", st, len(hits), f"<{T['blacklist_fail']}", 
        "这些词不携带画面。换成具体动作或具体物体。", hits[:8])

    # R08 段首总结句
    sum_open = []
    for pidx, p in paras:
        if SUMMARY_OPEN.match(p):
            sum_open.append({"para": pidx, "excerpt": excerpt(p, 30)})
    st = "PASS"
    if len(sum_open) >= T["summary_open_warn"]:
        st = "WARN"
    add("R08", "段首总结句（他知道/从此/这一切）", st, len(sum_open),
        f"<{T['summary_open_warn']}",
        "凡是替读者总结的句子，删掉。读者不需要被告知该感受到什么。", sum_open)

    # R09 段长分布
    plens = [hanzi_count(p) for _, p in paras]
    med = statistics.median(plens) if plens else 0
    long_paras = [{"para": i, "len": hanzi_count(p), "excerpt": excerpt(p, 20)}
                  for i, p in paras if hanzi_count(p) > T["para_long_len"]]
    st = "PASS"
    if med < T["para_median_min"] or med > T["para_median_max"] or long_paras:
        st = "WARN"
    add("R09", "段落长度分布", st, {"中位数": med, "超长段": len(long_paras)},
        f"中位数 {T['para_median_min']}—{T['para_median_max']}，无超长段",
        "全是短段像提纲，全是长段像说明书。长短要错开。", long_paras[:5])

    # R10 对话占比
    dlg_paras = [1 for _, p in paras if re.search(r"[「“\"]", p)]
    ratio = len(dlg_paras) / len(paras) if paras else 0
    st = "PASS"
    if ratio < T["dialogue_min"] or ratio > T["dialogue_max"]:
        st = "WARN"
    add("R10", "含对话段落占比", st, round(ratio, 3),
        f"{T['dialogue_min']}—{T['dialogue_max']}",
        "全是叙述读者会累，全是对话读者会浮。")

    # R11 弱副词密度
    adv = len(WEAK_ADVERB.findall(full))
    adv_per1k = adv * 1000.0 / total
    st = "PASS"
    if adv_per1k > T["adverb_per_1k_warn"]:
        st = "WARN"
    add("R11", "弱副词密度（缓缓/淡淡/微微…）", st, round(adv_per1k, 2),
        f"≤{T['adverb_per_1k_warn']}",
        "「缓缓开口」不如直接写他说了什么。副词删掉，动词才有力。")

    # R12 结尾总结段
    tail = paras[-2:] if len(paras) >= 2 else paras
    tail_hit = [{"para": i, "excerpt": excerpt(p, 30)} for i, p in tail
                if SUMMARY_OPEN.match(p) or re.search(r"(他知道|她知道|从此|从今天起|这一切)", p)]
    st = "PASS"
    if tail_hit:
        st = "WARN"
    add("R12", "章末总结倾向", st, len(tail_hit), "0",
        "章末该落在钩子上，不该落在感慨上。删掉最后那段感慨，钩子会更有力。", tail_hit)

    # R13 感叹号密度
    ex = full.count("！") + full.count("!")
    ex_per1k = ex * 1000.0 / total
    st = "PASS"
    if ex_per1k > T["exclaim_per_1k_warn"]:
        st = "WARN"
    add("R13", "感叹号密度（每千字）", st, round(ex_per1k, 2),
        f"≤{T['exclaim_per_1k_warn']}", "靠感叹号制造情绪，说明句子本身没做到。")

    # R14 三句同头（排比指纹）
    parallel = []
    run = []
    prev = None
    for i, s in enumerate(all_sents):
        if DIALOGUE_HEAD.match(s):
            if len(run) >= T["parallel_run_warn"]:
                parallel.append(list(run))
            run = []
            prev = None
            continue
        head = "".join(HANZI.findall(s))[:PARALLEL_START]
        if head and head == prev:
            run.append(i)
        else:
            if len(run) >= T["parallel_run_warn"]:
                parallel.append(list(run))
            run = [i]
            prev = head
    if len(run) >= T["parallel_run_warn"]:
        parallel.append(list(run))
    st = "PASS"
    if parallel:
        st = "WARN"
    add("R14", "同头排比（连续同字开头）", st, len(parallel), "0",
        "连续三句同字开头是 AI 的排比指纹。改掉其中两句的开头。",
        [{"para": sent_para.get(r[0], 0),
          "excerpt": " / ".join(excerpt(all_sents[i], 10) for i in r[:3])} for r in parallel[:3]])

    # ---------- 汇总 ----------
    weight = {"FAIL": 12, "WARN": 4, "PASS": 0}
    penalty = sum(weight[f["status"]] for f in findings)
    score = max(0, 100 - penalty)
    if score >= 88:
        grade = "A"
    elif score >= 74:
        grade = "B"
    elif score >= 60:
        grade = "C"
    else:
        grade = "D"

    fails = [f for f in findings if f["status"] == "FAIL"]
    warns = [f for f in findings if f["status"] == "WARN"]

    # 有阻断项时不给 A/B，避免"高分但仍不合格"的误导
    if fails and grade in ("A", "B"):
        grade = "C"

    return {
        "ok": True,
        "file_chars": len(text),
        "hanzi": total,
        "paragraphs": len(paras),
        "sentences": len(all_sents),
        "avg_sentence_len": round(statistics.fmean(lens_nonzero), 2) if lens_nonzero else 0,
        "score": score,
        "grade": grade,
        "verdict": "PASS" if not fails else "FAIL",
        "fail_count": len(fails),
        "warn_count": len(warns),
        "findings": findings,
        "note": "指标合格不等于好看；指标不合格一定有问题。R09—R13 属提示项，可结合语境豁免并记录理由。",
    }


def render_text(r):
    if not r.get("ok"):
        return "扫描失败：" + r.get("error", "未知错误")
    lines = []
    lines.append("=" * 58)
    lines.append("人味体检  等级 %s  分 %d  判定 %s" % (r["grade"], r["score"], r["verdict"]))
    lines.append("汉字 %d ｜ 段 %d ｜ 句 %d ｜ 平均句长 %.1f"
                 % (r["hanzi"], r["paragraphs"], r["sentences"], r["avg_sentence_len"]))
    lines.append("=" * 58)
    order = {"FAIL": 0, "WARN": 1, "PASS": 2}
    for f in sorted(r["findings"], key=lambda x: (order[x["status"]], x["id"])):
        mark = {"FAIL": "✗", "WARN": "!", "PASS": "·"}[f["status"]]
        val = f["value"]
        if isinstance(val, dict):
            val = ", ".join("%s=%s" % (k, v) for k, v in val.items())
        lines.append("%s %s %s ｜ 实测 %s ｜ 阈值 %s" %
                     (mark, f["id"], f["name"], val, f["threshold"]))
        if f["status"] != "PASS":
            lines.append("    改法：%s" % f["hint"])
            for w in f.get("where", [])[:3]:
                if w.get("para"):
                    lines.append("    第 %s 段：%s" % (w["para"], w.get("excerpt", "")))
                elif w.get("excerpt"):
                    lines.append("    %s" % w["excerpt"])
    lines.append("-" * 58)
    fails = [f["id"] for f in r["findings"] if f["status"] == "FAIL"]
    if fails:
        lines.append("必须先清零：%s" % "、".join(fails))
    else:
        lines.append("无阻断项。提示项可结合语境豁免，需在 qc 报告中写理由。")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="正文人味体检")
    ap.add_argument("path", help="正文 md/txt 路径")
    ap.add_argument("--json", dest="json_out", default=None, help="把结果另存为 JSON")
    ap.add_argument("--thresholds", default=None, help="阈值配置 JSON 路径")
    ap.add_argument("--quiet", action="store_true", help="只输出汇总行")
    a = ap.parse_args()

    if not os.path.exists(a.path):
        print("找不到文件：%s" % a.path)
        return 2
    with open(a.path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    cfg = None
    if a.thresholds:
        if not os.path.exists(a.thresholds):
            print("找不到阈值配置：%s" % a.thresholds)
            return 2
        with open(a.thresholds, "r", encoding="utf-8") as f:
            cfg = json.load(f)

    r = scan(text, cfg)
    if a.quiet and r.get("ok"):
        print("等级 %s 分 %d 判定 %s（FAIL %d / WARN %d）"
              % (r["grade"], r["score"], r["verdict"], r["fail_count"], r["warn_count"]))
    else:
        print(render_text(r))

    if a.json_out:
        d = os.path.dirname(os.path.abspath(a.json_out))
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        with open(a.json_out, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2)
        print("已写入：%s" % a.json_out)

    return 0 if r.get("ok") and not r.get("fail_count") else 1


if __name__ == "__main__":
    sys.exit(main())
