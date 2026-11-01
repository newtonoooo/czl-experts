#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
W2 审查台：合同正文 -> 风险清单 + 改法 + 依据

方法：
1. 解析正文并切条（支持 .docx / .txt / .md）
2. 识别合同类型（未指定时按条款特征打分）
3. 要素覆盖检查（该类型必须具备的 8 个要素缺了哪个）
4. 规则引擎扫描：regex / numeric / absent / mutual / conditional_absent 五类检测
5. 打分并输出 Markdown 报告 + JSON 结构化结果

设计原则：
- 只报“能落到条款上”的问题，措辞与格式不计入风险
- 同一规则在同一位置只报一次，避免刷屏
- 每条结论都带依据；confidence=verify 的条目提示复核
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from cc_common import ensure_dir, read_text_any, split_clauses, write_json, write_text  # noqa: E402

HERE = Path(__file__).parent
REF = HERE.parent / "references"


def _load(name):
    return json.loads((REF / name).read_text(encoding="utf-8"))


def guess_type(text, lib):
    """按“要素命中数 + 别名命中数”打分，返回 (type_key, scores)。"""
    scores = {}
    for key, meta in lib["types"].items():
        score = 0
        for req in meta.get("required", []):
            if any(kw in text for kw in req["any"]):
                score += 2
        for alias in meta.get("aliases", []):
            if alias and alias in text:
                score += 1
        scores[key] = score
    best = max(scores, key=scores.get) if scores else None
    return best, scores


def _snippet(text, start, end, pad=18):
    left = max(0, start - pad)
    right = min(len(text), end + pad)
    seg = text[left:right].replace("\n", " ")
    return ("…" if left > 0 else "") + seg + ("…" if right < len(text) else "")


def _num_compare(value, op, threshold):
    if op == "gt":
        return value > threshold
    if op == "gte":
        return value >= threshold
    if op == "lt":
        return value < threshold
    if op == "lte":
        return value <= threshold
    if op == "eq":
        return abs(value - threshold) < 1e-9
    return False


def _detect(rule, clause_text, full_text):
    """返回该规则在该条款上的命中列表（通常 0 或 1 项）。"""
    kind = rule["kind"]
    det = rule.get("detect", {})
    hits = []

    if kind == "regex":
        try:
            m = re.search(det["pattern"], clause_text)
        except re.error:
            return hits
        if m:
            hits.append({"evidence": _snippet(clause_text, m.start(), m.end()), "value": m.group(0)})

    elif kind == "numeric":
        try:
            for m in re.finditer(det["pattern"], clause_text):
                try:
                    value = float(m.group(1))
                except (IndexError, ValueError):
                    continue
                if _num_compare(value, det.get("op", "gt"), float(det.get("threshold", 0))):
                    hits.append({
                        "evidence": _snippet(clause_text, m.start(), m.end()),
                        "value": "%g%s" % (value, det.get("unit", "")),
                        "threshold": "%s%s" % ("%g" % float(det.get("threshold", 0)), det.get("unit", "")),
                    })
                    break
        except re.error:
            return hits

    elif kind == "absent":
        if not any(kw in full_text for kw in det.get("any", [])):
            hits.append({"evidence": "全文未出现：%s" % "、".join(det.get("any", [])), "value": "缺失"})

    elif kind == "mutual":
        neutral = det.get("neutral") or []
        for pat in neutral:
            try:
                if re.search(pat, full_text):
                    return hits  # 全文已有对等表述（如“另一方有权解除”），不再判为不对称
            except re.error:
                continue
        pats = det.get("patterns", [])
        labels = det.get("labels", ["一方", "另一方"])
        try:
            found = [bool(re.search(p, clause_text)) for p in pats]
        except re.error:
            return hits
        if any(found) and not all(found):
            missing = [labels[i] for i, f in enumerate(found) if not f]
            hits.append({
                "evidence": "仅%s出现对应约定，%s未见" % (
                    "、".join([labels[i] for i, f in enumerate(found) if f]), "、".join(missing)),
                "value": "不对称",
            })

    elif kind == "conditional_absent":
        conds = det.get("if", [])
        absents = det.get("absent", [])
        if any(c in full_text for c in conds) and not any(a in full_text for a in absents):
            hits.append({
                "evidence": "出现“%s”，但全文缺少：%s" % ("、".join(conds), "、".join(absents)),
                "value": "缺失",
            })

    return hits


