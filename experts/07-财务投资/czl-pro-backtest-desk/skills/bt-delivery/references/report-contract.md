# 报告载荷契约（payload）

`btreport.render(payload, out)` 把这份 JSON 塞进 `kit/template/report.tpl.html`。字段改名会直接让页面白屏，改之前先跑 `node tools/check_report.js`。

## 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `lang` | `"zh"` / `"en"` | 是 | 驱动全部界面文案，不填默认 zh |
| `title` | string | 是 | 报告主标题 |
| `subtitle` | string | 否 | 副标题（口径一句话） |
| `chips` | `[{k,v}]` | 否 | 顶部信息条：区间、市场、标的、资金、成本 |
| `kpis` | `[{label,value,sub,tone}]` | 是 | 建议 6 个；`tone` 取 `up`/`down`/`flat` |
| `equity` | `[{date,value}]` | 是 | 净值序列，至少 2 点才画图 |
| `benchmark` | `[{date,value}]` | 否 | 买入持有对照，长度与 equity 对齐最好 |
| `monthly` | `[{year,months[12],ytd}]` | 否 | 空数组则整块隐藏 |
| `table_mode` | `"trades"` / `"event"` | 否 | 事件模式切换成交表列名 |
| `trades` | 数组 | 否 | 最多建议 400 行 |
| `markers` | `[{date,action}]` | 否 | `action` 取 `buy`/`sell`，按日期对齐净值点 |
| `notes` | `[{title,items[]}]` | 否 | 底部"口径与说明"，建议 3—4 块 |
| `warnings` | `[string]` | 否 | 顶部黄色提示条 |
| `footer` | string | 否 | 免责声明（默认已内置） |

## 对齐规则（最容易错的地方）

1. `markers[].date` 必须能在 `equity[].date` 里找到，否则那个点不会画（不是报错，是静默丢失）。
2. `benchmark` 与 `equity` 的起始值会被各自归一化到 100 后比较，所以两条线可以直接叠。
3. `monthly` 里某月无数据填 `null`，不要填 0（0 会被画成"这个月持平"）。
4. `kpis[].value` 是**已经格式化好的字符串**（含 `%`、`+` 号），模板不再二次处理。

## 事件研究的差异

- `table_mode="event"`
- `trades` 每行：`symbol` 放事件标签、`entry_date`、`exit_date`、`entry_price`、`exit_price`、`pnl_pct`
- `equity` 用等权累计合成一条曲线（仅作走势参考，不是真实账户）
- KPI 用事件数/平均/中位/胜率/最好/最差，**不要放夏普、年化、最大回撤**

## 自检

```bash
node tools/check_report.js out/index.html
```

九项检查：脚本无异常、标题、KPI 数量、三张图、月度表、成交表、页脚。
