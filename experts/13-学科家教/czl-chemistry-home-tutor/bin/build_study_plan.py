#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把学情诊断结果生成为一份六周计划（Markdown）。

用法：
    python build_study_plan.py --profile profile.json --out 计划.md
    python build_study_plan.py --demo

profile.json 示例：
{
  "student": "学生A",
  "grade": "高二",
  "edition": "人教版",
  "exam": "等级考",
  "focus": ["E3", "E4"],
  "daily_minutes": 25,
  "note": "方程式漏条件为主，计算倒在单位换算"
}

设计约束：
  · 一周只改一个编码，不允许并列主攻方向
  · 每个编码只给一个每日动作和一个可观测的过关标准
  · 不输出分数目标，不输出"提分承诺"
"""

import argparse
import json
import sys

ACTIONS = {
    "E1": {
        "name": "概念模型错",
        "daily": "每天用 5 分钟复述一个模型：谁在动、受什么影响、边界在哪；再配 1 道换情境的小题",
        "pass": "能不看笔记把这个模型讲给家长听，且能说出一个不适用的情况",
        "parent": "只听，不纠正；讲不下去就记下来交给老师",
    },
    "E2": {
        "name": "化学用语不规范",
        "daily": "每天写 5 个方程式，写完按检查表盯一项（本周只盯这一项，如 ↑↓）",
        "pass": "连续 5 天，这一项的遗漏不超过 1 处",
        "parent": "只检查符号这一项，别顺手指错配平",
    },
    "E3": {
        "name": "方程式与配平",
        "daily": "每天 3 个改错 + 1 个新写，只练同一类反应（如氧化还原），写完查原子、电荷、电子",
        "pass": "同型题 5 个里至少 4 个三项全过",
        "parent": "不判对错，只问“三项都查了吗”",
    },
    "E4": {
        "name": "定量关系错",
        "daily": "每天 1 道计算，只写四步（设—列—代—验），单位必须写在数字后面",
        "pass": "连续 3 天，四步齐全且单位无遗漏",
        "parent": "掐时间 15 分钟，到点停笔",
    },
    "E5": {
        "name": "推断断链",
        "daily": "每天 1 道推断，先只做第一步：把题眼抄成表，写出每个现象的 1—3 个候选",
        "pass": "能说出切入点在哪、为什么是唯一候选",
        "parent": "不提示答案，只问“你先从哪一句看出来的”",
    },
    "E6": {
        "name": "流程目的读不懂",
        "daily": "每天 1 道流程题，只做四段拆解表，不写方程式",
        "pass": "每一段都能用一句话说出“除什么、为什么这么除”",
        "parent": "听孩子讲流程，讲不通的地方记下来",
    },
    "E7": {
        "name": "实验操作与装置",
        "daily": "每天画一个装置图，标出发生、净化、收集、尾气四处；口述气密性检查四句话",
        "pass": "四句话顺序不错，装置四处都能指出来",
        "parent": "让孩子讲给你听，你只当听众",
    },
    "E8": {
        "name": "审题与表达",
        "daily": "每天 2 道主观题，只做一件事：圈出题干限定词，按分值分点作答",
        "pass": "4 分题至少写 3 个点，且每点都带依据",
        "parent": "检查有没有分点，不看内容对错",
    },
}

ORDER = ["E3", "E2", "E8", "E1", "E4", "E5", "E6", "E7"]


def build(profile):
    student = profile.get("student", "学生A")
    grade = profile.get("grade", "高二")
    edition = profile.get("edition", "人教版")
    exam = profile.get("exam", "等级考")
    minutes = profile.get("daily_minutes", 25)
    focus = [c for c in profile.get("focus", []) if c in ACTIONS]
    if not focus:
        focus = ["E2", "E3"]

    # 排序：先修用语与表达，再修模型与推断
    focus = sorted(set(focus), key=lambda c: ORDER.index(c) if c in ORDER else 99)
    primary = focus[0]
    secondary = focus[1] if len(focus) > 1 else None

    lines = []
    lines.append("# 六周化学辅导计划（%s · %s · %s · %s）" % (student, grade, edition, exam))
    lines.append("")
    lines.append("> 生成工具：`bin/build_study_plan.py`　每日投入：%d 分钟" % minutes)
    lines.append("")
    lines.append("**一句话**：这六周只改一件事——%s（%s）。其余问题记下来，不改。"
                 % (primary, ACTIONS[primary]["name"]))
    lines.append("")
    if profile.get("note"):
        lines.append("**诊断备注**：%s" % profile["note"])
        lines.append("")

    lines.append("## 一、周计划")
    lines.append("")
    lines.append("| 周 | 主攻 | 每天做什么 | 怎么算过关 |")
    lines.append("|---|---|---|---|")
    for w in range(1, 7):
        if w <= 3:
            code = primary
            daily = ACTIONS[code]["daily"]
            pas = ACTIONS[code]["pass"]
        elif w <= 5 and secondary:
            code = secondary
            daily = ACTIONS[code]["daily"]
            pas = ACTIONS[code]["pass"]
        elif w == 6:
            code = primary
            daily = "回看前三周的记录，用同一套题重做一遍；只统计“同一类错还剩几处”"
            pas = "能自己说出进步在哪一项、还差哪一项"
        else:
            code = primary
            daily = "限时练：同型题 %d 分钟内完成，做完当场自检" % max(10, minutes)
            pas = "用时达标且正确率不低于第 3 周"
        lines.append("| 第 %d 周 | %s %s | %s | %s |"
                     % (w, code, ACTIONS[code]["name"], daily, pas))
    lines.append("")

    if secondary:
        lines.append("## 二、第二个待改项（第 4—5 周）")
        lines.append("")
        lines.append("- 编码：%s %s" % (secondary, ACTIONS[secondary]["name"]))
        lines.append("- 动作：%s" % ACTIONS[secondary]["daily"])
        lines.append("- 过关：%s" % ACTIONS[secondary]["pass"])
        lines.append("- 注意：第 1—3 周不要碰它，否则两条线都改不动。")
        lines.append("")

    lines.append("## 三、家长配合")
    lines.append("")
    lines.append("| 家长做 | 家长不做 |")
    lines.append("|---|---|")
    lines.append("| %s | 讲题、判对错 |" % ACTIONS[primary]["parent"])
    lines.append("| 每周日打勾，记录完成天数 | 加作业量、比较、许诺奖励 |")
    lines.append("| 只提醒“今天改这一样” | 临时增加新任务 |")
    lines.append("")

    lines.append("## 四、验收（第 6 周末填）")
    lines.append("")
    lines.append("| 指标 | 第 1 周 | 第 6 周 |")
    lines.append("|---|---|---|")
    lines.append("| 同类题错误处数（每 5 题） | | |")
    lines.append("| 步骤齐全率 | | |")
    lines.append("| 独立完成所需时间 | | |")
    lines.append("")
    lines.append("> 两项以上没有变化时，先查“完成天数”，不要先换方法。")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("本计划只给动作与验收标准，不承诺分数。执行中如与学校进度冲突，以学校进度为准。")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="生成六周化学辅导计划")
    ap.add_argument("--profile", help="学情 JSON 文件路径")
    ap.add_argument("--out", help="输出 Markdown 路径；缺省打印到屏幕")
    ap.add_argument("--demo", action="store_true", help="用内置示例生成一份，便于试跑")
    args = ap.parse_args()

    if args.demo:
        profile = {
            "student": "学生A",
            "grade": "高二",
            "edition": "人教版",
            "exam": "等级考",
            "focus": ["E3", "E4"],
            "daily_minutes": 25,
            "note": "方程式漏条件为主，计算倒在单位换算",
        }
    elif args.profile:
        try:
            profile = json.load(open(args.profile, encoding="utf-8"))
        except Exception as e:
            print("读取 profile 失败：%s" % e)
            return 1
    else:
        print("请提供 --profile 或 --demo")
        return 1

    text = build(profile)
    if args.out:
        open(args.out, "w", encoding="utf-8").write(text)
        print("已生成：%s（%d 字符）" % (args.out, len(text)))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
