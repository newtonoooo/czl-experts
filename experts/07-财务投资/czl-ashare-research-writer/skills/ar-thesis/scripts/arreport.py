#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""研报渲染器：draft.json -> 自包含 HTML + 同名 Markdown（零第三方依赖）。

特点：
  * HTML 内联全部 CSS 与 SVG，不引 CDN、不嵌外部字体，断网可开。
  * 含 @media print，A4 打印不串版。
  * Markdown 与 HTML 由同一份 draft 生成，两份内容必然一致。
  * 涨=红、跌=绿（A 股习惯）。

CLI:
  python arreport.py --input draft.json --out 600519-diagnosis-20261029.html
  python arreport.py --selftest
"""
import argparse
import html as html_mod
import json
import os
import re
import sys
from datetime import datetime

CREAM = "#fbfaf7"
INK = "#1c1c1a"
INK2 = "#4a4a45"
INK3 = "#7a7a72"
RULE = "#e2ded4"
ACCENT = "#1f5c4a"
UP = "#c0392b"
DOWN = "#1e7a4f"

DISCLAIMER_DEFAULT = ("本内容基于公开信息整理，仅供研究参考，不构成投资建议。"
                      "数据以公司公告与交易所披露为准，行情存在延迟。投资有风险，决策请自行判断。")

TASK_LABEL = {
    "diagnosis": "个股诊断",
    "valuation": "估值定价",
    "tape": "大盘复盘",
    "feature": "深度成稿",
    "portfolio": "持仓体检",
}


# ---------------- 迷你 Markdown ----------------

def _inline(text):
    """行内标记：**粗** / *斜* / `代码`。输入必须已经过 html 转义。"""
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"`([^`\n]+?)`", r"<code>\1</code>", text)
    return text


def md_to_html(md):
    """把受支持的 Markdown 子集转成 HTML 片段。

    支持：# / ## / ### 标题、- 与 * 无序列表、1. 有序列表、| 表格 |、
    > 引用、空行分段、行内粗体斜体代码。不支持的语法按普通段落输出。
    """
    if not md:
        return ""
    lines = md.replace("\r\n", "\n").split("\n")
    out, i, n = [], 0, len(lines)
    while i < n:
        raw = lines[i]
        line = raw.rstrip()
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # 表格
        if stripped.startswith("|") and stripped.endswith("|"):
            block = []
            while i < n and lines[i].strip().startswith("|"):
                block.append(lines[i].strip())
                i += 1
            out.append(_render_table(block))
            continue

        # 标题
        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            level = len(m.group(1))
            out.append("<h%d>%s</h%d>" % (level + 1, _inline(html_mod.escape(m.group(2))), level + 1))
            i += 1
            continue

        # 引用
        if stripped.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append("<blockquote>%s</blockquote>" % _inline(html_mod.escape(" ".join(buf))))
            continue

        # 无序列表
        if re.match(r"^[-*]\s+", stripped):
            buf = []
            while i < n and re.match(r"^[-*]\s+", lines[i].strip()):
                buf.append(re.sub(r"^[-*]\s+", "", lines[i].strip()))
                i += 1
            items = "".join("<li>%s</li>" % _inline(html_mod.escape(x)) for x in buf)
            out.append("<ul>%s</ul>" % items)
            continue

        # 有序列表
        if re.match(r"^\d+[.)]\s+", stripped):
            buf = []
            while i < n and re.match(r"^\d+[.)]\s+", lines[i].strip()):
                buf.append(re.sub(r"^\d+[.)]\s+", "", lines[i].strip()))
                i += 1
            items = "".join("<li>%s</li>" % _inline(html_mod.escape(x)) for x in buf)
            out.append("<ol>%s</ol>" % items)
            continue

        # 段落（连续非空行合并）
        buf = []
        while i < n and lines[i].strip() and not re.match(
                r"^\s*([-*]\s|\d+[.)]\s|#{1,4}\s|\||>)", lines[i].strip()):
            buf.append(lines[i].strip())
            i += 1
        if buf:
            out.append("<p>%s</p>" % _inline(html_mod.escape(" ".join(buf))))
    return "\n".join(out)


def _render_table(block):
    rows = []
    for line in block:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c or "") for c in cells if c):
            continue
        rows.append(cells)
    if not rows:
        return ""
    head, body = rows[0], rows[1:]
    th = "".join("<th>%s</th>" % _inline(html_mod.escape(c)) for c in head)
    trs = []
    for r in body:
        tds = []
        for c in r:
            cls = ""
            clean = c.replace("**", "")
            if re.fullmatch(r"[+\-]?\d[\d,.]*%?", clean) or re.fullmatch(r"[+\-]?\d[\d,.]*\s*[%％]?", clean):
                if clean.startswith("-"):
                    cls = ' class="down"'
                elif clean.startswith("+"):
                    cls = ' class="up"'
            tds.append("<td%s>%s</td>" % (cls, _inline(html_mod.escape(c))))
        trs.append("<tr>%s</tr>" % "".join(tds))
    return ("<div class=\"tbl\"><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>"
            % (th, "".join(trs)))


# ---------------- SVG 迷你走势 ----------------

def sparkline(series, width=640, height=88):
    vals = [float(v) for v in series if v is not None]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    step = width / (len(vals) - 1)
    pts = []
    for i, v in enumerate(vals):
        x = i * step
        y = height - (v - lo) / span * (height - 10) - 5
        pts.append("%.1f,%.1f" % (x, y))
    color = UP if vals[-1] >= vals[0] else DOWN
    last_x, last_y = pts[-1].split(",")
    base_y = height - (vals[0] - lo) / span * (height - 10) - 5
    return (
        '<svg viewBox="0 0 %d %d" width="100%%" height="%d" preserveAspectRatio="none" '
        'role="img" aria-label="收盘价走势">'
        '<line x1="0" y1="%.1f" x2="%d" y2="%.1f" stroke="%s" stroke-width="1" '
        'stroke-dasharray="3 3" opacity="0.45"/>'
        '<polyline points="%s" fill="none" stroke="%s" stroke-width="2" '
        'stroke-linejoin="round" stroke-linecap="round"/>'
        '<circle cx="%s" cy="%s" r="3" fill="%s"/>'
        '</svg>'
        % (width, height, height, base_y, width, base_y, RULE,
           " ".join(pts), color, last_x, last_y, color)
    )


# ---------------- HTML ----------------

CSS = """
*{box-sizing:border-box}
body{margin:0;background:%(cream)s;color:%(ink)s;
 font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei","PingFang SC",sans-serif;
 font-size:16px;line-height:1.75;-webkit-font-smoothing:antialiased}
