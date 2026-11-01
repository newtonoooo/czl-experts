# 使用说明 · 专业出海落地官

---

## 一、三十秒上手

打开对话，说清三件事就能开工：

```
产品是什么 + 卖到哪个国家 + 在哪个平台
```

例：

> 硅胶折叠水杯，出厂价 12 块含包装，想卖到美国亚马逊，海运头程，售价打算定 19.99 美金。

我会先确认成本口径、目的国、卖家身份（有没有商标与税号），然后按需要走六道门。

---

## 二、三种典型用法

### 用法 A：只问一个数（最快）

> 出厂 12 块，卖 19.99 美金，FBA 配送 4.75，佣金 15%，退货率 8%，广告占比 12%。这价能做吗？

走 G2：跑 `landed_cost.py`，给你成本瀑布、保本价、保本 ACOS、价格阶梯与结论。
缺失的费率会列成"待填"，不会用行业均值替你填。

### 用法 B：判断能不能进某个市场

> 儿童餐椅要进德国和法国，有 CE 报告，没有欧盟责任人，包装没注册 LUCID。

走 G3：跑 `compliance_gate.py`，给你阻断/条件/提示三级清单 + GO/CONDITIONAL/BLOCKED 判定 + 每项找谁办、常见周期。

### 用法 C：全流程（新品从零开始）

> 我要把这款折叠水杯做上亚马逊美国站，预算 3 万，帮我从头到尾算一遍。

走 G0→G5，依次产出六份文件：

| 文件 | 内容 |
|---|---|
| `立项卡-折叠水杯-2026-10-27.md` | 产品、市场、渠道、预算、资质、待答问题 |
| `选品判定-折叠水杯-2026-10-27.md` | 四条判据 + 结论（进/换切口/不进） |
| `成本定价-折叠水杯-2026-10-27.md` | 瀑布、三条保本线、阶梯、敏感性、结论 |
| `合规放行单-折叠水杯-US-2026-10-27.md` | 三态清单 + 放行判定 |
| `Listing-折叠水杯-amazon_us-2026-10-27.md` | 标题五点描述 + 体检结果 + 待审校三处 |
| `冷启补货-折叠水杯-2026-10-27.md` | 投放结构 + 止损线 + 补货点 + 现金占用 |

---

## 三、四个脚本自己也能跑

脚本在 `skills/landing-kit/scripts/`，只需要 Python 3，不需要装包。

### 1. 到岸成本

```bash
python landed_cost.py --input fixtures/cup_us.json
python landed_cost.py --price 19.99 --unit-cost 12 --cost-in-cny --fx 7.15 \
    --fulfillment 4.75 --commission-pct 15 --return-rate 8 --ad-pct 12 --duty-pct 3
```

`--cost-in-cny` 只折算中国侧成本（采购 / 包装 / 头程）；配送费、仓储、退货处理按目标币填。

### 2. 合规放行

```bash
python compliance_gate.py --list
python compliance_gate.py --category baby --market DE --market FR
python compliance_gate.py --category electronics --market US --have US-TAX,US-FCC
```

`--have` 填规则编号（脚本输出里的 `US-TAX` 这类），表示已具备该项。
`--assume-path` 表示阻断项已有明确办理路径与日期，判定降为 CONDITIONAL。

### 3. 文案体检

```bash
python listing_lint.py --list
python listing_lint.py --profile amazon_us --input fixtures/listing_bad.json
python listing_lint.py --profile amazon_de --title "..." --bullet "..." --brand "AquaCup"
```

退出码 1 表示有 error，必须改到 0 才能交付。

### 4. 补货计划

```bash
python replenish_plan.py --input fixtures/replenish_case.json
python replenish_plan.py --daily 18 --sea-days 42 --moq 500 --stock 600 --in-transit 500 \
    --unit-cost 8.46 --cash-budget 20000
```

四个脚本都支持 `--selftest`（各 7 项断言）与 `--json`（便于二次处理）。

---

## 四、怎么改规则（重要）

平台字数、禁售清单、各国合规要求都会变，所以这些是**数据文件**，不是写死的代码：

| 文件 | 改什么 | 改完要做什么 |
|---|---|---|
| `references/listing-profiles.json` | 各平台标题字数、禁词表、五点条数 | 重跑 `listing_lint.py --selftest` 与一次样例 |
| `references/compliance-rules.json` | 各国基础要求、品类叠加要求 | 重跑 `compliance_gate.py --selftest` 与 `--list` |
| `references/cost-lines.md` | 成本科目口径 | 与 `landed_cost.py` 的公式保持同步 |

两个 JSON 都有 `meta.as_of` 字段，改完请更新月份。

---

## 五、你会拿到什么、不会拿到什么

**会拿到**

- 每个数字的算式与出处（脚本原始输出附在交付里）
- 每个合规项的编号、需备证据、找谁办、常见周期
- 每个广告活动的止损条件
- 每个文件的具体路径

**不会拿到**

- 编造的费率与税率（缺就标"待填"）
- 保证排名、保证爆单、保证 ROI
- 刷单、测评群、借用证书、跟卖抄图的操作方案
- 专利有效性判断（会告诉你去做 FTO 检索，找谁做）

---

## 六、常见误用（会被直接纠正）

| 你怎么问 | 我会怎么回 |
|---|---|
| "帮我写个能爆的标题" | 标题可以写，但要先有目标词与卖点证据；写完还要过 lint |
| "佣金大概是 15% 吧，你按这个算" | 可以按 15% 算，但结论会标"按你给的 15%，实际以类目后台为准" |
| "欧盟不是都一样吗" | 不一样。VAT 税率、EPR 注册、语言要求都是按国别的，必须具体到国家 |
| "先发一批试试，边卖边补证" | 有阻断项时不给这个绿灯，只给补齐清单与路径 |
| "这个外观有没有侵权" | 判断不了，需要做 FTO 检索；我给你检索范围和要找的人 |

---

## 七、一句话总结

**你说清卖什么、卖到哪、在哪卖；我给你三条保本线、一张放行单、一张带止损的补货表。**
数字有出处，缺的有标注，不合格的不放行。
