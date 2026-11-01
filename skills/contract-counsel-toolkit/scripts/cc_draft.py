#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
W1 起草台：业务要件 -> 条款装配 -> .docx 合同文本

流程：
1. 解析合同类型（支持别名，如“购销”“租房”“NDA”）
2. 合并三层默认值：全局默认 < 类型默认 < 用户输入
3. 计算派生字段：金额大写、期末日、押金、试用期工资、管辖地
4. 按条款库装配正文块，渲染 docx 与 md 预览
5. 输出 draft_meta.json（含履约节点提示，供 W5 导入）

异常处理：
- 类型无法识别 -> 抛出 ValueError，CLI 返回可选类型清单
- 条款库缺字段 -> 用默认值并记入 used_defaults，不静默留白
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from cc_common import amount_to_cn, ensure_dir, today_str, write_json, write_text  # noqa: E402
from cc_docx import build_docx, verify_docx  # noqa: E402

CN_ORDINALS = [
    "一", "二", "三", "四", "五", "六", "七", "八", "九", "十",
    "十一", "十二", "十三", "十四", "十五", "十六", "十七", "十八", "十九", "二十",
    "二十一", "二十二", "二十三", "二十四", "二十五", "二十六", "二十七", "二十八",
]

PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def _ordinal(n):
    return CN_ORDINALS[n - 1] if 1 <= n <= len(CN_ORDINALS) else str(n)


def load_library():
    lib_path = Path(__file__).parent.parent / "references" / "clause_library.json"
    import json

    return json.loads(lib_path.read_text(encoding="utf-8"))


def resolve_type(lib, key):
    types = lib["types"]
    if key in types:
        return key
    low = (key or "").strip().lower()
    for name, meta in types.items():
        aliases = [a.lower() for a in meta.get("aliases", [])]
        if low == name.lower() or low in aliases or any(low in a or a in low for a in aliases if low):
            return name
    raise ValueError(
        "无法识别合同类型 %r，可选类型：%s"
        % (key, "、".join("%s(%s)" % (k, v["label"]) for k, v in types.items()))
    )


