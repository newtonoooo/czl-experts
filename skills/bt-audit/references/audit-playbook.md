# 审计执行手册（每项的具体查法）

配合 `SKILL.md` 的 12 项清单使用。命令以专家包根目录为工作目录。

## 1 可运行性

```bash
python run_xxx.py; echo "exit=$?"
ls -la out/xxx_equity.csv out/xxx_trades.csv out/xxx_summary.json
```

看三件事：退出码为 0、没有 `Traceback`、日志里没有"跳过 N 个标的"这类悄悄降级的话。

## 2 三件套完整

```bash
python - <<'EOF'
import json
s = json.load(open("out/xxx_summary.json", encoding="utf-8"))
print(sorted(s.keys()))
print(s["metrics"]["trade_count"], s["metrics"]["total_return_pct"])
EOF
```

## 3 成交时点（最关键的一项）

```bash
head -3 out/xxx_trades.csv
```

拿第一笔的 `entry_date` 回数据里找：它的 `entry_price` 必须等于**这一天**的 `open`（乘上滑点）。如果等于前一天的 `close`，就是未来函数。

```bash
python - <<'EOF'
import csv
rows = list(csv.DictReader(open("data/bars_x.csv")))
by = {r["date"]: r for r in rows}
t = list(csv.DictReader(open("out/xxx_trades.csv")))[0]
bar = by[t["entry_date"]]
print("记录买入价", t["entry_price"], "当日开盘", bar["open"], "前日收盘", rows[rows.index(bar)-1]["close"])
EOF
```

## 4 预热隔离

```bash
python -c "
import json;s=json.load(open('out/xxx_summary.json'));print(s['metrics']['initial_value'], s['meta']['initial_cash'])"
```

两个数必须相等。不等就是预热段交易了。

## 5 手数约束

```bash
python - <<'EOF'
import csv
rows = list(csv.DictReader(open("out/xxx_trades.csv")))
bad = [r for r in rows if int(float(r["shares"])) % 100 != 0]
print("违反手数:", len(bad), bad[:2])
EOF
```

## 6 T+1

```bash
python - <<'EOF'
import csv
rows = list(csv.DictReader(open("out/xxx_trades.csv")))
print("同日买卖:", [r for r in rows if r["entry_date"] == r["exit_date"]][:3])
EOF
```

A 股应为空列表。

## 7 费用计提

把 `CostModel.zero()` 换进去重跑一次，收益应当**变好**。如果一模一样，说明费用没进账。

```bash
python -c "
import sys;sys.path.insert(0,'kit')
from btcore import CostModel
print(CostModel.zero().describe())"
```

## 8 强平

```bash
tail -2 out/xxx_trades.csv
```

末笔 `exit_reason` 应为 `eod_close`；日期应等于 `eval_end` 或样本最后一根 bar 的日期。

## 9 账户恒等式（抽一天手算）

取任意一天，用那天的 `close` 算 `现金 + Σ(股数×收盘)`，与 `equity.csv` 里同一天的值比，误差应 < 0.01。

## 10 记录配对

`buy_fills` 应等于建仓次数；`sell_fills` 应等于减仓/清仓次数；`trade_count` 是平仓笔数（部分卖出会记多笔）。三者关系能对上就说明配对没乱。

## 11 首末 5 笔人眼过

```bash
head -6 out/xxx_trades.csv; echo ...; tail -5 out/xxx_trades.csv
```

重点看：
- 买入价量级对不对（对照当日行情）
- `holding_days` 有没有全是一样的值（说明可能是固定周期平仓，或日期算错）
- 首笔日期是否在评估区间内
- 有没有 `shares` 为 0 或负数

## 12 基准对照

```python
from btcore import buy_and_hold
bh = buy_and_hold(bars, res.meta["start"], res.meta["end"])
print((bh[-1]["value"]/bh[0]["value"]-1)*100)
```

差异超过 10 倍，先查复权与区间，再查是否漏费用。

---

## 附：快速全查脚本

```bash
python tools/selftest.py            # 内核本身是否可信（13 例）
node tools/check_report.js out/index.html   # 报告是否能正常渲染
```

内核自检不过，后面所有结果都不用看了。
