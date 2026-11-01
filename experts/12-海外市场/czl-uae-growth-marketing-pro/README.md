# 阿联酋营销增长专家 Pro / UAE Growth Marketing Pro

> 把营销目标变成一份能直接派活的投放方案：钱怎么分、投给谁、什么时候投、话怎么说、哪里会踩雷。

- **包名**：`czl-uae-growth-marketing-pro`
- **版本**：1.0.1
- **开发者**：虫志龙 · 47190078@qq.com
- **类型**：Agent 型单专家
- **分类**：05-MarketingGrowth

---

## 1. 它解决什么问题

出海品牌进阿联酋，最常见的四种翻车方式：

| 翻车方式 | 后果 | 本产品的对策 |
|---------|------|------------|
| 把阿联酋当成一个市场 | 预算摊在互不重叠的人群上，谁都打不透 | 强制五层人群分层（本国公民 / 阿拉伯外籍 / 南亚外籍 / 欧美外籍 / 游客） |
| 渠道凭感觉配 | 钱花了，但每个渠道都不够起量 | 确定性预算模型，分配精确到 AED，且不低于渠道起投门槛 |
| 忽略斋月节奏 | 在消费最低的时段投最贵的量 | 绑定真实日历的排期引擎，自动倒推素材与审批节点 |
| 文案写完才发现违规 | 返工，或直接下架 | 交付前合规扫描 + 双语规范，High 风险直接阻断 |

---

## 2. 快速开始

装好后在专家中心选择「阿联酋营销增长专家 Pro」，直接说需求即可。三种典型问法：

```
我要在阿联酋推一款新产品，预算 30 万迪拉姆，帮我出一份渠道配比和斋月节点排期方案
```

```
检查这段阿拉伯语和英语的促销文案，有没有文化或广告合规风险
```

```
阿联酋本地人和外籍居民的消费差异是什么？我的美妆品牌应该先打哪一层人群
```

### 它会先问你什么

全案模式下，如果缺以下任意一项，它会先停下来问，而不是硬编：

1. 品类 / 供给（卖什么）
2. 目标（声量 / 线索 / 成交 / 复购）
3. 预算（AED）
4. 时间窗（什么时候必须上线）
5. 目标人群线索（本地人还是外籍）

---

## 3. 工作流总览

```
需求 → 路由 → W1 目标校验 → W2 人群分层 → W3 预算建模 → W4 节点排期 → W5 合规与文案 → W6 质检门 → 交付
```

| 工作流 | 职责 | 关键产出 |
|--------|------|---------|
| **W1** Objective & Offer | 五要素校验，缺项追问 | 参数表 + 待确认假设 |
| **W2** Audience tiering | 三层结构切人群 | 分层表（语言/媒介/驱动/预算占比） |
| **W3** Spend architecture | 渠道配比与预算建模 | 渠道表 + 曝光触达区间 + KPI |
| **W4** Calendar | 绑定斋月/国庆/DSF 等节点 | 时间轴 + 倒推里程碑 |
| **W5** Safety & script | 合规扫描 + 双语文案 | 风险清单 + AR/EN 终稿 |
| **W6** QA Gate | 八项质检 | 通过 / 退回 |

详细定义见 [`docs/WORKFLOWS.md`](docs/WORKFLOWS.md)。

---

## 4. 内置工具

所有脚本零第三方依赖，仅用 Python 3 标准库。

```bash
# 渠道预算建模
python bin/uae_plan.py --budget 300000 --objective awareness \
  --audience core --sector beauty --market uae_wide

# 合规扫描（退出码 1 = 有 High 风险，禁止交付）
python bin/uae_compliance.py --text "限时秒杀，100% 保证有效" --sector beauty

# 节点日历
python bin/uae_campaign_calendar.py --year 2027 --format markdown
python bin/uae_campaign_calendar.py --year 2027 --format ics --out campaign.ics

# 市场情报查询
python skills/uae-market-intel/scripts/intel_query.py segments
python skills/uae-market-intel/scripts/intel_query.py channels-for --sector beauty

# 专家包自检
python bin/package_check.py

# 头像归一化（1024 → 512 正方形 + 透明圆角）
python bin/avatar_tool.py avatars/source.png avatars/expert.png --size 512
```

