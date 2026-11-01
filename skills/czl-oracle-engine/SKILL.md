---
name: czl-oracle-engine
description: The calculation core. Runs the bundled Python engine to produce BaZi four pillars, Zi Wei palaces, Plum Blossom and Six-Line hexagrams, tarot draws, almanac day details and date candidates — all as structured JSON or ready-to-send HTML. Use this whenever a chart, hexagram, calendar conversion or date lookup must be computed rather than recalled. Triggers on 排盘, 算八字, 起卦, 抽牌, 查黄历, 农历转换, 节气时刻, 大运, 流年.
---

# 排盘引擎调用

**职责**：把用户给的生辰/时间/数字，变成结构化盘面。本 skill 只管"算得对、取得出"，不管怎么解读。

## 铁律

1. 任何盘面**必须**由脚本产出。凭记忆写干支、农历、命宫，错误率高到不可接受。
2. 脚本已经通过节气、农历、日柱、黄历的对照验证，不要"修正"它的输出。若用户给的数据与盘面冲突，以用户提供的**记录**为准，并说明冲突点。
3. 不要手写 JSON 冒充引擎输出。字段名必须与脚本一致，解读层才接得上。

## 脚本位置与调用

脚本在本 skill 的 `scripts/` 目录下，主入口 `oracle.py`。用绝对路径调用即可，脚本内部已处理模块路径：

```bash
python "<本 skill 目录>/scripts/oracle.py" <子命令> [参数]
```

Windows 下若 `python` 不可用，依次尝试 `python3`、`py`。

## 子命令速查

| 子命令 | 用途 | 关键参数 |
|---|---|---|
| `today` | 今日日课 | `--date` 可覆盖 |
| `day` | 指定日日课（建除/值神/宿/冲煞/吉时/宜忌） | `--date 2026-10-26` |
| `pick` | 按用途筛候选日 | `--from --to --purpose --avoid-zhi --limit` |
| `bazi` | 四柱八字全盘 | `--date --time --gender --lon` |
| `ziwei` | 紫微斗数 | `--date --time --gender --lon` |
| `meihua` | 梅花易数 | `--numbers A B` 或 `--date --time`（默认此刻） |
| `liuyao` | 六爻纳甲 | `--toss`（默认，三钱摇卦）或 `--numbers n1..n6` |
| `tarot` | 塔罗 | `--spread single\|three\|three_time\|five\|celtic --question` |
| `solar` | 某年二十四节气时刻 | `--year 2026` |
| `lunar` | 公历↔农历 | `--date 2026-10-26` 或 `--lunar 2026 9 17 [--leap]` |

通用开关：`--json`（输出 JSON）、`--out-json 路径`（另存 JSON）、`--html 路径`（直接出成品页）、`--notes 路径`（解读 JSON，配合 `--html`）。

## 参数必读

**`--gender`**：八字定大运顺逆、紫微定大限顺逆都靠它，必填 `男` 或 `女`。

**`--lon`（出生地东经度数）**：给了就做真太阳时校正（经度差 + 均时差）。不给则按东八区标准时算，并在输出的 `correction` 字段体现。常用值：北京 116.41、上海 121.47、成都 104.06、重庆 106.55、广州 113.26、西安 108.94、乌鲁木齐 87.62、哈尔滨 126.53、昆明 102.83、拉萨 91.14。

**`--day-boundary`**：默认 `23:00`（晚子时换日，传统做法）。若用户的流派或习惯是午夜换日，传 `00:00`。

**`--time`**：24 小时制 `HH:MM`，按**当地标准时**（东八区）填，不要自己先换算成真太阳时——脚本会算。

## 关键输出字段

- `bazi`：`pillars`（四柱）、`pillars_detail`（十神/藏干/纳音/长生）、`wuxing.percent`（五行占比）、`strength`（旺衰粗判与依据）、`xunkong`、`shensha`、`zhi_relations`、`dayun.meta`（起运）、`dayun.list`、`liunian`、`correction`、`nearby_terms`
- `ziwei`：`ming_palace`、`shen_palace`、`ju`、`ziwei`/`tianfu`、`sihua`、`palaces[12]`、`dayun.list`
- `meihua`：`ben`/`hu`/`bian`、`moving_line`、`ti_yong.relation`
- `liuyao`：`ben`、`palace`（宫/世应）、`yao[6]`（六神/六亲/纳甲/旬空）、`bian`、`moving`
- `almanac`：`jianchu`、`day_god`、`xiu`、`chong`、`sha_direction`、`caishen`、`xishen`、`good_hours`、`yi`/`ji`

## 异常处理

| 情况 | 处理 |
|---|---|
| 日期格式错误 | 统一转成 `YYYY-MM-DD` 再传；不要传中文日期 |
| 节气交界（`nearby_terms` 非空） | 必须在解读里提示"出生时刻距交节 X 分钟，年/月柱以此为准，建议核对出生记录" |
| 缺时辰 | 不调 `bazi`，改走 B 级流程：只报年月日、说明缺时辰会丢时柱与大运起运 |
| 时辰存疑 | 两个候选时辰各跑一次，比对差异，交用户确认 |
| 脚本报错 | 如实告知报错内容，不要凭记忆补一个盘 |

## 依赖

纯 Python 3.8+ 标准库，无第三方依赖、无需联网。依赖文件：`astro.py`（星历）、`calendar_core.py`（历法）、`bazi.py`、`ziwei.py`、`divination.py`、`tarot.py`、`almanac.py`、`render.py`。

## 与其他模块的关系

- 上游：`czl-birth-intake`（规范化输入）
- 下游：`czl-bazi-read`、`czl-ziwei-read`、`czl-cast-read`、`czl-timing-pick`、`czl-oracle-atlas`