.page{max-width:820px;margin:0 auto;padding:56px 48px 80px}
.masthead{border-bottom:2px solid %(ink)s;padding-bottom:20px;margin-bottom:36px}
.kicker{font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:%(accent)s;font-weight:700;margin-bottom:12px}
h1{font-size:34px;line-height:1.28;margin:0 0 12px;font-weight:800;letter-spacing:-.01em}
.meta{font-size:13px;color:%(ink3)s;display:flex;gap:18px;flex-wrap:wrap}
.meta b{color:%(ink2)s;font-weight:600}
.verdict{background:#fff;border:1px solid %(rule)s;border-left:4px solid %(accent)s;
 padding:22px 24px;margin:0 0 34px;border-radius:3px}
.verdict h2.vtitle{margin:0 0 10px;padding:0;border:0;font-size:12px;letter-spacing:.16em;color:%(accent)s}
.verdict .lead{font-size:19px;font-weight:700;line-height:1.6;margin:0 0 12px}
.verdict .falsify{font-size:14px;color:%(ink2)s;margin:0}
.tag{display:inline-block;font-size:12px;font-weight:700;padding:2px 9px;border-radius:2px;
 background:%(accent)s;color:#fff;vertical-align:middle;margin-left:8px;letter-spacing:.04em}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;background:%(rule)s;
 border:1px solid %(rule)s;margin:0 0 34px}
