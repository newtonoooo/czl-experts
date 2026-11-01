#!/usr/bin/env python3
"""
uae_compliance.py - Pre-flight risk scan for UAE marketing copy.

Scans Arabic / English / Chinese marketing text against a rule base of
cultural and advertising risk patterns, then reports findings by severity.
It is a screening aid, not an approval authority: keyword matching cannot
judge context, so every High finding needs a human read.

Usage
-----
    python bin/uae_compliance.py --text "限时秒杀，史上最低价，保证有效"
    python bin/uae_compliance.py --file brief.md --sector beauty
    python bin/uae_compliance.py --text "..." --format json

Exit codes
----------
    0  no High findings (Medium/Low may still be present)
    1  at least one High finding: do not ship before rewriting
    2  bad usage
    4  rule base problem
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = ROOT / "skills" / "uae-brand-safety" / "data" / "risk_rules.json"

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
SEVERITY_LABEL = {"high": "High", "medium": "Medium", "low": "Low"}


def load_rules() -> list[dict]:
    if not RULES_PATH.exists():
        print(f"[FAIL] rule base missing: {RULES_PATH}", file=sys.stderr)
        raise SystemExit(4)
    try:
        return json.loads(RULES_PATH.read_text(encoding="utf-8"))["rules"]
    except (json.JSONDecodeError, KeyError) as exc:
        print(f"[FAIL] rule base unreadable: {exc}", file=sys.stderr)
        raise SystemExit(4)


def rule_applies(rule: dict, sector: str) -> bool:
    sectors = rule.get("applies_sectors", ["all"])
    return "all" in sectors or sector in sectors


def find_matches(text: str, pattern: str) -> list[int]:
    """Return match offsets. ASCII patterns use word boundaries to avoid false hits."""
    if pattern.isascii():
        regex = re.compile(r"(?<![a-z0-9])" + re.escape(pattern) + r"(?![a-z0-9])", re.IGNORECASE)
        return [m.start() for m in regex.finditer(text)]
    return [m.start() for m in re.finditer(re.escape(pattern), text)]


def scan(text: str, sector: str) -> dict:
    rules = load_rules()
    findings = []
    for rule in rules:
        if not rule_applies(rule, sector):
            continue
        hits = []
        for pattern in rule.get("patterns", []):
            for pos in find_matches(text, pattern):
                start = max(0, pos - 18)
                end = min(len(text), pos + len(pattern) + 18)
                hits.append({
                    "pattern": pattern,
                    "position": pos,
                    "context": text[start:end].replace("\n", " ").strip(),
                })
        if hits:
            findings.append({
                "rule_id": rule["id"],
                "category": rule["category"],
                "severity": rule["severity"],
                "message": rule["message"],
                "guidance": rule["guidance"],
                "alternative": rule["alternative"],
                "hits": hits,
            })

    findings.sort(key=lambda f: (SEVERITY_ORDER[f["severity"]], f["rule_id"]))
    counts = {"high": 0, "medium": 0, "low": 0}
    for f in findings:
        counts[f["severity"]] += 1

    return {
        "sector": sector,
        "text_length": len(text),
        "counts": counts,
        "findings": findings,
        "verdict": "block" if counts["high"] else ("review" if counts["medium"] else "pass"),
    }


def to_markdown(result: dict) -> str:
    c = result["counts"]
    verdict_map = {
        "block": "**阻断**：存在 High 风险项，改写后才能交付。",
        "review": "**需复核**：存在 Medium 风险项，交付时须置顶风险提示。",
        "pass": "**通过**：未命中规则库中的风险模式（仍需人工确认语境）。",
    }
    lines = [f"## 合规扫描结果（行业：{result['sector']}）\n"]
    lines.append(f"命中：High {c['high']} · Medium {c['medium']} · Low {c['low']}")
    lines.append(f"\n结论：{verdict_map[result['verdict']]}\n")

    if not result["findings"]:
        lines.append("未发现规则库命中的表达。\n")
        lines.append("> 注意：关键词扫描只能发现显性表达。图片构图、镜头语言、隐喻与方言语气仍需人工复核。")
        return "\n".join(lines)

    lines.append("| 等级 | 规则 | 类别 | 命中表达 | 处理建议 |")
    lines.append("|------|------|------|---------|---------|")
    for f in result["findings"]:
        patterns = "、".join(sorted({h["pattern"] for h in f["hits"]}))
        lines.append(f"| {SEVERITY_LABEL[f['severity']]} | {f['rule_id']} | {f['category']} | {patterns} | {f['alternative']} |")

    lines.append("\n### 逐条说明\n")
    for f in result["findings"]:
        lines.append(f"**{f['rule_id']} · {f['category']} · {SEVERITY_LABEL[f['severity']]}**")
        lines.append(f"- 问题：{f['message']}")
        lines.append(f"- 依据：{f['guidance']}")
        lines.append(f"- 替代：{f['alternative']}")
        for h in f["hits"][:3]:
            lines.append(f"- 上下文：…{h['context']}…")
        lines.append("")

    lines.append("> 扫描为辅助手段，不构成法律意见。涉及牌照、审批、内容审查的最终结论，须由主管机构与本地法律顾问确认。")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="UAE marketing copy risk scan.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", help="copy to scan")
    group.add_argument("--file", help="path to a text or markdown file to scan")
    parser.add_argument("--sector", default="all",
                        help="sector id to narrow the rule set (default: all)")
    parser.add_argument("--format", default="markdown", choices=["markdown", "json"])
    args = parser.parse_args(argv)

    if args.file:
        path = Path(args.file)
        if not path.exists():
            print(f"[FAIL] file not found: {path}", file=sys.stderr)
            return 2
        text = path.read_text(encoding="utf-8", errors="replace")
    else:
        text = args.text or ""

    if not text.strip():
        print("[FAIL] empty input", file=sys.stderr)
        return 2

    result = scan(text, args.sector)
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(to_markdown(result))

    return 1 if result["counts"]["high"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
