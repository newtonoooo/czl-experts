"""数据体检：覆盖率、时效、口径一致性、结论置信度。

这一层的存在意义：让“我不知道”变成一个明确的字段，
而不是让模型用看起来很像样的句子把缺口填满。
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from . import schema

CONFIDENCE_ORDER = {"高": 3, "中": 2, "低": 1}


def _block_coverage(block: Dict[str, Any], keys: Tuple[str, ...]) -> Tuple[int, int]:
    got = sum(1 for k in keys if isinstance(block.get(k), (int, float)))
    return got, len(keys)


def coverage(data: Dict[str, Any]) -> Dict[str, Any]:
    biz = data.get("business") or {}
    meta = data.get("meta") or {}
    tech = data.get("technical") or {}

    per_block: Dict[str, Any] = {}
    for block, keys in schema.PRIMARY_FIELDS.items():
        src = tech if block == "technical" else (biz.get(block) or {})
        got, total = _block_coverage(src, keys)
        per_block[block] = {"got": got, "total": total, "ratio": round(got / total, 2) if total else 0.0}

    core_ok = bool(meta.get("code")) and per_block["valuation"]["got"] >= 2 and per_block["profitability"]["got"] >= 2
    return {"per_block": per_block, "core_ok": core_ok}


def _confidence(total_cov: float, fresh: Dict[str, Any], adjust_declared: bool, warnings: List[str]) -> str:
    level = 0
    if total_cov >= 0.85:
        level = 3
    elif total_cov >= 0.65:
        level = 2
    else:
        level = 1
    if fresh.get("status") == "stale":
        level -= 1
    if fresh.get("status") in ("unknown", "invalid"):
        level -= 1
    if not adjust_declared:
        level -= 1
    hard = [w for w in warnings if w.startswith("缺少") or "无法评分" in w]
    if len(hard) >= 3:
        level -= 1
    level = max(1, min(3, level))
    return {3: "高", 2: "中", 1: "低"}[level]


def audit(data: Dict[str, Any], result: Dict[str, Any], norm_report: Dict[str, List[str]]) -> Dict[str, Any]:
    cov = coverage(data)
    fresh = schema.freshness(data)
    meta = data.get("meta") or {}
    warnings: List[str] = list(norm_report.get("warnings") or [])

    if not cov["core_ok"]:
        warnings.append("估值或盈利能力核心字段不足，总分只作参考，不宜作为结论主依据")
    if fresh.get("status") == "stale":
        warnings.append(f"财务数据已过期：{fresh.get('hint')}（{fresh.get('days')} 天）")
    elif fresh.get("status") == "invalid":
        warnings.append(f"报告期异常：{fresh.get('hint')}")
    pe = (data.get("business") or {}).get("valuation", {}).get("pe_ttm")
    if isinstance(pe, (int, float)) and pe <= 0:
        warnings.append("PE 为负或为零（亏损/微利），估值维度结论不成立")
    if (data.get("technical") or {}).get("close") and not (data.get("series") or {}).get("closes"):
        warnings.append("技术指标为外部直接给出，未经本地序列复算，口径以数据源为准")

    confidence = _confidence(result.get("total_coverage") or 0.0, fresh, bool(meta.get("adjust")), warnings)
    must_verify: List[str] = []
    if not meta.get("adjust"):
        must_verify.append("向用户确认技术面用的是前复权还是不复权")
    if fresh.get("status") in ("acceptable", "stale"):
        must_verify.append("确认是否有更新的季报/业绩快报未纳入")
    if not (data.get("peers") or []):
        must_verify.append("同业样本为空，横向对标缺失，需补 3 家以上可比公司")
    if not (data.get("events") or []):
        must_verify.append("事件清单为空，需补最近一次公告/业绩披露")
    flow = (data.get("business") or {}).get("capital", {})
    if flow.get("main_net_inflow_20d") is not None and flow.get("main_net_inflow_20d_pct") is None:
        must_verify.append("主力资金仅有绝对额，未按市值标准化，跨股票比较时需谨慎")

    return {
        "coverage": cov,
        "freshness": fresh,
        "confidence": confidence,
        "warnings": warnings,
        "must_verify": must_verify,
        "normalized": norm_report.get("normalized") or [],
        "errors": norm_report.get("errors") or [],
    }
