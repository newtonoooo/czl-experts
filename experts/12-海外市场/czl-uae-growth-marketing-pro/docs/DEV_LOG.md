# 开发记录与来源声明

- **产品**：阿联酋营销增长专家 Pro / `czl-uae-growth-marketing-pro`
- **开发者**：虫志龙 · 47190078@qq.com
- **开发日期**：2026-10-28
- **版本**：1.0.1（1.0.0 于同日发布，1.0.1 为头像与图标兼容性修订）

---

## 一、来源声明

### 1.1 功能分析的参考对象

开发前，对同类专家包做了一次**功能性阅读**，目的是理解"阿联酋营销顾问"这个角色需要覆盖哪些任务面，以及平台专家包的格式规范。阅读范围限于：

| 读取的文件 | 提取了什么 | 未提取什么 |
|-----------|-----------|-----------|
| `.codebuddy-plugin/plugin.json` | 平台元数据字段清单（这是平台规范，不是创作内容） | 未沿用其文案、标签、名称 |
| `agents/*.md` | 角色覆盖的任务面：人群、品牌落地、渠道、内容、增长 | 未复制任何段落、句式、结构、方法论命名 |
| `skills/*/SKILL.md` | 技能的组织方式（何时用/怎么用/注意事项） | 未复制规则条文、未沿用问卷流程 |
| `README.md` | 交付物应包含哪些说明 | 未复制描述文字 |

### 1.2 明确未使用的部分

| 项 | 处置 |
|----|------|
| 原有提示词文本 | **未使用**。本产品主提示词为从零撰写，采用自建的 OASIS 五段框架，与原产品的线性五步流程结构不同 |
| 原有工作流定义 | **未使用**。本产品的 W1~W6 含独立输入契约、判断条件、退出码语义，为重新设计 |
| 原有 12 步问卷流程 | **未使用**。本产品以"结构化受理 + 确定性计算 + 合规引擎"替代长问卷 |
| 原有头像 | **未使用**。本产品头像为独立生成的几何图形 |
| 原有 COS 数据桶依赖 | **未使用**。原产品依赖私有 COS 桶与内置凭证，不可分发给第三方；本产品改为自带本地知识库 + 在线检索，无凭证、无网络请求 |
| `expert-card.json` | **未使用**。经检索确认平台不读取该文件（`app.asar` 中命中 0 次） |
| 原有宣传文案 | **未使用**。展示文案为按实际功能重写 |

### 1.3 独立创作的部分

以下内容全部为本项目原创：

1. **OASIS 五段框架**（Objective / Audience / Spend / Islamic calendar / Safety）及其映射到 W1~W6 的工作流架构。
2. **五层人群模型**的结构设计与全部描述文本。
3. **渠道三分法**（信任/发现/转化）与 13 个渠道的采买参数、素材要求、KPI 形态。
4. **12 个行业**的渠道偏置与合规红线描述。
5. **22 条合规规则**的分类、模式、依据与替代表达。
6. **两级预算分配算法**（先按目标分角色，再按适配度分渠道）与门槛校验重分配逻辑。
7. **日历引擎**的锚点表、漂移算法、工作日回退规则。
8. **零依赖 PNG 编解码器**（`avatar_tool.py`），含自适应行过滤。
9. **包自检工具**（`package_check.py`）的三层 33 项检查。
10. **58 项单元测试与 24 项集成检查**。
11. **全部文档**与**头像**。

### 1.4 通用技术方法的使用

以下属于公开通用技术，按常规方式使用，不构成对特定产品的复制：

- WorkBuddy 专家包目录结构（平台规范，公开）
- PNG 文件格式规范（ISO/IEC 15948）
- 最大余数法（largest remainder method）用于整数分配
- 伊斯兰历每年约 10.9 天的公历漂移（公开天文常识）
- Python 标准库用法

---

## 二、开发过程

