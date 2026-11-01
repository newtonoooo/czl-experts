---
name: live-room-playbook
description: "The operating playbook for one livestream session, split into six gated workflows: session brief, assortment and rundown, script cards, host coaching, traffic gates, and session review. Load a single workflow file when one stage is needed, or run the full chain before a launch session. Each workflow defines inputs, steps, decision rules, output format, failure handling and hand-off to the next stage."
---

# 直播间操盘手册（六段制）

六段，每段一个文件，每段都有自己的输入、判断和产出。可以整条走完，也可以单点进入。

```
W0 场次立项 → W1 货盘排品 → W2 话术脚本 → W3 主播带教 → W4 流量闸门 → 播 → W5 场次复盘
                                    ↑__________________________|
                                    （复盘结论回灌下一场 W0/W1）
```

| 段 | 文件 | 一句话职责 | 结束标志 |
|---|---|---|---|
| W0 | `references/workflows/W0-session-brief.md` | 把"想播一场"变成任务书 | 目标、验收口径、资源、风险四项齐 |
| W1 | `references/workflows/W1-assortment-rundown.md` | 给每一波流量准备好接住它的货 | 分钟级 Rundown 表可执行 |
| W2 | `references/workflows/W2-script-cards.md` | 让主播有能念出来的话 | 每个主推品有一张脚本卡 |
| W3 | `references/workflows/W3-host-coaching.md` | 把脚本变成主播的肌肉记忆 | 彩排三遍过，评分表有数 |
| W4 | `references/workflows/W4-traffic-gates.md` | 把钱花在能算清的闸门里 | 保本线、预算、止损三项定死 |
| W5 | `references/workflows/W5-session-review.md` | 把这一场的错误变成下一场的动作 | 次日动作单三件，责任到人 |

配套：

- `references/rundown-blueprint.md` — 4 小时/2 小时两套骨架，直接套
- `references/compliance-wordbank.md` — 违禁表述与替换说法
- `references/category-playbooks.md` — 七大类的差异点
- `templates/` — 六张可直接填的表

---

## 通用执行规则

1. **一段做完再进下一段。** 输入不全就先补，不要"边排品边猜话术"。
2. **每段产出都是一张表。** 拿不出表的阶段等于没做完。
3. **每段结束时用一句话交接：** "W1 完成：4 小时 12 个货位，主力款在第 2、5、8 位，峰值时段留给 X。" 下一段从这句话开始。
4. **数字一律走 `live-room-metrics` 脚本**，手算的结论不可信。
5. **遇到合规问题立刻停。** 话术里出现绝对化用语、功效承诺、假比价，先改再往下走。

---

## 单点进入路由

| 用户说的 | 直接进哪段 |
|---|---|
| "下周要开一场大场，怎么准备" | W0 |
| "这些货怎么排""什么时候上什么" | W1 |
| "主播没词""给我写话术" | W2 |
| "主播状态不稳""怎么带新人" | W3 |
| "要不要投""投多少""投了不消耗" | W4 |
| "昨天数据很差""帮我复盘" | W5 |
| "从零开始做直播" | W0 → W5 全链 |
