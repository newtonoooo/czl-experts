#!/usr/bin/env python3
"""参考文献转换与检查：GB/T 7714 ↔ APA ↔ MLA ↔ IEEE，另查缺项与重复。

用法：
    python cite_format.py 参考文献.md                # 检查
    python cite_format.py 参考文献.md --to apa       # 转成 APA
    python cite_format.py 参考文献.md --to gb7714 --json

说明：转换只做**结构与标点**的重排。中文姓名转拼音、外文期刊名缩写等需要人工处理，
工具会逐条标注 `姓名/刊名需人工调整`，不要直接把输出当定稿。

退出码：0 无阻断问题；1 存在阻断问题（同号重复/无法解析）；2 参数或文件错误。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import Issue, finish, read_text, setup_stdout  # noqa: E402

ENTRY_START_RE = re.compile(r"^\s*(?:\[(\d+)\]|(\d+)\s*[.、)．]\s*)\s*(.+)$")
ENTRY_NUM_RE = re.compile(r"^\s*(?:\[(\d+)\]|(\d+)\s*[.、)．]\s*)\s*\S")
TYPE_RE = re.compile(r"\[([A-Z]{1,2}(?:/[A-Z]{2})?)\]")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
DOI_RE = re.compile(r"10\.\d{4,9}/\S+")
URL_RE = re.compile(r"https?://\S+|www\.\S+")
CITE_DATE_RE = re.compile(r"\[\s*(20\d{2}|19\d{2})\s*[-–—/]\s*\d{1,2}\s*[-–—/]\s*\d{1,2}\s*\]")
YEAR_RE = re.compile(r"(20\d{2}|19\d{2})")

JOURNAL_RE = re.compile(
    r"(?P<journal>[^,，]+?)[,，]\s*(?P<year>20\d{2}|19\d{2})"
    r"(?:\s*[,，]\s*(?P<volume>\d+))?"
    r"(?:\s*[(（]\s*(?P<issue>[^)）]+?)\s*[)）])?"
    r"\s*[:：]\s*(?P<pages>\d+\s*[-–—~]\s*\d+|\d+)"
)
BOOK_RE = re.compile(
    r"(?P<place>[^:：,.，]+?)\s*[:：]\s*(?P<publisher>[^,，.]+?)"
    r"\s*[,，]\s*(?P<year>20\d{2}|19\d{2})"
    r"(?:\s*[:：]\s*(?P<pages>[0-9\-–—~]+))?"
)
THESIS_RE = re.compile(
    r"(?P<place>[^:：,.，]+?)\s*[:：]\s*(?P<school>[^,，.]+?)\s*[,，]\s*(?P<year>20\d{2}|19\d{2})"
)


def parse_entries(text: str):
    """切分参考文献条目。

    若文中存在编号条目，则编号之前的正文（摘要、章节内容）会被跳过，避免整篇被当成一条；
    没有编号时，只保留含文献类型标识的段落。
    """
    lines = text.splitlines()
    start = 0
    for idx, line in enumerate(lines):
        if ENTRY_NUM_RE.match(line):
            start = idx
            break

    entries, current = [], None
    for idx in range(start, len(lines)):
        line = lines[idx]
        if not line.strip() or line.strip().startswith("#"):
            continue
        m = ENTRY_START_RE.match(line)
        if m:
            if current:
                entries.append(current)
            number = m.group(1) or m.group(2)
            current = {"number": int(number) if number else None, "raw": m.group(3).strip(), "line": idx + 1}
        elif current is not None:
            current["raw"] = (current["raw"] + " " + line.strip()).strip()
    if current:
        entries.append(current)

    return [e for e in entries if e["number"] is not None or TYPE_RE.search(e["raw"])]


def split_fields(raw: str):
    """拆成 作者 / 题名 / 类型标识 / 剩余部分。"""
    marker_match = TYPE_RE.search(raw)
    marker = marker_match.group(1) if marker_match else ""
    head = raw[: marker_match.start()] if marker_match else raw
    tail = raw[marker_match.end():] if marker_match else ""
    parts = re.split(r"[.．]\s*", head, maxsplit=1)
    authors = parts[0].strip()
    title = parts[1].strip() if len(parts) > 1 else ""
    tail = tail.strip().lstrip(".．").strip()
    return authors, title, marker, tail


def parse_detail(marker: str, tail: str) -> dict:
    detail = {"journal": "", "year": "", "volume": "", "issue": "", "pages": "",
              "place": "", "publisher": "", "school": "", "url": "", "cite_date": "", "raw_tail": tail}
    year_match = YEAR_RE.search(tail)
    if year_match:
        detail["year"] = year_match.group(1)
    if marker == "J":
        m = JOURNAL_RE.search(tail)
        if m:
            detail.update({k: (m.group(k) or "") for k in ("journal", "volume", "issue", "pages")})
            detail["year"] = m.group("year")
    elif marker == "M":
        m = BOOK_RE.search(tail)
        if m:
            detail.update({k: (m.group(k) or "") for k in ("place", "publisher", "pages")})
            detail["year"] = m.group("year")
    elif marker == "D":
        m = THESIS_RE.search(tail)
        if m:
            detail.update({k: (m.group(k) or "") for k in ("place", "school")})
            detail["year"] = m.group("year")
    elif marker and (marker.startswith("EB") or marker.endswith("/OL")):
        url = URL_RE.search(tail)
        detail["url"] = url.group(0).rstrip(".") if url else ""
        cd = CITE_DATE_RE.search(tail)
        detail["cite_date"] = cd.group(0) if cd else ""
    return detail


def format_authors(authors: str, style: str) -> str:
    names = [n.strip() for n in re.split(r"[,，、;；]", authors) if n.strip()]
    if not names:
        return authors
    if style == "gb7714":
        return ", ".join(names)
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]}, & {names[1]}" if style == "apa" else f"{names[0]}, and {names[1]}"
    head = ", ".join(names[:-1])
    tail = f"& {names[-1]}" if style == "apa" else f"and {names[-1]}"
    return f"{head}, {tail}"


def render(entry: dict, style: str) -> tuple[str, list[str]]:
    authors, title, marker, tail = split_fields(entry["raw"])
    detail = parse_detail(marker, tail)
    notes = []
    if CJK_RE.search(authors):
        notes.append("姓名需人工转拼音并调序")
    if CJK_RE.search(detail.get("journal", "")):
        notes.append("刊名需人工译为英文或按刊物缩写表处理")

    a = format_authors(authors, style)
    year = detail["year"] or "〔待补：年份〕"
    vol, iss, pages = detail["volume"], detail["issue"], detail["pages"]
    journal = detail["journal"] or "〔待补：刊名〕"

    if style == "gb7714":
        body = tail.rstrip()
        if not body.endswith("."):
            body += "."
        return f"{authors}. {title}[{marker}]. {body}", notes

    if style == "apa":
        if marker == "J":
            vol_part = f"*{journal}*"
            if vol:
                vol_part += f", *{vol}*"
            if iss:
                vol_part += f"({iss})"
            page_part = f", {pages}" if pages else ""
            out = f"{a} ({year}). {title}. {vol_part}{page_part}."
        elif marker == "M":
            out = f"{a} ({year}). *{title}*. {detail['place'] or '〔待补：出版地〕'}: {detail['publisher'] or '〔待补：出版者〕'}."
        elif marker == "D":
            out = f"{a} ({year}). *{title}* [Doctoral dissertation]. {detail['school'] or '〔待补：学校〕'}, {detail['place'] or '〔待补：地点〕'}."
        else:
            out = f"{a} ({year}). {title}. {detail['url'] or tail}."
        doi = DOI_RE.search(entry["raw"])
        if doi:
            out += f" https://doi.org/{doi.group(0).split('doi:')[-1].strip()}"
        return out, notes

    if style == "mla":
        if marker == "J":
            bits = [f"*{journal}*"]
            if vol:
                bits.append(f"vol. {vol}")
            if iss:
                bits.append(f"no. {iss}")
            bits.append(year)
            if pages:
                bits.append(f"pp. {pages}")
            return f'{a}. "{title}." {", ".join(bits)}.', notes
        return f'{a}. "{title}." {detail["place"] or "〔待补：出版地〕"}: {detail["publisher"] or "〔待补：出版者〕"}, {year}.', notes

    if style == "ieee":
        if marker == "J":
            bits = [f'"{title},"', f"*{journal}*"]
            if vol:
                bits.append(f"vol. {vol}")
            if iss:
                bits.append(f"no. {iss}")
            if pages:
                bits.append(f"pp. {pages}")
            bits.append(year)
            return f"{a}, {' '.join(bits)}.", notes
        return f'{a}, "{title}," {detail["place"] or "〔待补：出版地〕"}: {detail["publisher"] or "〔待补：出版者〕"}, {year}.', notes

    return entry["raw"], notes


def check(entries) -> list[Issue]:
    issues: list[Issue] = []
    seen_numbers: dict[int, int] = {}
    seen_titles: dict[str, int] = {}

    for pos, entry in enumerate(entries):
        raw, loc = entry["raw"], f"第{entry['line']}行"
        authors, title, marker, tail = split_fields(raw)

        if entry["number"] is not None:
            if entry["number"] in seen_numbers:
                issues.append(
                    Issue(
                        "CF001",
                        "BLOCKER",
                        f"编号 [{entry['number']}] 重复出现（另一处第 {seen_numbers[entry['number']]} 行）",
                        loc,
                        "同号重复会让正文引用无法定位，必须合并或重排。",
                    )
                )
            else:
                seen_numbers[entry["number"]] = entry["line"]
            expected = pos + 1
            if entry["number"] != expected:
                issues.append(
                    Issue(
                        "CF002",
                        "MAJOR",
                        f"编号不连续：第 {pos + 1} 条为 [{entry['number']}]，应为 [{expected}]",
                        loc,
                        "正文引用编号需同步修正。",
                    )
                )

        if not marker:
            issues.append(Issue("CF003", "MAJOR", f"缺文献类型标识（如 [J] [M] [D]）：{raw[:36]}…", loc, "按国标补标识。"))
        else:
            detail = parse_detail(marker, tail)
            if marker == "J":
                if not detail["year"]:
                    issues.append(Issue("CF004", "MAJOR", "期刊论文缺年份", loc, "补出版年。"))
                if not detail["pages"]:
                    issues.append(Issue("CF004", "MAJOR", "期刊论文缺起止页码", loc, "补 `: 起页-止页`。"))
            elif marker == "M":
                if not detail["place"] or not detail["publisher"]:
                    issues.append(Issue("CF005", "MAJOR", "专著缺出版地或出版者", loc, "形如 `北京: 高等教育出版社`。"))
                if not detail["year"]:
                    issues.append(Issue("CF005", "MAJOR", "专著缺出版年", loc, "补出版年。"))
            elif marker == "D":
                if not detail["school"]:
                    issues.append(Issue("CF006", "MAJOR", "学位论文缺保存单位", loc, "形如 `上海: 华东师范大学, 2021.`"))
                if not detail["year"]:
                    issues.append(Issue("CF006", "MAJOR", "学位论文缺年份", loc, "补授予年份。"))
            elif marker.startswith("EB") or marker.endswith("/OL"):
                if not detail["cite_date"]:
                    issues.append(Issue("CF007", "MAJOR", "电子资源缺引用日期", loc, "形如 `[2024-03-12]`。"))
                if not detail["url"]:
                    issues.append(Issue("CF007", "MAJOR", "电子资源缺 URL", loc, "补完整链接。"))

        if not raw.rstrip().endswith((".", "。", "/")):
            issues.append(Issue("CF008", "MINOR", "条目未以句点结尾", loc, "补句点。"))

        key = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]", "", title).lower()
        if len(key) >= 6:
            if key in seen_titles:
                issues.append(
                    Issue("CF009", "MAJOR", f"疑似重复条目：与第 {seen_titles[key]} 行题名相同", loc, "合并为一条并统一正文引用。")
                )
            else:
                seen_titles[key] = entry["line"]

    return issues


def main(argv=None) -> int:
    setup_stdout()
    parser = argparse.ArgumentParser(description="参考文献转换与检查")
    parser.add_argument("file")
    parser.add_argument("--to", choices=["gb7714", "apa", "mla", "ieee"], default="", help="转换目标格式")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    path = Path(args.file)
    if not path.exists():
        print(f"文件不存在：{path}", file=sys.stderr)
        return 2

    text = read_text(path)
    entries = parse_entries(text)
    if not entries:
        print("未识别到参考文献条目：请确认每条以 [1] 或 1. 开头。", file=sys.stderr)
        return 2

    issues = check(entries)
    payload = {"file": str(path), "entry_count": len(entries), "style": args.to or "check"}
    human = [f"文件：{path.name}", f"条目：{len(entries)} 条"]

    if args.to:
        lines, manual = [], []
        for i, entry in enumerate(entries, start=1):
            rendered, notes = render(entry, args.to)
            num = entry["number"] if entry["number"] is not None else i
            lines.append(f"[{num}] {rendered}")
            if notes:
                manual.append(f"[{num}] " + "；".join(notes))
        payload["converted"] = lines
        payload["manual_notes"] = manual
        human.append(f"目标格式：{args.to}")
        human.append("")
        human.extend(lines)
        if manual:
            human.append("")
            human.append(f"需人工调整（{len(manual)} 条）：")
            human.extend(f"- {m}" for m in manual)
    else:
        human.append("提示：只查条目自身结构，正文引用与文献表的对应关系需人工核对。")

    return finish("cite_format", payload, issues, human, args.json)


if __name__ == "__main__":
    sys.exit(main())
