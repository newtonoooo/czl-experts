---
name: egypt-landing-desk
description: Operational desk for Egypt market entry and investment landing. Twelve reference cards (method, macro and FX, legal and investment regime, sites and zones, entry routes, cost stack, customs and logistics, sector screens, risk ledger, national programmes, data ledger, deliverable templates) plus six dependency-free Python tools for FX stress, site scoring, route comparison, landed cost, labour cost and self-test. Load a card only when its gate is open.
---

# 埃及落地作战台 · 操作台

这是「埃及战略顾问·旗舰版」的工作台。它不提供埃及百科，只提供三样东西：**判定维度**、**可复算的算法**、**可交付的文件骨架**。

## 使用原则

1. **按门取卡**：只有对应闸门打开时才读那张卡。一次读十二张等于一张都没读。
2. **卡片给维度，不给结论**：卡里写的是"该看哪几项、常在哪翻车、去哪核"。具体税率、门槛、费率必须回到官方渠道，并在输出里写明检索日期。
3. **工具只算不判**：脚本负责算术和排序，输出结构化结果；放不放行由顾问判断，并说明理由。
4. **`待核实` 是合格答案**：写不出来就写待核实 + 复核渠道。编一个数字比空着危险一百倍。

## 卡片索引

| 闸门 | 卡片 | 解决什么 |
|---|---|---|
| 全流程 | `references/00-method.md` | 五问定框、证据分级、七个常见谬误 |
| G1 | `references/01-macro-fx.md` | 该盯哪些指标、口径怎么区分、贬值怎么传导 |
| G0/G4 | `references/02-legal-investment.md` | 投资法激励、公司形式、土地与许可、汇出约束 |
| G3 | `references/03-sites-zones.md` | 六类落点的适配产业、物流、电力、拿地方式 |
| G4 | `references/04-entry-routes.md` | 六条路径的控制力/速度/资本/退出成本 |
| G5 | `references/05-cost-stack.md` | 成本项拆解、税与社保口径、能源与融资 |
| G5 | `references/06-customs-logistics.md` | ACID 预登记、清关流程、关税结构、原产地 |
| G2 | `references/07-sector-screens.md` | 六个赛道的供需、门槛、中资位置与五维基线分 |
| G6 | `references/08-risk-ledger.md` | 风险分类、台账字段、分级规则、止损线 |
| G6 | `references/09-vision-programs.md` | 国家计划与政策窗口、可申报的激励类型 |
| 全流程 | `references/10-data-ledger.md` | 指标口径台账、发布机构、频率、常见陷阱 |
| G6 | `references/11-deliverable-templates.md` | 七份交付文件的字段骨架 |

## 工具索引

| 工具 | 输入 | 输出 | 用在哪 |
|---|---|---|---|
| `tools/fx_stress.py` | 币种结构、收入/成本、贬值情景 | 毛利变动、现金缺口、对冲缺口 | G1 |
| `tools/site_score.py` | 候选点得分或权重 | 加权排名、敏感性翻转点 | G3 |
| `tools/entry_route.py` | 四维打分、资本、时间要求 | 路径排名、可行性过滤、退出成本 | G4 |
| `tools/landed_cost.py` | CIF、关税、增值税、运保、本地加工 | 单位到岸成本、进口 vs 本地方案差 | G5 |
| `tools/labor_cost.py` | 岗位、人数、工资带、社保率 | 全口径人工、单位产品人工 | G5 |
| `tools/selftest.py` | 无 | 全部工具的固定样例断言结果 | 任意 |

全部脚本仅依赖 Python 标准库，`python tools/selftest.py` 应输出全 PASS。

## 与其他资产的关系

- `agents/egypt-strategy-pro.md` 定义七道闸门的顺序与判定红线，本技能只提供执行素材。
- `docs/` 是给人看的（规格、说明、测试、风险），不参与对话推理。
- `variants/` 存放 manifest 变体，用于解决导入后头像回退成文字的问题，见 `docs/08-图标显示问题诊断.md`。
