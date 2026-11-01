"""命令行入口。技能提示词里给模型用的就是这三条命令。

用法：
    python -m panorama.cli check  --input data/sample.json
    python -m panorama.cli score  --input data/sample.json --out score.json
    python -m panorama.cli report --input data/sample.json --out report.md

退出码：
    0 成功；1 运行异常；2 输入不合法（缺标的/结构错误）。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict

from . import schema
from . import report as report_mod
from . import scorecard
from . import qa as qa_mod
from . import levels as levels_mod
from . import __version__


def _load(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _dump(obj: Any, path: str) -> None:
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        if isinstance(obj, str):
            fh.write(obj)
        else:
            json.dump(obj, fh, ensure_ascii=False, indent=2)


def cmd_check(args) -> int:
    payload = _load(args.input)
    data, nr = schema.normalize(payload)
    cov = qa_mod.coverage(data)
    print(json.dumps({
        "ok": not nr["errors"],
        "errors": nr["errors"],
        "warnings": nr["warnings"],
        "normalized": nr["normalized"],
        "coverage": cov,
        "freshness": schema.freshness(data),
    }, ensure_ascii=False, indent=2))
    return 0 if not nr["errors"] else 2


def cmd_score(args) -> int:
    payload = _load(args.input)
    out = report_mod.run(payload, with_report=False)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if args.out:
        _dump(out, args.out)
    return 0 if out.get("ok") else 2


def cmd_report(args) -> int:
    payload = _load(args.input)
    data, nr = schema.normalize(payload)
    if nr["errors"]:
        print(json.dumps({"ok": False, "errors": nr["errors"]}, ensure_ascii=False, indent=2))
        return 2
    result = scorecard.evaluate(data)
    audit = qa_mod.audit(data, result, nr)
    md = report_mod.render_markdown(data, result, audit)
    if args.out:
        _dump(md, args.out)
        print(json.dumps({"ok": True, "out": os.path.abspath(args.out),
                          "chars": len(md),
                          "overall": result["overall"], "grade": result["grade"]},
                         ensure_ascii=False, indent=2))
    else:
        sys.stdout.write(md)
    return 0


def cmd_levels(args) -> int:
    payload = _load(args.input)
    data, nr = schema.normalize(payload)
    if nr["errors"]:
        print(json.dumps({"ok": False, "errors": nr["errors"]}, ensure_ascii=False))
        return 2
    print(json.dumps(levels_mod.compute_levels(data.get("technical") or {}), ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="panorama", description="个股全景诊断引擎 v" + __version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="只做数据体检，不打分")
    c.add_argument("--input", required=True)
    c.set_defaults(func=cmd_check)

    s = sub.add_parser("score", help="输出六维评分 JSON")
    s.add_argument("--input", required=True)
    s.add_argument("--out")
    s.set_defaults(func=cmd_score)

    r = sub.add_parser("report", help="输出 Markdown 诊断报告")
    r.add_argument("--input", required=True)
    r.add_argument("--out")
    r.set_defaults(func=cmd_report)

    l = sub.add_parser("levels", help="只算关键价位")
    l.add_argument("--input", required=True)
    l.set_defaults(func=cmd_levels)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as exc:
        print(json.dumps({"ok": False, "errors": [f"输入文件不存在：{exc}"]}, ensure_ascii=False))
        return 2
    except json.JSONDecodeError as exc:
        print(json.dumps({"ok": False, "errors": [f"JSON 解析失败：{exc}"]}, ensure_ascii=False))
        return 2
    except Exception as exc:  # 兜底：把异常原样抛出，便于定位而不是静默失败
        print(json.dumps({"ok": False, "errors": [f"{type(exc).__name__}: {exc}"]}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
