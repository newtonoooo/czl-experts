---
name: bt-engine
description: 用随包内核 kit/btcore.py 写一个自包含、可复现的回测脚本：信号与成交分离、预热段隔离、手数与 T+1、费用参数化、样本末强平、账户恒等式、三件套导出。负责策略回测、事件研究、组合轮动三种模式的实现规范与常见实现错误。
---

# WF-03 引擎构建与运行

不要从零手写撮合逻辑，也不要引入 backtrader / vectorbt 这类框架。用 `kit/btcore.py`——它只依赖 Python 标准库，装不上 pandas 的机器也能跑。

## 一、先选模式

| 模式 | 判据 | 用什么 | 出什么 |
|---|---|---|---|
| 策略回测 | 有账户、有仓位、有净值 | `Engine.run(strategy)` | 三件套 + 组合指标 |
| 事件研究 | 一个事件一行结果，不模拟资金 | `event_study()` | `trades.csv`（事件级）+ 事件统计 |
| 组合轮动 | 多标的、权重、调仓 | `Engine.run` + `Order(weight=…)` | 三件套 + 换手统计 |

判据只有一条：**用户问的是"这套规则长期跑下来怎么样"（策略），还是"某件事发生后 N 天平均涨多少"（事件）**。两者混着做，指标一定错。

## 二、六条实现硬规则

1. **信号在 t 日收盘评估，t+1 日开盘成交。** 内核已用 pending 队列实现，策略回调只能看到今天及以前的 bar。写策略时不要自己用 `iloc[i+1]`。
2. **预热段只喂历史，不下单。** 内核只在 `[eval_start, eval_end]` 内调用策略；指标窗口要够，就把 `eval_start` 往前多取数据（`warmup_days`）。
3. **手数取整在最底层做。** A 股 100 股一手；下单数量交给 `btcore` 取整，不要在策略里自己 `//100*100`，否则会和现金约束打架。
4. **费用参数化。** 佣金、最低收费、印花税、过户费、滑点都走 `CostModel`，不要写死在代码里；换市场时只换 `CostModel`。
5. **样本末强平。** 引擎自动按最后一根 bar 收盘价清仓，`exit_reason="eod_close"`。回复里必须说明这一点，否则最后一段浮盈会被误读成已实现收益。
6. **账户恒等式**：`equity = cash + Σ(数量 × 收盘价)`。任何自定义记账（融资、做空、多币种）都要显式写成这个形式，并把负债项单独列出。

## 三、三种模式的最小骨架

### 策略回测

```python
import sys; sys.path.insert(0, "kit")
from btcore import load_bars, Engine, CostModel, Order

bars = load_bars("data/bars_510300.csv", "510300.SH")

def strategy(ctx):
    c = ctx.closes("510300.SH", 61)
    if len(c) < 61:
        return None                      # 指标未成形，什么都不做
    fast = sum(c[-20:]) / 20
    slow = sum(c[-60:]) / 60
    holding = ctx.shares("510300.SH")
    if holding == 0 and fast > slow:     # 收盘确认
        return [Order("510300.SH", "buy", weight=0.95, reason="ma20>ma60")]
    if holding > 0 and fast < slow:
        return [Order("510300.SH", "sell", reason="ma20<ma60")]
    return None

eng = Engine({"510300.SH": bars}, cost=CostModel.china_a(), initial_cash=1_000_000,
             lot_size=100, t_plus_1=True,
             eval_start="2020-01-01", eval_end="2024-12-31", market="china_a",
             strategy_name="MA20/MA60 交叉")
res = eng.run(strategy)
res.dump("out", "ma_510300")
```

### 事件研究

```python
from btcore import load_bars, event_study, event_stats

bars = load_bars("data/bars_510300.csv")
rows = event_study(bars, [{"date": "2023-06-15", "label": "降息 10bp"}], hold_bars=20)
stats = event_stats(rows)     # 平均/中位/胜率/最好/最差；不报夏普
```

事件研究的三条纪律：
- 每条必须有 `label`，否则图上的点无法解释
- 不计佣金（要看价格反应，不是模拟交易）
- **不许**报夏普、年化、最大回撤——这套指标在这里没有意义

### 组合轮动

```python
orders = []
if ctx.shares("B") > 0:
    orders.append(Order("B", "sell", reason="rotate_out"))   # 先卖
if ctx.shares("A") == 0:
    orders.append(Order("A", "buy", weight=0.95, reason="rotate_in"))  # 后买
return orders
```

先卖后买，同一开盘价成交；不要假设卖出资金能当天到账做 T+0（A 股不成立，港股美股另行确认）。

## 四、写完之后立刻自查这五行

1. `res.metrics["trade_count"] > 0`：为 0 先查指标是否全是 NaN、条件方向是否写反。
2. `res.equity[0]["value"] == initial_cash`：不等说明预热段偷偷交易了。
3. `res.trades[-1]["exit_reason"] == "eod_close"`：不是的话可能提前清仓了。
4. `len(res.rejects) == 0`：有拒绝记录说明现金/手数/涨跌停有冲突，要解释给用户。
5. 打开 `trades.csv` 看第一行：买入价数量级对不对（3 元的 ETF 不该出现 300 元）。

## 五、常见实现错误（每条都真实存在过）

| 现象 | 根因 | 修法 |
|---|---|---|
| 年化 200%、夏普 5+ | 用收盘价决策又用收盘价成交 | 改次日开盘，或明确标注"含当日收盘假设" |
| 首笔交易在评估起点之前 | 预热段调用了策略 | 用 `eval_start` 卡住；不要自己在策略里判断日期 |
| 交易笔数极少（1—2 笔） | 指标窗口比样本还长 | 检查 `len(closes)` 与窗口；缩短窗口或延长数据 |
| 换手率高得离谱 | 把"状态"当"事件"，每天都在触发 | 用 `cross_above` 而非 `>` |
| 收益比买入持有高十倍 | 漏了费用或复权口径不一致 | 打印 `total_fees`；核对 `--fq` |
| 所有交易盈亏都是 ±8.00% | 止损直接用触发价成交、没有滑点 | 加滑点，用次日开盘价成交 |
| 净值曲线出现台阶 | 停牌日没数据却记了 0 收益 | 缺失日沿用上一收盘价计价 |

## 六、参数扫描与成本压力（默认要做）

```python
from btcore import param_sweep
rows = param_sweep(lambda cfg: {"total_return_pct": run(cfg["fast"], cfg["slow"]).metrics["total_return_pct"]},
                   {"fast": [3, 5, 10], "slow": [15, 21, 40]})
```

- 至少扫两个参数、各三档，看结论是不是只在最优点成立
- 成本至少跑 1× / 2× / 4× 三档，看结论是不是被成本吃掉
- 扫描结果写进报告"稳健性"段，一句话说清"9 组里几组为正"

## 七、API 与市场规则

完整函数签名见 `references/engine-api.md`；A 股/港股/美股的手数、T+1、费用、涨跌停差异见 `references/market-rules.md`。

## 八、退出条件

- 脚本能 `python run_xxx.py` 一次跑通
- 三件套都非空，`summary.json` 里 `metrics` 字段齐全
- 上面第 4 节的五行自查全过
- 参数扫描与成本压力结果已生成

然后才进 WF-04。
