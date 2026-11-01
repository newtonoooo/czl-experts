#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""compliance_gate.py — 品类 × 国别合规放行判定

把 rules JSON 里的"市场通用要求"与"品类要求"叠加，输出阻断/条件/提示三级清单，
再按"已具备项"给出 GO / CONDITIONAL / BLOCKED。

用法：
    python compliance_gate.py --category baby --market DE --market FR --have EU-RP
    python compliance_gate.py --category electronics --market US --json
    python compliance_gate.py --list
    python compliance_gate.py --selftest

规则来源为 references/compliance-rules.json，可替换为自有维护版；
本工具只做清单汇总，不替代官方口径与持牌服务商意见。
"""

import argparse
import json
import os
import sys

LEVEL_ORDER = ("blocking", "conditional", "info")
LEVEL_ZH = {"blocking": "阻断级", "conditional": "条件级", "info": "提示级"}


def rules_path():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "references", "compliance-rules.json"))


def load_rules(path=None):
    p = path or rules_path()
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve(markets, categories, rules):
    """返回 (per_market, errors)。per_market = {market: {level: [items]}}"""
    mf = rules["market_family"]
    cats = rules["categories"]
    base = rules["family_base"]
    errors = []
    per_market = {}

    for m in markets:
        m = m.upper()
        if m not in mf:
            errors.append("未收录市场: %s（可用: %s）" % (m, ", ".join(sorted(mf))))
            continue
        family = mf[m]
        items = []
        items.extend(base.get(family, []))
        for cat in categories:
            c = cats.get(cat)
            if not c:
                errors.append("未收录品类: %s（可用: %s）" % (cat, ", ".join(sorted(cats))))
                continue
            items.extend(c.get(family, []))
        # 去重（同 id 取首条，条件级优先于提示级）
        merged = {}
        for it in items:
            old = merged.get(it["id"])
            if old is None:
                merged[it["id"]] = dict(it)
            else:
                rank = {k: i for i, k in enumerate(LEVEL_ORDER)}
                if rank[it["level"]] < rank[old["level"]]:
                    merged[it["id"]] = dict(it)
        grouped = {lv: [] for lv in LEVEL_ORDER}
        for it in merged.values():
            grouped[it["level"]].append(it)
        for lv in grouped:
            grouped[lv].sort(key=lambda x: x["id"])
        per_market[m] = grouped
    return per_market, errors


def verdict(grouped, have, assume_path=False):
    have = set(x.strip() for x in have)
    missing_block = [i for i in grouped["blocking"] if i["id"] not in have]
    missing_cond = [i for i in grouped["conditional"] if i["id"] not in have]
    if missing_block:
        return ("CONDITIONAL" if assume_path else "BLOCKED"), missing_block, missing_cond
    if missing_cond:
        return "CONDITIONAL", [], missing_cond
    return "GO", [], []


def render(per_market, have, assume_path, rules):
    L = []
    L.append("# 合规放行单")
    L.append("")
    L.append("> 规则版本 %s（复核 %s）。%s" % (
        rules["meta"]["version"], rules["meta"]["reviewed"], rules["meta"]["disclaimer"]))
    L.append("")
    have = set(have)
    overall = "GO"
    for m, grouped in per_market.items():
        v, mb, mc = verdict(grouped, have, assume_path)
        if v == "BLOCKED":
            overall = "BLOCKED"
        elif v == "CONDITIONAL" and overall == "GO":
            overall = "CONDITIONAL"
        L.append("## %s · 判定 %s" % (m, v))
        L.append("")
        if v == "BLOCKED":
            L.append("**不可发货/不可上架**：阻断项未具备 %d 项。" % len(mb))
        elif v == "CONDITIONAL":
            L.append("**可先做下一步，但须限期补齐**：阻断项 %d 项待办，条件项 %d 项待办。"
                     % (len(mb), len(mc)))
        else:
            L.append("**无阻断项**，进入页面与补货环节。")
        L.append("")
        for lv in LEVEL_ORDER:
            items = grouped[lv]
            if not items:
                continue
            L.append("### %s（%d 项）" % (LEVEL_ZH[lv], len(items)))
            L.append("")
            L.append("| 状态 | 编号 | 要求 | 需备证据 | 谁办 | 常见周期 |")
            L.append("|---|---|---|---|---|---|")
            for it in items:
                mark = "已具备" if it["id"] in have else "待办"
                L.append("| %s | `%s` | %s | %s | %s | %s |" % (
                    mark, it["id"], it["title"], it["evidence"], it["owner"], it["lead"]))
            L.append("")
            for it in items:
                if it.get("note"):
                    L.append("- `%s` %s" % (it["id"], it["note"]))
            L.append("")
    L.append("## 总判定：%s" % overall)
    L.append("")
    if overall == "BLOCKED":
        L.append("先把阻断项补齐再谈上架与投放。按上表「谁办」逐项确认，拿到证据编号后回填 `--have`。")
    elif overall == "CONDITIONAL":
        L.append("阻断项已具备或有明确路径。上架同时设定补齐截止日，到期未补齐即停售。")
    else:
        L.append("可进入 G4 页面环节。合规文件仍需按平台要求上传归档，平台侧与国别法规是两道关。")
    L.append("")
    L.append("> 提示：单件产品可能命中多个品类（如带电池的儿童玩具），请叠加全部命中品类重跑一次。")
    return "\n".join(L)


def selftest():
    rules = load_rules()
    ok = 0

    per, errs = resolve(["US"], ["general"], rules)
    assert not errs and "US" in per
    v, mb, mc = verdict(per["US"], [], False)
    assert v == "BLOCKED" and len(mb) >= 1
    ok += 1

    all_ids = [i["id"] for lv in LEVEL_ORDER for i in per["US"][lv]]
    v2, mb2, mc2 = verdict(per["US"], all_ids, False)
    assert v2 == "GO" and not mb2
    ok += 1

    v3, _, _ = verdict(per["US"], [], True)
    assert v3 == "CONDITIONAL"
    ok += 1

    per2, errs2 = resolve(["DE", "FR"], ["baby"], rules)
    assert not errs2 and set(per2) == {"DE", "FR"}
    ids_de = [i["id"] for lv in LEVEL_ORDER for i in per2["DE"][lv]]
    assert "EU-RP" in ids_de and "EU-CE-TOY" not in ids_de
    assert any(i.startswith("EU-FCM") or i.startswith("EU-BABY") for i in ids_de)
    ok += 1

    per3, errs3 = resolve(["XX"], ["general"], rules)
    assert errs3 and not per3
    ok += 1

    per4, errs4 = resolve(["US"], ["nope"], rules)
    assert errs4
    ok += 1

    # 去重且等级取更高
    per5, _ = resolve(["US"], ["baby", "toy"], rules)
    ids = [i["id"] for lv in LEVEL_ORDER for i in per5["US"][lv]]
    assert len(ids) == len(set(ids))
    ok += 1

    print("selftest passed: %d checks" % ok)
    return 0


def main():
    ap = argparse.ArgumentParser(description="品类 × 国别合规放行判定")
    ap.add_argument("--category", action="append", default=[], help="品类 id，可重复")
    ap.add_argument("--market", action="append", default=[], help="国家代码，可重复")
    ap.add_argument("--have", action="append", default=[], help="已具备的要求编号，可重复")
    ap.add_argument("--assume-path", action="store_true", help="阻断项已有明确办理路径与日期")
    ap.add_argument("--rules", help="自定义规则文件路径")
    ap.add_argument("--list", action="store_true", help="列出可用品类与市场")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    rules = load_rules(args.rules)

    if args.list:
        print("品类：")
        for k, v in rules["categories"].items():
            print("  %-14s %s" % (k, v["zh"]))
        print("\n市场：")
        for k in sorted(rules["market_family"]):
            print("  %-4s %s" % (k, rules["families"][rules["market_family"][k]]))
        return 0

    if not args.market:
        print("ERROR: 至少给出一个 --market", file=sys.stderr)
        return 2
    cats = args.category or ["general"]

    per_market, errs = resolve(args.market, cats, rules)
    for e in errs:
        print("ERROR: %s" % e, file=sys.stderr)
    if not per_market:
        return 2

    have = []
    for h in args.have:
        have.extend([x for x in h.replace("，", ",").split(",") if x.strip()])

    if args.json:
        out = {}
        for m, grouped in per_market.items():
            v, mb, mc = verdict(grouped, have, args.assume_path)
            out[m] = {
                "verdict": v,
                "missing_blocking": [i["id"] for i in mb],
                "missing_conditional": [i["id"] for i in mc],
                "items": {lv: grouped[lv] for lv in LEVEL_ORDER},
            }
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(render(per_market, have, args.assume_path, rules))
    return 0


if __name__ == "__main__":
    sys.exit(main())
