# 文件清单 · 司南 v1.0.0

- 统计时间：2026-10-26
- 文件总数：33
- 总体积：约 1.64 MB（其中头像原图 1.06 MB）
- 代码量：Python 8 个产品模块 2,937 行 + 测试脚本 250 行
- 文档与提示词：约 60 KB

---

## 一、元数据

| 文件 | 大小 | 行数 | 职责 |
|---|---:|---:|---|
| `.codebuddy-plugin/plugin.json` | 2.7 KB | 74 | 专家唯一标识、版本、作者、展示字段、skills 声明 |

## 二、专家定义

| 文件 | 大小 | 行数 | 职责 |
|---|---:|---:|---|
| `agents/czl-oracle-advisor.md` | 9.7 KB | 170 | 人格、作业方式、作业台地图、开工三问、完整度分级、输出纪律、权重矩阵、路由、收工三查、边界、免责声明 |

## 三、工作流模块（9 个）

| 文件 | 大小 | 行数 | 职责 |
|---|---:|---:|---|
| `skills/czl-oracle-engine/SKILL.md` | 4.9 KB | 78 | 引擎调用手册：子命令、参数、字段、异常处理 |
| `skills/czl-oracle-atlas/SKILL.md` | 3.7 KB | 83 | HTML 装配：notes 契约、配色对照、质检清单 |
| `skills/czl-birth-intake/SKILL.md` | 4.5 KB | 80 | 生辰采集、八项字段、S/A/B/C 定级、时辰存疑处理 |
| `skills/czl-bazi-read/SKILL.md` | 6.1 KB | 114 | 八字六步读法、十神表、偏枯判读、宫位、节奏 |
| `skills/czl-ziwei-read/SKILL.md` | 5.7 KB | 122 | 紫微读盘顺序、14 主星对照、四化、十二宫、大限 |
| `skills/czl-cast-read/SKILL.md` | 4.9 KB | 82 | 梅花/六爻/塔罗的分工与读法、用神取法、异常处理 |
| `skills/czl-timing-pick/SKILL.md` | 4.8 KB | 98 | 择日五步、用途对照、时辰挑选、现实约束优先级 |
| `skills/czl-composite-verdict/SKILL.md` | 4.9 KB | 109 | 交叉验证、分歧归因、条件判断、合盘四结构 |
| `skills/czl-boundary-guard/SKILL.md` | 4.9 KB | 61 | 八条硬线、改写银行、语气要求、交付前自检 |

## 四、计算引擎（8 个模块）

| 文件 | 大小 | 行数 | 职责 |
|---|---:|---:|---|
| `skills/czl-oracle-engine/scripts/astro.py` | 15.9 KB | 411 | 儒略日、ΔT、太阳视黄经（VSOP87 截断）、月亮视黄经、节气、朔、均时差 |
| `skills/czl-oracle-engine/scripts/calendar_core.py` | 12.8 KB | 390 | 干支、五虎遁/五鼠遁、真太阳时、定朔定气农历、纳音、旬空 |
| `skills/czl-oracle-engine/scripts/bazi.py` | 13.9 KB | 345 | 四柱、十神、藏干、五行力量、旺衰、神煞、大运、流年 |
| `skills/czl-oracle-engine/scripts/ziwei.py` | 7.6 KB | 183 | 命身宫、五行局、紫微定位、14 主星、四化、十二宫、大限 |
| `skills/czl-oracle-engine/scripts/divination.py` | 16.8 KB | 360 | 梅花体用互变、六爻京房八宫装卦、纳甲六亲六神 |
| `skills/czl-oracle-engine/scripts/almanac.py` | 10.4 KB | 221 | 建除、黄道黑道、二十八宿、冲煞、吉时、择日打分 |
| `skills/czl-oracle-engine/scripts/tarot.py` | 15.6 KB | 223 | 78 张牌库（自撰牌义）、正逆位、5 种牌阵 |
| `skills/czl-oracle-engine/scripts/render.py` | 26.8 KB | 513 | 6 套配色的单文件 HTML 渲染 |
| `skills/czl-oracle-engine/scripts/oracle.py` | 13.1 KB | 291 | CLI 入口，10 个子命令 |

## 五、规范

| 文件 | 大小 | 行数 | 职责 |
|---|---:|---:|---|
| `rules/czl-input-standard.md` | 2.2 KB | 46 | 八项字段、时间口径、禁止的输入处理、冲突处理 |
| `rules/czl-reading-standard.md` | 2.4 KB | 66 | 六段式、语言纪律、可核对性、不确定性表达 |

## 六、视觉资源

| 文件 | 大小 | 说明 |
|---|---:|---|
| `avatars/expert.png` | 346 KB | **成品头像**，512×512 PNG，用于平台展示 |
| `avatars/expert-raw.png` | 1.06 MB | 原图 1024×1024，保留生成水印，供替换/举证用 |

## 七、文档

| 文件 | 大小 | 行数 | 职责 |
|---|---:|---:|---|
| `README.md` | 6.2 KB | 135 | 产品介绍 + **平台展示文案** + 目录结构 |
| `USAGE.md` | 4.9 KB | 133 | 使用说明（用户视角、含 FAQ） |
| `SPEC.md` | 5.0 KB | 121 | 产品规格说明（需求→规格、技术接口、取舍、不做范围） |
| `TEST-REPORT.md` | 8.5 KB | 167 | 功能测试报告（63 项断言 + 未验证事项） |
| `RISK-ASSESSMENT.md` | 7.8 KB | 156 | 商业发布风险清单（15 项，含需决策事项） |
| `DEVLOG.md` | 7.6 KB | 114 | 开发记录与来源声明 |
| `MANIFEST.md` | 本文件 | — | 文件清单 |
| `CHANGELOG.md` | 3.5 KB | 58 | 版本日志 |
| `LICENSE` | 1.1 KB | — | MIT，版权归虫志龙 |

## 八、开发与测试工具

| 文件 | 大小 | 行数 | 职责 |
|---|---:|---:|---|
| `tests/run_tests.py` | 13.1 KB | 250 | 63 条断言的回归测试，随包分发以便复核 |

运行方式：

```bash
python tests/run_tests.py
```

脚本会自动定位引擎目录（同包内 `skills/czl-oracle-engine/scripts`），也可用环境变量 `SINAN_ENGINE` 指定。

---

## 九、未纳入包内的开发辅助文件

以下文件仅用于本机开发，不随包分发：

| 文件 | 用途 |
|---|---|
| `pngutil.py` | 纯标准库 PNG 裁剪/缩放工具，用于头像裁切（环境无 Pillow 时的替代） |
| `_engine_test/*.html` | 开发期渲染产物，仅作人工检视 |

如需复现头像裁切，可用任意图像工具按 `(52,40,900,900)` 裁切原图并缩放到 512×512。
