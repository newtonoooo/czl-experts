#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""图册渲染 render.py

把引擎算出的结构化数据渲染成单文件 HTML（不依赖外链资源，可直接打开/打印/发送）。
每个流派一套独立视觉语言：
  八字 黑金 / 紫微 深蓝紫 / 梅花 素纸水墨 / 六爻 墨朱竹简 / 塔罗 深紫鎏金 / 择日 墨绿古铜

排版铁律（已在本文件内固化）：
  - 徽章一律 inline，禁止 position:absolute 浮层
  - 底部固定免责声明
  - 720px 以下降为单列

作者：虫志龙 <47190078@qq.com>
"""

import html
import json
import os

DISCLAIMER = ("⚠️ 本页由 AI 依据传统术数规则整理，属文化研究与娱乐参考，不构成医疗、法律、"
              "财务或投资建议。命理是参考，不是定数；涉及健康、法律、重大财务决策请咨询相应专业人士。")

PALETTES = {
    "bazi": {"bg": "#0e0b08", "panel": "#171310", "line": "#2e2519", "gold": "#d4af6e",
             "bright": "#f3d99c", "ink": "#ece4d3", "muted": "#9a8f7d", "accent": "#c44a3c",
             "name": "子平八字", "en": "Four Pillars"},
    "ziwei": {"bg": "#0a0e2a", "panel": "#131a3d", "line": "#27305c", "gold": "#ffd66e",
              "bright": "#e8e4ff", "ink": "#dfe0f5", "muted": "#8d92bd", "accent": "#a890ff",
              "name": "紫微斗数", "en": "Purple Star Astrology"},
    "meihua": {"bg": "#f3eee2", "panel": "#faf6e8", "line": "#d8cfb8", "gold": "#8a6824",
               "bright": "#2a2418", "ink": "#1f1c15", "muted": "#6f6656", "accent": "#6890a8",
               "name": "梅花易数", "en": "Plum Blossom"},
    "liuyao": {"bg": "#15110c", "panel": "#1c1812", "line": "#332a1d", "gold": "#c69838",
               "bright": "#e8cf98", "ink": "#e6dcc6", "muted": "#94856c", "accent": "#b8341e",
               "name": "六爻纳甲", "en": "Six Lines"},
    "tarot": {"bg": "#1a1133", "panel": "#241847", "line": "#3a2a63", "gold": "#d4af37",
              "bright": "#f0e3b8", "ink": "#e8dcc0", "muted": "#9d90b8", "accent": "#c44a3c",
              "name": "塔罗", "en": "Tarot"},
    "almanac": {"bg": "#0f1a1a", "panel": "#162422", "line": "#24403a", "gold": "#e0b555",
                "bright": "#6dcbbf", "ink": "#dcece6", "muted": "#84a79e", "accent": "#d85848",
                "name": "择日择时", "en": "Day Selection"},
}

ELEMENT_COLOR = {"木": "#6b9a5c", "火": "#c44a3c", "土": "#b08a4a", "金": "#c9c2ae", "水": "#5a86b8"}


def _e(text):
    return html.escape(str(text), quote=True)


def _css(p):
    return _CSS_T.substitute(p)


_CSS_T = __import__("string").Template("""
:root{--bg:$bg;--panel:$panel;--line:$line;--gold:$gold;--bright:$bright;
--ink:$ink;--muted:$muted;--accent:$accent;}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);
font-family:"PingFang SC","Hiragino Sans GB","Microsoft YaHei",STSong,serif;
line-height:1.75;padding:28px 18px 60px;-webkit-font-smoothing:antialiased}
.wrap{max-width:940px;margin:0 auto}
header{border-bottom:1px solid var(--line);padding-bottom:16px;margin-bottom:26px}
.title{font-size:26px;letter-spacing:.14em;color:var(--gold);font-weight:600}
.subtitle{font-size:12px;letter-spacing:.28em;color:var(--muted);text-transform:uppercase;margin-top:6px}
.meta{margin-top:12px;font-size:13px;color:var(--muted);line-height:2}
.meta b{color:var(--bright);font-weight:500}
section{margin:26px 0}
h2{font-size:15px;letter-spacing:.1em;color:var(--gold);font-weight:600;margin-bottom:14px;
padding-left:10px;border-left:3px solid var(--gold)}
.grid{display:grid;gap:12px}
.g4{grid-template-columns:repeat(4,1fr)}
.g3{grid-template-columns:repeat(3,1fr)}
.g2{grid-template-columns:repeat(2,1fr)}
.card{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:14px 16px}
.card .k{font-size:11px;letter-spacing:.2em;color:var(--muted);margin-bottom:6px}
.card .v{font-size:20px;color:var(--bright);letter-spacing:.06em}
.card .s{font-size:12px;color:var(--muted);margin-top:6px;line-height:1.7}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:9px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{color:var(--muted);font-weight:500;font-size:11px;letter-spacing:.12em}
.badge{display:inline-block;font-size:11px;padding:1px 7px;border-radius:3px;
border:1px solid var(--line);color:var(--bright);margin-left:6px;line-height:1.6}
.badge.gold{border-color:var(--gold);color:var(--gold)}
.badge.red{border-color:var(--accent);color:var(--accent)}
.bar{height:7px;background:var(--line);border-radius:4px;overflow:hidden;margin-top:7px}
.bar i{display:block;height:100%;border-radius:4px}
.note{font-size:12px;color:var(--muted);line-height:1.9;margin-top:10px}
blockquote{border-left:3px solid var(--gold);padding:4px 0 4px 14px;color:var(--bright);
font-size:16px;line-height:1.9;background:linear-gradient(90deg,rgba(255,255,255,.03),transparent)}
ul{list-style:none}li{padding-left:16px;position:relative;margin:6px 0;font-size:13.5px}
li:before{content:"·";position:absolute;left:4px;color:var(--gold)}
.disclaimer{margin-top:38px;border:1px dashed rgba(196,74,60,.55);border-radius:6px;
padding:14px 16px;font-size:11.5px;color:var(--muted);line-height:1.9}
.timeline{display:flex;gap:8px;overflow-x:auto;padding-bottom:6px}
.tl-item{min-width:104px;background:var(--panel);border:1px solid var(--line);
border-radius:5px;padding:10px;text-align:center}
.tl-item .a{font-size:11px;color:var(--muted)}
.tl-item .b{font-size:15px;color:var(--bright);margin:4px 0}
.tl-item.cur{border-color:var(--gold)}
@media(max-width:720px){
.g4,.g3,.g2{grid-template-columns:1fr}
body{padding:18px 12px 48px}
.title{font-size:21px}
.card .v{font-size:17px}
table{font-size:12px}
th,td{padding:7px 5px}
}
""")


def _plain_block(plain):
    """白话版：放在盘面之前，让不懂术语的人先读懂结论。"""
    if not plain:
        return ""
    parts = ['<section><h2>先说人话</h2>']
    if plain.get("one_line"):
        parts.append('<blockquote style="font-size:18px">%s</blockquote>' % _e(plain["one_line"]))
    for sec in plain.get("sections", []):
        items = "".join("<li>%s</li>" % _e(x) for x in sec.get("items", []))
        para = "<p style='font-size:14.5px;margin-top:6px'>%s</p>" % _e(sec["body"]) if sec.get("body") else ""
        parts.append('<h3 style="font-size:14px;color:var(--gold);margin:18px 0 4px;letter-spacing:.06em">%s</h3>%s%s'
                     % (_e(sec["title"]), para, "<ul>%s</ul>" % items if items else ""))
    if plain.get("glossary"):
        rows = "".join('<tr><td>%s</td><td>%s</td><td>%s</td></tr>'
                       % (_e(g["term"]), _e(g["say"]), _e(g["you"])) for g in plain["glossary"])
        parts.append('<h3 style="font-size:14px;color:var(--gold);margin:20px 0 8px">术语对照</h3>'
                     '<table><tr><th>术语</th><th>白话</th><th>在你身上</th></tr>%s</table>' % rows)
    if plain.get("actions"):
        parts.append('<h3 style="font-size:14px;color:var(--gold);margin:20px 0 4px">能做的事</h3><ul>%s</ul>'
                     % "".join("<li>%s</li>" % _e(x) for x in plain["actions"]))
    if plain.get("misread"):
        parts.append('<div class="note" style="margin-top:16px"><b style="color:var(--bright)">'
                     '几个容易误解的地方</b><br>%s</div>'
                     % "<br>".join("· " + _e(x) for x in plain["misread"]))
    parts.append("</section>")
    return "".join(parts)


def _page(palette, title, en, meta_rows, body, notes):
    p = PALETTES[palette]
    meta = "".join("<div>%s <b>%s</b></div>" % (_e(k), _e(v)) for k, v in meta_rows)
    plain_block = _plain_block((notes or {}).get("plain"))
    note_block = ""
    if notes:
        parts = []
        if notes.get("summary"):
            parts.append('<section><h2>总断</h2><blockquote>%s</blockquote></section>'
                         % _e(notes["summary"]))
        for sec in notes.get("sections", []):
            items = "".join("<li>%s</li>" % _e(x) for x in sec.get("items", []))
            listblock = "<ul>%s</ul>" % items if items else ""
            para = "<p style='font-size:14px'>%s</p>" % _e(sec["body"]) if sec.get("body") else ""
            parts.append('<section><h2>%s</h2>%s%s</section>' % (_e(sec["title"]), para, listblock))
        if notes.get("actions"):
            items = "".join("<li>%s</li>" % _e(x) for x in notes["actions"])
            parts.append("<section><h2>可以做的事</h2><ul>%s</ul></section>" % items)
        if notes.get("one_line"):
            parts.append("<section><h2>一句</h2><blockquote>%s</blockquote></section>"
                         % _e(notes["one_line"]))
        note_block = "".join(parts)

    return """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(title)s · %(pname)s</title><style>%(css)s</style></head>
