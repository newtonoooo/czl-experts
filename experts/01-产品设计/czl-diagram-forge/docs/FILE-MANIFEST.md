# 文件清单

- 根目录：`C:\Users\丛自龙\.workbuddy-ai\plugins\marketplaces\my-experts\plugins\czl-diagram-forge`
- 文件总数：48（与发布 zip 内文件数一致）
- 总体积：755.0 KB
- 生成时间：2026-10-28

## 完整清单

| # | 文件 | 体积 |
|---|---|---|
| 1 | `.codebuddy-plugin/plugin.json` | 2.3 KB |
| 2 | `CHANGELOG.md` | 2.7 KB |
| 3 | `LICENSE` | 1.1 KB |
| 4 | `NOTICE.md` | 2.9 KB |
| 5 | `README.md` | 4.1 KB |
| 6 | `USAGE.md` | 5.1 KB |
| 7 | `agents/czl-diagram-forge.md` | 14.7 KB |
| 8 | `avatars/expert.png` | 472.0 KB |
| 9 | `docs/AVATAR-ISSUE-ANALYSIS.md` | 6.0 KB |
| 10 | `docs/DEV-LOG.md` | 8.4 KB |
| 11 | `docs/FILE-MANIFEST.md` | 4.4 KB |
| 12 | `docs/PRODUCT-SPEC.md` | 7.2 KB |
| 13 | `docs/RISK-ASSESSMENT.md` | 7.6 KB |
| 14 | `docs/TEST-REPORT.md` | 7.3 KB |
| 15 | `docs/WORKFLOWS.md` | 8.9 KB |
| 16 | `skills/diagram-forge/SKILL.md` | 5.7 KB |
| 17 | `skills/diagram-forge/references/cli-reference.md` | 3.3 KB |
| 18 | `skills/diagram-forge/references/mermaid-syntax.md` | 5.1 KB |
| 19 | `skills/diagram-forge/references/model-schema.md` | 7.3 KB |
| 20 | `skills/diagram-forge/references/quality-rubric.md` | 3.5 KB |
| 21 | `skills/diagram-forge/references/themes.md` | 3.7 KB |
| 22 | `skills/diagram-forge/scripts/dg.mjs` | 10.1 KB |
| 23 | `skills/diagram-forge/scripts/lib/ascii.mjs` | 8.9 KB |
| 24 | `skills/diagram-forge/scripts/lib/core.mjs` | 4.0 KB |
| 25 | `skills/diagram-forge/scripts/lib/layout-graph.mjs` | 11.1 KB |
| 26 | `skills/diagram-forge/scripts/lib/lint.mjs` | 11.5 KB |
| 27 | `skills/diagram-forge/scripts/lib/mermaid-export.mjs` | 9.5 KB |
| 28 | `skills/diagram-forge/scripts/lib/model.mjs` | 19.4 KB |
| 29 | `skills/diagram-forge/scripts/lib/paint-common.mjs` | 6.0 KB |
| 30 | `skills/diagram-forge/scripts/lib/paint-data.mjs` | 16.1 KB |
| 31 | `skills/diagram-forge/scripts/lib/paint-graph.mjs` | 15.2 KB |
| 32 | `skills/diagram-forge/scripts/lib/paint-sequence.mjs` | 6.1 KB |
| 33 | `skills/diagram-forge/scripts/lib/render.mjs` | 6.9 KB |
| 34 | `skills/diagram-forge/scripts/lib/scene.mjs` | 8.4 KB |
| 35 | `skills/diagram-forge/scripts/lib/themes.mjs` | 5.1 KB |
| 36 | `skills/diagram-forge/scripts/tools/avatar_check.py` | 12.1 KB |
| 37 | `skills/diagram-forge/scripts/tools/selftest.mjs` | 6.8 KB |
| 38 | `skills/diagram-forge/templates/class-service.json` | 2.1 KB |
| 39 | `skills/diagram-forge/templates/er-commerce.json` | 2.5 KB |
| 40 | `skills/diagram-forge/templates/flow-approval.json` | 2.6 KB |
| 41 | `skills/diagram-forge/templates/gantt-sprint.json` | 1.2 KB |
| 42 | `skills/diagram-forge/templates/mindmap-plan.json` | 942 B |
| 43 | `skills/diagram-forge/templates/pie-budget.json` | 351 B |
| 44 | `skills/diagram-forge/templates/quadrant-priority.json` | 819 B |
| 45 | `skills/diagram-forge/templates/sequence-api.json` | 1.8 KB |
| 46 | `skills/diagram-forge/templates/state-order.json` | 1.4 KB |
| 47 | `skills/diagram-forge/templates/timeline-release.json` | 486 B |
| 48 | `skills/diagram-forge/templates/xy-growth.json` | 455 B |

## 目录职责

| 目录 | 职责 |
|---|---|
| `.codebuddy-plugin/` | 专家元数据，唯一入口文件 `plugin.json` |
| `agents/` | 专家提示词，定义角色、能力、六条工作流、质量门槛 |
| `skills/diagram-forge/` | 技能本体：说明、参考资料、渲染引擎、模板 |
| `skills/diagram-forge/scripts/lib/` | 渲染引擎核心（13 个模块） |
| `skills/diagram-forge/scripts/tools/` | 自检脚本与头像体检工具 |
| `skills/diagram-forge/references/` | 模型规范、语法速查、主题、CLI、评分细则 |
| `skills/diagram-forge/templates/` | 11 份可运行模板，每类图表一份 |
| `avatars/` | 原创头像 |
| `docs/` | 产品规格、工作流、测试报告、风险清单、开发记录、头像排查 |

## 关键文件说明

| 文件 | 作用 |
|---|---|
| `.codebuddy-plugin/plugin.json` | 专家标识、展示字段、资源声明 |
| `agents/czl-diagram-forge.md` | 专家人格与工作流，是行为的唯一来源 |
| `skills/diagram-forge/SKILL.md` | 技能触发条件与使用方式 |
| `skills/diagram-forge/scripts/dg.mjs` | 命令行入口，6 个子命令 |
| `skills/diagram-forge/scripts/tools/selftest.mjs` | 86 项自检 |
| `skills/diagram-forge/scripts/tools/avatar_check.py` | 头像合规体检与规范化 |
| `avatars/expert.png` | 原创头像，512×512，472KB |
| `LICENSE` / `NOTICE.md` | 许可与第三方权利说明 |
