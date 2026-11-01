# 标胜 · 政府数字化售前中标全流程顾问

> 一个能判断"这标该不该投"、并在投的过程中把废标风险清干净的售前顾问。
> 开发者：虫志龙（47190078@qq.com）｜版本 1.0.0

---

## 这个专家解决什么问题

政府数字化项目的失败，很少败在"方案写得不好看"。真实的失分点通常是这几处：

- 资格差一条，方案再漂亮也进不了评分；
- 招标文件里一句"未按要求密封恕不接收"，交标当天才发现；
- 评分表里数据治理占 10 分，方案却把 20 页花在三维可视化上；
- 报价压到成本线以下，中了标也交付不了；
- 答辩 15 分钟讲不完，评委记住的是"没讲清楚"。

标胜把这五件事拆成七道关口，逐关过关，关关有产出物。

## 七道关口

| 关口 | 干什么 | 产出 |
|---|---|---|
| 一 机会雷达 | 判断真假、值不值、打不打得动 | 一页纸机会评估（含打分与短板） |
| 二 需求共创 | 在招标文件发出前，把建设内容与验收口径说清 | 痛点—场景—建设内容清单 + 边界声明 |
| 三 方案成形 | 按评分表搭结构，用场景串架构，写差异化 | 技术方案 + 架构说明 + 量化价值表 |
| 四 标书体检 | 逐条清废标风险，做条款响应表 | 分级风险报告 + 响应表 + 材料清单 |
| 五 报价与商务 | 算成本底线，看价格分曲线 | 报价测算表 + 商务风险提示 |
| 六 答辩演练 | 15 分钟脚本 + 评委质询库 | 答辩手册 |
| 七 中标交接 | 把承诺变成台账 | 承诺台账 + 交接清单 + 复盘 |

关口四是一道**硬闸门**：有废标项没闭环，不许进入排版装订。这条规则比任何写作技巧都值钱。

## 四个可执行的技能

不是纯提示词，每个技能都带脚本，能算的算，不靠模型估。

| 技能 | 命令 | 作用 |
|---|---|---|
| `gov-opportunity-radar` | `radar.py score` | 七维加权打分，资格一票否决，输出档位与三条短板 |
| `tender-clause-audit` | `tender_audit.py scan` | 按 19 条规则扫招标文件，标行号、分级、给动作 |
| `proposal-architect` | `proposal_plan.py plan` | 按评分分值分配章节与页数，标每章必须出现的要素 |
| `compliance-matrix` | `matrix.py all` | 输出等保（按级别）/ 密评 / 信创三张矩阵表 |

另有 `tools/pack_check.py`（专家包自检，专治"导入后头像变文字"）和 `tools/avatar_norm.py`（零依赖 PNG 头像裁切）。

## 目录结构

```
czl-gov-presales-pro/
├── .codebuddy-plugin/plugin.json     专家元数据
├── agents/czl-gov-presales-pro.md    主提示词（七关工作流）
├── avatars/czl-gov-presales-pro.png  原创头像 512×512
├── skills/
│   ├── gov-opportunity-radar/        机会打分
│   ├── tender-clause-audit/          标书体检（含规则库）
│   ├── proposal-architect/           方案骨架
│   └── compliance-matrix/            合规矩阵（含目录数据）
├── tools/
│   ├── pack_check.py                 发布前自检
│   ├── avatar_norm.py                头像规范化
│   └── selftest.py                   11 项功能自检
├── tests/fixtures/                   自检用例数据
├── docs/                             规格、说明、文案、测试报告、风险清单、开发记录
├── README.md  CHANGELOG.md  LICENSE  NOTICE.md
```

## 安装

方式一（推荐）：WorkBuddy 专家中心 → 导入专家包 → 选择 `czl-gov-presales-pro.zip`。

方式二（手动）：把目录放到

```
~/.workbuddy/plugins/marketplaces/my-experts/plugins/czl-gov-presales-pro/
```

然后注册：

```bash
python3 <expert-manager>/scripts/register_expert.py <专家目录>
```

## 用起来

直接在对话框里说人话就行：

- 「手上有个区里的项目，860 万，帮我看看值不值得投」
- 「这份招标文件帮我过一遍废标风险」
- 「评分表在这，帮我搭方案框架」
- 「等保三级和信创怎么落，给我出表」

也可以直接跑脚本，输出可粘进标书或汇报材料。

## 发布前自检

```bash
python tools/pack_check.py .              # 结构、引用、头像
python tools/pack_check.py . --zip ../dist/czl-gov-presales-pro.zip
python tools/selftest.py                  # 11 项功能用例
```

`pack_check.py` 会在导入前抓出"头像路径写了但文件不在包里""头像不是正方形""zip 内路径用了反斜杠"这类问题——它们正是导入后头像退化成文字的原因。

## 边界

- 不承诺中标，不输出"中标概率"。
- 不参与围标、串标、陪标，不伪造案例与资质。
- 合规矩阵是工作提纲，不替代测评机构结论；标准条文以 GB/T 22239 现行版本原文为准。
- 政策与平台规则会变，涉及具体项目时以最新文件为准。

## 许可

专有软件，版权归虫志龙所有。详见 `LICENSE` 与 `NOTICE.md`。
