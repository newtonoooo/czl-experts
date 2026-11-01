---
name: czl-tomato-ops
description: "Operating knowledge base for the CZL Tomato Bestseller Operator (番茄爆款小说操盘手). Organised as six lifecycle gates instead of capability buckets: G1 topic screening, G2 opening pressure, G3 retention diagnosis, G4 surge handling, G5 serial endurance, G6 monetization. Contains 42 playbook modules, each with a decision standard, failure symptoms, rescue actions and an exit condition, plus 16 dependency-free Python CLI tools that turn the standards into numbers (topic scoring, first-200-character pressure scan, chapter-end hook audit, per-chapter information gain, retention drop localization, tension balance, subplot payoff rate, power-consistency jump detection, revenue structure, adaptation scoring, contract field checklist, Markdown export). Use when judging whether a serial should be started, rescued, cut short or finished."
version: 1.0.0
---

# 番茄爆款小说操盘手 · 运营知识库（czl-tomato-ops）

本知识库是「番茄爆款小说操盘手」的判据来源。它不提供"怎么写好"，只提供**该不该继续、该救哪里、该在哪停**。

**42 个模块 + 16 个工具**，按六道闸门组织。每道闸门的模块共享同一套四件套结构：**判断标准 / 失守症状 / 抢救动作 / 退出条件**。

---

## 一、六道闸门与模块索引

### G1 · 选题闸（这本书值不值得开）

| 编号 | 模块 | 用途 |
|---|---|---|
| G1-01 | 赛道容量估算法 | 判断题材盘子够不够大 |
| G1-02 | 设定差异度自检 | 把"我觉得新"拆成可对照的差异层级 |
| G1-03 | 目标读者画像还原 | 还原成具体阅读场景，不是人口标签 |
| G1-04 | 同类作品近 90 天表现读法 | 判断赛道是热是凉 |
| G1-05 | 换核换壳决策表 | 四象限决定换哪个、留哪个 |
| G1-06 | 弃题清单与止损线 | 五条清单决定弃不弃 |
| G1-07 | 新赛道试水节奏 | 三阶段最小成本验证 |

工具：`gate1_topic_scan.py`、`gate1_rival_read.py`

### G2 · 开局闸（前三章留不留人）

| 编号 | 模块 | 用途 |
|---|---|---|
| G2-01 | 首屏 200 字压强测试 | 前 200 字的信息压强 |
| G2-02 | 第一章目标可见性检查 | 三问缺一即不可见 |
| G2-03 | 首次兑现时机表 | 承诺的最晚兑现章 |
| G2-04 | 章末钩子分级标准 | 五级判定与验收线 |
| G2-05 | 前三章重写流程 | 先结构后句子 |
| G2-06 | 开局常见死法 12 例 | 逐条自查 |
| G2-07 | 开局自检表 | 8 项验收清单 |

工具：`gate2_pressure.py`、`gate2_goal_visibility.py`

### G3 · 留存闸（第 10–30 章能不能养成习惯）

| 编号 | 模块 | 用途 |
|---|---|---|
| G3-01 | 章末钩子密度体检 | 达标率与三连低 |
| G3-02 | 单章信息增量核算 | 五类增量，只给情绪不算 |
| G3-03 | 三章一起伏排布法 | 三章单元结构 |
| G3-04 | 对话可读性规则 | 单句长度与潜台词 |
| G3-05 | 补钩子包操作法 | 最低成本急救 |
| G3-06 | 情绪价值三条供给线 | 爽 / 痛 / 盼 |
| G3-07 | 追读习惯养成窗口 | 三段窗口期 |
| G3-08 | 掉量解剖：从数据到章号 | 找拐点，往前看 |

工具：`gate3_hook_audit.py`、`gate3_info_gain.py`、`gate3_drop_autopsy.py`

### G4 · 爆发闸（推荐流量接不接得住）

