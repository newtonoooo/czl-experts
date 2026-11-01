#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
czl_core.py — 数证台工具箱的共享核心。

提供：编码探测与表格读取、数值清洗、分位数与描述统计、正态与 t 分布尾概率、
bootstrap 区间、日期解析与周期键、Markdown 表格渲染。

纯标准库，无第三方依赖。本文件不单独使用，由同目录脚本 import。
"""

from __future__ import annotations

import csv
import io
import math
import os
import random
import sys
from datetime import date, datetime, timedelta

# ---------------------------------------------------------------- 基础输出


def die(msg: str, code: int = 2) -> "None":
    """统一的失败出口：中文提示 + 非零退出码，不抛堆栈。"""
    sys.stderr.write("错误：%s\n" % msg)
    sys.exit(code)


def warn(msg: str) -> None:
    sys.stderr.write("提示：%s\n" % msg)


# ---------------------------------------------------------------- 读表

ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "gbk", "latin-1")


def read_text(path: str) -> tuple[str, str]:
    if not os.path.exists(path):
        die("文件不存在：%s" % path)
    if os.path.isdir(path):
        die("这是一个目录，请指定具体文件：%s" % path)
    raw = open(path, "rb").read()
    if not raw.strip():
        die("文件是空的：%s" % path)
    for enc in ENCODINGS:
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    die("无法识别文件编码，请用 Excel 另存为 UTF-8 的 CSV 再试：%s" % path)


def detect_delimiter(sample: str) -> str:
    head = "\n".join(sample.splitlines()[:5])
    counts = {d: head.count(d) for d in (",", "\t", ";", "|")}
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else ","


def read_table(path: str) -> tuple[list[str], list[list[str]], str]:
    """返回 (表头, 数据行, 编码)。表头做去空白与去重处理。"""
    text, enc = read_text(path)
    delim = detect_delimiter(text)
    reader = csv.reader(io.StringIO(text), delimiter=delim)
    rows = [r for r in reader if any((c or "").strip() for c in r)]
    if not rows:
        die("文件里没有任何数据行：%s" % path)
    header = [(_clean_header(h) or "列%d" % (i + 1)) for i, h in enumerate(rows[0])]
    seen, uniq = {}, []
    for h in header:
        if h in seen:
            seen[h] += 1
            uniq.append("%s_%d" % (h, seen[h]))
        else:
            seen[h] = 0
            uniq.append(h)
    body = rows[1:]
    width = len(uniq)
    body = [(r + [""] * width)[:width] for r in body]
    return uniq, body, enc


def _clean_header(h: str) -> str:
    return (h or "").strip().strip('"').replace("\n", " ").strip()


def col_index(header: list[str], name: str) -> int:
    if name in header:
        return header.index(name)
    low = {h.lower(): i for i, h in enumerate(header)}
    if name.lower() in low:
        return low[name.lower()]
    die("找不到列「%s」。可用列：%s" % (name, "、".join(header[:20])))


# ---------------------------------------------------------------- 数值

_UNITS = {"万": 1e4, "萬": 1e4, "亿": 1e8, "億": 1e8, "千": 1e3, "k": 1e3, "K": 1e3}


def to_number(s) -> float | None:
    """把 "¥1,234.5"、"1.2万"、"-3.1%" 之类转成 float。失败返回 None。"""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    t = str(s).strip()
    if not t or t in ("-", "--", "—", "N/A", "n/a", "NA", "null", "NULL", "None"):
        return None
    t = t.replace(",", "").replace("，", "").replace(" ", "")
    mult = 1.0
    pct = False
    for unit, m in _UNITS.items():
        if t.endswith(unit):
            mult = m
            t = t[: -len(unit)]
            break
    if t.endswith("%"):
        pct = True
        t = t[:-1]
    t = t.replace("¥", "").replace("￥", "").replace("$", "").replace("元", "")
    try:
        v = float(t) * mult
    except ValueError:
        return None
    return v / 100.0 if pct else v


def numbers(rows, idx) -> list[float]:
    out = []
    for r in rows:
        v = to_number(r[idx])
        if v is not None:
            out.append(v)
    return out


def total(vals) -> float:
    return float(sum(vals))


def mean(vals) -> float:
    return sum(vals) / len(vals) if vals else float("nan")


def variance(vals, ddof: int = 1) -> float:
    n = len(vals)
    if n - ddof <= 0:
        return float("nan")
    m = mean(vals)
    return sum((v - m) ** 2 for v in vals) / (n - ddof)


def stdev(vals, ddof: int = 1) -> float:
    v = variance(vals, ddof)
    return math.sqrt(v) if v == v else float("nan")


def quantile(sorted_vals: list[float], q: float) -> float:
    """线性插值分位数，输入需已排序。"""
    if not sorted_vals:
        return float("nan")
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = (len(sorted_vals) - 1) * q
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def median(vals) -> float:
    return quantile(sorted(vals), 0.5)


# ---------------------------------------------------------------- 分布

def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_ppf(p: float) -> float:
    """标准正态分位数（Acklam 近似，误差 <1.15e-9）。"""
    if not 0 < p < 1:
        die("概率必须在 (0,1) 之间，收到 %s" % p)
    a = [-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
         1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00]
    b = [-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
         6.680131188771972e01, -1.328068155288572e01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
         -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
         3.754408661907416e00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
                ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


def _betacf(a: float, b: float, x: float) -> float:
    """不完全贝塔函数的连分式部分（Lentz 法）。"""
    MAXIT, EPS, FPMIN = 200, 3e-12, 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < FPMIN:
        d = FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < EPS:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    """正则化不完全贝塔函数 I_x(a,b)。"""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1 - x) / b


def t_sf_two_sided(t: float, df: float) -> float:
    """t 分布双侧尾概率。"""
    if df <= 0:
        return float("nan")
    x = df / (df + t * t)
    return betainc(df / 2.0, 0.5, x)


# ---------------------------------------------------------------- 区间

def bootstrap_diff_ci(a: list[float], b: list[float], bsize: int = 2000,
                      alpha: float = 0.05, seed: int = 20261026,
                      stat: str = "mean") -> tuple[float, float]:
    """两样本均值（或比例）之差的百分位 bootstrap 区间。"""
    rnd = random.Random(seed)
    diffs = []
    na, nb = len(a), len(b)
    for _ in range(bsize):
        sa = [a[rnd.randrange(na)] for _ in range(na)]
        sb = [b[rnd.randrange(nb)] for _ in range(nb)]
        if stat == "mean":
            diffs.append(mean(sb) - mean(sa))
        else:  # proportion
            diffs.append(sum(sb) / nb - sum(sa) / na)
    diffs.sort()
    return quantile(diffs, alpha / 2), quantile(diffs, 1 - alpha / 2)


# ---------------------------------------------------------------- 日期

_FMTS = ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S",
         "%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y%m", "%Y-%m", "%Y年%m月%d日",
         "%d/%m/%Y", "%m/%d/%Y")


def to_date(s) -> date | None:
    if isinstance(s, datetime):
        return s.date()
    if isinstance(s, date):
        return s
    if s is None:
        return None
    t = str(s).strip()
    if not t:
        return None
    if "T" in t:
        t = t.split("T")[0]
    if "." in t and len(t) > 10:
        t = t.split(".")[0]
    for fmt in _FMTS:
        try:
            return datetime.strptime(t, fmt).date()
        except ValueError:
            continue
    # 只有年月（如 2026-06）
    for sep in ("-", "/"):
        parts = t.split(sep)
        if len(parts) == 2 and parts[0].isdigit() and len(parts[0]) == 4:
            try:
                return date(int(parts[0]), int(parts[1]), 1)
            except ValueError:
                return None
    return None


def period_key(d: date, kind: str) -> str:
    if kind == "day":
        return d.isoformat()
    if kind == "week":
        iso = d.isocalendar()
        return "%d-W%02d" % (iso[0], iso[1])
    if kind == "month":
        return "%04d-%02d" % (d.year, d.month)
    if kind == "quarter":
        return "%d-Q%d" % (d.year, (d.month - 1) // 3 + 1)
    return d.isoformat()


def period_index(key: str, kind: str) -> int:
    """把周期键换成可比较的序号，便于算间隔。"""
    if kind == "week":
        y, w = key.split("-W")
        return int(y) * 53 + int(w)
    if kind == "month":
        y, m = key.split("-")
        return int(y) * 12 + int(m)
    if kind == "quarter":
        y, q = key.split("-Q")
        return int(y) * 4 + int(q)
    return date.fromisoformat(key).toordinal()


def month_range(start: date, end: date) -> list[str]:
    out, y, m = [], start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append("%04d-%02d" % (y, m))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


# ---------------------------------------------------------------- 输出格式

def pct(x: float, digits: int = 1) -> str:
    if x is None or x != x:
        return "—"
    return ("%." + str(digits) + "f%%") % (x * 100)


def money(x: float, currency: str = "元") -> str:
    """中文金额写法：≥10 万用「万」，≥1 亿用「亿」，其余带千分位。"""
    if x is None or x != x:
        return "—"
    ax = abs(x)
    if ax >= 1e8:
        return "%.2f 亿%s" % (x / 1e8, currency)
    if ax >= 1e5:
        return "%.2f 万%s" % (x / 1e4, currency)
    return "{:,.2f} {}".format(x, currency)


def num(x: float, digits: int = 2) -> str:
    if x is None or x != x:
        return "—"
    return ("%." + str(digits) + "f") % x


def signed_pct(x: float, digits: int = 1) -> str:
    if x is None or x != x:
        return "—"
    return ("%+." + str(digits) + "f%%") % (x * 100)


def md_table(headers: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(str(h) for h in headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        out.append("| " + " | ".join("" if c is None else str(c) for c in r) + " |")
    return "\n".join(out)


def write_out(text: str, path: str | None) -> None:
    if path:
        folder = os.path.dirname(os.path.abspath(path))
        if folder and not os.path.isdir(folder):
            os.makedirs(folder, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print("已写出：%s" % path)
    else:
        print(text)


# ---------------------------------------------------------------- 分组工具

def groups(rows, idx) -> dict:
    out = {}
    for r in rows:
        out.setdefault((r[idx] or "（空）").strip(), []).append(r)
    return out


def parse_range(span: str) -> tuple[date, date]:
    """支持 2026-06、2026-06-01、2026-06-01..2026-06-30。"""
    if ".." in span:
        a, b = span.split("..")
        da, db = to_date(a), to_date(b)
        if not da or not db:
            die("时间区间写法不对：%s（示例 2026-06-01..2026-06-30）" % span)
        return da, db
    d = to_date(span)
    if not d:
        die("日期写法不认识：%s（示例 2026-06 或 2026-06-15）" % span)
    if len(span.strip()) == 7:
        if d.month == 12:
            end = date(d.year + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(d.year, d.month + 1, 1) - timedelta(days=1)
        return date(d.year, d.month, 1), end
    return d, d
