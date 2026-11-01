---
name: saudi-entry-playbook
description: Operational playbook for Saudi market entry. Nine reference cards (entry gate, Saudization, entity routes, Etimad tendering, tax, product compliance, partner screening, business rhythm, risk and exit) plus five dependency-free Python calculators for eligibility rules, route cost comparison, partner scoring, opportunity ranking and self-test. Load a card only when its gate is open.
---

# Saudi Entry Playbook

这是「沙特商务拓展专家·旗舰版」的操作台。它的作用不是提供谈资，而是让每一道闸门都有可复核的依据和可交付的产物。

## 使用原则

1. **按门取卡**：只在对应闸门打开时读对应卡片，不要一次读完九张。读完不用等于没读。
2. **卡片是骨架，不是结论**：卡片给出判定维度、常见坑和核对路径；具体条款、费率、门槛必须回到官方渠道核对，并在输出里标注检索日期。
3. **脚本只算不判**：脚本做算术和规则匹配，输出结构化结果；是否放行、怎么走，由顾问判断并说明理由。
4. **不确定就标注**：`待核实` 是合格答案，编造不是。

## 卡片索引

| 闸门 | 卡片 | 解决什么 |
|---|---|---|
| G1 准入 | `references/01-entry-gate.md` | 外资能不能做、需要哪些许可、产品能不能进 |
| G1/G5 | `references/02-saudization-nitaqat.md` | 沙特化分级怎么算、招人前要算什么账 |
| G2 路径 | `references/03-entity-routes.md` | 独资/合资/代理/许可/RHQ/特区的取舍逻辑 |
| G4 投标 | `references/04-etimad-tender.md` | 政府项目资格、保函、分类分级、常见废标点 |
| G2/G5 | `references/05-tax-and-fiscal.md` | 所得税、扎卡特、增值税、预提税、关税口径 |
| G1/G5 | `references/06-product-compliance.md` | SABER/SASO 认证、电子发票、标签与准入 |
| G3 渠道 | `references/07-partner-scorecard.md` | 伙伴来源、八维评分、红旗项、尽调与谈判 |
| 全流程 | `references/08-business-rhythm.md` | 周节奏、斋月朝觐、决策链、沟通与礼仪 |
| G5 风险 | `references/09-risk-and-exit.md` | 风险分类、止损线、退出路径与条款 |

## 模板索引

| 模板 | 用途 |
|---|---|
| `templates/01-intake-card.md` | G0 立案卡 |
| `templates/02-entry-verdict.md` | G1 准入判定书 |
| `templates/03-partner-scorecard.md` | G3 伙伴评分卡 |
| `templates/04-mobilization-checklist.md` | G5 落地清单与风险台账 |

## 脚本索引

所有脚本仅依赖 Python 标准库，Windows / macOS / Linux 均可直接运行。

```bash
# G1 准入判定
python scripts/entry_gate.py --input fixtures/entry_gate_case.json

# G2 路径三年账
python scripts/route_cost.py --input fixtures/route_cost_case.json

# G3 伙伴八维评分
python scripts/partner_score.py --input fixtures/partner_score_case.json

# G4 商机排序
python scripts/pipeline_rank.py --input fixtures/pipeline_case.json

# 全部自检
python scripts/selftest.py
```

输出统一为 JSON（`--format md` 可切换为 Markdown 表格），字段含义见各脚本头部注释。

## 与其他组件的关系

- 本 Skill 只提供依据与工具，不定义人设与语气；人设、闸门编排、输出规范在 `agents/saudi-market-entry-pro.md`。
- 需要实时信息（招标公告、政策更新、展会排期、企业注册状态）时，用联网检索核对官方站点，不依赖本 Skill 的静态卡片。
- 卡片中的数字若与官方最新公告不一致，以官方为准，并在交付物中记录差异。
