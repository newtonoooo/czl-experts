# 净利操盘手 · czl-ecom-profit-ops

把单链接账本、货盘结构、投流预算、大促倒排和文案合规串成一条线，先算清赚不赚钱，再谈怎么起量。

- **类型**：Agent 型（单个 AI 专家）
- **分类**：07-SalesCommerce（销售商务 / 电商）
- **作者**：虫志龙（47190078@qq.com）
- **版本**：1.0.0
- **适用平台**：淘宝 / 天猫 / 京东 / 拼多多 / 抖音小店

## 它解决什么问题

大部分电商顾问一上来就给增长方案。这个专家反过来：**先给你一张成本瀑布，看你到底赚不赚钱。**

行业里两种死法它都要拦：

1. **卖得越多亏得越多**——广告和优惠把毛利吃穿，后台看着在涨，账上是负的
2. **大促卖爆但现金流断掉**——钱压在货上，结算还没到

## 七个工作流

| 编号 | 技能 | 做什么 | 主要产出 |
|---|---|---|---|
| A | `sku-margin` | 九层成本瀑布、单均贡献毛利、保本 ROI、保本价、保本单量、最大可承受退货率 | 单链接账本 |
| B | `assortment-roles` | 引流/利润/形象/清货四角色判定，毛利集中度、动销率、周转天数 | 货盘结构表 + 砍单清单 |
| C | `traffic-budget` | 保本 CPC = 毛利率 × 转化率 × 客单价；预算三池；放量阶梯与止损 | 出价上限表 |
| D1 | `promo-math` | 优惠叠加实收、保本实收、备货量、现金占用、五档达成率风险 | 活动机制账本 |
| D2 | `campaign-runbook` | T-60 倒排，按决策点排而非任务清单 | 倒排表 + 三段预算 |
| E | `funnel-review` | UV × 转化率 × 客单价 × (1−退款率) 逐项替换拆解 | GMV 拆解表 + 可以说/不能说 |
| F | `copy-compliance` | 六类文案风险 + 标题结构 + 类目资质 | 合规整改清单 |

## 四个自带工具（纯标准库，无需安装依赖）

```bash
# A 单品账本
python skills/sku-margin/scripts/sku_margin.py ledger \
  --price 129 --cost 38 --ship 6 --commission 0.05 --refund 0.18 \
  --return-ship 8 --return-handling 2 --restock 0.8 --ad-ratio 0.2 --fixed 30000

# A 批量测算整店链接
python skills/sku-margin/scripts/sku_margin.py batch skills/sku-margin/scripts/fixtures/skus.csv --fixed 60000

# D1 活动机制叠加
python skills/promo-math/scripts/promo_math.py stack \
  --price 199 --cost 62 --item-discount 0.9 --member 0.95 \
  --store-threshold 199 --store-coupon 20 --cross-threshold 300 --cross-off 50

# D1 备货与现金占用
python skills/promo-math/scripts/promo_math.py stock \
  --daily 20 --uplift 3 --days 3 --lead-days 10 --moq 50 --unit-cost 62

# E GMV 拆解
python skills/funnel-review/scripts/funnel_check.py decompose \
  --p1-uv 120000 --p1-cvr 0.031 --p1-aov 168 --p1-refund 0.14 \
  --p2-uv 98000 --p2-cvr 0.028 --p2-aov 181 --p2-refund 0.19

# F 文案合规体检
python skills/copy-compliance/scripts/copy_lint.py --text "最安全的儿童保温杯 全网最低" --title --limit 30
```

退出码约定：`0` 健康 / `1` 存在亏损或高风险 / `2` 输入错误。可直接接进发布前的检查脚本。

## 使用示例

- "这个链接卖 129，拿货 38，快递 6，退货率 18%，投流花 8000 卖了 4 万，到底赚不赚钱？"
- "双 11 报跨店满减再叠店铺券，女包客单 199，拿货 62，会不会亏？备多少货？"
- "这个月 GMV 掉了 25%，帮我拆一下是流量还是转化的问题。"
- "儿童保温杯文案写了'食品级 最安全 宝宝专用'，哪些会被罚？"

## 安装

把整个目录放到专家目录：

```
C:\Users\<用户名>\.workbuddy\plugins\marketplaces\my-experts\plugins\czl-ecom-profit-ops\
```

注册（使它出现在专家中心）：

```bash
python <expert-manager>/scripts/register_expert.py <expert-dir>
```

## 头像

`avatars/expert.png`，512×512 PNG，408KB。原创生成，无第三方素材、无水印。可自行替换（PNG/JPG，512×512，≤500KB）。

## 交付文档

- `docs/产品规格说明.md` — 需求来源、功能规格、输入输出规范
- `docs/使用说明.md` — 六个场景的完整用法
- `docs/平台展示文案.md` — 上架用的名称、简介、标签、推荐问法
- `docs/文件清单与开发记录.md` — 文件清单、开发过程、分类原则
- `docs/测试报告.md` — 实际执行的测试与结果
- `docs/商业发布风险清单.md` — 发布前的风险与待决事项（**上架前请先看这份**）
- `CHANGELOG.md` — 版本记录

## 重要说明

1. **平台费率、活动规则、标题字数上限、类目资质要求都会变。** 本专家不含任何"固定"的平台规则数字，一律要求现场检索或以后台当期公告为准。
2. **工具输出是经营测算，不是法律意见或财税意见。** 合规词表用于自查，具体认定以执法机关和平台规则为准。
3. **不提供刷单、虚假交易、改评价、虚假比价类建议。** 这类需求会被拒绝并给出合规替代方案。

## 许可

见 `LICENSE`。著作权归虫志龙所有。
