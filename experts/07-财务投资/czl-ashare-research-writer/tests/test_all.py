#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""端到端测试。

三层：
  T1 单元自检   逐个脚本跑内置 self-test
  T2 离线链路   固定夹具 -> 渲染 -> 闸门（正例放行 / 反例打回）
  T3 真实链路   联网取 600519 行情与 K 线 -> 指标 -> 出稿 -> 闸门

运行：
  python tests/test_all.py            # T1 + T2，T3 自动尝试
  python tests/test_all.py --no-live  # 只跑 T1 + T2
结果标记：PASS / FAIL / SKIP（SKIP 不算通过）
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import date, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable

RULES = os.path.join(ROOT, "skills", "ar-evidence", "scripts", "arrules.py")
FETCH = os.path.join(ROOT, "skills", "ar-evidence", "scripts", "arfetch.py")
IND = os.path.join(ROOT, "skills", "ar-evidence", "scripts", "arindicators.py")
VALUE = os.path.join(ROOT, "skills", "ar-value", "scripts", "arvalue.py")
REPORT = os.path.join(ROOT, "skills", "ar-thesis", "scripts", "arreport.py")
CHECK = os.path.join(ROOT, "skills", "ar-quality", "scripts", "archeck.py")
POSITION = os.path.join(ROOT, "skills", "ar-position", "scripts", "arposition.py")

RESULTS = []


def record(name, status, detail=""):
    RESULTS.append({"name": name, "status": status, "detail": detail})
    icon = {"PASS": "PASS", "FAIL": "FAIL", "SKIP": "SKIP"}[status]
    print("  [%s] %s%s" % (icon, name, (" — " + detail) if detail else ""))


def run_script(path, args, timeout=90):
    proc = subprocess.run([PY, path] + args, capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          timeout=timeout, cwd=ROOT)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


# ---------------- T1 单元自检 ----------------

def t1_unit():
    print("\n[T1] 脚本单元自检")
    cases = [
        ("arrules 规则校验", RULES, ["check", "--code", "600519",
                                     "--prev-close", "1500", "--price", "1650"]),
        ("arfetch 解析器", FETCH, ["parse-selftest"]),
        ("arindicators 指标", IND, ["--selftest"]),
        ("arvalue 估值", VALUE, ["selftest"]),
        ("arreport 渲染", REPORT, ["--selftest"]),
        ("archeck 闸门", CHECK, ["--selftest"]),
        ("arposition 持仓", POSITION, ["selftest"]),
    ]
    for name, path, sargs in cases:
        if not os.path.exists(path):
            record(name, "FAIL", "脚本不存在：%s" % path)
            continue
        code, out = run_script(path, sargs)
        last = [l for l in out.strip().splitlines() if l.strip()][-2:]
        if code == 0 and "FAIL" not in out:
            tail = [l for l in last if "通过" in l or '"ok"' in l]
            record(name, "PASS", (tail[0].strip() if tail else "exit=0"))
        else:
            record(name, "FAIL", " | ".join(x.strip() for x in last))


# ---------------- T2 离线链路 ----------------

def _fixture_draft():
    return {
        "code": "600519.SH", "name": "贵州茅台", "task": "diagnosis",
        "date": "2026-10-29", "data_as_of": "2026-10-29",
        "title": "贵州茅台（600519.SH）个股诊断",
        "verdict": {
            "text": "生意质量高，但增速已换挡，当前价隐含的假设偏乐观。",
            "confidence": "中",
            "falsify": "若下一季度预收款同比转正且批价站稳 2200 元，本判断失效。",
        },
        "key_numbers": [
            {"label": "收盘价", "value": "1520.50", "note": "元，2026-10-29"},
            {"label": "涨跌幅", "value": "+1.37", "note": "%"},
        ],
        "series": {"close": [1470, 1480, 1495, 1500, 1510, 1520.5],
                   "caption": "收盘价走势（最近 6 个交易日）"},
        "sections": [
            {"title": "证据", "md": "### 财务\n- 前三季度营收 1234.50 亿元[事实]\n"
                                    "- 毛利率 91.20%[事实]\n\n"
                                    "| 指标 | 数值 | 口径 |\n|---|---|---|\n"
                                    "| 毛利率 | 91.20% | 前三季度 |\n| 净利率 | 52.40% | 前三季度 |"},
            {"title": "分歧", "md": "卖方一致预期增速 18%，我按 **产能节奏** 推算为 11%。"},
            {"title": "定价", "md": "相对估值给出 1300.00 至 1600.00 元区间，假设表见附录。"},
            {"title": "情景", "md": "1. 乐观：批价站稳 2400 元\n2. 中性：维持现状\n3. 悲观：预收款转负"},
            {"title": "风险", "md": "> 批价下行会同时压制渠道利润与提价空间。"},
        ],
        "sources": [
            {"id": "S1", "name": "新浪财经 hq.sinajs.cn", "as_of": "2026-10-29 10:43", "quality": "primary"},
            {"id": "S2", "name": "公司定期报告", "as_of": "2026-09-30", "quality": "primary"},
        ],
    }


