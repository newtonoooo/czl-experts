#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A股行情取数（零第三方依赖，标准库 urllib）。

三级阶梯：
  L1 公开接口：新浪（实时行情）→ 东方财富（日K / 备用实时）
  L2 用户已连接的金融工具（本脚本不实现，由 Agent 在 L1 失败后调用）
  L3 联网检索（同上，由 Agent 调用）

设计约束：
  * 单源超时默认 8 秒，失败立即降级，不重试同一源。
  * 任何结果都带 source / fetch_time / quality 三个字段，缺一不可。
  * 取不到就返回 ok=false 与原因，绝不返回填充值。

CLI:
  python arfetch.py quote --codes 600519,000001
  python arfetch.py index
  python arfetch.py kline --code 600519 --days 250 --fq qfq
  python arfetch.py parse-selftest
"""
import argparse
import json
import re
import socket
import sys
import urllib.error
import urllib.request
from datetime import datetime

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
TIMEOUT = 8

SINA_QUOTE = "https://hq.sinajs.cn/list={symbols}"
SINA_INDEX = "https://hq.sinajs.cn/list={symbols}"
EM_KLINE = ("https://push2his.eastmoney.com/api/qt/stock/kline/get?"
            "secid={secid}&fields1=f1,f2,f3,f4,f5,f6&"
            "fields2=f51,f52,f53,f54,f55,f56,f57&klt={klt}&fqt={fqt}"
            "&beg=0&end=20500101&lmt={lmt}")

INDEXES = {
    "上证指数": "s_sh000001",
    "深证成指": "s_sz399001",
    "创业板指": "s_sz399006",
    "科创50": "s_sh000688",
    "北证50": "s_bj899050",
}


class FetchError(RuntimeError):
    pass


# ---------- 代码与市场 ----------

def split_code(code):
    """600519 / sh600519 / 600519.SH -> (market, digits)  market in sh/sz/bj"""
    s = str(code).strip().upper().replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
    for m in ("SH", "SZ", "BJ"):
        if s.startswith(m):
            s = s[len(m):]
            return m.lower(), s
    if not s.isdigit() or len(s) != 6:
        raise FetchError("代码格式错误：%r" % code)
    if s.startswith(("60", "68", "90")):
        return "sh", s
    if s.startswith(("00", "30", "20")):
        return "sz", s
    if s.startswith(("83", "87", "88", "43", "92")):
        return "bj", s
    raise FetchError("无法判断市场：%s" % s)


def em_secid(code):
    m, d = split_code(code)
    return ("1." if m == "sh" else "0.") + d


# ---------- HTTP ----------

def http_get(url, referer=None, timeout=TIMEOUT):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Referer": referer or "https://finance.sina.com.cn",
        "Accept": "*/*",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return raw
    except (urllib.error.URLError, socket.timeout, TimeoutError) as exc:
        raise FetchError("请求失败：%s（%s）" % (url.split("?")[0], exc))
    except Exception as exc:  # noqa: BLE001
        raise FetchError("请求异常：%s（%s）" % (url.split("?")[0], exc))


# ---------- 解析（纯函数，可离线测试） ----------

def parse_sina_quote(text):
    """解析新浪行情字符串。返回 list[dict]。

    个股字段顺序：名称,今开,昨收,现价,最高,最低,买一,卖一,成交量(股),成交额(元),...
    指数（s_ 前缀）：名称,现价,涨跌额,涨跌幅%,成交量(手),成交额(万元)
    """
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        m = re.match(r'var hq_str_(\w+)="(.*)";?', line)
        if not m:
            continue
        symbol, payload = m.group(1), m.group(2)
        if not payload.strip():
            out.append({"symbol": symbol, "ok": False, "error": "空数据（代码可能不存在或已退市）"})
            continue
        parts = payload.split(",")
        is_index = symbol.startswith("s_")
        try:
            if is_index:
                out.append({
                    "symbol": symbol, "ok": True,
                    "name": parts[0],
                    "last": float(parts[1]),
                    "change": float(parts[2]),
                    "pct_chg": float(parts[3]),
                    "volume": float(parts[4]) if parts[4] else None,
                    "amount_yuan": float(parts[5]) * 10000 if parts[5] else None,
                })
            else:
                last = float(parts[3])
                prev = float(parts[2])
                out.append({
                    "symbol": symbol, "ok": True,
                    "name": parts[0],
                    "open": float(parts[1]),
                    "prev_close": prev,
                    "last": last,
                    "high": float(parts[4]),
                    "low": float(parts[5]),
                    "volume_shares": float(parts[8]) if parts[8] else None,
                    "amount_yuan": float(parts[9]) if len(parts) > 9 and parts[9] else None,
                    "pct_chg": round((last / prev - 1) * 100, 2) if prev else None,
                    "trade_date": parts[30] if len(parts) > 30 else None,
                    "trade_time": parts[31] if len(parts) > 31 else None,
                })
        except (ValueError, IndexError) as exc:
            out.append({"symbol": symbol, "ok": False, "error": "字段解析失败：%s" % exc})
    return out


def parse_em_kline(payload):
    """解析东方财富日K JSON。返回 list[dict]。"""
    data = json.loads(payload)
    klines = (data.get("data") or {}).get("klines")
    if not klines:
        raise FetchError("东财返回无 K 线数据（代码可能不存在或停牌）")
    bars = []
    for row in klines:
        f = row.split(",")
        bars.append({
            "date": f[0],
            "open": float(f[1]),
            "close": float(f[2]),
            "high": float(f[3]),
            "low": float(f[4]),
            "volume": float(f[5]),
            "amount": float(f[6]) if len(f) > 6 and f[6] else None,
        })
    return bars


# ---------- 取数 ----------

def get_quotes(codes):
    symbols = []
    for c in codes:
        m, d = split_code(c)
        symbols.append(m + d)
    url = SINA_QUOTE.format(symbols=",".join(symbols))
    raw = http_get(url)
    text = raw.decode("gbk", errors="replace")
    items = parse_sina_quote(text)
    ok = [x for x in items if x.get("ok")]
    quality = "primary" if len(ok) == len(symbols) else "partial"
    return {
        "ok": bool(ok),
        "source": "新浪财经 hq.sinajs.cn",
        "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "quality": quality,
        "items": items,
    }


def get_indexes():
    url = SINA_INDEX.format(symbols=",".join(INDEXES.values()))
    raw = http_get(url)
    text = raw.decode("gbk", errors="replace")
    items = parse_sina_quote(text)
    name_map = {v: k for k, v in INDEXES.items()}
    for it in items:
        it["label"] = name_map.get(it.get("symbol"), it.get("symbol"))
    return {
        "ok": any(x.get("ok") for x in items),
        "source": "新浪财经 hq.sinajs.cn",
        "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "quality": "primary" if all(x.get("ok") for x in items) else "partial",
        "items": items,
    }


def get_kline(code, days=250, fq="qfq"):
    fqt = {"qfq": 1, "hfq": 2, "none": 0}.get(fq, 1)
    url = EM_KLINE.format(secid=em_secid(code), klt=101, fqt=fqt, lmt=int(days))
    raw = http_get(url, referer="https://quote.eastmoney.com/")
    bars = parse_em_kline(raw.decode("utf-8", errors="replace"))
    # 东财在 beg=0 时会忽略 lmt，按需从尾部截断
    if days and len(bars) > int(days):
        bars = bars[-int(days):]
    return {
        "ok": True,
        "code": code,
        "fq": fq,
        "source": "东方财富 push2his.eastmoney.com",
        "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "quality": "primary",
        "bars": bars,
    }


# ---------- 解析器自检（离线，不联网） ----------

def parse_selftest():
    sample = (
        'var hq_str_sh600519="贵州茅台,1500.000,1490.000,1520.500,1530.000,1495.000,'
        '1520.000,1520.500,1234567,1876500000.00,100,1520.000,200,1521.000,'
        '300,1522.000,400,1523.000,500,1524.000,600,1519.000,700,1518.000,'
        '800,1517.000,900,1516.000,1000,1515.000,2026-10-29,15:00:00,00";\n'
        'var hq_str_s_sh000001="上证指数,3412.567,12.345,0.36,3200000,45000000";'
    )
    items = parse_sina_quote(sample)
    stock = items[0]
    index = items[1]
    checks = [
        ("个股条数", len(items) == 2),
        ("名称解析", stock["name"] == "贵州茅台"),
        ("现价解析", stock["last"] == 1520.5),
        ("昨收解析", stock["prev_close"] == 1490.0),
        ("涨跌幅计算", stock["pct_chg"] == 2.05),
        ("成交额解析", stock["amount_yuan"] == 1876500000.00),
        ("日期解析", stock["trade_date"] == "2026-10-29"),
        ("指数解析", index["label"] if "label" in index else index["name"] == "上证指数"),
        ("指数成交额换算", index["amount_yuan"] == 450000000000.0),
    ]
    em = {"data": {"klines": ["2026-10-28,1490.0,1500.0,1505.0,1488.0,1200000,1.8e9",
                              "2026-10-29,1500.0,1520.5,1530.0,1495.0,1234567,1.87e9"]}}
    bars = parse_em_kline(json.dumps(em))
    checks.append(("K线根数", len(bars) == 2))
    checks.append(("K线收盘", bars[-1]["close"] == 1520.5))
    checks.append(("K线最高", bars[-1]["high"] == 1530.0))

    failed = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print(("  PASS  " if ok else "  FAIL  ") + n)
    print("结果：%d/%d 通过" % (len(checks) - len(failed), len(checks)))
    return 0 if not failed else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="A股行情取数（三级降级）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("quote")
    q.add_argument("--codes", required=True)
    sub.add_parser("index")
    k = sub.add_parser("kline")
    k.add_argument("--code", required=True)
    k.add_argument("--days", type=int, default=250)
    k.add_argument("--fq", default="qfq", choices=["qfq", "hfq", "none"])
    sub.add_parser("parse-selftest")
    args = ap.parse_args(argv)

    if args.cmd == "parse-selftest":
        return parse_selftest()

    try:
        if args.cmd == "quote":
            res = get_quotes([c.strip() for c in args.codes.split(",") if c.strip()])
        elif args.cmd == "index":
            res = get_indexes()
        else:
            res = get_kline(args.code, args.days, args.fq)
    except FetchError as exc:
        print(json.dumps({
            "ok": False,
            "quality": "fetch_failed",
            "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error": str(exc),
            "next": "L1 全部失败，请改用 L2（用户已连接的金融工具）或 L3（联网检索），并在报告中标注 [FALLBACK]",
        }, ensure_ascii=False, indent=2))
        return 3
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