<body><div class="wrap">
<header><div class="title">%(title)s</div>
<div class="subtitle">%(pname)s · %(en)s</div>
<div class="meta">%(meta)s</div></header>
%(plain)s
%(body)s
%(notes)s
<div class="disclaimer">%(disc)s</div>
</div></body></html>""" % {
        "title": _e(title), "pname": _e(p["name"]), "en": _e(en),
        "css": _css(p), "meta": meta, "plain": plain_block, "body": body, "notes": note_block,
        "disc": _e(DISCLAIMER),
    }


# ---------------------------------------------------------------- 八字

def bazi_html(data, notes=None):
    p = PALETTES["bazi"]
    cols = [("年柱", "year"), ("月柱", "month"), ("日柱", "day"), ("时柱", "hour")]
    head = "".join("<th>%s</th>" % c[0] for c in cols)
    rows = []

    def row(label, fn):
        cells = []
        for _, key in cols:
            cells.append("<td>%s</td>" % fn(data["pillars_detail"][key]))
        rows.append("<tr><th>%s</th>%s</tr>" % (label, "".join(cells)))

    row("天干十神", lambda d: _e(d["gan_shishen"]))
    row("干支", lambda d: '<span style="font-size:20px;color:%s;letter-spacing:.1em">%s</span>'
        % (p["gold"], _e(d["ganzhi"])))
    row("五行", lambda d: "%s / %s" % (_e(d["gan_element"]), _e(d["zhi_element"])))
    row("藏干", lambda d: "、".join("%s<span class='badge'>%s</span>" % (_e(x["gan"]), _e(x["shishen"]))
                                  for x in d["cang_gan"]))
    row("纳音", lambda d: _e(d["nayin"]))
    row("日干长生", lambda d: _e(d["changsheng"]))

    wx = data["wuxing"]["percent"]
    bars = "".join(
        '<div style="margin-bottom:10px"><div style="display:flex;justify-content:space-between;'
        'font-size:12px"><span>%s</span><span style="color:%s">%s%%</span></div>'
        '<div class="bar"><i style="width:%s%%;background:%s"></i></div></div>'
        % (e, ELEMENT_COLOR[e], wx[e], max(2, wx[e]), ELEMENT_COLOR[e]) for e in ["木", "火", "土", "金", "水"])

    dy = "".join('<div class="tl-item"><div class="a">%s–%s 岁</div><div class="b">%s</div>'
                 '<div class="a">%s</div></div>'
                 % (d["start_age"], d["end_age"], _e(d["ganzhi"]), _e(d["shishen"]))
                 for d in data["dayun"]["list"][:9])

    ln = "".join("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s 岁</td></tr>"
                 % (l["year"], _e(l["ganzhi"]), _e(l["shishen"]), l["age"]) for l in data["liunian"])

    shensha = "、".join("%s（%s）" % (_e(s["name"]), "".join(s["hit"])) for s in data["shensha"]) or "未现"
    rel = "、".join("%s%s" % (_e(r["type"]), "".join(r["members"])) for r in data["zhi_relations"]) or "无特殊合冲"

    meta = [("公历", data["solar"]), ("真太阳时", data["true_solar_time"]), ("农历", data["lunar"]),
            ("性别", data["gender"]), ("生肖", data["shengxiao"]),
            ("月令", "%s（%s 交节）" % (data["month_jie"]["name"], data["month_jie"]["time"]))]

    body = """