def review_text(text, type_key=None, stance="a", source=None):
    lib = _load("clause_library.json")
    rules_doc = _load("risk_rules.json")
    levels = rules_doc["levels"]

    guessed, scores = guess_type(text, lib)
    type_key = type_key or guessed
    if type_key not in lib["types"]:
        raise ValueError("无法识别合同类型，请用 --type 指定：%s" % "、".join(lib["types"].keys()))

    parsed = split_clauses(text)
    clauses = parsed["clauses"]
    full_text = text

    findings = []
    seen = set()
    # 这些规则看的是全文结构，不按条款逐条跑，否则同一问题会在每条里重复出现
    GLOBAL_KINDS = ("absent", "conditional_absent", "mutual")

    for clause in clauses:
        for rule in rules_doc["rules"]:
            if "*" not in rule["applies_to"] and type_key not in rule["applies_to"]:
                continue
            if rule["kind"] in GLOBAL_KINDS:
                continue
            for hit in _detect(rule, clause["text"], full_text):
                key = (rule["id"], clause["key"])
                if key in seen:
                    continue
                seen.add(key)
                findings.append({
                    "rule_id": rule["id"],
                    "name": rule["name"],
                    "level": rule["level"],
                    "clause": clause["key"],
                    "clause_index": clause["index"],
                    "clause_title": clause.get("title", ""),
                    "evidence": hit.get("evidence", ""),
                    "value": hit.get("value", ""),
                    "threshold": hit.get("threshold", ""),
                    "why": rule["why"],
                    "fix": rule["fix"],
                    "basis": rule.get("basis", {}),
                })

    for rule in rules_doc["rules"]:
        if rule["kind"] not in GLOBAL_KINDS:
            continue
        if "*" not in rule["applies_to"] and type_key not in rule["applies_to"]:
            continue
        for hit in _detect(rule, full_text, full_text):
            clause_key, clause_index, clause_title = "—", 999, "全文"
            if rule["kind"] == "mutual":
                pats = rule["detect"].get("patterns", [])
                present = None
                for p in pats:
                    try:
                        if re.search(p, full_text):
                            present = p
                            break
                    except re.error:
                        continue
                if present:
                    for c in clauses:
                        if re.search(present, c["text"]):
                            clause_key, clause_index, clause_title = c["key"], c["index"], c.get("title", "")
                            break
            findings.append({
                "rule_id": rule["id"],
                "name": rule["name"],
                "level": rule["level"],
                "clause": clause_key,
                "clause_index": clause_index,
                "clause_title": clause_title,
                "evidence": hit.get("evidence", ""),
                "value": hit.get("value", ""),
                "threshold": "",
                "why": rule["why"],
                "fix": rule["fix"],
                "basis": rule.get("basis", {}),
            })

    order = {"high": 0, "mid": 1, "low": 2}
    findings.sort(key=lambda f: (order.get(f["level"], 3), f.get("clause_index", 999)))

    # 要素覆盖
    coverage = []
    for req in lib["types"][type_key].get("required", []):
        hit = any(kw in text for kw in req["any"])
        coverage.append({"key": req["key"], "label": req["label"], "covered": hit,
                         "keywords": req["any"]})
    missing = [c for c in coverage if not c["covered"]]

    penalty = sum(levels[f["level"]]["weight"] for f in findings)
    penalty += sum(10 for c in missing if c["label"] in ("违约责任", "争议解决", "标的与数量"))
    penalty += sum(5 for c in missing if c["label"] not in ("违约责任", "争议解决", "标的与数量"))
    # 指数衰减：避免问题一多就直接归零，保留“很差”和“极差”的区分度
    import math

    score = int(round(100 * math.exp(-penalty / 70.0)))

    counts = {"high": 0, "mid": 0, "low": 0}
    for f in findings:
        counts[f["level"]] = counts.get(f["level"], 0) + 1

    if counts["high"] >= 3 or score < 55:
        verdict = "不建议按现文本签署"
    elif counts["high"] >= 1:
        verdict = "改完高风险条款再签"
    elif counts["mid"] >= 2:
        verdict = "可以谈，但先改中风险条款"
    elif findings:
        verdict = "整体可控，个别条款可优化"
    else:
        verdict = "未发现规则覆盖范围内的明显风险"

    return {
        "ok": True,
        "source": source,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "type": type_key,
        "type_label": lib["types"][type_key]["label"],
        "type_scores": scores,
        "stance": stance,
        "clause_count": len(clauses),
        "coverage": coverage,
        "missing_elements": missing,
        "findings": findings,
        "counts": counts,
        "score": score,
        "verdict": verdict,
    }


