# 输入输出规范（IO Spec v1.0）

本规范定义 W1 起草的输入 spec 与各工作流的输出结构。二次开发或对接自动化时以本文件为准。

## 一、起草输入：`spec.json`

```json
{
  "title": "采购合同",
  "file_stem": "purchase_20261101",
  "values": {
    "a_name": "成都甲科技有限公司",
    "b_name": "成都乙商贸有限公司",
    "a_addr": "成都市高新区…",
    "a_legal": "张三",
    "a_contact": "138****0000",
    "b_name": "…",
    "amount": 200000,
    "subject": "办公电脑 100 台",
    "stance": "a",
    "start_date": "2026-11-01",
    "delivery_days": 20,
    "payment_days": 30,
    "acceptance_days": 7,
    "warranty_months": 12,
    "contract_no": "CG-2026-018",
    "sign_place": "成都市高新区"
  },
  "clauses_exclude": ["P09"],
  "clauses_override": {
    "P10": "10.1 乙方逾期交货的，每逾期一日按合同总价的 0.03% 支付违约金……",
    "争议解决": "14.1 ……（按条标题覆盖亦可）"
  },
  "clauses_add": [
    { "title": "数据合规", "body": "16.1 乙方处理甲方数据应遵守……" }
  ]
}
```

### `values` 字段表

| 字段 | 类型 | 适用类型 | 说明 |
|---|---|---|---|
| `a_name` / `b_name` | string | 全部 | 主体全称 |
| `role_a` / `role_b` | string | 全部 | 角色标注，默认"甲方（采购方）/乙方（供货方）"等 |
| `a_addr` `a_id` `a_legal` `a_contact` `a_account` | string | 全部 | 住所地 / 统一社会信用代码 / 负责人 / 联系人电话 / 收款账户 |
| `amount` | number | 采购 服务 租赁 借款 劳动 | 金额；劳动合同时为月工资 |
| `subject` | string | 全部 | 标的/服务范围/房屋/保密事项 |
| `stance` | `a` `b` `neutral` | 全部 | 决定管辖地写法 |
| `start_date` | `YYYY-MM-DD` | 全部 | 起始日，默认今天 |
| `term_months` | int | 租赁 劳动 借款 | 期限（月） |
| `payment_days` | int | 采购 服务 | 验收后付款天数 |
| `delivery_days` | int | 采购 服务 | 交付/服务天数 |
| `acceptance_days` | int | 采购 服务 | 验收工作日 |
| `warranty_months` | int | 采购 服务 | 质保月数 |
| `penalty_rate` | number | 全部 | 日违约金百分比，默认 0.05（即日万分之五） |
| `deposit_months` / `deposit` | int / number | 租赁 | 押金月数 / 押金金额 |
| `pay_cycle` | string | 租赁 | 付租周期，如"每三个月" |
| `fee_bearer` | string | 租赁 | 水电物业费承担方，如"乙方" |
| `address` `area` `cert_no` | string | 租赁 | 房屋坐落 / 面积 / 权属证号 |
| `job_title` `work_place` `work_system` `welfare` | string | 劳动 | 岗位 / 地点 / 工时制 / 福利 |
| `probation_months` `probation_salary` | int | 劳动 | 试用期月数与工资 |
| `purpose` `repay_method` `guarantee` `rate` | string/number | 借款 | 用途 / 还款方式 / 担保 / 年利率 |

> 未提供的字段一律走类型默认值，并在输出的 `used_defaults` 中逐条披露，不静默留白。

## 二、起草输出：三方产物

| 文件 | 说明 |
|---|---|
| `<stem>.docx` | 合同正文，A4、宋体小四、1.5 倍行距、首行缩进 2 字符 |
| `<stem>.md` | 同内容 Markdown 预览，便于快速核对 |
| `<stem>.meta.json` | 结构化元数据，供 W5 与二次开发使用 |

`meta.json` 关键字段：

