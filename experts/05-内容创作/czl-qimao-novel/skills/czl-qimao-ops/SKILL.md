---
name: czl-qimao-ops
description: Execution toolkit for the Qimao (七猫中文网) serial-fiction production line. Contains seven work-order templates, eight reference cards covering Qimao's chart genres, submission pack, title grammar, opening pressure, the official retention-tier table, attendance cash flow, launch nodes and compliance red lines, plus six dependency-free Python checkers for topic fit, title scoring, outline audit, sample-chapter gating, retention-tier placement and attendance cash flow. Use when running any station of the Q1-Q7 pipeline, when a number has to be computed rather than estimated, or when a deliverable must be written as a filled work order.
---

# 七猫生产线执行工具包

这个 Skill 是"七猫爆款小说生成专家"的手。专家负责判断，这里负责把判断变成可复算的数字和可交付的工单。

## 什么时候用

- 要跑 Q1–Q7 任何一站，需要对应的工单模板 → `templates/工单模板.md`
- 要查七猫的主收盘、分档表、全勤规则、审核红线 → `references/`
- 要把"感觉还行"变成"算得出来" → `scripts/`

## 目录

```
skills/czl-qimao-ops/
├── SKILL.md
├── references/
│   ├── R1-主收盘图谱.md
│   ├── R2-投稿包规范.md
│   ├── R3-书名与简介语法.md
│   ├── R4-开篇压强四件事.md
│   ├── R5-留存分档与跃迁.md
│   ├── R6-全勤与产能.md
│   ├── R7-节点作战.md
│   └── R8-审核与合规红线.md
├── scripts/
│   ├── q1_topic_fit.py
│   ├── q2_title_pack.py
│   ├── q3_outline_audit.py
│   ├── q4_sample_gate.py
│   ├── q6_retention_tier.py
│   └── q7_cash_flow.py
└── templates/
    └── 工单模板.md
```

## 脚本用法

全部纯标准库，Python 3.8+，离线可跑，不联网、不写数据库、不改用户文件。

### Q1 选品

```bash
python q1_topic_fit.py --channel nv --genre 年代重生
python q1_topic_fit.py --scores 4,3,5,2,4
```

`--genre` 查主收盘匹配度，`--scores` 按五维（读者基数、壳的新鲜度、爽点可复现性、长线可续航、合规安全）算判定。两个都给就先查表再算分。

### Q2 书名

```bash
python q2_title_pack.py --titles "离婚后她惊艳了世界" "大佬十代单传，我为他一胎生四宝"
```

按七猫书名四种语法逐条打分，指出缺哪一种。

### Q3 大纲

```bash
python q3_outline_audit.py --file 大纲.md --words 1200000
```

检查结局方向、三幕、卷级节拍、伏笔表、人物表，并按计划字数估章数。

### Q4 样章

```bash
python q4_sample_gate.py --file 前三章.md
python q4_sample_gate.py --dir ./chapters
```

测总字数、首 200 字压强、句长、对话占比、章末钩子。

### Q6 留存档位

```bash
python q6_retention_tier.py --retention 9 --uv 300 --type normal
```

输出当前档位、单价、离下一档的均留缺口与 UV 门槛。

### Q7 现金流

```bash
python q7_cash_flow.py --daily 5000 --days 30 --price 20 --mode baodi
python q7_cash_flow.py --daily 5000 --retention 12 --mode chunfencheng
```

输出四个日更档位的月字数、全勤、收入区间与断更风险。

## 使用纪律

1. **先跑脚本，再下判断。** 手算容易漏掉"每月 20 万字上限"和"UV 附加门槛"这两条。
2. **脚本报错就读参考卡手算，不许编结果。** 脚本只做算术和规则匹配，不做审美判断。
3. **所有引用标口径。** 官方规则标"官方口径"，行业说法标"经验值"，自己算的标"推算"。
4. **工单必须填满。** 空着的格子比填错的格子更危险，因为没人会去补。

## 已知边界

- 分档表按七猫官方福利页（2025 年 2 月版本）录入，平台会调，跑之前先核对官方页。
- 脚本不做敏感词库判断，合规靠 `R8` 人工过。
- 不抓取平台数据，所有输入由用户提供。
