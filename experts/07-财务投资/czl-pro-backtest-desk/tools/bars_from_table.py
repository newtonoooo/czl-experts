#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bars_from_table.py — 把 Markdown 表 / TSV / CSV 行情表转成回测内核契约 CSV

支持的表头（中英混排都行）：
    date/日期/时间/交易日期     open/开盘/开盘价
    high/最高/最高价           low/最低/最低价
    close/收盘/收盘价           volume/成交量/成交额(不推荐)

用法：
    python tools/bars_from_table.py raw.md -o data/bars_510300.csv --symbol 510300.SH
    python tools/bars_from_table.py raw.md              # 只打印体检结果，不写文件
    type raw.txt | python tools/bars_from_table.py -     # 从标准输入读

退出码：0 正常 / 1 输入无法解析
"""
import argparse
import csv
import hashlib
import os
import re
import sys
from datetime import datetime

ALIASES = {
    "date": ["date", "日期", "时间", "交易日期", "trade_date", "day", "datetime"],
    "open": ["open", "开盘", "开盘价", "o"],
    "high": ["high", "最高", "最高价", "h"],
    "low": ["low", "最低", "最低价", "l"],
    "close": ["close", "收盘", "收盘价", "c", "最新价"],
    "volume": ["volume", "成交量", "vol", "v", "成交额", "amount", "turnover"],
}


def norm_key(s):
    s = str(s).strip().strip("|").strip()
    s = s.replace("*", "").replace("`", "")
    s = re.sub(r"[（(].*?[)）]", "", s)
    return s.strip().lower()


def split_rows(text):
    lines = [ln.rstrip("\n") for ln in text.splitlines() if ln.strip()]
    # 丢掉 Markdown 的分隔行 |---|---|
    lines = [ln for ln in lines if not re.match(r"^\s*\|?[\s:\-|]+\|?\s*$", ln)]
    if not lines:
        return [], None
    sample = lines[0]
    if sample.count("|") >= 3:
        delim = "|"
    elif "\t" in sample:
        delim = "\t"
    else:
        delim = ","

    def cells(line):
        if delim == "|":
            parts = [p for p in line.strip().strip("|").split("|")]
        elif delim == "\t":
            parts = line.split("\t")
        else:
            parts = next(csv.reader([line]))
        return [c.strip() for c in parts]

    header = [norm_key(c) for c in cells(lines[0])]
    body = []
    for ln in lines[1:]:
        row = cells(ln)
        if len(row) != len(header):
            continue
        body.append(dict(zip(header, row)))
    return body, header


def pick(header, field):
    for alias in ALIASES[field]:
        if alias in header:
            return alias
    return None


def to_float(raw):
    if raw is None:
        return None
    s = str(raw).replace(",", "").replace("%", "").strip()
    if s in ("", "-", "--", "nan", "NaN", "null", "None"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def norm_date(raw):
    s = str(raw).strip().replace("/", "-").split(" ")[0]
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", s):
        y, m, d = s.split("-")
        return "%s-%02d-%02d" % (y, int(m), int(d))
    return None


def convert(body, header):
    cols = {f: pick(header, f) for f in ("date", "open", "high", "low", "close", "volume")}
    missing = [f for f in ("date", "open", "high", "low", "close") if not cols[f]]
    if missing:
        raise ValueError("表头里找不到这些列：%s；实际表头：%s" % (missing, header))
    rows, dropped, ohlc_bad = [], 0, 0
    for r in body:
        d = norm_date(r.get(cols["date"], ""))
        o = to_float(r.get(cols["open"]))
        h = to_float(r.get(cols["high"]))
        l = to_float(r.get(cols["low"]))
        c = to_float(r.get(cols["close"]))
        if not d or None in (o, h, l, c) or min(o, h, l, c) <= 0:
            dropped += 1
            continue
        if h < max(o, c) - 1e-9 or l > min(o, c) + 1e-9:
            ohlc_bad += 1
        v = to_float(r.get(cols["volume"])) if cols["volume"] else 0.0
        rows.append([d, o, h, l, c, int(v or 0)])
    dedup = {}
    for r in rows:
        dedup[r[0]] = r
    rows = [dedup[k] for k in sorted(dedup)]
    return rows, {"dropped": dropped, "ohlc_bad": ohlc_bad}


def gaps(rows, max_days=5):
    out = []
    for i in range(1, len(rows)):
        d0 = datetime.strptime(rows[i - 1][0], "%Y-%m-%d")
        d1 = datetime.strptime(rows[i][0], "%Y-%m-%d")
        if (d1 - d0).days > max_days:
            out.append({"from": rows[i - 1][0], "to": rows[i][0], "days": (d1 - d0).days})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="输入文件，或 - 表示标准输入")
    ap.add_argument("-o", "--out", help="输出 CSV 路径；不给则只做体检")
    ap.add_argument("--symbol", default="", help="写入日志用的标的代码")
    args = ap.parse_args()

    if args.input == "-":
        text = sys.stdin.read()
    else:
        with open(args.input, "r", encoding="utf-8-sig", errors="replace") as fh:
            text = fh.read()

    body, header = split_rows(text)
    if not body:
        print("解析失败：没有数据行。前几行内容：\n%s" % "\n".join(text.splitlines()[:5]))
        return 1
    try:
        rows, info = convert(body, header)
    except ValueError as exc:
        print("解析失败：%s" % exc)
        return 1
    if not rows:
        print("解析失败：所有行都被判为无效（价格缺失或 ≤ 0）")
        return 1

    gs = gaps(rows)
    print("标的：%s｜行数：%d｜区间：%s → %s" % (args.symbol or "(未指定)", len(rows), rows[0][0], rows[-1][0]))
    print("丢弃行：%d｜OHLC 关系异常：%d｜超过 5 天的间隔：%d 处" % (info["dropped"], info["ohlc_bad"], len(gs)))
    for g in gs[:5]:
        print("  间隔 %s → %s（%d 天）" % (g["from"], g["to"], g["days"]))

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["date", "open", "high", "low", "close", "volume"])
            w.writerows(rows)
        digest = hashlib.sha256(open(args.out, "rb").read()).hexdigest()[:16]
        print("已写入：%s（sha256:%s…）" % (args.out, digest))
    return 0


if __name__ == "__main__":
    sys.exit(main())
