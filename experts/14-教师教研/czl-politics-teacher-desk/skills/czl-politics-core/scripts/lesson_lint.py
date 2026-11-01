#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""教案/规划/讲评稿结构检查器（纯标准库）。

用法:
    python lesson_lint.py <文件.md> [--duration 40]

只做机械检查，不判断教学设计好坏。退出码 0 = 无错误，1 = 有错误。
"""

import argparse
import re
import sys
from pathlib import Path

PLACEHOLDER = re.compile(r"\{\{[^}]{0,60}\}\}")
PRIME_MIN = re.compile(r"(\d{1,3})\s*[′']")
CN_MIN = re.compile(r"（约\s*(\d{1,3})\s*分钟）")

BANNED = [
    ("众所周知", "空话，无信息量"),
    ("显而易见", "空话，无信息量"),
    ("毋庸置疑", "空话，无信息量"),
    ("不言而喻", "空话，无信息量"),
    ("让我们一起", "口号式表述"),
    ("总而言之", "AI 腔收尾"),
    ("众所周知的是", "空话"),
    ("为了培养学生的核心素养", "不可观察的目标表述"),
    ("体会……情感", "不可观察的目标表述"),
]

REQUIRED = {
    "lesson": ["教学目标", "教学重难点", "教学过程", "板书", "作业", "教师备注"],
    "unit": ["单元目标", "课时分配", "议题线", "评价任务", "教师备注"],
    "review": ["数据摘要", "讲评优先级", "变式", "收口", "教师备注"],
    "generic": ["教师备注"],
}


def detect_type(text):
    if "讲评优先级" in text or "错解还原" in text:
        return "review"
    if "课时分配" in text and "单元目标" in text:
        return "unit"
    if "教学过程" in text or "教学重难点" in text:
        return "lesson"
    return "generic"


def section(text, title):
    """取出某个二级标题下的内容（到下一个同级标题为止）。"""
    m = re.search(r"^##\s*[一二三四五六七八九十\d、\.]*\s*" + re.escape(title) + r".*$", text, re.M)
    if not m:
        return ""
    start = m.end()
    nxt = re.search(r"^##\s", text[start:], re.M)
    return text[start:start + nxt.start()] if nxt else text[start:]


def table_rows(block):
    """返回表格数据行（去掉表头与分隔行）。"""
    rows, header_seen = [], False
    for line in block.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        if re.match(r"^\|[\s:\-\|]+\|$", s):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not header_seen:
            header_seen = True
            continue
        if any(cells):
            rows.append(cells)
    return rows


def count_table_rows(block):
    return len(table_rows(block))


def time_sum(text):
    block = section(text, "教学过程")
    if not block:
        return None
    vals = [int(x) for x in PRIME_MIN.findall(block)]
    if not vals:
        vals = [int(x) for x in CN_MIN.findall(block)]
    return sum(vals) if vals else None


def declared_duration(text, override=None):
    if override:
        return override
    m = re.search(r"(\d{2})\s*分钟", text)
    return int(m.group(1)) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--duration", type=int, default=None, help="课时分钟数，覆盖自动识别")
    args = ap.parse_args()

    p = Path(args.path)
    if not p.exists():
        print(f"[FAIL] 文件不存在: {p}")
        return 1
    text = p.read_text(encoding="utf-8")
    kind = detect_type(text)

    errors, warns = [], []

    # 1. 占位符
    ph = PLACEHOLDER.findall(text)
    if ph:
        errors.append(f"残留占位符 {len(ph)} 处，例如 {ph[0]}")

    # 2. 必备章节
    for sec in REQUIRED[kind]:
        if sec not in text:
            errors.append(f"缺少必备章节：{sec}")

    # 3. 时间加总
    total = time_sum(text)
    declared = declared_duration(text, args.duration)
    if total is not None and declared:
        if abs(total - declared) > 2:
            errors.append(f"环节时间加总 {total} 分钟，与课时 {declared} 分钟相差超过 2 分钟")
        else:
            print(f"[OK]   时间加总 {total} 分钟 ≈ 课时 {declared} 分钟")
    elif kind == "lesson":
        warns.append("未能识别环节时长，请确认教学过程表中是否标注了「N′」")

    # 4. 目标—评价数量
    goal_block = section(text, "教学目标")
    if goal_block:
        rows = table_rows(goal_block)
        n_goal = len(rows)
        if rows and len(rows[0]) >= 4:
            # 目标表自带"对应的评价证据"列时，直接看该列是否填满
            n_eval = sum(1 for r in rows if len(r) >= 4 and r[3] and not PLACEHOLDER.search(r[3]))
        else:
            eval_block = section(text, "评价证据") or section(text, "评价任务")
            n_eval = count_table_rows(eval_block) if eval_block else 0
        if n_goal and n_eval < n_goal:
            errors.append(f"目标 {n_goal} 条，有评价证据的只有 {n_eval} 条（每条目标至少对应一条证据）")
        elif n_goal:
            print(f"[OK]   目标 {n_goal} 条，评价证据 {n_eval} 条")

    # 5. 禁用表述
    for word, why in BANNED:
        if word in text:
            warns.append(f"出现「{word}」（{why}）")

    # 6. 教师备注三段
    note = section(text, "教师备注")
    if note:
        if "最可能出问题" not in note:
            warns.append("教师备注缺少「最可能出问题的地方」")
        if "调整" not in note:
            warns.append("教师备注缺少「需按学情调整」")
        if "替换" not in note:
            warns.append("教师备注缺少「可替换素材」")

    print(f"\n文件：{p.name}")
    print(f"类型判定：{kind}")
    print(f"错误：{len(errors)}　告警：{len(warns)}")
    for e in errors:
        print(f"  [ERROR] {e}")
    for w in warns:
        print(f"  [WARN ] {w}")
    if not errors:
        print("\n结论：结构检查通过（内容质量仍需人工判断）")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