.kpi{background:#fff;padding:14px 16px}
.kpi .l{font-size:12px;color:%(ink3)s;margin-bottom:4px}
.kpi .v{font-size:21px;font-weight:700;font-variant-numeric:tabular-nums}
.kpi .n{font-size:11px;color:%(ink3)s;margin-top:2px}
.chart{margin:0 0 34px}
.chart .cap{font-size:12px;color:%(ink3)s;margin-top:6px}
h2{font-size:15px;letter-spacing:.06em;text-transform:none;color:%(accent)s;font-weight:800;
 margin:44px 0 14px;padding-bottom:8px;border-bottom:1px solid %(rule)s}
h3{font-size:17px;margin:26px 0 10px}
h4{font-size:15px;margin:20px 0 8px}
p{margin:0 0 14px}
ul,ol{margin:0 0 16px;padding-left:22px}
li{margin:0 0 7px}
blockquote{margin:0 0 16px;padding:12px 18px;background:#fff;border-left:3px solid %(rule)s;
 color:%(ink2)s;font-size:15px}
code{font-family:ui-monospace,Consolas,monospace;font-size:.9em;background:#f1eee6;
 padding:1px 5px;border-radius:2px}
.tbl{overflow-x:auto;margin:0 0 20px}
table{border-collapse:collapse;width:100%%;font-size:14px;background:#fff}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid %(rule)s;vertical-align:top}
th{font-weight:700;background:#f5f2ea;font-size:13px;color:%(ink2)s;white-space:nowrap}
td{font-variant-numeric:tabular-nums}
.up{color:%(up)s;font-weight:600}
.down{color:%(down)s;font-weight:600}
.sources{margin-top:44px;padding-top:20px;border-top:2px solid %(ink)s}
.sources h2{margin-top:0}
.sources table{font-size:13px}
.disc{margin-top:34px;padding:16px 18px;background:#f1eee6;border-radius:3px;
 font-size:13px;color:%(ink2)s;line-height:1.7}
.foot{margin-top:26px;font-size:12px;color:%(ink3)s;display:flex;justify-content:space-between;
 gap:16px;flex-wrap:wrap}
@media (max-width:640px){
 .page{padding:32px 20px 56px}
 h1{font-size:26px}
 .verdict .lead{font-size:17px}
}
@media print{
 body{background:#fff;font-size:11pt}
 .page{max-width:none;padding:0}
 h2{page-break-after:avoid}
 .verdict,.tbl,.kpis{page-break-inside:avoid}
 a{color:inherit;text-decoration:none}
}
""" % {"cream": CREAM, "ink": INK, "ink2": INK2, "ink3": INK3, "rule": RULE,
       "accent": ACCENT, "up": UP, "down": DOWN}


def build_html(draft):
    code = draft.get("code", "")
    name = draft.get("name", "")
    task = draft.get("task", "diagnosis")
    date = draft.get("date") or datetime.now().strftime("%Y-%m-%d")
    title = draft.get("title") or ("%s（%s）%s" % (name, code, TASK_LABEL.get(task, "研究报告")))
    v = draft.get("verdict") or {}
    confidence = v.get("confidence", "中")

    kpis = draft.get("key_numbers") or []
    kpi_html = ""
    if kpis:
        cells = []
        for k in kpis:
            val = str(k.get("value", ""))
            cls = ""
            if val.startswith("-"):
                cls = ' class="down"'
            elif val.startswith("+"):
                cls = ' class="up"'
            cells.append('<div class="kpi"><div class="l">%s</div>'
                         '<div class="v"%s>%s</div><div class="n">%s</div></div>'
                         % (html_mod.escape(str(k.get("label", ""))), cls,
                            html_mod.escape(val), html_mod.escape(str(k.get("note", "")))))
        kpi_html = '<div class="kpis">%s</div>' % "".join(cells)

    chart = ""
    series = draft.get("series") or {}
    if series.get("close"):
        chart = ('<div class="chart">%s<div class="cap">%s</div></div>'
                 % (sparkline(series["close"]), html_mod.escape(
                     series.get("caption", "收盘价走势（最近 %d 个交易日）" % len(series["close"])))))

    sec_html = []
    for sec in draft.get("sections", []):
        if sec.get("hide_title"):
            sec_html.append(md_to_html(sec.get("md", "")))
        else:
            sec_html.append("<h2>%s</h2>\n%s" % (html_mod.escape(sec.get("title", "")),
                                                 md_to_html(sec.get("md", ""))))

    src = draft.get("sources") or []
    src_rows = "".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
        % (html_mod.escape(str(s.get("id", ""))), html_mod.escape(str(s.get("name", ""))),
           html_mod.escape(str(s.get("as_of", ""))), html_mod.escape(str(s.get("quality", ""))))
        for s in src) if src else "<tr><td colspan=\"4\">未登记来源</td></tr>"

    disc = draft.get("disclaimer") or DISCLAIMER_DEFAULT
    gen = draft.get("generated_at") or datetime.now().strftime("%Y-%m-%d %H:%M")

    body = "".join(sec_html)
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%s</title>
<style>%s</style>
</head>
<body>
<div class="page">
  <header class="masthead">
    <div class="kicker">%s · %s</div>
    <h1>%s</h1>
    <div class="meta">
      <span><b>标的</b> %s</span>
      <span><b>数据截至</b> %s</span>
      <span><b>报告日期</b> %s</span>
      <span><b>置信度</b> %s</span>
    </div>
  </header>

  <section class="verdict">
    <h2 class="vtitle">结论</h2>
    <p class="lead">%s<span class="tag">%s</span></p>
    <p class="falsify">%s</p>
  </section>

  %s
  %s
  %s

  <section class="sources">
    <h2>来源</h2>
    <div class="tbl"><table>
      <thead><tr><th>编号</th><th>数据来源</th><th>截至</th><th>质量</th></tr></thead>
      <tbody>%s</tbody>
    </table></div>
    <div class="disc">%s</div>
    <div class="foot"><span>生成于 %s</span><span>%s</span></div>
  </section>
</div>
</body>
</html>
""" % (html_mod.escape(title), CSS,
       html_mod.escape(TASK_LABEL.get(task, "研究")), html_mod.escape(code),
       html_mod.escape(title), html_mod.escape("%s %s" % (name, code)),
       html_mod.escape(str(draft.get("data_as_of", date))), html_mod.escape(date),
       html_mod.escape(confidence),
       _inline(html_mod.escape(v.get("text", ""))), html_mod.escape(confidence),
       _inline(html_mod.escape(v.get("falsify", ""))),
       kpi_html, chart, body, src_rows,
       html_mod.escape(disc), html_mod.escape(gen), html_mod.escape(code))


# ---------------- Markdown ----------------

def build_md(draft):
    code = draft.get("code", "")
    name = draft.get("name", "")
    task = draft.get("task", "diagnosis")
    date = draft.get("date") or datetime.now().strftime("%Y-%m-%d")
    title = draft.get("title") or ("%s（%s）%s" % (name, code, TASK_LABEL.get(task, "研究报告")))
    v = draft.get("verdict") or {}
    lines = ["# %s" % title, "",
             "> 标的：%s ｜ 数据截至：%s ｜ 报告日期：%s ｜ 置信度：%s"
             % ("%s %s" % (name, code), draft.get("data_as_of", date), date,
                v.get("confidence", "中")),
             "", "## 结论", "", "**%s**" % v.get("text", ""), "",
             "*%s*" % v.get("falsify", ""), ""]

    kpis = draft.get("key_numbers") or []
    if kpis:
        lines += ["## 关键数据", "", "| 项目 | 数值 | 说明 |", "|---|---|---|"]
        for k in kpis:
            lines.append("| %s | %s | %s |" % (k.get("label", ""), k.get("value", ""), k.get("note", "")))
        lines.append("")

    for sec in draft.get("sections", []):
        if not sec.get("hide_title"):
            lines += ["## %s" % sec.get("title", ""), ""]
        lines += [sec.get("md", ""), ""]

    src = draft.get("sources") or []
    lines += ["## 来源", "", "| 编号 | 数据来源 | 截至 | 质量 |", "|---|---|---|---|"]
    for s in src:
        lines.append("| %s | %s | %s | %s |" % (s.get("id", ""), s.get("name", ""),
                                                s.get("as_of", ""), s.get("quality", "")))
    lines += ["", "---", "", "*%s*" % (draft.get("disclaimer") or DISCLAIMER_DEFAULT), "",
              "生成于 %s ｜ %s" % (draft.get("generated_at") or
                                 datetime.now().strftime("%Y-%m-%d %H:%M"), code), ""]
    return "\n".join(lines)


# ---------------- 自检 ----------------

def selftest():
    draft = {
        "code": "600519.SH", "name": "贵州茅台", "task": "diagnosis",
        "date": "2026-10-29", "data_as_of": "2026-10-29",
        "title": "贵州茅台（600519.SH）个股诊断",
        "verdict": {"text": "生意质量高但增速已换挡，当前价隐含假设偏乐观。",
                    "confidence": "中",
                    "falsify": "若下一季度预收款同比转负且批价跌破 2000 元，本判断失效。"},
        "key_numbers": [
            {"label": "收盘价", "value": "1349.47", "note": "元，2026-10-29"},
            {"label": "涨跌幅", "value": "+1.41", "note": "%"},
            {"label": "MA20 乖离", "value": "-2.30", "note": "%"},
        ],
        "series": {"close": [1300, 1310, 1290, 1320, 1330, 1349.47],
                   "caption": "收盘价走势（最近 6 个交易日）"},
        "sections": [
            {"title": "证据", "md": "### 财务\n- 前三季度营收 1234.5 亿元[事实]\n- 扣非净利同比 +9.8%[事实]\n\n| 指标 | 数值 | 口径 |\n|---|---|---|\n| 毛利率 | 91.2% | 前三季度 |\n| 净利率 | 52.4% | 前三季度 |"},
            {"title": "分歧", "md": "市场共识是 20% 的增长，**我认为不会**，因为基数已高。"},
        ],
        "sources": [{"id": "S1", "name": "新浪财经", "as_of": "2026-10-29 10:43", "quality": "primary"}],
    }
    html = build_html(draft)
    md = build_md(draft)
    checks = [
        ("HTML 有 doctype", html.startswith("<!DOCTYPE html>")),
        ("HTML 无外部 http 引用", "http://" not in html and "https://" not in html),
        ("含打印样式", "@media print" in html),
        ("含涨色", "up" in html),
        ("表格已渲染", "<table>" in html),
        ("粗体已渲染", "<strong>" in html),
        ("列表已渲染", "<ul>" in html and "<li>" in html),
        ("含 SVG 走势", "<svg" in html),
        ("免责声明在 HTML", "不构成投资建议" in html),
        ("MD 有结论段", "## 结论" in md),
        ("MD 有来源段", "## 来源" in md),
        ("MD 有免责", "不构成投资建议" in md),
        ("七段之外无遗漏", md.count("## ") >= 4),
    ]
    failed = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print(("  PASS  " if ok else "  FAIL  ") + n)
    print("结果：%d/%d 通过" % (len(checks) - len(failed), len(checks)))
    return 0 if not failed else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="研报渲染器")
    ap.add_argument("--input")
    ap.add_argument("--out")
    ap.add_argument("--md-out")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.input or not args.out:
        ap.error("需要 --input 与 --out")

    with open(args.input, "r", encoding="utf-8") as fh:
        draft = json.load(fh)
    if "disclaimer" not in draft:
        draft["disclaimer"] = DISCLAIMER_DEFAULT
    if "generated_at" not in draft:
        draft["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    html_text = build_html(draft)
    md_text = build_md(draft)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(html_text)
    md_path = args.md_out or os.path.splitext(args.out)[0] + ".md"
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(md_text)
    print("HTML: %s (%d 字节)" % (os.path.abspath(args.out), len(html_text.encode("utf-8"))))
    print("MD  : %s (%d 字节)" % (os.path.abspath(md_path), len(md_text.encode("utf-8"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
