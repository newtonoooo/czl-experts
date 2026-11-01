---
name: sku-margin
description: "First gate. Turns one listing into a nine-layer cost waterfall - landed cost, packaging, outbound freight, return freight, return handling loss, commission, payment fee, tax, ad spend - and returns contribution margin per order, breakeven ROI, breakeven price, breakeven volume and the maximum sustainable refund rate. Use whenever someone asks whether a listing makes money, what price to set, whether to raise ad spend, or why a store with rising GMV is running out of cash."
---

# 账本：这条链接到底赚不赚钱

## 什么时候用

- "这个链接赚不赚钱" / "定价定多少"
- "要不要加预算"（本质是问保本 ROI 之下的空间还有多少）
- "卖得挺多的，但账上没钱"
- 上新前算能不能做
- 活动结束后核对实际毛利

## 为什么先做这一步

因为绝大多数运营算的是**假利润**：

- 用 GMV 减拿货价，当毛利（没扣运费、佣金、退货、广告）
- 用"毛利率 45%"讲故事，把广告费放在报表外边
- 用成交单数算成本，用成交额算收入，两边口径不同
- 把退货率当成"少卖了几单"，忘了发货成本照付、回程运费照付、拆封的货卖不掉

一次只算一条链接，算准了再复制。**账算不清的店，增长速度就是亏损速度。**

## 九层成本瀑布

按顺序扣，一层都不能跳：

| 层 | 内容 | 常被漏掉的部分 |
|---|---|---|
| 1 商品成本 | 拿货价 + 头程/入仓 | 打样、质检、次品率 |
| 2 包装 | 纸箱、填充、贴纸、说明书 | 定制品起订量摊薄 |
| 3 发货运费 | 面单 + 超区 + 偏远 | 抛货计费重 |
| 4 退货回程运费 | 按退货单计 | 买家承担时不用付，但揽收失败仍要付 |
| 5 退货货损 | 拆封不能二次销售的比例 | 只能降价处理的残值损失 |
| 6 平台佣金 | 按类目 | 部分类目含技术服务费 |
| 7 支付手续费 | 按渠道 | 分期、花呗类会更高 |
| 8 税费 | 按经营主体 | 小规模与一般纳税人差很多 |
| 9 广告费 | 按成交额占比 | 站内推广 + 内容投流 + 达人佣金 |

固定费用（人工、仓储月租、软件、摄影）单独算，用盈亏平衡单量覆盖，不要摊进单均，否则一上量就失真。

## 三个生死数

```
单均贡献毛利 = (净成交额 − 除广告外全部变动成本 − 广告费) ÷ 发货单数
保本 ROI     = 净成交额 ÷ 广告费上限   其中 广告费上限 = 净成交额 − 除广告外全部变动成本
保本成交价   = 与价格无关的成本 ÷ [有效单数 × (1 − 佣金率 − 支付费率 − 税率 − 广告占比)]
```

保本 ROI 是最有用的一句话：**广告 ROI 低于它，每一单都在补贴买家。** 它等于"1 ÷ 不含广告毛利率"，所以毛利率 30% 的链接，保本 ROI 是 3.3。

## 操作

```bash
# 单链接完整账本
python scripts/sku_margin.py ledger \
  --price 129 --cost 38 --ship 6 --pack 1.2 \
  --commission 0.05 --payment 0.006 --tax 0.03 \
  --refund 0.18 --return-ship 8 --return-handling 2 --restock 0.8 \
  --ad-ratio 0.2 --fixed 30000

# 退货率敏感性（含最大可承受退货率）
python scripts/sku_margin.py sensitivity --price 129 --cost 38 --ship 6 --refund 0.18 --ad-ratio 0.2

# 全店多条链接一起算
python scripts/sku_margin.py batch scripts/fixtures/skus.csv --fixed 60000
```

`--restock 0.8` 表示退货里有 80% 能二次销售；剩下的按成本全额损失计入。这个参数最容易被忽略，也是退货率真正吃利润的地方。

## 输出

一段成本瀑布表 + 三个生死数 + 判定（健康 / 薄利 / 亏损）。

判定阈值：单均贡献毛利为负 = 亏损；占净收入不足 8% = 薄利（一波退货或一次涨价就转亏）。

写进操盘单时，只保留三到五个数，每行标口径，例如：
"单均贡献毛利 38.37 元/单（100 单发货均摊，已扣广告与退货损耗）"。

## 异常

| 情况 | 处理 |
|---|---|
| 给不出退货率 | 先去后台查近 30 天退货率；查不到就按类目常见区间给三档（低/中/高）做区间账本，并标明是估算 |
| 佣金率不确定 | 用后台"费率说明"页的实际值；不确定就按两档算，不要用一个中间数假装确定 |
| 有多个 SKU 混在一个链接 | 拆到 SKU 级再算，混算的账本没有指导意义 |
| 广告费与自然流量分不开 | 用"广告成交额占比"分摊，不要全算给广告，也不要全不算 |
| 用户只想听"能不能做" | 给账本三行 + 一句结论 + 一个前提。别展开九层，他没耐心看 |
| 结果是亏损但用户不想改价 | 给三条路：改价、改成本结构（换包装/换物流/换规格）、改流量结构（降广告依赖）。只能选，不能都不要 |

## 与其他技能的关系

- 下游：`traffic-budget`（用保本 ROI 推保本 CPC）、`promo-math`（把活动价代进同一套成本行）
- 交叉：`assortment-roles`（判断哪些链接该被淘汰）
- 成本行清单：`references/cost-lines.md`
