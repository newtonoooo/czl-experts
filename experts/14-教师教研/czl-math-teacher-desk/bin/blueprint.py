#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""blueprint.py —— 双向细目表的生成与体检（纯标准库，零依赖）。

为什么要有这个脚本：
    组卷最常见的失败不是题写得差，是"表没摊平"：分值加不到 150、某个模块占了半张卷、
    难度标了却没算过系数。这些都能用加法查出来，不该靠人眼。

用法：
    # 1) 生成可填的空白细目表（默认 8+3+3+5）
    python bin/blueprint.py --init 细目表.csv

    # 2) 填好后体检
    python bin/blueprint.py 细目表.csv
    python bin/blueprint.py 细目表.csv --total 150 --max-module 0.35
    python bin/blueprint.py 细目表.csv --md 细目表.md --json 细目表.json

CSV 列（顺序固定，第一行是表头）：
    题号,题型,分值,考点,难度,预测得分率,模块
    题型取值：单选 / 多选 / 填空 / 解答
    难度取值：易 / 中 / 难
    预测得分率：0–1 之间的小数（可留空，留空则该题不参与系数估算）

退出码：0 = 全部通过；1 = 有错误项（错误不阻断输出，但组卷前必须修）。
"""

import argparse
import csv
import json
import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

STANDARD = [("单选", 8, 5), ("多选", 3, 6), ("填空", 3, 5), ("解答", 5, None)]
TYPE_ALIASES = {
    "单选": "单选", "单项选择题": "单选", "单选题": "单选",
    "多选": "多选", "多项选择题": "多选", "多选题": "多选",
    "填空": "填空", "填空题": "填空",
    "解答": "解答", "解答题": "解答", "大题": "解答",
}
LEVELS = ("易", "中", "难")


def init_template(path, total):
    rows = [["题号", "题型", "分值", "考点", "难度", "预测得分率", "模块"]]
    seq = 0
    plan = [("单选", 8, 5), ("多选", 3, 6), ("填空", 3, 5)]
    for t, n, m in plan:
        for _ in range(n):
            seq += 1
            rows.append([str(seq), t, str(m), "", "中", "", ""])
    # 解答题 5 题共 77 分：13+15+15+17+17
    for m in (13, 15, 15, 17, 17):
        seq += 1
        rows.append([str(seq), "解答", str(m), "", "中", "", ""])
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows(rows)
    s = 8 * 5 + 3 * 6 + 3 * 5 + 13 + 15 + 15 + 17 + 17
    print("已生成空白细目表：%s（%d 题，合计 %d 分，目标 %s）" % (path, seq, s, total))


def load(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.reader(f) if any(c.strip() for c in r)]
    if not rows:
        raise SystemExit("错误：细目表为空")
    header = [c.strip() for c in rows[0]]
    need = ["题号", "题型", "分值", "考点", "难度"]
    for n in need:
        if n not in header:
            raise SystemExit("错误：缺少列『%s』。当前列：%s" % (n, "、".join(header)))
    idx = {n: header.index(n) for n in header}
    items = []
    for r in rows[1:]:
        if len(r) < len(need):
            continue

        def g(key, default=""):
            i = idx.get(key)
            return r[i].strip() if i is not None and i < len(r) else default

        raw_type = g("题型")
        if not raw_type:
            continue
        t = TYPE_ALIASES.get(raw_type)
        try:
            mark = float(g("分值"))
        except ValueError:
            mark = 0.0
        try:
            rate = float(g("预测得分率"))
            rate = max(0.0, min(1.0, rate))
        except ValueError:
            rate = None
        items.append({
            "no": g("题号"),
            "type": t or raw_type,
            "mark": mark,
            "point": g("考点"),
            "level": g("难度") or "中",
            "rate": rate,
            "module": g("模块") or "未标",
        })
    return items


def check(items, total, max_module, structure):
    errors, warns = [], []
    n = len(items)
    s = sum(i["mark"] for i in items)

    if abs(s - total) > 1e-6:
        errors.append("总分 %.1f，与目标 %g 相差 %.1f" % (s, total, s - total))

    if structure:
        by_type = {}
        for i in items:
            by_type.setdefault(i["type"], []).append(i)
        for t, cnt, per in STANDARD:
            got = by_type.get(t, [])
            if len(got) != cnt:
                errors.append("%s 应有 %d 题，实际 %d 题" % (t, cnt, len(got)))
            if per is not None:
                bad = [i["no"] for i in got if abs(i["mark"] - per) > 1e-6]
                if bad:
                    errors.append("%s 每题应为 %d 分，题号 %s 不符" % (t, per, "、".join(bad)))
        if abs(sum(i["mark"] for i in items if i["type"] == "解答") - 77) > 1e-6:
            warns.append("解答题合计 %.0f 分，新高考标准为 77 分"
                         % sum(i["mark"] for i in items if i["type"] == "解答"))

    mods = {}
    for i in items:
        mods[i["module"]] = mods.get(i["module"], 0) + i["mark"]
    for m, v in sorted(mods.items(), key=lambda x: -x[1]):
        share = v / s if s else 0
        if share > max_module:
            errors.append("模块『%s』占 %.0f%%（%g 分），超过上限 %.0f%%"
                          % (m, share * 100, v, max_module * 100))

    dup = {}
    for i in items:
        key = (i["point"], i["level"])
        dup.setdefault(key, []).append(i["no"])
    for (p, lv), nos in dup.items():
        if p and len(nos) > 2:
            warns.append("考点『%s』在『%s』难度上出现 %d 次（%s）" % (p, lv, len(nos), "、".join(nos)))

    bad_level = [i["no"] for i in items if i["level"] not in LEVELS]
    if bad_level:
        warns.append("难度取值不在 易/中/难 内：%s" % "、".join(bad_level))

    no_rate = [i["no"] for i in items if i["rate"] is None]
    est = None
    if s and not no_rate:
        est = sum(i["rate"] * i["mark"] for i in items) / s

    lv_marks = {lv: sum(i["mark"] for i in items if i["level"] == lv) for lv in LEVELS}
    return {
        "count": n, "total": s, "errors": errors, "warns": warns,
        "modules": mods, "levels": lv_marks, "estimate": est,
        "no_rate": no_rate,
    }


def render(items, res, target):
    L = []
    A = L.append
    A("# 双向细目表")
    A("")
    A("**题量**：%d　**总分**：%g / 目标 %g　**预估难度系数**：%s"
      % (res["count"], res["total"], target,
         "%.2f" % res["estimate"] if res["estimate"] is not None else "—（有题目未填预测得分率）"))
    A("")
    A("| 题号 | 题型 | 分值 | 考点 | 难度 | 预测得分率 | 模块 |")
    A("|---|---|---|---|---|---|---|")
    for i in items:
        A("| %s | %s | %g | %s | %s | %s | %s |"
          % (i["no"], i["type"], i["mark"], i["point"] or "—", i["level"],
             "%.2f" % i["rate"] if i["rate"] is not None else "—", i["module"]))
    A("")
    A("## 体检结果")
    A("")
    A("| 项 | 结果 |")
    A("|---|---|")
    A("| 总分 | %s |" % ("通过：%g" % res["total"] if abs(res["total"] - target) < 1e-6
                          else "❌ %g（目标 %g）" % (res["total"], target)))
    A("| 题量 | %d |" % res["count"])
    A("| 难度分布（易/中/难） | %g / %g / %g |"
      % (res["levels"]["易"], res["levels"]["中"], res["levels"]["难"]))
    if res["estimate"] is not None:
        A("| 预估系数 | %.2f |" % res["estimate"])
    A("")
    A("### 模块占比")
    A("")
    A("| 模块 | 分值 | 占比 |")
    A("|---|---|---|")
    for m, v in sorted(res["modules"].items(), key=lambda x: -x[1]):
        A("| %s | %g | %.0f%% |" % (m, v, v / res["total"] * 100 if res["total"] else 0))
    A("")
    if res["errors"]:
        A("### 必须修")
        A("")
        for e in res["errors"]:
            A("- %s" % e)
        A("")
    if res["warns"]:
        A("### 建议看")
        A("")
        for w in res["warns"]:
            A("- %s" % w)
        A("")
    if not res["errors"] and not res["warns"]:
        A("细目表通过体检，可以进入逐题写作。")
        A("")
    A("> 本表确认后再生题。改表两分钟，改题两小时。")
    A("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="双向细目表生成与体检")
    ap.add_argument("file", nargs="?", help="细目表 CSV")
    ap.add_argument("--init", nargs="?", const="细目表.csv", help="生成空白模板")
    ap.add_argument("--total", type=float, default=150, help="目标总分，默认 150")
    ap.add_argument("--max-module", type=float, default=0.35, help="单模块占比上限，默认 0.35")
    ap.add_argument("--no-structure", action="store_true", help="不检查 8+3+3+5 结构")
    ap.add_argument("--unit", action="store_true",
                    help="单元卷模式：不检查模块占比（单元卷本就集中在一个模块）")
    ap.add_argument("--md", default=None, help="输出 Markdown 路径")
    ap.add_argument("--json", dest="json_out", default=None, help="输出 JSON 路径")
    args = ap.parse_args()

    if args.init:
        init_template(args.init, args.total)
        return

    if not args.file:
        ap.print_help()
        raise SystemExit(2)
    if not os.path.isfile(args.file):
        raise SystemExit("错误：找不到文件 %s" % args.file)

    items = load(args.file)
    if not items:
        raise SystemExit("错误：细目表里没有有效题目行")
    res = check(items, args.total, 1.01 if args.unit else args.max_module,
                not args.no_structure)
    if args.unit:
        res["warns"].insert(0, "单元卷模式：已跳过模块占比检查（单元卷集中在一个模块是正常的）")

    print(render(items, res, args.total))
    if args.md:
        with open(args.md, "w", encoding="utf-8") as f:
            f.write(render(items, res, args.total))
        print("已写出：%s" % args.md)
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump({"items": items, "result": res}, f, ensure_ascii=False, indent=2)
        print("已写出：%s" % args.json_out)

    sys.exit(1 if res["errors"] else 0)


if __name__ == "__main__":
    main()
