# -*- coding: utf-8 -*-
"""三棱镜 · 交付渲染层

把 analyze / verify 的 JSON 渲染成四种成品：
  report.html   单文件网页报告（内联 SVG 图表，离线可看，可直接打印成 PDF）
  deck.html     16:9 幻灯片网页版（可投屏、可打印）
  deck_spec.json 幻灯片内容规格（交给平台 PPT 能力生成 .pptx）
  onepager.md   一页纸摘要（贴进周报/群消息）
  workbook.xlsx 多工作表数据底稿

所有图表数字均来自 JSON，不在渲染阶段做任何计算，避免二次口径漂移。
"""

from __future__ import annotations

import datetime as _dt
import html
import json
import os

from triad_xlsx import Sheet, write_workbook

PALETTE = {
    "ink": "#0F1B2D", "blue": "#1F3A5F", "accent": "#2F80ED", "cyan": "#38D6E8",
    "amber": "#F2994A", "red": "#D64545", "green": "#2E9E6B", "gray": "#667085",
    "line": "#E4E9F2", "bg": "#F7F9FC", "white": "#FFFFFF",
}
GRADE_COLOR = {"A": "#2E9E6B", "B": "#2F80ED", "C": "#F2994A", "D": "#D64545"}
SEV_COLOR = {"CRITICAL": "#D64545", "WARN": "#F2994A", "INFO": "#667085"}


def esc(s):
    return html.escape(str(s if s is not None else ""))


def fmt_num(v, digits=2):
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "是" if v else "否"
    if isinstance(v, (int, float)):
        if abs(v) >= 10000:
            return f"{v:,.{digits}f}"
        if v == int(v):
            return f"{int(v):,}"
        return f"{v:,.{digits}f}"
    return esc(v)


def fmt_pct(v):
    return "—" if v is None else f"{v:+.2f}%" if v else "0.00%"


# ---------------------------------------------------------------- SVG 图表

def _axis_num(v):
    """坐标轴数字：过万折算成「万」，避免中文报告里出现一长串数字被裁切。"""
    a = abs(v)
    if a >= 100000000:
        return f"{v/100000000:.1f}亿"
    if a >= 10000:
        return f"{v/10000:.0f}万"
    if a >= 1000:
        return f"{v:,.0f}"
    if a >= 10:
        return f"{v:.0f}"
    return f"{v:.1f}"


