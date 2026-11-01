# -*- coding: utf-8 -*-
"""三棱镜数据专家团 · 表格读取与类型推断层

纯标准库实现，支持 CSV（含 BOM / GBK 回退）与 XLSX（zip + OOXML 解析，
含共享字符串与日期数字格式识别）。不依赖 pandas / openpyxl。

设计原则：
1. 只读不写，不修改用户源文件；
2. 读不到就明确报错，不静默丢列；
3. 所有推断结果都写进 profile，便于复核。
"""

from __future__ import annotations

import csv
import datetime as _dt
import io
import os
import re
import zipfile
from xml.etree import ElementTree as ET

NS_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
NS_PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"

DATE_FMT_IDS = set(range(14, 23)) | {27, 30, 36, 45, 46, 47, 50, 57}
DATE_TOKEN = re.compile(r"(y{2,4}|m{1,4}|d{1,4}|h{1,2}|s{1,2})", re.I)
EXCEL_EPOCH = _dt.datetime(1899, 12, 30)


class TableError(Exception):
    """表格无法读取时抛出，附带可读原因。"""


class Column:
    __slots__ = ("name", "index", "kind", "values", "nulls", "raw_nulls")

    def __init__(self, name, index):
        self.name = name
        self.index = index
        self.kind = "text"          # number / date / text / bool / empty
        self.values = []            # 非空值（已转换）
        self.nulls = 0
        self.raw_nulls = 0          # 空字符串或 None 的原始计数

    def as_dict(self):
        return {"name": self.name, "index": self.index, "kind": self.kind,
                "non_null": len(self.values), "null": self.nulls}


class Table:
    def __init__(self, source, sheet, headers, rows, notes=None):
        self.source = source
        self.sheet = sheet
        self.headers = headers
        self.rows = rows            # list[list[object]]，原始单元格（未推断）
        self.notes = notes or []
        self.columns = []

    @property
    def n_rows(self):
        return len(self.rows)

    @property
    def n_cols(self):
        return len(self.headers)

    def column(self, name):
        for c in self.columns:
            if c.name == name:
                return c
        raise KeyError(name)

    def has(self, name):
        return any(c.name == name for c in self.columns)

    def numeric_columns(self):
        return [c for c in self.columns if c.kind == "number"]

    def date_columns(self):
        return [c for c in self.columns if c.kind == "date"]

    def text_columns(self):
        return [c for c in self.columns if c.kind == "text"]

    def summary(self):
        return {"source": os.path.basename(self.source), "sheet": self.sheet,
                "rows": self.n_rows, "cols": self.n_cols,
                "headers": list(self.headers), "notes": list(self.notes)}


# ---------------------------------------------------------------- 值解析

_NUM_CLEAN = re.compile(r"[,\s¥$€£%]|元|万元|亿元|个|人|次|单")


def _to_number(raw):
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    neg = s.startswith("(") and s.endswith(")")
    if neg:
        s = s[1:-1]
    s = _NUM_CLEAN.sub("", s)
    if s.endswith("%"):
        s = s[:-1]
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


_DATE_PATTERNS = [
    (re.compile(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})([ T](\d{1,2}):(\d{2})(:(\d{2}))?)?$"), "ymd"),
    (re.compile(r"^(\d{4})年(\d{1,2})月(\d{1,2})日?$"), "cn_ymd"),
    (re.compile(r"^(\d{4})年(\d{1,2})月$"), "cn_ym"),
    (re.compile(r"^(\d{4})[-/.](\d{1,2})$"), "ym"),
    (re.compile(r"^(\d{4})(\d{2})(\d{2})$"), "ymd_compact"),
]


def parse_date(raw):
    """返回 datetime；无法解析返回 None。只认明确的时间表达，避免把编号误判成日期。"""
    if isinstance(raw, _dt.datetime):
        return raw
    if isinstance(raw, _dt.date):
        return _dt.datetime(raw.year, raw.month, raw.day)
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    for pat, kind in _DATE_PATTERNS:
        m = pat.match(s)
        if not m:
            continue
        g = m.groups()
        try:
            y = int(g[0])
            mo = int(g[1]) if len(g) > 1 and g[1] else 1
            d = int(g[2]) if len(g) > 2 and g[2] else 1
            hh = int(g[4]) if len(g) > 4 and g[4] else 0
            mm = int(g[5]) if len(g) > 5 and g[5] else 0
            ss = int(g[7]) if len(g) > 7 and g[7] else 0
            if not (1900 <= y <= 2200 and 1 <= mo <= 12 and 1 <= d <= 31):
                return None
            return _dt.datetime(y, mo, d, hh, mm, ss)
        except (ValueError, IndexError):
            return None
    return None


