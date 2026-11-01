# 文件清单

- 包名：czl-rival-teardown-pro
- 版本：1.0.0
- 根目录：`<WorkBuddy 配置目录>/plugins/marketplaces/my-experts/plugins/czl-rival-teardown-pro/`
- 文件总数：25（不含平台生成的 `.pending-preview-session` 等点文件）

---

## 一、核心运行文件（缺一不可）

| 文件 | 大小 | 行数 | 职责 |
|---|---|---|---|
| `.codebuddy-plugin/plugin.json` | 2.5 KB | 60 | 专家元数据：名称、版本、作者、展示文案、分类、标签、推荐提示词、头像引用 |
| `agents/czl-rival-teardown-pro.md` | 8.2 KB | 108 | 主 Agent 定义：角色、6 项核心能力、P0-P5 工作流、输出规范、异常处理表、注意事项 |
| `skills/rival-teardown-playbook/SKILL.md` | 6.4 KB | 121 | 技能入口：六步执行顺序、五层一览、交付物、质检门槛、依赖与边界 |
| `avatars/expert.png` | 389 KB | — | 头像 512×512 PNG |

## 二、技能参考文档（框架与规则）

| 文件 | 大小 | 行数 | 职责 |
|---|---|---|---|
| `skills/.../references/framework.md` | 9.7 KB | 217 | 五层拆解框架：每层的观察点、必答三问、常见错误、从五层到打法的转换规则 |
| `skills/.../references/evidence-rules.md` | 4.9 KB | 115 | 证据规则：四级来源、编号格式、台账写法、缺口披露、样本量披露、合规红线、禁止事项 |
| `skills/.../references/output-contract.md` | 5.1 KB | 158 | 输出契约：文件命名、15 章顺序与各章要求、打法卡/文案种子结构、质检项对照表 |
| `skills/.../references/playbook-patterns.md` | 5.9 KB | 156 | 八种切口模式 + 二维筛选法 + 伪切口清单 |

## 三、模板

| 文件 | 大小 | 行数 | 职责 |
|---|---|---|---|
| `skills/.../templates/report-template.md` | 5.3 KB | 183 | 主报告 15 章模板，`<!-- FILL -->` 标记待填 |
| `skills/.../templates/one-pager-template.md` | 0.9 KB | 33 | 打法卡一页纸模板 |
| `skills/.../templates/copy-seeds-template.md` | 1.2 KB | 52 | 文案种子模板（3 角度）+ 合规自查清单 |

## 四、可执行脚本

| 文件 | 大小 | 行数 | 职责 | 依赖 |
|---|---|---|---|---|
| `skills/.../scripts/teardown_toolkit.py` | 23.6 KB | 605 | CLI：parse / ledger / score / scaffold / check / selftest | Python 标准库 |
| `tools/package_qa.py` | 8.5 KB | 196 | 发布前 37 项完整性检查 + `--portable` 生成 data-URI 头像兼容版 | Python 标准库 |

## 五、文档

| 文件 | 大小 | 行数 | 职责 |
|---|---|---|---|
| `README.md` | 5.2 KB | 152 | 产品说明、快速开始、框架概览、工具用法、目录结构、边界 |
| `CHANGELOG.md` | 2.4 KB | 33 | 版本更新日志（1.0.0 新增项、设计取舍、已知限制） |
| `LICENSE` | 2.9 KB | 62 | 专有软件许可（授权范围、限制、产出物归属、免责） |
| `NOTICE.md` | 2.4 KB | 53 | 第三方组件与来源声明（代码、文档、图像、数据、商标、平台条款） |
| `docs/SPEC.md` | 9.1 KB | 185 | 产品规格：目标用户、场景、问题、输入输出规范、流程、工具接口、非功能要求、设计增量 |
| `docs/USAGE.md` | 6.8 KB | 218 | 使用说明：安装三种方式、四种场景问法、无抓取时的配合格式、交付物解读、FAQ |
| `docs/AVATAR-TROUBLESHOOTING.md` | 7.3 KB | 179 | 头像显示为文字的原因分析（含代码依据）、排查步骤、三种修复方案 |
| `docs/TEST-REPORT.md` | 8.7 KB | 220 | 功能测试报告：15 项测试、执行记录、4 个缺陷、未验证事项 |
| `docs/RISK-REGISTER.md` | 7.3 KB | 120 | 商业发布风险清单：10 项风险、处置方案、需决策事项 |
| `docs/DEVLOG.md` | 6.7 KB | 150 | 开发记录：需求重写、命名决策、框架设计、工程实现、测试返工、重合自查 |
| `docs/FILE-MANIFEST.md` | 本文件 | — | 文件清单与职责对照 |

## 六、示例

| 文件 | 大小 | 行数 | 职责 |
|---|---|---|---|
| `samples/竞品拆解-B0DEMO0001-2026-10-28.md` | 11.5 KB | 217 | 完整填写的示例报告（虚构数据），用于展示格式与质检通过状态 |

---

## 七、平台生成的文件（不随包分发）

| 文件 | 说明 |
|---|---|
| `.pending-preview-session` | 平台标记「待预览」的会话 ID，用于让新专家出现在当前会话的「我的专家」 |
| `.created-by-session` | 注册脚本写入的创建会话 ID（若平台已消费则不存在） |
| `__pycache__/` | Python 运行缓存，打包时自动排除 |

---

## 八、引用关系图

```
plugin.json
 ├─ agents/czl-rival-teardown-pro.md   (agentName)
 │    └─ skills: [rival-teardown-playbook]
 ├─ skills/rival-teardown-playbook/SKILL.md
 │    ├─ references/framework.md
 │    ├─ references/evidence-rules.md
 │    ├─ references/output-contract.md
 │    ├─ references/playbook-patterns.md
 │    ├─ templates/report-template.md
 │    ├─ templates/one-pager-template.md
 │    ├─ templates/copy-seeds-template.md
 │    └─ scripts/teardown_toolkit.py
 └─ avatars/expert.png                 (avatar)
```

路径校验方式：`python3 tools/package_qa.py`（37 项，含全部路径存在性检查）。