def _fixture_evidence():
    return {"items": [
        {"label": "收盘价", "value": 1520.50, "quality": "primary"},
        {"label": "前收", "value": 1500.00, "quality": "primary"},
        {"label": "营收", "value": 1234.50, "unit": "亿元", "quality": "primary"},
        {"label": "毛利率", "value": 91.20, "unit": "%", "quality": "primary"},
        {"label": "净利率", "value": 52.40, "unit": "%", "quality": "primary"},
        {"label": "涨跌幅", "value": 1.37, "unit": "%", "quality": "estimated"},
        {"label": "合理区间下限", "value": 1300.00, "quality": "estimated"},
        {"label": "合理区间上限", "value": 1600.00, "quality": "estimated"},
        {"label": "卖方一致预期增速", "value": 18.00, "unit": "%", "quality": "consensus"},
        {"label": "自算增速", "value": 11.00, "unit": "%", "quality": "estimated"},
        {"label": "乐观批价", "value": 2400.00, "quality": "assumption"},
        {"label": "批价阈值", "value": 2200.00, "quality": "assumption"},
    ]}


def t2_offline(tmp):
    print("\n[T2] 离线链路（夹具 -> 渲染 -> 闸门）")
    draft = _fixture_draft()
    dp = os.path.join(tmp, "draft.json")
    ep = os.path.join(tmp, "evidence.json")
    hp = os.path.join(tmp, "600519-diagnosis-20261029.html")
    with open(dp, "w", encoding="utf-8") as fh:
        json.dump(draft, fh, ensure_ascii=False)
    with open(ep, "w", encoding="utf-8") as fh:
        json.dump(_fixture_evidence(), fh, ensure_ascii=False)

    code, out = run_script(REPORT, ["--input", dp, "--out", hp])
    if code != 0 or not os.path.exists(hp):
        record("渲染 HTML+MD", "FAIL", out.strip()[-200:])
        return
    md = os.path.splitext(hp)[0] + ".md"
    size = os.path.getsize(hp)
    record("渲染 HTML+MD", "PASS" if os.path.exists(md) and size > 3000
           else "FAIL", "html=%d 字节, md=%s" % (size, os.path.exists(md)))

    with open(hp, "r", encoding="utf-8") as fh:
        html = fh.read()
    checks = [
        ("HTML 自包含无外链", "http://" not in html and "https://" not in html),
        ("含打印样式", "@media print" in html),
        ("含内联 SVG", "<svg" in html),
        ("含免责声明", "不构成投资建议" in html),
        ("含来源表", "来源" in html and "primary" in html),
    ]
    for name, ok in checks:
        record(name, "PASS" if ok else "FAIL")

    code, out = run_script(CHECK, ["--doc", hp, "--evidence", ep,
                                   "--code", "600519", "--data-as-of", "2026-10-29", "--json"])
    try:
        res = json.loads(out)
    except json.JSONDecodeError:
        record("闸门放行正例", "FAIL", "输出非 JSON：" + out.strip()[:200])
        return
    record("闸门放行正例", "PASS" if res["verdict"] == "放行" else "FAIL",
           "阻塞项 %d；A4 匹配率 %s" % (
               res["blocking_count"],
               next((c.get("ratio") for c in res["checks"] if c["id"] == "A4"), "n/a")))

    # 反例：塞入禁用词与缺失免责
    bad = os.path.join(tmp, "bad.html")
    with open(bad, "w", encoding="utf-8") as fh:
        fh.write("<html><body><p>## 结论 这票必涨，建议立即买入。</p>"
                 "<p>今日北向资金净流入 50 亿。</p></body></html>")
    code, out = run_script(CHECK, ["--doc", bad, "--json"])
    try:
        res = json.loads(out)
        blocked = res["verdict"] == "打回"
        failed_ids = [c["id"] for c in res["checks"] if not c["pass"] and not c.get("skipped")]
    except json.JSONDecodeError:
        blocked, failed_ids = False, []
    record("闸门拦截反例", "PASS" if blocked and {"A1", "A2", "A3", "A7"} & set(failed_ids)
           else "FAIL", "未通过项：%s" % ",".join(failed_ids))
    record("闸门退出码正确", "PASS" if code == 1 else "FAIL", "exit=%d" % code)