<section><div class="grid g4">
<div class="card"><div class="k">日主</div><div class="v">%(dm)s %(el)s</div>
<div class="s">%(pol)s干 · 月令临 %(cs)s</div></div>
<div class="card"><div class="k">旺衰粗判</div><div class="v">%(lvl)s</div>
<div class="s">同类+印星 %(sup)s%%</div></div>
<div class="card"><div class="k">空亡</div><div class="v">%(xk)s</div>
<div class="s">以日柱旬空为主</div></div>
<div class="card"><div class="k">起运</div><div class="v">%(age)s 岁</div>
<div class="s">%(dir)s · %(ref)s 交节</div></div>
</div></section>

<section><h2>四柱</h2><table>%(head)s%(rows)s</table>
<div class="note">当月节：%(jie)s（%(jiet)s）。真太阳时校正：经度 %(lon)s°，经度差 %(lond)s 分钟，
均时差 %(eot)s 分钟。</div></section>

<section><h2>五行力量</h2>
<div class="grid g2"><div>%(bars)s</div>
<div class="card"><div class="k">旁证</div><div class="s">%(notes)s</div>
<div class="k" style="margin-top:12px">地支关系</div><div class="s">%(rel)s</div>
<div class="k" style="margin-top:12px">神煞命中</div><div class="s">%(ss)s</div></div></div>
<div class="note">换算口径：天干各计 1.0；地支藏干按本气 1.0、中气 0.4、余气 0.2 折算；月支整体 ×1.5。</div></section>

