#!/usr/bin/env python3
"""摘要与关键词检查：字数、五要素、关键词质量、中英文数字一致性。

用法：
    python abstract_check.py 正文.md
    python abstract_check.py 正文.md --zh-min 250 --zh-max 600 --json

退出码：0 正常；1 有阻断问题；2 参数或文件错误。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import Issue, count_cjk, count_words, finish, read_text, setup_stdout  # noqa: E402

HEADING_RE = re.compile(r"^(#{1,6})\s*(.+)$")
ZH_ABSTRACT_RE = re.compile(r"^\s*(摘\s*要|内容摘要|中文摘要)\s*[:：]?\s*$")
EN_ABSTRACT_RE = re.compile(r"^\s*(abstract|ABSTRACT)\s*[:：]?\s*$", re.IGNORECASE)
INLINE_ZH_RE = re.compile(r"^\s*摘\s*要\s*[:：]\s*(.+)$")
KEYWORD_RE = re.compile(r"^\s*(关\s*键\s*词|关键字|Keywords?|KEYWORDS?)\s*[:：]\s*(.+)$", re.IGNORECASE)

ELEMENT_PATTERNS = {
    "目的": [r"本研究|本文|旨在|目的在于|目的是|考察|探讨|检验|分析"],
    "方法": [r"采用|基于|以.*为(对象|样本)|样本|问卷|访谈|实验|数据|模型|回归|编码"],
    "结果": [r"显示|表明|发现|结果显示|结果表明|呈现|差异"],
    "结论": [r"认为|说明|提示|因此|可见|可以得出|结论"],
    "边界": [r"受.*限制|局限|仅|有待|不能|不宜|谨慎"],
}
CITATION_RE = re.compile(r"\[\s*\d+\s*\]|[（(]\s*[\u4e00-\u9fff]{2,4}\s*[,，]\s*(19|20)\d{2}")
BANNED_KEYWORDS = {"研究", "分析", "对策", "思考", "初探", "浅析", "探析", "探讨", "问题"}
FORMULAIC = [r"随着[^。]{0,15}的(不断)?发展", r"越来越", r"众所周知", r"具有(重要|深远)的(理论|现实)意义"]
NUMBER_RE = re.compile(r"\d+(?:\.\d+)?\s*%?|\d+(?:\.\d+)?")


def extract_sections(text: str):
    lines = text.splitlines()
    zh, en, keywords = [], [], []
    mode = None
    for line in lines:
        stripped = line.strip()
        plain = stripped.lstrip("#").strip()
        if not plain:
            continue
        m_inline = INLINE_ZH_RE.match(plain)
        if m_inline:
            zh.append(m_inline.group(1))
            mode = "zh"
            continue
        if ZH_ABSTRACT_RE.match(plain):
            mode = "zh"
            continue
        if EN_ABSTRACT_RE.match(plain):
            mode = "en"
            continue
        m_kw = KEYWORD_RE.match(plain)
        if m_kw:
            keywords.append(m_kw.group(2).strip())
            continue
        if stripped.startswith("#"):
            # 其他标题出现即结束当前摘要区
            mode = None
            continue
        if mode == "zh":
            zh.append(plain)
        elif mode == "en":
            en.append(plain)
    return "\n".join(x for x in zh if x).strip(), "\n".join(x for x in en if x).strip(), keywords


def check_elements(zh: str, en: str):
    body = zh or en
    found, missing = {}, []
    for name, pats in ELEMENT_PATTERNS.items():
        hit = any(re.search(p, body) for p in pats)
        found[name] = hit
        if not hit:
            missing.append(name)
    return found, missing


def numbers_in(text: str):
    out = set()
    for m in NUMBER_RE.finditer(text):
        token = m.group(0).replace(" ", "")
        if "%" in token or (len(token.split(".")[0]) >= 2):
            out.add(token.rstrip("%"))
    return out


def analyze(text: str, zh_min=200, zh_max=800, en_min=120, en_max=400):
    zh, en, keywords = extract_sections(text)
    issues: list[Issue] = []
    metrics = {
        "zh_chars": count_cjk(zh),
        "en_words": count_words(en),
        "keyword_count": len([k for k in keywords if k]),
        "keywords": keywords,
    }

    if not zh and not en:
        issues.append(
            Issue(
                "AB001",
                "MAJOR",
                "未识别到摘要",
                hint="用 `摘要：……` 或 `## 摘要` 起头，工具才能检查。",
            )
        )
        return metrics, issues

    if zh and not (zh_min <= metrics["zh_chars"] <= zh_max):
        issues.append(
            Issue(
                "AB002",
                "MAJOR",
                f"中文摘要 {metrics['zh_chars']} 字，不在建议区间 {zh_min}—{zh_max} 字",
                hint="超长通常是写了背景；过短通常是缺结果与结论。"
            )
        )

    if en and not (en_min <= metrics["en_words"] <= en_max):
        issues.append(
            Issue(
                "AB003",
                "MINOR",
                f"英文摘要 {metrics['en_words']} 词，不在建议区间 {en_min}—{en_max} 词",
                hint="英文摘要不是逐句直译，按英文习惯重组可压缩 15—20%。",
            )
        )

    found, missing = check_elements(zh, en)
    metrics["elements"] = found
    if missing:
        severity = "MAJOR" if len(missing) >= 2 else "MINOR"
        issues.append(
            Issue(
                "AB004",
                severity,
                f"摘要可能缺少：{'、'.join(missing)}",
                hint="五要素：目的—方法—结果—结论—边界；结果部分必须有具体数字。",
            )
        )

    body = (zh or "") + " " + (en or "")
    if CITATION_RE.search(body):
        issues.append(
            Issue("AB005", "MINOR", "摘要中出现引用标记", hint="多数期刊与学校不允许摘要带引用，删掉或移入正文。")
        )

    for pat in FORMULAIC:
        if re.search(pat, body):
            issues.append(
                Issue("AB006", "MINOR", f"摘要含空转表达：{pat}", hint="摘要里出现背景句就删，那是引言的事。")
            )
            break

    if not keywords:
        issues.append(Issue("AB007", "MAJOR", "未识别到关键词", hint="用 `关键词：A；B；C` 单列一行，3—5 个。"))
    else:
        kws = [k.strip() for k in re.split(r"[；;，,、]\s*", keywords[0]) if k.strip()]
        metrics["keywords"] = kws
        metrics["keyword_count"] = len(kws)
        if not (3 <= len(kws) <= 8):
            issues.append(
                Issue("AB007", "MAJOR", f"关键词 {len(kws)} 个，建议 3—5 个（最多 8 个）", hint="从题目与研究问题里取。")
            )
        banned = [k for k in kws if k in BANNED_KEYWORDS]
        if banned:
            issues.append(
                Issue(
                    "AB008",
                    "MINOR",
                    f"关键词含无区分度的词：{'、'.join(banned)}",
                    hint="换成具体对象、变量或情境词，检索才搜得到。",
                )
            )

    if zh and en:
        zh_nums, en_nums = numbers_in(zh), numbers_in(en)
        if zh_nums and en_nums and not (zh_nums & en_nums):
            issues.append(
                Issue(
                    "AB009",
                    "MAJOR",
                    "中英文摘要的数字对不上",
                    hint=f"中文：{sorted(zh_nums)[:5]}；英文：{sorted(en_nums)[:5]}。样本量、比例、效应量必须一致。",
                )
            )
        elif zh_nums - en_nums:
            issues.append(
                Issue(
                    "AB010",
                    "MINOR",
                    f"英文摘要缺少中文里出现的数字：{sorted(zh_nums - en_nums)[:5]}",
                    hint="关键数字不能漏译。",
                )
            )

    return metrics, issues


def main(argv=None) -> int:
    setup_stdout()
    parser = argparse.ArgumentParser(description="摘要与关键词检查")
    parser.add_argument("file")
    parser.add_argument("--zh-min", type=int, default=200)
    parser.add_argument("--zh-max", type=int, default=800)
    parser.add_argument("--en-min", type=int, default=120)
    parser.add_argument("--en-max", type=int, default=400)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    path = Path(args.file)
    if not path.exists():
        print(f"文件不存在：{path}", file=sys.stderr)
        return 2

    metrics, issues = analyze(read_text(path), args.zh_min, args.zh_max, args.en_min, args.en_max)
    elements = metrics.get("elements", {})
    element_line = "；".join(f"{k}{'✓' if v else '✗'}" for k, v in elements.items()) if elements else "未检测"
    human = [
        f"文件：{path.name}",
        f"中文摘要：{metrics['zh_chars']} 字｜英文摘要：{metrics['en_words']} 词",
        f"五要素：{element_line}",
        f"关键词：{metrics['keyword_count']} 个" + (f"（{'；'.join(metrics['keywords'])}）" if metrics.get("keywords") else ""),
    ]
    return finish("abstract_check", metrics, issues, human, args.json)


if __name__ == "__main__":
    sys.exit(main())
