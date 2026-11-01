#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
czl-taxops 财税体检工具（纯标准库，无第三方依赖）

子命令
  check      三表勾稽与表内合计校验
  ratios     财务比率、杜邦拆解、现金流质量
  variance   预算差异与量价拆分
  calendar   申报日历（周末顺延，节假日需人工覆盖）
  selftest   内置用例自检

设计原则
  1. 只做算术，不做判断。判断交给顾问。
  2. 缺字段就跳过并说明，不猜、不填默认值。
  3. 任何结果都能被手工复算。

字段约定见 ../references/02-数据规范化与勾稽.md 第三节。
"""

import argparse
import datetime as dt
import json
import sys
import unicodedata

# ---------------------------------------------------------------- 基础工具


def load_json(path):
    with open(path, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def pick(section, key):
    """取值；缺失或非数值返回 None（代表未知，不等于 0）。"""
    if not isinstance(section, dict):
        return None
    val = section.get(key)
    if val is None or isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            return float(val.replace(",", "").strip())
        except ValueError:
            return None
    return None


def fmt(val, unit=""):
    if val is None:
        return "—"
    if isinstance(val, str):
        return val
    return "{:,.2f}{}".format(val, unit)


def pct(val):
    if val is None:
        return "—"
    return "{:.2f}%".format(val * 100)


def div(a, b):
    if a is None or b in (None, 0):
        return None
    return a / b


def dwidth(text):
    """按终端显示宽度计算：中日韩全角字符占 2 列。"""
    width = 0
    for ch in str(text):
        width += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return width


def pad(text, width, align="left"):
    gap = width - dwidth(text)
    if gap <= 0:
        return str(text)
    return str(text) + " " * gap if align == "left" else " " * gap + str(text)


def diff_tol(expected):
    """允许的舍入误差：绝对 1 个单位 + 相对百万分之一。"""
    return max(1.0, abs(expected) * 1e-6)


# ---------------------------------------------------------------- check


def build_checks(doc):
    bs = doc.get("balance_sheet") or {}
    ist = doc.get("income_statement") or {}
    cf = doc.get("cash_flow") or {}

    checks = []

    # B1 资产负债平衡
    assets = pick(bs, "资产总计")
    liab = pick(bs, "负债合计")
    equity = pick(bs, "所有者权益合计")
    if None not in (assets, liab, equity):
        checks.append(("B1", "资产总计 = 负债合计 + 所有者权益合计", assets, liab + equity,
                       "录入错误、漏项，或损益未结转"))

    # B2 资产分类
    ca = pick(bs, "流动资产合计")
    nca = pick(bs, "非流动资产合计")
    if None not in (assets, ca, nca):
        checks.append(("B2", "资产总计 = 流动资产合计 + 非流动资产合计", assets, ca + nca,
                       "明细汇总错，或有科目未归类"))

    # B3 负债分类
    cl = pick(bs, "流动负债合计")
    ncl = pick(bs, "非流动负债合计")
    if None not in (liab, cl, ncl):
        checks.append(("B3", "负债合计 = 流动负债合计 + 非流动负债合计", liab, cl + ncl,
                       "明细汇总错，或有科目未归类"))

    # B4 货币资金合理区间
    cash = pick(bs, "货币资金")
    if None not in (cash, ca):
        if cash < 0:
            checks.append(("B4", "货币资金不应为负", cash, 0.0,
                           "账务处理有误（除非透支已单列科目）"))
        elif cash > ca + diff_tol(ca):
            checks.append(("B4", "货币资金应不大于流动资产合计", cash, ca,
                           "科目归类错，或流动资产合计漏项"))
        else:
            checks.append(("B4", "货币资金 ∈ [0, 流动资产合计]", cash, cash,
                           "合理区间内"))

    # P1 营业利润阶梯
    # 说明：费用类字段缺失时不验算，否则会把"没填"误判成"不平"
    rev = pick(ist, "营业收入")
    cost = pick(ist, "营业成本")
    tax_sur = pick(ist, "税金及附加")
    sell = pick(ist, "销售费用")
    admin = pick(ist, "管理费用")
    rd = pick(ist, "研发费用")
    fin = pick(ist, "财务费用")
    inv = pick(ist, "投资收益")
    op = pick(ist, "营业利润")
    components = [tax_sur, sell, admin, rd, fin]
    if None not in (rev, cost, op) and all(v is not None for v in components):
        s = rev - cost
        for v in components:
            s -= v
        if inv is not None:
            s += inv
        hint = "某级科目漏加减，或费用列示方向不一致"
        if inv is None:
            hint += "（投资收益未填，按 0 计）"
        checks.append(("P1", "营业利润 = 收入 − 成本 − 税金及附加 − 三项费用 − 研发 ± 财务 + 投资收益",
                       op, s, hint))

    # P2 利润总额
    non_op_in = pick(ist, "营业外收入")
    non_op_out = pick(ist, "营业外支出")
    total = pick(ist, "利润总额")
    if None not in (op, total):
        s = op + (non_op_in or 0.0) - (non_op_out or 0.0)
        checks.append(("P2", "利润总额 = 营业利润 + 营业外收入 − 营业外支出", total, s,
                       "营业外收支漏记"))

    # P3 净利润（所得税费用未填时不验算）
    itax = pick(ist, "所得税费用")
    net = pick(ist, "净利润")
    if None not in (total, net, itax):
        checks.append(("P3", "净利润 = 利润总额 − 所得税费用", net, total - itax,
                       "所得税漏记或多记"))

    # C1 现金流量三项合计
    cfo = pick(cf, "经营活动现金流量净额")
    cfi = pick(cf, "投资活动现金流量净额")
    cff = pick(cf, "筹资活动现金流量净额")
    cnet = pick(cf, "现金及现金等价物净增加额")
    if None not in (cfo, cfi, cff, cnet):
        checks.append(("C1", "经营 + 投资 + 筹资 = 现金净增加额", cnet, cfo + cfi + cff,
                       "某类活动现金流漏项"))

    return checks


def cmd_check(args):
    doc = load_json(args.file)
    unit = doc.get("unit", "元")
    period = doc.get("period", "未标注")

    print("=" * 68)
    print("财务数据体检  期间：{}  单位：{}".format(period, unit))
    print("=" * 68)

    checks = build_checks(doc)
    if not checks:
        print("可用字段不足，无法执行任何勾稽检查。请按字段表补充数据。")
        return 0

    passed, warns, fails = 0, 0, 0
    for code, name, actual, expected, hint in checks:
        delta = actual - expected
        ok = abs(delta) <= diff_tol(expected)
        if ok:
            passed += 1
            flag = "PASS"
        else:
            fails += 1
            flag = "FAIL"
        print("[{}] {}  {}".format(flag, code, name))
        if not ok:
            print("       报表值 {} / 应为 {} / 差异 {:.2f}".format(
                fmt(actual), fmt(expected), delta))
            print("       可能原因：{}".format(hint))

    # 跨表合理性预警
    bs = doc.get("balance_sheet") or {}
    ist = doc.get("income_statement") or {}
    rev = pick(ist, "营业收入")
    cost = pick(ist, "营业成本")
    net = pick(ist, "净利润")
    cfo = pick((doc.get("cash_flow") or {}), "经营活动现金流量净额")
    cl = pick(bs, "流动负债合计")
    cash = pick(bs, "货币资金")
    ca = pick(bs, "流动资产合计")

    alerts = []
    gm = div((rev - cost) if None not in (rev, cost) else None, rev)
    if gm is not None and (gm > 0.80 or gm < -0.20):
        alerts.append("毛利率 {} 超出常见区间（−20%—80%）。请确认收入是否已换算为不含税、成本是否完整结转。".format(pct(gm)))
    if None not in (net, cfo) and net not in (0, None):
        gap = div(abs(cfo - net), abs(net))
        if gap is not None and gap > 0.5:
            alerts.append("经营现金流与净利润差异 {:.0f}%，请核查应收、存货变动。".format(gap * 100))
    cr = div(ca, cl)
    if cr is not None and cr < 1:
        alerts.append("流动比率 {:.2f} 小于 1，短期偿付存在压力（需结合预收与账期判断）。".format(cr))
    cash_ratio = div(cash, cl)
    if cash_ratio is not None and cash_ratio < 0.1:
        alerts.append("现金比率 {:.2f}，货币资金对流动负债覆盖很低。".format(cash_ratio))

    print("-" * 68)
    print("勾稽结论：通过 {} 项，不平 {} 项".format(passed, fails))
    all_codes = ["B1", "B2", "B3", "B4", "P1", "P2", "P3", "C1"]
    skipped = [c for c in all_codes if c not in [x[0] for x in checks]]
    if skipped:
        print("未校验（字段缺失）：{} —— 补上对应科目后可复核".format("、".join(skipped)))
    if alerts:
        print("合理性预警：")
        for a in alerts:
            print("  · {}".format(a))
    else:
        print("合理性预警：无")
    print("说明：本工具只做算术校验，不平项的原因判断需结合明细账核对。")

    if args.strict and fails:
        return 2
    return 0


# ---------------------------------------------------------------- ratios


def avg(cur, prior):
    if cur is None:
        return None
    if prior is None:
        return cur
    return (cur + prior) / 2.0


def cmd_ratios(args):
    doc = load_json(args.file)
    bs = doc.get("balance_sheet") or {}
    ist = doc.get("income_statement") or {}
    cf = doc.get("cash_flow") or {}
    prior_bs = (doc.get("prior") or {}).get("balance_sheet") or {}
    days = float(doc.get("days", args.days or 30))
    unit = doc.get("unit", "元")

    rev = pick(ist, "营业收入")
    cost = pick(ist, "营业成本")
    net = pick(ist, "净利润")
    total = pick(ist, "利润总额")
    fin = pick(ist, "财务费用")

    assets = pick(bs, "资产总计")
    equity = pick(bs, "所有者权益合计")
    ca = pick(bs, "流动资产合计")
    cl = pick(bs, "流动负债合计")
    inv = pick(bs, "存货")
    ar = pick(bs, "应收账款")
    ap = pick(bs, "应付账款")
    liab = pick(bs, "负债合计")
    cash = pick(bs, "货币资金")

    avg_assets = avg(assets, pick(prior_bs, "资产总计"))
    avg_equity = avg(equity, pick(prior_bs, "所有者权益合计"))
    avg_ar = avg(ar, pick(prior_bs, "应收账款"))
    avg_inv = avg(inv, pick(prior_bs, "存货"))
    avg_ap = avg(ap, pick(prior_bs, "应付账款"))

    basis = "平均值（含期初）" if pick(prior_bs, "资产总计") is not None else "期末值（缺期初，口径有偏差）"

    print("=" * 68)
    print("财务比率  期间：{}  单位：{}  期间天数：{:.0f}".format(doc.get("period", "未标注"), unit, days))
    print("存量类指标口径：{}".format(basis))
    print("=" * 68)

    rows = []

    rows.append(("【偿债】", None, None, ""))
    rows.append(("流动比率", div(ca, cl), "流动资产 ÷ 流动负债", "一般 1.5—2 较宽裕，行业差异大"))
    rows.append(("速动比率", div((ca - inv) if None not in (ca, inv) else None, cl),
                 "（流动资产 − 存货）÷ 流动负债", "1 左右为常见参考"))
    rows.append(("资产负债率", div(liab, assets), "负债 ÷ 资产", "预收款多的行业天然偏高"))
    rows.append(("现金比率", div(cash, cl), "货币资金 ÷ 流动负债", "最保守的偿付视角"))
    ie = None
    if None not in (total, fin) and fin:
        ie = div(total + fin, fin)
    rows.append(("利息保障倍数", ie, "（利润总额 + 财务费用）÷ 财务费用",
                 "＜2 时融资空间受限；严格口径应用利息支出而非财务费用总额"))

    rows.append(("【营运】", None, None, ""))
    rows.append(("应收账款周转天数", div((avg_ar or 0) * days, rev) if None not in (avg_ar, rev) else None,
                 "平均应收 ÷ 收入 × 期间天数", "与行业账期比，不设绝对标准"))
    rows.append(("存货周转天数", div((avg_inv or 0) * days, cost) if None not in (avg_inv, cost) else None,
                 "平均存货 ÷ 营业成本 × 天数", "分母用成本，用收入会系统性低估"))
    rows.append(("应付账款周转天数", div((avg_ap or 0) * days, cost) if None not in (avg_ap, cost) else None,
                 "平均应付 ÷ 营业成本 × 天数", "与应收天数对比看谁在垫钱"))
    ar_d = div((avg_ar or 0) * days, rev) if None not in (avg_ar, rev) else None
    inv_d = div((avg_inv or 0) * days, cost) if None not in (avg_inv, cost) else None
    ap_d = div((avg_ap or 0) * days, cost) if None not in (avg_ap, cost) else None
    ccc = None if None in (ar_d, inv_d, ap_d) else ar_d + inv_d - ap_d
    rows.append(("现金转换周期（天）", ccc, "应收天数 + 存货天数 − 应付天数", "正数越大越依赖外部资金"))
    rows.append(("总资产周转率", div(rev, avg_assets), "收入 ÷ 平均资产", "反映资产产出效率"))

    rows.append(("【盈利】", None, None, ""))
    rows.append(("毛利率", div((rev - cost) if None not in (rev, cost) else None, rev),
                 "（收入 − 成本）÷ 收入", "含税未还原会虚高"))
    rows.append(("营业利润率", div(pick(ist, "营业利润"), rev), "营业利润 ÷ 收入", "剔除营业外因素"))
    rows.append(("净利率", div(net, rev), "净利润 ÷ 收入", "受所得税与一次性损益影响"))
    rows.append(("ROA", div(net, avg_assets), "净利润 ÷ 平均资产", ""))
    rows.append(("ROE", div(net, avg_equity), "净利润 ÷ 平均权益", "受杠杆放大"))

    rows.append(("【现金】", None, None, ""))
    cfo = pick(cf, "经营活动现金流量净额")
    cap = args.capex
    rows.append(("现金含量", div(cfo, net), "经营现金流 ÷ 净利润", "长期明显低于 1 说明利润没变现"))
    rows.append(("自由现金流（简化）", None if cfo is None else cfo - cap,
                 "经营现金流 − 资本性支出（假设 {}）".format(fmt(cap)), "可分红与还债的真实空间"))

    for name, val, formula, note in rows:
        if val is None and formula is None:
            print("\n" + name)
            continue
        if name in ("应收账款周转天数", "存货周转天数", "应付账款周转天数", "现金转换周期（天）"):
            shown = "—" if val is None else "{:.1f} 天".format(val)
        elif name in ("毛利率", "营业利润率", "净利率", "ROA", "ROE", "资产负债率"):
            shown = pct(val)
        elif name in ("流动比率", "速动比率", "现金比率", "利息保障倍数", "现金含量", "总资产周转率"):
            shown = "—" if val is None else "{:.2f}".format(val)
        else:
            shown = fmt(val, " " + unit if unit and name.startswith("自由") else "")
        print("  " + pad(name, 18) + pad(shown, 16) + formula)
        if note:
            print("  " + pad("", 18) + "注：" + note)

    # 杜邦
    npm = div(net, rev)
    tat = div(rev, avg_assets)
    em = div(avg_assets, avg_equity)
    roe = div(net, avg_equity)
    print("\n【杜邦拆解】ROE = 净利率 × 总资产周转率 × 权益乘数")
    if None not in (npm, tat, em):
        print("  {:.2%} = {:.2%} × {:.2f} × {:.2f}".format(npm * tat * em, npm, tat, em))
        print("  校验：直接算 ROE = {}".format(pct(roe)))
        weakest = min([("净利率", npm), ("周转率", tat), ("权益乘数", em)], key=lambda x: x[1])
        print("  三因子中数值最低的是「{}」，改善优先从这里入手（需结合行业特征判断）。".format(weakest[0]))
    else:
        print("  缺字段，无法拆解。")

    print("\n说明：以上为计算口径与读法参考，不构成优劣结论。判断需结合历史、预算与同业。")
    return 0


# ---------------------------------------------------------------- variance


def cmd_variance(args):
    doc = load_json(args.file)
    items = doc.get("items") or []
    unit = doc.get("unit", "元")
    if not items:
        print("items 为空")
        return 1

    print("=" * 68)
    print("预算差异分析  期间：{}  单位：{}".format(doc.get("period", "未标注"), unit))
    print("=" * 68)

    tot_price = tot_vol = tot_diff = 0.0
    header = (pad("项目", 16) + pad("预算", 14, "right") + pad("实际", 14, "right")
              + pad("差异额", 14, "right") + pad("差异率", 10, "right")
              + pad("其中价差", 14, "right"))
    print(header)
    print("-" * 68)

    for it in items:
        name = str(it.get("name", "未命名"))
        if all(k in it for k in ("budget_qty", "budget_price", "actual_qty", "actual_price")):
            bq, bp = float(it["budget_qty"]), float(it["budget_price"])
            aq, ap = float(it["actual_qty"]), float(it["actual_price"])
            budget, actual = bq * bp, aq * ap
            price_var = (ap - bp) * aq
            vol_var = (aq - bq) * bp
            tot_price += price_var
            tot_vol += vol_var
        else:
            budget = float(it.get("budget", 0) or 0)
            actual = float(it.get("actual", 0) or 0)
            price_var = None
            vol_var = None

        d = actual - budget
        tot_diff += d
        rate = "—" if budget == 0 else "{:.1f}%".format(d / budget * 100)
        print(pad(name, 16)
              + pad("{:,.2f}".format(budget), 14, "right")
              + pad("{:,.2f}".format(actual), 14, "right")
              + pad("{:,.2f}".format(d), 14, "right")
              + pad(rate, 10, "right")
              + pad("—" if price_var is None else "{:,.2f}".format(price_var), 14, "right"))
        if price_var is not None:
            print(pad("", 16) + "量价拆分：价差 {:,.2f}　量差 {:,.2f}　合计 {:,.2f}".format(
                price_var, vol_var, price_var + vol_var))

    print("-" * 68)
    print("合计差异：{:,.2f}{}　其中价差 {:,.2f}　量差 {:,.2f}".format(
        tot_diff, unit, tot_price, tot_vol))
    print("判定提示：差异率 ≥10% 或绝对额超阈值的科目须书面说明原因；")
    print("          连续三个月同向超预算，转入专项分析。")
    return 0


# ---------------------------------------------------------------- calendar


def roll_forward(day):
    """周六/周日顺延到周一。"""
    while day.weekday() >= 5:
        day += dt.timedelta(days=1)
    return day


def cmd_calendar(args):
    year = args.year or dt.date.today().year
    month = args.month
    events = []

    for m in range(1, 13):
        nm_y, nm_m = (year + 1, 1) if m == 12 else (year, m + 1)
        due = roll_forward(dt.date(nm_y, nm_m, 15))
        events.append((due, "增值税及附加申报（月度）"))
        if m % 3 == 0:
            events.append((due, "增值税及附加申报（季度）／企业所得税季度预缴"))
    events.append((roll_forward(dt.date(year, 5, 31)), "企业所得税年度汇算清缴截止"))
    events.append((roll_forward(dt.date(year, 3, 31)), "经营所得汇算清缴截止"))
    events.append((dt.date(year, 3, 1), "个人所得税综合所得年度汇算开始"))
    events.append((dt.date(year, 6, 30), "个人所得税综合所得年度汇算截止"))
    events.append((dt.date(year, 6, 30), "工商年报公示截止"))

    events = [e for e in events if month is None or e[0].month == month]
    events.sort()

    print("=" * 68)
    print("申报日历  {}年{}".format(year, "" if month is None else " {}月".format(month)))
    print("=" * 68)
    for d, label in events:
        print("  {}  {}  {}".format(d.isoformat(), "一二三四五六日"[d.weekday()], label))
    print("-" * 68)
    print("注意：本日历只做周末顺延，不含法定节假日与征管延期公告；")
    print("      实际截止日以电子税务局当期提示与主管税务机关通知为准。")
    return 0


# ---------------------------------------------------------------- selftest


def _assert(cond, label, detail=""):
    if cond:
        print("PASS  {}".format(label))
        return 1
    print("FAIL  {}  {}".format(label, detail))
    return 0


def cmd_selftest(args):
    print("=" * 68)
    print("工具自检")
    print("=" * 68)
    ok = 0
    total = 0

    # 1 三表勾稽：构造一份平衡的数据
    balanced = {
        "unit": "元", "period": "2026-09", "days": 30,
        "balance_sheet": {
            "货币资金": 90000, "应收账款": 110000, "存货": 50000,
            "流动资产合计": 250000, "非流动资产合计": 150000, "资产总计": 400000,
            "流动负债合计": 150000, "非流动负债合计": 50000, "负债合计": 200000,
            "所有者权益合计": 200000,
        },
        "income_statement": {
            "营业收入": 860000, "营业成本": 636400, "税金及附加": 5200,
            "销售费用": 68000, "管理费用": 92000, "研发费用": 0, "财务费用": 4300,
            "投资收益": 0, "营业利润": 54100, "营业外收入": 0, "营业外支出": 1100,
            "利润总额": 53000, "所得税费用": 10600, "净利润": 42400,
        },
        "cash_flow": {
            "经营活动现金流量净额": -140000, "投资活动现金流量净额": -30000,
            "筹资活动现金流量净额": 0, "现金及现金等价物净增加额": -170000,
        },
    }
    checks = build_checks(balanced)
    total += 1
    bad = [c for c in checks if abs(c[2] - c[3]) > diff_tol(c[3])]
    ok += _assert(not bad, "平衡数据应全部通过勾稽", [c[0] for c in bad])

    # 2 故意打破：资产多 1000
    broken = json.loads(json.dumps(balanced))
    broken["balance_sheet"]["资产总计"] = 401000
    checks_b = build_checks(broken)
    total += 1
    b1 = [c for c in checks_b if c[0] == "B1"]
    ok += _assert(bool(b1) and abs(b1[0][2] - b1[0][3]) == 1000.0,
                  "B1 应识别出 1000 的不平额")

    # 3 缺字段不报错
    sparse = {"balance_sheet": {"资产总计": 100}}
    checks_s = build_checks(sparse)
    total += 1
    ok += _assert(checks_s == [], "缺字段时应跳过而不是崩")

    # 4 比率：流动比率
    ca, cl = 250000.0, 150000.0
    total += 1
    ok += _assert(abs(div(ca, cl) - 1.6666666) < 1e-5, "流动比率计算")

    # 5 毛利率与净利率
    gm = div(860000.0 - 636400.0, 860000.0)
    total += 1
    ok += _assert(abs(gm - 0.26) < 1e-9, "毛利率应为 26%", gm)

    # 6 杜邦恒等：净利率 × 周转率 × 权益乘数 = ROE
    net, rev = 42400.0, 860000.0
    assets, equity = 400000.0, 200000.0
    dupont = div(net, rev) * div(rev, assets) * div(assets, equity)
    total += 1
    ok += _assert(abs(dupont - div(net, equity)) < 1e-9, "杜邦三因子乘积应等于 ROE")

    # 7 量价拆分恒等：价差 + 量差 = 总差异
    bq, bp, aq, ap = 1000.0, 56.0, 1120.0, 50.0
    price_var = (ap - bp) * aq
    vol_var = (aq - bq) * bp
    total += 1
    ok += _assert(abs((price_var + vol_var) - (aq * ap - bq * bp)) < 1e-9,
                  "价差 + 量差 应等于实际与预算之差")

    # 8 申报日顺延：2026-08-15 是周六，应顺延到 8-17
    total += 1
    ok += _assert(roll_forward(dt.date(2026, 8, 15)) == dt.date(2026, 8, 17),
                  "周末顺延逻辑（2026-08-15 → 08-17）")

    # 9 除零保护
    total += 1
    ok += _assert(div(1.0, 0) is None, "分母为 0 时返回 None 而非异常")

    print("-" * 68)
    print("自检结果：{}/{} 通过".format(ok, total))
    return 0 if ok == total else 1


# ---------------------------------------------------------------- main


def main(argv=None):
    parser = argparse.ArgumentParser(description="czl-taxops 财税体检工具")
    sub = parser.add_subparsers(dest="cmd")

    p_check = sub.add_parser("check", help="三表勾稽与表内合计校验")
    p_check.add_argument("--file", required=True)
    p_check.add_argument("--strict", action="store_true", help="有不平项时返回码 2")
    p_check.set_defaults(func=cmd_check)

    p_ratios = sub.add_parser("ratios", help="比率与杜邦")
    p_ratios.add_argument("--file", required=True)
    p_ratios.add_argument("--days", type=float, default=None, help="期间天数，默认取 JSON 或 30")
    p_ratios.add_argument("--capex", type=float, default=0.0, help="资本性支出，用于简化自由现金流")
    p_ratios.set_defaults(func=cmd_ratios)

    p_var = sub.add_parser("variance", help="预算差异与量价拆分")
    p_var.add_argument("--file", required=True)
    p_var.set_defaults(func=cmd_variance)

    p_cal = sub.add_parser("calendar", help="申报日历")
    p_cal.add_argument("--year", type=int, default=None)
    p_cal.add_argument("--month", type=int, default=None)
    p_cal.set_defaults(func=cmd_calendar)

    p_test = sub.add_parser("selftest", help="内置用例自检")
    p_test.set_defaults(func=cmd_selftest)

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 1
    try:
        return args.func(args)
    except FileNotFoundError:
        print("找不到文件：{}".format(getattr(args, "file", "")))
        return 1
    except json.JSONDecodeError as exc:
        print("JSON 解析失败：{}".format(exc))
        print("提示：检查是否含注释、千分位逗号、百分号，或中文引号。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
