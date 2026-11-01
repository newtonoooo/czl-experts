# 行情命令行速查（外部工具，非本包内置）

本包**不捆绑**任何第三方数据 CLI。如果当前环境已装 `westock-data` / `westock-tool`，按下表调用；没装就走用户 CSV 或公开数据源，并披露来源。

## 取日线

```bash
westock-data kline sh510300 --period day --limit 2000 --fq qfq
westock-data kline hk00700  --period week --limit 10
westock-data kline usAAPL   --period day  --limit 60
westock-data kline sh600000,sh600519 --period day --limit 20    # 批量
```

| 参数 | 取值 | 备注 |
|---|---|---|
| `--period` | `day` / `week` / `month` | 分钟级数据不在本专家范围内 |
| `--limit` | ≤ 2000 | 超过要分段拼接 |
| `--fq` | `qfq` 前复权（默认）/ `hfq` 后复权 / `bfq` 不复权 | 长持与分红相关策略用 `qfq` |
| `--start` / `--end` | `YYYY-MM-DD` | 区间查询 |

## 其它常用

```bash
westock-data quote sh600000                 # 实时行情
westock-data finance sh600000 --num 4       # 最近 4 期财报
westock-data technical sh600000 --group macd,rsi
westock-data sector sw1_pt01801080           # 板块成份股
westock-data index sh000300                  # 指数成份
westock-data macro pmi --start 2024 --end 2025
westock-tool <筛选条件>                       # 条件选股，具体参数见该工具自带说明
```

## 接到回测里的标准动作

```bash
# 1) 取原始表（Markdown 表格）
westock-data kline sh510300 --period day --limit 2000 --fq qfq > raw/510300.md

# 2) 转成内核契约
python tools/bars_from_table.py raw/510300.md \
       -o data/bars_510300.csv --symbol 510300.SH

# 3) 体检（脚本会打印行数、首末日期、OHLC 异常数）
```

## 限制与坑

1. **代码前缀错一位就是另一只股票**，取完先核一遍标的名称。
2. 港股、美股的货币单位分别是 HKD、USD，**不要套人民币符号**；跨币种不要叠在一条净值线上。
3. 指数与 ETF 的成交量含义不同（指数常为"手数汇总"或空），做量能信号前先看一眼数值量级。
4. 接口不可用时不要重试到天荒地老：换本地 CSV，或在回复里说明"数据源不可用，本次仅提供方法与脚本骨架"。