```json
{
  "ok": true,
  "type": "purchase",
  "type_label": "采购合同",
  "docx": "/abs/path/xxx.docx",
  "markdown": "/abs/path/xxx.md",
  "clause_count": 15,
  "placeholders": { "amount": "200,000", "amount_cn": "人民币贰拾万元整", "...": "..." },
  "used_defaults": { "payment_days": 30, "court": "甲方所在地" },
  "missing_placeholders": [],
  "ledger_hints": [{ "item": "交货完成", "obligor": "乙方", "offset_days": 30 }],
  "verify": { "ok": true, "paragraphs": 89, "tables": 1, "parts": ["..."] }
}
```

## 三、审查输出

```json
{
  "ok": true,
  "type": "lease",
  "type_label": "房屋租赁合同",
  "stance": "b",
  "clause_count": 9,
  "score": 17,
  "verdict": "不建议按现文本签署",
  "counts": { "high": 5, "mid": 7, "low": 2 },
  "coverage": [{ "key": "deposit", "label": "押金及退还", "covered": true, "keywords": ["押金"] }],
  "missing_elements": [{ "key": "repair", "label": "维修义务", "covered": false, "keywords": ["维修"] }],
  "findings": [
    {
      "rule_id": "R-002",
      "name": "按日违约金比例明显偏高",
      "level": "high",
      "clause": "第三条",
      "clause_index": 3,
      "clause_title": "租金及支付",
      "evidence": "…每逾期一日按当期应付租金的 1% 支付违约金。",
      "why": "按日 0.5% 折年化约 182%……",
      "fix": "改为每日万分之五（0.05%）左右，并设累计上限……",
      "basis": { "law": "民法典", "article": "第585条", "gist": "……", "confidence": "high" }
    }
  ]
}
```

字段约束：

- `level` ∈ `high` / `mid` / `low`；`score` ∈ 0–100 整数；`verdict` 为四档固定表述之一。
- `clause` 为条号或 `—`（全文类问题）；`clause_index` 用于排序，全文类为 999。
- `basis.confidence = "verify"` 时，交付必须提示"条号请复核"。

## 四、比对输出

```json
{
  "ok": true,
  "align_mode": "按条号对齐",
  "clause_count": { "a": 8, "b": 9 },
  "stats": { "added": 1, "removed": 0, "major": 7, "normal": 1, "minor": 0, "unchanged": 1 },
  "changes": [
    {
      "kind": "修改",
      "level": "major",
      "clause": "第五条",
      "title": "违约责任",
      "before": "…0.05%…",
      "after": "…0.02%…0.1%…",
      "similarity": 0.86,
      "numbers": { "added": ["0.02%", "0.1%"], "removed": ["0.05%"] },
      "impact": "新增数值：0.02%、0.1%；删除数值：0.05%"
    }
  ],
  "negotiation": [{ "clause": "第五条", "topic": "违约责任", "issue": "…", "suggestion": "…" }]
}
```

`kind` ∈ `新增` / `删除` / `修改`；`level` ∈ `major` / `normal` / `minor`。

## 五、履约台账

`ledger.json`：

```json
{
  "meta": { "version": "1.0.0", "created": "2026-10-26" },
  "entries": [
    {
      "id": "L0001",
      "contract": "采购合同",
      "item": "交货完成",
      "obligor": "乙方",
      "due": "2026-11-25",
      "note": "",
      "status": "open",
      "created": "2026-10-26",
      "days_left": 30,
      "state": "正常"
    }
  ]
}
```

`status` ∈ `open` / `done`；`state` 由程序实时计算：`正常` / `临近（N 天）` / `逾期 N 天` / `已完成` / `无截止日`。

## 六、法条索引检索输出

```json
{
  "ok": true,
  "query": "违约金",
  "count": 2,
  "results": [
    { "law": "民法典", "article": "第585条", "topic": "违约金", "gist": "……", "use": "违约金比例是否过高", "confidence": "high" }
  ],
  "note": "条目为要点摘录，引用原文前请核对 国家法律法规数据库、最高人民法院、中国政府网政策文件库"
}
```

## 七、错误输出

```json
{ "ok": false, "error": "暂不支持直接解析 .pdf 文件（本产品不带 PDF/OCR 依赖）。请用 Word/WPS 另存为 .docx，或把合同正文粘贴给我。", "hint": "请另存为 .docx 或粘贴文本" }
```

退出码：0 成功｜2 参数错误｜3 格式不支持｜4 文件不存在｜5 数据或校验错误｜6 台账编号不存在。
