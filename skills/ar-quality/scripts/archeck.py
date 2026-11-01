#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交付闸门：7 项机器检查（零第三方依赖）。

检查项：
  A1 禁用词       收益承诺、操作指令、绝对化表述
  A2 免责声明     固定文本必须存在
  A3 七段完整性   结论/证据/分歧/定价/情景/风险/来源
  A4 数字可追溯   正文数字与证据台账的匹配率
  A5 时间一致性   不出现未来日期；"今日/最新"须与数据日期一致
  A6 涨跌停合规   台账中的现价须落在按板块算出的区间内
  A7 北向口径     不得出现实时净流入表述

退出码：0 = 全部通过；1 = 存在阻塞项；2 = 输入错误。

CLI:
  python archeck.py --doc 600519-diagnosis-20261029.html \
                    --evidence data/600519-evidence-20261029.json --code 600519
  python archeck.py --selftest
"""
import argparse
import json
import os
import re
import sys
from datetime import date, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
RULES_PATH = os.path.join(HERE, "..", "..", "ar-evidence", "scripts", "arrules.py")

FORBIDDEN = [
    (r"保证收益|稳赚|必赚|包赚|稳赚不赔", "收益承诺"),
    (r"必涨|一定(会)?涨|必然(突破|上涨)|必到", "确定性涨跌表述"),
    (r"无风险|零风险", "无风险表述"),
    (r"翻倍|涨一倍|翻番", "夸大收益"),
    (r"建议(立即)?买入|推荐买入|建议卖出|满仓|重仓介入|抄底|清仓出局", "操作指令"),
    (r"强烈推荐|五星推荐", "推介口吻"),
]

SECTIONS = ["结论", "证据", "分歧", "定价", "情景", "风险", "来源"]

DISCLAIMER_KEY = "不构成投资建议"

FUTURE_TOLERANCE = 1  # 允许时区导致的 1 天误差


def strip_tags(text):
    text = re.sub(r"<script.*?</script>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;|&amp;|&lt;|&gt;|&quot;", " ", text)
    return re.sub(r"\s+", " ", text)


def to_text(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        raw = fh.read()
    if path.lower().endswith((".html", ".htm")):
        return strip_tags(raw)
    return re.sub(r"[#>*|`\-]{1,}", " ", raw)


# ---------- 数字抽取与归一 ----------

NUM_RE = re.compile(r"[+\-]?\d[\d,]*\.?\d*")


def nums_in_text(text):
    """抽取候选数字：带小数、带百分号、或 4 位以上整数。

    排除两类噪音，否则任何报告都会被误判：
      * 6 位纯数字 —— 股票代码（600519、000001）
      * 19xx / 20xx —— 年份
    1-3 位整数多为序号或日期碎片，本就忽略。
    """
    out = set()
    for m in NUM_RE.finditer(text):
        token = m.group(0).strip(".,")
        if not token or token in ("-", "+", "."):
            continue
        tail = text[m.end():m.end() + 2]
        has_unit = tail[:1] in ("%", "％") or tail[:1] in ("亿", "万", "元", "倍", "家", "只")
        digits = re.sub(r"[^\d]", "", token)
        if not digits:
            continue
        if re.fullmatch(r"\d{6}", token):          # 股票代码
            continue
        if re.fullmatch(r"(19|20)\d{2}", token):    # 年份
            continue
        if "." in token or has_unit or len(digits) >= 4:
            try:
                out.add(abs(float(token.replace(",", ""))))
            except ValueError:
                continue
    return out


def flatten_evidence(ev):
    """把证据台账里的所有数值摊平成集合。支持多种结构。"""
    vals = set()

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("value", "last", "close", "prev_close", "pct_chg", "amount"):
                    try:
                        vals.add(abs(float(str(v).replace(",", ""))))
                    except (TypeError, ValueError):
                        pass
                walk(v)
        elif isinstance(node, (list, tuple)):
            for x in node:
                walk(x)
        elif isinstance(node, (int, float)):
            vals.add(abs(float(node)))
        elif isinstance(node, str):
            for m in NUM_RE.finditer(node):
                try:
                    vals.add(abs(float(m.group(0).replace(",", ""))))
                except ValueError:
                    pass

    walk(ev)
    return vals


def num_match(a, b, tol=0.011):
    if b == 0:
        return a == 0
    return abs(a - b) <= max(tol, abs(b) * 0.001)


# ---------- 七项检查 ----------

def check_a1(text):
    hits = []
    for pattern, label in FORBIDDEN:
        for m in re.finditer(pattern, text):
            hits.append({"type": label, "hit": m.group(0),
                         "context": text[max(0, m.start() - 20):m.end() + 20]})
    return {"id": "A1", "name": "禁用词", "pass": not hits, "blocking": True,
            "detail": hits[:8] if hits else "未命中"}


def check_a2(text):
    ok = DISCLAIMER_KEY in text
    return {"id": "A2", "name": "免责声明", "pass": ok, "blocking": True,
            "detail": "已找到固定免责文本" if ok else "缺少「不构成投资建议」免责声明"}


def check_a3(text):
    missing = [s for s in SECTIONS if s not in text]
    excused = []
    for s in list(missing):
        if ("%s不适用" % s) in text.replace(" ", "") or ("无%s" % s) in text:
            excused.append(s)
            missing.remove(s)
    ok = not missing
    return {"id": "A3", "name": "七段完整性", "pass": ok, "blocking": True,
            "detail": "七段齐全" if ok else "缺失段落：%s" % "、".join(missing),
            "excused": excused}


def check_a4(text, evidence, threshold=0.75):
    if evidence is None:
        return {"id": "A4", "name": "数字可追溯", "pass": True, "blocking": False,
                "skipped": True, "detail": "未提供证据台账，本项未执行（不得视为通过）"}
    doc_nums = nums_in_text(text)
    ev_nums = flatten_evidence(evidence)
    if not doc_nums:
        return {"id": "A4", "name": "数字可追溯", "pass": True, "blocking": True,
                "detail": "正文未出现可校验数字"}
    matched = [n for n in doc_nums if any(num_match(n, e) for e in ev_nums)]
    ratio = len(matched) / len(doc_nums)
    unmatched = sorted(doc_nums - set(matched), reverse=True)[:10]
    ok = ratio >= threshold
    return {"id": "A4", "name": "数字可追溯", "pass": ok, "blocking": True,
            "ratio": round(ratio, 3), "threshold": threshold,
            "doc_numbers": len(doc_nums), "matched": len(matched),
            "unmatched_sample": unmatched,
            "detail": "匹配率 %.1f%%（阈值 %.0f%%）" % (ratio * 100, threshold * 100)}


def check_a5(text, data_as_of=None, today=None):
    today = today or date.today()
    issues = []
    # 未来日期
    for m in re.finditer(r"(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})", text):
        try:
            d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            continue
        if (d - today).days > FUTURE_TOLERANCE:
            issues.append("出现未来日期 %s" % d.isoformat())
    # "今日/最新" 与数据日期
    if data_as_of:
        try:
            dao = datetime.strptime(str(data_as_of)[:10], "%Y-%m-%d").date()
        except ValueError:
            dao = None
        if dao and (today - dao).days > FUTURE_TOLERANCE:
            for kw in ("今日", "最新价", "当前价"):
                if kw in text:
                    issues.append("正文使用「%s」，但数据截至 %s（非当日），须改为具体日期"
                                  % (kw, dao.isoformat()))
                    break
    return {"id": "A5", "name": "时间一致性", "pass": not issues, "blocking": True,
            "detail": "时间口径一致" if not issues else "；".join(issues[:5])}


def _load_rules():
    sys.path.insert(0, os.path.dirname(RULES_PATH))
    import arrules  # noqa: E402
    return arrules


def check_a6(evidence, code=None, st=False):
    """台账里的现价须落在涨跌停区间内——用来抓数据源异常。"""
    if not evidence or not code:
        return {"id": "A6", "name": "涨跌停合规", "pass": True, "blocking": False,
                "skipped": True, "detail": "未提供代码或台账，本项未执行（不得视为通过）"}

    last = prev = None
    found = {}

    def walk(node):
        nonlocal last, prev
        if isinstance(node, dict):
            label = str(node.get("label", "")) + str(node.get("name", ""))
            val = node.get("value")
            if val is not None:
                try:
                    f = float(str(val).replace(",", ""))
                except ValueError:
                    f = None
                if f is not None:
                    if any(k in label for k in ("现价", "最新价", "收盘价", "last")):
                        last = f if last is None else last
                        found["last"] = f
                    if any(k in label for k in ("前收", "昨收", "prev")):
                        prev = f if prev is None else prev
                        found["prev_close"] = f
            if "last" in node and isinstance(node["last"], (int, float)):
                found.setdefault("last", float(node["last"]))
            if "prev_close" in node and isinstance(node["prev_close"], (int, float)):
                found.setdefault("prev_close", float(node["prev_close"]))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for x in node:
                walk(x)

    walk(evidence)
    last = found.get("last")
    prev = found.get("prev_close")
    if last is None or prev is None:
        return {"id": "A6", "name": "涨跌停合规", "pass": True, "blocking": False,
                "skipped": True, "detail": "台账缺少现价或前收，本项未执行（不得视为通过）"}

    try:
        rules = _load_rules()
        res = rules.check_price(code, prev, last, st=st)
    except Exception as exc:  # noqa: BLE001
        return {"id": "A6", "name": "涨跌停合规", "pass": False, "blocking": True,
                "detail": "规则校验失败：%s" % exc}

    hard = [i for i in res["issues"] if "高于" in i or "低于" in i]
    return {"id": "A6", "name": "涨跌停合规", "pass": not hard, "blocking": True,
            "checked": {"prev_close": prev, "last": last,
                        "limit_up": res["limit"]["limit_up"],
                        "limit_down": res["limit"]["limit_down"],
                        "pct_chg": res["pct_chg"]},
            "detail": "现价在涨跌停区间内" if not hard else "；".join(hard)}


def check_a7(text):
    bad = []
    for m in re.finditer(r"北向(资金)?[^。；\n]{0,12}(净流入|净买入|净卖出)", text):
        bad.append(m.group(0))
    for m in re.finditer(r"(今日|今日北向)[^。；\n]{0,6}北向", text):
        pass
    ok = not bad
    return {"id": "A7", "name": "北向口径", "pass": ok, "blocking": True,
            "detail": "未使用已停更的实时净流入口径" if ok
            else "出现实时净流入表述（2024-08 起已停止披露）：%s" % "；".join(bad[:3])}


def run(doc_path, evidence_path=None, code=None, data_as_of=None,
        threshold=0.75, today=None, st=False):
    text = to_text(doc_path)
    evidence = None
    if evidence_path:
        with open(evidence_path, "r", encoding="utf-8") as fh:
            evidence = json.load(fh)
    results = [
        check_a1(text), check_a2(text), check_a3(text),
        check_a4(text, evidence, threshold), check_a5(text, data_as_of, today),
        check_a6(evidence, code, st), check_a7(text),
    ]
    blocking = [r for r in results if (not r["pass"]) and r.get("blocking")]
    skipped = [r["id"] for r in results if r.get("skipped")]
    return {
        "doc": os.path.abspath(doc_path),
        "verdict": "打回" if blocking else "放行",
        "checks": results,
        "blocking_count": len(blocking),
        "skipped": skipped,
        "note": ("存在未执行项 %s，不得声称「全部通过」" % skipped) if skipped else "",
    }


# ---------- 自检 ----------

def selftest():
    import tempfile

    good = """<html><body><h1>测试</h1>
