#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
契约守门人 · 统一命令行入口

用法：
    python cc.py draft   --type purchase --a "甲公司" --b "乙公司" --amount 200000
    python cc.py review  ./contract.docx --stance a
    python cc.py compare ./v1.docx ./v2.docx
    python cc.py ledger  import --draft .contract-workspace/xxx.meta.json
    python cc.py ledger  report
    python cc.py laws    --q 违约金
    python cc.py amount  200000
    python cc.py doctor

所有命令输出 JSON 摘要到 stdout（便于程序解析），报告正文写到 --out 指定目录。
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import cc_common as C  # noqa: E402
import cc_compare  # noqa: E402
import cc_draft  # noqa: E402
import cc_ledger  # noqa: E402
import cc_review  # noqa: E402
from cc_docx import build_docx, verify_docx  # noqa: E402

REF = Path(__file__).parent.parent / "references"


def _print(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _values_from_args(args):
    mapping = {
        "a_name": args.a,
        "b_name": args.b,
        "amount": args.amount,
        "subject": args.subject,
        "stance": args.stance,
        "sign_place": args.place,
        "start_date": args.start,
        "delivery_days": args.delivery_days,
        "payment_days": args.payment_days,
        "acceptance_days": args.acceptance_days,
        "warranty_months": args.warranty,
        "term_months": args.term,
        "address": args.address,
    }
    return {k: v for k, v in mapping.items() if v not in (None, "")}


def cmd_draft(args):
    spec = {}
    if args.spec:
        spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    values = dict(spec.get("values") or {})
    values.update(_values_from_args(args))
    result = cc_draft.draft(args.type, values, out_dir=args.out, spec=spec)
    _print(result)
    return 0


def cmd_review(args):
    result = cc_review.review_file(args.file, type_key=args.type, stance=args.stance, out_dir=args.out)
    summary = {
        "ok": result["ok"],
        "type": result["type_label"],
        "stance": result["stance"],
        "clause_count": result["clause_count"],
        "verdict": result["verdict"],
        "score": result["score"],
        "counts": result["counts"],
        "missing_elements": [m["label"] for m in result["missing_elements"]],
        "findings": [
            {"level": f["level"], "clause": f["clause"], "name": f["name"], "evidence": f["evidence"][:80]}
            for f in result["findings"]
        ],
        "report_md": result["report_md"],
        "report_json": result["report_json"],
    }
    _print(summary)
    return 0


def cmd_compare(args):
    result = cc_compare.compare_files(args.a_file, args.b_file, out_dir=args.out)
    summary = {
        "ok": result["ok"],
        "align_mode": result["align_mode"],
        "stats": result["stats"],
        "major": [
            {"clause": c["clause"], "title": c["title"], "impact": c["impact"]}
            for c in result["changes"] if c["level"] == "major"
        ],
        "negotiation": result["negotiation"],
        "report_md": result["report_md"],
        "report_json": result["report_json"],
    }
    _print(summary)
    return 0


def cmd_ledger(args):
    path = args.path
    if args.action == "add":
        created = cc_ledger.add(args.contract, args.item, obligor=args.obligor or "", due=args.due,
                                note=args.note or "", path=path)
        _print({"ok": True, "created": created})
        return 0
    if args.action == "import":
        created = cc_ledger.import_from_draft(args.draft, start_date=args.start, path=path)
        _print({"ok": True, "created": created, "count": len(created)})
        return 0
    if args.action == "list":
        rows = cc_ledger.list_entries(path, state=args.state, contract=args.contract)
        _print({"ok": True, "count": len(rows), "entries": rows})
        return 0
    if args.action == "due":
        rows = cc_ledger.due_soon(args.days, path)
        _print({"ok": True, "count": len(rows), "entries": rows})
        return 0
    if args.action == "done":
        entry = cc_ledger.mark_done(args.id, path)
        _print({"ok": True, "entry": entry})
        return 0
    if args.action == "remove":
        cc_ledger.remove(args.id, path)
        _print({"ok": True, "removed": args.id})
        return 0
    if args.action == "report":
        _print(cc_ledger.report(path, out_dir=args.out))
        return 0
    _print({"ok": False, "error": "未知的台账操作：%s" % args.action})
    return 2


def cmd_laws(args):
    doc = json.loads((REF / "law_index.json").read_text(encoding="utf-8"))
    q = (args.q or "").strip()
    hits = []
    for law in doc["laws"]:
        for art in law["articles"]:
            blob = "%s%s%s%s" % (law["law"], art["article"], art["topic"], art["gist"])
            if not q or q in blob:
                hits.append({
                    "law": law["law"], "article": art["article"], "topic": art["topic"],
                    "gist": art["gist"], "use": art.get("use", ""),
                    "confidence": art.get("confidence", "high"),
                })
    for item in doc.get("scenario_index", []):
        if q and q in item["question"]:
            hits.append({"scenario": item["question"], "point_to": item["point_to"]})
    _print({
        "ok": True,
        "query": q,
        "count": len(hits),
        "results": hits[: args.limit],
        "note": "条目为要点摘录，引用原文前请核对 %s" % "、".join(s["name"] for s in doc["meta"]["official_sources"]),
    })
    return 0


def cmd_amount(args):
    _print({"ok": True, "amount": args.value, "cn": C.amount_to_cn(args.value)})
    return 0


def cmd_doctor(args):
    checks = []

    def check(name, fn):
        try:
            detail = fn()
            checks.append({"check": name, "ok": True, "detail": detail})
        except Exception as exc:  # noqa: BLE001
            checks.append({"check": name, "ok": False, "detail": "%s: %s" % (type(exc).__name__, exc)})

    def _lib():
        lib = json.loads((REF / "clause_library.json").read_text(encoding="utf-8"))
        return "%d 类合同、%d 条原创条款" % (len(lib["types"]), sum(len(t["clauses"]) for t in lib["types"].values()))

    def _rules():
        doc = json.loads((REF / "risk_rules.json").read_text(encoding="utf-8"))
        levels = {r["level"] for r in doc["rules"]}
        if not levels <= {"high", "mid", "low"}:
            raise ValueError("存在非法风险等级：%s" % levels)
        return "%d 条规则（高 %d / 中 %d / 低 %d）" % (
            len(doc["rules"]),
            sum(1 for r in doc["rules"] if r["level"] == "high"),
            sum(1 for r in doc["rules"] if r["level"] == "mid"),
            sum(1 for r in doc["rules"] if r["level"] == "low"))

    def _laws():
        doc = json.loads((REF / "law_index.json").read_text(encoding="utf-8"))
        n = sum(len(l["articles"]) for l in doc["laws"])
        return "%d 部法律、%d 条导航" % (len(doc["laws"]), n)

    def _docx():
        with tempfile.TemporaryDirectory() as tmp:
            model = {"meta": {"title": "自检"}, "blocks": [
                {"t": "title", "text": "自检文档"},
                {"t": "para", "text": "这是 DOCX 写入器的自检段落，用于确认包结构与 XML 合法。"},
                {"t": "table", "rows": [["项目", "值"], ["金额", "1,000.00"]], "widths": [3000, 3000]},
            ]}
            p = build_docx(model, Path(tmp) / "selfcheck.docx")
            r = verify_docx(p)
            if not r["ok"]:
                raise ValueError("; ".join(r["errors"]))
            return "段落 %d、表格 %d、部件 %d" % (r["paragraphs"], r["tables"], len(r["parts"]))

    def _amount():
        got = C.amount_to_cn(200000)
        if got != "人民币贰拾万元整":
            raise ValueError("大写转换异常：%s" % got)
        return "200000 -> %s" % got

    def _py():
        v = sys.version_info
        if v < (3, 8):
            raise ValueError("需要 Python 3.8+，当前 %s" % sys.version.split()[0])
        return "Python %s" % sys.version.split()[0]

    check("Python 版本", _py)
    check("条款库", _lib)
    check("风险规则表", _rules)
    check("法条索引", _laws)
    check("金额大写转换", _amount)
    check("DOCX 写入与结构校验", _docx)

    ok = all(c["ok"] for c in checks)
    _print({"ok": ok, "checks": checks})
    return 0 if ok else 1


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cc.py", description="契约守门人合同工具箱")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("draft", help="W1 起草合同并输出 docx")
    p.add_argument("--type", required=True, help="合同类型：purchase/service/lease/labor/nda/loan 或别名")
    p.add_argument("--a", help="甲方名称")
    p.add_argument("--b", help="乙方名称")
    p.add_argument("--amount", help="金额（数字）")
    p.add_argument("--subject", help="标的描述")
    p.add_argument("--stance", default="a", choices=["a", "b", "neutral"], help="用户站位，影响管辖地")
    p.add_argument("--place", help="签订地点")
    p.add_argument("--start", help="起始日 YYYY-MM-DD")
    p.add_argument("--term", help="期限（月）")
    p.add_argument("--delivery-days", dest="delivery_days", help="交付天数")
    p.add_argument("--payment-days", dest="payment_days", help="付款天数")
    p.add_argument("--acceptance-days", dest="acceptance_days", help="验收工作日")
    p.add_argument("--warranty", help="质保月数")
    p.add_argument("--address", help="房屋坐落（租赁）")
    p.add_argument("--spec", help="完整 spec JSON 文件")
    p.add_argument("--out", default=".contract-workspace")
    p.set_defaults(func=cmd_draft)

    p = sub.add_parser("review", help="W2 审查合同风险")
    p.add_argument("file")
    p.add_argument("--type", help="指定合同类型，缺省自动识别")
    p.add_argument("--stance", default="a", choices=["a", "b", "neutral"])
    p.add_argument("--out", default=".contract-workspace")
    p.set_defaults(func=cmd_review)

    p = sub.add_parser("compare", help="W3 比对两版合同")
    p.add_argument("a_file")
    p.add_argument("b_file")
    p.add_argument("--out", default=".contract-workspace")
    p.set_defaults(func=cmd_compare)

    p = sub.add_parser("ledger", help="W5 履约台账")
    p.add_argument("action", choices=["add", "import", "list", "due", "done", "remove", "report"])
    p.add_argument("--contract", help="合同名称")
    p.add_argument("--item", action="append", help="节点名称，可重复")
    p.add_argument("--obligor", help="义务方")
    p.add_argument("--due", help="截止日 YYYY-MM-DD")
    p.add_argument("--note", help="备注")
    p.add_argument("--draft", help="起草台 meta.json 路径（import 用）")
    p.add_argument("--start", help="基准日 YYYY-MM-DD（import 用）")
    p.add_argument("--id", help="节点编号（done/remove 用）")
    p.add_argument("--days", type=int, default=7, help="临近天数（due 用）")
    p.add_argument("--state", choices=["open", "done"], help="过滤状态（list 用）")
    p.add_argument("--path", help="台账文件路径")
    p.add_argument("--out", default=".contract-workspace")
    p.set_defaults(func=cmd_ledger)

    p = sub.add_parser("laws", help="W4 本地法条索引检索")
    p.add_argument("--q", default="", help="关键词，如 违约金 / 试用期")
    p.add_argument("--limit", type=int, default=8)
    p.set_defaults(func=cmd_laws)

    p = sub.add_parser("amount", help="金额转中文大写")
    p.add_argument("value")
    p.set_defaults(func=cmd_amount)

    p = sub.add_parser("doctor", help="环境与数据自检")
    p.set_defaults(func=cmd_doctor)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except C.UnsupportedFormat as exc:
        _print({"ok": False, "error": str(exc), "hint": "请另存为 .docx 或粘贴文本"})
        return 3
    except FileNotFoundError as exc:
        _print({"ok": False, "error": str(exc)})
        return 4
    except ValueError as exc:
        _print({"ok": False, "error": str(exc)})
        return 5
    except KeyError as exc:
        _print({"ok": False, "error": str(exc)})
        return 6


if __name__ == "__main__":
    sys.exit(main())
