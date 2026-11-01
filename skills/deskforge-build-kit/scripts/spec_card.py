#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
spec_card.py — 收束卡生成与闸门校验

© 2026 虫志龙 · 版权所有 ｜ 授权范围见包内 LICENSE
纯标准库实现：不联网、不装依赖、不上传任何数据。

职责：
  1 把 JSON 需求整理成《收束卡》Markdown
  2 卡住规模闸门：模块 > 4 直接拒绝（退出码 2）
  3 卡住字段闸门：字段缺类型/缺示例/卡原语非法，逐条报出

用法：
  python spec_card.py --input 需求.json --out 收束卡.md
  python spec_card.py --input 需求.json            # 打到标准输出
  python spec_card.py --init 需求模板.json          # 生成空白模板
  python spec_card.py --input 需求.json --json      # 只输出校验结果

退出码：0 通过 ｜ 1 有警告 ｜ 2 有错误（含模块超限）
"""

import argparse
import json
import sys
from pathlib import Path

CARDS = {
    "list": "清单卡",
    "matrix": "矩阵卡",
    "form": "表单卡",
    "metric": "指标卡",
    "time": "时间卡",
}
TYPES = {"text", "number", "date", "enum", "bool"}
MAX_MODULES = 4

TEMPLATE = {
    "app": "（台子名，例：备考打卡台）",
    "need": "（用户原话，例：每天记刷题量和错题，倒计时到考前）",
    "user": "本人",
    "assumptions": ["（推断项，例：默认手机为主，双端适配）"],
    "modules": [
        {
            "name": "今日待办",
            "card": "list",
            "fill": "任务名、截止日",
            "see": "今天与逾期两条泳道",
            "judge": "先做哪一件",
            "fields": [
                {"name": "title", "type": "text", "example": "整理错题本", "required": True},
                {"name": "due", "type": "date", "example": "今天-1", "required": False},
                {"name": "done", "type": "bool", "example": False, "required": True},
            ],
        }
    ],
    "not_doing": ["（本期砍掉的块 + 原因）"],
    "phases": [{"stage": "下期", "content": "（放下一期的模块）", "why": "（为什么放后面）"}],
}


def validate(spec):
    errors, warnings = [], []
    modules = spec.get("modules") or []
    if not spec.get("app"):
        errors.append("缺 app（台子名）")
    if not spec.get("need"):
        warnings.append("缺 need（用户原话），收束卡无法回溯需求")
    if not modules:
        errors.append("modules 为空")
    if len(modules) > MAX_MODULES:
        errors.append(f"模块数 {len(modules)} 超过上限 {MAX_MODULES}：先出分期方案，本期只做 {MAX_MODULES} 块以内")
    for i, m in enumerate(modules, 1):
        tag = f"模块{i}「{m.get('name', '未命名')}」"
        for key, label in (("name", "名称"), ("fill", "填什么"), ("see", "看到什么"), ("judge", "据此判断什么")):
            if not str(m.get(key, "")).strip():
                errors.append(f"{tag} 缺 {label}（三问必须都答得出）")
        card = m.get("card", "")
        if card not in CARDS:
            errors.append(f"{tag} 的卡原语 “{card}” 非法，只能是 {'/'.join(CARDS)}")
        fl = m.get("fields") or []
        if not fl:
            errors.append(f"{tag} 没有字段")
        for f in fl:
            fn = f.get("name", "?")
            if not fn:
                errors.append(f"{tag} 存在无名字段")
            ft = f.get("type", "")
            if ft not in TYPES:
                errors.append(f"{tag} 字段 “{fn}” 类型 “{ft}” 非法，只能是 {'/'.join(sorted(TYPES))}")
            if "example" not in f:
                warnings.append(f"{tag} 字段 “{fn}” 缺示例值")
            if ft == "enum" and not f.get("values"):
                errors.append(f"{tag} 枚举字段 “{fn}” 未列出取值")
        if card == "metric" and not str(m.get("kpi", "")).strip():
            warnings.append(f"{tag} 是指标卡但没有写明口径（kpi：sum/count/avg7/ratio）")
    if len(modules) > MAX_MODULES and not spec.get("phases"):
        errors.append("模块超限且没有 phases 分期表：必须给出本期/下期边界")
    forms = [m for m in modules if m.get("card") == "form"]
    lists = [m for m in modules if m.get("card") == "list"]
    if forms and not lists:
        warnings.append("有表单卡但没有清单卡承接：填进去的数据没地方被看见")
    return errors, warnings


def render(spec):
    mods = spec.get("modules") or []
    L = []
    L.append(f"# 收束卡 · {spec.get('app','')} · {spec.get('_date','')}")
    L.append("")
    L.append(f"**一句话**：给{spec.get('user','本人')}用的{spec.get('app','')}，解决“{spec.get('need','')}”。")
    L.append("")
    L.append("**本次假设**：")
    for a in spec.get("assumptions") or ["（无）"]:
        L.append(f"- {a}")
    L.append("")
    L.append(f"## 一、模块表（{len(mods)} 块）")
    L.append("")
    L.append("| # | 模块名 | 主卡 | 填什么 | 看到什么 | 据此判断什么 |")
    L.append("|---|---|---|---|---|---|")
    for i, m in enumerate(mods, 1):
        card = CARDS.get(m.get("card", ""), m.get("card", ""))
        L.append(f"| {i} | {m.get('name','')} | {card} | {m.get('fill','')} | {m.get('see','')} | {m.get('judge','')} |")
    L.append("")
    L.append("## 二、顶栏「今天要处理」")
    L.append(spec.get("top_bar") or "供料：各模块的逾期项与今日项；规则：逾期标红、昨日未完成自动滚入今天、每条一个完成按钮。")
    L.append("")
    L.append("## 三、字段草案")
    for i, m in enumerate(mods, 1):
        L.append(f"### {i}. {m.get('name','')}（{CARDS.get(m.get('card',''), '')}）")
        L.append("")
        L.append("| 字段 | 类型 | 取值/单位 | 必填 | 示例 |")
        L.append("|---|---|---|---|---|")
        for f in m.get("fields") or []:
            vals = ",".join(f.get("values", [])) if f.get("type") == "enum" else (f.get("unit", "—"))
            L.append(
                f"| `{f.get('name','')}` | {f.get('type','')} | {vals or '—'} | "
                f"{'是' if f.get('required') else '否'} | {f.get('example','')} |"
            )
        L.append("")
    L.append("## 四、明确不做")
    for x in spec.get("not_doing") or ["（无）"]:
        L.append(f"- {x}")
    L.append("")
    if spec.get("phases"):
        L.append("## 五、分期表")
        L.append("")
        L.append("| 期次 | 内容 | 为什么放这一期 |")
        L.append("|---|---|---|")
        for p in spec["phases"]:
            L.append(f"| {p.get('stage','')} | {p.get('content','')} | {p.get('why','')} |")
        L.append("")
    L.append("---")
    L.append("")
    L.append("闸门：模块 ≤4 ｜ 每块三问可答 ｜ 卡原语合法 ｜ 字段有类型与示例")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="收束卡生成与规模闸门校验（零依赖）")
    ap.add_argument("--input", help="需求 JSON 路径")
    ap.add_argument("--out", help="输出 Markdown 路径；省略则打到标准输出")
    ap.add_argument("--init", help="生成空白需求模板到指定路径后退出")
    ap.add_argument("--json", action="store_true", help="只输出校验结果 JSON")
    args = ap.parse_args()

    if args.init:
        Path(args.init).write_text(json.dumps(TEMPLATE, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"已生成模板：{args.init}")
        return 0

    if not args.input:
        print("需要 --input 或 --init", file=sys.stderr)
        return 3

    src = Path(args.input)
    if not src.exists():
        print(f"找不到文件：{args.input}", file=sys.stderr)
        return 3
    try:
        spec = json.loads(src.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"JSON 解析失败：{e}", file=sys.stderr)
        return 3

    import datetime
    spec.setdefault("_date", datetime.date.today().isoformat())

    errors, warnings = validate(spec)
    if args.json:
        print(json.dumps({"error": errors, "warning": warnings,
                          "modules": len(spec.get("modules") or []),
                          "exit": 2 if errors else (1 if warnings else 0)},
                         ensure_ascii=False, indent=2))
    else:
        for e in errors:
            print(f"[x] {e}", file=sys.stderr)
        for w in warnings:
            print(f"[!] {w}", file=sys.stderr)
        if errors:
            print(f"\n闸门未通过：{len(errors)} 个错误，{len(warnings)} 个警告。先改再出卡。", file=sys.stderr)
        else:
            md = render(spec)
            if args.out:
                Path(args.out).write_text(md, encoding="utf-8")
                print(f"已生成收束卡：{args.out}（{len(spec.get('modules') or [])} 块，{len(warnings)} 个警告）")
            else:
                print(md)

    return 2 if errors else (1 if warnings else 0)


if __name__ == "__main__":
    sys.exit(main())
