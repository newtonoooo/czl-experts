#!/usr/bin/env python3
"""Spec structure linter.

Checks a requirement spec written in Markdown for the failures that make a spec
unbuildable: a missing section, a requirement with no testable acceptance
criterion, an acceptance criterion nobody can pass or fail, a P0 list that is
everything, leftover placeholders, and a missing non-goal list.

Standard library only. Exit code 0 = clean, 1 = blocking issue.

Usage:
    python spec_lint.py 02-需求规格.md [--json]
"""
import argparse
import json
import os
import re
import sys

# (key, 显示名, 匹配标题的正则)
SECTIONS = [
    ("definition", "一句话定义", r"一句话定义|一句话说明"),
    ("goals", "目标", r"^目标|目标（"),
    ("users", "用户与场景", r"用户|场景"),
    ("pool", "需求池", r"需求池|需求清单"),
    ("acceptance", "验收标准", r"验收"),
    ("nongoals", "边界与非目标", r"非目标|边界|不做什么"),
    ("constraints", "约束与假设", r"约束|假设"),
    ("open", "开放问题", r"开放问题|待确认"),
    ("scope", "范围台账", r"范围台账|范围变更"),
]

PLACEHOLDER = re.compile(r"待补充|待填写|TBD|TODO|XXX|xxx|……\s*$|\?\?\?")
VAGUE = ("流畅", "友好", "快速", "强大", "易用", "智能", "高效", "稳定", "美观")
REQ_RE = re.compile(r"\bREQ-(\d{1,3})\b")
AC_RE = re.compile(r"\bAC-(\d{1,3})\.(\d{1,3})\b")


def load_sections(text):
    """Split markdown into {heading_text: body} using level 2/3 headings."""
    lines = text.splitlines()
    sections, current, buf = [], None, []
    for line in lines:
        m = re.match(r"^(#{2,4})\s+(.*)$", line)
        if m:
            if current is not None:
                sections.append((current, "\n".join(buf)))
            current, buf = m.group(2).strip(), []
        else:
            if current is not None:
                buf.append(line)
    if current is not None:
        sections.append((current, "\n".join(buf)))
    return sections


def find_section(sections, pattern):
    for title, body in sections:
        clean = re.sub(r"^[0-9０-９]+\s*[.、)）]?\s*", "", title).strip()
        if re.search(pattern, clean):
            return title, body
    return None, ""


def table_rows(body):
    rows = []
    for line in body.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        if re.match(r"^\|[\s:\-\|]+\|$", s):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if cells and re.fullmatch(r"编号|序号|ID|id|项目", cells[0]):
            continue
        rows.append(cells)
    return rows


def lint(path):
    text = open(path, "r", encoding="utf-8-sig").read()
    sections = load_sections(text)
    errors, warnings = [], []

    missing = [name for key, name, pat in SECTIONS if find_section(sections, pat)[0] is None]
    for name in missing:
        errors.append("缺少章节：%s" % name)

    _, pool_body = find_section(sections, r"需求池|需求清单")
    _, acc_body = find_section(sections, r"验收")
    _, ng_body = find_section(sections, r"非目标|边界|不做什么")

    pool_rows = table_rows(pool_body)
    pool_ids = []
    for cells in pool_rows:
        joined = " ".join(cells)
        m = REQ_RE.search(joined)
        if m:
            pool_ids.append("REQ-%s" % m.group(1))

    dupes = {i for i in pool_ids if pool_ids.count(i) > 1}
    for d in sorted(dupes):
        errors.append("需求编号重复：%s" % d)
    if not pool_ids:
        errors.append("需求池里没有 REQ 编号行")

    ac_pairs = [(int(a), int(b)) for a, b in AC_RE.findall(text)]
    ac_parents = {p for p, _ in ac_pairs}
    for rid in pool_ids:
        num = int(rid.split("-")[1])
        if num not in ac_parents:
            errors.append("%s 没有验收标准（缺 AC-%02d.x）" % (rid, num))
    for parent in sorted(ac_parents):
        if parent not in {int(r.split("-")[1]) for r in pool_ids}:
            errors.append("AC-%02d.x 挂在不存在的 REQ-%02d 上" % (parent, parent))

    ac_lines = []
    for line in acc_body.splitlines():
        if AC_RE.search(line) or re.match(r"^\s*-\s*\[[ x]\]", line):
            ac_lines.append(line.strip())
    if not ac_lines:
        errors.append("验收标准章节没有任何 AC 条目")
    for line in ac_lines:
        has_gwt = ("given" in line.lower() and "then" in line.lower())
        has_check = bool(re.match(r"^\s*-\s*\[[ x]\]", line))
        if not (has_gwt or has_check):
            warnings.append("验收条目缺少 Given/When/Then 或检查清单格式：%s" % line[:40])
        if re.search(r"[\u4e00-\u9fa5]", line) and not re.search(r"\d", line):
            warnings.append("验收条目无任何数值/界值，可能不可测：%s" % line[:40])

    ng_items = [c for c in table_rows(ng_body) if " ".join(c).strip()]
    ng_bullets = [l for l in ng_body.splitlines() if re.match(r"^\s*[-*]\s+\S", l)]
    if len(ng_items) + len(ng_bullets) < 3:
        errors.append("非目标少于 3 条（当前 %d 条）" % (len(ng_items) + len(ng_bullets)))

    for m in PLACEHOLDER.finditer(text):
        line_no = text[:m.start()].count("\n") + 1
        errors.append("第 %d 行残留占位符：%s" % (line_no, m.group(0)))

    for line in ac_lines:
        for w in VAGUE:
            if w in line and not re.search(r"\d", line):
                warnings.append("验收条目含不可测形容词「%s」且无数值：%s" % (w, line[:40]))

    p0 = sum(1 for cells in pool_rows if " ".join(cells).upper().find("P0") >= 0)
    if pool_ids and p0 > len(pool_ids) / 2:
        errors.append("P0 占比过高：%d/%d，等于没有优先级" % (p0, len(pool_ids)))

    for cells in pool_rows:
        joined = " ".join(cells)
        if REQ_RE.search(joined) and "EVD-" not in joined and "假设" not in joined:
            warnings.append("需求缺依据（EVD 编号或显式假设）：%s" % joined[:40])

    return errors, warnings, {
        "requirements": len(pool_ids),
        "acceptance": len(ac_lines),
        "nongoals": len(ng_items) + len(ng_bullets),
        "p0": p0,
        "sections_found": len(SECTIONS) - len(missing),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Requirement spec linter")
    ap.add_argument("file")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if not os.path.exists(args.file):
        print("[ERR] 找不到文件：%s" % args.file)
        return 1

    errors, warnings, stats = lint(args.file)
    if args.json:
        print(json.dumps({"errors": errors, "warnings": warnings, "stats": stats},
                         ensure_ascii=False, indent=2))
    else:
        print("规格校验  %s" % os.path.basename(args.file))
        print("  章节 %d/9  需求 %d  验收 %d  非目标 %d  P0 %d"
              % (stats["sections_found"], stats["requirements"],
                 stats["acceptance"], stats["nongoals"], stats["p0"]))
        for w in warnings:
            print("[WARN] %s" % w)
        for e in errors:
            print("[ERR] %s" % e)
        print("结果：%s" % ("通过" if not errors else "存在 %d 个阻断项" % len(errors)))

    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
