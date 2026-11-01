---
name: contract-counsel-toolkit
description: "Local, offline contract workbench built on the Python standard library: no third-party dependencies, no network, and contract text never leaves the machine. Six commands cover the contract lifecycle - draft a purchase, lease or service contract from a structured spec; review an existing .docx/.txt/.md for risk with severity grading and clause-level citations; diff two versions and grade every change by impact; look up the governing article for a legal question with a confidence score; track acceptance and payment milestones in an obligation ledger; convert amounts to Chinese uppercase. Use when the user asks to draft a contract, check whether a contract is safe to sign, see what the counterparty changed, find the article behind a legal claim, or track contract obligations."
---

# Contract Counsel Toolkit（契约守门人工具箱）

合同起草、风险审查、版本比对、法条检索、履约跟踪的本地工具箱。**纯 Python 标准库实现，零第三方依赖，不联网，不上传合同正文。**

## 什么时候用

| 用户意图 | 用哪个命令 | 产出 |
|---|---|---|
| 起草 / 拟一份 / 来份模板 | `draft` | `.docx` 合同 + `.md` 预览 + `.meta.json` |
| 审一下 / 有没有坑 / 能不能签 | `review` | 风险报告 `.md` + 结构化 `.json` |
| 两版差在哪 / 对方改了什么 | `compare` | 变更分级报告 `.md` + `.json` |
| 法律怎么规定 / 哪一条 | `laws` | 条号 + 要点 + 置信度（JSON） |
| 什么时候该验收 / 别忘付款 | `ledger` | 履约台账 JSON + 台账报告 `.md` |
| 金额大写 / 环境自检 | `amount` / `doctor` | JSON |

## 命令速查

脚本入口：`scripts/cc.py`（其余模块由它调用，也可单独 import）。

```bash
# W1 起草
python scripts/cc.py draft --type purchase --a "甲公司" --b "乙公司" \
  --amount 200000 --subject "办公电脑 100 台" --delivery-days 20 --payment-days 30 \
  --stance a --out .contract-workspace

# 用完整 spec（可覆盖/增删条款）
python scripts/cc.py draft --type lease --spec my_spec.json --out .contract-workspace

# W2 审查（支持 .docx / .txt / .md）
python scripts/cc.py review ./合同.docx --type purchase --stance b --out .contract-workspace

# W3 比对（A=原版，B=新版，按传参顺序）
python scripts/cc.py compare ./v1.docx ./v2.docx --out .contract-workspace

# W4 法条索引检索
python scripts/cc.py laws --q 违约金 --limit 5

# W5 台账
python scripts/cc.py ledger import --draft .contract-workspace/xxx.meta.json --start 2026-11-01
python scripts/cc.py ledger list --state open
python scripts/cc.py ledger due --days 15
python scripts/cc.py ledger done --id L0003
python scripts/cc.py ledger report --out .contract-workspace

# 工具
python scripts/cc.py amount 123456.78
python scripts/cc.py doctor
```

`--type` 取值：`purchase`（采购/买卖）、`service`（技术服务）、`lease`（房屋租赁）、`labor`（劳动合同）、`nda`（保密协议）、`loan`（借款）。也认别名：购销、租房、用工、NDA、借贷等。

## 数据文件

| 文件 | 作用 | 改它的场景 |
|---|---|---|
| `references/clause_library.json` | 6 类合同、72 条原创通用条款，含必备要素清单与履约节点提示 | 想固化自家条款口径、加合同类型 |
| `references/risk_rules.json` | 31 条可解释审查规则（5 类检测器 + 等级 + 依据） | 想加行业特有红线、调阈值 |
| `references/law_index.json` | 4 部法律 44 条导航 + 10 个高频场景索引 | 补常用法条、修正置信度 |
| `references/workflows.md` | 五条工作流的完整规格 | 改流程定义 |
| `references/io_spec.md` | 输入 spec 与输出 JSON 的字段规范 | 二次开发对接 |
| `templates/samples/` | 三份样例（含一份故意写坏的租赁合同、一对前后版本） | 演示与回归测试 |

## 输出约定

- 所有命令向 stdout 打印 JSON：成功含 `"ok": true`，失败含 `"ok": false` 与 `"error"`。
- 报告正文写入 `--out` 目录（默认 `.contract-workspace`），文件名带合同类型与日期，便于归档。
- 退出码：0 成功 / 2 参数错误 / 3 文件格式不支持 / 4 文件不存在 / 5 数据或校验错误 / 6 台账编号不存在。

## 异常处理约定

| 情况 | 行为 |
|---|---|
| PDF、图片、.doc | 抛 `UnsupportedFormat`，提示另存为 .docx 或粘贴正文；**不得假装已读** |
| 合同类型识别失败 | 要求用 `--type` 明确指定，并列出可选值 |
| 金额无法解析 | 正文保留原文并在 `used_defaults` 标记，不中断出稿 |
| 必填信息缺失 | 用行业默认值出稿，全部记入 `used_defaults`，交付时逐条提示 |
| 台账文件损坏 | 报错并要求先备份再重建，不做静默覆盖 |
| 规则正则写错 | 单条规则跳过，其余继续（不影响整份审查） |

## 质量红线

1. 起草必须有 `.docx` 产物，只给大纲不算完成。
2. 审查每条结论必须有：位置 + 后果 + 改法；不写“建议完善”这类空话。
3. 引用条文必须来自 `law_index.json` 或官方来源核实；`confidence=verify` 的条号必须提示复核。
4. 不虚构测试结果、不虚构文件路径、不承诺胜诉或合同效力。
5. 不生成规避法律强制性规定、阴阳合同、虚假出资等条款。

## 版本

1.0.0 — 首个版本：五条工作流、6 类合同条款库、31 条审查规则、DOCX 生成器、履约台账。
