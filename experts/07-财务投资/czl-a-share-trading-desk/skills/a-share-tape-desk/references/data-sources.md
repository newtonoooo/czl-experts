# 数据源与字段映射

采集时间：2026-10-27 11:30–12:20（北京时间），全部接口当场实测通过。
接口均为公开行情页面对外提供的查询地址，不需要账号。

> **重要**：这些接口没有任何书面授权或 SLA 承诺。产品把它当作"尽力而为"的数据来源，
> 商用前必须评估合规与稳定性风险（见项目 `docs/商业发布风险清单.md` 第 2 项）。

## 1. 实时快照 — 腾讯行情（主源）

```
http://qt.gtimg.cn/q=sh600519,sz300750
Referer: https://gu.qq.com
编码: GBK
```

一次请求可带多只（本项目每批 40 只）。返回每条以 `~` 分隔，字段位置实测如下：

| 索引 | 含义 | 备注 |
|---|---|---|
| 0 | 市场标记 | 1=沪, 51=深 |
| 1 | 名称 | |
| 2 | 代码 | |
| 3 | 最新价 | |
| 4 | 昨收 | |
| 5 | 今开 | |
| 6 | 成交量（手） | |
| 7 / 8 | 外盘 / 内盘 | |
| 9–28 | 买卖五档 | 本项目不使用 |
| 30 | 时间戳 | yyyymmddHHMMSS |
| 31 / 32 | 涨跌额 / 涨跌幅% | 仅用于交叉校验 |
| 33 / 34 | 最高 / 最低 | |
| 35 | `价/量/成交额(元)` | **成交额取这一段，精确到元** |
| 36 | 成交量（手） | |
| 37 | 成交额（万元） | 精度较低，仅作兜底 |
| 38 | 换手率% | |
| 39 | PE(TTM) | |
| 43 | 振幅% | 交叉校验用 |
| 44 / 45 | 流通市值 / 总市值（亿元） | |
| 46 | PB | |
| 47 / 48 | 涨停价 / 跌停价 | 已按板块限制比例给出，实测 600519=1484.98、300750=285.60 |
| 49 | 量比 | |
| 51 | 均价 | |

**校验规则**：涨跌幅、振幅用 `最新价/昨收/最高/最低` 自行重算；与厂商字段偏差 >0.05 个百分点时
以重算值为准，并在 `flags` 里写一条提示。这样即使厂商字段顺序变动，核心数值也不会错。

## 2. 实时快照 — 新浪行情（备源）

```
http://hq.sinajs.cn/list=sh600519,sz300750
Referer: https://finance.sina.com.cn
编码: GBK
```

字段（逗号分隔）：`名称,今开,昨收,现价,最高,最低,买一,卖一,成交量(股),成交额(元),... ,日期,时间`

缺换手率、量比、PE/PB、市值。因此**只在腾讯失败时用于兜底**，输出里会标注"备源数据"。

## 3. 指数快照 — 新浪简版

```
http://hq.sinajs.cn/list=s_sh000001,s_sz399001,s_sz399006
```

字段：`名称,点位,涨跌额,涨跌幅%,成交量(手),成交额(万元)`。注意成交额单位是**万元**。

## 4. 日线历史 — 腾讯（主源）

```
https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh600519,day,,,250,qfq
Referer: https://gu.qq.com
```

`qfq` 为前复权。返回 `data[code]['qfqday']`，每行 `[日期, 开, 收, 高, 低, 成交量(手), ...]`。
行内没有成交额，也不需要——指标只用价与量。

## 5. 日线历史 — 东方财富（备源）

```
https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=1.600519&klt=101&fqt=1&lmt=250
    &fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58
```

每行：`日期,开,收,高,低,成交量(手),成交额(元),振幅%,涨跌幅%,涨跌额,换手率%`。

> 实测提示：东方财富 `push2*` 系列主机对高频请求有临时断流（连续多次请求后返回 0 字节）。
> 本项目已把主机冷却写进 `atd/net.py`（连续失败 2 次即冷却 90 秒），并把东方财富放在备源位置。

## 6. 全市场快照 — 新浪分页（情绪扫描用）

```
# 总数
http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeStockCount?node=hs_a
# 明细（page 从 1 开始，num 上限实测 100 条/页有效）
http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData
    ?page=1&num=100&sort=changepercent&asc=0&node=hs_a&symbol=&_s_r_a=page
```

明细字段（JSON）：`code, name, trade(现价), settlement(昨收), changepercent, open, high, low,
volume(股), amount(元), per(PE), pb, mktcap(万元), nmc(万元), turnoverratio(%), ticktime`

- `node=hs_a` = 沪深A股，实测 5576 只（不含北交所）。
- 56 页 × 100 条，10 线程并发，实测 **2.07 秒**取全量。
- 本项目用它自己算涨跌家数、涨跌停家数、涨跌分布、成交额，**不依赖任何第三方给出的"情绪值"**。

## 7. 板块聚合 — 新浪

```
# 行业板块
http://vip.stock.finance.sina.com.cn/q/view/newSinaHy.php
# 概念板块
http://vip.stock.finance.sina.com.cn/q/view/newFLJK.php?param=class
# 板块成分股
http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData
    ?page=1&num=80&sort=changepercent&asc=0&node=<板块node>
```

板块字符串（逗号分隔）实测字段顺序：

```
node, 板块名, 成分家数, 均价, 平均涨跌额, 涨跌幅%, 成交量, 成交额, 
领涨股symbol, 领涨股涨跌幅, 领涨股价格, 领涨股涨跌额, 领涨股名称
```

实测数量：行业板块 49 个、概念板块 175 个。

## 8. 分时（未接入主流程，备用）

```
https://web.ifzq.gtimg.cn/appstock/app/minute/query?code=sh600519
```

返回 `data[code]['data']['data']`，每项 `"HHMM 价格 累计量 累计额"`，实测 121 个点（9:30–11:30）。
当前版本没有把分时做成命令，因为"分时形状"用文字描述收益很低；需要时再用。

## 9. 编码与请求头注意事项

- 新浪与腾讯的行情接口返回 **GBK**，必须按 GBK 解码，否则中文名称乱码。
- 新浪 `hq.sinajs.cn` 不带 `Referer` 会返回空内容，必须带。
- 全部请求带 `User-Agent`，`Connection: close`，超时 12 秒，失败重试 2 次（0.4s/0.8s 退避 + 抖动）。
