# czl-experts

WorkBuddy 专家包与技能库。**61 个专家包**，覆盖 14 个业务领域；**176 个独立技能**，可脱离专家单独使用。以 MIT 开源。

每个专家解决一类具体的活儿——不是"什么都能聊"的通用助手，而是带着固定流程、明确产出和验收标准的角色。

---

## 从这里开始

| 你想做什么 | 去哪 |
|---|---|
| 找一个能用的专家 | [专家目录 CATALOG.md](CATALOG.md) — 按分类浏览，每个都写了它做什么、可以怎么问它 |
| 只想要某个能力 | [技能清单 SKILLS.md](SKILLS.md) — 176 个技能，按分类分组，带中文名 |
| 不会装 | [使用指南](docs/01-使用指南.md) — 装专家、装技能、组合使用、排错 |
| 想改或自己做一个 | [开发说明](docs/02-开发说明.md) — 包结构、命名铁律、技能设计、校验流程 |
| 想上传开放平台 | [合规报告](docs/03-合规报告.md) — 20 个包的字段待修项 |

## 30 秒上手

```bash
git clone https://github.com/newtonoooo/czl-experts.git
cd czl-experts

# 装一个专家（以"定盘"产品决策审校为例）
unzip dist/experts/01-产品设计/czl-product-decision-audit.zip \
      -d "$WORKBUDDY_CONFIG_DIR/plugins/marketplaces/my-experts/plugins/"

# 或者只装一个技能
cp -r skills/evidence-ledger ~/.workbuddy-ai/skills/
```

装完重启 WorkBuddy，在左侧「专家」里就能看到。

## 这个库里有什么

| 分类 | 数量 | 解决什么 |
|---|---|---|
| 产品设计 | 4 | 想清楚做什么、值不值得做、怎么讲给不同人听 |
| 工程开发 | 4 | 把想法变成能上线、能维护的代码与站点 |
| 数据分析 | 3 | 从一份表里问出可信结论，并把证据留痕 |
| 市场增长 | 1 | 拉新、起量、做内容 |
| 内容创作 | 8 | 长文、网文、公众号、论文，从选题到成稿 |
| 电商销售 | 5 | 选品、Listing、竞品、直播、利润 |
| 财务投资 | 8 | 看盘、选股、回测、结账、报税 |
| 职场人事 | 1 | 简历过筛与投递策略 |
| 法务合规 | 1 | 合同起草、条款审查、风险清单 |
| 生活咨询 | 2 | 择日、决策类的生活问题 |
| 商务投标 | 3 | 标书、方案、应答 |
| 海外市场 | 5 | 中东、东南亚市场的进入策略与本地化 |
| 学科家教 | 7 | 高中九科的讲解、陪练与学情诊断 |
| 教师教研 | 7 | 备课、命题、教案、课堂设计 |

完整的名字、职业、能力、技能挂载见 [CATALOG.md](CATALOG.md)。

## 目录结构

```
czl-experts/
├── CATALOG.md                 专家目录：按分类，带定位/场景/技能/下载入口
├── SKILLS.md                  技能清单：176 个，按分类分组
├── docs/                      使用指南、开发说明、合规报告
├── dist/                      成品包，下载即用
│   ├── experts/<分类>/<包标识>.zip
│   ├── skills/<分类>/<技能标识>.zip
│   └── MANIFEST.csv           体积与 SHA-256
├── experts/<分类>/<包标识>/    源码形态，可读可改
└── skills/<技能标识>/          拆解后的独立技能
```

**源码层给人看，成品层给机器装，索引层给人找。** 三层分开是为了让 diff 保持可读、让下载保持简单。

## 一个专家包长什么样

```
czl-product-decision-audit/
├── .codebuddy-plugin/plugin.json   身份与挂载声明
├── agents/czl-product-decision-audit.md   系统提示词
├── skills/                         7 个技能，每个一件具体的事
│   ├── decision-triage/            分诊：这是什么类型的决策
│   ├── evidence-ledger/            证据台账：逐条标注 A/B/C/D/X
│   └── ...
├── avatars/                        头像 512×512
├── docs/                           规格、使用说明、测试报告、风险清单、开发记录
├── CHANGELOG.md
└── LICENSE
```

## 许可

[MIT](LICENSE)。可自由使用、修改、商用、再分发，保留版权与许可声明即可。

部分包内附带的 `LICENSE` / `NOTICE` 是历史文件，与仓库级 MIT 冲突时以根目录的 MIT 为准。

## 已知说明

- `czl-site-launch-pro/tests/fixtures/leaky-app/` 内有一个**伪造的 Stripe 测试密钥**，用于验证密钥脱敏能力，非真实凭据。
- 重名技能（同一标识出现在多个包中）按体积取最完整版本收录一份，取舍明细见 [skills-conflicts.md](skills-conflicts.md)。
- 两处展示名重复：`czl-gov-presales-pro` 与 `czl-proposal-strategy-studio` 都叫「标胜」，见 [开发说明](docs/02-开发说明.md) 的技术债一节。

## 反馈

包的问题、命名冲突、技能取舍建议，欢迎提 Issue。
