#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交付体检：提交前最后一道闸。

原则：只放行没有硬伤的东西。出现阻断项时脚本以退出码 2 结束，
调用方（或人）必须看见它，不能当没发生。

用法：
    python qc_check.py ./标书目录 --client 蜀通 --rubric rubric.txt
    python qc_check.py 标书.md --client 蜀通
    python qc_check.py ./标书目录 --client 蜀通 --allow-blocker   # 只出报告，不返回 2
"""

import argparse
import re
import sys
from pathlib import Path

PLACEHOLDERS = [
    (r"TODO", "TODO 未清"),
    (r"TBD", "TBD 未清"),
    (r"待补", "待补 未清"),
    (r"待确认", "待确认 未清"),
    (r"待定", "待定 未清"),
    (r"【[^】]{0,12}】", "空方括号占位"),
    (r"\{\{[^}]{0,20}\}\}", "模板变量未替换"),
    (r"XX|xx公司|某某", "占位名"),
    (r"示例公司|示例项目", "示例字样"),
    (r"贵公司|贵司", "对客户的口语称呼，标书里应写客户全称"),
    (r"我司|本公司", "自称，正式标书建议用投标人全称或“我方”"),
]

ABSOLUTE = ["最强", "最好", "最优", "唯一", "第一", "顶级", "国家级",
            "保证中标", "百分百", "100%", "零风险", "绝不会", "无条件"]

MONEY_RE = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(万元|元)")
PERIOD_RE = re.compile(r"(\d+)\s*(日历天|个工作日|个日历天|天|个月)")
FIG_RE = re.compile(r"(图|表)\s*(\d+)(?:[-—.](\d+))?")


def collect(path: Path, exts=(".md", ".txt", ".markdown")):
    if path.is_file():
        return [path]
    files = [p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in exts]
    return sorted(files)


def read(p: Path) -> str:
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return p.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return ""


def check_file(p: Path, text: str, client: str, allow_self: bool):
    blockers, warns, notes = [], [], []
    name = p.name

    for pat, label in PLACEHOLDERS:
        if label == "自称，正式标书建议用投标人全称或“我方”" and allow_self:
            continue
        for m in re.finditer(pat, text):
            line = text[:m.start()].count("\n") + 1
            bucket = blockers if label in ("TODO 未清", "TBD 未清", "待补 未清",
                                           "空方括号占位", "模板变量未替换", "占位名") else warns
            bucket.append(f"{name}:{line} {label} → “{m.group(0)[:20]}”")

    if client:
        cnt = text.count(client)
        if cnt == 0:
            blockers.append(f"{name}: 全文没有出现客户名“{client}”，这份文件不是给他写的")
        elif cnt == 1:
            notes.append(f"{name}: 客户名只出现 1 次，检查是否只在封面出现")

    for w in ABSOLUTE:
        if w in text:
            for m in re.finditer(re.escape(w), text):
                line = text[:m.start()].count("\n") + 1
                blockers.append(f"{name}:{line} 绝对化/越界承诺 → “{w}”")

    # 金额一致性
    monies = {}
    for m in MONEY_RE.finditer(text):
        val = m.group(1).replace(",", "")
        unit = m.group(2)
        key = f"{val}{unit}"
        monies[key] = monies.get(key, 0) + 1
    if len(monies) > 1:
        warns.append(f"{name}: 金额写法 {len(monies)} 种（"
                     + "、".join(list(monies)[:6]) + "），确认是否为同一笔钱的不同写法")

    # 工期一致性
    periods = {}
    for m in PERIOD_RE.finditer(text):
        k = f"{m.group(1)}{m.group(2)}"
        periods[k] = periods.get(k, 0) + 1
    if len(periods) > 3:
        warns.append(f"{name}: 工期/时限写法有 {len(periods)} 种（"
                     + "、".join(list(periods)[:6]) + "），确认是否存在口径混用")

    # 图表编号
    figs, tabs = {}, {}
    for m in FIG_RE.finditer(text):
        kind, num = m.group(1), int(m.group(2))
        target = figs if kind == "图" else tabs
        target.setdefault(num, 0)
        target[num] += 1
    for kind, d in (("图", figs), ("表", tabs)):
        if not d:
            continue
        nums = sorted(d)
        dup = [n for n, c in d.items() if c > 1]
        missing = [n for n in range(nums[0], nums[-1] + 1) if n not in d]
        if dup:
            warns.append(f"{name}: {kind}编号重复 {dup}")
        if missing:
            warns.append(f"{name}: {kind}编号缺 {missing}")
    return blockers, warns, notes


def check_rubric(text_all: str, rubric_path: Path):
    """按评分项在正文里找落点。找不到只算警告——章节怎么命名是人决定的。"""
    warns, notes = [], []
    items = [l.strip() for l in read(rubric_path).splitlines() if l.strip()]
    for it in items:
        parts = [p for p in re.split(r"[与和、及/]", it) if len(p) >= 2]
        hit = [p for p in parts if p in text_all]
        if not hit:
            warns.append(f"评分项“{it}”在正文里找不到落点（试过：{'、'.join(parts)}）")
        else:
            notes.append(f"评分项“{it}”落点命中：{'、'.join(hit)}")
    return warns, notes


def main():
    ap = argparse.ArgumentParser(description="交付体检")
    ap.add_argument("target", help="标书目录或单个文件")
    ap.add_argument("--client", default="", help="客户全称，用于一致性检查")
    ap.add_argument("--rubric", default=None, help="评分项清单（每行一项）")
    ap.add_argument("--allow-self", action="store_true",
                    help="允许出现“我司/本公司”（有些行业习惯这么写）")
    ap.add_argument("--allow-blocker", action="store_true",
                    help="有阻断项时仍返回 0（只出报告）")
    ap.add_argument("--md", default=None, help="报告输出路径")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    target = Path(args.target)
    if not target.exists():
        raise SystemExit(f"路径不存在: {target}")

    files = collect(target)
    if not files:
        raise SystemExit("没有找到 .md / .txt 文件")

    all_blockers, all_warns, all_notes = [], [], []
    text_all = ""
    total_chars = 0
    for p in files:
        t = read(p)
        text_all += t + "\n"
        total_chars += len(re.sub(r"\s", "", t))
        b, w, n = check_file(p, t, args.client, args.allow_self)
        all_blockers += b
        all_warns += w
        all_notes += n

    rubric_notes = []
    if args.rubric:
        rw, rn = check_rubric(text_all, Path(args.rubric))
        all_warns += rw
        rubric_notes = rn

    lines = ["# 交付体检报告", ""]
    verdict = "不通过，存在阻断项" if all_blockers else "通过（未发现阻断项）"
    lines.append(f"**结论：{verdict}**")
    lines.append("")
    lines.append(f"- 检查文件 {len(files)} 个，合计 {total_chars} 字")
    lines.append(f"- 阻断 {len(all_blockers)} 项，警告 {len(all_warns)} 项，提示 {len(all_notes)} 项")
    lines.append("")

    def block(title, items):
        lines.append(f"## {title}")
        lines.append("")
        if not items:
            lines.append("无。")
        else:
            for i in items[:60]:
                lines.append(f"- {i}")
            if len(items) > 60:
                lines.append(f"- …另有 {len(items) - 60} 项，见命令行输出")
        lines.append("")

    block("阻断项（改完才能提交）", all_blockers)
    block("警告（建议改）", all_warns)
    if rubric_notes:
        block("评分项覆盖", rubric_notes)
    block("提示", all_notes)

    lines += ["---", "",
              "本报告只覆盖能自动检查的部分：占位符、绝对化用语、客户名、编号、金额写法、评分项覆盖。",
              "**不覆盖**：格式与密封要求、签章位置、电子标上传规则、资质原件、是否需要公证。"
              "这些必须人工对照招标文件逐条核对，脚本默认它们是「未验证」，不是「通过」。"]

    md = "\n".join(lines)
    print(md)
    if args.md:
        Path(args.md).write_text(md, encoding="utf-8")
        print(f"\n已写出：{args.md}")

    if all_blockers and not args.allow_blocker:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
