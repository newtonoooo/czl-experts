---
name: landing-kit
description: "Working kit for taking one SKU from a Chinese factory to a foreign marketplace. Six stage playbooks (intake, market screen, landed cost, compliance release, listing build, cold-start and replenishment), each with inputs, steps, pass conditions, output file, failure handling and neighbours. Four standard-library calculators: landed_cost.py models per-kept-order economics with return dilution and returns breakeven price, breakeven ACOS, breakeven daily volume and sensitivity; compliance_gate.py joins market base requirements with category requirements and returns GO, CONDITIONAL or BLOCKED with named blocking items; listing_lint.py enforces per-marketplace title limits, banned claims, keyword stuffing, all-caps and off-platform contact rules; replenish_plan.py returns reorder point, stockout date, sea-air split, cash locked and latest order date. Reference tables cover cost definitions, the compliance matrix by market, listing structure and localisation, and ad launch with stop-loss rules. Load one playbook at a time instead of the whole kit."
version: 1.0.0
---

# 出海落地套件（landing-kit）

> 这不是行业知识库，是**施工图 + 量具**：六道工序怎么走，四个脚本怎么量。
> 读法：按当前卡在哪道门，只取那一份工序文件，不要一次全读。

---

## 一、套件目录

```
landing-kit/
├── SKILL.md                       # 本文件：总纲、工序速查、阈值、纪律
├── workflows/                     # 六道工序（按需取一份）
│   ├── 01-立项.md
│   ├── 02-选品.md
│   ├── 03-成本.md
│   ├── 04-合规.md
│   ├── 05-页面.md
│   └── 06-冷启补货.md
├── references/
│   ├── cost-lines.md              # 成本科目口径、公式、常见口径错误
│   ├── compliance-matrix.md       # 品类 × 市场矩阵、办理路径、常见误解
│   ├── compliance-rules.json      # 机读规则（compliance_gate.py 读取）
│   ├── listing-rules.md           # 标题/五点/描述结构与本地化
│   ├── listing-profiles.json      # 机读平台档案（listing_lint.py 读取）
│   └── launch-and-replenish.md    # 广告四层结构与补货模型
└── scripts/
    ├── landed_cost.py
    ├── compliance_gate.py
    ├── listing_lint.py
    ├── replenish_plan.py
    └── fixtures/                  # 三个可直接跑的样例输入
        ├── cup_us.json
        ├── chair_de.json
        ├── listing_bad.json
        └── replenish_case.json
```

---

## 二、六道工序速查

| 工序 | 一句话职责 | 产出文件 | 卡住的条件 |
|---|---|---|---|
| ① 立项 | 把口语需求压成一张能开工的卡 | `立项卡-{产品}-{日期}.md` | 成本口径 / 目的国 / 卖家身份 三不清 |
| ② 选品 | 判断进、换切口还是不进 | `选品判定-{产品}-{日期}.md` | 四条判据有两条无数据来源 |
| ③ 成本 | 算到每成交一单，出三条保本线 | `成本定价-{产品}-{日期}.md` | 缺 ≥3 个关键费率；净利率 <10% 仍被要求"给个能做"的结论 |
| ④ 合规 | 品类 × 国别出三态放行单 | `合规放行单-{产品}-{市场}-{日期}.md` | 有阻断项且无办理路径 |
| ⑤ 页面 | 出可审的文案底稿并过体检 | `Listing-{产品}-{平台}-{日期}.md` | lint 有 error；未标母语审校点 |
| ⑥ 冷启补货 | 投放带止损线，补货带断货日 | `冷启补货-{产品}-{日期}.md` | 没有止损条件；首单一次铺满 |

**单向依赖**：①→②→③→④→⑤→⑥。允许跳步（单点提问），但跳了必须在交付里写明"未做前置，本结论以此为限"。

---

## 三、判定阈值（写死，不临场商量）

| 项目 | 阈值 | 出处 |
|---|---|---|
| 月搜索量下限 | 3,000 | `workflows/02-选品.md` |
| 首页评论数中位数上限 | 800 | 同上 |
| 价格带下限 | 到岸成本的 3 倍 | 同上 |
| 净利率警戒线 | 15% | `agents/czl-crossborder-landing-pro.md` 第二节 |
| 净利率否决线 | 10%（低于此不给"可以做"） | 同上 |
| 合规阻断项容忍度 | 0（有则 BLOCKED） | `workflows/04-合规.md` |
| Listing error 容忍度 | 0 | `workflows/05-页面.md` |
| 首单覆盖天数 | 30–45 天（试水），跑通后 60–90 天 | `workflows/06-冷启补货.md` |
| 安全库存天数 | 21 天起，旺季 +7～14 天 | 同上 |
| 广告 ACOS 止损 | 连续 7 天 > 保本 ACOS → 降价或关停 | 同上 |

---

## 四、四个脚本

```bash
python scripts/landed_cost.py --input fixtures/cup_us.json
python scripts/compliance_gate.py --category baby --market DE --market FR --have EU-RP
python scripts/listing_lint.py --profile amazon_us --input fixtures/listing_bad.json
python scripts/replenish_plan.py --input fixtures/replenish_case.json
```

| 脚本 | 退出码含义 | 必看输出 |
|---|---|---|
| `landed_cost.py` | 0 正常 / 2 参数错 | 落地成本、保本价、保本 ACOS、阶梯判定 |
| `compliance_gate.py` | 0 正常 / 2 参数错 | 总判定 GO / CONDITIONAL / BLOCKED |
| `listing_lint.py` | 0 无 error（可交付）/ 1 有 error | error 条数与改法 |
| `replenish_plan.py` | 0 正常 / 2 参数错 | 补货点、最晚下单日、海空切分、占用资金 |

四个脚本都支持 `--selftest`（各 7 项断言）与 `--json`。规则数据在 `references/*.json`，可以按自己类目维护，改完重跑即可。

---

## 五、使用纪律

1. **先取工序，再取参考。** 卡在成本就只看 `workflows/03-成本.md` + `references/cost-lines.md`，不翻整本套件。
2. **脚本优先于口算。** 任何出现在交付里的成本、保本线、补货量，都要能追溯到一次脚本运行。
3. **缺参数标 `[待填]`，不许填默认值假装算过。** 脚本的费率默认是 0，不是 15%。
4. **规则带日期。** 引用任何平台费率或字数上限，写明"取数日期"，超过 6 个月先复核。
5. **合规定位是清单，不是法律意见。** 涉及税务申报、产品责任、专利有效性，一律建议转持牌方。
6. **改了 JSON 就重跑。** `compliance-rules.json` 与 `listing-profiles.json` 是数据不是文档，改完必须重跑验证。

---

## 六、维护

- 平台费率、字数上限、禁售清单：每季度核对一次，改动记在 `references/*.json` 的 `meta.as_of`。
- 新增市场：在 `market_family` 加映射，在 `family_base` 加该国基础项，跑 `compliance_gate.py --list` 确认被识别。
- 新增平台：在 `listing-profiles.json` 加档案，先跑 `--list` 再跑一次样例，确认字数与禁词生效。
- 脚本改动后必须 `--selftest` 全绿才能用；断言不过就是模型错了，不许改断言迁就结果。
