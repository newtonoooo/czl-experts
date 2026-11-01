#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""blueprint.py — 双向细目表生成与校验

用法：
    python blueprint.py --spec spec.json --out 细目表.md
    python blueprint.py --spec spec.json --print          # 只打印不落盘

spec.json 结构：
{
  "title": "高一上 Unit 3 单元测",
  "total_score": 100,
  "difficulty_target": {"易": 0.5, "中": 0.3, "难": 0.2},
  "sections": [
    {"name": "阅读理解", "type": "阅读", "items": 12, "points": 2.5,
     "points_pool": ["细节理解", "推理判断", "主旨大意", "词义猜测"],
     "difficulty": {"易": 6, "中": 4, "难": 2},
     "note": "三篇，每篇四题"}
  ]
}

退出码：0 正常（可含 WARN），2 配置错误。
"""
import argparse
import json
import sys
from pathlib import Path

LEVELS = ["易", "中", "难"]
DEFAULT_TARGET = {"易": 0.5, "中": 0.3, "难": 0.2}


def _to_int_counts(raw, n):
    """把难度配置规整为 n 题的整数分档；缺省时按 5:3:2 分配。"""
    if not isinstance(raw, dict) or not raw:
        base = {lvl: DEFAULT_TARGET[lvl] * n for lvl in LEVELS}
    else:
        base = {}
        for lvl in LEVELS:
            try:
                base[lvl] = max(0.0, float(raw.get(lvl, 0)))
            except (TypeError, ValueError):
                base[lvl] = 0.0
    total = sum(base.values())
    if total <= 0:
        base = {lvl: DEFAULT_TARGET[lvl] * n for lvl in LEVELS}
        total = sum(base.values())

    scaled = {lvl: base[lvl] * n / total for lvl in LEVELS}
    counts = {lvl: int(scaled[lvl]) for lvl in LEVELS}
    remain = n - sum(counts.values())
    # 余数按小数部分从大到小补齐，保证合计等于题量
    order = sorted(LEVELS, key=lambda x: (scaled[x] - counts[x]), reverse=True)
    i = 0
    while remain > 0:
        counts[order[i % len(order)]] += 1
        remain -= 1
        i += 1
    return counts


def _interleave(counts):
    """把分档数量均匀铺开，避免难度扎堆在卷首或卷尾。"""
    buckets = {lvl: counts[lvl] for lvl in LEVELS}
    seq = []
    while any(buckets[lvl] > 0 for lvl in LEVELS):
        for lvl in LEVELS:
            if buckets[lvl] > 0:
                seq.append(lvl)
                buckets[lvl] -= 1
    return seq


def build(spec):
    sections = spec.get("sections") or []
    if not sections:
        raise ValueError("spec.sections 为空，至少需要一个板块")

    rows = []
    no = 1
    for sec in sections:
        name = str(sec.get("name") or "未命名板块").strip()
        qtype = str(sec.get("type") or name).strip()
        try:
            items = int(sec.get("items", 0))
            points = float(sec.get("points", 0))
        except (TypeError, ValueError):
            raise ValueError(f"板块「{name}」的 items/points 必须是数字")
        if items <= 0 or points <= 0:
            raise ValueError(f"板块「{name}」题量与分值必须大于 0")

        pool = [str(p).strip() for p in (sec.get("points_pool") or []) if str(p).strip()]
        if not pool:
            pool = [name]

        counts = _to_int_counts(sec.get("difficulty"), items)
        levels = _interleave(counts)

        for k in range(items):
            rows.append({
                "no": no,
                "section": name,
                "type": qtype,
                "point": pool[k % len(pool)],
                "level": levels[k],
                "points": points,
                "note": str(sec.get("note") or "").strip(),
            })
            no += 1
    return rows


def summarize(rows, spec):
    total_items = len(rows)
    total_score = sum(r["points"] for r in rows)
    level_counts = {lvl: sum(1 for r in rows if r["level"] == lvl) for lvl in LEVELS}
    level_ratio = {lvl: (level_counts[lvl] / total_items if total_items else 0) for lvl in LEVELS}

    target = spec.get("difficulty_target") or DEFAULT_TARGET
    try:
        target = {lvl: float(target.get(lvl, DEFAULT_TARGET[lvl])) for lvl in LEVELS}
    except (TypeError, ValueError):
        target = DEFAULT_TARGET
    tsum = sum(target.values()) or 1.0
    target = {lvl: target[lvl] / tsum for lvl in LEVELS}

    point_counts = {}
    for r in rows:
        point_counts[r["point"]] = point_counts.get(r["point"], 0) + 1

    warnings = []
    declared = spec.get("total_score")
    if declared is not None:
        try:
            declared = float(declared)
            if abs(declared - total_score) > 1e-6:
                warnings.append(
                    f"分值合计 {total_score:g} 与声明的 total_score {declared:g} 不一致，差值 {total_score - declared:+g}"
                )
        except (TypeError, ValueError):
            warnings.append("total_score 不是数字，已跳过校验")

    for lvl in LEVELS:
        if abs(level_ratio[lvl] - target[lvl]) > 0.05:
            warnings.append(
                f"{lvl}题占比 {level_ratio[lvl]:.0%}，目标 {target[lvl]:.0%}，偏差超过 5 个百分点"
            )

    for point, cnt in point_counts.items():
        if cnt > max(3, total_items * 0.3):
            warnings.append(f"考点「{point}」出现 {cnt} 次，占比过高，建议拆分设问角度")

    return {
        "total_items": total_items,
        "total_score": total_score,
        "level_counts": level_counts,
        "level_ratio": level_ratio,
        "target": target,
        "warnings": warnings,
    }


def render(rows, summary, spec):
    title = str(spec.get("title") or "双向细目表").strip()
    out = [f"# {title} · 双向细目表", ""]
    note = str(spec.get("note") or "").strip()
    if note:
        out += [f"> {note}", ""]

    out += ["| 题号 | 板块 | 题型 | 考点 | 难度 | 分值 | 情境/备注 |",
            "|---|---|---|---|---|---|---|"]
    for r in rows:
        cell = dict(r)
        cell["note"] = r["note"] or "—"
        out.append(
            "| {no} | {section} | {type} | {point} | {level} | {points:g} | {note} |".format(**cell)
        )

    out += ["", "## 汇总", ""]
    out.append(f"- 题量：{summary['total_items']} 题")
    out.append(f"- 总分：{summary['total_score']:g} 分")
    lv = summary["level_counts"]
    ratio = summary["level_ratio"]
    tgt = summary["target"]
    out.append(
        "- 难度分布：易 {e} 题（{er:.0%}）/ 中 {m} 题（{mr:.0%}）/ 难 {d} 题（{dr:.0%}）".format(
            e=lv["易"], er=ratio["易"], m=lv["中"], mr=ratio["中"], d=lv["难"], dr=ratio["难"]
        )
    )
    out.append(
        "- 目标配比：易 {a:.0%} / 中 {b:.0%} / 难 {c:.0%}".format(a=tgt["易"], b=tgt["中"], c=tgt["难"])
    )

    out += ["", "## 校验", ""]
    if summary["warnings"]:
        for w in summary["warnings"]:
            out.append(f"- ⚠️ {w}")
        out.append("")
        out.append("结论：存在需人工确认项，调整后可重新生成。")
    else:
        out.append("- ✅ 题量、分值、难度配比、考点分布均通过校验。")
    out.append("")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="生成双向细目表并校验题量/分值/难度配比")
    ap.add_argument("--spec", required=True, help="spec.json 路径")
    ap.add_argument("--out", help="输出 markdown 路径")
    ap.add_argument("--print", dest="to_stdout", action="store_true", help="打印到标准输出")
    args = ap.parse_args(argv)

    spec_path = Path(args.spec)
    if not spec_path.exists():
        print(f"[ERROR] 找不到配置文件：{spec_path}", file=sys.stderr)
        return 2
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[ERROR] spec.json 不是合法 JSON：{e}", file=sys.stderr)
        return 2

    try:
        rows = build(spec)
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 2

    summary = summarize(rows, spec)
    text = render(rows, summary, spec)

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"[OK] 已生成：{args.out}（{summary['total_items']} 题 / {summary['total_score']:g} 分）")
    if args.to_stdout or not args.out:
        print(text)
    if summary["warnings"]:
        print(f"[WARN] {len(summary['warnings'])} 项需确认", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
