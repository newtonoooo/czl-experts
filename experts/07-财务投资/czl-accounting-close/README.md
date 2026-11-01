# 账衡（czl-accounting-close）

> 账务结账与报表专家 · WorkBuddy 专家包 · v1.0.0
> 开发者：虫志龙 · 47190078@qq.com

一个按「接单 → 做平 → 校表 → 归档」四段闭环工作的中文账务专家。默认中国企业会计准则（CAS），需要时切换 IFRS / US GAAP 并只标差异点。核心计算与校验由随包的 `ledgerkit.py` 执行，纯 Python 标准库、无第三方依赖、结果可复现。

## 它解决的问题

月末结账那几天，真正耗时的是四件事：数据缺项来回问、凭证借贷不平、账面对不上、报表勾稽不过。这四件事都不是"懂准则"能解决的，要么靠规则，要么靠算。这个专家包把规则和算术都落成了可执行的东西。

- **接单门禁**：六要素任务单 + 缺件清单，缺什么、缺了会怎样，开工前说清。
- **三平校验**：凭证平、账账平、账实平，不达标不出结论。
- **五条勾稽**：三表之间必须全部对上，一条不成立就不发布。
- **风险分级**：R0 红线 / R1 关注 / R2 常规，R0 未清不许结账。
- **差异说人话**：把波动拆到价格、数量、结构，解释必须带数字、可被推翻。

## 安装

把 `czl-accounting-close/` 整个目录放到 WorkBuddy 专家目录下：

```
<WORKBUDDY_CONFIG_DIR>/plugins/marketplaces/my-experts/plugins/czl-accounting-close/
```

在 WorkBuddy 中运行注册，使其出现在【专家中心 - 我的专家】：

```bash
python scripts/register_expert.py <expert-dir>
```

或直接使用发布包 `czl-accounting-close.zip` 在平台导入。

## 三分钟上手

直接说话就行，不需要记命令：

- 「9 月要结账了，帮我排顺序，缺什么数据列给我。」→ 走 W1 接单 + W6 排程
- 「这笔业务怎么做分录：9 月一次付了 12 个月房租 24 万，专票，税率 9%。」→ 走 W2 分录
- 「银行账面对不上，账面 117.4 万，对账单 120 万。」→ 走 W3 对账
- 「帮我出三大表并检查勾稽。」→ 走 W4 报表
- 「9 月收入比 8 月多 15%，拆一下主因。」→ 走 W5 差异
- 「审计下周进场，帮我准备资料。」→ 走 W6 审计交接

## 随包工具 ledgerkit

```bash
python bin/ledgerkit.py list                # 列出全部命令
python bin/ledgerkit.py selftest            # 内置自检（8 个用例）
python bin/ledgerkit.py entry-check -f 分录批次.json
python bin/ledgerkit.py rollforward -f 滚算.json
python bin/ledgerkit.py bank-rec   -f 调节.json
python bin/ledgerkit.py depreciation -f 折旧.json
python bin/ledgerkit.py amortize   -f 摊销.json
python bin/ledgerkit.py variance   -f 差异.json
python bin/ledgerkit.py tieout     -f 三表.json
python bin/ledgerkit.py materiality -f 重要性.json
```

每个命令都支持 `--json`（机器可读）和 `--out 路径`（写入底稿留痕）。
退出码：`0` 通过 / `1` 有阻断问题 / `2` 输入非法。

样例输入在 `bin/samples/`，可以先跑样例看输出长什么样。

## 目录结构

```
czl-accounting-close/
├── .codebuddy-plugin/plugin.json   专家元数据
├── agents/czl-accounting-close.md  主提示词（工作法、硬规矩、边界）
├── skills/                         六个工作流
│   ├── close-intake/               接单、任务单、缺件、风险分级
│   ├── journal-builder/            分录、价税分离、折旧摊销
│   ├── recon-balance/              对账、余额调节、四柱滚算
│   ├── statement-tieout/           三表、五条勾稽、列报
│   ├── variance-drill/             差异分解、说明规范
│   └── close-runbook/              结账日历、审计交接
├── bin/ledgerkit.py                计算与校验工具
├── bin/samples/                    样例输入
├── avatars/expert.png              头像 512×512
├── docs/                           规格、说明、清单、测试、风险
├── README.md  CHANGELOG.md  LICENSE
```

## 边界

- 不替代执业注册会计师、税务师；不出审计结论，不代客户签字。
- 不做两套账，不提供规避监管的处理方式。
- 涉及舞弊迹象只做提示并建议内部核查，不参与掩盖。
- 涉税定性（税率适用、优惠、跨境）给判断要点，不给结论。

## 版本

v1.0.0（2026-10-27）首个公开发布版。变更记录见 `CHANGELOG.md`，完整文档见 `docs/`。
