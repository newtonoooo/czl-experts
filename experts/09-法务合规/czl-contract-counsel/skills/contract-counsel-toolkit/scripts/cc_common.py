#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
契约守门人 · 公共工具模块

设计约束（有意为之）：
- 只使用 Python 标准库，不引入 python-docx / PyPDF / requests 等第三方包，
  保证专家包在任何装有 Python 3.8+ 的机器上开箱可用，也便于商业分发时做依赖审计。
- 所有解析、切分、换算均在本地完成，不发起任何网络请求。

模块职责：
1. 文本读取与归一化（.txt/.md/.docx）
2. 条款切分（按“第X条”或序号段落）
3. 金额中文大写转换、比例合计校验
4. 统一的 JSON / Markdown 落盘
"""

import json
import re
import zipfile
from datetime import date, datetime
from pathlib import Path
from xml.sax.saxutils import unescape

__all__ = [
    "UnsupportedFormat",
    "read_text_any",
    "read_docx_text",
    "normalize",
    "split_clauses",
    "amount_to_cn",
    "extract_percentages",
    "write_json",
    "write_text",
    "ensure_dir",
    "today_str",
    "add_days",
]

CN_DIGITS = "零壹贰叁肆伍陆柒捌玖"
CN_UNITS = ["", "拾", "佰", "仟"]
CN_GROUPS = ["", "万", "亿", "万亿"]

# 条款标题正则：第一条 / 第1条 / 第十二条
CLAUSE_HEAD = re.compile(
    r"^\s*(第[一二三四五六七八九十百零〇\d]{1,6}条)\s*[、.．:：]?\s*(.{0,40})$"
)
# 常见序号标题：一、 / 1. / （一）
NUM_HEAD = re.compile(r"^\s*(?:[（(]?[一二三四五六七八九十]{1,3}[）)]|[一二三四五六七八九十]{1,3}、|\d{1,2}[.、．])\s*\S")


class UnsupportedFormat(Exception):
    """遇到当前无法解析的文件格式时抛出，由上层给出可执行的替代建议。"""


def ensure_dir(path):
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def normalize(text):
    """统一换行、去零宽字符、压缩行内多余空白，保留段落结构。"""
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\u200b-\u200f\ufeff]", "", text)
    text = re.sub(r"[ \t\u3000]+", " ", text)
    return text.strip()


def read_docx_text(path):
    """从 .docx 提取纯文本：不依赖第三方库，直接解析 OOXML。"""
    try:
        with zipfile.ZipFile(path) as zf:
            xml = zf.read("word/document.xml").decode("utf-8", "ignore")
    except KeyError:
        raise UnsupportedFormat("该 .docx 文件缺少 word/document.xml，可能已损坏或并非 Word 文档。")
    except zipfile.BadZipFile:
        raise UnsupportedFormat("该文件不是有效的 .docx（可能是改了扩展名的 .doc 或加密文件）。")

    xml = re.sub(r"<w:tab[^>]*/>", "\t", xml)
    xml = re.sub(r"<w:br[^>]*/>", "\n", xml)
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"</w:tc>", "\t", xml)
    text = re.sub(r"<[^>]+>", "", xml)
    return normalize(unescape(text))


def read_text_any(path):
    """读取合同正文。返回 (text, source_info)。"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在：{p}")
    suffix = p.suffix.lower()
    if suffix == ".docx":
        return read_docx_text(p), {"file": str(p), "format": "docx", "bytes": p.stat().st_size}
    if suffix in (".txt", ".md", ".markdown"):
        raw = p.read_bytes()
        for enc in ("utf-8", "utf-8-sig", "gb18030"):
            try:
                return normalize(raw.decode(enc)), {"file": str(p), "format": "plain", "encoding": enc}
            except UnicodeDecodeError:
                continue
        return normalize(raw.decode("utf-8", "ignore")), {"file": str(p), "format": "plain", "encoding": "utf-8/ignore"}
    if suffix in (".pdf", ".png", ".jpg", ".jpeg", ".webp", ".doc"):
        raise UnsupportedFormat(
            f"暂不支持直接解析 {suffix} 文件（本产品不带 PDF/OCR 依赖）。"
            "请用 Word/WPS 另存为 .docx，或把合同正文粘贴给我。"
        )
    raise UnsupportedFormat(f"未识别的文件类型：{suffix or '无扩展名'}，请提供 .docx / .txt / .md。")


