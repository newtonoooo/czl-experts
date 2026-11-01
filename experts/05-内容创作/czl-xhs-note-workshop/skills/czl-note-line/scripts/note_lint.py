#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""note_lint.py - 小红书笔记体检

把一张笔记卡（或纯文本）过一遍机器能判定的规则：标题、封面、正文结构、
合规红线、机器味特征。输出命中项与改法，退出码供流水线判断。

用法：
    python note_lint.py <文件.md|.txt>
    python note_lint.py <文件> --json 报告.json
    python note_lint.py <文件> --strict      # 中危也阻断
    python note_lint.py <文件> --quiet       # 只输出结论行

退出码：0 = 无阻断项；1 = 有阻断项；2 = 输入错误
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

VERSION = "1.0.0"
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

LEVEL_ORDER = {"high": 0, "mid": 1, "low": 2}
LEVEL_NAME = {"high": "高危", "mid": "中危", "low": "低危"}

QUANT_RE = re.compile(
    r"(\d|[一二三四五六七八九十百千万两半])\s*"
    r"(元|块|毛|角|天|日|周|月|年|次|支|个|瓶|袋|盒|斤|克|g|ml|毫升|平|米|度|小时|分钟|点|折|倍|人|家|款|条|张|杯|碗|岁|楼|站)"
)
EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF\U00002B00-\U00002BFF]"
)
TITLE_LINE_RE = re.compile(r"^\s*(?:\d{1,2}\s*[.、)）]|[-*+•])\s*(.+?)\s*$")
BRACKET_RE = re.compile(r"[〔【\[]([^〕】\]]{0,20})[〕】\]]")

SECTION_ALIASES = {
    "标题候选": "titles",
    "标题": "titles",
    "封面": "cover",
    "正文": "body",
    "首评": "first_comment",
    "标签": "tags",
}

EMOJI_MAX_TOTAL = 5
PLACEHOLDER_MARKERS = ("待补", "〔", "【待")
LOW_VALUE_TAGS = {"日常", "分享", "生活", "记录", "随手拍", "plog", "碎片", "日记"}
CTA_WORDS = ("收藏", "点赞", "关注", "蹲", "私信", "评论区", "求同款", "留言", "码住")


def make_finding(fid, name, level, message, evidence=None, fix=""):
    return {
        "id": fid,
        "name": name,
        "level": level,
        "message": message,
        "evidence": list(evidence or []),
        "fix": fix,
    }


def load_json(name):
    path = DATA_DIR / name
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def cjk_len(text):
    """正文字数：去掉所有空白后的字符数。"""
    return len(re.sub(r"\s", "", text or ""))


def split_sections(text):
    """按二级及以下标题切分笔记卡结构。返回 (sections, plain)。"""
    sections = {}
    current = None
    buffer = []
    plain = []

    for line in text.splitlines():
        # Markdown 标题要求 # 后跟空格；这样行首的 #护手霜 会被当作标签内容，不会被误判为标题
        heading = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", line)
        if heading:
            if current:
                sections.setdefault(current, []).extend(buffer)
            buffer = []
            current = None
            title = heading.group(1).strip()
            for alias, key in SECTION_ALIASES.items():
                if title.startswith(alias):
                    current = key
                    break
            continue
        if current:
            buffer.append(line)
        else:
            plain.append(line)
    if current:
        sections.setdefault(current, []).extend(buffer)
    return sections, "\n".join(plain)


def parse_titles(lines):
    titles = []
    for line in lines:
        match = TITLE_LINE_RE.match(line)
        if not match:
            continue
        raw = BRACKET_RE.sub("", match.group(1)).strip()
        raw = raw.strip("　 \t-—")
        if raw:
            titles.append(raw)
    return titles


def parse_cover(lines):
    cover = {}
    for line in lines:
        match = re.match(r"^\s*(主标|副标|角标)\s*[:：]\s*(.+?)\s*$", line)
        if match:
            value = BRACKET_RE.sub("", match.group(2)).strip()
            cover[{"主标": "main", "副标": "sub", "角标": "corner"}[match.group(1)]] = value
    return cover


