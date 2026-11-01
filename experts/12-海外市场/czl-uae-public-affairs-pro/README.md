# 阿联酋公共事务权威顾问 · czl-uae-public-affairs-pro

> 由 **虫志龙** 独立开发 ｜ 联系：47190078@qq.com ｜ 版本 **1.0.0**
> 类型：Agent 型专家（单角色） ｜ 分类：行业顾问（12-IndustryConsultant）

---

## 这是什么

一个面向中国企业、投资机构与跨境贸易商的**阿联酋公共事务作业型专家**。它不做"阿联酋概况介绍"，而是把一件具体的事拆成：**谁在管 → 依据什么 → 走哪条路径 → 什么时间点 → 什么话不能说 → 失败会怎样 → 下一步找谁**。

核心差异：**七酋长国分列**（阿布扎比 / 迪拜 / 沙迦 / 阿治曼 / 乌姆盖万 / 哈伊马角 / 富查伊拉），以及**同国不同辖区分层**（本土 / 普通自由区 / 金融自由区 / 离岸）。

## 七条工作流

| 编号 | 工作流 | 什么时候用 |
|---|---|---|
| W0 | 受理与范围界定 | 任何新任务的第一跳，输出任务简报卡与缺口清单 |
| W1 | 政策与监管情报扫描 | "这事归谁管、要批吗、依据哪条" |
| W2 | 七酋长国分层评估 | 选址、区域总部、产能布局、成本比较 |
| W3 | 利益相关方与决策路径映射 | "找谁、按什么顺序推进、多久" |
| W4 | 沟通策略与红线校验 | 新闻稿、社媒、广告、代言、监管回函 |
| W5 | 风险量化与交付物装配 | 上会、投委会、存档；输出一页纸/决策备忘 |
| W6 | 危机快车道（0–72h） | 舆情、突查、事故、被点名 |

配套四道质量闸门（Q1 结构 / Q2 依据 / Q3 数字口径 / Q4 红线）与一张异常处理总表。

## 目录结构

```
czl-uae-public-affairs-pro/
├── .codebuddy-plugin/plugin.json        专家元数据（唯一标识、展示信息、头像引用）
├── agents/
│   └── czl-uae-public-affairs-pro.md     主提示词：角色、7 条工作流、闸门、异常处理
├── skills/czl-uae-pa-toolkit/            作业工具箱
│   ├── SKILL.md                          技能入口与索引
│   ├── references/                       7 份原创作业手册
│   │   ├── 01-emirate-profile-matrix.md
│   │   ├── 02-regulatory-domain-index.md
│   │   ├── 03-stakeholder-decision-path.md
│   │   ├── 04-communication-redlines.md
│   │   ├── 05-risk-scoring-model.md
│   │   ├── 06-deliverable-templates.md
│   │   └── 07-source-verification-protocol.md
│   ├── scripts/
│   │   ├── risk_score.py                 五维风险打分（纯标准库）
│   │   └── brief_check.py                任务简报完整性校验（纯标准库）
│   └── templates/                        4 份交付物模板
├── avatars/expert.png                    原创头像 512×512
├── docs/                                 产品规格、使用说明、测试报告、风险清单、开发记录
├── tools/                                打包与体检脚本
├── CHANGELOG.md
├── LICENSE
├── THIRD-PARTY-NOTICES.md
└── README.md
```

## 安装

1. 解压后确认目录结构为：`czl-uae-public-affairs-pro/.codebuddy-plugin/plugin.json`
   - **不要**出现 `czl-uae-public-affairs-pro/czl-uae-public-affairs-pro/` 的双层嵌套（这会导致选择专家后头像回退成文字）。
2. 将整个 `czl-uae-public-affairs-pro/` 放入专家目录：
   `~/.workbuddy-ai/plugins/marketplaces/my-experts/plugins/`
3. 重启客户端，在「专家 → 我的专家」中即可看到「阿联酋公共事务权威顾问」。

或直接使用 `dist/czl-uae-public-affairs-pro.zip` 通过客户端「导入专家」功能导入。

## 快速自检

```bash
# 结构体检
python tools/build_package.py check .

# 打包（自动体检 + 回读验证）
python tools/build_package.py build . ./dist

# 单独验证已有 zip 是否会导致头像丢失
python tools/build_package.py verify ./dist/czl-uae-public-affairs-pro.zip
```

## 三个推荐问法

1. 我要在阿联酋设立区域总部，请给我一份七酋长国选址的公共事务与合规对比方案
2. 阿联酋刚出台 XX 新政策，评估对我业务的影响，并告诉我该找哪个监管机构、怎么沟通
3. 阿联酋社交媒体上出现关于我公司的负面舆情，给我一份 24 小时应对方案和对外声明

## 边界与声明

- 本专家输出为**公共事务咨询建议**，不构成法律意见；具体交易与申报须由阿联酋持牌律师、审计师复核。
- 政策以官方最新公告为准；专家会在每份输出末尾给出「信息截止日 + 待复核项」。
- 不提供规避监管的方案，不评价阿联酋内政与皇室事务，不提供具体官员个人联系方式。

## 许可

本产品为商业授权产品，版权归 **虫志龙** 所有。授权范围见 `LICENSE`。第三方组件与公开规范的适用情况见 `THIRD-PARTY-NOTICES.md`。