---

## 5. 知识库与口径

| 文件 | 内容 |
|------|------|
| `skills/uae-market-intel/data/audience_segments.json` | 五个人群层 |
| `skills/uae-market-intel/data/channel_catalog.json` | 13 个渠道的采买参数 |
| `skills/uae-market-intel/data/sector_notes.json` | 12 个行业的渠道偏置与合规红线 |
| `skills/uae-brand-safety/data/risk_rules.json` | 22 条合规风险规则 |

**每个数值都带 `basis` 字段**：`official-stat` / `industry-report` / `platform-stated` / `planning-range`。标为 `planning-range` 的数字只能作为建模假设，不能当作事实对外陈述。

> 这些是采买基线，不是审计数据。对外发布前必须用平台实时报价与官方统计复核。

---

## 6. 安装

### 方式一：导入 zip

专家中心 → 导入专家 → 选择 `dist/czl-uae-growth-marketing-pro.zip`。

### 方式二：手动放置

```
<WorkBuddy 配置目录>/plugins/marketplaces/my-experts/plugins/czl-uae-growth-marketing-pro/
```

Windows 下配置目录通常为 `C:\Users\<用户名>\.workbuddy-ai`，macOS / Linux 为 `~/.workbuddy-ai`。

```bash
python "<expert-manager 路径>/scripts/register_expert.py" \
  "<配置目录>/plugins/marketplaces/my-experts/plugins/czl-uae-growth-marketing-pro"
```

注册后重启客户端，专家中心即可看到。

---

## 7. 图标显示为文字？先看这份

如果你导入后**专家图标变成一个字**（比如"阿"），不是图片坏了，而是平台的头像解析链没拿到绝对地址，回退成了名称首字。

完整原因与自查清单见 [`docs/ICON_FALLBACK_DIAGNOSIS.md`](docs/ICON_FALLBACK_DIAGNOSIS.md)。

一句话结论：**保证 zip 内有 `avatars/expert.png`、路径与 `plugin.json` 的 `avatar` 字段完全一致、文件 ≤500KB、正方形 PNG**，这四条满足后图标就能正常显示。

本包的头像已按最保守的配置出图：**512×512、8bit RGB（不带 alpha 通道）、200KB、全幅不透明**。这是兼容性最好的组合——透明通道与圆角在某些客户端会增加加载失败概率，所以刻意不用。

---

## 8. 目录结构

```
czl-uae-growth-marketing-pro/
├── .codebuddy-plugin/
│   └── plugin.json              # 平台元数据
├── agents/
│   └── czl-uae-growth-marketing-pro.md   # 主提示词与工作流
├── skills/
│   ├── uae-market-intel/        # 市场情报底座（3 份 JSON + 查询脚本）
│   ├── uae-channel-mix/         # 渠道配比方法论
│   └── uae-brand-safety/        # 合规与双语文案
├── bin/
│   ├── uae_plan.py              # 预算建模
│   ├── uae_compliance.py        # 合规扫描
│   ├── uae_campaign_calendar.py # 节点日历
│   ├── package_check.py         # 包自检
│   └── avatar_tool.py           # 头像归一化
├── avatars/expert.png           # 512×512 原创头像（阿联酋人物形象，RGB，200KB）
├── docs/assets/avatar-source-880.png  # 头像源图（已去水印，创作溯源）
├── tests/                       # 58 项单元测试
├── docs/                        # 规格、工作流、测试、风险、开发记录
├── README.md
├── CHANGELOG.md
└── LICENSE
```

---

## 9. 边界

- 不承诺 ROI 或具体转化数字，只给区间、假设和验证方法。
- 不提供法律意见。牌照、审批、内容审查的最终结论由主管机构与本地法律顾问确认。
- 合规扫描是辅助手段，关键词通过不等于内容安全，语境仍需人工判断。

---

## 10. 许可

专有软件，商业分发需授权。详见 [`LICENSE`](LICENSE)。
