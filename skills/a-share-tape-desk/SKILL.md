---
name: a-share-tape-desk
description: 沪深A股盘中交易数据与计算工具。取实时行情、算技术指标、扫全市场情绪、排板块龙头、算仓位止损、管预警清单。当用户问A股行情、个股技术面、大盘情绪、热点板块、买卖点位、仓位多少时使用。
---

# A股盘面工具箱（a-share-tape-desk）

这个技能只做一件事：把"能算的"算出来，交给专家去解释。
价格、涨跌幅、涨跌停、指标、情绪分、仓位股数——全部由脚本计算，不让模型估。

## 一、什么时候用

| 用户说的 | 用哪条命令 |
|---|---|
| "看看茅台现在多少" / "我持仓这几只怎么样" | `quote` |
| "这票技术面怎么样" / "能不能拿" / "支撑压力在哪" | `tech` |
| "今天大盘怎么样" / "情绪如何" / "该几成仓" | `pulse` |
| "今天什么板块强" / "龙头是谁" | `sectors` |
| "我 20 万想买这个，怎么买" / "止损放哪" | `plan` |
| "跌到 1300 提醒我" | `watch add` |
| "上次那个预警触发了吗" | `watch check` |
| 数据取不到 / 判断不准 | `doctor` |

## 二、入口

```bash
python <技能目录>/scripts/tapedesk.py <命令> [参数]
```

Windows 下用 `python`，macOS / Linux 下用 `python3`。
**任何命令加 `--json` 输出结构化数据**（`--json` 放在命令前后都行）。

命令清单：

```bash
tapedesk.py session                              # 交易时段（盘前/竞价/早盘/午休/午盘/收盘）
tapedesk.py quote 600519 300750 688981           # 批量实时快照
tapedesk.py tech 600519 --days 250               # 技术面体检（本地算指标）
tapedesk.py pulse                                # 全市场情绪体温（56页全量扫描，约2秒）
tapedesk.py sectors --kind both --top 8          # 行业+概念板块排行与龙头
tapedesk.py plan 600519 --capital 200000 --risk-pct 1 --max-position 25
tapedesk.py watch add 600519 --type price_below --threshold 1300 --note "跌破MA60"
tapedesk.py watch check                          # 核对全部预警
tapedesk.py watch list / watch rm --id w12345678
tapedesk.py doctor                               # 数据链路自检
```

## 三、必须遵守的执行顺序

1. **先 `session`**（可与其他命令并行）：知道现在是不是盘中，决定报告里写"实时"还是"上一交易日收盘"。
2. **再取数**：按问题取 `quote` / `tech` / `pulse` / `sectors`，互不依赖的并行调用。
3. **最后 `plan`**：只有拿到真实价格与 ATR 之后才算仓位，**不要自己心算**。
4. 报告末尾统一附免责声明。

## 四、读输出时要看住的几个字段

- `data_age` / `phase`：数据是实时还是定格。午休、收盘后、周末必须说清楚。
- `limit_up` / `limit_down` / `is_limit_up`：涨停价是按"昨收 × 板块限制比例"算的，主板 10%、创业板/科创板 20%、主板 ST 5%。
- `flags`：源数据被降级或重算过，必须在报告里向用户说明。
- `sentiment.score` / `temperature` / `risk_level` / `suggested_max_position`：情绪温度、风险等级、仓位上限，直接引用，不要另编。
- `plan.shares` / `plan.checks` / `plan.min_viable`：股数为 0 时，把 `min_viable.suggestion` 原样告诉用户，不要含糊过去。
- `sectors.hot[].leader_candidates`：龙头候选按涨幅55%+成交额分位25%+换手分位12%+涨停8%评分，不是"谁涨得最高就是龙头"。

## 五、异常处理（按这个顺序降级，不要跳过）

| 现象 | 处置 |
|---|---|
| `quote` 有 `missing` | 说明哪只没取到，其余照常输出；提示可能停牌或代码错误 |
| 全部取不到，`errors` 非空 | 跑 `doctor` 定位是哪一层失败；把失败原因如实告诉用户，不要编价格 |
| `--no-cache` 后仍失败 | 公开接口被限流，告知需等 1–2 分钟；不要连续重试超过 2 次 |
| `tech` 返回"K线不足30根" | 次新股或长期停牌，改用 `quote` 的日内数据 + 明确说明指标不可用 |
| `pulse` 的 `declared_total` 与实际行数差很多 | 分页丢包，报告里注明样本量，不要当成全市场 |
| 北交所/港股/美股代码 | 直接说明不在服务范围（脚本会抛 CodeError） |

## 六、绝对不要做

- 不要自己编价格、涨跌幅、PE、成交量。取不到就说取不到。
- 不要把 `quote` 的价格当成"可以买到的价格"——涨停板买不到，跌停板卖不掉，脚本的 `is_limit_up` 已经标出来了。
- 不要在没算 `plan` 的情况下给出"买多少股""亏多少"的数字。
- 不要承诺收益，不要说"必涨""稳赚""抄底机会"。用概率和条件表述。
- 不要推荐"今天买哪只"。用户问代码，就先问他自己的逻辑，再给条件化的分析。

## 七、依赖

- Python 3.8+，**只用标准库**（urllib / json / concurrent.futures / datetime），无需 pip 安装。
- 网络：需能访问 `qt.gtimg.cn`、`hq.sinajs.cn`、`vip.stock.finance.sina.com.cn`、`web.ifzq.gtimg.cn`。
- 缓存：`~/.workbuddy/cache/a-share-tape-desk/`（可用环境变量 `ATD_CACHE_DIR` 改）。
- 预警清单：默认 `~/.workbuddy/cache/a-share-tape-desk/watchlist.json`（可用 `ATD_WATCHLIST` 指到别处）。

## 八、参考资料

- `references/data-sources.md` — 每个接口的地址、字段映射、实测时间
- `references/indicator-math.md` — 指标公式与口径（为什么这么算）
- `references/sentiment-rubric.md` — 情绪评分与风险等级的完整规则
- `references/risk-and-compliance.md` — 仓位算法、合规红线、免责表述
- `templates/` — 五类报告的输出骨架
