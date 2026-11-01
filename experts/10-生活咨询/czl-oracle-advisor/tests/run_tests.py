#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""司南 · 引擎回归测试

运行：python run_tests.py
对照数据来源：
  - 节气/农历：中国科学院紫金山天文台《二〇二六年日历资料》、公开报道的立春时刻
  - 日柱/黄历：公开黄历站点 2026-10-26 条目（干支、建除、值神、宿、冲煞、财神喜神、吉时）
  - 春节：2020–2035 年公认日期
  - 卦象/星曜：京房八宫与紫微斗数通行排布规则
"""
import os
import sys
import json
import subprocess
import tempfile
from datetime import date, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
CANDIDATES = [
    os.environ.get("SINAN_ENGINE", ""),
    os.path.join(HERE, "..", "skills", "czl-oracle-engine", "scripts"),
    os.path.join(os.path.expanduser("~"), ".workbuddy", "plugins", "marketplaces", "my-experts",
                 "plugins", "czl-oracle-advisor", "skills", "czl-oracle-engine", "scripts"),
]
SCRIPTS = next((os.path.abspath(p) for p in CANDIDATES
                if p and os.path.isfile(os.path.join(p, "oracle.py"))), None)
if not SCRIPTS:
    raise SystemExit("找不到引擎脚本，请设置环境变量 SINAN_ENGINE 指向 scripts 目录")
sys.path.insert(0, SCRIPTS)

import astro
import calendar_core as cc
import bazi as bazi_mod
import almanac as alm
import divination as dv
import tarot as tarot_mod
import ziwei as ziwei_mod

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  PASS  " if cond else "  FAIL  ") + name + ("   " + detail if detail else ""))


def near(actual_dt, expect_str, tol_sec=60):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            exp = datetime.strptime(expect_str, fmt).replace(tzinfo=astro.CST)
            break
        except ValueError:
            exp = None
    if exp is None:
        return False, 99999
    d = (actual_dt - exp).total_seconds()
    return abs(d) <= tol_sec, d


print("== A. 历法核心 ==")
check("JD(2000-01-01 12:00 UT) = 2451545.0",
      abs(astro.jd_from_datetime(datetime(2000, 1, 1, 12, tzinfo=astro.timezone.utc)) - 2451545.0) < 1e-6)
check("JD 往返一致", abs(astro.jd_from_datetime(
    astro.datetime_from_jd(2461340.0, astro.timezone.utc)) - 2461340.0) < 1e-6)

ok, d = near(astro.solar_term_time(2026, "立春"), "2026-02-04 04:01:51")
check("2026 立春 vs 紫金山 04:01:51", ok, "差 %.0f 秒" % d)
ok, d = near(astro.solar_term_time(2024, "立春"), "2024-02-04 16:26:53")
check("2024 立春 vs 公开报道 16:26:53", ok, "差 %.0f 秒" % d)
ok, d = near(astro.solar_term_time(2026, "春分"), "2026-03-20 22:46")
check("2026 春分 vs 紫金山 22:46", ok, "差 %.0f 秒" % d)
ok, d = near(astro.solar_term_time(2026, "清明"), "2026-04-05 02:40")
check("2026 清明 vs 紫金山 02:40", ok, "差 %.0f 秒" % d)
ok, d = near(astro.solar_term_time(2026, "小寒"), "2026-01-05 16:23")
check("2026 小寒 vs 紫金山 16:23", ok, "差 %.0f 秒" % d)
ok, d = near(astro.solar_term_time(2026, "立夏"), "2026-05-05 19:49")
check("2026 立夏 vs 紫金山 19:49", ok, "差 %.0f 秒" % d)

SPRING = {2020: "2020-01-25", 2021: "2021-02-12", 2022: "2022-02-01", 2023: "2023-01-22",
          2024: "2024-02-10", 2025: "2025-01-29", 2026: "2026-02-17", 2027: "2027-02-06",
          2028: "2028-01-26", 2029: "2029-02-13", 2030: "2030-02-03", 2031: "2031-01-23",
          2032: "2032-02-11", 2033: "2033-01-31", 2034: "2034-02-19", 2035: "2035-02-08"}
bad = [y for y, s in SPRING.items() if str(cc._lunar_year_start(y)) != s]
check("2020–2035 春节 16 年全对", not bad, "错: %s" % bad if bad else "16/16")

leaps = {}
for y in (2017, 2020, 2023, 2025, 2028, 2033, 2036):
    leaps[y] = [cc.lunar_month_name(n, l) for _s, n, l in cc.lunar_year_months(y) if l]
check("闰月：2023 闰二月 / 2025 闰六月 / 2033 闰冬月",
      leaps[2023] == ["闰二月"] and leaps[2025] == ["闰六月"] and leaps[2033] == ["闰冬月"],
      str(leaps))

m2033 = {(n, l): s for s, n, l in cc.lunar_year_months(2033)}
dz33 = astro.solar_term_time(2033, "冬至").date()
nov_start = m2033[(11, False)]
dec_start = m2033[(11, True)]
check("2033 冬至落在十一月内（十一月界定正确）",
      nov_start <= dz33 < dec_start, "冬至 %s ∈ [%s, %s)" % (dz33, nov_start, dec_start))

check("日柱 2026-10-26 = 癸酉", cc.day_ganzhi(date(2026, 10, 26)) == "癸酉")
check("农历 2026-10-26 = 九月十七", cc.lunar_text(date(2026, 10, 26)).endswith("九月十七"))

print("== B. 黄历对照（2026-10-26 公开黄历）==")
info = alm.day_info(date(2026, 10, 26))
check("干支 癸酉 / 纳音 剑锋金", info["ganzhi"] == "癸酉" and info["nayin"] == "剑锋金")
check("建除 = 闭", info["jianchu"] == "闭")
check("值神 = 天德（黄道）", info["day_god"] == "天德" and info["day_god_luck"] == "黄道")
check("宿 = 危（凶）", info["xiu"].endswith("危") and info["xiu_luck"] == "凶")
check("冲 = 丁卯（兔）", info["chong"].startswith("丁卯"))
check("煞东 / 财神正南 / 喜神东南",
      info["sha_direction"] == "东" and info["caishen"] == "正南" and info["xishen"] == "东南")
check("吉时 = 子寅卯午未酉",
      [h["zhi"] for h in info["good_hours"]] == ["子", "寅", "卯", "午", "未", "酉"])

print("== C. 八字 ==")
bd = datetime(1990, 6, 15, 8, 30, tzinfo=astro.CST)
bz = bazi_mod.chart(bd, "女", longitude=104.06)
check("四柱 庚午/壬午/辛亥/壬辰",
      [bz["pillars"][k] for k in ("year", "month", "day", "hour")] == ["庚午", "壬午", "辛亥", "壬辰"])
ok, d = near(datetime.strptime(bz["true_solar_time"], "%Y-%m-%d %H:%M").replace(tzinfo=astro.CST),
             "1990-06-15 07:25", 120)
check("真太阳时 07:25（±2 分钟）", ok, "差 %.0f 秒" % d)
check("阳年女命 → 大运逆行", bz["dayun"]["meta"]["forward"] is False)
check("起运 3.02 岁（±0.15）", abs(bz["dayun"]["meta"]["start_age"] - 3.02) < 0.15,
      str(bz["dayun"]["meta"]["start_age"]))
check("大运首三步 辛巳/庚辰/己卯",
      [x["ganzhi"] for x in bz["dayun"]["list"][:3]] == ["辛巳", "庚辰", "己卯"])
check("纳音 辛亥 = 钗钏金", bz["pillars_detail"]["day"]["nayin"] == "钗钏金")
check("五行占比合计 100%%（±0.5）", abs(sum(bz["wuxing"]["percent"].values()) - 100) < 0.5,
      str(bz["wuxing"]["percent"]))
check("十神：甲见庚为七杀", bazi_mod.shishen("甲", "庚") == "七杀")
check("十神：甲见辛为正官", bazi_mod.shishen("甲", "辛") == "正官")
check("十神：辛见壬为伤官", bazi_mod.shishen("辛", "壬") == "伤官")
check("空亡：甲子旬为戌亥", cc.xunkong(0) == "戌亥")

print("== D. 六爻 ==")
qian = dv._liuyao_core([1, 1, 1, 1, 1, 1], [], [], "test")
check("乾为天：乾宫本宫 / 世6应3",
      qian["palace"]["name"] == "乾宫" and qian["palace"]["shi"] == 6 and qian["palace"]["ying"] == 3)
check("乾为天纳甲：初爻甲子子孙、五爻壬申兄弟",
      qian["yao"][0]["gan"] + qian["yao"][0]["zhi"] == "甲子" and qian["yao"][0]["liuqin"] == "子孙"
      and qian["yao"][4]["gan"] + qian["yao"][4]["zhi"] == "壬申"
      and qian["yao"][4]["liuqin"] == "兄弟")
gou = dv._liuyao_core([0, 1, 1, 1, 1, 1], [], [], "test")
check("天风姤：乾宫一世 / 世1应4 / 卦名对",
      gou["palace"]["step"] == "一世" and gou["palace"]["shi"] == 1
      and gou["palace"]["ying"] == 4 and gou["ben"]["name"] == "天风姤")
check("天风姤纳甲：初爻辛丑父母、四爻壬午官鬼",
      gou["yao"][0]["gan"] + gou["yao"][0]["zhi"] == "辛丑" and gou["yao"][0]["liuqin"] == "父母"
      and gou["yao"][3]["gan"] + gou["yao"][3]["zhi"] == "壬午" and gou["yao"][3]["liuqin"] == "官鬼")
eight = []
for lines in [(1, 1, 1, 1, 1, 1), (0, 1, 1, 1, 1, 1), (0, 0, 1, 1, 1, 1), (0, 0, 0, 1, 1, 1),
              (0, 0, 0, 0, 1, 1), (0, 0, 0, 0, 0, 1), (0, 0, 0, 1, 0, 1), (1, 1, 1, 1, 0, 1)]:
    eight.append(dv._palace_of(list(lines))[2])
check("乾宫八卦步序 姤/遁/否/观/剥/晋/大有 → 一至五世+游魂+归魂",
      eight == ["本宫", "一世", "二世", "三世", "四世", "五世", "游魂", "归魂"], str(eight))
toss = dv.liuyao_toss()
check("摇卦：6 爻齐备且动爻标记一致",
      len(toss["yao"]) == 6 and all((y["moving"] == ((y["position"]) in toss["moving"])) for y in toss["yao"]))

print("== E. 梅花 ==")
mh = dv.meihua_by_numbers(3, 8)
check("数字 3,8 → 火地晋 / 互水山蹇 / 变天地否",
      mh["ben"]["name"] == "火地晋" and mh["hu"]["name"] == "水山蹇" and mh["bian"]["name"] == "天地否")
check("动爻第 5 爻 → 上卦为用", mh["moving_line"] == 5 and mh["moving_pos"] == "上卦")
check("体坤土 / 用离火 → 用生体", mh["ti_yong"]["relation"] == "用生体")

print("== F. 紫微 ==")
zw = ziwei_mod.chart(bd, "女", longitude=104.06)
check("命宫寅（戊寅）/ 身宫戌", zw["ming_palace"]["zhi"] == "寅"
      and zw["ming_palace"]["ganzhi"] == "戊寅" and zw["shen_palace"]["zhi"] == "戌")
check("五行局 土五局", zw["ju"]["name"] == "土五局")
check("紫微申 / 天府申", zw["ziwei"]["zhi"] == "申" and zw["tianfu"]["zhi"] == "申")
stars = [s["name"] for p in zw["palaces"] for s in p["stars"]]
check("十四主星齐备无重复", len(stars) == 14 and len(set(stars)) == 14)
check("命宫主星 = 七杀", [s["name"] for p in zw["palaces"] if p["is_ming"] for s in p["stars"]] == ["七杀"])
check("庚干四化 = 阳禄武权阴科同忌",
      zw["sihua"] == {"禄": "太阳", "权": "武曲", "科": "太阴", "忌": "天同"})
check("阳女逆行：大限第二步落父母宫", zw["dayun"]["list"][1]["palace"] == "父母"
      and zw["dayun"]["list"][1]["palace_zhi"] == "卯")
check("大限起运虚岁 = 5", zw["dayun"]["list"][0]["age_range"].startswith("5"))

print("== G. 塔罗 ==")
check("牌库 78 张", len(tarot_mod.DECK) == 78)
t3 = tarot_mod.draw("three", "test")
check("三张牌阵：三张不重复且位置正确",
      len(t3["cards"]) == 3 and len({c["name"] for c in t3["cards"]}) == 3
      and [c["position_name"] for c in t3["cards"]] == ["现况", "卡点", "走向"])
tc = tarot_mod.draw("celtic", "test")
check("凯尔特十字 10 张不重复", len({c["name"] for c in tc["cards"]}) == 10)

print("== H. 命令行与渲染 ==")
CLI = os.path.join(SCRIPTS, "oracle.py")
tmp = tempfile.mkdtemp(prefix="sinan_test_")
cases = [
    ("today", {}, None),
    ("day", {"--date": "2026-10-26"}, "almanac.html"),
    ("pick", {"--from": "2026-11-01", "--to": "2026-11-30", "--purpose": "嫁娶"}, "pick.html"),
    ("bazi", {"--date": "1990-06-15", "--time": "08:30", "--gender": "女", "--lon": "104.06"}, "bazi.html"),
    ("ziwei", {"--date": "1990-06-15", "--time": "08:30", "--gender": "女", "--lon": "104.06"}, "ziwei.html"),
    ("meihua", {"--numbers": ["3", "8"]}, "meihua.html"),
    ("liuyao", {"--toss": ""}, "liuyao.html"),
    ("tarot", {"--spread": "three", "--question": "测试"}, "tarot.html"),
    ("solar", {"--year": "2026"}, None),
    ("lunar", {"--date": "2026-10-26"}, None),
]
for cmd, args, out in cases:
    argv = [sys.executable, CLI, cmd]
    for k, v in args.items():
        argv.append(k)
        if isinstance(v, list):
            argv.extend(v)
        elif v != "":
            argv.append(v)
    if out:
        argv += ["--html", os.path.join(tmp, out)]
    r = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8")
    ok = r.returncode == 0 and (not out or os.path.exists(os.path.join(tmp, out)))
    check("CLI %-8s 退出 0%s" % (cmd, " 且生成 HTML" if out else ""), ok,
          (r.stderr or "").strip().splitlines()[-1][:90] if not ok else "")

htmls = [f for f in os.listdir(tmp) if f.endswith(".html")]
okall = True
for f in htmls:
    s = open(os.path.join(tmp, f), encoding="utf-8").read()
    if "%s" in s or "None" in s or "nan" in s or "本页由 AI" not in s:
        okall = False
        print("     异常文件：", f)
check("七份 HTML 结构完整（无占位符/None 残留、含免责声明）", okall and len(htmls) == 7, "生成 %d 份" % len(htmls))

print("== I. 数据一致性 ==")
bad_sum = []
for i in range(40):
    d = date(2026, 1, 1).toordinal() + i * 9
    dd = date.fromordinal(d)
    ly, lm, ld, leap = cc.solar_to_lunar(dd)
    back = cc.lunar_to_solar(ly, lm, ld, leap)
    bz2 = bazi_mod.chart(datetime(dd.year, dd.month, dd.day, 12, tzinfo=astro.CST), "男")
    if back != dd or bz2["pillars"]["day"] != cc.day_ganzhi(dd):
        bad_sum.append(str(dd))
check("农历↔公历往返 40 个抽样日全对，且日柱一致", not bad_sum, str(bad_sum))

print()
print("合计：PASS %d / FAIL %d" % (len(PASS), len(FAIL)))
if FAIL:
    print("失败项：")
    for f in FAIL:
        print("  -", f)
sys.exit(1 if FAIL else 0)