def parse_tags(lines):
    text = " ".join(lines)
    tags = re.findall(r"#([^\s#，,、]+)", text)
    if not tags:
        tags = [t for t in re.split(r"[\s，,、#]+", text) if t]
    return [t for t in tags if t]


def paragraphs_of(body):
    return [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]


def first_lines(body, n=3):
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    return lines[:n]


def has_quantity(text):
    return bool(QUANT_RE.search(text or "")) or bool(re.search(r"\d", text or ""))


# --------------------------------------------------------------------------
# 规则实现
# --------------------------------------------------------------------------


def check_titles(titles, compliance):
    findings = []
    if len(titles) < 5:
        findings.append(
            make_finding(
                "T01", "标题候选不足", "mid",
                f"只有 {len(titles)} 个标题候选，规矩是 5 个",
                [f"第 {i+1} 个：{t}" for i, t in enumerate(titles)],
                "补齐到 5 个，覆盖至少 3 类结构（留空/代价/对照/亲历/清单）。",
            )
        )

    too_long = [(t, cjk_len(t)) for t in titles if cjk_len(t) > 20]
    if too_long:
        findings.append(
            make_finding(
                "T02", "标题超长被截断", "high",
                f"{len(too_long)} 个标题超过 20 字上限",
                [f"{t}（{n} 字）" for t, n in too_long],
                "压到 20 字内。前 8 字必须能独立成立。",
            )
        )

    if titles and not any(has_quantity(t) for t in titles):
        findings.append(
            make_finding(
                "T03", "标题里没有可核对的量", "mid",
                f"{len(titles)} 个标题里没有一个是数字、价格、时长或次数",
                titles,
                "至少 3 个标题要含可核对的量，或一个越界动作（拆了、翻了 200 条评论）。",
            )
        )

    absolute_terms = []
    for group in compliance["groups"]:
        if group["id"] == "K01":
            absolute_terms = group["terms"]
    hit_absolute = []
    for title in titles:
        for term in absolute_terms:
            if term in title:
                hit_absolute.append(f"{title} ← 「{term}」")
    if hit_absolute:
        findings.append(
            make_finding(
                "T04", "标题含绝对化用语", "high",
                f"命中 {len(hit_absolute)} 处",
                hit_absolute,
                "换成可核对的比较，无法核对的直接删。",
            )
        )

    cliche = ("绝了", "必买", "YYDS", "yyds", "谁懂", "宝藏", "封神", "天花板", "真的会谢")
    hit_cliche = []
    for title in titles:
        for word in cliche:
            if word in title:
                hit_cliche.append(f"{title} ← 「{word}」")
    if len(hit_cliche) > 2:
        findings.append(
            make_finding(
                "T05", "烂大街词过多", "low",
                f"命中 {len(hit_cliche)} 处",
                hit_cliche,
                "一篇最多用一个，且不能放在主标。",
            )
        )

    self_answered = [t for t in titles if re.search(r"(就懂了|看完这篇|一看就懂|必须买|一定要买|真的能|亲测有效)", t)]
    if self_answered:
        findings.append(
            make_finding(
                "T06", "标题把结论说完了", "low",
                f"{len(self_answered)} 个标题已自答，读者不必点开",
                self_answered,
                "给前提、留空位。例如「护手霜怎么选」改成「第四支才不裂」。",
            )
        )

    seen = {}
    for title in titles:
        key = re.sub(r"[\s，,。！？!?、]", "", title)
        seen.setdefault(key, []).append(title)
    dup = [v for v in seen.values() if len(v) > 1]
    if dup:
        findings.append(
            make_finding(
                "T07", "标题重复", "mid",
                f"{len(dup)} 组重复标题",
                [v[0] for v in dup],
                "5 个候选要赌不同人群，不是同一个意思换说法。",
            )
        )
    return findings