<section><h2>大运（%(dir2)s）</h2><div class="timeline">%(dy)s</div></section>

<section><h2>流年</h2><table><tr><th>年份</th><th>干支</th><th>十神</th><th>年龄</th></tr>%(ln)s</table></section>

<section><h2>口径披露</h2><div class="note">%(qn)s 大运起运按「三日折一年」换算。
节气时刻由本产品星历引擎计算，误差在 1 分钟内。</div></section>
""" % {
        "dm": _e(data["day_master"]["gan"]), "el": _e(data["day_master"]["element"]),
        "pol": _e(data["day_master"]["polarity"]), "cs": _e(data["day_master"]["changsheng_in_month"]),
        "lvl": _e(data["strength"]["level"]), "sup": data["strength"]["support_percent"],
        "xk": _e(data["xunkong"]["day"]),
        "age": data["dayun"]["meta"]["start_age"],
        "dir": "顺行" if data["dayun"]["meta"]["forward"] else "逆行",
        "ref": data["dayun"]["meta"]["reference_term"],
        "head": head, "rows": "".join(rows),
        "jie": data["month_jie"]["name"], "jiet": data["month_jie"]["time"],
        "lon": data["correction"]["longitude"], "lond": data["correction"]["longitude_offset_minutes"],
        "eot": data["correction"]["equation_of_time_minutes"],
        "bars": bars, "notes": "；".join(_e(n) for n in data["strength"]["notes"]),
        "rel": rel, "ss": shensha,
        "dir2": "顺行" if data["dayun"]["meta"]["forward"] else "逆行",
        "dy": dy, "ln": ln, "qn": _e(data["quant_note"]),
    }
    return _page("bazi", "四柱八字盘", "BaZi Chart", meta, body, notes)


# ---------------------------------------------------------------- 紫微

def ziwei_html(data, notes=None):
    p = PALETTES["ziwei"]
    order = data["palaces"]
    cards = []
    for item in order:
        stars = "".join('<span class="badge %s">%s%s</span>'
                        % ("gold" if s["sihua"] else "", _e(s["name"]),
                           ("·" + "".join(s["sihua"])) if s["sihua"] else "")
                        for s in item["stars"])
        mark = ""
        if item["is_ming"]:
            mark = '<span class="badge red">命</span>'
        elif item["is_shen"]:
            mark = '<span class="badge">身</span>'
        empty = '<span style="font-size:12px;color:%s">空宫</span>' % p["muted"] if item["empty"] else ""
        cards.append(
            '<div class="card" style="%s"><div class="k">%s %s %s</div>'
            '<div class="v" style="font-size:15px">%s</div>'
            '<div class="s">%s</div></div>'
            % ("border-color:%s" % p["accent"] if item["is_ming"] else "",
               _e(item["palace"]), _e(item["palace_zhi"]), mark, _e(item["ganzhi"]),
               stars + empty))

    dy = "".join('<div class="tl-item"><div class="a">%s</div><div class="b" style="font-size:13px">%s</div>'
                 '<div class="a">%s</div></div>'
                 % (_e(d["palace"]), _e(d["palace_zhi"] + "宫"), _e(d["age_range"]))
                 for d in data["dayun"]["list"])

    sh = "、".join("%s化%s" % (_e(v), _e(k)) for k, v in data["sihua"].items())

    meta = [("公历", data["solar"]), ("农历", data["lunar"]), ("时辰", data["hour_zhi"] + "时"),
            ("性别", data["gender"]), ("年干支", data["year_ganzhi"])]

    body = """
