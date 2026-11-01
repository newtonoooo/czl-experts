#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""卓识化学 · 工作流静态自检

它检查的是"提示词工程层面的完整性"，不是真实大模型推理：
  1. 8+1 个工作流文件是否齐全、九要素是否写清；
  2. 主提示词的路由表是否覆盖全部工作流；
  3. 所有 `knowledge/xx.md`、`playbooks/Wx.md` 引用是否都能落到真实文件；
  4. 是否残留 TODO / 占位符 / 未经核对的"待补"；
  5. 用 16 条教师常见话语做一次路由规则模拟，检查是否指到存在的文件。

用法：
    python tools/selftest_workflows.py
退出码：0 通过；1 有失败项。
"""

from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENT = os.path.join(ROOT, "agents", "czl-chem-teaching-suite.md")

ELEMENTS = ["任务职责", "输入参数", "执行步骤", "判断条件", "输出格式", "异常处理", "必要依赖"]
CROSS = ["与其他工作流的关系", "关系"]

# 路由模拟：关键词 → 期望的工作流文件
CASES = [
    ("帮我写一份《盐类的水解》的教案", "W1-lesson.md"),
    ("出一套反应原理单元测，先给细目表", "W2-assessment.md"),
    ("按错因码批改这 30 份答卷", "W3-grading.md"),
    ("这是月考成绩表，帮我做学情分析", "W4-diagnosis.md"),
    ("学生总把水解和电离搞混，讲一下", "W5-explainer.md"),
    ("这道 2024 年广东卷的流程题怎么讲", "W6-gaokao.md"),
    ("帮我配平这个氧化还原方程式", "W7-chem-lab.md"),
    ("设计一个实验室制氯气的方案", "W7-chem-lab.md"),
    ("设计一条从苯到苯甲酸的合成路线", "W7-chem-lab.md"),
    ("这个工业流程题每一步的目的是什么", "W7-chem-lab.md"),
    ("算一下这个平衡常数", "W7-chem-lab.md"),
    ("把教材这几页做成课件 PPT", "W8-courseware.md"),
    ("这个知识点怎么讲才能听懂", "W5-explainer.md"),
    ("帮我讲讲这道高考真题", "W6-gaokao.md"),
    ("批改一下这份实验报告", "W3-grading.md"),
    ("帮我看看这个（附一张教材页图片）", "W0-triage.md"),
]


def main() -> int:
    errors, passes = [], []

    def ok(m):
        passes.append(m)

    def err(m):
        errors.append(m)

    if not os.path.isfile(AGENT):
        print("找不到主提示词")
        return 1
    agent = open(AGENT, encoding="utf-8").read()

    # 1 路由表覆盖
    for i in range(0, 9):
        tag = f"W{i}"
        if tag in agent:
            ok(f"主提示词路由表含 {tag}")
        else:
            err(f"主提示词路由表缺少 {tag}")

    # 2 playbook 九要素
    for i in range(0, 9):
        cands = [f for f in os.listdir(os.path.join(ROOT, "playbooks")) if f.startswith(f"W{i}-")]
        if not cands:
            err(f"缺少 W{i} 工作流文件")
            continue
        p = os.path.join(ROOT, "playbooks", cands[0])
        text = open(p, encoding="utf-8").read()
        miss = [e for e in ELEMENTS if e not in text]
        if not any(c in text for c in CROSS):
            miss.append("与其他工作流的关系")
        if miss:
            err(f"{cands[0]} 缺要素：{'、'.join(miss)}")
        else:
            ok(f"{cands[0]} 九要素齐全（{len(text)} 字符）")
        if len(text) < 800:
            err(f"{cands[0]} 内容过短（{len(text)} 字符），难以支撑执行")

    # 3 交叉引用可落地
    refs = set(re.findall(r"`((?:knowledge|playbooks|materials)/[^`]+\.(?:md|csv))`", agent))
    for pb in os.listdir(os.path.join(ROOT, "playbooks")):
        text = open(os.path.join(ROOT, "playbooks", pb), encoding="utf-8").read()
        refs |= set(re.findall(r"`((?:knowledge|playbooks|materials)/[^`]+\.(?:md|csv))`", text))
    for ref in sorted(refs):
        if os.path.isfile(os.path.join(ROOT, ref)):
            ok(f"引用可落地：{ref}")
        else:
            err(f"引用指向不存在的文件：{ref}")

    # 4 占位符（只扫提示词与知识内容；文档里"讨论占位符"不算）
    bad_patterns = ["TODO", "TBD", "待补", "xxxx", "XXXX", "（略）"]
    scan_dirs = ["agents", "playbooks", "knowledge", "materials"]
    for d in scan_dirs:
        for base, _dd, files in os.walk(os.path.join(ROOT, d)):
            for f in files:
                if not f.endswith(".md"):
                    continue
                p = os.path.join(base, f)
                t = open(p, encoding="utf-8").read()
                for b in bad_patterns:
                    if b in t:
                        err(f"{os.path.relpath(p, ROOT)} 含占位符：{b}")

    # 5 路由模拟（关键词规则，与主提示词路由表同构）
    def route(utter: str) -> str:
        rules = [
            ("W8", ["课件", "PPT", "幻灯片"]),
            ("W4", ["学情", "成绩表", "分数段", "失分点", "月考成绩"]),
            ("W3", ["批改", "答卷", "评语", "打分"]),
            ("W2", ["出题", "组卷", "单元测", "细目表", "周练", "专项训练"]),
            ("W6", ["真题", "高考题", "广东卷", "全国卷", "考法"]),
            ("W7", ["配平", "方程式", "离子方程式", "电极反应", "实验方案", "制取", "制备", "实验室制", "合成路线", "工业流程", "平衡常数", "算一下"]),
            ("W5", ["讲一下", "怎么讲", "听不懂", "知识点", "搞混"]),
            ("W1", ["教案", "备课", "教学设计", "学案", "板书"]),
            ("W0", ["帮我看看", "怎么办", "这个"]),
        ]
        for tag, keys in rules:
            if any(k in utter for k in keys):
                return tag
        return "W0"

    for utter, expect in CASES:
        tag = route(utter)
        got = [f for f in os.listdir(os.path.join(ROOT, "playbooks")) if f.startswith(tag)]
        if got and got[0] == expect:
            ok(f"路由命中：{utter} → {expect}")
        else:
            err(f"路由偏差：{utter} → {tag}（期望 {expect}）")

    print("=" * 66)
    print("工作流静态自检")
    print("=" * 66)
    for m in passes:
        print(f"  [PASS] {m}")
    for m in errors:
        print(f"  [FAIL] {m}")
    print("-" * 66)
    print(f"通过 {len(passes)} 项，失败 {len(errors)} 项")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
