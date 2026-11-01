---
name: czl-uae-pa-toolkit
description: "Working toolkit for the UAE Public Affairs Authority Advisor — emirate comparison matrices, regulatory domain index, stakeholder and decision-path maps, communication red lines, a five-dimension risk scoring model, deliverable templates, and a source-verification protocol. Load individual reference files on demand."
---

# UAE 公共事务作业工具箱（czl-uae-pa-toolkit）

本技能为「阿联酋公共事务权威顾问」提供可执行的作业组件。它不存放法律条文全文，而是存放**作业方法、判断矩阵、模板与校验规则**——需要条文原文时，按 `07` 的信息源协议到官方渠道核实。

## 使用原则

1. **按需加载**：一次任务只读 1–3 个文件，不要全量读取。
2. **方法优先**：本工具箱给的是"怎么判断"，不是"标准答案"。法规会变，判断框架不会。
3. **不确定就标不确定**：任何拿不到官方原文的条目，写"待核实"，不得用经验值伪装成事实。

## 文件索引

| # | 文件 | 内容 | 对应工作流 |
|---|---|---|---|
| 01 | `references/01-emirate-profile-matrix.md` | 七酋长国画像与八维对比矩阵（含同国分层） | W2 |
| 02 | `references/02-regulatory-domain-index.md` | 12 个监管域 × 三层主管机构 × 常见动作 | W1 |
| 03 | `references/03-stakeholder-decision-path.md` | 审批层/影响层/监督层映射法与推进表 | W3 |
| 04 | `references/04-communication-redlines.md` | 对外沟通红线清单与改写对照 | W4 |
| 05 | `references/05-risk-scoring-model.md` | 五维风险打分模型、权重、阈值与等级 | W5 |
| 06 | `references/06-deliverable-templates.md` | 一页纸/决策备忘/回函框架/危机声明/口径包模板 | W5、W6 |
| 07 | `references/07-source-verification-protocol.md` | 来源分级、时效校验、常见信息陷阱 | 全流程 |

## 脚本索引

| 脚本 | 用途 | 用法 |
|---|---|---|
| `scripts/risk_score.py` | 五维风险打分与等级判定 | `python risk_score.py --rule 3 --approval 4 --timing 2 --reputation 5 --enforcement 4` |
| `scripts/brief_check.py` | 校验 12 项任务简报完整性 | `python brief_check.py --file brief.json` |

两个脚本均为纯标准库实现，无第三方依赖，可在任意 Python 3.8+ 环境运行。

## 模板索引

| 模板 | 用途 |
|---|---|
| `templates/one-pager.md` | 一页纸决策摘要 |
| `templates/decision-memo.md` | 上会决策备忘 |
| `templates/regulator-reply.md` | 监管问询回函框架 |
| `templates/crisis-statement.md` | 危机对外声明三段式 |

## 边界

- 本工具箱不含任何第三方版权文本、条文汇编或他人整理的知识库。
- 所有矩阵与评分模型为独立设计，仅用于内部判断排序，不构成法律结论。