<p>## 结论 生意质量高。数据 1234.50 亿元。</p>
<p>## 证据 见来源。</p><p>## 分歧 无重大分歧。</p><p>## 定价 区间 1300.00 至 1600.00 元。</p>
<p>## 情景 三档。</p><p>## 风险 批价下滑。</p><p>## 来源 S1 新浪财经。</p>
<p>本内容仅供研究参考，不构成投资建议。</p></body></html>"""
    bad = """<html><body><p>## 结论 这票必涨，建议立即买入，稳赚不赔。</p>
<p>今日北向资金净流入 50 亿。</p><p>目标价 2000 元，必到。</p></body></html>"""

    tmpdir = tempfile.mkdtemp()
    gp = os.path.join(tmpdir, "good.html")
    bp = os.path.join(tmpdir, "bad.html")
    ep = os.path.join(tmpdir, "ev.json")
    with open(gp, "w", encoding="utf-8") as fh:
        fh.write(good)
    with open(bp, "w", encoding="utf-8") as fh:
        fh.write(bad)
    with open(ep, "w", encoding="utf-8") as fh:
        json.dump({"items": [
            {"label": "收盘价", "value": 1520.50},
            {"label": "前收", "value": 1500.00},
            {"label": "营收", "value": 1234.50},
            {"label": "合理区间下限", "value": 1300.00, "quality": "estimated"},
            {"label": "合理区间上限", "value": 1600.00, "quality": "estimated"},
        ]}, fh, ensure_ascii=False)

    r_good = run(gp, ep, code="600519", data_as_of=date.today().isoformat())
    r_bad = run(bp, None, code=None)
    checks = [
        ("好文档放行", r_good["verdict"] == "放行"),
        ("A1 对好文档无命中", next(c for c in r_good["checks"] if c["id"] == "A1")["pass"]),
        ("A1 抓到买入指令", not next(c for c in r_bad["checks"] if c["id"] == "A1")["pass"]),
        ("A2 好文档有免责", next(c for c in r_good["checks"] if c["id"] == "A2")["pass"]),
        ("A2 坏文档缺免责", not next(c for c in r_bad["checks"] if c["id"] == "A2")["pass"]),
        ("A3 好文档七段齐", next(c for c in r_good["checks"] if c["id"] == "A3")["pass"]),
        ("A3 坏文档缺段", not next(c for c in r_bad["checks"] if c["id"] == "A3")["pass"]),
        ("A4 执行了匹配", next(c for c in r_good["checks"] if c["id"] == "A4").get("ratio") is not None),
        ("A6 校验了涨跌停", next(c for c in r_good["checks"] if c["id"] == "A6")["pass"]),
        ("A7 抓到北向净流入", not next(c for c in r_bad["checks"] if c["id"] == "A7")["pass"]),
        ("坏文档被打回", r_bad["verdict"] == "打回"),
    ]
    failed = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print(("  PASS  " if ok else "  FAIL  ") + n)
    print("结果：%d/%d 通过" % (len(checks) - len(failed), len(checks)))
    for f in (gp, bp, ep):
        try:
            os.remove(f)
        except OSError:
            pass
    try:
        os.rmdir(tmpdir)
    except OSError:
        pass
    return 0 if not failed else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="交付闸门")
    ap.add_argument("--doc")
    ap.add_argument("--evidence")
    ap.add_argument("--code")
    ap.add_argument("--data-as-of")
    ap.add_argument("--threshold", type=float, default=0.75)
    ap.add_argument("--st", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.doc or not os.path.exists(args.doc):
        print(json.dumps({"error": "文档不存在：%s" % args.doc}, ensure_ascii=False))
        return 2
    if args.evidence and not os.path.exists(args.evidence):
        print(json.dumps({"error": "台账不存在：%s" % args.evidence}, ensure_ascii=False))
        return 2

    res = run(args.doc, args.evidence, args.code, args.data_as_of,
              args.threshold, st=args.st)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print("闸门结果：%s（阻塞项 %d）" % (res["verdict"], res["blocking_count"]))
        for c in res["checks"]:
            mark = "PASS" if c["pass"] else ("SKIP" if c.get("skipped") else "FAIL")
            print("  [%s] %s %s — %s" % (mark, c["id"], c["name"],
                                         c["detail"] if isinstance(c["detail"], str) else "见明细"))
        if res["note"]:
            print("  注意：%s" % res["note"])
    return 0 if res["verdict"] == "放行" else 1


if __name__ == "__main__":
    sys.exit(main())
