---
name: evidence-ledger
description: Keep an evidence ledger for every claim in a proposal draft. Defines four evidence levels, audits a draft to find claims without a tag, lists the E4 assumptions that must carry hedged wording, and counts empty adjectives. Use when the user asks whether a statement is defensible, when a reviewer will grill the numbers, or before a draft goes to red-team review.
description_zh: 证据账本。按 E1–E4 四级标注每条主张，扫出无标注的主张、需软化表述的假设与空词。
---

# 证据账本

## 四级证据

| 级别 | 含义 | 例子 | 可用性 |
|---|---|---|---|
| E1 | 客户侧可核实数据 | 客户提供的现网拓扑、报表、合同条款 | 最硬，可直接下结论 |
| E2 | 同类项目实证 | 有验收单、可提供联系人的案例 | 硬，需注意客户保密 |
| E3 | 方法可复现 | 标准、流程、工具，任何人照做能复现 | 中，能证明"做得到"不能证明"做得好" |
| E4 | 假设 | 尚未验证的判断 | 弱，必须写"预计/计划/待验证" |

**降级规则**：E1/E2 拿不出原始材料，自动降为 E4。这不是保守，是防评委追问。

## 怎么标

在正文句子末尾加 `[E1]`～`[E4]`。一句话只标一个，取最低的那级。

```markdown
PACS 影像数据年增长 40TB [E1]
同城某三甲医院 2025 年采用同一流程，实测停机 3.5 小时 [E2]
回滚脚本预置 6 类触发条件，任一命中 20 分钟内回退 [E3]
割接窗口单次不超过 4 小时 [E4]
```

## 命令

```bash
python scripts/claim_audit.py 技术方案.md --strict --md 主张体检.md
```

脚本按"含数字或含断言动词"识别主张句，统计已标/未标比例、E4 数量、空词次数，列出未标主张的行号。`--strict` 时未标比例超过 40% 返回退出码 1。

`samples/draft.md` 是一份混着硬证据与空话的稿子，跑一遍能看清脚本怎么抓。

## 判据

- 未标比例 ≤40%：可进红队。
- E4 数量不超过主张总数的 25%：超过说明方案主要靠推测。
- 空词为 0：出现一个删一个。

## 输出

体检表 + 待补清单（哪条主张缺什么材料、找谁要）。待补清单比得分表更能推动事情——它指出的是"现在去要还能要得到"的东西。

## 异常处理

- **客户不让写具体数据**：改写成区间或相对值（"停机从半天压到 4 小时以内"），仍标 E1/E2，并在账本备注"原始数据客户保密，可现场查验"。
- **案例不能点名**：写"同城某三甲医院"，账本里保留真实名称供内部核对，对外版本删除。
- **满篇 E4**：不是标注问题，是方案没有事实基础。回到 `bid-gatekeeper` 重新判断要不要投。
- **同一句里既有事实又有承诺**：拆成两句，各标各的。

## 与其他技能的关系

账本服务于 `narrative-build`（摘要里的证据段）与 `bid-redteam`（评委追问时的防线）。主题卡里的"证据"字段应与账本条目一一对应，对不上就是有一处写虚了。
