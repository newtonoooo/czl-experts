# btcore / btreport API 速查

版本以 `btcore.__version__` 为准。改动本文件前先跑 `python tools/selftest.py`。

## 数据

```python
load_bars(path, symbol=None) -> list[Bar]
load_bars_multi({"A": "a.csv", "B": "b.csv"}) -> dict[str, list[Bar]]
```

`Bar` 字段：`date, open, high, low, close, volume`。

必需列 `date, open, high, low, close`；缺列直接抛 `ValueError` 并列出实际列名（不要吞异常）。

## 成本

```python
CostModel.china_a(commission_bps=2.5, min_commission=5.0)
CostModel.us_stock(commission_bps=0.0, slippage_bps=3.0)
CostModel.hk_stock(commission_bps=8.0, slippage_bps=8.0)
CostModel.zero()
cost.buy_cost(notional) / cost.sell_cost(notional) / cost.describe()
```

字段：`commission_bps, min_commission, stamp_tax_bps, transfer_bps, slippage_bps`（bp = 万分之一）。

## 下单

```python
Order(symbol, side, shares=None, weight=None, reason="")
```

| 参数 | 语义 |
|---|---|
| `shares=1000` | 买/卖 1000 股（买入自动按手数向下取整） |
| `weight=0.95` | 目标权重，按「上一交易日收盘总资产」计算差额股数 |
| `shares=None` 且 `weight=None`（卖出） | 清掉该标的可卖数量 |
| `reason` | 写进 `trades.csv` 的 `exit_reason`，用于归因 |

## 引擎

```python
Engine(bars_by_symbol, cost=None, initial_cash=1_000_000, lot_size=100,
       t_plus_1=True, eval_start=None, eval_end=None, market="china_a",
       strategy_name="", note="")
Engine.run(strategy) -> BacktestResult
```

- `strategy(ctx) -> list[Order] | Order | None`
- 引擎只在 `[eval_start, eval_end]` 内调用策略；预热段仅累积历史
- 最后一根 bar 之后强制清仓，`exit_reason="eod_close"`

### Context 提供的读接口

| 方法 | 说明 |
|---|---|
| `ctx.date` / `ctx.i` | 当前 bar 日期 / 序号 |
| `ctx.closes(sym, n=None)` | 最近 n 个收盘价（含今天） |
| `ctx.bar(sym)` | 今日 Bar（可能为 None，停牌） |
| `ctx.history(sym)` | 到今天为止的全部 Bar |
| `ctx.shares(sym)` / `ctx.cash()` / `ctx.equity()` | 持仓、现金、总资产 |
| `ctx.ma(sym, n)` | 简单均线，数据不足返回 None |
| `ctx.atr(sym, n=14)` | ATR，数据不足返回 None |
| `ctx.avg_cost(sym)` / `ctx.open_date(sym)` | 持仓均价 / 开仓日 |
| `ctx.broker` | 底层账户对象（一般不用） |

## 结果

```python
res.equity      # [{"date", "value"}]
res.trades      # [{symbol, side, entry_date, exit_date, shares, entry_price,
                #   exit_price, pnl, pnl_pct, holding_days, exit_reason}]
res.metrics     # 见下表
res.meta        # 策略名、区间、成本描述、手数、T+1、引擎版本
res.rejects     # 被拒订单（现金不足 / 不足一手 / T+1 锁定）
res.warnings    # 数据与样本告警
res.monthly     # [{year, months[12], ytd}]，报告热力图用
res.dump(outdir, prefix, language="zh") -> {"equity":…, "trades":…, "summary":…}
```

### metrics 字段

| 字段 | 含义 |
|---|---|
| `total_return_pct` / `annual_return_pct` | 累计 / 年化（按自然日 365.25 折算） |
| `max_drawdown_pct` / `max_drawdown_date` | 最大回撤及谷底日期 |
| `sharpe` / `sortino` / `calmar` | 无风险利率按 0 处理；日收益 × √252 |
| `annual_vol_pct` | 年化波动 |
| `win_rate_pct` / `profit_factor` | 胜率 / 盈亏比（总盈利 ÷ 总亏损） |
| `trade_count` / `buy_fills` / `sell_fills` | 平仓笔数 / 买入成交次数 / 卖出成交次数 |
| `avg_holding_days` / `best_trade_pct` / `worst_trade_pct` | 持有天数与极值 |
| `exposure_pct` | 有持仓的 bar 占比 |
| `total_fees` / `evaluation_bars` | 累计费用 / 评估区间 bar 数 |

## 事件研究

```python
event_study(bars, events, hold_bars=20, entry="next_open", exit_at="close")
event_stats(rows)
```

`events`: `[{"date": "2023-06-15", "label": "降息"}]`。

- 事件日非交易日自动顺延到下一个交易日
- 样本不够 N 根 bar 时不伪造结果，返回 `status != "ok"` 并在统计里计入 `skipped`
- `event_stats` 返回 `event_count, skipped, avg_pct, median_pct, win_rate_pct, best_pct, worst_pct, stdev_pct`

## 工具函数

```python
compute_metrics(equity_series, trades, initial_cash) -> dict
monthly_table(equity_series) -> list
buy_and_hold(bars, eval_start, eval_end, initial_cash=1_000_000) -> equity list
param_sweep(runner, {"fast": [3,5], "slow": [20,60]}) -> list[dict]
```

## btreport

```python
build_payload(result, title, subtitle="", lang="zh", benchmark=None,
              notes=None, extra_kpis=None, markers=None, footer_extra="")
render(payload, out_path, template_path=None)
report_from_result(result, out_path="index.html", title=..., ...)
event_payload(event_rows, stats, title, lang="zh", extra=None)
build_markers(trades, limit=200, lang="zh")
```

- `lang` 必须显式传 `"zh"` 或 `"en"`，跟随用户提问语言，不跟随标的市场
- `notes`: `[{"title": "...", "items": ["..."]}]`，报告底部"口径与说明"区
- 报告模板 `kit/template/report.tpl.html` 自包含，不联网、不引 CDN
- 生成后跑 `node tools/check_report.js <html>` 做渲染自检
