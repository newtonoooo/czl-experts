"""论文写作工具的公共模块（纯标准库，无第三方依赖）。

提供编码安全读取、问题记录、中英文字数统计、段落句子切分、统一报告输出。
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

SEVERITY_ORDER = {"BLOCKER": 0, "MAJOR": 1, "MINOR": 2}

CJK_RE = re.compile(r"[\u4e00-\u9fff]")
WESTERN_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\u2019\-]*")
SENTENCE_RE = re.compile(r"[^。！？!?;；\n]+[。！？!?;；]?")
CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)


def read_text(path) -> str:
    data = Path(path).read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gb18030", "utf-16"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


@dataclass
class Issue:
    code: str
    severity: str
    message: str
    location: str = ""
    hint: str = ""

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "location": self.location,
            "hint": self.hint,
        }


def sort_issues(issues):
    return sorted(issues, key=lambda i: (SEVERITY_ORDER.get(i.severity, 9), i.code, str(i.location)))


def count_cjk(text: str) -> int:
    return len(CJK_RE.findall(text))


def count_words(text: str) -> int:
    return len(WESTERN_WORD_RE.findall(text))


def body_words(text: str) -> int:
    """中文按字 + 西文按词，作为统一字数口径。"""
    return count_cjk(text) + count_words(text)


def strip_code_fences(text: str) -> str:
    return CODE_FENCE_RE.sub("", text)


def split_paragraphs(text: str):
    """返回 [(起始行号, 段落文本)]，跳过空行与代码块。"""
    text = strip_code_fences(text)
    result, buf, start = [], [], 1
    for idx, line in enumerate(text.splitlines(), start=1):
        if line.strip():
            if not buf:
                start = idx
            buf.append(line.strip())
        else:
            if buf:
                result.append((start, " ".join(buf)))
                buf = []
    if buf:
        result.append((start, " ".join(buf)))
    return result


def split_sentences(text: str):
    out = []
    for m in SENTENCE_RE.finditer(strip_code_fences(text)):
        s = m.group(0).strip()
        if s:
            out.append(s)
    return out


def summarize(issues) -> dict:
    counts = {"BLOCKER": 0, "MAJOR": 0, "MINOR": 0}
    for i in issues:
        counts[i.severity] = counts.get(i.severity, 0) + 1
    counts["total"] = len(issues)
    return counts


def render_human(name: str, payload: dict, human_lines, issues) -> str:
    lines = [f"=== {name} ==="]
    lines.extend(human_lines)
    counts = payload.get("summary", {})
    lines.append("")
    lines.append(
        f"问题：BLOCKER {counts.get('BLOCKER', 0)} / MAJOR {counts.get('MAJOR', 0)} / "
        f"MINOR {counts.get('MINOR', 0)}"
    )
    if issues:
        lines.append("")
        for issue in sort_issues(issues):
            loc = f" [{issue.location}]" if issue.location else ""
            lines.append(f"- {issue.severity} {issue.code}{loc} {issue.message}")
            if issue.hint:
                lines.append(f"    改法：{issue.hint}")
    else:
        lines.append("未发现问题。")
    return "\n".join(lines)


def finish(name: str, payload: dict, issues, human_lines, as_json: bool = False) -> int:
    payload = dict(payload)
    payload["tool"] = name
    payload["issues"] = [i.as_dict() for i in sort_issues(issues)]
    payload["summary"] = summarize(issues)

    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_human(name, payload, human_lines, issues))

    return 1 if payload["summary"].get("BLOCKER", 0) else 0


def setup_stdout():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