# ---------------- T3 真实链路 ----------------

def t3_live(tmp):
    print("\n[T3] 真实链路（联网取数 -> 指标 -> 出稿 -> 闸门）")
    code, out = run_script(FETCH, ["quote", "--codes", "600519"], timeout=40)
    if code != 0:
        record("联网取行情", "SKIP", "网络不可用或接口失败")
        record("真实链路出稿", "SKIP", "依赖联网取数")
        return
    try:
        quote = json.loads(out)
        item = quote["items"][0]
        last = float(item["last"])
        prev = float(item["prev_close"])
        name = item["name"]
        as_of = item.get("trade_date") or date.today().isoformat()
    except (json.JSONDecodeError, KeyError, IndexError, ValueError) as exc:
        record("联网取行情", "FAIL", "解析失败：%s" % exc)
        return
    record("联网取行情", "PASS", "%s %.2f（%+.2f%%），%s" %
           (name, last, float(item.get("pct_chg") or 0), as_of))

    code, out = run_script(FETCH, ["kline", "--code", "600519", "--days", "260"], timeout=60)
    if code != 0:
        record("联网取K线", "SKIP", "K线接口失败")
    else:
        try:
            bars = json.loads(out)["bars"]
            record("联网取K线", "PASS", "%d 根，%s 至 %s" %
                   (len(bars), bars[0]["date"], bars[-1]["date"]))
        except (json.JSONDecodeError, KeyError, IndexError):
            record("联网取K线", "FAIL", "K线解析失败")
            bars = []

    if bars:
        kp = os.path.join(tmp, "bars.json")
        with open(kp, "w", encoding="utf-8") as fh:
            json.dump(bars, fh, ensure_ascii=False)
        code, out = run_script(IND, ["--file", kp])
        try:
            ind = json.loads(out)
            record("指标计算", "PASS" if ind["ma"]["ma20"] and ind["trend"] != "数据不足"
                   else "FAIL", "%s，MA20=%.2f，RSI=%.1f" %
                   (ind["trend"], ind["ma"]["ma20"] or 0, ind["rsi14"] or 0))
        except (json.JSONDecodeError, KeyError, TypeError):
            ind = None
            record("指标计算", "FAIL", out.strip()[:160])
    else:
        ind = None

    # 用真实数字出稿
    draft = _fixture_draft()
    draft["name"] = name
    draft["data_as_of"] = as_of
    pct = float(item.get("pct_chg") or 0)
    draft["key_numbers"] = [
        {"label": "收盘/最新价", "value": "%.2f" % last, "note": "元，%s" % as_of},
        {"label": "涨跌幅", "value": "%+.2f" % pct, "note": "%"},
    ]
    if ind:
        draft["key_numbers"].append({"label": "MA20", "value": "%.2f" % ind["ma"]["ma20"],
                                     "note": "趋势：%s" % ind["trend"]})
        draft["key_numbers"].append({"label": "RSI14", "value": "%.1f" % (ind["rsi14"] or 0),
                                     "note": "超买>70 / 超卖<30"})
        draft["series"] = {"close": [b["close"] for b in bars[-60:]],
                           "caption": "收盘价走势（最近 60 个交易日，前复权）"}
        draft["sections"][0]["md"] += ("\n\n### 技术面\n- MA20 = %.2f，当前价相对 MA20 乖离 %.2f%%[推算]\n"
                                       "- RSI14 = %.1f[推算]\n- MACD：%s[推算]"
                                       % (ind["ma"]["ma20"], ind["bias_ma20_pct"] or 0,
                                          ind["rsi14"] or 0, ind["macd"]["cross"] or "无交叉"))
    draft["sources"] = [
        {"id": "S1", "name": quote["source"], "as_of": quote["fetch_time"], "quality": quote["quality"]},
        {"id": "S2", "name": "公司定期报告", "as_of": "2026-09-30", "quality": "primary"},
    ]

    ev = _fixture_evidence()
    ev["items"] += [
        {"label": "收盘价", "value": last, "quality": "primary"},
        {"label": "前收", "value": prev, "quality": "primary"},
    ]
    if ind:
        ev["items"] += [
            {"label": "MA20", "value": ind["ma"]["ma20"], "quality": "estimated"},
            {"label": "RSI14", "value": ind["rsi14"], "quality": "estimated"},
            {"label": "MA20乖离", "value": ind["bias_ma20_pct"], "quality": "estimated"},
        ]

    dp = os.path.join(tmp, "live-draft.json")
    ep = os.path.join(tmp, "live-evidence.json")
    hp = os.path.join(tmp, "600519-diagnosis-%s.html" % as_of.replace("-", ""))
    with open(dp, "w", encoding="utf-8") as fh:
        json.dump(draft, fh, ensure_ascii=False)
    with open(ep, "w", encoding="utf-8") as fh:
        json.dump(ev, fh, ensure_ascii=False)

    code, out = run_script(REPORT, ["--input", dp, "--out", hp])
    if code != 0:
        record("真实链路出稿", "FAIL", out.strip()[-200:])
        return
    record("真实链路出稿", "PASS", "%d 字节" % os.path.getsize(hp))

    code, out = run_script(CHECK, ["--doc", hp, "--evidence", ep,
                                   "--code", "600519", "--data-as-of", as_of, "--json"])
    try:
        res = json.loads(out)
        ratio = next((c.get("ratio") for c in res["checks"] if c["id"] == "A4"), None)
        record("真实链路过闸", "PASS" if res["verdict"] == "放行" else "FAIL",
               "阻塞 %d；A4=%s" % (res["blocking_count"], ratio))
    except json.JSONDecodeError:
        record("真实链路过闸", "FAIL", out.strip()[:200])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-live", action="store_true")
    args = ap.parse_args()

    print("=" * 62)
    print("专业A股投研主笔 · 端到端测试")
    print("时间：%s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 62)

    t1_unit()
    tmp = tempfile.mkdtemp(prefix="ar-test-")
    t2_offline(tmp)
    if args.no_live:
        record("真实链路（T3）", "SKIP", "按 --no-live 跳过")
    else:
        t3_live(tmp)

    pass_n = sum(1 for r in RESULTS if r["status"] == "PASS")
    fail_n = sum(1 for r in RESULTS if r["status"] == "FAIL")
    skip_n = sum(1 for r in RESULTS if r["status"] == "SKIP")
    print("\n" + "=" * 62)
    print("合计 %d 项：PASS %d / FAIL %d / SKIP %d" % (len(RESULTS), pass_n, fail_n, skip_n))
    if skip_n:
        print("注意：SKIP 项未经验证，不得计入通过。")
    print("=" * 62)

    report = os.path.join(ROOT, "tests", "last_run.json")
    with open(report, "w", encoding="utf-8") as fh:
        json.dump({"run_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                   "pass": pass_n, "fail": fail_n, "skip": skip_n,
                   "results": RESULTS}, fh, ensure_ascii=False, indent=2)
    print("明细已写入 %s" % report)
    return 0 if fail_n == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