| 阶段 | 工作 | 产出 |
|------|------|------|
| 1. 规范确认 | 读平台专家包规范（plugin.json 字段、agent frontmatter、skill 结构、头像规格）与官方校验/打包/注册脚本 | 明确了必填字段、字数限制、目录限制 |
| 2. 图标问题定位 | 反查客户端渲染层代码，定位头像回退为文字的四条代码路径 | `docs/ICON_FALLBACK_DIAGNOSIS.md` |
| 3. 需求转化 | 把"阿联酋营销顾问"的任务面转成 7 个问题（P1~P7）与对应解法 | `docs/PRODUCT_SPEC.md` |
| 4. 架构设计 | 设计 OASIS 五段框架、三种执行模式、八项质检门 | 主提示词 |
| 5. 知识库 | 编写 3 份 JSON 知识库，每个数值标 basis 口径 | `skills/uae-market-intel/data/` |
| 6. 工具实现 | 5 个零依赖脚本 | `bin/` |
| 7. 测试 | 58 单元 + 24 集成，抓到 5 个真实缺陷并修复 | `docs/TEST_REPORT.md` |
| 8. 头像 | 生成人物形象，裁掉工具水印，归一化为 512 RGB 200KB | `avatars/expert.png` |
| 9. 文档 | 规格、工作流、测试、风险、展示文案、开发记录 | `docs/` |
| 10. 发布 | 官方脚本校验 → 打包 → 注册 | 见第三节 |

### 测试驱动的缺陷修复记录

| 缺陷 | 发现方式 | 修复 |
|------|---------|------|
| 角色覆盖保证互相覆盖 | `test_large_budget_keeps_a_trust_channel` 失败 | 改为必需角色优先占位 |
| 分配低于渠道起投门槛 | `test_no_channel_below_its_minimum_budget` 失败 | 增加 `allocate_with_floor` 重分配 |
| 占比合计只有 90% | `test_shares_sum_to_about_hundred` 失败 | 分母改为可投放预算 |
| 周五被当作安全截止日 | `test_sunday_moves_back_to_thursday` 失败 | 回退至周一至周四 |
| 元组解包错误 | 12 个用例报 ERROR | 修正为字典查表 |

---

## 三、发布记录（实际执行结果）

### 3.1 自研包自检

```
$ python bin/package_check.py
合计：PASS 33 · WARN 0 · FAIL 0
结论：通过。
```

### 3.2 平台官方校验

```
$ WORKBUDDY_CONFIG_DIR=... python validate_expert.py <installed path>
🔍 Validating expert package: .../czl-uae-growth-marketing-pro
✅ Expert package is valid!
```

零 error、零 warning。

### 3.3 打包

```
$ python package_expert.py <installed path> <workspace>/dist
✅ Packaged 33 files to: .../dist/czl-uae-growth-marketing-pro.zip
   Size: 861.8 KB
```

zip 结构确认：唯一根目录 `czl-uae-growth-marketing-pro/`，内含 `avatars/expert.png`，无 `dist/` 嵌套。

### 3.4 注册

```
$ python register_expert.py <installed path>
✅ Validation passed
✅ Registered 'czl-uae-growth-marketing-pro' in marketplace.json
🎉 Expert is now registered and visible in WorkBuddy!
```

`my-experts/.codebuddy-plugin/marketplace.json` 条目数：33（含本产品）。
会话标记 `.pending-preview-session` 已写入。

### 3.5 安装副本复测

```
$ cd <installed path> && python -m unittest discover -s tests
Ran 67 tests in 3.180s
OK
```

安装后的副本与开发副本行为一致。

---

## 四、文件清单

