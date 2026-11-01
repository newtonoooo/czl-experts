---
name: ar-evidence
description: Fetch A-share data through a three-tier fallback ladder (public HTTP endpoints, user-connected financial tools, web retrieval), register every number with source and timestamp, tag data quality, and refuse to invent missing values. Ships zero-dependency Python scripts for quotes, K-lines, indicators and A-share rule checks. Triggers on any need for price, volume, financials, capital flow, or before any diagnosis, valuation or review.
---

# 取数与证据台账

这个流程的产出不是"数据"，是**一份能被别人复核的证据清单**。数据谁都能抓，可追溯性才是壁垒。

## 职责

**做**：三级降级取数、字段归一、来源与时间戳登记、质量标记、A股规则校验。
**不做**：不做分析判断、不算估值、不写结论。

## 输入参数

| 参数 | 必填 | 说明 |
|---|---|---|
| 标的代码 | 是 | `600519.SH` |
| 需要的数据项 | 是 | 行情 / K线 / 财务 / 资金 / 公告 / 股东，可多选 |
| 时间范围 | 否 | K线默认最近 250 交易日；财务默认最近 8 期 |
| 复权方式 | 否 | 默认前复权 `qfq` |

## 执行步骤

### 1. 数据源阶梯

按顺序尝试，前一级失败或字段缺失才降级：

| 级 | 通道 | 适用 | 超时 |
|---|---|---|---|
| L1 | 公开 HTTP 接口（新浪 / 东方财富），`scripts/arfetch.py` 实现 | 实时行情、指数、日K | 8 秒 |
| L2 | 用户已连接的金融类工具 / MCP | 财务、资金、公告等结构化数据 | 15 秒 |
| L3 | 联网检索（WebSearch / WebFetch） | 事件、政策、公告原文 | 15 秒 |

单源超时即降级；总预算 30 秒。**降级必须在报告里显形**，不能悄悄换了源还假装是首选。

### 2. 字段归一

无论哪一级取到，统一成同一套字段名，避免下游到处判断来源差异：

```
code, name, market, board, last, prev_close, open, high, low,
volume(手), amount(元), turnover_rate(%), pct_chg(%), 
trade_date, fetch_time, source, quality, flags[]
```

金额统一为元，展示时再换亿元；比率统一为百分数（12.34 表示 12.34%）。

### 3. 质量标记

每个数据块挂一个 `quality` 值，取值与含义见 `rules/ar-evidence-grade.md` 第五节：

`primary` / `fallback` / `stale` / `partial` / `estimated` / `missing` / `fetch_failed`

**规则：quality 不是 `primary` 时，最终报告的置信度不得为"高"。**

### 4. A股规则校验（不可跳过）

拿到价格后立刻过一遍 `scripts/arrules.py`：

```bash
python scripts/arrules.py check --code 600519 --prev-close 1500.00 --price 1650.00
```

校验：代码归属、板块涨跌幅、价格是否越界、是否需 ST 口径。校验不通过，说明数据有错，回查数据源，**不要绕过继续算**。

### 5. 记录台账

把取到的每个关键数字写进 `data/{code}-evidence-{YYYYMMDD}.json`，含 `value / unit / source / as_of / quality`。这份台账是报告"来源"一节的唯一依据，也是事后复核的凭证。

## 判断条件

| 情形 | 动作 |
|---|---|
| 行情（价格+成交量）完全拿不到 | 停止，输出缺失清单，不出任何结论 |
| 仅财务拿不到 | 继续，跳过基本面维，技术面与资金面权重上调，报告注明 |
| 仅资金面拿不到 | 继续，跳过资金维，不得用"主力动向不明"填充 |
| 数据日期不是最近交易日 | 标 `stale`，写明实际日期，禁止写"最新" |
| 停牌 | 标 `suspended`，技术面结论全部失效 |
| 复权口径不明 | 按未复权处理并标注，禁止跨除权日比较涨跌幅 |
| 数值明显异常（如 PE 为负、成交额为 0 但换手率>5%） | 视为数据错误，回查；查不出则标 `partial` |

## 输出

```
## 证据台账 · 600519.SH
| 项目 | 数值 | 单位 | 来源 | 截至 | 质量 |
|---|---|---|---|---|---|
| 收盘价 | 1500.00 | 元 | 新浪财经 | 2026-10-29 | primary |
| 成交额 | 32.15 | 亿元 | 新浪财经 | 2026-10-29 | primary |
| 三季报营收 | [MISSING] | — | — | — | missing |
缺失影响：无最新季报，成长性结论只能依赖中报，置信度降为中。
```

## 异常处理

- 接口反爬/改版：换备用接口；两者都失败则走 L2/L3，并在报告注明"行情取自检索，存在延迟，不作为交易依据"。
- 编码乱码：新浪接口为 GBK，需转码；转码失败视为该源失败，降级。
- 返回空数组：视为失败，不视为"无数据"。
- 数值单位歧义（元 vs 万元）：以接口字段定义为准，不确定则不采用。

## 依赖

- `skills/ar-evidence/scripts/arfetch.py`：行情与 K 线抓取（仅标准库）
- `skills/ar-evidence/scripts/arindicators.py`：MA/MACD/KDJ/RSI/BOLL/ATR 计算
- `skills/ar-evidence/scripts/arrules.py`：A股规则校验
- `rules/ar-market-rules.md`、`rules/ar-evidence-grade.md`

## 与其他工作流的关系

- 上游：`ar-intake`
- 下游：`ar-autopsy`、`ar-value`、`ar-tape`、`ar-position`（全部共用本台账，禁止各自重复取数导致口径不一致）
- 回写：台账文件供 `ar-quality` 校验"每个数字是否有出处"