<section><div class="grid g4">
<div class="card"><div class="k">命宫</div><div class="v">%(mz)s</div><div class="s">%(mg)s</div></div>
<div class="card"><div class="k">身宫</div><div class="v">%(sz)s</div><div class="s">后天着力处</div></div>
<div class="card"><div class="k">五行局</div><div class="v">%(ju)s</div><div class="s">起运虚岁 %(jn)s</div></div>
<div class="card"><div class="k">紫微 / 天府</div><div class="v" style="font-size:16px">%(zw)s · %(tf)s</div>
<div class="s">生年四化见下</div></div>
</div></section>

<section><h2>生年四化（%(yg)s 年）</h2>
<div class="note" style="font-size:14px;color:%(bright)s">%(sh)s</div></section>

<section><h2>十二宫</h2><div class="grid g3">%(cards)s</div>
<div class="note">命宫起，逆时针依次为兄弟、夫妻、子女、财帛、疾厄、迁移、交友、官禄、田宅、福德、父母。</div></section>

<section><h2>大限（%(dir)s）</h2><div class="timeline">%(dy)s</div>
<div class="note">%(dnote)s</div></section>
""" % {
        "mz": _e(data["ming_palace"]["zhi"]), "mg": _e(data["ming_palace"]["ganzhi"]),
        "sz": _e(data["shen_palace"]["zhi"]), "ju": _e(data["ju"]["name"]),
        "jn": data["ju"]["number"],
        "zw": _e(data["ziwei"]["zhi"]), "tf": _e(data["tianfu"]["zhi"]),
        "yg": _e(data["year_ganzhi"]), "sh": sh, "cards": "".join(cards),
        "dir": "顺行" if data["dayun"]["forward"] else "逆行", "dy": dy,
        "dnote": _e(data["dayun"]["note"]), "bright": p["bright"],
    }
    return _page("ziwei", "紫微斗数盘", "Zi Wei Dou Shu", meta, body, notes)


# ---------------------------------------------------------------- 梅花

def meihua_html(data, notes=None):
    p = PALETTES["meihua"]
    tv = data["ti_yong"]
    meta = [("起卦方式", data["meta"]["method"]), ("依据", data["meta"]["basis"]),
            ("时间", data["meta"]["time"])]
    body = """