def line_chart(series, forecast=None, width=720, height=280, unit=""):
    if not series:
        return '<p class="muted">无可用时间序列</p>'
    pad_l, pad_r, pad_t, pad_b = (74 if width >= 600 else 58), 18, 22, 46
    iw, ih = width - pad_l - pad_r, height - pad_t - pad_b
    vals = [p["value"] for p in series]
    fpts = (forecast or {}).get("points") or []
    all_vals = vals + [p["value"] for p in fpts] + [p["low"] for p in fpts] + [p["high"] for p in fpts]
    lo, hi = min(all_vals), max(all_vals)
    if lo >= 0:
        lo = 0.0                      # 非负数据一律从 0 起，不做视觉放大
    if hi == lo:
        hi = lo + 1
    pad = (hi - lo) * 0.10
    hi = hi + pad
    if lo > 0:
        lo = lo - pad
    n = len(series)
    total_pts = n + len(fpts)

    def x_of(i):
        return pad_l + (iw * i / max(1, total_pts - 1))

    def y_of(v):
        return pad_t + ih - (v - lo) / (hi - lo) * ih

    parts = [f'<svg viewBox="0 0 {width} {height}" class="chart" role="img" aria-label="时间序列走势">']
    for k in range(5):
        gy = pad_t + ih * k / 4
        gv = hi - (hi - lo) * k / 4
        parts.append(f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{pad_l+iw}" y2="{gy:.1f}" stroke="{PALETTE["line"]}" stroke-width="1"/>')
        parts.append(f'<text x="{pad_l-8}" y="{gy+4:.1f}" text-anchor="end" class="axis">{_axis_num(gv)}</text>')
    pts = " ".join(f"{x_of(i):.1f},{y_of(v):.1f}" for i, v in enumerate(vals))
    area = f"{pad_l},{pad_t+ih} " + pts + f" {x_of(n-1):.1f},{pad_t+ih}"
    parts.append(f'<polygon points="{area}" fill="url(#gradLine)" opacity="0.55"/>')
    parts.append(f'<polyline points="{pts}" fill="none" stroke="{PALETTE["accent"]}" stroke-width="2.4" stroke-linejoin="round"/>')
    if fpts:
        fpath = " ".join(f"{x_of(n+i):.1f},{y_of(p['value']):.1f}" for i, p in enumerate(fpts))
        parts.append(f'<polyline points="{x_of(n-1):.1f},{y_of(vals[-1]):.1f} {fpath}" fill="none" stroke="{PALETTE["amber"]}" stroke-width="2" stroke-dasharray="5 4"/>')
        band = (f"{x_of(n-1):.1f},{y_of(vals[-1]):.1f} " +
                " ".join(f"{x_of(n+i):.1f},{y_of(p['high']):.1f}" for i, p in enumerate(fpts)) + " " +
                " ".join(f"{x_of(n+i):.1f},{y_of(p['low']):.1f}" for i, p in reversed(list(enumerate(fpts)))) + " " +
                f"{x_of(n-1):.1f},{y_of(vals[-1]):.1f}")
        parts.append(f'<polygon points="{band}" fill="{PALETTE["amber"]}" opacity="0.14"/>')
        parts.append(f'<text x="{x_of(n):.1f}" y="{pad_t+10}" class="axis" fill="{PALETTE["amber"]}">外推</text>')
    # 横轴标签：同年份时只显示月/周，年份挪到轴注里，避免标签互相挤压
    periods = [p["period"] for p in series]
    prefix = os.path.commonprefix(periods)
    year_note = ""
    if len(prefix) >= 5 and prefix.endswith("-") and all(len(p) > len(prefix) for p in periods):
        year_note = prefix[:-1]
        short = [p[len(prefix):] for p in periods]
    else:
        short = periods
    max_labels = max(4, int(iw / 34))
    step = max(1, -(-n // max_labels))
    for i in range(0, n, step):
        parts.append(f'<text x="{x_of(i):.1f}" y="{height-20}" text-anchor="middle" class="axis">{esc(short[i])}</text>')
    if (n - 1) % step and n - 1 > step:
        parts.append(f'<text x="{x_of(n-1):.1f}" y="{height-20}" text-anchor="middle" class="axis">{esc(short[-1])}</text>')
    axis_note = " · ".join(x for x in (f"{year_note} 年" if year_note else "", unit or "") if x)
    if axis_note:
        parts.append(f'<text x="{pad_l}" y="{height-4}" class="axis" fill="{PALETTE["gray"]}">{esc(axis_note)}</text>')
    parts.append(f'<defs><linearGradient id="gradLine" x1="0" y1="0" x2="0" y2="1">'
                 f'<stop offset="0%" stop-color="{PALETTE["accent"]}" stop-opacity="0.35"/>'
                 f'<stop offset="100%" stop-color="{PALETTE["accent"]}" stop-opacity="0.02"/></linearGradient></defs>')
    parts.append("</svg>")
    return "".join(parts)


def bar_chart(rows, width=720, unit=""):
    if not rows:
        return '<p class="muted">无可用结构数据</p>'
    row_h, gap, pad_l, pad_r = 34, 10, 120, 70
    height = len(rows) * (row_h + gap) + 20
    iw = width - pad_l - pad_r
    mx = max(r["share"] or 0 for r in rows) or 1
    parts = [f'<svg viewBox="0 0 {width} {height}" class="chart" role="img" aria-label="构成占比">']
    for i, r in enumerate(rows):
        y = 10 + i * (row_h + gap)
        w = iw * (r["share"] or 0) / mx
        color = PALETTE["accent"] if i == 0 else PALETTE["cyan"] if i < 3 else "#B9CBDD"
        parts.append(f'<text x="{pad_l-10}" y="{y+row_h*0.68:.1f}" text-anchor="end" class="bar-label">{esc(r["name"])}</text>')
        parts.append(f'<rect x="{pad_l}" y="{y}" width="{iw}" height="{row_h}" rx="4" fill="#EEF2F8"/>')
        parts.append(f'<rect x="{pad_l}" y="{y}" width="{max(2, w):.1f}" height="{row_h}" rx="4" fill="{color}"/>')
        parts.append(f'<text x="{pad_l+max(2,w)+8:.1f}" y="{y+row_h*0.68:.1f}" class="bar-val">{r["share"]:.2f}%</text>')
    parts.append("</svg>")
    return "".join(parts)


def sparkline(values, width=180, height=44, color=None):
    if not values:
        return ""
    lo, hi = min(values), max(values)
    if hi == lo:
        hi = lo + 1
    pts = " ".join(f"{i/(len(values)-1)*width:.1f},{height-((v-lo)/(hi-lo))*height:.1f}"
                   for i, v in enumerate(values)) if len(values) > 1 else f"0,{height/2}"
    return (f'<svg viewBox="0 0 {width} {height}" class="spark" aria-hidden="true">'
            f'<polyline points="{pts}" fill="none" stroke="{color or PALETTE["accent"]}" stroke-width="2"/></svg>')


# ---------------------------------------------------------------- 报告装配

def _collect(bundle):
    lanes = bundle.get("lanes") or {}
    course = lanes.get("course") or {}
    comp = lanes.get("composition") or {}
    integ = lanes.get("integrity") or {}
    findings = []
    for lane in ("course", "composition", "integrity"):
        for f in (lanes.get(lane) or {}).get("findings") or []:
            f = dict(f)
            f["lane"] = lane
            findings.append(f)
    return course, comp, integ, findings


def pick_headlines(findings, limit=4):
    """摘要顺序：三视角轮流取第一条，保证读者先看到三条线各自的主结论。

    不按等级排序——等级最高的往往是「扫描了 108 行」这种过程性结论，
    放到摘要第一条会让人抓不到重点。
    """
    live = [f for f in findings if f.get("verified") is not False and f.get("grade") != "D"]
    by_lane = {"course": [], "composition": [], "integrity": []}
    for f in live:
        by_lane.setdefault(f.get("lane"), []).append(f)
    out = []
    idx = 0
    while len(out) < limit:
        added = False
        for lane in ("course", "composition", "integrity"):
            bucket = by_lane.get(lane) or []
            if idx < len(bucket):
                out.append(bucket[idx])
                added = True
                if len(out) >= limit:
                    break
        if not added:
            break
        idx += 1
    return out


def _verified_badge(f):
    if f.get("verified") is True:
        return '<span class="tag ok">已复算</span>'
    if f.get("verified") is None:
        return '<span class="tag warn">未复算</span>'
    if f.get("verified") is False:
        return '<span class="tag bad">已作废</span>'
    return ""


def build_html(bundle, profile, verify_report, meta):
    course, comp, integ, findings = _collect(bundle)
    live = [f for f in findings if f.get("verified") is not False and f.get("grade") != "D"]
    top = pick_headlines(findings, 4)
    q = profile["quality"]
    stats = course.get("stats") or {}
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    def kpi(label, value, sub="", color=None):
        return (f'<div class="kpi"><div class="kpi-label">{esc(label)}</div>'
                f'<div class="kpi-value" style="color:{color or PALETTE["ink"]}">{value}</div>'
                f'<div class="kpi-sub">{esc(sub)}</div></div>')

    kpis = []
    if stats:
        kpis.append(kpi("区间变化", f'<span class="{"up" if (stats.get("change_pct") or 0)>=0 else "down"}">{fmt_pct(stats.get("change_pct"))}</span>',
                        f'{course.get("series")[0]["period"]} → {course.get("series")[-1]["period"]}'))
        kpis.append(kpi("最新一期", fmt_num(stats.get("last")), f'{(course.get("metric") or {}).get("name","")}'))
        mom = course.get("mom") or {}
        kpis.append(kpi("环比", fmt_pct(mom.get("change_pct")), f'对比 {mom.get("prev_period","—")}'))
    if comp.get("available"):
        kpis.append(kpi("结构集中度", f'{comp.get("hhi", 0):,.0f}', comp.get("hhi_level", "")))
    if integ.get("counts"):
        c = integ["counts"]
        kpis.append(kpi("异常条目", f'{c["CRITICAL"]} 高危', f'关注 {c["WARN"]} · 提示 {c["INFO"]}',
                        SEV_COLOR["CRITICAL"] if c["CRITICAL"] else PALETTE["green"]))
    kpis.append(kpi("数据可信度", q["grade"], f'{q["score"]} 分 · 闸门 {q["gate"]}', GRADE_COLOR[q["grade"]]))

    # 摘要
    summary_html = "".join(
        f'<li><span class="dot" style="background:{GRADE_COLOR.get(f.get("grade"), PALETTE["gray"])}"></span>'
        f'{esc(f["claim"])} {_verified_badge(f)}</li>' for f in top) or "<li>本次没有达到可结论门槛的发现</li>"

    # 体检
    issue_rows = "".join(
        f'<tr><td><span class="sev" style="background:{SEV_COLOR.get(i["level"].upper(), PALETTE["gray"])}">'
        f'{esc(i["level"])}</span></td><td>{esc(i["message"])}</td></tr>'
        for i in q["issues"]) or '<tr><td colspan="2">未发现结构性问题</td></tr>'

    # 走势
    chart = line_chart(course.get("series") or [], course.get("forecast"), unit=(course.get("metric") or {}).get("unit") or "")
    inf_rows = "".join(
        f'<tr><td>{esc(i["period"])}</td><td>{esc(i["note"])}</td>'
        f'<td>{fmt_num(i["before_slope"])} → {fmt_num(i["after_slope"])}</td></tr>'
        for i in course.get("inflections") or []) or '<tr><td colspan="3">未识别到显著拐点</td></tr>'
    fc = course.get("forecast") or {}
    fc_rows = "".join(
        f'<tr><td>{esc(p["period"])}</td><td>{fmt_num(p["value"])}</td>'
        f'<td>{fmt_num(p["low"])} ~ {fmt_num(p["high"])}</td></tr>' for p in fc.get("points") or [])
    fc_html = (f'<p class="muted">方法：{esc(fc.get("method"))}；置信度：{esc(fc.get("confidence"))}；R²={fmt_num(fc.get("r2"))}</p>'
               f'<table class="tbl"><thead><tr><th>期次</th><th>中枢</th><th>区间</th></tr></thead><tbody>{fc_rows}</tbody></table>'
               if fc.get("available") else '<p class="muted">时点不足以做外推</p>')

    # 结构
    comp_html = ""
    if comp.get("available"):
        comp_html = f"""
        <div class="grid2">
          <div>{bar_chart(comp.get("rows") or [])}</div>
          <div>
            <table class="tbl"><thead><tr><th>分组</th><th>数值</th><th>占比</th><th>累计</th></tr></thead><tbody>
            {''.join(f'<tr><td>{esc(r["name"])}</td><td>{fmt_num(r["value"])}</td><td>{r["share"]:.2f}%</td><td>{r["cum_share"]:.2f}%</td></tr>' for r in comp.get("rows") or [])}
            </tbody></table>
            <p class="muted">按「{esc(comp.get("dimension"))}」拆解；HHI {comp.get("hhi"):,.0f}（{esc(comp.get("hhi_level"))}）；
            前两名合计 {comp.get("top2_share"):.2f}%；覆盖 80% 需 {comp.get("pareto_n")} 个分组。</p>
          </div>
        </div>"""
        if comp.get("shift"):
            comp_html += ('<h4>结构位移（首期 → 末期）</h4><table class="tbl"><thead><tr><th>分组</th>'
                          '<th>首期占比</th><th>末期占比</th><th>变化</th></tr></thead><tbody>' +
                          "".join(f'<tr><td>{esc(s["name"])}</td><td>{s["share_first"]:.2f}%</td>'
                                  f'<td>{s["share_last"]:.2f}%</td><td class="{"up" if s["delta_pp"]>=0 else "down"}">{s["delta_pp"]:+.2f} pp</td></tr>'
                                  for s in comp["shift"]) + "</tbody></table>")
    else:
        comp_html = f'<p class="muted">{esc(comp.get("reason", "本次未执行结构拆解"))}</p>'

    # 异常
    integ_rows = "".join(
        f'<tr><td><span class="sev" style="background:{SEV_COLOR.get(i["severity"], PALETTE["gray"])}">{esc(i["severity"])}</span></td>'
        f'<td>{esc(i.get("column") or "整行")}</td><td>{esc(i.get("row") or "—")}</td>'
        f'<td>{fmt_num(i.get("value"))}</td><td>{esc(i["message"])}</td><td>{esc(i["action"])}</td></tr>'
        for i in integ.get("items") or []) or '<tr><td colspan="6">未发现异常</td></tr>'

    # 证据链
    v_rows = "".join(
        f'<tr><td>{esc(r["lane"])}</td><td>{esc(r["id"])}</td><td>{esc(r.get("op",""))}</td>'
        f'<td>{fmt_num(r.get("claim_value"))}</td><td>{fmt_num(r.get("recomputed"))}</td>'
        f'<td><span class="tag {"ok" if r["status"]=="PASS" else "warn" if r["status"]=="SKIP" else "bad"}">{r["status"]}</span></td></tr>'
        for r in verify_report.get("results") or [])

    contract = bundle.get("contract") or {}
    contract_json = esc(json.dumps(contract, ensure_ascii=False, indent=2))
    disclaimers = [c for c in (course.get("caveats") or []) + (comp.get("caveats") or []) + (integ.get("caveats") or [])]
    sheet_label = "" if profile["sheet"] == profile["source"] else f"（{profile['sheet']}）"
    notes_txt = "；".join(profile.get("notes") or [])
    notes_html = f"<br/><span class=\"muted\">{esc(notes_txt)}</span>" if notes_txt else ""

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{esc(meta.get('title'))}</title>
<style>
:root{{--ink:{PALETTE['ink']};--gray:{PALETTE['gray']};--line:{PALETTE['line']};--accent:{PALETTE['accent']};--bg:{PALETTE['bg']};}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:"Microsoft YaHei","PingFang SC","Segoe UI",system-ui,sans-serif;font-size:14px;line-height:1.75}}
.wrap{{max-width:1080px;margin:0 auto;padding:32px 28px 64px}}
header.hero{{background:linear-gradient(135deg,{PALETTE['blue']} 0%,{PALETTE['ink']} 100%);color:#fff;border-radius:16px;padding:30px 32px;position:relative;overflow:hidden}}
header.hero:after{{content:"";position:absolute;right:-60px;top:-60px;width:220px;height:220px;border-radius:50%;background:rgba(56,214,232,.16)}}
.eyebrow{{font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:{PALETTE['cyan']};margin-bottom:8px}}
h1{{margin:0 0 6px;font-size:26px;font-weight:700;letter-spacing:.01em}}
.hero-meta{{color:#B9CBDD;font-size:13px}}
.badge-row{{margin-top:16px;display:flex;gap:10px;flex-wrap:wrap}}
.badge{{background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.22);border-radius:999px;padding:4px 12px;font-size:12px}}
section{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:24px 26px;margin-top:18px}}
h2{{font-size:17px;margin:0 0 14px;padding-left:12px;border-left:4px solid var(--accent)}}
h3{{font-size:15px;margin:20px 0 8px;color:var(--blue)}}
h4{{font-size:13px;margin:16px 0 6px;color:var(--gray);font-weight:600}}
p{{margin:8px 0}}
.muted{{color:var(--gray);font-size:12.5px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(146px,1fr));gap:10px;margin:4px 0 8px}}
.kpi{{background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:12px 13px}}
.kpi-label{{font-size:12px;color:var(--gray)}}
.kpi-value{{font-size:21px;font-weight:700;margin:4px 0 2px;letter-spacing:-.01em}}
.kpi-sub{{font-size:11px;color:var(--gray)}}
.up{{color:{PALETTE['red']}}}
.down{{color:{PALETTE['green']}}}
ul.findings{{list-style:none;padding:0;margin:0}}
ul.findings li{{padding:9px 0;border-bottom:1px dashed var(--line);display:flex;gap:10px;align-items:flex-start}}
ul.findings li:last-child{{border-bottom:none}}
.dot{{width:8px;height:8px;border-radius:50%;margin-top:8px;flex:0 0 8px}}
.tbl{{width:100%;border-collapse:collapse;font-size:13px;margin:8px 0}}
.tbl th{{background:var(--bg);text-align:left;font-weight:600;color:var(--blue);padding:9px 10px;border-bottom:1px solid var(--line);font-size:12.5px}}
.tbl td{{padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}}
.tbl tr:last-child td{{border-bottom:none}}
.sev{{color:#fff;border-radius:4px;padding:1px 7px;font-size:11px;font-weight:600;white-space:nowrap}}
.tag{{font-size:11px;border-radius:4px;padding:1px 7px;border:1px solid;white-space:nowrap}}
.tag.ok{{color:{PALETTE['green']};border-color:#BFE3D2;background:#F1FAF5}}
.tag.warn{{color:{PALETTE['amber']};border-color:#F6DCC1;background:#FEF7F0}}
.tag.bad{{color:{PALETTE['red']};border-color:#F1C9C9;background:#FDF2F2}}
.chart{{width:100%;height:auto;display:block}}
.axis{{font-size:10.5px;fill:{PALETTE['gray']}}}
.bar-label{{font-size:12px;fill:var(--ink)}}
.bar-val{{font-size:11.5px;fill:var(--gray)}}
.grid2{{display:grid;grid-template-columns:1.15fr 1fr;gap:20px;align-items:start}}
pre{{background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:14px;font-size:12px;overflow:auto;max-height:320px}}
footer{{margin-top:22px;color:var(--gray);font-size:12px;text-align:center;line-height:1.9}}
@media (max-width:820px){{.grid2{{grid-template-columns:1fr}}}}
@media print{{body{{background:#fff}}section{{break-inside:avoid;border-color:#ddd}}header.hero{{border-radius:0}}}}
</style></head><body><div class="wrap">
<header class="hero">
  <div class="eyebrow">TriPrism · 三视角数据会诊</div>
  <h1>{esc(meta.get('title'))}</h1>
  <div class="hero-meta">数据源：{esc(profile['source'])}{sheet_label} · {profile['rows']} 行 × {profile['cols']} 列 · 生成于 {now}</div>
  <div class="badge-row">
    <span class="badge">可信度 {esc(q['grade'])} / {q['score']} 分</span>
    <span class="badge">结论复算 {esc(verify_report.get('overall'))}（{verify_report.get('passed')}/{verify_report.get('checked')}）</span>
    <span class="badge">{len(findings)} 条结论 · {len([f for f in findings if f.get('verified') is not False])} 条有效</span>
    <span class="badge">全程本地处理</span>
  </div>
</header>

<section><h2>一页纸结论</h2>
<div class="kpis">{''.join(kpis)}</div>
<ul class="findings">{summary_html}</ul>
</section>

<section><h2>数据体检</h2>
<p>体检在分析之前完成，决定这份数据能支撑多强的结论。<strong>可信度 {esc(q['grade'])}（{q['score']} 分），闸门 {esc(q['gate'])}</strong>。
{notes_html}</p>
<table class="tbl"><thead><tr><th style="width:90px">级别</th><th>发现</th></tr></thead><tbody>{issue_rows}</tbody></table>
<p class="muted">时间轴：{esc((profile.get('time_axis') or {}).get('column') or '未识别')}　
粒度：{esc((profile.get('time_axis') or {}).get('grain') or '—')}　
覆盖：{esc((profile.get('time_axis') or {}).get('from') or '—')} → {esc((profile.get('time_axis') or {}).get('to') or '—')}</p>
</section>

<section><h2>走势线 · 时间怎么变</h2>
{chart}
<h3>关键统计</h3>
<table class="tbl"><tbody>
<tr><th>方向</th><td>{esc(stats.get('direction', '—'))}</td><th>区间变化</th><td>{fmt_pct(stats.get('change_pct'))}</td></tr>
<tr><th>每期斜率</th><td>{fmt_num(stats.get('slope_per_period'))}</td><th>拟合优度 R²</th><td>{fmt_num(stats.get('r2'))}</td></tr>
<tr><th>波动系数 CV</th><td>{fmt_num(stats.get('cv'))}</td><th>时点数</th><td>{fmt_num(stats.get('points'))}</td></tr>
</tbody></table>
<h3>拐点</h3>
<table class="tbl"><thead><tr><th>期次</th><th>形态</th><th>斜率变化</th></tr></thead><tbody>{inf_rows}</tbody></table>
<h3>外推（谨慎使用）</h3>
{fc_html}
</section>

<section><h2>拆解线 · 内部怎么组成</h2>
{comp_html}
</section>

<section><h2>验伤线 · 哪里不对劲</h2>
<table class="tbl"><thead><tr><th style="width:80px">级别</th><th>字段</th><th>行号</th><th>数值</th><th>说明</th><th>建议动作</th></tr></thead><tbody>{integ_rows}</tbody></table>
</section>

<section><h2>证据链</h2>
<p class="muted">每条结论都用同一份源数据重算过一次。PASS = 复算一致；SKIP = 规格不足以复算，正文已标注；FAIL = 不一致，已从结论中作废。</p>
<table class="tbl"><thead><tr><th>线</th><th>编号</th><th>复算方式</th><th>报告值</th><th>复算值</th><th>状态</th></tr></thead><tbody>{v_rows}</tbody></table>
</section>

<section><h2>口径与免责</h2>
<p>本报告所有指标均在下列口径下计算，换口径结果会变，请勿跨口径比较。</p>
<pre>{contract_json}</pre>
{'<h4>使用限制</h4><ul class="muted">' + ''.join(f'<li>{esc(d)}</li>' for d in disclaimers) + '</ul>' if disclaimers else ''}
<p class="muted">数据全程在本机处理，未上传任何云端。结论基于所提供表格，未包含表格之外的信息（如市场价格、竞品动作、政策变化）。</p>
</section>

<footer>由「{esc(meta.get('product'))}」生成 · 开发者 {esc(meta.get('author'))} · v{esc(meta.get('version'))}<br/>
{esc(meta.get('footer_note', '本报告为数据辅助材料，不构成审计、税务或投资意见。'))}</footer>
</div></body></html>"""


def build_deck(bundle, profile, verify_report, meta):
    course, comp, integ, findings = _collect(bundle)
    live = [f for f in findings if f.get("verified") is not False and f.get("grade") != "D"]
    stats = course.get("stats") or {}
    slides = []

    slides.append({"title": meta.get("title"), "kicker": "TriPrism · 三视角数据会诊",
                   "bullets": [f"数据源：{profile['source']}（{profile['rows']} 行 × {profile['cols']} 列）",
                               f"数据可信度：{profile['quality']['grade']}（{profile['quality']['score']} 分）",
                               f"结论复算：{verify_report.get('overall')}（{verify_report.get('passed')}/{verify_report.get('checked')}）",
                               f"生成：{_dt.datetime.now().strftime('%Y-%m-%d')}"], "chart": None})

    slides.append({"title": "三句话结论", "kicker": "摘要",
                   "bullets": [f["claim"] for f in pick_headlines(findings, 3)] or ["本次没有达到可结论门槛的发现"],
                   "chart": "kpi"})

    if course.get("available"):
        slides.append({"title": "走势：时间维度发生了什么", "kicker": "走势线",
                       "bullets": [f"方向 {stats.get('direction')}，区间变化 {fmt_pct(stats.get('change_pct'))}",
                                   f"每期斜率 {fmt_num(stats.get('slope_per_period'))}，R²={fmt_num(stats.get('r2'))}",
                                   *[f"{i['period']} {i['note']}（斜率 {fmt_num(i['before_slope'])} → {fmt_num(i['after_slope'])}）"
                                     for i in course.get("inflections") or []][:2],
                                   *[f"外推 {p['period']} 中枢 {fmt_num(p['value'])}（区间 {fmt_num(p['low'])}~{fmt_num(p['high'])}）"
                                     for p in (course.get("forecast") or {}).get("points") or []][:2]],
                       "chart": "line"})
    if comp.get("available"):
        slides.append({"title": "结构：钱从哪来、集中在谁身上", "kicker": "拆解线",
                       "bullets": [f"按「{comp['dimension']}」拆解，第一名为 {comp['rows'][0]['name']}（{comp['rows'][0]['share']}%）",
                                   f"集中度 HHI {comp['hhi']:,.0f}（{comp['hhi_level']}），前两名合计 {comp['top2_share']:.2f}%",
                                   *[f"{s['name']} 占比 {s['share_first']}% → {s['share_last']}%（{s['delta_pp']:+.2f} pp）"
                                     for s in (comp.get("shift") or [])[:2]]],
                       "chart": "bar"})
    if integ.get("counts"):
        c = integ["counts"]
        slides.append({"title": "验伤：哪里可能不对", "kicker": "验伤线",
                       "bullets": [f"高危 {c['CRITICAL']} 条、关注 {c['WARN']} 条、提示 {c['INFO']} 条",
                                   *[f"[{i['severity']}] {i['message']}" for i in (integ.get("items") or [])[:4]]],
                       "chart": "table"})

    actions = []
    for f in live[:3]:
        lane = f.get("lane")
        if lane == "course":
            actions.append("把走势结论写进周报，并锁定下一期的对比基期")
        elif lane == "composition":
            actions.append("对占比最高与位移最大的两个分组做专项归因")
        else:
            actions.append("按异常清单逐条核对原始凭证，确认后再修正数据")
    slides.append({"title": "下一步动作", "kicker": "行动",
                   "bullets": actions or ["补充数据后再做一轮会诊"], "chart": None})

    spec = {"meta": meta, "slides": slides}
    return spec


def deck_html(spec, meta, bundle=None):
    """渲染 16:9 幻灯片。传入 bundle 时，走势页与结构页会内嵌同源 SVG 图表。"""
    course = comp = {}
    if bundle:
        course = (bundle.get("lanes") or {}).get("course") or {}
        comp = (bundle.get("lanes") or {}).get("composition") or {}

    cards = []
    for i, s in enumerate(spec["slides"], 1):
        body = "".join(f"<li>{esc(b)}</li>" for b in s["bullets"])
        viz = ""
        if s.get("chart") == "line" and course.get("available"):
            viz = line_chart(course.get("series") or [], course.get("forecast"),
                             width=470, height=250,
                             unit=(course.get("metric") or {}).get("unit") or "")
        elif s.get("chart") == "bar" and comp.get("available"):
            viz = bar_chart(comp.get("rows") or [], width=470)
        if viz:
            inner = (f'<div class="cols"><div class="txt"><ul>{body}</ul></div>'
                     f'<div class="viz">{viz}</div></div>')
            cls = "slide has-chart"
        else:
            inner = f"<ul>{body}</ul>"
            cls = "slide"
        cards.append(f"""<section class="{cls}">
  <div class="s-kicker">{esc(s.get('kicker',''))}</div>
  <h2>{esc(s['title'])}</h2>
  {inner}
  <div class="s-num">{i:02d}</div>
</section>""")
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"/>
<title>{esc(meta.get('title'))} · 幻灯片</title>
<style>
body{{margin:0;background:#0B1220;font-family:"Microsoft YaHei","PingFang SC",system-ui,sans-serif}}
.slide{{position:relative;width:960px;height:540px;margin:24px auto;background:#fff;border-radius:12px;padding:48px 56px;box-sizing:border-box;overflow:hidden;page-break-after:always}}
.s-kicker{{font-size:12px;letter-spacing:.18em;color:{PALETTE['accent']};text-transform:uppercase;margin-bottom:10px}}
.slide h2{{font-size:32px;margin:0 0 22px;color:{PALETTE['ink']};line-height:1.25}}
.slide ul{{margin:0;padding-left:20px}}
.slide li{{font-size:17px;line-height:1.8;color:#22303F;margin-bottom:9px}}
.cols{{display:grid;grid-template-columns:1fr 1fr;gap:26px;align-items:center}}
.has-chart li{{font-size:14.5px;line-height:1.7;margin-bottom:8px}}
.viz svg{{width:100%;height:auto}}
.s-num{{position:absolute;right:40px;bottom:24px;font-size:52px;font-weight:800;color:#EDF2F9}}
@media print{{body{{background:#fff}}.slide{{margin:0;border-radius:0;box-shadow:none}}@page{{size:960px 540px;margin:0}}}}
</style></head><body>{''.join(cards)}</body></html>"""


def onepager_md(bundle, profile, verify_report, meta):
    course, comp, integ, findings = _collect(bundle)
    live = [f for f in findings if f.get("verified") is not False and f.get("grade") != "D"]
    stats = course.get("stats") or {}
    lines = [f"# {meta['title']}", "",
             f"- 数据源：{profile['source']}（{profile['rows']} 行 × {profile['cols']} 列）",
             f"- 可信度：{profile['quality']['grade']}（{profile['quality']['score']} 分，闸门 {profile['quality']['gate']}）",
             f"- 复算：{verify_report.get('overall')}（{verify_report.get('passed')}/{verify_report.get('checked')} 通过）", "",
             "## 三句话", ""]
    heads = pick_headlines(findings, 3)
    if heads:
        for i, f in enumerate(heads, 1):
            lines.append(f"{i}. {f['claim']}（{f.get('grade')} 级，{_verified_badge_text(f)}）")
    else:
        lines.append("1. 本次没有达到可结论门槛的发现，建议补充数据。")
    lines += ["", "## 关键数字", ""]
    if stats:
        lines += [f"- 区间变化：{fmt_pct(stats.get('change_pct'))}（{course['series'][0]['period']} → {course['series'][-1]['period']}）",
                  f"- 最新一期：{fmt_num(stats.get('last'))}，环比 {fmt_pct((course.get('mom') or {}).get('change_pct'))}",
                  f"- 拟合优度 R²：{fmt_num(stats.get('r2'))}"]
    if comp.get("available"):
        lines.append(f"- 结构集中度：HHI {comp['hhi']:,.0f}（{comp['hhi_level']}），前两名合计 {comp['top2_share']:.2f}%")
    if integ.get("counts"):
        c = integ["counts"]
        lines.append(f"- 异常：高危 {c['CRITICAL']} / 关注 {c['WARN']} / 提示 {c['INFO']}")
    lines += ["", "## 下一步", ""]
    for i in (integ.get("items") or [])[:3]:
        lines.append(f"- [{i['severity']}] {i['message']} → {i['action']}")
    if not integ.get("items"):
        lines.append("- 无高危项，可直接进入汇报")
    lines += ["", f"> 由 {meta['product']} 生成 · {meta['author']} · v{meta['version']}"]
    return "\n".join(lines)


def _verified_badge_text(f):
    if f.get("verified") is True:
        return "已复算"
    if f.get("verified") is None:
        return "未复算"
    return "已作废"


def build_xlsx(bundle, profile, verify_report, path):
    course, comp, integ, findings = _collect(bundle)
    sheets = []
    q = profile["quality"]
    overview = [["数据源", profile["source"]], ["工作表", profile["sheet"]],
                ["行数", profile["rows"]], ["列数", profile["cols"]],
                ["可信度", f"{q['grade']}（{q['score']} 分）"], ["闸门", q["gate"]],
                ["结论复算", f"{verify_report.get('overall')}（{verify_report.get('passed')}/{verify_report.get('checked')}）"],
                ["生成时间", _dt.datetime.now().strftime("%Y-%m-%d %H:%M")], [], ["体检发现", ""]]
    for i in q["issues"]:
        overview.append([i["level"], i["message"]])
    sheets.append(Sheet("00-概览", ["项目", "内容"], overview, [22, 90]))

    if course.get("available"):
        rows = [["期次", "数值", "类型"]]
        for p in course["series"]:
            rows.append([p["period"], p["value"], "实际"])
        for p in (course.get("forecast") or {}).get("points") or []:
            rows.append([p["period"], p["value"], "外推"])
        s = course["stats"]
        rows += [[], ["区间变化%", s.get("change_pct")], ["斜率/期", s.get("slope_per_period")],
                 ["R²", s.get("r2")], ["波动系数", s.get("cv")], ["方向", s.get("direction")]]
        sheets.append(Sheet("01-走势", rows[0], rows[1:], [16, 18, 12], number_cols={1}))

    if comp.get("available"):
        rows = [["分组", "数值", "占比%", "累计占比%"]]
        rows += [[r["name"], r["value"], r["share"], r["cum_share"]] for r in comp["rows"]]
        rows += [[], ["HHI", comp["hhi"]], ["集中度", comp["hhi_level"]], ["前两名合计%", comp["top2_share"]]]
        sheets.append(Sheet("02-结构", rows[0], rows[1:], [22, 18, 12, 14], number_cols={1}))

    if integ.get("items"):
        rows = [["级别", "字段", "行号", "数值", "说明", "建议动作"]]
        rows += [[i["severity"], i.get("column") or "整行", i.get("row") or "", i.get("value"),
                  i["message"], i["action"]] for i in integ["items"]]
        sheets.append(Sheet("03-异常清单", rows[0], rows[1:], [12, 14, 8, 14, 52, 40], number_cols={3}))

    vrows = [["线", "编号", "复算方式", "报告值", "复算值", "状态"]]
    vrows += [[r["lane"], r["id"], r.get("op", ""), r.get("claim_value"), r.get("recomputed"), r["status"]]
              for r in verify_report.get("results") or []]
    sheets.append(Sheet("04-证据链", vrows[0], vrows[1:], [14, 8, 18, 14, 14, 10], number_cols={3, 4}))

    prows = [["列名", "类型", "非空", "缺失", "缺失率%", "唯一值"]]
    for c in profile["columns"]:
        prows.append([c["name"], c["kind"], c["non_null"], c["null"], c["null_rate"], c.get("distinct")])
    sheets.append(Sheet("05-体检明细", prows[0], prows[1:], [20, 10, 10, 10, 12, 12]))

    frows = [["线", "编号", "等级", "复算", "结论"]]
    for f in findings:
        frows.append([f.get("lane"), f.get("id"), f.get("grade"), _verified_badge_text(f), f.get("claim")])
    sheets.append(Sheet("06-结论清单", frows[0], frows[1:], [14, 8, 8, 10, 90]))

    write_workbook(path, sheets)
    return path
