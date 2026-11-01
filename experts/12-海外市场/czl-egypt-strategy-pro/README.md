# 埃及战略顾问·旗舰版

> 七道闸门做埃及落地：环境体检、赛道筛选、选址打分、路径比选、成本建模、风险台账，每步都出可交付文件。

- 包名：`czl-egypt-strategy-pro`
- 版本：1.0.0
- 开发者：虫志龙 · 47190078@qq.com
- 类型：Agent 型单专家
- 依赖：无（Python 标准库）

---

## 这是什么

一个把"要不要去埃及、怎么去、去了怎么活"拆成七道顺序闸门的决策工作台。

每道闸门都必须给出 **PASS / CONDITIONAL / STOP** 的判定，并留下一份可以拿去开会的文件。上一道没有结论，不会开下一道。

它不做国情百科，也不给"加强沟通""关注风险"这类无法执行的话。

## 七道闸门

| 闸门 | 名称 | 产出 |
|---|---|---|
| G0 | 案头立档 | `00-case-file.md` |
| G1 | 环境体检（宏观与汇率） | `01-macro-fx-brief.md` |
| G2 | 赛道筛选 | `02-sector-screen.md` |
| G3 | 落点选址 | `03-site-scorecard.md` |
| G4 | 进入路径 | `04-entry-route.md` |
| G5 | 单位经济与合规 | `05-unit-economics.md` + `cost-model.json` |
| G6 | 落地排期与风险台账 | `06-mobilization-plan.md` + `07-risk-ledger.md` |

## 目录结构

```
czl-egypt-strategy-pro/
├── .codebuddy-plugin/plugin.json      # 专家清单
├── agents/egypt-strategy-pro.md       # 主 Agent 提示词（七道闸门定义）
├── avatars/expert.png                 # 原创头像 512x512
├── skills/egypt-landing-desk/
│   ├── SKILL.md                       # 操作台索引
│   └── references/                    # 12 张原创参考卡
├── tools/                             # 6 个标准库脚本 + 2 个头像工具
├── examples/                          # 工具输入样例
├── variants/                          # manifest 变体（头像切换用）
├── docs/                              # 规格、工作流、说明、测试、风险
├── README.md  CHANGELOG.md  LICENSE  NOTICE.md
```

## 快速开始

```bash
# 1. 自检（应输出 11/11 通过）
python tools/selftest.py

# 2. 跑一个汇率压力测试
python tools/fx_stress.py examples/g1-fx-stress.json

# 3. 如果导入后图标变成汉字
python tools/apply_inline_avatar.py --apply
```

然后在 WorkBuddy 里选择「埃及战略顾问·旗舰版」，用这句话开场：

> 我们计划在埃及建一条面向本地和欧洲市场的中型产线，预算两千万美元以内。请从案头立档开始，一步步带我到能签字的落地方案。

## 参考卡

`skills/egypt-landing-desk/references/`

| 卡 | 内容 |
|---|---|
| 00-method | 五问定框、证据分级 E1–E4、七个常见谬误 |
| 01-macro-fx | 10 个观察指标、口径陷阱、资金出入境三条路径 |
| 02-legal-investment | 投资法三套制度、公司形式、土地、许可链条 |
| 03-sites-zones | 六类落点、打分权重、SCZone 提示 |
| 04-entry-routes | 六条路径、治理条款清单、退出成本 |
| 05-cost-stack | 成本栈、税与社保口径、能源与融资 |
| 06-customs-logistics | ACID、清关流程、原产地与本地含量 |
| 07-sector-screens | 六个赛道的五维基线分 |
| 08-risk-ledger | 台账字段、分级矩阵、止损线 |
| 09-vision-programs | 国家计划与政策窗口 |
| 10-data-ledger | 指标口径台账与复核节奏 |
| 11-deliverable-templates | 七份文件的字段骨架 |

## 工具

| 脚本 | 作用 |
|---|---|
| `fx_stress.py` | 四档贬值情景下的毛利、现金缺口、需涨价幅度 |
| `site_score.py` | 加权打分 + 权重敏感性翻转检测 |
| `entry_route.py` | 硬约束过滤 + 四维排序 + 退出成本 |
| `landed_cost.py` | FOB → 到厂单价，含清关/滞港/在途资金 |
| `labor_cost.py` | 全口径人工与单位产品人工 |
| `selftest.py` | 11 条断言回归 |
| `avatar_prep.py` | 裁剪、降采样、data URI 导出 |
| `apply_inline_avatar.py` | 头像在相对路径与内联之间切换 |

## 已知限制

- 宏观数据有滞后，所有数字必须带时点；本包不内置数据库，实时数据需自行核。
- 不提供法律、税务、审计的最终意见。
- 不预测汇率点位，不承诺审批结果。
- 导入后若图标显示为汉字，见 `docs/08-图标显示问题诊断.md`。

## 许可

专有软件，版权归虫志龙所有。使用条款见 `LICENSE`，第三方情况见 `NOTICE.md`。

## 免责

本专家输出为商业决策参考，不构成投资、法律、税务或审计意见。埃及市场数据变化频繁，正式决策前请结合实地调研与当地持牌专业机构意见，并对关键数据交叉验证。