<section><div class="grid g3">
<div class="card" style="background:%(panel)s"><div class="k">本卦</div>
<div class="v">%(ben)s</div><div class="s">上%(bu)s 下%(bl)s<br>%(bg)s</div></div>
<div class="card"><div class="k">互卦（过程）</div><div class="v">%(hu)s</div>
<div class="s">上%(hu_u)s 下%(hu_l)s<br>%(hg)s</div></div>
<div class="card"><div class="k">变卦（落点）</div><div class="v">%(bian)s</div>
<div class="s">动爻第 %(mv)s 爻<br>%(bg2)s</div></div>
</div></section>

<section><h2>体用</h2><div class="grid g2">
<div class="card"><div class="k">体（我方）</div><div class="v">%(tt)s %(te)s</div>
<div class="s">%(tn)s</div></div>
<div class="card"><div class="k">用（事方）</div><div class="v">%(yt)s %(ye)s</div>
<div class="s">%(yn)s · 动在%(yp)s</div></div>
</div><div class="note" style="font-size:14px;color:%(ink)s;margin-top:12px">
<b>%(rel)s</b> —— %(verdict)s</div></section>

<section><h2>读卦次第</h2><ul>%(order)s</ul></section>
""" % {
        "panel": p["panel"],
        "ben": _e(data["ben"]["name"]), "bu": _e(data["ben"]["upper"]), "bl": _e(data["ben"]["lower"]),
        "bg": _e(data["ben"]["gloss"]),
        "hu": _e(data["hu"]["name"]), "hu_u": _e(data["hu"]["upper"]), "hu_l": _e(data["hu"]["lower"]),
        "hg": _e(data["hu"]["gloss"]),
        "bian": _e(data["bian"]["name"]), "bg2": _e(data["bian"].get("gloss", "")),
        "mv": data["moving_line"],
        "tt": _e(tv["ti"]["trigram"]), "te": _e(tv["ti"]["element"]), "tn": _e(tv["ti"]["nature"]),
        "yt": _e(tv["yong"]["trigram"]), "ye": _e(tv["yong"]["element"]), "yn": _e(tv["yong"]["nature"]),
        "yp": _e(data["moving_pos"]), "rel": _e(tv["relation"]), "verdict": _e(tv["verdict"]),
        "ink": p["ink"], "order": "".join("<li>%s</li>" % _e(x) for x in data["reading_order"]),
    }
    return _page("meihua", "梅花卦盘", "Plum Blossom Divination", meta, body, notes)


# ---------------------------------------------------------------- 六爻

def liuyao_html(data, notes=None):
    p = PALETTES["liuyao"]
    rows = []
    for y in reversed(data["yao"]):
        mark = '<span class="badge red">动</span>' if y["moving"] else ""
        kong = '<span class="badge">空</span>' if y["kong"] else ""
        sy = ""
        if y["shi_ying"]:
            sy = '<span class="badge gold">' + _e(y["shi_ying"]) + "</span>"
        liuqin = _e(y["liuqin"]) + sy
        symbol = "▬▬" if y["yin_yang"] == "阳" else "▬ ▬"
        rows.append(
            "<tr><td>%d</td><td>%s %s</td><td>%s%s%s</td><td>%s</td>"
            "<td>%s</td><td>%s</td></tr>"
            % (y["position"], symbol, y["yin_yang"], _e(y["liushen"]), mark, kong,
               liuqin, _e(y["gan"] + y["zhi"]), _e(y["element"])))
    bian_rows = "".join("<tr><td>第 %s 爻</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                        % (b["position"], _e(b["zhi"]), _e(b["element"]), _e(b["liuqin"]))
                        for b in data["bian"].get("yao", []))

    meta = [("起卦时间", data["cast_time"]), ("日辰", data["day_ganzhi"]),
            ("旬空", data["xunkong"]), ("动爻", "、".join("第%d爻" % m for m in data["moving"]) or "六爻皆静")]

    body = """
