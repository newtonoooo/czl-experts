---
name: czl-evidence-playbook
description: "Method and toolchain for the Evidence Desk (数证台), an evidence-first data analysis expert. Four layers: workflows/ holds six stage SOPs (briefing and metric definition, data audit, exploration, attribution, five-check grading, delivery) each with inputs, steps, decision rules, output format, exception handling, dependencies and hand-offs; templates/ holds six record sheets that make every gate traceable; references/ holds eight method notes on writing metric definitions, a common metric dictionary, five attribution methods, statistical testing, common attribution traps, chart and report structure, data-quality grading, and privacy limits; scripts/ holds eight pure-stdlib tools for table profiling, period comparison with volume-price-mix decomposition, funnels, cohort retention, ABC and RFM segmentation, significance testing, and Markdown to docx/html export; samples/ holds four small datasets with hand-verifiable ground truth. Read one to two references on demand, never load the whole corpus."
version: 1.0.0
---

# 数证台 · 技能包（v1.0.0）

四层资产，别混着用：流程层说按什么顺序干，表单层留痕，方法层给口径，工具层负责算。

```
czl-evidence-playbook/
├── workflows/    6 份工序 SOP
├── templates/    6 张记录单
├── references/   8 份方法参考
├── scripts/      8 个纯标准库脚本
└── samples/      4 份带真值的样例数据
```

---

## 一、流程层：六道工序

| 工序 | 文件 | 产物 | 什么时候必须走 |
|---|---|---|---|
| W1 立项与口径 | `workflows/01-立项与口径.md` | 任务书 + 口径账 | 每次开工 |
| W2 数据体检 | `workflows/02-数据体检.md` | 质量账 + 可用性评级 | 有原始表格时 |
| W3 探索与假设 | `workflows/03-探索与假设.md` | 假设清单 | 需要归因时 |
| W4 归因五法 | `workflows/04-归因五法.md` | 归因结果 | 需要解释"为什么"时 |
| W5 五验与分级 | `workflows/05-五验与分级.md` | 证据账 + A/B/C/D | **永不跳过** |
| W6 交付与落地 | `workflows/06-交付与落地.md` | 一页纸 / 报告 / 看板规格 | **永不跳过** |

表单一一对应：`templates/T1`–`T6`。

---

## 二、方法层：八份参考

| # | 文件 | 解决什么问题 |
|---|---|---|
| 01 | `references/01-指标口径怎么写.md` | 一张能被人照着复算的口径卡长什么样 |
| 02 | `references/02-常用指标定义库.md` | 40 余个常用指标的定义与坑 |
| 03 | `references/03-归因五法.md` | 五种归因方法的选型表与操作要点 |
| 04 | `references/04-统计检验速查.md` | 比例/均值检验、bootstrap、样本量、多重比较 |
| 05 | `references/05-常见归因陷阱.md` | 辛普森悖论、极端值、回归均值等十类陷阱 |
| 06 | `references/06-图表与汇报结构.md` | 按"要说的话"选图，三层汇报结构 |
| 07 | `references/07-数据质量判定标准.md` | 五维评级口径与常见问题清单 |
| 08 | `references/08-隐私与合规底线.md` | 什么数据不能碰，怎么拒绝越界要求 |

按需读一到两份，别一次全读。

---

## 三、工具层：八个脚本

全部纯标准库、零依赖、可离线。`--help` 看参数。

| 脚本 | 干什么 | 典型命令 |
|---|---|---|
| `profile_table.py` | 表格体检，出质量账与五维评级 | `python profile_table.py 订单.csv --by 渠道 --key 订单号` |
| `period_compare.py` | 两期对比 + 量价结构三因子分解 | `python period_compare.py 订单.csv --date 支付日期 --value 金额 --qty 件数 --period 2026-05:2026-06 --by 渠道` |
| `funnel_steps.py` | 漏斗单步转化与短板定位，可带基期 | `python funnel_steps.py 访问=10000,加购=3200,下单=1500,支付=980 --aov 120` |
| `cohort_retention.py` | 同期群留存矩阵，可附金额留存 | `python cohort_retention.py 事件.csv --user 用户ID --date 日期 --period month` |
| `segment_abc.py` | ABC 集中度与 RFM 分群 | `python segment_abc.py 订单.csv --key 客户ID --value 金额 --rfm --date 支付日期` |
| `ab_test.py` | 两比例 / 两均值检验，出区间与结论措辞 | `python ab_test.py --control 512/10000 --treat 583/10000` |
| `doc_export.py` | Markdown 导出 docx / html | `python doc_export.py 报告.md --to docx,html` |
| `czl_core.py` | 共享核心（读取、统计、分布、日期） | 不单独运行 |

**脚本的退出码**：0 成功；1 保留未用；2 参数或数据有问题（会在 stderr 给中文提示，不抛堆栈）。

---

## 四、样例数据（带手算真值）

`samples/` 四份小数据，用来验证脚本与教学。真值见 `samples/README.md`。

| 文件 | 行数 | 真值 |
|---|---|---|
| `orders_demo.csv` | 680 | 5 月 40,000 → 6 月 36,000，-10%；线上 -12,000（量），门店 +8,000（价） |
| `events_demo.csv` | 1568 | 访问 1000 → 加购 320 → 下单 150 → 支付 98 |
| `cohort_demo.csv` | 110 | 2026-07 群：60% / 40%；2026-08 群：50% |
| `ab_demo.csv` | 2000 | 对照 51/1000=5.10%，实验 78/1000=7.80% |

---

## 五、使用纪律

1. **口径先行**：没有口径账，不跑任何计算。用户不肯给口径，就按默认口径算并在报告首行标注。
2. **先体检再分析**：评级 C 以下，结论最高只能给 B；D 级不出业务结论。
3. **一次只回答一个问题**：多个目标拆成多次分析。
4. **结论必须带级别**（A/B/C/D）和"什么会推翻它"。
5. **数字可复算**：报告里写明用了哪个脚本、什么参数。
6. **不确定就写不确定**：样本不够、基线缺失、口径冲突，一律明写，不用模糊话掩盖。
7. **不碰个人身份信息**：只处理聚合或脱敏数据，遇到明细要求直接拒绝并给替代方案。
8. **不做预测**：销量、流量、股价预测一律不接。
9. **交付落盘**：Markdown 存档，需要 Word/网页用 `doc_export.py`。

---

*© 2026 虫志龙 · 版权所有，保留一切权利 ｜ 授权范围见包根目录 `LICENSE`*