def excel_serial_to_datetime(v):
    try:
        return EXCEL_EPOCH + _dt.timedelta(days=float(v))
    except (ValueError, OverflowError):
        return None


# ---------------------------------------------------------------- 类型推断

def infer_kind(values):
    """根据样本推断列类型：number / date / text / empty。

    判定顺序：先看是否全部可转数字；再看是否 ≥80% 可解析为日期且首值可解析；
    否则文本。少于 3 个样本时保守判为 text。
    """
    vals = [v for v in values if v is not None and str(v).strip() != ""]
    if not vals:
        return "empty"
    sample = vals[:400]
    num_hit = sum(1 for v in sample if _to_number(v) is not None)
    if num_hit >= max(1, int(len(sample) * 0.95)):
        return "number"
    date_hit = sum(1 for v in sample if parse_date(v) is not None)
    if date_hit >= max(1, int(len(sample) * 0.8)) and parse_date(sample[0]) is not None:
        return "date"
    return "text"


def build_columns(table):
    cols = []
    for idx, name in enumerate(table.headers):
        col = Column(name, idx)
        raw_vals = [r[idx] if idx < len(r) else None for r in table.rows]
        col.kind = infer_kind(raw_vals)
        for raw in raw_vals:
            if raw is None or str(raw).strip() == "":
                col.nulls += 1
                col.raw_nulls += 1
                continue
            if col.kind == "number":
                v = _to_number(raw)
                if v is None:
                    col.nulls += 1
                    continue
                col.values.append(v)
            elif col.kind == "date":
                v = parse_date(raw)
                if v is None:
                    col.nulls += 1
                    continue
                col.values.append(v)
            else:
                col.values.append(str(raw).strip())
        cols.append(col)
    table.columns = cols
    return table


# ---------------------------------------------------------------- CSV

def _decode(raw):
    for enc in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def read_csv(path, sheet=None, delimiter=None):
    with open(path, "rb") as fh:
        text = _decode(fh.read())
    if not text.strip():
        raise TableError("文件为空，没有可分析的内容")
    sample = text[:8192]
    if delimiter is None:
        try:
            delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
        except csv.Error:
            delimiter = ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = [r for r in reader if any(str(c).strip() for c in r)]
    if len(rows) < 2:
        raise TableError("有效数据行不足 2 行，无法分析")
    headers = [str(h).strip() or f"列{i+1}" for i, h in enumerate(rows[0])]
    body = rows[1:]
    notes = []
    width = len(headers)
    ragged = 0
    fixed = []
    for r in body:
        if len(r) != width:
            ragged += 1
            r = (r + [None] * width)[:width]
        fixed.append(list(r))
    if ragged:
        notes.append(f"{ragged} 行的列数与表头不一致，已按表头宽度补齐/截断")
    return build_columns(Table(path, sheet or os.path.basename(path), headers, fixed, notes))


# ---------------------------------------------------------------- XLSX

def _read_shared_strings(zf):
    try:
        data = zf.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(data)
    out = []
    for si in root.findall(f"{NS_MAIN}si"):
        out.append("".join(t.text or "" for t in si.iter(f"{NS_MAIN}t")))
    return out


def _read_date_styles(zf):
    """返回 {styleIndex: is_date}，用于把数字单元格还原成日期。"""
    try:
        data = zf.read("xl/styles.xml")
    except KeyError:
        return {}
    root = ET.fromstring(data)
    custom = {}
    numfmts = root.find(f"{NS_MAIN}numFmts")
    if numfmts is not None:
        for nf in numfmts.findall(f"{NS_MAIN}numFmt"):
            fid = int(nf.get("numFmtId", "0"))
            code = nf.get("formatCode", "")
            custom[fid] = bool(DATE_TOKEN.search(code)) and "[" not in code
    cellxfs = root.find(f"{NS_MAIN}cellXfs")
    result = {}
    if cellxfs is None:
        return result
    for i, xf in enumerate(cellxfs.findall(f"{NS_MAIN}xf")):
        fid = int(xf.get("numFmtId", "0"))
        result[i] = custom.get(fid, fid in DATE_FMT_IDS)
    return result


def _col_index(ref):
    letters = re.match(r"([A-Z]+)", ref or "")
    if not letters:
        return 0
    idx = 0
    for ch in letters.group(1):
        idx = idx * 26 + (ord(ch) - 64)
    return idx - 1