<section><div class="grid g3">
<div class="card"><div class="k">本卦</div><div class="v">%(ben)s</div>
<div class="s">上%(bu)s 下%(bl)s<br>%(bg)s</div></div>
<div class="card"><div class="k">卦宫</div><div class="v">%(pal)s</div>
<div class="s">%(el)s · %(step)s · 世%(shi)s 应%(ying)s</div></div>
<div class="card"><div class="k">变卦</div><div class="v">%(bian)s</div>
<div class="s">%(bg2)s</div></div>
</div></section>

<section><h2>装卦（上爻在下，初爻在上）</h2>
<table><tr><th>爻位</th><th>爻象</th><th>六神</th><th>六亲 / 世应</th><th>纳甲</th><th>五行</th></tr>
%(rows)s</table>
<div class="note">纳甲以京房体例，六亲以本卦卦宫五行为我。旬空之爻当下虚而不实。</div></section>

%(bian_block)s
""" % {
        "ben": _e(data["ben"]["name"]), "bu": _e(data["ben"]["upper"]), "bl": _e(data["ben"]["lower"]),
        "bg": _e(data["ben"]["gloss"]),
        "pal": _e(data["palace"]["name"]), "el": _e(data["palace"]["element"]),
        "step": _e(data["palace"]["step"]), "shi": data["palace"]["shi"], "ying": data["palace"]["ying"],
        "bian": _e(data["bian"].get("name") or "无"), "bg2": _e(data["bian"].get("gloss")
                                                           or data["bian"].get("note", "")),
        "rows": "".join(rows),
        "bian_block": ('<section><h2>变卦诸爻</h2><table><tr><th>爻位</th><th>地支</th>'
                       '<th>五行</th><th>六亲</th></tr>%s</table></section>' % bian_rows)
        if bian_rows else "",
    }
    return _page("liuyao", "六爻卦盘", "Six Lines with Najia", meta, body, notes)


# ---------------------------------------------------------------- 塔罗

def tarot_html(data, notes=None):
    p = PALETTES["tarot"]
    cards = []
    for c in data["cards"]:
        rev = c["orientation"] == "逆位"
        cards.append(
            '<div class="card" style="%s"><div class="k">%s · %s</div>'
            '<div class="v" style="font-size:17px">%s<span class="badge %s">%s</span></div>'
            '<div class="s" style="color:%s">%s</div>'
            '<div class="s" style="margin-top:8px;color:%s">%s</div></div>'
            % ("border-color:%s" % p["accent"] if rev else "",
               _e(c["position_name"]), _e(c["deck"]), _e(c["name"]),
               "red" if rev else "gold", _e(c["orientation"]),
               p["muted"], _e(c["keywords"]), p["ink"], _e(c["message"])))

    meta = [("牌阵", data["spread"]), ("抽牌时间", data["time"])]
    if data.get("question"):
        meta.append(("所问", data["question"]))

    body = """
<section><div class="grid %(cls)s">%(cards)s</div></section>
<section><h2>读牌说明</h2><div class="note">%(note)s</div></section>
""" % {"cls": "g3" if len(data["cards"]) > 2 else "g2", "cards": "".join(cards),
       "note": _e(data["reading_note"])}
    return _page("tarot", "塔罗牌阵", "Tarot Spread", meta, body, notes)


# ---------------------------------------------------------------- 择日

def almanac_html(data, notes=None):
    p = PALETTES["almanac"]
    if "candidates" in data:
        rows = "".join(
            "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
            "<td style='color:%s'>%s</td></tr>"
            % (c["date"], _e(c["ganzhi"]), _e(c["lunar"]), _e(c["jianchu"]),
               _e(c["day_god"]), _e(c["xiu"]),
               p["bright"] if c["score"] >= 4 else p["muted"], c["score"])
            for c in data["candidates"])
        body = """
