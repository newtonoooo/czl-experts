# 文件清单

包名：`czl-livestream-ops-coach` ｜ 版本 1.0.0 ｜ 文件 32 个 ｜ 目录内容合计约 571 KB ｜ 打包后约 492 KB

## 一、元数据与协议

| 文件 | 大小 | 作用 |
|---|---|---|
| `.codebuddy-plugin/plugin.json` | 3.1 KB | 平台元数据：名称、版本、作者、许可、展示字段、3 标签、3 推荐问法、技能引用 |
| `README.md` | 5.9 KB | 使用说明：解决什么问题、六段工作流、三条铁律、安装与运行方式、边界与免责 |
| `CHANGELOG.md` | 3.3 KB | 版本更新日志（1.0.0 的完整变更项与已知限制） |
| `LICENSE` | 2.4 KB | 专有许可条款（非开源，禁止未授权转授权与公开分发） |
| `THIRD-PARTY-NOTICES.md` | 4.0 KB | 第三方内容声明：确认不含第三方代码/提示词/素材，说明头像与行业数据的来源 |

## 二、主提示词

| 文件 | 大小 | 作用 |
|---|---|---|
| `agents/czl-livestream-ops-coach.md` | 11.2 KB | 人设「阿麦」；三条判断铁律；六段工作流路由；开场七项输入与五条降级规则；七条输出规范；七条合规红线；七类异常处理；语气与能力边界 |

## 三、头像

| 文件 | 大小 | 作用 |
|---|---|---|
| `avatars/expert.png` | 399 KB | 原创头像，512×512 PNG，无水印、无文字，干练女性操盘教练形象（暖金背景） |

## 四、技能一：算数与诊断（`live-room-metrics`）

| 文件 | 大小 | 作用 |
|---|---|---|
| `skills/live-room-metrics/SKILL.md` | 4.7 KB | 技能说明：四个命令的用途、调用方式、输出契约、阈值表、常见错误、不做什么 |
| `skills/live-room-metrics/references/metric-definitions.md` | 9.3 KB | 指标口径与公式推导：五层漏斗、GPM、UV 价值、净 ROI、单件经济模型、保本 ROI、目标反推、类目修正 |
| `skills/live-room-metrics/scripts/live_metrics.py` | 25.3 KB | 计算脚本：`session` / `breakeven` / `plan` / `selftest`，纯标准库，22 项公式自检，支持 `--json` |

## 五、技能二：流程与模板（`live-room-playbook`）

| 文件 | 大小 | 作用 |
|---|---|---|
| `skills/live-room-playbook/SKILL.md` | 2.9 KB | 六段流水线总览、单点进入路由（8 类问法 → 对应段）、通用执行规则 |
| `references/workflows/W0-session-brief.md` | 5.3 KB | 场次立项：四种互斥目标、资源瓶颈判定、验收口径、风险预案 |
| `references/workflows/W1-assortment-rundown.md` | 5.3 KB | 货盘排品：五类货位、价格带梯度 1:2:3:5、三段节奏、30/40/30 库存释放、七条自检 |
| `references/workflows/W2-script-cards.md` | 5.9 KB | 话术脚本：整场三段结构、单品六段卡（含示例话术）、互动指令表、五个脚本版本切换条件 |
| `references/workflows/W3-host-coaching.md` | 6.0 KB | 主播带教：五项行为评分、逐句纠偏四步法、三轮彩排、30 天路径 |
| `references/workflows/W4-traffic-gates.md` | 6.0 KB | 流量闸门：三道闸门、预算上限公式、投放节奏表、自然流量四抓手、不消耗排查顺序 |
| `references/workflows/W5-session-review.md` | 5.3 KB | 场次复盘：五层漏斗、四类归因矩阵、真实盈亏、三件动作、唯一主变量 |
| `references/rundown-blueprint.md` | 4.1 KB | 节奏骨架：4 小时 24 段 / 2 小时 12 段分钟级骨架 + 波峰对齐四条自查 |
| `references/compliance-wordbank.md` | 5.8 KB | 合规词表：绝对化、功效医疗、保健食品、假比价、贬低同行、站外引流、未成年人七类替换表 + 自检三问 |
| `references/category-playbooks.md` | 5.6 KB | 类目手册：美妆、食品、服饰、家居、3C、母婴、本地生活七类的关键动作、排品、退货与合规风险 + 横向对比表 |
| `templates/session-brief.md` | 1.7 KB | 场次任务书填空表 |
| `templates/rundown-4h.md` | 2.3 KB | 4 小时 Rundown 填空表（24 行） |
| `templates/script-card.md` | 1.9 KB | 单品脚本卡填空表（六段 + 合规自检） |
| `templates/host-coaching-sheet.md` | 1.5 KB | 主播带教单（评分 + 纠偏 + 彩排 + 训练表） |
| `templates/traffic-plan.md` | 1.8 KB | 投放与流量计划（三道闸门 + 节奏表 + 自然流量四项） |
| `templates/review-report.md` | 1.7 KB | 场次复盘报告（指标 + 诊断 + 归因 + 盈亏 + 三件动作） |

## 六、交付文档

| 文件 | 大小 | 作用 |
|---|---|---|
| `docs/product-spec.md` | 7.2 KB | 产品规格：目标用户、场景、六类问题、输入输出、处理步骤、技术要求、10 条功能需求 |
| `docs/dev-record.md` | 8.9 KB | 开发记录：时间线、参考专家审计、六处补强、命名与定位决策、原创性说明、未采纳方案、维护计划 |
| `docs/test-report.md` | 7.8 KB | 测试报告：13 项实测/静态测试的真实命令与结果、10 条需求验收对照、6 项未验证事项 |
| `docs/risk-register.md` | 5.7 KB | 商业发布风险清单：20 条风险分级与缓解、发布前必做四件事、三项未能核实事项 |
| `docs/marketplace-listing.md` | 4.2 KB | 平台展示文案：卡片字段、推荐问法、详细介绍、关键词、文案自查 |
| `docs/file-manifest.md` | 本文件 | 文件清单与体积 |

## 七、不包含的内容（有意排除）

| 内容 | 原因 |
|---|---|
| 第三方营销技能库（23 个模块） | 许可链需单独核实，与本产品定位关联弱 |
| 平台 API 对接代码 | 各平台开放能力与授权条件差异大，且有账号安全风险 |
| 示例数据文件 | 避免被误当作真实行业基准 |
| 原参考专家的任何文本、模板、头像 | 版权与原创性要求 |

## 八、校验状态

| 检查 | 结果 |
|---|---|
| 平台校验脚本 `validate_expert.py` | 通过（无 error、无 warning） |
| 包完整性自检 17 项 | 全部通过 |
| 计算脚本自检 22 项 | 全部通过 |
| 注册 `marketplace.json` | 成功 |
| 打包 | 成功（32 个文件 → 约 492 KB） |
