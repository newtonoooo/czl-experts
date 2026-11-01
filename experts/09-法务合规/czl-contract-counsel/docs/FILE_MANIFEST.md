# 文件清单（File Manifest）

- 专家包：`czl-contract-counsel` v1.0.0
- 根目录：`~/.workbuddy/plugins/marketplaces/my-experts/plugins/czl-contract-counsel/`
- 文件总数：29 个（不含 `.gitkeep` 与平台会话标记 `.pending-preview-session`），其中本清单自身 1 个，故上表列 28 个
- 总体积：约 700 KB，其中头像 425 KB（占六成）
- 校验方式：MD5（生成时间 2026-10-26，内容如有改动校验值会变化，属正常）

## 一、清单

| # | 路径 | 字节 | 职责 | MD5 |
|---|---|---|---|---|
| 1 | `.codebuddy-plugin/plugin.json` | 2,938 | 专家元数据与市场展示字段（名称、职业头衔、分类、标签、推荐提问） | `32cd0e1958a843ae40b2511a4808c09d` |
| 2 | `agents/czl-contract-counsel.md` | 8,145 | 主提示词：角色定位、工作流路由、开工分流、执行纪律、交付体例、边界 | `e762f41e9c8470a70b235cc4be7feb06` |
| 3 | `avatars/expert.png` | 425,464 | 原创头像，512×512 PNG | `782f294af93bd93a6fbc75eda208d9ec` |
| 4 | `README.md` | 5,069 | 包说明：定位、能力、目录结构、安装注册、边界 | `955c5f983675553d7178b654d4e609d9` |
| 5 | `CHANGELOG.md` | 4,002 | 版本更新日志 | `d90e7f3e02af7aed54c94b691ddd9e25` |
| 6 | `LICENSE.md` | 4,319 | 许可协议（授予权利、限制、免责、第三方声明） | `00d89328fce35df8402dd266da597f93` |
| 7 | `docs/PRODUCT_SPEC.md` | 6,280 | 产品规格：目标用户、场景、问题、输入输出、处理步骤、质量要求、差异化 | `c6961508b0aa1a283e222279beb73363` |
| 8 | `docs/USAGE.md` | 6,486 | 使用说明：五条工作流用法、常见组合、排错表 | `4b9a3ad37372bac8d5abc729ac49f8b8` |
| 9 | `docs/DEVLOG.md` | 8,557 | 开发记录：阶段、决策、规模、测试、原创性说明、遗留事项 | `f35ce1f6492a373f71a1bb5ed4885c83` |
| 10 | `docs/TEST_REPORT.md` | 约 9 KB | 功能测试报告：32 用例结果、性能、缺陷修复、未验证项 | 见文件 |
| 11 | `docs/RELEASE_RISK.md` | 8,664 | 商业发布风险清单（12 项）与需开发者确认的 3 件事 | `98a79fc100e9a38cb32c5344efc4dd2e` |
| 12 | `docs/PLATFORM_LISTING.md` | 3,781 | 平台展示文案：名称、职业头衔、介绍、标签、推荐提问、关键词、上架备注 | `fb1dcfd691752c64690ab0958109bea6` |
| 13 | `skills/contract-counsel-toolkit/SKILL.md` | 4,684 | 技能说明：意图路由表、命令速查、数据文件、输出约定、异常约定、质量红线 | `526ede3d202d5f0a0f3dadea4b2f52c5` |
| 14 | `…/references/clause_library.json` | 58,426 | 原创条款库：6 类合同 72 条条款 + 必备要素清单 + 履约节点提示 | `419fc030ebd4792ba9a0d95e62ac4f3d` |
| 15 | `…/references/risk_rules.json` | 25,751 | 原创风险规则：31 条（含触发方式、风险说明、改法、法律依据、置信度） | `ec43b22c932e32be12623ef0f1e9f418` |
| 16 | `…/references/law_index.json` | 16,048 | 法条导航：4 部法律 44 条 + 10 个高频场景索引 + 官方来源 | `10f26606c8e80d95dec9455a67d54ca6` |
| 17 | `…/references/workflows.md` | 13,081 | 五条工作流完整规格（输入参数/步骤/判断条件/输出/异常/依赖/关系） | `710f818c92f4c9efa3fd68f0cf591155` |
| 18 | `…/references/io_spec.md` | 7,369 | 输入输出规范：spec 字段表、各工作流 JSON 结构、错误输出、退出码 | `0691ac302e6f748ac78f2069a2e8e5b5` |
| 19 | `…/scripts/cc.py` | 12,621 | 统一 CLI 入口（draft/review/compare/ledger/laws/amount/doctor） | `ac367d8f973f33ddfe8b29bf1ece3cc8` |
| 20 | `…/scripts/cc_common.py` | 9,031 | 公共层：文本读取（含 docx 解析）、条款切分、金额大写、IO | `f41caccad20d47ccb0d5631e8072d91f` |
| 21 | `…/scripts/cc_docx.py` | 17,441 | DOCX 写入器 + 包结构校验（OOXML 最小子集） | `7aa3302181f040c739c105b09e2e9952` |
| 22 | `…/scripts/cc_draft.py` | 12,286 | W1 起草：默认值合并、派生字段、正文装配、产物落盘 | `d20495b3446967b82a134bafd472a0d2` |
| 23 | `…/scripts/cc_review.py` | 14,543 | W2 审查：类型识别、五类检测器、打分、报告渲染 | `1d21df57dcbbd779199bf4bdda662a90` |
| 24 | `…/scripts/cc_compare.py` | 11,664 | W3 比对：对齐、相似度、数值比对、指向翻转、谈判清单 | `c7163f2f502b4c5407588e574e4c4d69` |
| 25 | `…/scripts/cc_ledger.py` | 7,481 | W5 台账：增删改查、日期推算、状态计算、报告 | `9efd9678b6e051db9d640f8ff0f4faf4` |
| 26 | `…/templates/samples/lease_risky.txt` | 1,911 | 演示样例：故意写坏的租赁合同（含 5 类高风险） | `963be3aa72101bb62ce81ab954ac67aa` |
| 27 | `…/templates/samples/purchase_v1.txt` | 1,208 | 演示样例：采购合同原版 | `37c176fc4ce0dfd828b0b78a2ef48280` |
| 28 | `…/templates/samples/purchase_v2_counterparty.txt` | 1,408 | 演示样例：对方回传的修改版 | `1438665e38b2cb19dee1d5cd14ed44ae` |

