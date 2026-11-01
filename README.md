# czl-experts

WorkBuddy 专家包与技能库，作者：虫志龙。以 MIT 许可开源。

**61 个专家包**（含单角色专家与多角色专家团），覆盖 14 个业务分类；**176 个独立技能**，已从专家包中拆解去重，可单独使用或发布。

- [专家包清单](EXPERTS.md) — 61 个包的花名、职业、类型、版本、技能数
- [技能清单](SKILLS.md) — 176 个技能的来源与分类
- [重名技能取舍说明](skills-conflicts.md) — 重名技能的去重依据
- [合规自查报告](COMPLIANCE.md) — 上架开放平台前的待修项
- [技能清单 CSV](skills-manifest.csv) — 机器可读版本

---

## 下载

`dist/` 下是可直接使用的成品包，完整清单（含体积与 SHA-256）见 [dist/MANIFEST.csv](dist/MANIFEST.csv)。

| 内容 | 位置 | 数量 |
|---|---|---|
| 专家包 zip | `dist/experts/<包标识>.zip` | 61 |
| 技能包 zip | `dist/skills/<技能标识>.zip` | 176 |

专家包 zip 内为 `<包标识>/...`（含 `.codebuddy-plugin/`），技能包 zip 内为 `<技能标识>/SKILL.md`。

```bash
# 克隆后直接安装某个专家
git clone https://github.com/newtonoooo/czl-experts.git
unzip czl-experts/dist/experts/czl-product-decision-audit.zip \
      -d "$WORKBUDDY_CONFIG_DIR/plugins/marketplaces/my-experts/plugins/"
```

## 目录结构

```
czl-experts/
├── dist/                        成品包（下载即用）
│   ├── experts/<包标识>.zip
│   ├── skills/<技能标识>.zip
│   └── MANIFEST.csv             体积与 SHA-256 校验值
├── experts/<分类>/<包标识>/      源码形态的专家包
│   ├── .codebuddy-plugin/plugin.json   身份与挂载声明
│   ├── agents/<包标识>.md              系统提示词
│   ├── skills/                         该专家挂载的技能
│   ├── avatars/                        头像 512×512
│   └── docs/                           开发记录、规格、测试报告、风险清单
└── skills/<技能标识>/            从专家包中拆解出的独立技能
    ├── SKILL.md                        技能主体（YAML frontmatter + 指令）
    ├── references/                     参考资料（按需）
    └── scripts/                        可执行脚本（按需）
```

## 安装专家包

把 `experts/<分类>/<包标识>/` 整个目录复制到 WorkBuddy 的专家目录，或直接解压 `dist/experts/` 下的 zip：

```bash
cp -r experts/01-产品设计/czl-product-decision-audit \
      "$WORKBUDDY_CONFIG_DIR/plugins/marketplaces/my-experts/plugins/"
```

复制后需在 WorkBuddy 的专家中心刷新，或重启客户端。

## 单独使用技能

每个 `skills/<技能标识>/` 都是自包含的，把整个目录复制到技能目录即可：

```bash
cp -r skills/evidence-ledger ~/.workbuddy-ai/skills/
```

技能的触发条件、输入输出、执行步骤都写在 `SKILL.md` 正文里，frontmatter 的 `description` 决定何时被调用。

## 许可

本仓库以 **MIT License** 开源，见 [LICENSE](LICENSE)。可自由使用、修改、商用、再分发，保留版权与许可声明即可。

部分包内附带的 `LICENSE` / `NOTICE` 是历史文件，其条款与仓库级 MIT 许可冲突时，以仓库根目录的 MIT 为准。

## 已知说明

- `czl-site-launch-pro/tests/fixtures/leaky-app/` 内含一个**伪造的 Stripe 测试密钥**，用于验证密钥脱敏能力，非真实凭据。
- 重名技能（同一技能标识出现在多个专家包中）按体积取最完整版本收录一份，取舍明细见 [skills-conflicts.md](skills-conflicts.md)。
- [COMPLIANCE.md](COMPLIANCE.md) 列出了上架开放平台前建议修正的字段问题，不影响本地安装与使用。

## 反馈

包的问题、命名冲突、技能取舍建议，欢迎提 Issue。
