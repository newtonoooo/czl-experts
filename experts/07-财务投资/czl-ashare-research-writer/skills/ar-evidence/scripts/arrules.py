#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A股规则校验器（零第三方依赖）。

子命令：
  board   --code 600519                     板块、交易所、涨跌幅限制
  limit   --code 000001 --prev-close 12.34  涨停价与跌停价
  check   --code 600519 --prev-close 1500 --price 1650 [--st]
                                            价格是否越界、是否需要 ST 口径
  codes   --file codes.txt                  批量归类

所有价格按人民币元、四舍五入到分（ROUND_HALF_UP），不使用 Python 内建 round，
因为内建 round 采用银行家舍入，会在 .005 处产生与交易所不一致的结果。
"""
import argparse
import json
import sys
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")

# 板块定义：prefix -> (交易所, 板块, 涨跌幅%, 是否注册制新股前5日不限)
BOARDS = [
    (("600", "601", "603", "605"), "上交所", "主板", 10.0),
    (("688", "689"), "上交所", "科创板", 20.0),
    (("000", "001", "002", "003"), "深交所", "主板", 10.0),
    (("300", "301"), "深交所", "创业板", 20.0),
    (("900",), "上交所", "B股", 10.0),
    (("200",), "深交所", "B股", 10.0),
    (("400", "420", "430"), "股转系统", "两网及退市", 5.0),
    (("920",), "北交所", "北交所", 30.0),
    (("83", "87", "88", "43"), "北交所", "北交所", 30.0),
]


class RuleError(ValueError):
    pass


def normalize_code(code):
    """把 600519 / sh600519 / 600519.SH 统一成 6 位数字。"""
    if code is None:
        raise RuleError("代码为空")
    s = str(code).strip().upper()
    for token in (".SH", ".SZ", ".BJ", ".SS"):
        s = s.replace(token, "")
    for token in ("SH", "SZ", "BJ", "SS"):
        if s.startswith(token):
            s = s[len(token):]
    s = s.strip()
    if not s.isdigit():
        raise RuleError("代码必须是数字：%r" % code)
    if len(s) != 6:
        raise RuleError("A股代码应为 6 位，收到 %d 位：%s" % (len(s), s))
    return s


def classify(code):
    """返回板块信息字典。无法归类时抛 RuleError。"""
    c = normalize_code(code)
    for prefixes, exch, board, pct in BOARDS:
        for p in prefixes:
            if c.startswith(p):
                # 北交所 43/83/87/88 是两位前缀，其余为三位
                if len(p) == 2 or c.startswith(p):
                    return {
                        "code": c,
                        "exchange": exch,
                        "board": board,
                        "limit_pct": pct,
                        "currency": "HKD" if board == "B股" and exch == "深交所" else (
                            "USD" if board == "B股" else "CNY"),
                        "t_plus": 1,
                    }
    raise RuleError("无法归类的代码：%s" % c)


def limit_prices(code, prev_close, st=False):
    """计算涨跌停价。ST 在主板为 5%，创业板/科创板维持 20%。"""
    info = classify(code)
    pct = info["limit_pct"]
    if st:
        if info["board"] == "主板":
            pct = 5.0
        # 创业板/科创板 ST 仍为 20%，不调整
    prev = Decimal(str(prev_close))
    if prev <= 0:
        raise RuleError("前收盘价必须为正数")
    rate = Decimal(str(pct)) / Decimal("100")
    up = (prev * (Decimal("1") + rate)).quantize(CENT, rounding=ROUND_HALF_UP)
    down = (prev * (Decimal("1") - rate)).quantize(CENT, rounding=ROUND_HALF_UP)
    if down < 0:
        down = Decimal("0.00")
    return {
        "code": info["code"],
        "exchange": info["exchange"],
        "board": info["board"],
        "currency": info["currency"],
        "limit_pct": pct,
        "st_applied": bool(st),
        "prev_close": float(prev),
        "limit_up": float(up),
        "limit_down": float(down),
    }


def check_price(code, prev_close, price, st=False, name=None):
    """校验价格是否落在涨跌停区间内，并给出结论。"""
    lp = limit_prices(code, prev_close, st=st)
    p = Decimal(str(price))
    up = Decimal(str(lp["limit_up"]))
    down = Decimal(str(lp["limit_down"]))
    issues = []
    if p > up:
        issues.append("价格 %.2f 高于涨停价 %.2f，数据或口径有误" % (float(p), float(up)))
    if p < down:
        issues.append("价格 %.2f 低于跌停价 %.2f，数据或口径有误" % (float(p), float(down)))
    chg = (p - Decimal(str(prev_close))) / Decimal(str(prev_close)) * Decimal("100")
    chg = chg.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    at_limit = "涨停" if p == up else ("跌停" if p == down else None)
    if at_limit:
        issues.append("处于%s价，注意价格存在但未必可成交（一字板无法买入/卖出）" % at_limit)
    notes = []
    if name and ("ST" in str(name).upper()):
        notes.append("名称含 ST，主板幅度应为 5%，请确认已使用 --st")
    if lp["exchange"] == "股转系统":
        notes.append("该代码属两网及退市板块，不适用常规 A 股交易规则")
    if lp["currency"] != "CNY":
        notes.append("B 股以非人民币计价，不可与 A 股价格直接比较")
    return {
        "ok": len([i for i in issues if "高于" in i or "低于" in i]) == 0,
        "code": lp["code"],
        "board": lp["board"],
        "pct_chg": float(chg),
        "limit": lp,
        "at_limit": at_limit,
        "issues": issues,
        "notes": notes,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="A股规则校验器")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("board", help="板块与涨跌幅")
    b.add_argument("--code", required=True)

    l = sub.add_parser("limit", help="涨跌停价")
    l.add_argument("--code", required=True)
    l.add_argument("--prev-close", required=True, type=float)
    l.add_argument("--st", action="store_true")

    c = sub.add_parser("check", help="价格校验")
    c.add_argument("--code", required=True)
    c.add_argument("--prev-close", required=True, type=float)
    c.add_argument("--price", required=True, type=float)
    c.add_argument("--st", action="store_true")
    c.add_argument("--name", default=None)

    m = sub.add_parser("codes", help="批量归类")
    m.add_argument("--file", required=True)

    args = ap.parse_args(argv)
    try:
        if args.cmd == "board":
            out = classify(args.code)
        elif args.cmd == "limit":
            out = limit_prices(args.code, args.prev_close, st=args.st)
        elif args.cmd == "check":
            out = check_price(args.code, args.prev_close, args.price,
                              st=args.st, name=args.name)
        else:
            results = []
            with open(args.file, "r", encoding="utf-8") as fh:
                for line in fh:
                    token = line.strip()
                    if not token or token.startswith("#"):
                        continue
                    try:
                        results.append(classify(token))
                    except RuleError as exc:
                        results.append({"code": token, "error": str(exc)})
            out = results
    except RuleError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