def _add_months(d, months):
    y, m = d.year, d.month + int(months)
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    day = min(d.day, [31, 29 if y % 4 == 0 and (y % 100 != 0 or y % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1])
    from datetime import date

    return date(y, m, day)


def build_placeholders(lib, type_key, values):
    """合并默认值并计算派生字段。返回 (placeholders, used_defaults)。"""
    from datetime import date

    meta = lib["types"][type_key]
    defaults = dict(lib.get("global_defaults", {}))
    defaults.update(meta.get("defaults", {}))

    values = {k: v for k, v in (values or {}).items() if v not in (None, "")}
    used_defaults = {}
    ph = {}
    for k, v in defaults.items():
        if k in values:
            ph[k] = values[k]
        else:
            ph[k] = v
            used_defaults[k] = v
    for k, v in values.items():
        ph.setdefault(k, v)

    stance = str(values.get("stance", "a")).lower()
    ph["stance"] = stance
    if "court" not in values:
        ph["court"] = {"a": "甲方所在地", "b": "乙方所在地"}.get(stance, "被告住所地")
        used_defaults["court"] = ph["court"]

    ph["today"] = values.get("sign_date") or today_str()
    ph["sign_date"] = ph["today"]
    ph["contract_no"] = values.get("contract_no") or "CC-%s-001" % ph["today"][:4]

    # 金额与中文大写
    amount = ph.get("amount")
    if amount not in (None, ""):
        try:
            num = round(float(str(amount).replace(",", "")), 2)
            ph["amount_num"] = num
            ph["amount"] = "{:,}".format(int(num)) if num == int(num) else "{:,.2f}".format(num)
            ph.setdefault("amount_cn", amount_to_cn(num))
        except (TypeError, ValueError):
            used_defaults["amount"] = "输入无法解析为数字，已按原文保留：%s" % amount
    else:
        ph["amount"] = "＿＿"
        ph["amount_cn"] = "＿＿"
        used_defaults["amount"] = "未提供金额，正文留空待填"

    # 期限与起止日
    start = values.get("start_date")
    if start:
        try:
            start_date = date.fromisoformat(start)
        except ValueError:
            start_date = date.today()
            used_defaults["start_date"] = "日期格式无法解析，已按今天处理"
    else:
        start_date = date.today()
        used_defaults["start_date"] = start_date.isoformat()
    ph["start_date"] = start_date.isoformat()

    term_months = ph.get("term_months")
    if not values.get("end_date"):
        computed = None
        if term_months:
            try:
                computed = _add_months(start_date, int(term_months)).isoformat()
            except (TypeError, ValueError):
                computed = None
        elif ph.get("delivery_days"):
            # 服务类合同按"起始日 + 服务天数"推算到期日
            try:
                from datetime import timedelta

                computed = (start_date + timedelta(days=int(ph["delivery_days"]))).isoformat()
            except (TypeError, ValueError):
                computed = None
        if computed:
            ph["end_date"] = computed
            used_defaults.setdefault("end_date", computed)
    if "end_date" in ph and not ph.get("end_date"):
        ph["end_date"] = "＿＿"

    # 租赁押金
    if type_key == "lease" and "deposit" not in values and ph.get("amount"):
        try:
            months = float(ph.get("deposit_months", 1))
            ph["deposit"] = "{:,.0f}".format(float(ph["amount_num"]) * months)
            used_defaults["deposit"] = ph["deposit"]
        except (TypeError, ValueError, KeyError):
            ph["deposit"] = "＿＿"

    # 劳动合同试用期工资
    if type_key == "labor" and "probation_salary" not in values and ph.get("amount_num"):
        ph["probation_salary"] = "{:,.0f}".format(float(ph["amount_num"]) * 0.8)
        used_defaults["probation_salary"] = ph["probation_salary"] + "（按约定工资 80%）"

    for k in ("address", "area", "cert_no", "pay_cycle", "fee_bearer", "work_system",
              "work_place", "job_title", "welfare", "purpose", "repay_method", "guarantee",
              "role_a", "role_b", "a_name", "b_name", "a_id", "b_id", "a_addr", "b_addr",
              "a_legal", "b_legal", "a_contact", "b_contact", "a_account", "b_account"):
        if k not in ph:
            ph[k] = values.get(k, "")
    ph.setdefault("role_a", "甲方")
    ph.setdefault("role_b", "乙方")
    if type_key == "purchase":
        ph["role_a"] = ph.get("role_a") or "甲方（采购方）"
        ph["role_b"] = ph.get("role_b") or "乙方（供货方）"
    # 记录被程序计算覆盖后的真实值，避免“建议确认项”里显示模板占位
    for k in ("contract_no", "court", "start_date", "end_date", "amount", "amount_cn", "deposit", "probation_salary"):
        if k in used_defaults:
            used_defaults[k] = ph.get(k, used_defaults[k])
    return ph, used_defaults


def _fill(text, ph, missing):
    def rep(m):
        key = m.group(1)
        if key in ph and ph[key] not in (None, ""):
            return str(ph[key])
        missing.add(key)
        return "＿＿"

    return PLACEHOLDER.sub(rep, text or "")


def assemble(lib, type_key, ph, spec, missing):
    meta = lib["types"][type_key]
    blocks = []
    title = spec.get("title") or meta["default_title"]
    blocks.append({"t": "title", "text": title})
    blocks.append({"t": "subtitle", "text": "合同编号：%s　　签订地点：%s" % (ph.get("contract_no", ""), ph.get("sign_place", ""))})

    for side, role_key, name_key in (("a", "role_a", "a_name"), ("b", "role_b", "b_name")):
        role = ph.get(role_key) or ("甲方" if side == "a" else "乙方")
        name = ph.get(name_key) or "＿＿"
        blocks.append({"t": "para", "text": "%s：%s" % (role, name), "indent": False})
        rows = [
            ("住所地", ph.get(side + "_addr")),
            ("统一社会信用代码/身份证号", ph.get(side + "_id")),
            ("法定代表人/负责人", ph.get(side + "_legal")),
            ("联系人及电话", ph.get(side + "_contact")),
        ]
        for label, val in rows:
            if val:
                blocks.append({"t": "para", "text": "%s：%s" % (label, val), "indent": False})
        blocks.append({"t": "para", "text": "", "indent": False})

    recital = _fill(meta.get("recitals", ""), ph, missing)
    if recital:
        blocks.append({"t": "para", "text": recital})

    exclude = set(spec.get("clauses_exclude") or [])
    overrides = spec.get("clauses_override") or {}
    idx = 0
    for clause in meta["clauses"]:
        if clause["id"] in exclude:
            continue
        idx += 1
        blocks.append({"t": "h1", "text": "第%s条　%s" % (_ordinal(idx), clause["title"])})
        body = overrides.get(clause["id"]) or overrides.get(clause["title"]) or clause["body"]
        body = _fill(body, ph, missing)
        for line in body.split("\n"):
            line = line.strip()
            if not line:
                continue
            blocks.append({"t": "para", "text": line})

    extra = spec.get("clauses_add") or []
    for item in extra:
        idx += 1
        blocks.append({"t": "h1", "text": "第%s条　%s" % (_ordinal(idx), item.get("title", "补充约定"))})
        for line in _fill(item.get("body", ""), ph, missing).split("\n"):
            if line.strip():
                blocks.append({"t": "para", "text": line.strip()})

    blocks.append({"t": "para", "text": ""})
    blocks.append({"t": "para", "text": "（以下无正文，为签署页）", "indent": False, "align": "center"})
    blocks.append({"t": "sign",
                   "left": ["甲方（盖章）：", "", "法定代表人/授权代表签字：", "", "签署日期：　　　年　　月　　日"],
                   "right": ["乙方（盖章）：", "", "法定代表人/授权代表签字：", "", "签署日期：　　　年　　月　　日"]})
    return blocks, idx


def draft(type_key, values, out_dir=".contract-workspace", spec=None):
    lib = load_library()
    resolved = resolve_type(lib, type_key)
    values = dict(values or {})
    spec = dict(spec or {})
    ph, used_defaults = build_placeholders(lib, resolved, values)
    missing = set()

    blocks, clause_count = assemble(lib, resolved, ph, spec, missing)

    out = ensure_dir(out_dir)
    stem = spec.get("file_stem") or "%s_%s" % (resolved, ph.get("today", today_str()).replace("-", ""))
    docx_path = build_docx(
        {"meta": {"title": spec.get("title") or lib["types"][resolved]["default_title"],
                  "creator": "契约守门人",
                  "subject": "%s（czl-contract-counsel 生成）" % lib["types"][resolved]["label"]},
         "blocks": blocks},
        out / (stem + ".docx"),
    )

    md_lines = []
    for b in blocks:
        if b["t"] in ("title",):
            md_lines.append("# " + b["text"] + "\n")
        elif b["t"] == "subtitle":
            md_lines.append("*" + b["text"] + "*\n")
        elif b["t"] == "h1":
            md_lines.append("\n## " + b["text"] + "\n")
        elif b["t"] == "para" and b["text"]:
            md_lines.append(b["text"] + "\n")
        elif b["t"] == "sign":
            md_lines.append("\n" + "　　".join(b["left"][:1]) + "　　　　　　　　" + b["right"][0] + "\n")
    md_path = write_text(out / (stem + ".md"), "\n".join(md_lines))

    verify = verify_docx(docx_path)
    meta = {
        "ok": verify["ok"],
        "type": resolved,
        "type_label": lib["types"][resolved]["label"],
        "title": spec.get("title") or lib["types"][resolved]["default_title"],
        "docx": docx_path,
        "markdown": md_path,
        "clause_count": clause_count,
        "placeholders": ph,
        "used_defaults": used_defaults,
        "missing_placeholders": sorted(missing),
        "ledger_hints": lib["types"][resolved].get("ledger_hints", []),
        "stance": ph.get("stance"),
        "verify": verify,
    }
    meta_path = write_json(out / (stem + ".meta.json"), meta)
    meta["meta_file"] = meta_path
    return meta
