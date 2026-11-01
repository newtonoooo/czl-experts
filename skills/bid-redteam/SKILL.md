---
name: bid-redteam
description: Review a finished draft from two seats at once - the evaluator scoring it against the tender's scoring table, and the rival trying to beat it. Computes the self-scored total and rate, compares it with three rival archetypes, ranks the biggest three losses, lists recoverable points, and checks the hand-over checklist for unsigned, unsealed or missing items. Use when the user asks for a final review, a mock evaluation, or whether the bid could be rejected.
description_zh: 交标关。按评分表自评并对三类对手做假设，排出丢分最多三项与可捞分项，同时核对交标清单。
---

# 交标关 · 红队体检

## 两只眼睛

同一份稿子，用两个身份各看一遍：

- **评委的眼睛**：按评分表逐项给分。不是"我们写得挺好"，而是"这一项能拿几分、为什么不是满分"。
- **对手的眼睛**：假设三类对手各会怎么打——低价型（压价抢分）、关系型（靠既有合作与案例分）、技术型（靠架构与指标）。每类写一句他们的攻击点，再写一句我们的回应。

一只眼睛看会自我感觉良好，两只眼睛看才会发现真问题。

## 输入

```json
{
  "items": [{"item": "技术方案", "score": 30, "self": 24,
             "rivals": {"低价型": 26, "关系型": 25, "技术型": 28}}],
  "checks": [{"item": "签字盖章", "done": false}]
}
```

`score` 是满分，`self` 是自评，`rivals` 是各类对手在同一项上的预估分（可只填有把握的项）。

## 命令

```bash
python scripts/redteam_score.py samples/review.json --md 红队记录.md
```

输出：自评总分与得分率、对手总分与分差、丢分最多三项、可捞分清单、交标核查状态。

## 判据

| 自评得分率 | 含义 | 动作 |
|---|---|---|
| ≥85% | 领先 | 别丢低级分：格式、盖章、响应偏离表 |
| 70–85% | 胶着 | 在一到两个高分项上做可验证的增量 |
| <70% | 落后 | 先确认是否值得投；若投，换打法或找联合体 |

分差大于 5 分时，不要靠润色追分，要靠补证据或改配置。

## 交标核查（六项，缺一不可）

资格文件齐全｜签字盖章｜份数（正本/副本）｜密封与骑缝章｜电子文件命名与格式｜送达或上传预留时间。

这一项不是形式主义。每年都有技术分第一、因未盖章被判无效的标。

## 输出

红队记录（内部用）+ 一份"改这三处"的清单，按可得分数排序，每条写清改什么、谁改、什么时候改完。

## 异常处理

- **自评全部接近满分**：多半是自评太松。换一个没参与写作的人复评，或按"评委只给 80%"重打一遍。
- **对手信息完全空白**：至少按三类假设填一版，哪怕是估的；空白比估错更危险。
- **发现否决项风险**：立刻停下手上的润色工作，先解决否决项。技术分再高也救不回来。
- **时间只剩一天**：只做两件事——过否决项清单、补可捞分最多的那一项。

## 与其他技能的关系

红队用的是 `rfp-decode` 的同一张矩阵、`evidence-ledger` 的同一本账。三处对不上，说明中间有人私自改了数据，先对齐再评审。
