#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stress-test win themes before they reach the proposal.

Usage:
    python theme_check.py themes.json [--md out.md]

Input JSON:
{
  "anchor": "某某医院",
  "themes": [
    {
      "id": "T1",
      "text": "把停机窗口压到 4 小时：某某医院 HIS 割接不停门诊",
      "pain": "上次割接停诊半天，投诉 17 起",
      "move": "双活并行 + 三次演练",
      "evidence": "E2 同城三甲医院 2025 年同类割接，停机 3.5 小时",
      "sections": ["3.2", "5.1"],
      "clone_risk": "low"
    }
  ]
}

Rules checked per theme:
  R1 text length 12-60 chars
  R2 no empty adjectives (行业领先/一流/全方位/...)
  R3 evidence carries an E-level tag (E1/E2/E3/E4)
  R4 sections not empty
  R5 anchor appears in text or pain (otherwise theme is not buyer-specific)
  R6 clone_risk=high with only E3/E4 evidence -> warning
Exit codes: 0 ok, 2 invalid input, 1 when any theme fails.
"""
import json
import re
import sys

EMPTY_WORDS = ["行业领先", "国内领先", "一流", "顶尖", "全方位", "全维度", "深度赋能",
               "极致", "颠覆", "完美", "最强", "最佳", "唯一", "首创", "闭环生态",
               "高水平", "高质量服务", "卓越"]
E_TAG = re.compile(r"[（(]?\bE([1-4])\b[)）]?")


def out(text=""):
    sys.stdout.write(text + "\n")


def fail(msg):
    out("ERROR: " + msg)
    sys.exit(2)


def load(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        fail("找不到输入文件: %s" % path)
    except json.JSONDecodeError as e:
        fail("JSON 解析失败: %s" % e)


def check_theme(t, anchor):
    issues, warns = [], []
    text = (t.get("text") or "").strip()
    pain = (t.get("pain") or "").strip()
    ev = (t.get("evidence") or "").strip()
    secs = t.get("sections") or []
    risk = (t.get("clone_risk") or "").strip().lower()

    if not text:
        issues.append("主题句为空")
        return issues, warns, None
    if not 12 <= len(text) <= 60:
        warns.append("主题句长度 %d 字（建议 12-60）" % len(text))
    hit = [w for w in EMPTY_WORDS if w in text]
    if hit:
        issues.append("含空词：%s" % "、".join(hit))
    tags = E_TAG.findall(ev)
    if not tags:
        issues.append("证据未标等级（需 E1/E2/E3/E4）")
    if not secs:
        issues.append("未映射到章节")
    move = (t.get("move") or "").strip()
    if anchor and anchor not in (text + pain + move):
        warns.append("三处字段都未出现客户锚点「%s」，请人工确认换别家是否也成立" % anchor)
    if risk == "high" and tags and all(x in ("3", "4") for x in tags):
        warns.append("易被照抄且只有 E3/E4 证据，建议换角度或补实证")
    if not pain:
        warns.append("缺客户原话痛点，主题容易写成自我表扬")
    best = max(tags) if tags else None
    return issues, warns, best


def render(data):
    themes = data.get("themes") or []
    if not themes:
        fail("themes 为空")
    anchor = (data.get("anchor") or "").strip()
    rows, failed, warned = [], 0, 0
    for n, t in enumerate(themes, 1):
        tid = t.get("id") or ("T%d" % n)
        issues, warns, best = check_theme(t, anchor)
        status = "FAIL" if issues else ("WARN" if warns else "PASS")
        if issues:
            failed += 1
        elif warns:
            warned += 1
        rows.append((tid, (t.get("text") or "").strip(), status, issues, warns, best))

    lines = ["# 主题卡体检", ""]
    lines.append("客户锚点：%s　主题数：%d" % (anchor or "（未指定）", len(themes)))
    lines.append("")
    lines.append("| 编号 | 主题句 | 结论 | 问题 | 提示 | 最高证据 |")
    lines.append("|---|---|---|---|---|---|")
    for tid, text, status, issues, warns, best in rows:
        lines.append("| %s | %s | %s | %s | %s | %s |" % (
            tid, text, status, "；".join(issues) or "-", "；".join(warns) or "-", best or "-"))
    lines.append("")
    lines.append("**结果：PASS %d / WARN %d / FAIL %d**" % (len(rows) - failed - warned, warned, failed))
    lines.append("")
    if failed:
        lines.append("有主题未过三问（是否只对这家成立 / 有没有证据 / 对手照抄会不会露馅），改完再进成篇关。")
    elif warned:
        lines.append("可用，但提示项建议在评审前补一轮。")
    else:
        lines.append("主题全部通过形式检查。仍需人工判断：对手能否提出同样的主张。")
    lines.append("")
    lines.append("> 形式检查不等于判断力。脚本只能发现空词、缺证据、缺锚点，判断差异化是否成立仍需人来做。")
    return "\n".join(lines), failed


def main():
    argv = sys.argv[1:]
    if not argv:
        out(__doc__)
        sys.exit(2)
    data = load(argv[0])
    md = None
    if "--md" in argv:
        i = argv.index("--md")
        md = argv[i + 1] if i + 1 < len(argv) else None
    report, failed = render(data)
    out(report)
    if md:
        with open(md, "w", encoding="utf-8") as f:
            f.write(report + "\n")
        out("\n已写入: %s" % md)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