def check_cover(cover):
    findings = []
    missing = [label for key, label in (("main", "主标"), ("sub", "副标"), ("corner", "角标")) if not cover.get(key)]
    if missing:
        findings.append(
            make_finding(
                "C01", "封面三行不全", "mid",
                f"缺：{'、'.join(missing)}",
                [],
                "主标说讲什么、副标给一个数字或动作、角标给身份或场景。",
            )
        )

    main = cover.get("main", "")
    if cjk_len(main) > 9:
        findings.append(
            make_finding(
                "C02", "主标过长", "mid",
                f"主标 {cjk_len(main)} 字，上限 9 字",
                [main],
                f"压到 9 字内。当前可考虑删掉「{main[:3]}」这类铺垫。",
            )
        )

    total = sum(cjk_len(v) for v in cover.values())
    if total > 30:
        findings.append(
            make_finding(
                "C03", "封面文字总量过多", "low",
                f"三行合计 {total} 字，超过 30 字",
                [],
                "封面上限 30 字，超过就成了 PPT。",
            )
        )

    if main and not has_quantity(main):
        findings.append(
            make_finding(
                "C04", "主标没有具体物", "low",
                "主标里既没有数字也没有量词",
                [main],
                "主标只能留一个元素时，留数字或动作，删形容词。",
            )
        )
    return findings


def check_body(body, tags, first_comment):
    findings = []
    length = cjk_len(body)

    if length == 0:
        findings.append(
            make_finding("B01", "正文缺失", "high", "没找到正文内容", [], "按 T4 模板补 `## 正文` 一节。")
        )
        return findings

    if length < 300:
        findings.append(
            make_finding(
                "B01", "正文过短", "mid",
                f"正文 {length} 字，低于 300 字",
                [],
                "要么补一个具体信息点，要么承认它是短笔记并删掉多余结构。不要注水。",
            )
        )
    if length > 1000:
        findings.append(
            make_finding(
                "B02", "正文过长", "low",
                f"正文 {length} 字，超过 1000 字",
                [],
                "完读率会掉。删掉没有新增信息的段落。",
            )
        )

    long_paras = [p[:24] + "…" for p in paragraphs_of(body) if cjk_len(p) > 150]
    if long_paras:
        findings.append(
            make_finding(
                "B03", "段落过长", "low",
                f"{len(long_paras)} 段超过 150 字",
                long_paras,
                "手机上超过 4 行就会跳读，拆成两三段。",
            )
        )

    head = " ".join(first_lines(body, 3))
    if head and not re.search(r"(\d|我|今天|上周|去年|昨天)", head):
        findings.append(
            make_finding(
                "B04", "前 3 行没有具体承诺", "low",
                "开头三行里没有数字、没有第一人称、没有时间锚点",
                first_lines(body, 3),
                "折叠前只露 3 行。开头换成结论、代价或场景，不要自我介绍。",
            )
        )

    if not re.search(r"[？?]", body) and not re.search(r"(吗|呢|多少|有没有|求|谁知道|有人|哪家)", body):
        findings.append(
            make_finding(
                "B05", "没有可回答的问题", "mid",
                "正文没有问句，也没有指向具体的提问",
                [],
                "埋一个能被具体回答的问题，例如「你们那边超市这个卖多少？我这边 39」。",
            )
        )

    emoji_count = len(EMOJI_RE.findall(body))
    if emoji_count > EMOJI_MAX_TOTAL:
        findings.append(
            make_finding(
                "B06", "emoji 过多", "low",
                f"正文 {emoji_count} 个 emoji，上限 {EMOJI_MAX_TOTAL}",
                [],
                "保留必要的一两个，其余删掉。每段开头一个 emoji 是最典型的机器味。",
            )
        )

    if len(tags) != 8:
        findings.append(
            make_finding(
                "B07", "标签数不是 8 个", "mid",
                f"当前 {len(tags)} 个",
                tags,
                "按 3 个品类词 + 3 个场景词 + 2 个长尾词配齐。",
            )
        )

    bad_tags = [t for t in tags if t in LOW_VALUE_TAGS]
    if bad_tags:
        findings.append(
            make_finding(
                "B08", "零信息标签", "low",
                f"{len(bad_tags)} 个标签不产生作用",
                bad_tags,
                "8 个位子很贵。换成品类词或长尾问句。",
            )
        )

    if not first_comment:
        findings.append(
            make_finding("B09", "缺首评", "low", "没有首评", [], "补一句 30 字内的补充或提问。")
        )

    placeholders = [marker for marker in PLACEHOLDER_MARKERS if marker in body]
    if placeholders:
        findings.append(
            make_finding(
                "B10", "占位符未填", "high",
                f"正文残留：{'、'.join(placeholders)}",
                [ln for ln in body.splitlines() if any(m in ln for m in placeholders)][:5],
                "补齐后再发布。带占位符发布等于把半成品给读者。",
            )
        )

    cta_hits = [w for w in CTA_WORDS if w in body]
    if len(cta_hits) > 3:
        findings.append(
            make_finding(
                "B11", "CTA 过多", "low",
                f"出现 {len(cta_hits)} 种引导词",
                cta_hits,
                "一篇只留一个 CTA：收藏理由 / 求同款 / 蹲后续。",
            )
        )

    if not re.search(r"\d", body):
        findings.append(
            make_finding(
                "B12", "正文没有任何数字", "mid",
                "全篇没有出现一个数字",
                [],
                "至少给一个价格、时长、数量或次数。没有量的内容无法被判断。",
            )
        )
    return findings