> 表中 `…` 指 `skills/contract-counsel-toolkit`。本清单自身（`docs/FILE_MANIFEST.md`）未列入上表。

## 二、目录结构

```
czl-contract-counsel/
├── .codebuddy-plugin/plugin.json
├── agents/czl-contract-counsel.md
├── avatars/expert.png
├── docs/
│   ├── PRODUCT_SPEC.md
│   ├── USAGE.md
│   ├── DEVLOG.md
│   ├── TEST_REPORT.md
│   ├── RELEASE_RISK.md
│   ├── PLATFORM_LISTING.md
│   └── FILE_MANIFEST.md          ← 本文件
├── skills/contract-counsel-toolkit/
│   ├── SKILL.md
│   ├── references/{clause_library,risk_rules,law_index}.json
│   ├── references/{workflows,io_spec}.md
│   ├── scripts/{cc,cc_common,cc_docx,cc_draft,cc_review,cc_compare,cc_ledger}.py
│   └── templates/samples/{lease_risky,purchase_v1,purchase_v2_counterparty}.txt
├── README.md
├── CHANGELOG.md
└── LICENSE.md
```

## 三、完整性检查记录

| 检查 | 方法 | 结果 |
|---|---|---|
| 元数据可解析 | `json.loads(plugin.json)` | 通过 |
| 引用路径存在 | 校验 `agents` / `skills` / `avatar` 指向的文件 | 通过（3 处引用全部命中） |
| agentName 与文件名一致 | `agentName` = `czl-contract-counsel` ↔ `agents/czl-contract-counsel.md` | 通过 |
| frontmatter 合规 | `name` 与文件名一致；无 `tools` 字段；含 description / displayName / profession / maxTurns | 通过 |
| 展示字段完整 | displayName / profession / displayDescription / defaultInitPrompt 中英文均非空 | 通过 |
| tags 与 quickPrompts 数量 | 均为 3；`defaultInitPrompt` 与 `quickPrompts[0]` 一致 | 通过 |
| 数据文件可解析 | 三个 JSON 全部 `json.loads` 通过，且被 `doctor` 计数校验 | 通过 |
| 脚本可执行 | 7 个模块 import 无异常，`cc.py doctor` 六项通过 | 通过 |
| 平台包校验 | `validate_expert.py` | 通过（见交付说明） |
| 打包产物 | `package_expert.py` 生成的 zip 内含全部文件且排除隐藏文件 | 见交付说明 |

## 四、不在包内的文件（仅开发期使用，不随包分发）

| 文件 | 位置 | 说明 |
|---|---|---|
| 头像原始生成图 `avatar-original-1024.png` | 开发者本机归档目录 | 1024×1024 带平台水印的原始生成图，仅作创作记录 |
| `png_tool.py` | 开发者本机归档目录 | 纯标准库 PNG 裁剪/重采样脚本，用于把生成图处理成 512×512 |
| `test_all.py` / `test_results.json` / `out_final/` | 开发者本机归档目录 | 回归测试脚本与执行产物 |

如需把测试脚本一并纳入版本管理，可放入 `tests/` 目录后重新打包；当前版本为控制包体积未纳入。
