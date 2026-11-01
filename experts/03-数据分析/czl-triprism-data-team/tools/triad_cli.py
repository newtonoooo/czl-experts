# -*- coding: utf-8 -*-
"""三棱镜 · 统一命令行入口

一条命令跑完整条流水线：
  体检 → 口径冻结 → 三路分析 → 结论复算 → 四格式交付 → 运行清单

用法（示例）：
  python triad_cli.py run --path data.xlsx --outdir out --title "2026Q1 经营会诊"
  python triad_cli.py profile --path data.csv --brief
  python triad_cli.py analyze --path data.csv --contract c.json --out bundle.json
  python triad_cli.py verify --path data.csv --bundle bundle.json

退出码：0 成功 / 2 输入错误 / 3 体检闸门拦截 / 4 复算失败
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import triad_analyze as A            # noqa: E402
import triad_contract as C           # noqa: E402
import triad_profile as P            # noqa: E402
import triad_render as R             # noqa: E402
import triad_verify as V             # noqa: E402
from triad_io import TableError, read_table   # noqa: E402

PRODUCT = "三棱镜·专业数据分析专家团"
AUTHOR = "虫志龙"
VERSION = "1.0.0"


def _dump(path, obj):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
    return path


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def cmd_profile(args):
    try:
        prof = P.profile_table(args.path, args.sheet)
    except TableError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    if args.out:
        _dump(args.out, prof)
    if args.brief:
        print(P.summarize_for_prompt(prof))
    else:
        print(json.dumps(prof, ensure_ascii=False, indent=2))
    return 0 if prof["quality"]["gate"] != "block" else 3


def cmd_analyze(args):
    try:
        table = read_table(args.path, args.sheet)
        contract = C.load_contract(args.contract) if args.contract else None
        if contract is None:
            prof = P.profile_table(args.path, args.sheet)
            contract = C.draft_contract(prof, args.metric, args.dimension, args.grain)
        ok, errors, warnings = C.check_contract(contract, table)
        if not ok:
            print(json.dumps({"ok": False, "errors": errors, "warnings": warnings},
                             ensure_ascii=False, indent=2))
            return 2
        bundle = A.run_lanes(table, contract, args.lanes, args.metric, args.dimension)
    except (TableError, C.ContractError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    bundle["contract_check"] = {"errors": errors, "warnings": warnings}
    _dump(args.out, bundle)
    print(json.dumps({"ok": True, "out": args.out,
                      "lanes": {k: len(v.get("findings") or []) for k, v in bundle["lanes"].items()}},
                     ensure_ascii=False, indent=2))
    return 0


def cmd_verify(args):
    try:
        table = read_table(args.path, args.sheet)
    except TableError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    with open(args.bundle, "r", encoding="utf-8") as fh:
        bundle = json.load(fh)
    report = V.verify_findings(table, bundle)
    _dump(args.out, report)
    if args.demote_out:
        _dump(args.demote_out, V.demote(bundle, report))
    print(json.dumps({"ok": report["overall"] != "FAIL", "overall": report["overall"],
                      "checked": report["checked"], "passed": report["passed"],
                      "failed": report["failed"], "skipped": report["skipped"]},
                     ensure_ascii=False, indent=2))
    return 0 if report["overall"] != "FAIL" else 4


def cmd_run(args):
    t0 = time.time()
    outdir = args.outdir
    os.makedirs(outdir, exist_ok=True)
    try:
        prof = P.profile_table(args.path, args.sheet)
    except TableError as exc:
        print(json.dumps({"ok": False, "stage": "profile", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    _dump(os.path.join(outdir, "profile.json"), prof)

    if prof["quality"]["gate"] == "block":
        blocked = os.path.join(outdir, "blocked.md")
        with open(blocked, "w", encoding="utf-8") as fh:
            fh.write("# 本次分析被体检闸门拦截\n\n")
            fh.write(f"数据源：{prof['source']}（{prof['rows']} 行 × {prof['cols']} 列）\n\n")
            fh.write(f"可信度：{prof['quality']['grade']}（{prof['quality']['score']} 分）\n\n## 拦截原因\n\n")
            for i in prof["quality"]["issues"]:
                if i["level"] == "block":
                    fh.write(f"- {i['message']}\n")
            fh.write("\n## 建议\n\n补齐上述问题后重跑，或提供更完整的数据表。\n")
        print(json.dumps({"ok": False, "stage": "gate", "gate": "block",
                          "report": blocked, "brief": P.summarize_for_prompt(prof)},
                         ensure_ascii=False, indent=2))
        return 3

    table = read_table(args.path, args.sheet)
    contract = C.load_contract(args.contract) if args.contract else C.draft_contract(
        prof, args.metric, args.dimension, args.grain)
    ok, errors, warnings = C.check_contract(contract, table)
    _dump(os.path.join(outdir, "contract.json"), contract)
    if not ok:
        print(json.dumps({"ok": False, "stage": "contract", "errors": errors, "warnings": warnings},
                         ensure_ascii=False, indent=2))
        return 2

    bundle = A.run_lanes(table, contract, args.lanes, args.metric, args.dimension)
    _dump(os.path.join(outdir, "bundle.json"), bundle)

    report = V.verify_findings(table, bundle)
    bundle = V.demote(bundle, report)
    _dump(os.path.join(outdir, "verify.json"), report)
    _dump(os.path.join(outdir, "bundle.verified.json"), bundle)

    title = args.title or f"{os.path.splitext(os.path.basename(args.path))[0]} · 三视角数据会诊"
    meta = {"title": title, "product": PRODUCT, "author": AUTHOR, "version": VERSION,
            "footer_note": "本报告为数据辅助材料，不构成审计、税务或投资意见。"}
    outputs = []
    formats = [f.strip() for f in (args.formats or "html,deck,xlsx,md").split(",") if f.strip()]

    if "html" in formats:
        p = os.path.join(outdir, "report.html")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(R.build_html(bundle, prof, report, meta))
        outputs.append(p)
    if "md" in formats:
        p = os.path.join(outdir, "onepager.md")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(R.onepager_md(bundle, prof, report, meta))
        outputs.append(p)
    if "deck" in formats:
        spec = R.build_deck(bundle, prof, report, meta)
        p1 = os.path.join(outdir, "deck.html")
        with open(p1, "w", encoding="utf-8") as fh:
            fh.write(R.deck_html(spec, meta, bundle=bundle))
        p2 = _dump(os.path.join(outdir, "deck_spec.json"), spec)
        outputs += [p1, p2]
    if "xlsx" in formats:
        p = os.path.join(outdir, "workbook.xlsx")
        R.build_xlsx(bundle, prof, report, p)
        outputs.append(p)

    manifest = {
        "product": PRODUCT, "author": AUTHOR, "version": VERSION,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_sec": round(time.time() - t0, 2),
        "input": {"path": os.path.abspath(args.path), "sha256": _sha256(args.path),
                  "rows": prof["rows"], "cols": prof["cols"]},
        "quality": prof["quality"],
        "contract_warnings": warnings,
        "verification": {k: report[k] for k in ("overall", "checked", "passed", "failed", "skipped")},
        "outputs": [{"path": os.path.abspath(p), "bytes": os.path.getsize(p)} for p in outputs],
    }
    _dump(os.path.join(outdir, "run.json"), manifest)
    print(json.dumps({"ok": True, "outdir": os.path.abspath(outdir),
                      "gate": prof["quality"]["gate"], "grade": prof["quality"]["grade"],
                      "verify": report["overall"], "outputs": [os.path.basename(p) for p in outputs],
                      "elapsed_sec": manifest["elapsed_sec"]}, ensure_ascii=False, indent=2))
    return 0 if report["overall"] != "FAIL" else 4


def main(argv=None):
    ap = argparse.ArgumentParser(prog="triad", description=f"{PRODUCT} v{VERSION}")
    ap.add_argument("--version", action="version", version=f"{PRODUCT} {VERSION}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("profile", help="只做体检")
    p.add_argument("path")
    p.add_argument("--sheet")
    p.add_argument("--out")
    p.add_argument("--brief", action="store_true")
    p.set_defaults(func=cmd_profile)

    a = sub.add_parser("analyze", help="三路分析")
    a.add_argument("--path", required=True)
    a.add_argument("--sheet")
    a.add_argument("--contract")
    a.add_argument("--out", required=True)
    a.add_argument("--metric", nargs="*")
    a.add_argument("--dimension", nargs="*")
    a.add_argument("--grain")
    a.add_argument("--lanes", nargs="*")
    a.set_defaults(func=cmd_analyze)

    v = sub.add_parser("verify", help="结论复算")
    v.add_argument("--path", required=True)
    v.add_argument("--sheet")
    v.add_argument("--bundle", required=True)
    v.add_argument("--out", required=True)
    v.add_argument("--demote-out")
    v.set_defaults(func=cmd_verify)

    r = sub.add_parser("run", help="跑完整流水线")
    r.add_argument("--path", required=True)
    r.add_argument("--sheet")
    r.add_argument("--outdir", required=True)
    r.add_argument("--contract")
    r.add_argument("--title")
    r.add_argument("--metric", nargs="*")
    r.add_argument("--dimension", nargs="*")
    r.add_argument("--grain")
    r.add_argument("--lanes", nargs="*")
    r.add_argument("--formats", default="html,deck,xlsx,md")
    r.set_defaults(func=cmd_run)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