def check_compliance(text_pool, compliance):
    findings = []
    for group in compliance["groups"]:
        hits = []
        for term in group["terms"]:
            count = text_pool.count(term)
            if count:
                hits.append(f"{term}（{count} 次）")
        if hits:
            findings.append(
                make_finding(
                    group["id"], group["name"], group["level"],
                    f"命中 {len(hits)} 个词",
                    hits,
                    group["fix"],
                )
            )
    return findings


def check_tone(body, tone_data):
    findings = []
    for pattern in tone_data["patterns"]:
        pid = pattern["id"]
        limit = pattern["limit"]
        level = pattern["level"]

        if pid == "A06":
            paras = paragraphs_of(body)
            emoji_paras = [p[:16] for p in paras if p and EMOJI_RE.match(p[0])]
            if len(emoji_paras) > limit:
                findings.append(
                    make_finding(
                        pid, pattern["name"], level,
                        f"{len(emoji_paras)} 段以 emoji 开头，上限 {limit}",
                        emoji_paras,
                        pattern["fix"],
                    )
                )
            continue

        regex = pattern.get("regex") or ""
        if not regex:
            continue
        matches = [m.group(0) for m in re.finditer(regex, body)]
        if len(matches) > limit:
            findings.append(
                make_finding(
                    pid, pattern["name"], level,
                    f"命中 {len(matches)} 处，上限 {limit}",
                    matches[:6],
                    pattern["fix"],
                )
            )
    return findings


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------


def lint_text(text, compliance, tone_data):
    sections, plain = split_sections(text)
    has_structure = bool(sections)

    titles = parse_titles(sections.get("titles", []))
    cover = parse_cover(sections.get("cover", []))
    body = "\n".join(sections.get("body", [])).strip()
    first_comment_lines = [ln.strip() for ln in sections.get("first_comment", []) if ln.strip()]
    first_comment = first_comment_lines[0] if first_comment_lines else ""
    tags = parse_tags(sections.get("tags", []))

    if not has_structure or not body:
        body = plain.strip() or text.strip()

    findings = []
    findings.extend(check_titles(titles, compliance))
    findings.extend(check_cover(cover))
    findings.extend(check_body(body, tags, first_comment))

    text_pool = "\n".join([body, first_comment] + titles + list(cover.values()))
    findings.extend(check_compliance(text_pool, compliance))
    findings.extend(check_tone(body, tone_data))

    findings.sort(key=lambda f: (LEVEL_ORDER[f["level"]], f["id"]))

    stats = {
        "structured": has_structure,
        "chars": cjk_len(body),
        "titles": len(titles),
        "cover_lines": len(cover),
        "tags": len(tags),
        "has_first_comment": bool(first_comment),
        "paragraphs": len(paragraphs_of(body)),
    }
    summary = {
        "high": sum(1 for f in findings if f["level"] == "high"),
        "mid": sum(1 for f in findings if f["level"] == "mid"),
        "low": sum(1 for f in findings if f["level"] == "low"),
        "total": len(findings),
    }
    return findings, stats, summary