| 文件 | 职责 | 行数级 |
|------|------|-------|
| `.codebuddy-plugin/plugin.json` | 平台元数据：名称、版本、作者、双语展示字段、3 标签、3 推荐提示、头像引用 | 90 |
| `agents/czl-uae-growth-marketing-pro.md` | 主提示词：立场边界、OASIS 框架、路由、W1~W6、输出规范、数据纪律 | 380 |
| `skills/uae-market-intel/SKILL.md` | 市场情报技能说明与数据口径纪律 | 80 |
| `skills/uae-market-intel/data/audience_segments.json` | 5 个人群层画像 | 90 |
| `skills/uae-market-intel/data/channel_catalog.json` | 13 个渠道采买参数 | 260 |
| `skills/uae-market-intel/data/sector_notes.json` | 12 个行业渠道偏置与红线 | 140 |
| `skills/uae-market-intel/scripts/intel_query.py` | 情报查询 CLI（5 子命令） | 220 |
| `skills/uae-channel-mix/SKILL.md` | 渠道配比方法论与参数说明 | 100 |
| `skills/uae-brand-safety/SKILL.md` | 合规与双语文案规则 | 120 |
| `skills/uae-brand-safety/data/risk_rules.json` | 22 条风险规则 | 230 |
| `bin/uae_plan.py` | 渠道预算模型（两级分配 + 门槛校验） | 330 |
| `bin/uae_compliance.py` | 合规扫描（退出码即判断条件） | 200 |
| `bin/uae_campaign_calendar.py` | 节点日历（含 ICS 导出） | 260 |
| `bin/package_check.py` | 包自检（33 项） | 300 |
| `bin/avatar_tool.py` | 零依赖 PNG 编解码与归一化 | 300 |
| `avatars/expert.png` | 512×512 8bit RGB 原创人物头像（阿联酋本地特征），200KB，无水印 | — |
| `docs/assets/avatar-source-880.png` | 头像源图（已裁去工具水印，创作溯源） | — |
| `tests/test_plan.py` | 预算模型 15 项 | 150 |
| `tests/test_compliance.py` | 合规扫描 12 项 | 100 |
| `tests/test_calendar.py` | 日历 18 项 | 130 |
| `tests/test_package.py` | 包完整性 13 项 | 110 |
| `tests/test_avatar.py` | PNG 工具链 9 项 | 90 |
| `tests/run_integration.py` | 24 项集成检查 | 200 |
| `docs/PRODUCT_SPEC.md` | 产品规格说明 | 200 |
| `docs/WORKFLOWS.md` | 工作流契约 | 230 |
| `docs/TEST_REPORT.md` | 功能测试报告 | 230 |
| `docs/RISK_REGISTER.md` | 商业发布风险清单 | 160 |
| `docs/ICON_FALLBACK_DIAGNOSIS.md` | 图标回退诊断 | 180 |
| `docs/MARKETPLACE_COPY.md` | 平台展示文案 | 200 |
| `docs/DEV_LOG.md` | 开发记录与来源声明（本文件） | 180 |
| `README.md` | 使用说明 | 220 |
| `CHANGELOG.md` | 更新日志 | 90 |
| `LICENSE` | 专有许可 | 80 |

合计 33 个文件（含 `dist/` 下的 zip）。

---

## 四之一、头像修订记录（1.0.1）

### 为什么换

1.0.0 用的是纯几何徽标。实际使用中两个问题：一是用户希望专家列表里是"人"，与平台其他专家一致；二是原图生成时带工具水印（右下角），且输出为 RGBA 透明圆角，在部分客户端上加载失败概率更高。

### 怎么做的

| 步骤 | 操作 | 工具 |
|------|------|------|
| 1 | 生成人物形象：年轻阿联酋男性，kandura + ghutra + agal，短须，深青底 | ImageGen（1024×1024） |
| 2 | 定位水印：水印在图像内部右下角，直接裁掉会破坏构图 | 像素扫描 |
| 3 | 裁剪 880×880 干净区域（x72 y20 起），完全排除水印带 | `avatar_tool.py --crop` |
| 4 | 合成到背景色 `#17474A`，输出 8bit RGB（无 alpha），512×512 | `avatar_tool.py --flatten` |
| 5 | 体积 200KB，远低于 500KB 上限 | — |
| 6 | 归档干净源图 `docs/assets/avatar-source-880.png`，删除带水印的中间文件 | — |

### 为什么改成 RGB 而不是 RGBA

带透明通道的头像在部分客户端上解码失败概率更高，失败就会触发 `onError` → 首字回退。圆形头像容器本身会裁掉四角，圆角透明没有视觉收益，所以直接放弃 alpha，换取最高的显示成功率。

### 版权说明

头像为本产品定制生成，无第三方素材、无水印、无人物肖像权问题（虚构形象，非真实人物）。源图与成品均保留在本包内作为创作溯源。

---

## 五、尚未完成、需开发者决定

| # | 事项 | 说明 |
|---|------|------|
| 1 | 目标市场同名检索 | 本地 33 个专家包中无重名，市场侧未检索 |
| 2 | 平台分成与独家条款确认 | 需阅读平台协议 |
| 3 | 阿语母语审校 | 建议找母语者过一遍阿语规则与示例 |
| 4 | 全新实例导入验证 | 本机已完成安装与注册，跨设备导入未验证 |
| 5 | 真实账户 CPM 校准 | 需客户后台数据 |

详见 `docs/RISK_REGISTER.md` 第四节。