def render_markdown(result):
    label = {"high": "高", "mid": "中", "low": "低"}
    lines = []
    lines.append("# 合同风险审查报告")
    lines.append("")
    lines.append("- 合同类型：%s（识别置信度按要素命中打分，可人工指定）" % result["type_label"])
    lines.append("- 审查立场：%s" % ("甲方/委托方" if result["stance"] == "a" else ("乙方/受托方" if result["stance"] == "b" else "中立第三方")))
    lines.append("- 条款数量：%d 条" % result["clause_count"])
    lines.append("- 生成时间：%s" % result["generated_at"])
    if result.get("source"):
        lines.append("- 源文件：%s" % result["source"])
    lines.append("")
    lines.append("## 结论")
    lines.append("")
    lines.append("**%s**。风险分 %d/100，命中 %d 项问题（高 %d / 中 %d / 低 %d），缺失必备要素 %d 项。" % (
        result["verdict"], result["score"],
        sum(result["counts"].values()), result["counts"].get("high", 0),
        result["counts"].get("mid", 0), result["counts"].get("low", 0),
        len(result["missing_elements"])))
    lines.append("")

    if result["findings"]:
        lines.append("## 风险清单")
        lines.append("")
        lines.append("| 等级 | 位置 | 问题 | 触发证据 |")
        lines.append("|---|---|---|---|")
        for f in result["findings"]:
            ev = (f["evidence"] or "").replace("|", "／").replace("\n", " ")
            if len(ev) > 60:
                ev = ev[:60] + "…"
            lines.append("| %s | %s %s | %s | %s |" % (
                label.get(f["level"], f["level"]), f["clause"],
                (f["clause_title"] or "")[:12], f["name"], ev))
        lines.append("")

        top = result["findings"][:3]
        lines.append("## 必改条款（Top %d）" % len(top))
        lines.append("")
        for i, f in enumerate(top, 1):
            basis = f.get("basis", {})
            basis_txt = ""
            if basis:
                basis_txt = "（依据：%s%s，%s%s）" % (
                    basis.get("law", ""), basis.get("article", ""), basis.get("gist", ""),
                    "；条号请复核" if basis.get("confidence") == "verify" else "")
            lines.append("### %d. %s（%s，%s）" % (i, f["name"], f["clause"], label.get(f["level"], f["level"])))
            lines.append("")
            lines.append("- 原文/证据：%s" % f["evidence"])
            lines.append("- 为什么是问题：%s" % f["why"])
            lines.append("- 怎么改：%s" % f["fix"])
            if basis_txt:
                lines.append("- 依据：%s" % basis_txt.strip("（）"))
            lines.append("")

        rest = result["findings"][3:]
        if rest:
            lines.append("## 其余条目改法速查")
            lines.append("")
            for f in rest:
                lines.append("- **%s**（%s，%s）：%s" % (f["name"], f["clause"], label.get(f["level"], f["level"]), f["fix"]))
            lines.append("")

    missing = result["missing_elements"]
    if missing:
        lines.append("## 缺失的必备要素")
        lines.append("")
        for m in missing:
            lines.append("- **%s**：全文未出现 %s 相关表述，建议补齐。" % (m["label"], "、".join(m["keywords"][:4])))
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("本报告由规则引擎对文本做模式识别生成，用于自查与谈判准备，不构成法律意见。"
                 "规则覆盖的是常见失衡条款，无法覆盖交易背景、主体资信与行业监管；"
                 "标注“条号请复核”的依据，引用前请以国家法律法规数据库的现行文本核对。")
    lines.append("")
    return "\n".join(lines)


def review_file(path, type_key=None, stance="a", out_dir=".contract-workspace"):
    text, info = read_text_any(path)
    result = review_text(text, type_key=type_key, stance=stance, source=str(path))
    out = ensure_dir(out_dir)
    stem = Path(path).stem + "_review"
    md_path = write_text(out / (stem + ".md"), render_markdown(result))
    json_path = write_json(out / (stem + ".json"), result)
    result["report_md"] = md_path
    result["report_json"] = json_path
    result["source_info"] = info
    return result
