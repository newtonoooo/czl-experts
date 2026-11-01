#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""qa_check.py — 试卷 / 答案成品自检

用法：
    python qa_check.py --paper 试卷.md --answers 答案与解析.md
    python qa_check.py --paper 试卷.md --json report.json

检查项：
  1. 占位符残留（[TODO]、XX、待补、（略）、自行补充）
  2. 题号连续性（1..N，无跳号/重号）
  3. 选择题选项完整性（出现选项标记的题目须有 A–D 或 A–G）
  4. 分值合计与卷头满分一致性
  5. 答案数量与题目数量一致性
  6. 答案字母合法性
  7. 学生隐私字段（手机号、身份证号）

退出码：0 全部通过或有 WARN；1 存在 FAIL。
"""
import argparse
import json
import re
import sys
from pathlib import Path

PLACEHOLDERS = ["[TODO]", "TODO", "XX", "待补", "（略）", "(略)", "自行补充", "此处填写"]
Q_RE = re.compile(r"^\s*(\d{1,3})\s*[.、．)]\s*")
OPT_RE = re.compile(r"(?<![A-Za-z])([A-G])\s*[.、．)]\s*")
SCORE_RE = re.compile(r"[（(]\s*(\d+(?:\.\d+)?)\s*分\s*[)）]")
HEAD_FULL_RE = re.compile(r"满分\s*[：:]\s*(\d+(?:\.\d+)?)")
ANS_RE = re.compile(r"【答案】\s*([A-Ga-g]{1,7}|\S+)")
PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
ID_RE = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")

SEV = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}


def read(path):
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return Path(path).read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return Path(path).read_text(encoding="utf-8", errors="replace")


def check_placeholders(text):
    hits = []
    for p in PLACEHOLDERS:
        if p in text:
            cnt = text.count(p)
            hits.append({"token": p, "count": cnt})
    if hits:
        desc = "、".join(f"{h['token']}×{h['count']}" for h in hits)
        return [("FAIL", "占位符", f"发现未清理的占位符：{desc}")]
    return [("PASS", "占位符", "未发现占位符")]


def check_numbering(papers):
    nums = []
    for line in papers.splitlines():
        m = Q_RE.match(line)
        if m:
            nums.append(int(m.group(1)))
    if not nums:
        return [("WARN", "题号", "未识别到题号（格式应为「1. 」或「1、」）")], nums
    expected = list(range(1, max(nums) + 1))
    missing = [n for n in expected if n not in nums]
    dups = sorted({n for n in nums if nums.count(n) > 1})
    out = []
    if missing:
        out.append(("FAIL", "题号", f"缺号：{missing[:12]}{'…' if len(missing) > 12 else ''}"))
    if dups:
        out.append(("FAIL", "题号", f"重号：{dups[:12]}"))
    if not missing and not dups:
        out.append(("PASS", "题号", f"1–{max(nums)} 连续，共 {len(nums)} 题"))
    return out, nums


def check_options(papers):
    """按题目块检查选项：题目若带 2 个以上选项标记，则应有完整 4 项。"""
    blocks = []
    cur = None
    for line in papers.splitlines():
        m = Q_RE.match(line)
        if m:
            if cur:
                blocks.append(cur)
            cur = {"no": int(m.group(1)), "text": line}
        elif cur:
            cur["text"] += "\n" + line
    if cur:
        blocks.append(cur)

    bad = []
    checked = 0
    for b in blocks:
        letters = sorted(set(OPT_RE.findall(b["text"])))
        if len(letters) < 2:
            continue
        checked += 1
        if letters != ["A", "B", "C", "D"]:
            bad.append((b["no"], "".join(letters)))
    if checked == 0:
        return [("WARN", "选项", "未识别到选择题选项（非选择题卷可忽略）")]
    if bad:
        detail = "；".join(f"第{n}题：{s or '无'}" for n, s in bad[:10])
        return [("FAIL", "选项", f"选项不完整或异常：{detail}")]
    return [("PASS", "选项", f"{checked} 道选择题选项均为 A–D")]


def check_scores(papers):
    total = sum(float(x) for x in SCORE_RE.findall(papers))
    m = HEAD_FULL_RE.search(papers)
    if m:
        declared = float(m.group(1))
        if abs(total - declared) > 1e-6:
            return [("FAIL", "分值", f"题目分值合计 {total:g}，卷头满分 {declared:g}，差值 {total - declared:+g}")]
        return [("PASS", "分值", f"题目分值合计 {total:g} = 卷头满分 {declared:g}")]
    if total > 0:
        return [("WARN", "分值", f"题目分值合计 {total:g}，卷头未标注满分，无法核对")]
    return [("WARN", "分值", "未识别到分值标注（如「（2.5分）」）")]


def check_answers(papers, answers, q_count):
    if answers is None:
        return [("WARN", "答案", "未提供答案文件，跳过答案核对")]
    found = ANS_RE.findall(answers)
    out = []
    if not found:
        return [("FAIL", "答案", "答案文件中未找到【答案】标记")]
    if q_count and len(found) != q_count:
        out.append(("FAIL", "答案", f"答案条目 {len(found)} 个，题目 {q_count} 道，数量不一致"))
    else:
        out.append(("PASS", "答案", f"答案条目 {len(found)} 个，与题目数量一致"))

    bad = [a for a in found if re.fullmatch(r"[A-Ga-g]{1,7}", a) and a.upper() not in list("ABCDEFG")]
    bad += [a for a in found if re.fullmatch(r"[H-Zh-z]+", a)]
    if bad:
        out.append(("FAIL", "答案", f"答案字母异常：{bad[:8]}"))
    return out


def check_privacy(text):
    hits = []
    if PHONE_RE.search(text):
        hits.append("手机号")
    if ID_RE.search(text):
        hits.append("身份证号")
    if hits:
        return [("FAIL", "隐私", f"疑似包含个人敏感信息：{'、'.join(hits)}")]
    return [("PASS", "隐私", "未发现手机号/身份证号")]


def main(argv=None):
    ap = argparse.ArgumentParser(description="试卷与答案成品自检")
    ap.add_argument("--paper", required=True)
    ap.add_argument("--answers")
    ap.add_argument("--json", dest="json_out")
    args = ap.parse_args(argv)

    try:
        paper = read(args.paper)
    except OSError as e:
        print(f"[ERROR] 读取试卷失败：{e}", file=sys.stderr)
        return 2
    answers = read(args.answers) if args.answers else None

    results = []
    results += check_placeholders(paper)
    nr, nums = check_numbering(paper)
    results += nr
    results += check_options(paper)
    results += check_scores(paper)
    results += check_answers(paper, answers, len(nums))
    results += check_privacy(paper + (answers or ""))

    fails = [r for r in results if r[0] == "FAIL"]
    warns = [r for r in results if r[0] == "WARN"]

    print("# 成品自检报告")
    print()
    print("| 结果 | 项目 | 说明 |")
    print("|---|---|---|")
    for sev, item, msg in results:
        print(f"| {SEV[sev]} {sev} | {item} | {msg} |")
    print()
    print(f"结论：FAIL {len(fails)} 项，WARN {len(warns)} 项。")
    if fails:
        print("未通过：修复 FAIL 项后重新检查。")

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps([{"level": s, "item": i, "message": m} for s, i, m in results],
                       ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] JSON：{args.json_out}")

    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
