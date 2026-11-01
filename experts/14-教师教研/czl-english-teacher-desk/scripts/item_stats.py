#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""item_stats.py — 成绩 CSV 统计与失分点定位

用法：
    python item_stats.py --csv scores.csv --full full.json --out 学情.md
    python item_stats.py --csv scores.csv --full full.json --json stats.json

full.json：
{
  "sections": {"阅读理解": 50, "七选五": 12.5, "完形填空": 15, "语法填空": 15, "应用文": 15, "读后续写": 25},
  "total": 132.5,
  "pass_ratio": 0.6,
  "excellent_ratio": 0.85
}

CSV：第一列为学生编号时自动识别（全部非数字即视为编号）；其余列为板块得分。
缺考行：整行为空或总分列为空，计为缺考，不进入均分。
退出码：0 正常，2 输入错误。
"""
import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

BANDS = [(0, 40, "0–39%"), (40, 50, "40–49%"), (50, 60, "50–59%"), (60, 70, "60–69%"),
         (70, 80, "70–79%"), (80, 90, "80–89%"), (90, 100.01, "90–100%")]


def _num(v):
    if v is None:
        return None
    s = str(v).strip().replace("，", "").replace(",", "")
    if s == "" or s in {"-", "—", "缺考", "缺", "NA", "N/A"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def read_csv(path):
    for enc in ("utf-8-sig", "utf-8", "gbk", "gb18030"):
        try:
            with open(path, "r", encoding=enc, newline="") as f:
                rows = list(csv.reader(f))
            if rows:
                return rows, enc
        except UnicodeDecodeError:
            continue
        except FileNotFoundError:
            raise
    raise ValueError("无法识别文件编码，请另存为 UTF-8 CSV")


def parse(rows, sections):
    header = [h.strip() for h in rows[0]]
    body = rows[1:]
    if not header:
        raise ValueError("CSV 没有表头")

    # 判断第一列是否是编号
    first_vals = [_num(r[0]) for r in body if r]
    id_col = bool(first_vals) and all(v is None for v in first_vals)

    keep_idx = []
    extra = []
    for i, name in enumerate(header):
        if id_col and i == 0:
            continue
        if name in sections:
            keep_idx.append((i, name))
        elif name and name not in {"姓名", "学号", "班级", "总分"}:
            extra.append(name)

    if not keep_idx:
        raise ValueError(f"CSV 表头与 full.json 的 sections 无交集。表头：{header}")

    data = []
    absent = 0
    bad_cells = 0
    for r in body:
        if not any(str(c).strip() for c in r):
            continue
        rec = {}
        empty = True
        for i, name in keep_idx:
            v = _num(r[i]) if i < len(r) else None
            if v is None:
                bad_cells += 1
            else:
                empty = False
            rec[name] = v
        if empty:
            absent += 1
            continue
        data.append(rec)
    return data, absent, bad_cells, extra


def analyse(data, sections, meta):
    total_full = meta.get("total")
    if total_full is None:
        total_full = sum(float(sections[s]) for s in sections)
    total_full = float(total_full)
    pass_ratio = float(meta.get("pass_ratio", 0.6))
    exc_ratio = float(meta.get("excellent_ratio", 0.85))

    totals = []
    for rec in data:
        vals = [rec[s] for s in sections if rec.get(s) is not None]
        if vals:
            totals.append(sum(vals))

    n = len(totals)
    out = {"n": n, "total_full": total_full}
    if n == 0:
        return out, []

    out["mean"] = statistics.fmean(totals)
    out["sd"] = statistics.pstdev(totals) if n > 1 else 0.0
    out["max"] = max(totals)
    out["min"] = min(totals)
    out["pass_rate"] = sum(1 for t in totals if t >= total_full * pass_ratio) / n
    out["excellent_rate"] = sum(1 for t in totals if t >= total_full * exc_ratio) / n

    bands = []
    for low, high, label in BANDS:
        cnt = sum(1 for t in totals if low <= t / total_full * 100 < high)
        bands.append({"label": label, "count": cnt, "ratio": cnt / n})
    out["bands"] = bands

    # 板块统计
    sec_rows = []
    total_loss_sum = 0.0
    tmp = []
    for s in sections:
        full = float(sections[s])
        vals = [rec[s] for rec in data if rec.get(s) is not None]
        if not vals:
            tmp.append({"name": s, "full": full, "mean": None, "rate": None, "loss": 0.0, "n": 0})
            continue
        mean = statistics.fmean(vals)
        rate = mean / full if full else 0.0
        loss = full - mean
        total_loss_sum += loss
        tmp.append({"name": s, "full": full, "mean": mean, "rate": rate, "loss": loss, "n": len(vals)})

    for r in tmp:
        r["contribution"] = (r["loss"] / total_loss_sum) if total_loss_sum > 0 else 0.0
        sec_rows.append(r)
    out["sections"] = sec_rows

    ranked = [r for r in sec_rows if r["rate"] is not None]
    ranked.sort(key=lambda r: (r["rate"], -r["contribution"]))
    out["loss_points"] = ranked[:5]
    return out, sec_rows


def render(out, meta, absent, bad_cells, extra):
    lines = ["# 学情统计与失分点", ""]
    lines.append("> 口径：得分率 = 板块均分 ÷ 板块满分；贡献率 = 板块平均失分 ÷ 全班平均总失分。")
    lines.append("")

    if out["n"] == 0:
        lines.append("⚠️ 没有可统计的有效成绩，请检查 CSV 与 full.json 的列名是否一致。")
        return "\n".join(lines)

    lines += ["## 一、总体", "",
              "| 参考人数 | 满分 | 均分 | 标准差 | 最高 | 最低 | 及格率 | 优秀率 |",
              "|---|---|---|---|---|---|---|---|",
              "| {n} | {f:g} | {m:.1f} | {s:.1f} | {mx:g} | {mn:g} | {p:.0%} | {e:.0%} |".format(
                  n=out["n"], f=out["total_full"], m=out["mean"], s=out["sd"],
                  mx=out["max"], mn=out["min"], p=out["pass_rate"], e=out["excellent_rate"]),
              ""]

    if absent or bad_cells:
        notes = []
        if absent:
            notes.append(f"缺考/空行 {absent} 条（未计入均分）")
        if bad_cells:
            notes.append(f"空值/非数字单元格 {bad_cells} 个（按缺失处理，未参与该板块均分）")
        lines += [f"> 数据提示：{'；'.join(notes)}。", ""]
    if extra:
        lines += [f"> 未纳入统计的列：{', '.join(extra)}（不在 full.json 的 sections 中）。", ""]

    lines += ["## 二、得分率分布", "", "| 区间 | 人数 | 占比 |", "|---|---|---|"]
    for b in out["bands"]:
        lines.append(f"| {b['label']} | {b['count']} | {b['ratio']:.0%} |")
    lines.append("")

    lines += ["## 三、板块得分", "",
              "| 板块 | 满分 | 均分 | 得分率 | 失分贡献率 | 画像 |",
              "|---|---|---|---|---|---|"]
    for r in out["sections"]:
        if r["rate"] is None:
            lines.append(f"| {r['name']} | {r['full']:g} | — | — | — | 无有效数据 |")
            continue
        if r["rate"] < 0.6 and r["contribution"] >= 0.2:
            tag = "首要缺口"
        elif r["rate"] < 0.7:
            tag = "需关注"
        elif r["rate"] >= 0.85:
            tag = "优势板块"
        else:
            tag = "正常"
        lines.append(
            f"| {r['name']} | {r['full']:g} | {r['mean']:.1f} | {r['rate']:.0%} | {r['contribution']:.0%} | {tag} |"
        )
    lines.append("")

    lines += ["## 四、失分点排序（得分率低 + 贡献率高）", "",
              "| # | 板块 | 得分率 | 贡献率 | 建议动作 |", "|---|---|---|---|---|"]
    for i, r in enumerate(out["loss_points"], 1):
        if r["rate"] < 0.6:
            act = "下节课优先讲评 + 变式训练"
        elif r["rate"] < 0.75:
            act = "专项限时训练 + 错因归类"
        else:
            act = "维持，转入高分段突破"
        lines.append(f"| {i} | {r['name']} | {r['rate']:.0%} | {r['contribution']:.0%} | {act} |")
    lines.append("")

    if out["n"] < 15:
        lines += ["> ⚠️ 样本小于 15 人，以上百分比仅作描述，不作趋势结论。", ""]

    lines += ["## 五、下一步", "",
              "1. 首选缺口：{}".format(out["loss_points"][0]["name"] if out["loss_points"] else "—"),
              "2. 需要配题：按上述缺口在 W3 细目表中提高对应考点权重。",
              "3. 需要调课：把缺口板块的专项训练排进下一周，不挤占优势板块。",
              ""]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="成绩 CSV → 统计与失分点")
    ap.add_argument("--csv", required=True, help="成绩 CSV 路径")
    ap.add_argument("--full", required=True, help="满分配置 full.json 路径")
    ap.add_argument("--out", help="输出 markdown 路径")
    ap.add_argument("--json", dest="json_out", help="输出 JSON 路径")
    args = ap.parse_args(argv)

    try:
        meta = json.loads(Path(args.full).read_text(encoding="utf-8"))
        sections = {k: float(v) for k, v in (meta.get("sections") or {}).items()}
        if not sections:
            raise ValueError("full.json 缺少 sections")
    except (OSError, json.JSONDecodeError, ValueError) as e:
        print(f"[ERROR] 读取 full.json 失败：{e}", file=sys.stderr)
        return 2

    try:
        rows, enc = read_csv(args.csv)
    except (OSError, ValueError) as e:
        print(f"[ERROR] 读取 CSV 失败：{e}", file=sys.stderr)
        return 2
    if not rows:
        print("[ERROR] CSV 为空", file=sys.stderr)
        return 2

    try:
        data, absent, bad_cells, extra = parse(rows, sections)
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 2

    out, _ = analyse(data, sections, meta)
    text = render(out, meta, absent, bad_cells, extra)

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"[OK] 已生成：{args.out}（编码 {enc}，有效样本 {out['n']} 人）")
    else:
        print(text)

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] JSON：{args.json_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