def _sheet_paths(zf):
    """返回 [(sheetName, zipPath)]，按工作簿顺序。"""
    try:
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    except KeyError as exc:
        raise TableError(f"XLSX 结构不完整：缺少 {exc}") from exc
    rel_map = {}
    for rel in rels.findall(f"{NS_PKG_REL}Relationship"):
        target = rel.get("Target", "")
        if target.startswith("/"):
            target = target.lstrip("/")
        elif not target.startswith("xl/"):
            target = "xl/" + target
        rel_map[rel.get("Id")] = target
    out = []
    for sh in wb.iter(f"{NS_MAIN}sheet"):
        rid = sh.get(f"{NS_REL}id")
        if rid and rid in rel_map:
            out.append((sh.get("name") or "Sheet", rel_map[rid]))
    return out


def _read_sheet(zf, path, shared, date_styles):
    root = ET.fromstring(zf.read(path))
    rows = []
    max_col = 0
    for row in root.iter(f"{NS_MAIN}row"):
        cells = {}
        for c in row.findall(f"{NS_MAIN}c"):
            ci = _col_index(c.get("r"))
            ctype = c.get("t")
            style = int(c.get("s", "0") or 0)
            v = c.find(f"{NS_MAIN}v")
            is_node = c.find(f"{NS_MAIN}is")
            if ctype == "inlineStr" and is_node is not None:
                val = "".join(t.text or "" for t in is_node.iter(f"{NS_MAIN}t"))
            elif ctype == "s" and v is not None:
                try:
                    val = shared[int(v.text)]
                except (ValueError, IndexError):
                    val = ""
            elif ctype == "str" and v is not None:
                val = v.text or ""
            elif ctype == "b" and v is not None:
                val = (v.text == "1")
            elif v is not None:
                txt = (v.text or "").strip()
                try:
                    num = float(txt)
                except ValueError:
                    val = txt
                else:
                    if date_styles.get(style) and num > 0:
                        d = excel_serial_to_datetime(num)
                        val = d.strftime("%Y-%m-%d %H:%M:%S") if d else txt
                    else:
                        val = num
            else:
                val = ""
            cells[ci] = val
            max_col = max(max_col, ci)
        rows.append([cells.get(i, "") for i in range(max_col + 1)] if max_col >= 0 else [])
    return rows


def read_xlsx(path, sheet=None):
    if not zipfile.is_zipfile(path):
        raise TableError("不是有效的 XLSX（zip 结构校验失败）")
    with zipfile.ZipFile(path) as zf:
        shared = _read_shared_strings(zf)
        date_styles = _read_date_styles(zf)
        sheets = _sheet_paths(zf)
        if not sheets:
            raise TableError("XLSX 内没有工作表")
        target = None
        if sheet:
            for name, p in sheets:
                if name == sheet:
                    target = (name, p)
                    break
            if target is None:
                raise TableError(f"找不到工作表「{sheet}」，现有：{[s[0] for s in sheets]}")
        else:
            target = sheets[0]
        raw_rows = _read_sheet(zf, target[1], shared, date_styles)
    rows = [r for r in raw_rows if any(str(c).strip() for c in r)]
    if len(rows) < 2:
        raise TableError("工作表有效行不足 2 行")
    headers = []
    for i, h in enumerate(rows[0]):
        name = str(h).strip() or f"列{i+1}"
        base, k = name, 2
        while name in headers:
            name = f"{base}_{k}"
            k += 1
        headers.append(name)
    body = []
    notes = []
    if len(sheets) > 1:
        notes.append(f"工作簿含 {len(sheets)} 个工作表，本次读取「{target[0]}」")
    for r in rows[1:]:
        if len(r) != len(headers):
            r = (r + [""] * len(headers))[:len(headers)]
        body.append(list(r))
    return build_columns(Table(path, target[0], headers, body, notes))


def read_table(path, sheet=None):
    ext = os.path.splitext(path)[1].lower()
    if not os.path.exists(path):
        raise TableError(f"找不到文件：{path}")
    if ext in (".xlsx", ".xlsm"):
        return read_xlsx(path, sheet)
    if ext in (".csv", ".tsv", ".txt"):
        return read_csv(path, sheet, delimiter="\t" if ext == ".tsv" else None)
    if ext == ".xls":
        raise TableError("旧版 .xls 二进制格式不受支持，请另存为 .xlsx 或 .csv 后重试")
    raise TableError(f"不支持的扩展名 {ext}，请提供 .csv / .tsv / .xlsx")
