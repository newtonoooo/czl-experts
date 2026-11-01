---
name: czl-sg-bd-core
description: "Methodology and tooling for the STRAIT six-stage Singapore business development workflow: scoping, candidate pool, dual-layer scoring, buying-entity mapping, first-touch design, action tracking, plus evidence-ledger and package-compliance scripts."
---

# STRAIT 新加坡商务拓展方法论（czl-sg-bd-core）

本技能为「新加坡商务拓展专家·旗舰版」提供方法论、模板与可执行工具。它不是数据仓库，而是一套**可复用的判断流程**：把"找客户"拆成六段可验证的动作，每段有输入、判断门与输出，避免产出"看起来专业但无法执行"的名单。

## 何时加载哪些文件

| 用户需求 | 必读 | 选读 |
|---------|------|------|
| 任何全流程任务 | `01-strait-workflow.md` | `08-quality-gates.md` |
| 需要判断信息可信度、写证据台账 | `02-evidence-standard.md` | `08-quality-gates.md` |
| 需要排序、评分、解释优先级 | `03-scoring-models.md` | `04-entity-and-signal.md` |
| 分不清集团/子公司/项目/采购主体 | `04-entity-and-signal.md` | `01-strait-workflow.md` |
| 需要查新加坡公开数据源 | `05-sg-data-sources.md` | `02-evidence-standard.md` |
| 需要输出文件、表格、报告 | `06-output-templates.md` + `assets/templates/` | — |
| 需要评估合作风险、写合同条款 | `07-risk-matrix.md` | `03-scoring-models.md` |
| 输出前自检 | `08-quality-gates.md` | — |

## 六段结构

```
S 定标 → T 建池 → R 排序 → A 进入 → I 接触 → T 跟踪
```

- **S**：把模糊需求变成 ICP 卡 + 假设登记 + 检索关键词矩阵。
- **T**：按四条路径建候选池，每个候选过"实体四问"。
- **R**：Fit 与 Priority 双层评分，每家写反证三条，排序只看 Priority。
- **A**：判定采购主体与公开采购入口，给出路径与切换触发条件。
- **I**：五位置角色地图 + 首触四要素 + 三个接触顺位。
- **T**：30/90/180 天动作，每条挂假设编号与成功判据。

## 四条硬规则

1. **无编号不事实**：任何企业事实都要有 E 编号与来源，否则降级为推断或删除。
2. **无来源不数字**：收入、人数、设施数、金额、概率，无来源一律不写具体值。
3. **无进入不排序**：算不出"从哪进"的账户，最高只能排第二梯队。
4. **无反证不前三**：进前三必须写清"为什么它可能不该被开发"并正面回应。

## 工具

| 脚本 | 用途 | 依赖 |
|------|------|------|
| `scripts/score.py` | 双层评分，输出档位与置信度，缺失维度强制降级 | Python 3.8+ 标准库 |
| `scripts/ledger_check.py` | 证据台账校验（等级/日期/URL/陈旧/D 级单独支撑） | 同上 |
| `scripts/pack_check.py` | 专家包体检，含 zip 导入头像解析模拟 | 同上 |
| `scripts/build_zip.py` | 生成符合平台导入规范的 zip | 同上 |

四个脚本均为纯标准库实现，不含第三方依赖，可商用再分发。

## 模板

`assets/templates/` 下五个文件，可直接复制填写：

- `intake-form.md` — 需求定标问卷（8 项最小信息集）
- `account-card.md` — 单账户卡片（12 个必填字段）
- `target-list.csv` — 候选池与排序表
- `evidence-ledger.csv` — 证据台账
- `bd-plan.md` — 90 天行动计划

## 使用边界

- 本技能提供的是**判断流程与工具**，不提供企业数据库。所有企业事实必须实时检索并注明来源。
- 不提供征信报告、个人联系方式、商业机密。
- 涉及注册、税务、签证、合同的具体办理，提示用户咨询新加坡持牌专业机构。

## References

- `references/01-strait-workflow.md` — 六段 SOP 卡
- `references/02-evidence-standard.md` — 证据标准与台账规范
- `references/03-scoring-models.md` — 双层评分模型与反证规则
- `references/04-entity-and-signal.md` — 实体类型学与采购信号分级
- `references/05-sg-data-sources.md` — 新加坡公开数据源目录
- `references/06-output-templates.md` — 输出模板字段说明
- `references/07-risk-matrix.md` — 合作风险矩阵与条款建议
- `references/08-quality-gates.md` — 质量门禁与失败案例
