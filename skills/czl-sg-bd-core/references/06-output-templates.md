# 输出模板字段说明

模板文件在 `assets/templates/`，可直接复制。字段定义如下，禁止增删必填列（可加备注列）。

## 一、account-card.md（单账户卡片）

12 个必填字段：

| 字段 | 内容要求 | 不合格示例 |
|------|---------|-----------|
| 账户名 | 法律主体全称 + 本地角色 | "某某集团" |
| 实体核验 | 四问结论，含 UEN 或"待核实" | "是新加坡大公司" |
| 业务相关性 | 与我们产品的具体接口环节 | "行业相关" |
| 最高信号等级 | 一级/二级/三级/四级 + 依据 E 编号 | "有需求" |
| Fit 档 | 高/中/低 + 五维简述 | "85 分" |
| Priority 档 | 高/中/低 + 六维简述 | "很优先" |
| 反证三条 | 每条含"反证 + 回应" | "竞争激烈" |
| 采购主体 | 已确认主体或"待确认" | "采购部" |
| 进入路径 | 路径 + 触发条件 | "找代理" |
| 首触对象 | 部门 + 职能（不含人名） | "王总" |
| 首触由头 | 可验证的近期变化 + E 编号 | "介绍我们的产品" |
| 下一步动作 | 一条，30 天内可完成 | "保持联系" |

## 二、target-list.csv（候选池与排序）

```
rank,account,entity_type,uen_or_hint,local_business,top_signal,fit_band,priority_band,evidence_ids,counter_summary,verdict,next_action
```

| 列 | 说明 |
|----|------|
| `rank` | 按 Priority 排序；观察区账户 rank 留空 |
| `entity_type` | 集团/本地法人/分公司/项目公司/设施/机构/总包 |
| `uen_or_hint` | UEN 或登记线索；无则写 `待核实` |
| `top_signal` | 1/2/3/4，对应信号等级 |
| `fit_band` / `priority_band` | 高/中/低 |
| `evidence_ids` | 分号分隔，如 `E3;E7` |
| `verdict` | A/B/C/D 或 `观察区` |
| `next_action` | 一条具体动作 |

规则：`rank` 连续不跳号；`verdict=A` 的行必须 `top_signal<=2` 且 `evidence_ids` 至少两个。

## 三、evidence-ledger.csv（证据台账）

```
claim_id,claim,grade,source_name,published_or_accessed,url,status,note
```

- `grade`：A/B/C/D
- `status`：已确认/部分确认/待确认/已失效
- `url` 无法公开时填 `N/A`，并在 `note` 说明获取方式，该条最高 B 级

校验：运行 `python scripts/ledger_check.py <ledger.csv>`。

## 四、bd-plan.md（90 天行动计划）

表头固定五列：

```
| 动作 | 对象 | 验证假设 | 成功判据 | 失败后的转向 |
```

- 0–30 天：以补证据、确认采购主体、锁定入口为主，不安排销售动作。
- 30–90 天：首触、踏勘、试点方案、伙伴初谈。
- 90–180 天：报价、条款、复制到第二家。

每条动作必须能被第三方判断"做没做、成没成"。

## 五、写作规则

1. 表格列 ≤7；超出拆表。
2. 不用颜色、不生成图片；用箭头、缩进、表格表达结构。
3. 事实句带 E 编号；建议句用祈使句，写清对象与时点。
4. 中英混排时，机构与平台名首次出现保留英文原名。
5. 结论段控制在 5 行内，先给判断再给依据。
6. 不写"建议进一步调研""加强沟通""提升影响力"这类不可执行表述。

## 六、交付组合

| 用户要什么 | 给什么 |
|-----------|--------|
| 快速判断 | 结论 + 证据 + 缺口（不落文件） |
| 一份名单 | target-list.csv + 每家的 3 行摘要 |
| 深度评估 | account-card.md × N + target-list.csv + evidence-ledger.csv |
| 落地执行 | bd-plan.md + 首触要点 |
| 对外汇报 | 全流程结构（见 Agent 第四节）+ 台账附件 |
