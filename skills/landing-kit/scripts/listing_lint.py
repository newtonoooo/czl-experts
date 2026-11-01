#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""listing_lint.py — 跨境电商 Listing 文案体检

按平台规则档案（references/listing-profiles.json）检查标题长度、禁词、堆砌、
全大写、联系方式、单位制、五点条数与长度等，给出 error / warn / info 三级结果与改法。

用法：
    python listing_lint.py --profile amazon_us --input listing.json
    python listing_lint.py --profile amazon_us --brand "AquaCup" \
        --title "AquaCup Collapsible Water Bottle 750ml" --bullet "..." --bullet "..."
    python listing_lint.py --list
    python listing_lint.py --selftest

error 数量决定退出码：0 = 无 error（可交付），1 = 有 error（必须改）。
"""

import argparse
import json
import os
import re
import sys
import unicodedata

STOPWORDS = set("""a an the and or for with of to in on at by from your you our this that
is are be as it its all not no more most can will just than then""".split())

CONTACT_PATTERNS = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "邮箱"),
    (re.compile(r"(?:https?://|www\.)\S+", re.I), "网址"),
    (re.compile(r"(?:\+?\d[\d\s\-()]{6,}\d)"), "电话号码"),
    (re.compile(r"(whatsapp|wechat|weixin|微信|line\s*id|telegram|加\s*v|扫码)", re.I), "社交账号/站外引流"),
]
PRICE_PATTERNS = [
    re.compile(r"[$€£¥]\s?\d"),
    re.compile(r"\b\d+(\.\d+)?\s?(usd|eur|gbp|jpy|rmb|cny)\b", re.I),
]


def profiles_path():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "references", "listing-profiles.json"))


def load_profiles(path=None):
    with open(path or profiles_path(), "r", encoding="utf-8") as f:
        return json.load(f)


def has_emoji(text):
    for ch in text:
        cp = ord(ch)
        if 0x1F000 <= cp <= 0x1FAFF or 0x2600 <= cp <= 0x27BF or cp == 0xFE0F:
            return True
    return False


def words(text):
    return [w for w in re.split(r"[^\w']+", text.lower()) if w]


def find_claims(text, banned):
    low = text.lower()
    hits = []
    for term in banned:
        t = term.lower()
        if not t:
            continue
        if re.search(r"[a-z0-9]", t):
            if re.search(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])", low):
                hits.append(term)
        else:
            if t in low:
                hits.append(term)
    return hits


def lint(doc, profile, advice):
    res = []

    def add(sev, code, where, msg, extra=""):
        res.append({"severity": sev, "code": code, "where": where,
                    "message": msg, "advice": advice.get(code, extra)})

    title = doc.get("title", "") or ""
    bullets = doc.get("bullets", []) or []
    desc = doc.get("description", "") or ""
    brand = doc.get("brand", "") or ""
    keywords = doc.get("keywords", []) or []

    # 标题长度
    tmax = profile.get("title_max", 0)
    if tmax and len(title) > tmax:
        add("error", "TITLE_LEN", "标题", "标题 %d 字符，超过平台上限 %d。" % (len(title), tmax))

    # 表情符号
    for where, text in (("标题", title), ("五点", " ".join(bullets)), ("描述", desc)):
        if text and has_emoji(text):
            add("error" if where == "标题" else "warn", "TITLE_EMOJI", where,
                "%s 中含表情符号。" % where)

    # 全大写
    tw = [w for w in words(title) if len(w) >= 4]
    caps = [w for w in tw if w.isupper() and any(c.isalpha() for c in w)]
    if len(tw) >= 4 and len(caps) / len(tw) > 0.30 and len(caps) >= 2:
        add("warn", "TITLE_CAPS", "标题",
            "全大写词 %d/%d（%s），平台易判低质。" % (len(caps), len(tw), ", ".join(caps[:4])))

    # 同词根堆砌（标题）
    counts = {}
    for w in words(title):
        if len(w) >= 4 and w not in STOPWORDS:
            counts[w] = counts.get(w, 0) + 1
    repeat = {w: c for w, c in counts.items() if c > 2}
    if repeat:
        detail = "，".join("%s×%d" % (w, c) for w, c in sorted(repeat.items(), key=lambda x: -x[1]))
        add("warn", "TITLE_REPEAT", "标题", "同一词根出现超过 2 次：%s。" % detail)

    # 禁词
    banned = profile.get("banned", [])
    for where, text in (("标题", title), ("五点", " ".join(bullets)), ("描述", desc)):
        for term in find_claims(text, banned):
            sev = "warn" if where == "描述" else "error"
            add(sev, "CLAIM_BANNED", where, "命中禁词「%s」（%s）。" % (term, where))

    # 联系方式
    for where, text in (("标题", title), ("五点", " ".join(bullets)), ("描述", desc)):
        for pat, label in CONTACT_PATTERNS:
            m = pat.search(text)
            if m:
                add("error", "CONTACT", where, "%s中出现%s：%s" % (where, label, m.group(0)[:40]))

    # 五点条数与长度
    bcount = profile.get("bullet_count", 0)
    if bcount and len(bullets) != bcount:
        add("warn", "BULLET_COUNT", "五点", "五点 %d 条，平台建议 %d 条。" % (len(bullets), bcount))
    bmax = profile.get("bullet_max", 0)
    if bmax:
        for i, b in enumerate(bullets, 1):
            if len(b) > bmax:
                add("warn", "BULLET_LEN", "五点第%d条" % i,
                    "%d 字符，超过 %d。" % (len(b), bmax))

    # 描述长度
    dmax = profile.get("desc_max", 0)
    if dmax and len(desc) > dmax:
        add("warn", "DESC_LEN", "描述", "描述 %d 字符，超过 %d。" % (len(desc), dmax))

    # 描述堆砌
    dc = {}
    for w in words(desc):
        if len(w) >= 4 and w not in STOPWORDS:
            dc[w] = dc.get(w, 0) + 1
    over = {w: c for w, c in dc.items() if c > 6}
    if over:
        detail = "，".join("%s×%d" % (w, c) for w, c in sorted(over.items(), key=lambda x: -x[1])[:5])
        add("warn", "STUFFING_DESC", "描述", "描述中词根重复过多：%s。" % detail)

    # 单位制
    unit = profile.get("unit_system")
    blob = " ".join([title, " ".join(bullets), desc])
    if unit == "imperial":
        if re.search(r"\b\d+\s?(cm|mm|kg|ml|l)\b", blob, re.I) and not re.search(
                r"\b(inch|inches|in\.|lb|lbs|oz|fl oz|feet|ft)\b", blob, re.I):
            add("info", "UNIT_MISSING", "全文", "出现公制单位但没给英制，美国站建议双标。")
    elif unit == "metric":
        if re.search(r"\b\d+\s?(inch|inches|lb|lbs|oz)\b", blob, re.I) and not re.search(
                r"\b(cm|mm|kg|ml|l)\b", blob, re.I):
            add("info", "UNIT_MISSING", "全文", "出现英制单位但没给公制，欧洲/日本站建议双标。")

    # 标题含价格
    for pat in PRICE_PATTERNS:
        if pat.search(title):
            add("warn", "PRICE_IN_TITLE", "标题", "标题中出现价格或币种符号。")
            break

    # 品牌位置
    bn = profile.get("brand_first_words", 0)
    if brand and bn:
        head = " ".join(title.split()[:bn]).lower()
        if brand.lower() not in head:
            add("warn", "BRAND_POS", "标题", "品牌「%s」未出现在前 %d 个词内。" % (brand, bn))

    # 核心词覆盖
    if keywords:
        tl = title.lower()
        body = (title + " " + " ".join(bullets) + " " + desc).lower()
        miss_t, miss_b = [], []
        for k in keywords:
            k = str(k).strip()
            if not k:
                continue
            if k.lower() not in tl:
                miss_t.append(k)
            if k.lower() not in body:
                miss_b.append(k)
        if miss_t:
            add("info", "KEYWORD_MISS", "标题", "以下核心词未进标题：%s。" % "、".join(miss_t[:6]))
        if miss_b:
            add("info", "KEYWORD_MISS", "全文", "以下核心词全文未出现：%s。" % "、".join(miss_b[:6]))

    return res


def summarize(res, profile):
    errs = [r for r in res if r["severity"] == "error"]
    warns = [r for r in res if r["severity"] == "warn"]
    infos = [r for r in res if r["severity"] == "info"]
    score = max(0, 100 - 10 * len(errs) - 3 * len(warns))
    return errs, warns, infos, score


def render(doc, profile, res, advice):
    errs, warns, infos, score = summarize(res, profile)
    L = []
    L.append("# Listing 体检 · %s" % profile.get("label", ""))
    L.append("")
    L.append("字数：标题 %d 字符（上限 %s）｜五点 %d 条（建议 %s）｜描述 %d 字符（上限 %s）"
             % (len(doc.get("title", "")), profile.get("title_max", "-"),
                len(doc.get("bullets", []) or []), profile.get("bullet_count", "-"),
                len(doc.get("description", "")), profile.get("desc_max", "-")))
    L.append("")
    L.append("结果：error %d ｜ warn %d ｜ info %d ｜ 得分 %d" % (len(errs), len(warns), len(infos), score))
    L.append("")
    if not res:
        L.append("未发现问题。仍需母语审校三处：标题、卖点首句、场景描述。")
        return "\n".join(L)
    L.append("| 级别 | 位置 | 问题 | 怎么改 |")
    L.append("|---|---|---|---|")
    tag = {"error": "error", "warn": "warn", "info": "info"}
    for r in errs + warns + infos:
        L.append("| %s | %s | %s | %s |" % (tag[r["severity"]], r["where"],
                                            r["message"].replace("|", "/"),
                                            (r["advice"] or "").replace("|", "/")))
    L.append("")
    if errs:
        L.append("**不可交付**：error 必须清零后重跑。")
    else:
        L.append("**可交付（warn 逐条说明为什么可以留）**。")
    L.append("")
    L.append("> 字数上限与禁词为 %s 口径，以平台后台当期限制为准。" % profile.get("locale", ""))
    return "\n".join(L)


def selftest():
    data = load_profiles()
    prof = data["profiles"]["amazon_us"]
    adv = data["advice"]
    ok = 0

    doc = {"brand": "AquaCup", "title": "AquaCup Collapsible Water Bottle 750ml Silicone",
           "bullets": ["a"] * 5, "description": "Reusable bottle.", "keywords": ["collapsible bottle"]}
    res = lint(doc, prof, adv)
    assert not [r for r in res if r["severity"] == "error"], res
    ok += 1

    bad = {"brand": "AquaCup", "title": "BEST Water Bottle 100% Safe Chair Cup Bottle Bottle Bottle",
           "bullets": ["contact me at a@b.com"] * 5, "description": "x"}
    res2 = lint(bad, prof, adv)
    codes = {r["code"] for r in res2 if r["severity"] == "error"}
    assert "CONTACT" in codes
    assert "CLAIM_BANNED" in codes
    ok += 1

    long_title = dict(doc)
    long_title["title"] = "A" * 220
    res3 = lint(long_title, prof, adv)
    assert any(r["code"] == "TITLE_LEN" for r in res3)
    ok += 1

    emo = dict(doc)
    emo["title"] = "AquaCup Bottle 🔥 750ml"
    res4 = lint(emo, prof, adv)
    assert any(r["code"] == "TITLE_EMOJI" for r in res4)
    ok += 1

    de = data["profiles"]["amazon_de"]
    de_doc = {"brand": "AquaCup", "title": "AquaCup Flasche beste Qualität 750 ml",
              "bullets": ["x"] * 5, "description": "y"}
    res5 = lint(de_doc, de, adv)
    assert any(r["code"] == "CLAIM_BANNED" and "beste" in r["message"] for r in res5)
    ok += 1

    rep = dict(doc)
    rep["title"] = "AquaCup bottle bottle bottle bottle 750ml"
    res6 = lint(rep, prof, adv)
    assert any(r["code"] == "TITLE_REPEAT" for r in res6)
    ok += 1

    errs, warns, infos, score = summarize([], prof)
    assert score == 100
    ok += 1

    print("selftest passed: %d checks" % ok)
    return 0


def main():
    ap = argparse.ArgumentParser(description="跨境电商 Listing 文案体检")
    ap.add_argument("--profile", default="amazon_us", help="平台档案 id")
    ap.add_argument("--input", help="JSON 文稿：{brand,title,bullets[],description,keywords[]}")
    ap.add_argument("--title")
    ap.add_argument("--bullet", action="append", default=[])
    ap.add_argument("--desc")
    ap.add_argument("--brand")
    ap.add_argument("--keyword", action="append", default=[])
    ap.add_argument("--profiles", help="自定义档案文件")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    data = load_profiles(args.profiles)

    if args.list:
        for k, v in data["profiles"].items():
            print("  %-14s %s（标题上限 %s）" % (k, v["label"], v.get("title_max")))
        return 0

    prof = data["profiles"].get(args.profile)
    if not prof:
        print("ERROR: 未知平台档案 %s，可用：%s" % (args.profile, ", ".join(data["profiles"])),
              file=sys.stderr)
        return 2

    if args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            doc = json.load(f)
    else:
        doc = {"brand": args.brand or "", "title": args.title or "",
               "bullets": args.bullet, "description": args.desc or "",
               "keywords": args.keyword}
    if not doc.get("title"):
        print("ERROR: 缺少标题（--title 或 --input 里的 title）", file=sys.stderr)
        return 2

    res = lint(doc, prof, data["advice"])
    errs, warns, infos, score = summarize(res, prof)

    if args.json:
        print(json.dumps({"profile": args.profile, "score": score,
                          "errors": len(errs), "warnings": len(warns),
                          "findings": res, "lengths": {
                              "title": len(doc.get("title", "")),
                              "bullets": len(doc.get("bullets", []) or []),
                              "description": len(doc.get("description", ""))}},
                         ensure_ascii=False, indent=2))
    else:
        print(render(doc, prof, res, data["advice"]))
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
