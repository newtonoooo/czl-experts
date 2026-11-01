# 专业级短视频增长操盘手 · 阿爆

把抖音账号当生意盘：数据体检、爆款脚本、直播排品、投放测算与合规扫描，五段闭环落到能直接执行的表格。

- 包标识：`czl-douyin-growth-ops`
- 类型：Agent 型（单专家）
- 版本：1.0.0
- 开发者：虫志龙 · 47190078@qq.com

## 它解决什么问题

抖音上的建议大多停在"内容要好、钩子要抓人、坚持更新"。这些话都对，但没法执行。这个专家换一种做法：

- 不猜阈值 —— 用脚本把你的后台数据算成 0—100 分，指出漏斗上第一个掉人的环节。
- 不估时长 —— 口播稿按语速算到秒，检查钩子有没有落在前三秒。
- 不算糊涂账 —— 投放和直播先算保本线，再谈投多少、播多久。
- 不靠运气过审 —— 成稿必须过一遍词表扫描，高风险命中不交付。

## 五个能力

| 能力 | 挂载技能 | 你什么时候用它 |
|---|---|---|
| 账号与内容体检 | `dy-account-diagnosis` | "做了三个月没起量""这条为什么只有 300 播放" |
| 口播脚本工坊 | `dy-hook-script` | "这个选题怎么写""开头不抓人""要三版" |
| 直播排品与场控 | `dy-live-runbook` | "这场怎么排品""留不住人""播多少不亏" |
| 投放与周期复盘 | `dy-boost-review` | "要不要投 DOU+""钱烧了没效果""周末复盘" |
| 合规与话术风控 | `dy-compliance-lint` | "这句能不能说""会不会违规""被拒审了" |

## 四个可直接运行的脚本

全部纯标准库 Python 3.8+，无需安装任何第三方包。

```bash
# 1. 账号体检：算漏斗指标、定主断点
python skills/dy-account-diagnosis/scripts/dy_metrics.py --input data.json
python skills/dy-account-diagnosis/scripts/dy_metrics.py --demo

# 2. 口播时长：逐句时间轴 + 钩子落点
python skills/dy-hook-script/scripts/dy_timing.py --file script.txt --rate 270 --target 45

# 3. 投放与直播测算：保本 ROAS / CPA / GPM
python skills/dy-boost-review/scripts/dy_boost.py ads  --aov 129 --margin 0.4 --refund 0.15 --cpc 0.8 --cvr 0.02 --spend 3000
python skills/dy-boost-review/scripts/dy_boost.py live --aov 129 --margin 0.4 --refund 0.15 --fixed 3000 --spend 2000 --views 30000
python skills/dy-boost-review/scripts/dy_boost.py plan --aov 129 --margin 0.4 --refund 0.15 --budgets 1000,3000,5000

# 4. 合规扫描：7 类风险 + 改后稿（有高风险时退出码为 1，可做发布闸门）
python skills/dy-compliance-lint/scripts/dy_lint.py --file draft.txt
python skills/dy-compliance-lint/scripts/dy_lint.py --demo
```

退出码约定：`0` 正常 ／ `1` 检出高等级合规风险 ／ `2` 输入有误。

## 使用示例

- 我这个抖音号做了三个月还没起量，帮我把账号从头体检一遍，指出问题出在哪，给我这周就能执行的调整清单。
- 我这条选题是「月薪五千怎么存下第一个十万」，写三版不同钩子的口播脚本，标好时间轴、分镜和字幕重点。
- 下周六要播两小时卖家居用品，帮我排品、排节奏、写话术，并算出这场要卖多少才不亏。

## 目录结构

```
czl-douyin-growth-ops/
├── .codebuddy-plugin/plugin.json     # 专家元数据
├── agents/czl-douyin-growth-ops.md   # 主 Agent 提示词（工作流、闸门、红线）
├── avatars/expert.png                # 原创头像 512×512
├── skills/
│   ├── dy-account-diagnosis/         # SKILL.md + scripts/dy_metrics.py
│   ├── dy-hook-script/               # SKILL.md + scripts/dy_timing.py + templates/
│   ├── dy-live-runbook/              # SKILL.md + templates/
│   ├── dy-boost-review/              # SKILL.md + scripts/dy_boost.py
│   └── dy-compliance-lint/           # SKILL.md + scripts/dy_lint.py + references/banned-words.json
├── docs/
│   ├── 产品规格说明.md
│   ├── 使用说明.md
│   ├── 开发记录与文件清单.md
│   ├── 测试报告.md
│   └── 商业发布风险清单.md
├── CHANGELOG.md
├── LICENSE
└── README.md
```

## 头像

`avatars/expert.png`，512×512 PNG，457 KB，原创生成（详见 `docs/开发记录与文件清单.md` 的生成记录）。
替换要求：PNG/JPG，512×512，单张 ≤500KB。

## 安装与注册

专家必须放在专家目录才能被 WorkBuddy 检测到：

```
%WORKBUDDY_CONFIG_DIR%/plugins/marketplaces/my-experts/plugins/czl-douyin-growth-ops/
```

默认即 `~/.workbuddy/plugins/marketplaces/my-experts/plugins/`。

注册（写入 marketplace.json，注册后才会出现在专家中心）：

```bash
python scripts/register_expert.py <expert-dir>
```

校验与打包：

```bash
python scripts/validate_expert.py <expert-dir>
python scripts/package_expert.py <expert-dir> <output-dir>
```

## 边界声明

- 不承诺播放量、涨粉数、GMV 等结果，只给区间、条件与验证方法。
- 不提供刷量、刷评、养号、群控等违规操作方案。
- 合规扫描是机械自查工具，不构成法律意见；强监管类目需具备资质的主体或法务复核。
- 平台规则与工具报价会变动，方案中的规则引用以平台最新公示为准。

## 许可

本专家包内容（提示词、工作流、脚本、文档、头像）由虫志龙原创开发，保留所有权利，详见 `LICENSE`。
未包含任何第三方代码或素材。
