#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""算卦台 · 排盘引擎命令行

统一入口，所有子命令都可输出结构化 JSON，并可直接渲染成单文件 HTML。

用法示例
  python oracle.py today
  python oracle.py day --date 2026-10-26 --html out/day.html
  python oracle.py pick --from 2026-11-01 --to 2026-11-30 --purpose 嫁娶
  python oracle.py bazi --date 1990-06-15 --time 08:30 --gender 女 --lon 104.06 --json
  python oracle.py ziwei --date 1990-06-15 --time 08:30 --gender 女 --lon 104.06 --html out/ziwei.html
  python oracle.py meihua --numbers 3 8
  python oracle.py liuyao --toss
  python oracle.py tarot --spread three --question "这个offer接不接"
  python oracle.py solar --year 2026
  python oracle.py lunar --date 2026-10-26

作者：虫志龙 <47190078@qq.com>
"""

import argparse
import json
import os
import sys
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import astro
import calendar_core as cc
import bazi as bazi_mod
import almanac as almanac_mod
import divination as div_mod
import tarot as tarot_mod
import ziwei as ziwei_mod
import render


def _dt(date_str, time_str="12:00"):
    y, m, d = [int(x) for x in date_str.replace("/", "-").split("-")]
    hh, mm = [int(x) for x in time_str.replace("：", ":").split(":")]
    return datetime(y, m, d, hh, mm, tzinfo=astro.CST)


def _load_notes(path):
    if not path:
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _emit(data, args, kind=None, title=""):
    if getattr(args, "json", False):
        text = json.dumps(data, ensure_ascii=False, indent=2)
        if getattr(args, "out_json", None):
            _write(args.out_json, text)
        print(text)
        return
    if getattr(args, "html", None) and kind:
        notes = _load_notes(getattr(args, "notes", None))
        path = render.render(kind, data, notes, args.html)
        print("已生成：%s" % os.path.abspath(args.html))
        if getattr(args, "out_json", None):
            _write(args.out_json, json.dumps(data, ensure_ascii=False, indent=2))
        return
    print(_summary(kind, data))


def _write(path, text):
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _summary(kind, data):
    lines = []
    if kind == "bazi":
        p = data["pillars"]
        lines.append("四柱：%s %s %s %s（%s）" % (p["year"], p["month"], p["day"], p["hour"], data["lunar"]))
        lines.append("真太阳时：%s" % data["true_solar_time"])
        lines.append("日主：%s%s，旺衰粗判：%s（同类+印星 %.1f%%）"
                     % (data["day_master"]["gan"], data["day_master"]["element"],
                        data["strength"]["level"], data["strength"]["support_percent"]))
        lines.append("五行：%s" % "、".join("%s %.1f%%" % (k, v) for k, v in data["wuxing"]["percent"].items()))
        lines.append("空亡：%s　起运：%s 岁（%s）" % (data["xunkong"]["day"],
                                              data["dayun"]["meta"]["start_age"],
                                              "顺行" if data["dayun"]["meta"]["forward"] else "逆行"))
        lines.append("大运：%s" % " ".join("%s(%s)" % (d["ganzhi"], d["start_age"])
                                          for d in data["dayun"]["list"][:6]))
        if data["nearby_terms"]:
            lines.append("交界提示：" + "；".join("%s 相差 %.0f 分钟" % (t["term"], t["gap_minutes"])
                                              for t in data["nearby_terms"]))
    elif kind == "ziwei":
        lines.append("农历：%s　时辰：%s时　年：%s" % (data["lunar"], data["hour_zhi"], data["year_ganzhi"]))
        lines.append("命宫：%s（%s）　身宫：%s　五行局：%s"
                     % (data["ming_palace"]["zhi"], data["ming_palace"]["ganzhi"],
                        data["shen_palace"]["zhi"], data["ju"]["name"]))
        lines.append("紫微：%s　天府：%s" % (data["ziwei"]["zhi"], data["tianfu"]["zhi"]))
        lines.append("四化：" + "、".join("%s化%s" % (v, k) for k, v in data["sihua"].items()))
        for item in data["palaces"]:
            if item["stars"]:
                lines.append("  %s %s：%s" % (item["palace"], item["palace_zhi"],
                                              "、".join(s["name"] for s in item["stars"])))
    elif kind == "meihua":
        lines.append("本卦：%s　互卦：%s　变卦：%s　动爻：第%d爻"
                     % (data["ben"]["name"], data["hu"]["name"], data["bian"]["name"], data["moving_line"]))
        lines.append("体 %s(%s) / 用 %s(%s)：%s —— %s"
                     % (data["ti_yong"]["ti"]["trigram"], data["ti_yong"]["ti"]["element"],
                        data["ti_yong"]["yong"]["trigram"], data["ti_yong"]["yong"]["element"],
                        data["ti_yong"]["relation"], data["ti_yong"]["verdict"]))
    elif kind == "liuyao":
        lines.append("本卦：%s（%s，%s，世%d 应%d）"
                     % (data["ben"]["name"], data["palace"]["name"], data["palace"]["step"],
                        data["palace"]["shi"], data["palace"]["ying"]))
        lines.append("变卦：%s　动爻：%s" % (data["bian"].get("name") or "无（六爻皆静）",
                                        "、".join("第%d爻" % m for m in data["moving"]) or "无"))
        lines.append("日辰：%s　旬空：%s" % (data["day_ganzhi"], data["xunkong"]))
        for y in reversed(data["yao"]):
            lines.append("  %d爻 %s %s %s %s%s%s" % (
                y["position"], "阳" if y["yin_yang"] == "阳" else "阴",
                y["liushen"], y["liuqin"], y["gan"] + y["zhi"],
                (" 世" if y["shi_ying"] == "世" else (" 应" if y["shi_ying"] == "应" else "")),
                " 动" if y["moving"] else ""))
    elif kind == "tarot":
        lines.append("牌阵：%s" % data["spread"])
        for c in data["cards"]:
            lines.append("  %s：%s（%s）— %s" % (c["position_name"], c["name"], c["orientation"], c["message"]))
    elif kind == "almanac":
        if "candidates" in data:
            lines.append("择日候选：%s（%s ~ %s）" % (data["purpose"], data["range"][0], data["range"][1]))
            for c in data["candidates"]:
                lines.append("  %s %s %s｜%s %s %s｜评分 %s｜吉时 %s"
                             % (c["date"], c["ganzhi"], c["lunar"], c["jianchu"],
                                c["day_god"], c["xiu"], c["score"], "、".join(c["good_hours"])))
            lines.append("说明：%s" % data["note"])
        else:
            lines.append("%s 星期%s　%s　%s" % (data["date"], data["weekday"], data["lunar"], data["ganzhi"]))
            lines.append("建除：%s　值神：%s（%s）　宿：%s（%s）"
                         % (data["jianchu"], data["day_god"], data["day_god_luck"],
                            data["xiu"], data["xiu_luck"]))
            lines.append("冲：%s　煞%s　财神%s　喜神%s" % (data["chong"], data["sha_direction"],
                                                    data["caishen"], data["xishen"]))
            lines.append("吉时：%s" % "、".join(h["zhi"] for h in data["good_hours"]))
            lines.append("宜：%s" % "、".join(data["yi"]))
            lines.append("忌：%s" % "、".join(data["ji"]))
    else:
        lines.append(json.dumps(data, ensure_ascii=False, indent=2))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="算卦台 · 传统术数排盘引擎")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--json", action="store_true", help="输出 JSON")
        p.add_argument("--out-json", help="把 JSON 另存为文件")
        p.add_argument("--html", help="渲染单文件 HTML 到指定路径")
        p.add_argument("--notes", help="解读内容 JSON（summary/sections/actions/one_line）")

    p = sub.add_parser("today", help="今日日课")
    common(p)
    p.add_argument("--date", default=None)

    p = sub.add_parser("day", help="指定日期的日课")
    common(p)
    p.add_argument("--date", required=True)

    p = sub.add_parser("pick", help="按用途筛候选日")
    common(p)
    p.add_argument("--from", dest="start", required=True)
    p.add_argument("--to", dest="end", required=True)
    p.add_argument("--purpose", default="通用")
    p.add_argument("--avoid-zhi", default=None, help="需要回避的地支（如生肖属兔传 卯）")
    p.add_argument("--limit", type=int, default=8)

    p = sub.add_parser("bazi", help="四柱八字")
    common(p)
    p.add_argument("--date", required=True)
    p.add_argument("--time", default="12:00")
    p.add_argument("--gender", required=True, choices=["男", "女"])
    p.add_argument("--lon", type=float, default=None, help="出生地东经度数")
    p.add_argument("--day-boundary", default="23:00", choices=["23:00", "00:00"])
    p.add_argument("--years", type=int, default=8)

    p = sub.add_parser("ziwei", help="紫微斗数")
    common(p)
    p.add_argument("--date", required=True)
    p.add_argument("--time", default="12:00")
    p.add_argument("--gender", required=True, choices=["男", "女"])
    p.add_argument("--lon", type=float, default=None)

    p = sub.add_parser("meihua", help="梅花易数起卦")
    common(p)
    p.add_argument("--numbers", nargs=2, type=int, default=None)
    p.add_argument("--date", default=None)
    p.add_argument("--time", default=None)

    p = sub.add_parser("liuyao", help="六爻起卦")
    common(p)
    p.add_argument("--numbers", nargs=6, type=int, default=None)
    p.add_argument("--toss", action="store_true", help="三钱摇卦（默认）")

    p = sub.add_parser("tarot", help="塔罗抽牌")
    common(p)
    p.add_argument("--spread", default="three",
                   choices=["single", "three", "three_time", "five", "celtic"])
    p.add_argument("--question", default="")

    p = sub.add_parser("solar", help="某年二十四节气时刻")
    common(p)
    p.add_argument("--year", type=int, required=True)

    p = sub.add_parser("lunar", help="公历↔农历")
    common(p)
    p.add_argument("--date", default=None)
    p.add_argument("--lunar", nargs=3, default=None, metavar=("YEAR", "MONTH", "DAY"))
    p.add_argument("--leap", action="store_true")

    args = ap.parse_args(argv)

    if args.cmd == "today":
        d = date.today() if not args.date else date(*[int(x) for x in args.date.split("-")])
        data = almanac_mod.day_info(d)
        _emit(data, args, "almanac")

    elif args.cmd == "day":
        d = date(*[int(x) for x in args.date.replace("/", "-").split("-")])
        data = almanac_mod.day_info(d)
        _emit(data, args, "almanac")

    elif args.cmd == "pick":
        s = date(*[int(x) for x in args.start.replace("/", "-").split("-")])
        e = date(*[int(x) for x in args.end.replace("/", "-").split("-")])
        data = almanac_mod.pick_days(s, e, args.purpose, args.avoid_zhi, args.limit)
        _emit(data, args, "almanac")

    elif args.cmd == "bazi":
        dt = _dt(args.date, args.time)
        data = bazi_mod.chart(dt, args.gender, longitude=args.lon,
                              day_boundary=args.day_boundary, liunian_years=args.years)
        _emit(data, args, "bazi")

    elif args.cmd == "ziwei":
        dt = _dt(args.date, args.time)
        data = ziwei_mod.chart(dt, args.gender, longitude=args.lon)
        _emit(data, args, "ziwei")

    elif args.cmd == "meihua":
        if args.numbers:
            data = div_mod.meihua_by_numbers(args.numbers[0], args.numbers[1])
        else:
            dt = _dt(args.date, args.time) if args.date else datetime.now(astro.CST)
            data = div_mod.meihua_by_time(dt)
        _emit(data, args, "meihua")

    elif args.cmd == "liuyao":
        if args.numbers:
            data = div_mod.liuyao_by_numbers(args.numbers)
        else:
            data = div_mod.liuyao_toss()
        _emit(data, args, "liuyao")

    elif args.cmd == "tarot":
        data = tarot_mod.draw(args.spread, args.question)
        _emit(data, args, "tarot")

    elif args.cmd == "solar":
        items = astro.solar_terms_of_year(args.year)
        data = {"year": args.year,
                "terms": [{"name": n, "time": t.strftime("%Y-%m-%d %H:%M:%S")} for n, t in items]}
        if args.json:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            for it in data["terms"]:
                print("%s  %s" % (it["name"], it["time"]))

    elif args.cmd == "lunar":
        if args.lunar:
            y, m, dd = [int(x) for x in args.lunar]
            s = cc.lunar_to_solar(y, m, dd, args.leap)
            data = {"lunar": "%d年%s%s" % (y, cc.lunar_month_name(m, args.leap), cc.lunar_day_name(dd)),
                    "solar": str(s), "ganzhi_day": cc.day_ganzhi(s)}
        else:
            d = date(*[int(x) for x in (args.date or str(date.today())).split("-")])
            ly, lm, ld, leap = cc.solar_to_lunar(d)
            data = {"solar": str(d), "lunar": cc.lunar_text(d),
                    "lunar_raw": {"year": ly, "month": lm, "day": ld, "leap": leap},
                    "ganzhi_day": cc.day_ganzhi(d)}
        print(json.dumps(data, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
