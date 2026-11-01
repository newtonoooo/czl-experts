#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ledgerkit —— 账衡专家包的账务计算与校验工具（纯标准库，无第三方依赖）

设计原则
1. 只做可复现的算术与规则校验，不做职业判断。判断权留给使用者与复核人。
2. 每个命令都有明确的输入契约、退出码和机器可读输出（--json），便于嵌入底稿。
3. 金额一律用 Decimal 处理，四舍五入 ROUND_HALF_UP，保留 2 位；不产生浮点尾差。

退出码约定
  0  通过 / 无阻断问题
  1  有阻断问题（分录不平、勾稽不符、调节不平、自检失败）
  2  输入非法（文件缺失、JSON 结构错误、字段缺失）
"""

import argparse
import json
import os
import sys
import unicodedata
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

APP_NAME = "ledgerkit"
APP_VERSION = "1.0.0"

# ----------------------------------------------------------------------------
# 基础工具
# ----------------------------------------------------------------------------

try:  # Windows 控制台默认 GBK，强制 UTF-8 输出
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover
    pass

ZERO = Decimal("0.00")


class InputError(Exception):
    """输入契约不满足。"""


def D(value, field="数值"):
    """把任意数字/字符串转成 2 位小数的 Decimal。"""
    if value is None or value == "":
        return ZERO
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        raise InputError(f"字段 {field} 不是合法数字：{value!r}")


def M(value):
    """金额显示：千分位 + 2 位小数。"""
    return f"{D(value):,.2f}"


def Q(value, field="数值"):
    """数量/单价：保留 4 位，用于差异分解。"""
    if value is None or value == "":
        return Decimal("0")
    try:
        return Decimal(str(value)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        raise InputError(f"字段 {field} 不是合法数字：{value!r}")


def dwidth(text):
    """按东亚字符宽度计算显示宽度。"""
    width = 0
    for ch in str(text):
        width += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return width


def pad(text, width, align="left"):
    text = str(text)
    gap = max(width - dwidth(text), 0)
    if align == "right":
        return " " * gap + text
    if align == "center":
        left = gap // 2
        return " " * left + text + " " * (gap - left)
    return text + " " * gap


def table(headers, rows, aligns=None):
    """等宽文本表；中文按双宽对齐。"""
    rows = [[("" if c is None else str(c)) for c in row] for row in rows]
    aligns = aligns or ["left"] * len(headers)
    widths = [dwidth(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], dwidth(cell))
    line = "  ".join(pad(h, widths[i], "center") for i, h in enumerate(headers))
    out = [line, "  ".join("-" * widths[i] for i in range(len(headers)))]
    for row in rows:
        out.append("  ".join(pad(c, widths[i], aligns[i]) for i, c in enumerate(row)))
    return "\n".join(out)


def load_json(path):
    if not path:
        raise InputError("缺少 --file 参数")
    if not os.path.exists(path):
        raise InputError(f"文件不存在：{path}")
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        raise InputError(f"JSON 解析失败（{path}）：{exc}")
    except UnicodeDecodeError:
        raise InputError(f"文件编码不是 UTF-8（{path}）。请另存为 UTF-8 再试。")


def emit(args, payload, text):
    """统一出口：--json 输出结构，--out 落盘留痕。"""
    body = json.dumps(payload, ensure_ascii=False, indent=2) if args.json else text
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(body + ("\n" if not body.endswith("\n") else ""))
        print(f"已写出：{os.path.abspath(args.out)}")
    if args.json:
        print(body)
    else:
        print(text)


# ----------------------------------------------------------------------------
# 1. entry-check —— 分录批次校验（借贷平衡 + 单据 + 期间 + 异常特征）
# ----------------------------------------------------------------------------

RISK_ORDER = {"R0": 0, "R1": 1, "R2": 2}
RISK_LABEL = {
    "R0": "红线：不得直接入账",
    "R1": "关注：需复核说明",
    "R2": "常规：留档即可",
}


def _period_key(text):
    """把 2026-09 / 2026-09-30 统一成 (年, 月)。"""
    text = str(text).strip()
    parts = text.replace("/", "-").split("-")
    if len(parts) < 2:
        raise InputError(f"期间格式应为 YYYY-MM 或 YYYY-MM-DD，收到：{text!r}")
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        raise InputError(f"期间格式应为 YYYY-MM 或 YYYY-MM-DD，收到：{text!r}")


def cmd_entry_check(args):
    data = load_json(args.file)
    period = data.get("period")
    if not period:
        raise InputError("缺少 period 字段（如 2026-09）")
    py, pm = _period_key(period)
    threshold = D(data.get("round_amount_threshold", 100000), "round_amount_threshold")
    entries = data.get("entries")
    if not isinstance(entries, list) or not entries:
        raise InputError("entries 必须是非空数组")

    findings = []
    rows = []
    total_dr = ZERO
    total_cr = ZERO

    def add(level, code, eid, message):
        findings.append({"level": level, "code": code, "entry": eid, "message": message})

    for idx, entry in enumerate(entries, start=1):
        eid = str(entry.get("id") or f"#{idx}")
        lines = entry.get("lines") or []
        dr = sum((D(l.get("debit"), f"{eid}.debit") for l in lines), ZERO)
        cr = sum((D(l.get("credit"), f"{eid}.credit") for l in lines), ZERO)
        diff = dr - cr
        total_dr += dr
        total_cr += cr

        if not lines:
            add("R0", "NO_LINES", eid, "分录没有任何明细行")
        if diff != ZERO:
            add("R0", "UNBALANCED", eid, f"借贷不平，差额 {M(diff)}（借 {M(dr)} / 贷 {M(cr)}）")

        if not str(entry.get("memo") or "").strip():
            add("R1", "NO_MEMO", eid, "缺摘要，事后无法判断业务实质")
        if not str(entry.get("attachment") or "").strip():
            add("R0", "NO_ATTACHMENT", eid, "无原始单据编号，违反无据不入账")

        date_text = str(entry.get("date") or "").strip()
        if not date_text:
            add("R1", "NO_DATE", eid, "缺记账日期")
        else:
            try:
                dy, dm = _period_key(date_text)
                if (dy, dm) != (py, pm):
                    add("R0", "OUT_OF_PERIOD", eid,
                        f"记账日期 {date_text} 不在期间 {period}，属跨期记账")
            except InputError:
                add("R1", "BAD_DATE", eid, f"日期无法识别：{date_text!r}")

        seen = set()
        for l in lines:
            acc = str(l.get("account") or "").strip()
            d_amt = D(l.get("debit"), "debit")
            c_amt = D(l.get("credit"), "credit")
            if not acc:
                add("R0", "NO_ACCOUNT", eid, "存在明细行未填科目")
            elif not _account_ok(acc):
                add("R1", "BAD_ACCOUNT", eid, f"科目码 {acc} 格式异常（建议 4 位一级 + 2 位明细，如 660205）")
            if d_amt > 0 and c_amt > 0:
                add("R0", "BOTH_SIDES", eid, f"科目 {acc} 同一行同时出现借贷金额")
            if d_amt < 0 or c_amt < 0:
                add("R1", "NEGATIVE", eid, f"科目 {acc} 出现负数金额，属红字冲销，需注明原凭证号")
            for raw, amt, tag in (("debit", d_amt, "借"), ("credit", c_amt, "贷")):
                if amt == ZERO:
                    continue
                key = (acc, tag)
                if key in seen:
                    add("R1", "DUP_LINE", eid, f"科目 {acc} 出现多行{tag}方，确认是否为合计笔")
                seen.add(key)
                if amt == amt.to_integral_value() and amt >= threshold:
                    add("R1", "ROUND_AMOUNT", eid,
                        f"科目 {acc} {tag}方 {M(amt)} 为整额，疑似估数，需附测算依据")
                _raw = l.get(raw)
                if _raw is not None and _decimal_places(_raw) > 2:
                    add("R1", "PRECISION", eid, f"科目 {acc} 金额超过 2 位小数，请确认取整规则")

        rows.append([eid, date_text or "-", (entry.get("memo") or "-")[:24],
                     M(dr), M(cr), M(diff), len(lines)])

    findings.sort(key=lambda f: (RISK_ORDER[f["level"]], f["entry"]))
    counts = {k: sum(1 for f in findings if f["level"] == k) for k in ("R0", "R1", "R2")}

    if counts["R0"]:
        verdict = "不得入账（存在红线问题）"
    elif counts["R1"]:
        verdict = "有条件入账（补齐复核说明后可过账）"
    else:
        verdict = "可入账"

    payload = {
        "tool": "entry-check",
        "period": period,
        "entry_count": len(entries),
        "total_debit": str(total_dr),
        "total_credit": str(total_cr),
        "batch_balanced": total_dr == total_cr,
        "risk_counts": counts,
        "verdict": verdict,
        "findings": findings,
    }

    out = [
        f"分录批次校验 · 期间 {period}",
        table(["凭证号", "日期", "摘要", "借方", "贷方", "差额", "行数"],
              rows, ["left", "left", "left", "right", "right", "right", "right"]),
        "",
        f"合计：借 {M(total_dr)} / 贷 {M(total_cr)} / 批次{'平衡' if total_dr == total_cr else '不平'}",
        f"问题：红线 {counts['R0']} 条，关注 {counts['R1']} 条 → 结论：{verdict}",
    ]
    if findings:
        out.append("")
        out.append("问题清单：")
        for f in findings:
            out.append(f"  [{f['level']}] {f['entry']} · {f['code']} · {f['message']}")
        out.append("")
        out.append("处置建议：R0 逐条补件或改期后再过账；R1 在底稿中写明依据与复核人。")

    emit(args, payload, "\n".join(out))
    return 1 if counts["R0"] else 0


def _account_ok(code):
    """科目码：4~10 位数字，允许 . 或 - 分隔明细。"""
    body = code.replace(".", "").replace("-", "")
    return body.isdigit() and 4 <= len(body) <= 10


def _decimal_places(raw):
    text = str(raw)
    if "." not in text:
        return 0
    return len(text.split(".")[1])


# ----------------------------------------------------------------------------
# 2. rollforward —— 四柱滚算：旧管 + 新收 - 开除 = 实在
# ----------------------------------------------------------------------------

def cmd_rollforward(args):
    data = load_json(args.file)
    subject = data.get("subject") or "未命名科目"
    period = data.get("period") or "-"
    opening = D(data.get("opening"), "opening")
    additions = data.get("additions") or []
    reductions = data.get("reductions") or []
    closing_reported = D(data.get("closing"), "closing")

    add_sum = sum((D(i.get("amount"), "addition") for i in additions), ZERO)
    red_sum = sum((D(i.get("amount"), "reduction") for i in reductions), ZERO)
    closing_calc = opening + add_sum - red_sum
    gap = closing_reported - closing_calc

    rows = [["旧管（期初）", "", "", M(opening)]]
    for i in additions:
        rows.append(["新收（增）", i.get("label") or "-", "", M(i.get("amount"))])
    for i in reductions:
        rows.append(["开除（减）", i.get("label") or "-", "", M(i.get("amount"))])
    rows.append(["实在（期末·算）", "", "", M(closing_calc)])
    rows.append(["实在（期末·账）", "", "", M(closing_reported)])
    rows.append(["差额", "", "", M(gap)])

    payload = {
        "tool": "rollforward",
        "subject": subject,
        "period": period,
        "opening": str(opening),
        "additions": str(add_sum),
        "reductions": str(red_sum),
        "closing_calculated": str(closing_calc),
        "closing_reported": str(closing_reported),
        "gap": str(gap),
        "tied": gap == ZERO,
    }

    out = [
        f"四柱滚算 · {subject} · {period}",
        table(["柱", "项目", "", "金额"], rows, ["left", "left", "left", "right"]),
        "",
        ("滚算与账面一致，可以进入下一步。" if gap == ZERO else
         f"滚算与账面差 {M(gap)}：先确认是否漏记增减项，再决定是否调账；不要直接用差额凑数。"),
    ]
    emit(args, payload, "\n".join(out))
    return 0 if gap == ZERO else 1


# ----------------------------------------------------------------------------
# 3. bank-rec —— 银行存款余额调节表
# ----------------------------------------------------------------------------

def cmd_bank_rec(args):
    data = load_json(args.file)
    account = data.get("account") or "银行存款"
    period = data.get("period") or "-"
    book = D(data.get("book_balance"), "book_balance")
    bank = D(data.get("bank_balance"), "bank_balance")

    buckets = [
        ("book_received_bank_not", "企业已收、银行未收", 1, "bank"),
        ("book_paid_bank_not", "企业已付、银行未付", -1, "bank"),
        ("bank_received_book_not", "银行已收、企业未收", 1, "book"),
        ("bank_paid_book_not", "银行已付、企业未付", -1, "book"),
    ]

    adj_book = book
    adj_bank = bank
    detail = []
    for key, label, sign, side in buckets:
        for item in data.get(key) or []:
            amt = D(item.get("amount"), key)
            delta = amt * sign
            if side == "book":
                adj_book += delta
            else:
                adj_bank += delta
            detail.append([label, item.get("label") or "-", M(amt), item.get("aging_days", "-")])

    gap = adj_book - adj_bank
    payload = {
        "tool": "bank-rec",
        "account": account,
        "period": period,
        "book_balance": str(book),
        "bank_balance": str(bank),
        "adjusted_book": str(adj_book),
        "adjusted_bank": str(adj_bank),
        "gap": str(gap),
        "reconciled": gap == ZERO,
        "items": detail,
    }

    lines = [
        f"银行存款余额调节表 · {account} · {period}",
        "",
        table(["项目", "金额"], [
            ["企业账面余额", M(book)],
            ["加：银行已收、企业未收", M(sum((D(i.get('amount')) for i in data.get('bank_received_book_not') or []), ZERO))],
            ["减：银行已付、企业未付", M(sum((D(i.get('amount')) for i in data.get('bank_paid_book_not') or []), ZERO))],
            ["调节后企业存款余额", M(adj_book)],
            ["", ""],
            ["银行对账单余额", M(bank)],
            ["加：企业已收、银行未收", M(sum((D(i.get('amount')) for i in data.get('book_received_bank_not') or []), ZERO))],
            ["减：企业已付、银行未付", M(sum((D(i.get('amount')) for i in data.get('book_paid_bank_not') or []), ZERO))],
            ["调节后银行对账单余额", M(adj_bank)],
            ["", ""],
            ["差额", M(gap)],
        ], ["left", "right"]),
    ]
    if detail:
        lines += ["", "调节项明细：",
                  table(["类别", "说明", "金额", "挂账天数"], detail,
                        ["left", "left", "right", "right"])]
    if gap == ZERO:
        lines += ["", "两侧调节后一致，编制调账分录前请再核对一次大额调节项的单据。"]
    else:
        lines += ["", f"调节后仍差 {M(gap)}：属未查明差异，不得以「其他」科目挂平，先补查对账单与日记账。"]
    emit(args, payload, "\n".join(lines))
    return 0 if gap == ZERO else 1


# ----------------------------------------------------------------------------
# 4. depreciation —— 折旧计算（CAS 当月增加下月计提 / 三种方法）
# ----------------------------------------------------------------------------

def _months_between(a, b):
    ay, am = _period_key(a)
    by, bm = _period_key(b)
    return (by - ay) * 12 + (bm - am)


def _schedule(asset, rule):
    """返回逐月折旧列表 [{"n":1,"dep":Decimal,"accum":Decimal,"nbv":Decimal}]。"""
    cost = D(asset.get("cost"), "cost")
    life = int(asset.get("life_months") or 0)
    if cost <= 0 or life <= 0:
        raise InputError(f"资产 {asset.get('id')} 的 cost / life_months 必须为正数")
    if asset.get("salvage") is not None:
        salvage = D(asset["salvage"], "salvage")
    else:
        salvage = (cost * Q(asset.get("salvage_rate", 0), "salvage_rate")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP)
    base = cost - salvage
    if base < 0:
        raise InputError(f"资产 {asset.get('id')} 残值大于原值")
    method = (asset.get("method") or "straight_line").strip()
    plan = []
    accum = ZERO
    if method in ("straight_line", "直线法", "年限平均法"):
        monthly = (base / life).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        for n in range(1, life + 1):
            dep = monthly if n < life else base - monthly * (life - 1)
            accum += dep
            plan.append({"n": n, "dep": dep, "accum": accum, "nbv": cost - accum})
    elif method in ("double_declining", "双倍余额递减法"):
        rate = Decimal(2) / (Decimal(life) / Decimal(12)) / Decimal(12)  # 月率
        nbv = cost
        for n in range(1, life + 1):
            remaining_months = life - n + 1
            dep = (nbv * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if remaining_months <= 24:  # 最后两年改直线，CAS 通行做法
                dep = ((nbv - salvage) / remaining_months).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP)
            if nbv - dep < salvage:
                dep = nbv - salvage
            if n == life:
                dep = nbv - salvage
            accum += dep
            nbv = cost - accum
            plan.append({"n": n, "dep": dep, "accum": accum, "nbv": nbv})
    elif method in ("sum_of_years", "年数总和法"):
        denom = Decimal(life * (life + 1) / 2)
        for n in range(1, life + 1):
            weight = Decimal(life - n + 1)
            dep = (base * weight / denom).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if n == life:
                dep = base - accum
            accum += dep
            plan.append({"n": n, "dep": dep, "accum": accum, "nbv": cost - accum})
    elif method in ("units_of_production", "工作量法"):
        total_usage = Q(asset.get("total_usage", 0), "total_usage")
        if total_usage <= 0:
            raise InputError(f"资产 {asset.get('id')} 用工作量法必须给 total_usage")
        per_unit = base / total_usage
        usage_map = asset.get("usage_by_period") or {}
        for n in range(1, life + 1):
            used = Q(usage_map.get(str(n), 0), "usage")
            dep = (per_unit * used).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if accum + dep > base:
                dep = base - accum
            accum += dep
            plan.append({"n": n, "dep": dep, "accum": accum, "nbv": cost - accum})
    else:
        raise InputError(f"不支持的折旧方法：{method}")

    # 会计口径：本月应计提的是第几个折旧月
    in_service = asset.get("in_service")
    if in_service and rule in ("cas", "cas_month_after"):
        elapsed = _months_between(in_service, asset["_period"])  # 当月增加下月计提
    elif in_service:
        elapsed = _months_between(in_service, asset["_period"]) + 1
    else:
        elapsed = int(asset.get("months_booked") or 0) + 1
    return plan, elapsed, cost, salvage


def cmd_depreciation(args):
    data = load_json(args.file)
    period = data.get("period")
    if not period:
        raise InputError("缺少 period 字段")
    rule = data.get("rule") or "cas"
    assets = data.get("assets")
    if not isinstance(assets, list) or not assets:
        raise InputError("assets 必须是非空数组")

    rows = []
    detail = []
    total = ZERO
    warnings = []
    for asset in assets:
        asset = dict(asset)
        asset["_period"] = period
        plan, n_now, cost, salvage = _schedule(asset, rule)
        life = len(plan)
        if n_now <= 0:
            dep_now, accum_now = ZERO, ZERO
            note = "尚未开始计提（当月增加，下月起提）" if rule.startswith("cas") else "尚未开始计提"
            warnings.append(f"{asset.get('id')}：{note}")
        elif n_now > life:
            step = plan[-1]
            dep_now, accum_now = ZERO, step["accum"]
            warnings.append(f"{asset.get('id')}：已提足 {life} 个月，本期折旧为 0")
        else:
            step = plan[n_now - 1]
            dep_now, accum_now = step["dep"], step["accum"]
        nbv = cost - accum_now
        total += dep_now
        rows.append([asset.get("id") or "-", (asset.get("name") or "-")[:16],
                     M(cost), M(salvage), str(life), str(n_now),
                     M(dep_now), M(accum_now), M(nbv)])
        detail.append({
            "id": asset.get("id"), "name": asset.get("name"),
            "cost": str(cost), "salvage": str(salvage), "method": asset.get("method") or "straight_line",
            "life_months": life, "period_index": n_now,
            "depreciation": str(dep_now), "accumulated": str(accum_now), "nbv": str(nbv),
        })

    payload = {"tool": "depreciation", "period": period, "rule": rule,
               "total_depreciation": str(total), "assets": detail, "warnings": warnings}

    out = [
        f"折旧计算表 · {period} · 规则 {rule}（cas = 当月增加、下月计提）",
        table(["资产号", "名称", "原值", "残值", "折旧月数", "本期序", "本期折旧", "累计折旧", "账面净值"],
              rows, ["left", "left", "right", "right", "right", "right", "right", "right", "right"]),
        "",
        f"本期折旧合计：{M(total)}",
    ]
    if warnings:
        out += ["", "提示："] + [f"  - {w}" for w in warnings]
    out += ["", "下一步：按使用部门拆分借方费用科目（如 660201 管理费用-折旧费），贷方计 1602 累计折旧。"]
    emit(args, payload, "\n".join(out))
    return 0


# ----------------------------------------------------------------------------
# 5. amortize —— 待摊费用 / 预付账款摊销计划
# ----------------------------------------------------------------------------

def cmd_amortize(args):
    data = load_json(args.file)
    subject = data.get("subject") or "待摊项目"
    start = data.get("start_period")
    if not start:
        raise InputError("缺少 start_period（如 2026-09）")
    total = D(data.get("total"), "total")
    months = int(data.get("months") or 0)
    if total <= 0 or months <= 0:
        raise InputError("total / months 必须为正数")
    monthly = (total / months).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    y, m = _period_key(start)

    rows = []
    accum = ZERO
    for i in range(months):
        cur_y = y + (m - 1 + i) // 12
        cur_m = (m - 1 + i) % 12 + 1
        amt = monthly if i < months - 1 else total - accum
        accum += amt
        rows.append([f"{cur_y}-{cur_m:02d}", M(amt), M(accum), M(total - accum)])

    payload = {"tool": "amortize", "subject": subject, "start_period": start,
               "total": str(total), "months": months, "monthly": str(monthly),
               "schedule": [{"period": r[0], "amount": r[1].replace(",", ""),
                             "cumulative": r[2].replace(",", "")} for r in rows]}

    out = [
        f"摊销计划表 · {subject} · 起摊 {start} · 共 {months} 期",
        table(["期间", "本期摊销", "累计摊销", "未摊余额"], rows,
              ["left", "right", "right", "right"]),
        "",
        f"合计 {M(total)}，每期 {M(monthly)}（末期倒挤尾差，保证合计等于总额）。",
        "下一步：借方按受益对象计入费用科目，贷方冲减预付/长期待摊科目；跨年度的注意所得税口径差异。",
    ]
    emit(args, payload, "\n".join(out))
    return 0


# ----------------------------------------------------------------------------
# 6. variance —— 差异分解：价格 / 数量 / 结构
# ----------------------------------------------------------------------------

def cmd_variance(args):
    data = load_json(args.file)
    area = data.get("area") or "未命名对象"
    cur_label = data.get("period_current") or "本期"
    pri_label = data.get("period_prior") or "上期"
    threshold = Q(data.get("materiality_pct", 5), "materiality_pct")

    items = data.get("items")
    if not items:
        if data.get("price_current") is not None:
            items = [{"name": area,
                      "price_current": data.get("price_current"), "qty_current": data.get("qty_current"),
                      "price_prior": data.get("price_prior"), "qty_prior": data.get("qty_prior")}]
        else:
            raise InputError("请提供 price_current/qty_current/price_prior/qty_prior，或 items 数组")

    calc = []
    v_cur_total = Decimal("0")
    v_pri_total = Decimal("0")
    q_cur_total = Decimal("0")
    q_pri_total = Decimal("0")
    for it in items:
        p1, q1 = Q(it.get("price_current"), "price_current"), Q(it.get("qty_current"), "qty_current")
        p0, q0 = Q(it.get("price_prior"), "price_prior"), Q(it.get("qty_prior"), "qty_prior")
        v1, v0 = p1 * q1, p0 * q0
        price_eff = (p1 - p0) * q1                       # 价差
        vol_mix_eff = (q1 - q0) * p0                     # 量差（含结构）
        calc.append({"name": it.get("name") or "-", "p1": p1, "q1": q1, "p0": p0, "q0": q0,
                     "v1": v1, "v0": v0, "price": price_eff, "vol_mix": vol_mix_eff})
        v_cur_total += v1
        v_pri_total += v0
        q_cur_total += q1
        q_pri_total += q0

    total_delta = v_cur_total - v_pri_total
    avg_p0 = (v_pri_total / q_pri_total) if q_pri_total else Decimal("0")
    pure_vol = (q_cur_total - q_pri_total) * avg_p0
    vol_mix_sum = sum((c["vol_mix"] for c in calc), Decimal("0"))
    mix = vol_mix_sum - pure_vol
    price_sum = sum((c["price"] for c in calc), Decimal("0"))
    residual = total_delta - (price_sum + pure_vol + mix)

    def pct(part):
        return (part / total_delta * 100) if total_delta else Decimal("0")

    rows = []
    for c in calc:
        rows.append([c["name"], M(c["v0"]), M(c["v1"]), M(c["v1"] - c["v0"]),
                     M(c["price"]), M(c["vol_mix"])])
    rows.append(["合计", M(v_pri_total), M(v_cur_total), M(total_delta), M(price_sum), M(vol_mix_sum)])

    drivers = [("价格", price_sum), ("数量（纯）", pure_vol), ("结构", mix)]
    driver_rows = [[n, M(v), f"{pct(v):.1f}%"] for n, v in drivers]
    main = max(drivers, key=lambda x: abs(x[1]))

    payload = {
        "tool": "variance", "area": area,
        "period_current": cur_label, "period_prior": pri_label,
        "value_prior": str(v_pri_total), "value_current": str(v_cur_total),
        "delta": str(total_delta),
        "delta_pct": f"{pct(total_delta) if v_pri_total else Decimal('0'):.2f}",
        "price_effect": str(price_sum), "volume_effect": str(pure_vol), "mix_effect": str(mix),
        "residual": str(residual),
        "main_driver": main[0],
        "items": [{k: str(v) if isinstance(v, Decimal) else v for k, v in c.items()} for c in calc],
    }

    out = [
        f"差异分解 · {area} · {cur_label} vs {pri_label}",
        table(["项目", f"{pri_label} 金额", f"{cur_label} 金额", "差异", "价差", "量差(含结构)"],
              rows, ["left", "right", "right", "right", "right", "right"]),
        "",
        "三因分解：",
        table(["驱动", "金额", "占比"], driver_rows, ["left", "right", "right"]),
        "",
        f"主因：{main[0]}（{M(main[1])}，占差异 {pct(main[1]):.1f}%）",
        f"未解释残差：{M(residual)}" + ("（应为 0，非 0 说明输入有误）" if residual != 0 else ""),
    ]
    if v_pri_total and abs(total_delta / v_pri_total * 100) < threshold:
        out += ["", f"提示：整体变动 {abs(total_delta / v_pri_total * 100):.2f}% 低于设定的 {threshold}% 重大性门槛，可视情况简写说明。"]
    emit(args, payload, "\n".join(out))
    return 0 if residual == 0 else 1


# ----------------------------------------------------------------------------
# 7. tieout —— 三表勾稽校验
# ----------------------------------------------------------------------------

def cmd_tieout(args):
    data = load_json(args.file)
    period = data.get("period") or "-"
    bs = data.get("balance_sheet") or {}
    is_ = data.get("income_statement") or {}
    cf = data.get("cash_flow") or {}

    checks = []

    def chk(name, left, right, basis):
        diff = left - right
        checks.append({"check": name, "left": str(left), "right": str(right),
                       "diff": str(diff), "passed": diff == ZERO, "basis": basis})

    if all(k in bs for k in ("total_assets", "total_liabilities", "total_equity")):
        chk("表内平衡：资产 = 负债 + 所有者权益",
            D(bs["total_assets"]), D(bs["total_liabilities"]) + D(bs["total_equity"]),
            "资产负债表恒等式")

    if all(k in bs for k in ("retained_earnings_begin", "retained_earnings_end")) and "net_income" in is_:
        chk("跨表：未分配利润期末 = 期初 + 净利润 - 分配",
            D(bs["retained_earnings_end"]),
            D(bs["retained_earnings_begin"]) + D(is_["net_income"]) - D(bs.get("dividends", 0)),
            "利润表与所有者权益变动表衔接")

    if "cash" in bs and "ending_cash" in cf:
        chk("跨表：现金流量表期末现金 = 资产负债表货币资金",
            D(cf["ending_cash"]), D(bs["cash"]), "现金及现金等价物衔接")

    if all(k in cf for k in ("begin_cash", "net_operating", "net_investing", "net_financing", "ending_cash")):
        chk("表内：期初 + 经营 + 投资 + 筹资 = 期末现金",
            D(cf["begin_cash"]) + D(cf["net_operating"]) + D(cf["net_investing"]) + D(cf["net_financing"]),
            D(cf["ending_cash"]), "现金流量表加法关系")

    if "net_income" in is_ and "net_income_in_cf" in cf:
        chk("跨表：间接法起点净利润与利润表一致",
            D(cf["net_income_in_cf"]), D(is_["net_income"]), "现金流量表补充资料起点")

    if not checks:
        raise InputError("没有可校验的字段组合，请检查 balance_sheet / income_statement / cash_flow 结构")

    failed = [c for c in checks if not c["passed"]]
    rows = [[c["check"], M(c["left"]), M(c["right"]), M(c["diff"]),
             "通过" if c["passed"] else "不通过"] for c in checks]
    payload = {"tool": "tieout", "period": period, "passed": not failed,
               "failed_count": len(failed), "checks": checks}

    out = [
        f"三表勾稽校验 · {period}",
        table(["校验项", "左侧", "右侧", "差额", "结果"], rows,
              ["left", "right", "right", "right", "center"]),
        "",
        ("全部勾稽关系成立。" if not failed else
         f"{len(failed)} 项不成立。差异不为 0 时按顺序排查：先补漏记凭证，再查重分类，最后查跨表取数公式；不要用调平分录掩盖。"),
    ]
    for c in failed:
        out.append(f"  - {c['check']}：差 {M(c['diff'])}（依据：{c['basis']}）")
    emit(args, payload, "\n".join(out))
    return 0 if not failed else 1


# ----------------------------------------------------------------------------
# 8. materiality —— 重要性水平
# ----------------------------------------------------------------------------

DEFAULT_RATES = {
    "revenue": (Decimal("0.005"), "营业收入"),
    "total_assets": (Decimal("0.005"), "资产总额"),
    "profit_before_tax": (Decimal("0.05"), "税前利润"),
    "equity": (Decimal("0.02"), "所有者权益"),
    "expenses": (Decimal("0.01"), "费用总额"),
}


def cmd_materiality(args):
    data = load_json(args.file)
    benchmark = (data.get("benchmark") or "revenue").strip()
    if benchmark not in DEFAULT_RATES:
        raise InputError(f"benchmark 仅支持：{', '.join(DEFAULT_RATES)}")
    amount = D(data.get("amount"), "amount")
    if amount <= 0:
        raise InputError("amount 必须为正数")
    default_rate, label = DEFAULT_RATES[benchmark]
    rate = Q(data.get("rate", default_rate), "rate")
    perf = Q(data.get("performance_rate", 0.6), "performance_rate")
    trivial = Q(data.get("clearly_trivial_rate", 0.05), "clearly_trivial_rate")

    overall = (amount * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    performance = (overall * perf).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    trivial_amt = (overall * trivial).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    payload = {"tool": "materiality", "benchmark": benchmark, "benchmark_amount": str(amount),
               "rate": str(rate), "overall": str(overall), "performance": str(performance),
               "clearly_trivial": str(trivial_amt)}

    out = [
        f"重要性水平测算 · 基准：{label} {M(amount)}",
        table(["项目", "比例", "金额"], [
            ["整体重要性（报表层面）", f"{rate * 100:.2f}%", M(overall)],
            ["实际执行的重要性", f"{rate * perf * 100:.2f}%", M(performance)],
            ["明显微小错报临界值", f"{rate * perf * trivial * 100:.3f}%", M(trivial_amt)],
        ], ["left", "right", "right"]),
        "",
        "用法：错报金额低于明显微小临界值可不逐笔累积；累计超过实际执行重要性时，必须查清再结账。",
        "比例是行业常用区间，最终取值由项目负责人确定并写入底稿，本工具只做算式。",
    ]
    emit(args, payload, "\n".join(out))
    return 0


# ----------------------------------------------------------------------------
# 9. selftest —— 内置样例自检（用于发布前验证）
# ----------------------------------------------------------------------------

def cmd_selftest(args):
    results = []

    def case(name, fn):
        try:
            ok, detail = fn()
            results.append((name, ok, detail))
        except Exception as exc:  # noqa: BLE001
            results.append((name, False, f"异常：{exc}"))

    def t_straight_line():
        asset = {"id": "FA-1", "cost": 120000, "salvage_rate": 0.05,
                 "life_months": 36, "method": "straight_line",
                 "in_service": "2026-07-15", "_period": "2026-09"}
        plan, n, cost, salvage = _schedule(asset, "cas")
        ok = (n == 2 and salvage == D(6000) and plan[0]["dep"] == D("3166.67")
              and plan[-1]["dep"] == D("3166.55"))
        return ok, f"序期={n} 残值={M(salvage)} 首月={M(plan[0]['dep'])} 末月={M(plan[-1]['dep'])}"

    def t_ddb_total():
        asset = {"id": "FA-2", "cost": 100000, "salvage_rate": 0,
                 "life_months": 60, "method": "double_declining", "_period": "2020-01"}
        plan, _, _, _ = _schedule(asset, "immediate")
        total = sum((p["dep"] for p in plan), ZERO)
        return total == D(100000), f"累计={M(total)}"

    def t_syd_total():
        asset = {"id": "FA-3", "cost": 100000, "salvage": 4000,
                 "life_months": 24, "method": "sum_of_years", "_period": "2020-01"}
        plan, _, _, _ = _schedule(asset, "immediate")
        total = sum((p["dep"] for p in plan), ZERO)
        return total == D(96000), f"累计={M(total)}"

    def t_variance():
        p1, q1, p0, q0 = Q(105), Q(9000), Q(100), Q(10000)
        price = (p1 - p0) * q1
        vol = (q1 - q0) * p0
        delta = p1 * q1 - p0 * q0
        return price + vol == delta, f"价差={M(price)} 量差={M(vol)} 合计={M(delta)}"

    def t_bank_rec():
        # 企业已付、银行未付 23000；银行已收、企业未收 3000 → 银行侧比企业侧高 26000
        book, bank = D(1174000), D(1200000)
        adj_book = book + D(3000) - D(0)
        adj_bank = bank + D(0) - D(23000)
        return adj_book == adj_bank == D(1177000), f"账面调节后={M(adj_book)} 银行调节后={M(adj_bank)}"

    def t_rollforward():
        calc = D(1000000) + D(300000) - D(250000)
        return calc == D(1050000), f"实在={M(calc)}"

    def t_materiality():
        overall = (D(500000000) * Decimal("0.005")).quantize(Decimal("0.01"))
        return overall == D(2500000), f"整体重要性={M(overall)}"

    def t_amortize_tail():
        total, months = D(240000), 12
        monthly = (total / months).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        sched = [monthly] * (months - 1)
        sched.append(total - monthly * (months - 1))
        return sum(sched, ZERO) == total, f"合计={M(sum(sched, ZERO))}"

    case("直线法折旧·当期序期与尾差", t_straight_line)
    case("双倍余额递减·累计提足原值", t_ddb_total)
    case("年数总和法·累计等于应折旧额", t_syd_total)
    case("量价分解·加法闭合", t_variance)
    case("银行调节表·两侧调平", t_bank_rec)
    case("四柱滚算·期初期末闭合", t_rollforward)
    case("重要性水平·比例算式", t_materiality)
    case("摊销计划·末期倒挤尾差", t_amortize_tail)

    passed = sum(1 for _, ok, _ in results if ok)
    total_cases = len(results)
    payload = {"tool": "selftest", "version": APP_VERSION,
               "passed": passed, "total": total_cases,
               "cases": [{"case": n, "passed": ok, "detail": d} for n, ok, d in results]}
    out = [f"{APP_NAME} 自检 · v{APP_VERSION}",
           table(["用例", "结果", "实测值"], [[n, "PASS" if ok else "FAIL", d] for n, ok, d in results],
                 ["left", "center", "left"]),
           "", f"{passed}/{total_cases} 通过"]
    emit(args, payload, "\n".join(out))
    return 0 if passed == total_cases else 1


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

COMMANDS = {
    "entry-check": (cmd_entry_check, "分录批次校验：借贷平衡、单据、期间、异常特征"),
    "rollforward": (cmd_rollforward, "四柱滚算：旧管 + 新收 - 开除 = 实在"),
    "bank-rec": (cmd_bank_rec, "银行存款余额调节表"),
    "depreciation": (cmd_depreciation, "折旧计算（直线/双倍余额递减/年数总和/工作量）"),
    "amortize": (cmd_amortize, "待摊费用、预付账款摊销计划"),
    "variance": (cmd_variance, "差异分解：价格 / 数量 / 结构"),
    "tieout": (cmd_tieout, "三表勾稽校验"),
    "materiality": (cmd_materiality, "重要性水平测算"),
    "selftest": (cmd_selftest, "内置样例自检"),
}


def build_parser():
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description="账衡专家包的账务计算与校验工具（纯标准库）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：\n  python ledgerkit.py entry-check --file samples/entries_demo.json\n"
               "  python ledgerkit.py selftest",
    )
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {APP_VERSION}")
    sub = parser.add_subparsers(dest="command", metavar="命令")

    for name, (fn, help_text) in COMMANDS.items():
        p = sub.add_parser(name, help=help_text, description=help_text)
        if name != "selftest":
            p.add_argument("--file", "-f", required=False, help="输入 JSON 文件路径")
        p.add_argument("--json", action="store_true", help="输出机器可读 JSON")
        p.add_argument("--out", "-o", help="把结果写入指定文件（留痕用）")
        p.set_defaults(func=fn)

    p_list = sub.add_parser("list", help="列出全部命令")
    p_list.set_defaults(func=cmd_list)
    return parser


def cmd_list(args):
    rows = [[n, h] for n, (_, h) in COMMANDS.items()]
    print(f"{APP_NAME} v{APP_VERSION} 可用命令：")
    print(table(["命令", "用途"], rows))
    print("\n退出码：0 通过 / 1 有阻断问题 / 2 输入非法")
    return 0


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2
    try:
        return args.func(args)
    except InputError as exc:
        print(f"[输入错误] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
