# 口径卡模板（spec.json）

脚本只读这张卡，不读聊天记录。字段名固定，不要临时加自由字段。

```json
{
  "task_id": "bt-20261028-001",
  "mode": "strategy",
  "market": "china_a",
  "universe": ["510300.SH"],
  "universe_names": {"510300.SH": "沪深300ETF"},
  "eval_start": "2019-01-01",
  "eval_end": "2024-12-31",
  "warmup_days": 180,
  "signal": {
    "entry": "close MA20 cross_above close MA60",
    "exit": "close MA20 cross_below close MA60",
    "field": "close",
    "event_vs_state": "event",
    "compound_logic": "all"
  },
  "execution": {
    "fill": "next_open",
    "slippage_bps": 5.0,
    "same_day_close_accepted": false
  },
  "sizing": {
    "method": "full_position",
    "target_weight": 0.95,
    "lot_size": 100,
    "max_positions": 1,
    "allow_add": false
  },
  "exits": {
    "priority": ["reverse_signal", "stop_loss"],
    "stop_loss_pct": 8.0,
    "take_profit_pct": null,
    "max_holding_days": null
  },
  "costs": {
    "commission_bps": 2.5,
    "min_commission": 5.0,
    "stamp_tax_bps": 5.0,
    "transfer_bps": 0.1,
    "slippage_bps": 5.0
  },
  "benchmark": "buy_and_hold",
  "output_language": "zh",
  "assumptions_note": "用户接受 8% 止损按收盘价确认，不模拟盘中触发",
  "user_choices": [
    {"question": "涨幅 5% 当天买还是次日开盘买", "answer": "次日开盘"}
  ]
}
```

## 字段约束

| 字段 | 允许值 | 说明 |
|---|---|---|
| `mode` | `strategy` / `event` / `portfolio` | 决定后续用哪套指标与报告结构 |
| `market` | `china_a` / `hong_kong` / `us` | 决定手数、T+1、默认成本 |
| `signal.event_vs_state` | `event` / `state` | `event` 只认穿越那一刻 |
| `execution.fill` | `next_open` / `next_close` / `same_close` | `same_close` 必须同时 `same_day_close_accepted=true` |
| `exits.priority` | 数组 | 同一根 bar 上多个出场条件同时触发时按顺序取第一个 |
| `warmup_days` | 整数 | 一般取最长指标窗口 × 1.5（自然日） |

## 改动规则

- 口径卡是唯一事实来源。用户中途说"改成年初至今"，改卡、改 `eval_start`，然后**从 WF-02 重跑**，不要只改脚本。
- 每次改卡留一条 `user_choices`，交付时把这几条原样贴进回复的"口径"段。