<section><h2>候选日（%(purpose)s）</h2>
<table><tr><th>日期</th><th>干支</th><th>农历</th><th>建除</th><th>值神</th><th>宿</th><th>评分</th></tr>
%(rows)s</table><div class="note">%(note)s</div></section>
""" % {"purpose": _e(data["purpose"]), "rows": rows, "note": _e(data["note"])}
        return _page("almanac", "择日候选", "Day Selection", [("用途", data["purpose"]),
                                                              ("区间", " ~ ".join(data["range"]))],
                     body, notes)

    hours = "".join('<div class="tl-item %s"><div class="a">%s</div><div class="b">%s</div>'
                    '<div class="a">%s</div></div>'
                    % ("cur" if h["luck"] == "吉" else "", _e(h["zhi"] + "时"),
                       _e(h["god"]), _e(h["range"])) for h in data["hours"])
    meta = [("公历", "%s 星期%s" % (data["date"], data["weekday"])), ("农历", data["lunar"]),
            ("干支", data["ganzhi"]), ("纳音", data["nayin"]), ("当节", data["month_jie"])]
    body = """
<section><div class="grid g4">
<div class="card"><div class="k">建除十二神</div><div class="v">%(jc)s</div><div class="s">当日值神</div></div>
<div class="card"><div class="k">黄道 / 黑道</div><div class="v">%(god)s</div>
<div class="s">%(luck)s</div></div>
<div class="card"><div class="k">二十八宿</div><div class="v">%(xiu)s</div>
<div class="s">%(xluck)s</div></div>
<div class="card"><div class="k">冲煞</div><div class="v">%(chong)s</div>
<div class="s">煞%(sha)s</div></div>
</div></section>

<section><h2>时辰吉凶</h2><div class="timeline">%(hours)s</div>
<div class="note">高亮者为黄道六神（青龙·明堂·金匮·天德·玉堂·司命）所临之时。</div></section>

<section><h2>方位与禁忌</h2><div class="grid g3">
<div class="card"><div class="k">财神 / 喜神</div><div class="v" style="font-size:16px">%(cs)s · %(xs)s</div></div>
<div class="card"><div class="k">旬空</div><div class="v" style="font-size:16px">%(xk)s</div></div>
<div class="card"><div class="k">彭祖百忌</div><div class="s">%(pz)s</div></div>
</div></section>

<section><h2>传统宜忌（建除层面）</h2><div class="grid g2">
<div class="card"><div class="k">宜</div><div class="s">%(yi)s</div></div>
<div class="card"><div class="k">忌</div><div class="s">%(ji)s</div></div>
</div><div class="note">%(note)s</div></section>
""" % {
        "jc": _e(data["jianchu"]), "god": _e(data["day_god"]), "luck": _e(data["day_god_luck"]),
        "xiu": _e(data["xiu"]), "xluck": _e(data["xiu_luck"] + "宿"),
        "chong": _e(data["chong"]), "sha": _e(data["sha_direction"]),
        "hours": hours, "cs": _e(data["caishen"]), "xs": _e(data["xishen"]),
        "xk": _e(data["xunkong"]), "pz": "；".join(_e(x) for x in data["pengzu"]),
        "yi": "、".join(_e(x) for x in data["yi"]), "ji": "、".join(_e(x) for x in data["ji"]),
        "note": _e(data["note"]),
    }
    return _page("almanac", "日课", "Daily Almanac", meta, body, notes)


RENDERERS = {"bazi": bazi_html, "ziwei": ziwei_html, "meihua": meihua_html,
             "liuyao": liuyao_html, "tarot": tarot_html, "almanac": almanac_html}


def render(kind, data, notes=None, out_path=None):
    fn = RENDERERS[kind]
    doc = fn(data, notes)
    if out_path:
        d = os.path.dirname(os.path.abspath(out_path))
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(doc)
    return doc