| 编号 | 模块 | 用途 |
|---|---|---|
| G4-01 | 推荐窗口承接准备 | 窗口前四项就位 |
| G4-02 | 加更节奏与质量平衡 | 找自己的加更临界点 |
| G4-03 | 前三章高光前移重排 | 窗口期唯一允许的结构手术 |
| G4-04 | 书评区情绪读法 | 情绪极性、争论对象 |
| G4-05 | 流量异常归因表 | 分清流量侧与内容侧 |
| G4-06 | 窗口期内容排产 | 单元先定，不换线 |

工具：`gate4_surge_prep.py`、`gate4_sentiment.py`

### G5 · 续航闸（长篇会不会崩）

| 编号 | 模块 | 用途 |
|---|---|---|
| G5-01 | 主线张力余额盘查 | 未兑现承诺的加权余额 |
| G5-02 | 支线回收率统计 | 回收 + 明确作废 ≥ 70% |
| G5-03 | 设定与战力自洽校验 | 三张表校验 |
| G5-04 | 中段高潮分布设计 | 15 章内必有大事件 |
| G5-05 | 长篇大纲三层拆法 | 不变层 / 可调层 / 消耗层 |
| G5-06 | 断更风险评估 | 四项周盘 |
| G5-07 | 完结止损判定 | 三种处置：压缩 / 加速 / 立即完结 |

工具：`gate5_tension.py`、`gate5_thread_close.py`、`gate5_consistency.py`

### G6 · 变现闸（怎么变成钱与资产）

| 编号 | 模块 | 用途 |
|---|---|---|
| G6-01 | 收益结构拆解 | 分项看趋势，不看合计 |
| G6-02 | 有效阅读与听读收益口径 | 三层转化核对 |
| G6-03 | 平台奖励机制适用条件 | 条件核对，不写死金额 |
| G6-04 | 改编适配度评分法 | 五维 25 分制 |
| G6-05 | 可拍场景与名场面埋点 | 四条标准 + 密度要求 |
| G6-06 | 签约版权字段检查表 | 六字段逐项确认 |
| G6-07 | IP 长期价值评估 | 四项长期指标 |

工具：`gate6_revenue.py`、`gate6_adapt_score.py`、`gate6_contract_check.py`

### 通用

`draft_exporter.py` —— Markdown 导出 HTML / TXT。

---

## 二、使用纪律

1. **一次只读 1–2 个模块**，不要全量加载。判断哪道闸，就读哪一组。
2. **脚本用 `--help` 先看参数**，全部为纯标准库实现，零第三方依赖，Python 3.8+ 可跑。
3. **脚本输出是初筛，不是结论**。`gate2_pressure.py`、`gate3_hook_audit.py`、`gate4_sentiment.py` 用关键词规则，必须人工复核后再下判断。
4. **不许跳闸**：开局没过不谈留存，留存没过不谈变现。

---

## 三、数据与合规纪律

- 本知识库**不写死任何金额、分成比例、奖励档位**。涉及这些的回答必须回到作者后台核对当月公告，并注明数据日期。
- 无法核实的写「**待官方公告确认**」，不填看起来合理的数字。
- 所有阈值（如 70% 回收率、15 章高潮间隔、50% 钩子达标率）均为**经验参考**，不是平台官方标准，输出时必须注明。
- 涉及收益、签约、版权的判断**不构成法律意见**，重大事项提示咨询专业人士。

---

## 四、模块标准结构

每份模块固定六段，便于横向对照：

```
一、这个模块解决什么
二、判断标准（表格为主）
三、操作步骤（编号，可当天执行）
四、输出模板（可直接填）
五、三个常见误判
六、关联模块
```

---

## 五、版本

当前 **v1.0.0**（2026-10-27 首次发布）。变更历史见 `CHANGELOG.md`。

---

*本知识库由虫志龙独立开发，内容为原创表述。平台规则类事实来自公开渠道，以官方公告为准。*
