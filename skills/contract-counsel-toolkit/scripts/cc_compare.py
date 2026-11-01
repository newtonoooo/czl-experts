#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
W3 比对台：原版 vs 新版 -> 实质变更分级 + 谈判清单

方法：
1. 两版分别切条
2. 优先按“第X条”条号对齐；条号体系差异过大时按顺序对齐
3. 逐条算文本相似度，并抽取“数值+单位”做精确比对（金额、比例、天数、月数）
4. 分级：数值变动或核心利益条款实质改写 -> 重大；表述强化、流程细节 -> 一般；措辞润色 -> 轻微
5. 纯排版、标点、空白差异不计入变更清单
"""

import difflib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from cc_common import ensure_dir, read_text_any, split_clauses, write_json, write_text  # noqa: E402

NUM_UNIT = re.compile(
    r"(\d+(?:\.\d+)?)\s*(个工作日|个月|个|万元|元|工作日|日内|日|天|年|倍|小时|份|台|套|件|人|次|%)"
)

CORE_KEYWORDS = [
    ("违约金", 10), ("赔偿", 9), ("管辖", 8), ("解除", 8), ("付款", 8), ("支付", 7),
    ("价款", 8), ("金额", 7), ("交付", 6), ("验收", 5), ("质保", 5), ("保修", 4),
    ("知识产权", 7), ("保密", 5), ("期限", 4), ("定金", 6), ("押金", 6), ("利率", 7),
]

LEVEL_LABEL = {"major": "重大", "normal": "一般", "minor": "轻微"}


def _numbers(text):
    text = re.sub(r"(?<=\d),(?=\d)", "", text or "")  # 500,000 -> 500000
    out = set()
    for value, unit in NUM_UNIT.findall(text):
        out.add("%s%s" % (value, unit))
    return out


def _core_score(text):
    return sum(w for kw, w in CORE_KEYWORDS if kw in text)


def _clip(text, n=110):
    text = re.sub(r"\s+", " ", (text or "").strip())
    return text if len(text) <= n else text[:n] + "…"


def _align(pa, pb):
    """返回 [(key, clause_a_or_None, clause_b_or_None)]"""
    ca, cb = pa["clauses"], pb["clauses"]
    ka = {c["key"]: c for c in ca}
    kb = {c["key"]: c for c in cb}
    keys_a, keys_b = [c["key"] for c in ca], [c["key"] for c in cb]
    overlap = len(set(keys_a) & set(keys_b)) / max(1, min(len(keys_a), len(keys_b)))

    if overlap >= 0.6:
        ordered = list(keys_a) + [k for k in keys_b if k not in set(keys_a)]
        return [(k, ka.get(k), kb.get(k)) for k in ordered], "按条号对齐"

    pairs = []
    for i in range(max(len(ca), len(cb))):
        a = ca[i] if i < len(ca) else None
        b = cb[i] if i < len(cb) else None
        pairs.append(((a or b)["key"], a, b))
    return pairs, "按顺序对齐（两版条号体系不一致）"


def compare_texts(a_text, b_text, name_a="原版", name_b="新版"):
    pa, pb = split_clauses(a_text), split_clauses(b_text)
    pairs, align_mode = _align(pa, pb)

    changes = []
    stats = {"added": 0, "removed": 0, "major": 0, "normal": 0, "minor": 0, "unchanged": 0}

    for key, a, b in pairs:
        if a and not b:
            stats["removed"] += 1
            stats["major"] += 1
            changes.append({
                "kind": "删除", "level": "major", "clause": key,
                "title": a.get("title", ""), "before": _clip(a["text"]), "after": "",
                "impact": "新版删除了该条，原版赋予的权利或义务随之消失，需确认是否为有意删除。",
                "numbers": [],
            })
            continue
        if b and not a:
            stats["added"] += 1
            added_level = "major" if _core_score(b["text"]) >= 6 else "normal"
            stats[added_level] += 1
            changes.append({
                "kind": "新增", "level": added_level,
                "clause": key, "title": b.get("title", ""), "before": "", "after": _clip(b["text"]),
                "impact": "新版新增条款，需确认是否增加了己方义务或限制了己方权利。",
                "numbers": [],
            })
            continue

        ta = re.sub(r"\s+", "", a["text"])
        tb = re.sub(r"\s+", "", b["text"])
        if ta == tb:
            stats["unchanged"] += 1
            continue

        ratio = difflib.SequenceMatcher(None, ta, tb).ratio()
        num_a, num_b = _numbers(a["text"]), _numbers(b["text"])
        num_added = sorted(num_b - num_a)
        num_removed = sorted(num_a - num_b)
        num_changed = num_added or num_removed
        # 甲乙方指向翻转（如管辖从甲方所在地改成乙方所在地）比数字更隐蔽，单独识别
        place_a = re.findall(r"(甲方|乙方)所在地", a["text"])
        place_b = re.findall(r"(甲方|乙方)所在地", b["text"])
        flip = bool(place_a and place_b and place_a != place_b)
        if not flip:
            scope = a["text"] + b["text"]
            if any(k in scope for k in ("解除", "管辖", "付款", "支付", "违约金")):
                flip = (a["text"].count("甲方") != b["text"].count("甲方")) or (
                    a["text"].count("乙方") != b["text"].count("乙方"))

        if num_changed or flip:
            level = "major"
        elif ratio < 0.90 and max(_core_score(a["text"]), _core_score(b["text"])) >= 6:
            level = "major"
        elif ratio < 0.95:
            level = "normal"
        else:
            level = "minor"

        if level == "major":
            stats["major"] += 1
        elif level == "normal":
            stats["normal"] += 1
        else:
            stats["minor"] += 1

        impl = []
        if num_added:
            impl.append("新增数值：%s" % "、".join(num_added))
        if num_removed:
            impl.append("删除数值：%s" % "、".join(num_removed))
        if flip:
            impl.append("甲乙方指向发生变化，义务主体可能被调换")
        if ratio < 0.6:
            impl.append("条款实质改写，需逐句比对权利义务")
        elif ratio < 0.9:
            impl.append("表述有实质变化")

        changes.append({
            "kind": "修改", "level": level, "clause": key,
            "title": b.get("title") or a.get("title", ""),
            "before": _clip(a["text"]), "after": _clip(b["text"]),
            "similarity": round(ratio, 3),
            "numbers": {"added": num_added, "removed": num_removed},
            "impact": "；".join(impl) or "措辞调整，实质影响较小",
        })

    order = {"major": 0, "normal": 1, "minor": 2}
    changes.sort(key=lambda c: (order[c["level"]], c["clause"]))

    majors = [c for c in changes if c["level"] == "major"]
    scored = sorted(majors, key=lambda c: -(_core_score(c["before"] + c["after"]) + len(c.get("numbers", {}).get("added", [])) * 3))
    negotiation = [
        {
            "clause": c["clause"],
            "topic": c["title"] or c["kind"],
            "issue": c["impact"],
            "suggestion": _suggest(c),
        }
        for c in scored[:3]
    ]

    return {
        "ok": True,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "align_mode": align_mode,
        "name_a": name_a,
        "name_b": name_b,
        "clause_count": {"a": len(pa["clauses"]), "b": len(pb["clauses"])},
        "stats": stats,
        "changes": changes,
        "negotiation": negotiation,
    }


def _suggest(change):
    nums = change.get("numbers", {})
    if nums.get("added") and nums.get("removed"):
        return "把数值退回可接受区间（原为 %s，对方改为 %s），并同步核对连带条款（付款、质保、上限）。" % (
            "、".join(nums["removed"]), "、".join(nums["added"]))
    if nums.get("added"):
        return "对方新增了 %s，确认是否会显著增加己方成本或责任；必要时要求对等约束。" % "、".join(nums["added"])
    if change["kind"] == "删除":
        return "确认删除是否有替代安排；若该条保护的是己方权利，要求恢复或换一种写法保留。"
    if change["kind"] == "新增":
        return "逐句看新增义务是否单向；要求补充对应的对方义务或明确适用条件。"
    return "要求对方说明改动理由；对己方不利的表述恢复到原版，或加入对等限制。"


def render_markdown(result):
    s = result["stats"]
    lines = ["# 版本比对报告", ""]
    lines.append("- 原版（A）：%s" % result["name_a"])
    lines.append("- 新版（B）：%s" % result["name_b"])
    lines.append("- 对齐方式：%s" % result["align_mode"])
    lines.append("- 条款数量：A %d 条 / B %d 条" % (result["clause_count"]["a"], result["clause_count"]["b"]))
    lines.append("- 生成时间：%s" % result["generated_at"])
    lines.append("")
    lines.append("## 变更全景")
    lines.append("")
    total = len(result["changes"])
    modified = total - s["added"] - s["removed"]
    lines.append("共 %d 处变更：新增 %d 条、删除 %d 条、修改 %d 条；按影响分 重大 %d / 一般 %d / 轻微 %d，未变 %d 条。" % (
        total, s["added"], s["removed"], modified, s["major"], s["normal"], s["minor"], s["unchanged"]))
    lines.append("")

    majors = [c for c in result["changes"] if c["level"] == "major"]
    if majors:
        lines.append("## 重大变更")
        lines.append("")
        lines.append("| 位置 | 类型 | 原版 | 新版 | 影响 |")
        lines.append("|---|---|---|---|---|")
        for c in majors:
            lines.append("| %s | %s | %s | %s | %s |" % (
                c["clause"], c["kind"],
                (c["before"] or "—").replace("|", "／"),
                (c["after"] or "—").replace("|", "／"),
                c["impact"].replace("|", "／")))
        lines.append("")

    normal = [c for c in result["changes"] if c["level"] == "normal"]
    if normal:
        lines.append("## 一般变更")
        lines.append("")
        for c in normal:
            lines.append("- **%s %s**（%s）：%s" % (c["clause"], c["title"][:16], c["kind"], c["impact"]))
        lines.append("")

    minor = [c for c in result["changes"] if c["level"] == "minor"]
    if minor:
        lines.append("## 轻微变更")
        lines.append("")
        lines.append("共 %d 处，主要为措辞与顺序调整，不影响权利义务：" % len(minor))
        lines.append("、".join(c["clause"] for c in minor))
        lines.append("")

    if result["negotiation"]:
        lines.append("## 谈判清单（优先谈这 %d 条）" % len(result["negotiation"]))
        lines.append("")
        for i, n in enumerate(result["negotiation"], 1):
            lines.append("### %d. %s %s" % (i, n["clause"], n["topic"]))
            lines.append("")
            lines.append("- 问题：%s" % n["issue"])
            lines.append("- 怎么谈：%s" % n["suggestion"])
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("比对基于文本相似度与数值比对，纯排版、标点、空白差异已被过滤。"
                 "重大变更的“影响”是根据条款主题推断的方向性提示，具体损益仍需结合交易背景判断。")
    lines.append("")
    return "\n".join(lines)


def compare_files(path_a, path_b, out_dir=".contract-workspace"):
    a_text, a_info = read_text_any(path_a)
    b_text, b_info = read_text_any(path_b)
    result = compare_texts(a_text, b_text, name_a=str(path_a), name_b=str(path_b))
    out = ensure_dir(out_dir)
    stem = "%s_vs_%s" % (Path(path_a).stem, Path(path_b).stem)
    md_path = write_text(out / (stem + "_diff.md"), render_markdown(result))
    json_path = write_json(out / (stem + "_diff.json"), result)
    result["report_md"] = md_path
    result["report_json"] = json_path
    result["sources"] = {"a": a_info, "b": b_info}
    return result