TITLE_RULE_COUNT = 7
COVER_RULE_COUNT = 4
BODY_RULE_COUNT = 12


def count_rules(compliance, tone_data):
    """规则总数 = 标题 7 + 封面 4 + 正文 12 + 合规 N + 机器味 N。"""
    return (
        TITLE_RULE_COUNT
        + COVER_RULE_COUNT
        + BODY_RULE_COUNT
        + len(compliance["groups"])
        + len(tone_data["patterns"])
    )


def render_text(path, findings, stats, summary, blocked, rule_count):
    lines = []
    lines.append(f"笔记体检 v{VERSION} · 规则 {rule_count} 条")
    lines.append(f"文件：{path}")
    lines.append("")
    if stats["structured"]:
        lines.append(
            "结构识别：标题 {titles} · 封面 {cover_lines} 行 · 正文 {chars} 字 · 标签 {tags} 个 · 首评 {fc}".format(
                titles=stats["titles"], cover_lines=stats["cover_lines"], chars=stats["chars"],
                tags=stats["tags"], fc="有" if stats["has_first_comment"] else "无",
            )
        )
    else:
        lines.append(f"结构识别：未找到笔记卡标题结构，按纯文本体检（正文 {stats['chars']} 字）")
    lines.append(
        "命中：高危 {h} · 中危 {m} · 低危 {l}".format(h=summary["high"], m=summary["mid"], l=summary["low"])
    )
    lines.append("")

    if not findings:
        lines.append("没有命中项。")
    for item in findings:
        lines.append(f"[{LEVEL_NAME[item['level']]}] {item['id']} {item['name']} · {item['message']}")
        if item["evidence"]:
            lines.append(f"       证据：{' / '.join(item['evidence'])}")
        if item["fix"]:
            lines.append(f"       改法：{item['fix']}")
        lines.append("")

    lines.append("─" * 40)
    if blocked:
        lines.append(f"结论：☒ 不放行（{summary['high']} 项高危）")
    else:
        lines.append("结论：☑ 放行" + ("" if summary["total"] == 0 else f"（{summary['mid'] + summary['low']} 项非阻断项可择要修）"))
    return "\n".join(lines)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="小红书笔记体检")
    parser.add_argument("path", help="笔记卡或纯文本文件")
    parser.add_argument("--json", metavar="FILE", help="把完整报告写成 JSON")
    parser.add_argument("--strict", action="store_true", help="中危项也阻断")
    parser.add_argument("--quiet", action="store_true", help="只输出结论行")
    args = parser.parse_args(argv)

    target = Path(args.path)
    if not target.exists():
        print(f"❌ 文件不存在：{target}", file=sys.stderr)
        return 2
    try:
        text = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = target.read_text(encoding="gbk", errors="replace")
    except OSError as exc:
        print(f"❌ 读取失败：{exc}", file=sys.stderr)
        return 2

    try:
        compliance = load_json("compliance_terms.json")
        tone_data = load_json("ai_tone_patterns.json")
    except (OSError, json.JSONDecodeError) as exc:
        print(f"❌ 规则表读取失败：{exc}", file=sys.stderr)
        return 2

    findings, stats, summary = lint_text(text, compliance, tone_data)
    rule_count = count_rules(compliance, tone_data)
    blocked = summary["high"] > 0 or (args.strict and summary["mid"] > 0)

    if args.quiet:
        verdict = "BLOCKED" if blocked else "PASS"
        print(f"{verdict}\thigh={summary['high']}\tmid={summary['mid']}\tlow={summary['low']}")
    else:
        print(render_text(target, findings, stats, summary, blocked, rule_count))

    if args.json:
        payload = {
            "tool": "note_lint",
            "version": VERSION,
            "file": str(target),
            "rule_count": rule_count,
            "stats": stats,
            "summary": summary,
            "blocked": blocked,
            "findings": findings,
        }
        Path(args.json).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
