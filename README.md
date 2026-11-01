# czl-experts

WorkBuddy 专家包与技能库，作者：虫志龙。

**51 个专家包**（49 个单角色专家 + 2 个多角色专家团），覆盖 13 个业务分类；**159 个独立技能**，已从专家包中拆解去重，可单独使用或发布。

- [专家包清单](EXPERTS.md) — 51 个包的花名、职业、类型、版本、技能数
- [技能清单](SKILLS.md) — 159 个技能的来源与分类
- [重名技能取舍说明](skills-conflicts.md) — 20 个重名技能的去重依据
- [技能清单 CSV](skills-manifest.csv) — 机器可读版本

---

## 目录结构

```
czl-experts/
├── experts/<分类>/<包标识>/     完整专家包，可直接安装到 WorkBuddy
│   ├── .codebuddy-plugin/plugin.json   身份与挂载声明
│   ├── agents/<包标识>.md              系统提示词
│   ├── skills/                         该专家挂载的技能
│   ├── avatars/                        头像 512×512
│   └── docs/                           开发记录、规格、测试报告、风险清单
└── skills/<技能标识>/           从专家包中拆解出的独立技能
    ├── SKILL.md                        技能主体（YAML frontmatter + 指令）
    ├── references/                     参考资料（按需）
    └── scripts/                        可执行脚本（按需）
```

## 分类一览

| 分类 | 包数 | 代表专家 |
|---|---|---|
| 产品设计 | 4 | 定盘（产品决策审校）、制图宗师（图表设计）、产品战略参谋 / 作战室 |
| 工程开发 | 4 | 陆工（全栈开发）、码上线（小程序交付）、桌匠（工作台架构） |
| 数据分析 | 3 | 数证台、三棱镜（分析师 / 专家团） |
| 市场增长 | 1 | 阿爆（抖音增长） |
| 内容创作 | 7 | 朱笔（公众号质检）、文衡（论文）、番茄 / 七猫爆款小说、爆款笔记车间 |
| 电商销售 | 5 | 净利操盘手、阿麦（直播）、拆敌（竞品拆解）、亚马逊 Listing、出海落地官 |
| 财务投资 | 8 | 盘锋（A股盘中）、账衡（结账）、刻度（股票研究）、专业回测台、财税全流程 |
| 职场人事 | 1 | 简锋（简历过筛） |
| 法务合规 | 1 | 契约守门人（合同审查） |
| 生活咨询 | 2 | 算卦台、司南 |
| 商务投标 | 3 | 中标方案专家、标胜（政府售前 / 方案策划） |
| 海外市场 | 5 | 埃及、沙特、新加坡、阿联酋（营销增长 / 公共事务） |
| 学科家教 | 7 | 高中九科辅导（数学陆九章、物理顾衡等） |

## 安装专家包

把 `experts/<分类>/<包标识>/` 整个目录复制到 WorkBuddy 的专家目录，再注册即可：

```bash
# 专家目录（由 WORKBUDDY_CONFIG_DIR 决定）
cp -r experts/01-产品设计/czl-product-decision-audit \
      "$WORKBUDDY_CONFIG_DIR/plugins/marketplaces/my-experts/plugins/"
```

复制后需在 WorkBuddy 的专家中心刷新，或重启客户端。

## 单独使用技能

每个 `skills/<技能标识>/` 都是自包含的，把整个目录复制到技能目录即可：

```bash
cp -r skills/evidence-ledger ~/.workbuddy-ai/skills/
```

技能的触发条件、输入输出、执行步骤都写在 `SKILL.md` 的正文里，frontmatter 的 `description` 决定何时被调用。

## 关于许可

每个专家包内自带 `LICENSE` 与 `NOTICE`，许可条款以包内文件为准。各包许可不完全相同，商用、二次分发、改名发布前请先阅读对应包的 `LICENSE`。

## 已知说明

- `czl-site-launch-pro/tests/fixtures/leaky-app/` 内含一个**伪造的 Stripe 测试密钥**，用于验证密钥脱敏能力，非真实凭据。
- 20 个技能名在多个专家包中重复出现，本仓库按体积取最完整版本收录一份，取舍明细见 [skills-conflicts.md](skills-conflicts.md)。

## 反馈

包的问题、命名冲突、技能取舍建议，欢迎提 Issue。