def split_clauses(text):
    """
    把合同正文切成条款序列。
    返回 {"preamble": str, "clauses": [{"key","title","text","index"}]}
    优先按“第X条”切；若无条号，退化为按序号标题切；再无则按空行段落切。
    """
    text = normalize(text)
    lines = text.split("\n")
    preamble_parts = []
    clauses = []
    current = None

    for line in lines:
        stripped = line.strip()
        m = CLAUSE_HEAD.match(stripped)
        # 允许“第一条 合同标的”或“第一条  合同标的 内容……”同一行出现
        if m:
            if current:
                clauses.append(current)
            current = {"key": m.group(1), "title": m.group(2).strip(), "lines": []}
            if current["title"]:
                current["lines"].append(current["title"])
            continue
        if current is None:
            if stripped:
                preamble_parts.append(stripped)
        else:
            current["lines"].append(stripped)

    if current:
        clauses.append(current)

    if len(clauses) < 2:
        # 退化 1：按“一、二、三”等序号切
        clauses = []
        current = None
        for line in lines:
            stripped = line.strip()
            if NUM_HEAD.match(stripped) and len(stripped) < 60:
                if current:
                    clauses.append(current)
                current = {"key": f"段{len(clauses) + 1}", "title": stripped[:40], "lines": [stripped]}
            elif current is not None:
                current["lines"].append(stripped)
            elif stripped:
                preamble_parts.append(stripped)
        if current:
            clauses.append(current)

    if len(clauses) < 2:
        # 退化 2：按空行分段
        blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
        clauses = [
            {"key": f"段{i + 1}", "title": b.split("\n")[0][:40], "lines": b.split("\n")}
            for i, b in enumerate(blocks)
        ]
        preamble_parts = []

    out = []
    for i, c in enumerate(clauses):
        body = "\n".join([ln for ln in c["lines"] if ln]).strip()
        out.append(
            {
                "index": i + 1,
                "key": c["key"],
                "title": c["title"],
                "text": body,
                "length": len(body),
            }
        )
    return {"preamble": "\n".join(preamble_parts).strip(), "clauses": out}


def _four(n):
    """0-9999 的中文大写，不含单位“万”。"""
    units = ["仟", "佰", "拾", ""]
    digits = [n // 1000, n // 100 % 10, n // 10 % 10, n % 10]
    out = ""
    pending_zero = False
    for i, d in enumerate(digits):
        if d == 0:
            pending_zero = True
        else:
            if pending_zero and out:
                out += "零"
            out += CN_DIGITS[d] + units[i]
            pending_zero = False
    return out


def amount_to_cn(amount):
    """金额转人民币中文大写，如 200000 -> 人民币贰拾万元整。"""
    try:
        value = round(float(amount), 2)
    except (TypeError, ValueError):
        raise ValueError(f"金额无法识别：{amount!r}")
    if value < 0:
        raise ValueError("金额不能为负数，请检查输入。")

    integer = int(value)
    cents = int(round((value - integer) * 100))

    if integer == 0:
        int_str = "零"
    else:
        groups = []
        n = integer
        while n > 0:
            groups.append(n % 10000)
            n //= 10000
        parts = []
        for idx in range(len(groups) - 1, -1, -1):
            g = groups[idx]
            if g == 0:
                continue
            seg = _four(g)
            if parts and g < 1000:
                parts.append("零")
            parts.append(seg + CN_GROUPS[idx])
        int_str = "".join(parts)

    result = int_str + "元"
    if cents == 0:
        result += "整"
    else:
        jiao, fen = divmod(cents, 10)
        if jiao:
            result += CN_DIGITS[jiao] + "角"
        elif fen:
            result += "零"
        if fen:
            result += CN_DIGITS[fen] + "分"
    return "人民币" + result


def extract_percentages(text):
    """提取文本中的百分比数值（返回 float 列表，按出现顺序）。"""
    return [float(x) for x in re.findall(r"(\d{1,3}(?:\.\d+)?)\s*%", text or "")]


def write_json(path, data):
    p = Path(path)
    ensure_dir(p.parent)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(p)


def write_text(path, text):
    p = Path(path)
    ensure_dir(p.parent)
    p.write_text(text, encoding="utf-8")
    return str(p)


def today_str():
    return date.today().strftime("%Y-%m-%d")


def add_days(base, days):
    from datetime import timedelta

    if isinstance(base, str):
        base = datetime.strptime(base, "%Y-%m-%d").date()
    return (base + timedelta(days=int(days))).strftime("%Y-%m-%d")
