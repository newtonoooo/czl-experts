# 阿麦 · 专业级直播间操盘教练

**把一场直播拆成排品表、脚本卡、带教单、投放排期和复盘表，分钟级节奏配保本测算，照着就能播。**

- 开发者：虫志龙（47190078@qq.com）
- 专家类型：Agent 型（单专家）
- 标识：`czl-livestream-ops-coach`
- 版本：1.0.0
- 适配平台：抖音、快手、视频号、淘宝直播、小红书

---

## 这个专家解决什么问题

直播做不好，通常不是"不会讲"，是四件事里至少一件没排对：**货的顺序错了、话不能念、人撑不住、钱花得没算过。**
市面上的建议大多停在"要加强互动""要提升停留"，这类话听完还是不知道明天做什么。

阿麦的做法相反：**每一条建议都落到"谁、在第几分钟、做什么、验收标准是什么"**，并且所有涉及钱的判断都先算保本线。

## 六段工作流

| 段 | 名称 | 产出 |
|---|---|---|
| W0 | 场次立项 | 任务书：目标、验收口径、资源瓶颈、风险预案 |
| W1 | 货盘排品 | 分钟级 Rundown、价格带梯度、库存释放表 |
| W2 | 话术脚本 | 单品六段脚本卡（可直接念）、整场三段结构、互动指令表 |
| W3 | 主播带教 | 五项评分、逐句纠偏单、三轮彩排、30 天路径 |
| W4 | 流量闸门 | 保本测算、预算上限、放量/止损条件、投放节奏表 |
| W5 | 场次复盘 | 五层漏斗诊断、四类归因、真实盈亏、次日动作单 |

可以整条走完（新品首播、大场），也可以单点进入（"帮我写话术""帮我复盘"）。

## 三条判断铁律

1. **先看流量结构，再看成交数字。** 同样 5 万 GMV，一个是自然流量撑的，一个是广告费烧的，结论完全相反。
2. **建议必须落到分钟。** "加强互动"不是建议，"第 12 分钟让中控发一次关注抽奖、主播念前三个新进房的名字"才是。
3. **不算保本线的投放建议是劝你亏钱。** 单件净毛利、保本 ROI、单场保本 GMV，这三个数不出来，不给投放方案。

## 内置技能

| 技能 | 职责 | 关键内容 |
|---|---|---|
| `live-room-metrics` | 算数与诊断 | 场次指标、保本 ROI、目标反推、漏斗诊断；纯标准库脚本，22 项公式自检 |
| `live-room-playbook` | 流程与模板 | W0-W5 六段工作流规格、节奏骨架、合规词表、七大类目差异、六张可填表 |

算数一律走脚本，不靠心算；脚本输出的每个数字都能被纸笔复核（推导见 `skills/live-room-metrics/references/metric-definitions.md`）。

## 使用示例

- 「我们是刚开播的新号，客单价 99 元，团队三个人，帮我排一场 4 小时的直播：先出排品和节奏，再给能直接念的话术。」
- 「这是昨天一场直播的数据（曝光 18 万、进房 1.26 万、停留 41 秒、点击 880、付款 31 单、成交 3069 元、投流 1800 元），帮我查漏斗漏在哪一层，再给我明天的动作单。」
- 「主播一讲产品就冷场，停留掉得很厉害，帮我做一份带教计划加彩排脚本。」
- 「这款卖 129、成本 41、退货率 22%，投流投产比做到多少才不亏？」
- 「下周要做一场清库存的场，只有 5 个品、库存都很薄，怎么排？」

## 开场会问你什么

平台与账号阶段、类目与主推品、价格带、毛利与履约成本、团队编制、历史场次数据、本场目标。
**缺项不会瞎猜**：缺毛利就不出投放方案，缺数据就把这场定义成基线场，缺团队就默认两人编制——所有假设都会写在方案开头。

## 目录结构

```
czl-livestream-ops-coach/
├── .codebuddy-plugin/plugin.json      元数据与展示字段
├── agents/czl-livestream-ops-coach.md 主提示词（人设、铁律、路由、规范、红线）
├── avatars/expert.png                  原创头像 512×512
├── skills/
│   ├── live-room-metrics/              算数与诊断
│   │   ├── SKILL.md
│   │   ├── references/metric-definitions.md
│   │   └── scripts/live_metrics.py
│   └── live-room-playbook/             流程与模板
│       ├── SKILL.md
│       ├── references/workflows/W0-W5*.md
│       ├── references/rundown-blueprint.md
│       ├── references/compliance-wordbank.md
│       ├── references/category-playbooks.md
│       └── templates/*.md（6 张可填表）
├── docs/                               规格、开发记录、测试报告、风险清单、上架文案
├── CHANGELOG.md
├── LICENSE
├── THIRD-PARTY-NOTICES.md
└── README.md
```

## 安装

把整个目录放到专家目录：

```
<WORKBUDDY_CONFIG_DIR>/plugins/marketplaces/my-experts/plugins/czl-livestream-ops-coach/
```

（Windows 默认 `C:\Users\<用户名>\.workbuddy\plugins\marketplaces\my-experts\plugins\`）

然后注册，注册后在专家中心可见：

```bash
python scripts/register_expert.py <expert-dir>
```

## 跑一次算数脚本

```bash
python skills/live-room-metrics/scripts/live_metrics.py selftest
python skills/live-room-metrics/scripts/live_metrics.py breakeven --price 129 --cost 41 --fulfillment 7 --return-rate 0.22
```

Python 3.8+，只用标准库，不联网、不写文件。

## 边界与免责

- **指标参考线是经验区间，不是任何平台的官方考核标准。** 平台后台字段定义以各平台当期文档为准。
- **不提供法律意见。** 合规词表用于降低文案风险，具体执法判断请咨询平台客服或专业律师。
- **不承诺 GMV。** 任何承诺具体 GMV 的方案都不值得付费。
- 不抓取平台数据，所有输入由使用者提供。

## 许可

专有软件，版权归虫志龙所有。使用与分发条件见 `LICENSE`。
本包不包含任何第三方代码、提示词或素材，见 `THIRD-PARTY-NOTICES.md`。
