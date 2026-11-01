# 专业亚马逊Listing专家

> 亚马逊 Listing 撰写与合规增长顾问。六道闸门，每一步都出数字、出文件、出放行条件。
> 由虫志龙独立开发 · v1.0.1

---

## 它解决什么

写 Listing 最耗时间的不是"想不出词"，是**写完不知道会不会被压、不知道哪句话违规、不知道该准备什么材料**。

这个产品把这三件事变成可执行的检查：

| 你原来的做法 | 现在的做法 |
|---|---|
| 写完数一下字符，靠感觉删 | 先算预算再写，脚本核字符、全大写、符号、堆砌、重复 |
| 觉得"best"应该没问题 | 10 类宣称规则逐条扫，命中即给级别、原因、改法 |
| 上架后才知道德国要责任人 | 7 类目门槛 × 9 站点义务，提前列清单 |
| 不知道文案能不能被 AI 助手引用 | 七维加权打分 + 未答问题清单 |
| 被下架了不知道怎么写申诉 | 四段式框架 + 证据清单 + 提交前自查 |

## 六道闸门

```
G0 输入体检  →  G1 关键词预算  →  G2 文案构建  →  G3 合规放行  →  G4 AI 就绪度
                                                        ↘  G5 申诉框架（独立入口）
```

| 门 | 产物 | 过门条件 |
|---|---|---|
| G0 输入体检 | 输入卡 + 缺失项 | 站点、类目、产品本体、≥1 主词齐备 |
| G1 关键词预算 | 词 → 位置 → 字符预算 分配表 | 每词唯一归属，标题不超预算 |
| G2 文案构建 | 标题 / 五点 / 描述 / 后台词 | lint 无 BLOCK |
| G3 合规放行 | 三级清单 + GO / CONDITIONAL / BLOCKED | 无 BLOCK |
| G4 AI 就绪度 | 0–100 分 + 逐项扣分 + 问答缺口 | 每个扣分项都有改写动作 |
| G5 申诉框架 | 根因 / 纠正 / 预防 / 证据 | 每段有可执行动作 |

## 内置审计引擎

`skills/listing-ops-kit/scripts/listing_audit.py`，纯 Python 标准库，不联网、不装包、不需要 API Key。

```bash
S=skills/listing-ops-kit/scripts/listing_audit.py

python $S lint       --listing x.json --market US
python $S compliance --listing x.json --market DE --category juvenile_products
python $S score      --listing x.json
python $S keywords   --listing x.json --market US
python $S report     --listing x.json --market US --category general --out report.md
```

退出码：`0` 通过 / `1` 警告 / `2` 阻断。加 `--json` 拿机器可读结果。

### 四类计算结果

| 子命令 | 算出来的东西 |
|---|---|
| `lint` | 标题/五点/描述/后台词的字符预算、全大写、非标准符号、词频堆砌、重复短语、五点数量与信息量 |
| `compliance` | 10 类宣称规则 + 7 类目门槛 + 9 站点义务 → BLOCK / CONDITION / INFO + 放行判定 |
| `score` | 七维加权 0–100：属性完整度、场景人群、问答覆盖、实体一致性、结构化、差异化证据、关键词自然度 |
| `keywords` | 词池去重、token 重叠分组、按字符预算分配到标题/五点/描述/后台词 |

## 覆盖范围

- **站点**：US / UK / DE / FR / IT / ES / JP / CA / AU
- **类目**：electronics、juvenile_products、food_contact、textiles、toys、battery_products、general
- **语言**：中文交互；站点文案按目标语言写，不确定处标注 `[待校对]`

## 它不做的事

不做广告投放、不做选品、不做成本与定价、不做图片视频、不代写申诉终稿、不承诺排名与销量。

这不是能力不足，是**边界**：混进来会稀释每道门的判断标准。

## 目录

```
czl-amazon-listing-growth/
├── .codebuddy-plugin/plugin.json     # 专家元数据
├── agents/czl-amazon-listing-growth.md  # 角色与闸门规则
├── avatars/expert.png                # 512×512 头像
├── skills/listing-ops-kit/
│   ├── SKILL.md                      # 套件总纲
│   ├── workflows/                    # 六道闸门操作手册
│   ├── references/                   # 规则包（站点/合规/写法/评分）
│   └── scripts/listing_audit.py      # 审计引擎 + 四份样本
├── docs/                             # 规格、工作流设计、测试、风险、清单
├── README.md  USAGE.md  CHANGELOG.md  LICENSE  NOTICE.md
```

## 三条纪律

1. **不编费率**——佣金、FBA 费、广告费没有来源就标"未提供，未计入"。
2. **不给结论不给清单**——任何放行判定都要带阻断项/条件项。
3. **不交未检文案**——交付前必须跑 lint，退出码和命中项一起给。

## 边界声明

本产品提供文案写作与合规自查建议，**不构成法律意见，不构成对亚马逊政策的官方解释，不构成对销售结果的承诺**。规则包中的字符上限与合规义务为配置基线，会随平台与法规变化；冲突时以你的后台显示与当地法规为准。本产品与亚马逊公司无任何隶属或合作关系。

## 许可

见 `LICENSE`。开发者：虫志龙 · 47190078@qq.com
