---
name: assortment-roles
description: "Second gate. Diagnoses a store as four product roles - traffic driver, profit core, image anchor and clearance - instead of a flat list of listings. Checks gross-profit concentration, sell-through rate, inventory days, price-band coverage and whether cheap traffic drivers are cannibalising the profit core. Returns a role table, the three structural moves with the highest payoff, and a cut list. Use for 'nothing sells', 'should I launch this', 'which SKUs should I kill', or before a campaign assortment decision."
---

# 货盘：一个店不是一堆链接

## 什么时候用

- "上新上什么" / "该砍哪些款"
- "销量有，利润没有"
- "动销差，一半链接没出单"
- 大促前定主推、定备货优先级

## 四个角色

| 角色 | 任务 | 毛利率 | 库存深度 | 投放 | 判断它称职的标准 |
|---|---|---|---|---|---|
| 引流款 | 拿流量、拉新客 | 低（10%–25%） | 浅，快返 | 高，敢亏一点 | 带来的新客能不能被利润款接住 |
| 利润款 | 赚钱 | 高（40%+） | 中，稳定 | 中，看 ROI | 毛利贡献占比是否过半 |
| 形象款 | 立价格锚、抬客单 | 高 | 极浅 | 低 | 有没有人真的买，还是只用来比价 |
| 清货款 | 回现金、清库存 | 负到低 | 只减不增 | 无 | 清完就下架，不许回补 |

**角色不是按价格分的，是按任务分的。** 一个 39 元的杯子可能是利润款（成本 12），一个 199 元的包可能是引流款（成本 150）。

## 诊断五件事

### 1. 毛利集中度

`前 3 个 SKU 毛利占比`。超过 70% 就是脆弱结构——一个款被跟卖或断货，整店利润塌一半。

### 2. 动销率

`近 30 天有销量的 SKU 数 ÷ 在架 SKU 数`。低于 60% 说明货盘在拖库存和流量。

### 3. 库存周转天数

`平均库存成本 ÷ 日均销货成本`。超过 90 天，现金已经在货里睡着了。服装、季节品要看季节窗口，不能只看天数。

### 4. 价格带覆盖

把在架 SKU 按价格分 5 档，看销量分布。**断档**（某一档完全没货）会让买家在你的店里找不到下一件，连带率上不去。

### 5. 角色错位

三个信号：

- 引流款销量占比高、毛利占比接近 0，且**利润款销量没跟着涨** → 流量白引了
- 利润款库存最深，但销量最慢 → 押错款
- 清货款还在补货 → 角色混乱

## 输出

一张货盘结构表：

| SKU | 角色 | 售价 | 单均贡献毛利 | 近 30 天销量 | 毛利贡献占比 | 库存天数 | 判定 |

后面接三件事，不要多：

1. **保谁**：毛利贡献最大的 1–2 个款，给资源和库存优先级
2. **改谁**：角色错位的款，给具体改法（改价 / 改规格 / 改主图人群 / 换流量来源）
3. **砍谁**：动销为 0 且库存天数 > 90 的款，给清货方式和时间点

砍单要给数量，不要给形容词。"砍 7 个款，释放库存资金约 3.2 万"比"优化货盘结构"有用。

## 异常

| 情况 | 处理 |
|---|---|
| 只给销量不给毛利 | 先按售价排序粗判，明确标注"毛利未核实，角色判定为推测" |
| SKU 上百个 | 先按价格带和销量做二维分布，只对前 20 个和末位 20 个做逐款判定 |
| 全是新品，没有历史数据 | 不做角色判定，改做"上新结构建议"：首单比例 5:3:1:1（引流:利润:形象:清货） |
| 用户舍不得砍 | 算清每个滞销款占用的资金和仓租，把"不砍的成本"写成数字 |
| 店只有 3–5 个链接 | 不做四角色，直接做单款账本和单款流量结构 |

## 与其他技能的关系

- 上游：`sku-margin`（每款的贡献毛利是角色判定的基础）
- 下游：`traffic-budget`（预算优先给利润款）、`campaign-runbook`（备货优先级按角色排）
- 判定阈值与动作库：`references/role-playbook.md`
