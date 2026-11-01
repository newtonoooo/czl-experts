# draft.json 数据结构

渲染器 `scripts/arreport.py` 的唯一输入。HTML 与 Markdown 由同一份 draft 生成，因此两份文件内容必然一致。

## 最小示例

```json
{
  "code": "600519.SH",
  "name": "贵州茅台",
  "task": "diagnosis",
  "date": "2026-10-29",
  "data_as_of": "2026-10-29",
  "title": "贵州茅台（600519.SH）个股诊断",
  "verdict": {
    "text": "生意质量高但增速已换挡，当前价隐含假设偏乐观。",
    "confidence": "中",
    "falsify": "若下一季度预收款同比转负且批价跌破 2000 元，本判断失效。"
  },
  "key_numbers": [
    {"label": "收盘价", "value": "1349.47", "note": "元，2026-10-29"},
    {"label": "涨跌幅", "value": "+1.41", "note": "%"},
    {"label": "PE-TTM 分位", "value": "62", "note": "%（近5年）"}
  ],
  "series": {"close": [1300, 1310, 1290, 1320, 1330, 1349.47],
             "caption": "收盘价走势（最近 6 个交易日）"},
  "sections": [
    {"title": "证据", "md": "### 财务\n- 前三季度营收 1234.5 亿元[事实]\n\n| 指标 | 数值 |\n|---|---|\n| 毛利率 | 91.2% |"},
    {"title": "分歧", "md": "..."},
    {"title": "定价", "md": "..."},
    {"title": "情景", "md": "..."},
    {"title": "风险", "md": "..."}
  ],
  "sources": [
    {"id": "S1", "name": "新浪财经 hq.sinajs.cn", "as_of": "2026-10-29 10:43", "quality": "primary"},
    {"id": "S2", "name": "公司三季报", "as_of": "2026-09-30", "quality": "primary"}
  ]
}
```

## 字段说明

| 字段 | 必填 | 说明 |
|---|---|---|
| `code` | 是 | `600519.SH` 形式 |
| `name` | 是 | 证券简称 |
| `task` | 是 | `diagnosis` / `valuation` / `tape` / `feature` / `portfolio` |
| `date` | 否 | 报告日期，缺省取当天 |
| `data_as_of` | 否 | 数据截至日期，缺省同 `date`。**与 `date` 不同时必须填**，否则闸门 A5 会拦 |
| `title` | 否 | 缺省自动拼 |
| `verdict` | 是 | `text` 判断、`confidence` 高/中/低、`falsify` 证伪条件 |
| `key_numbers` | 否 | 顶部指标卡，建议 3-6 个；`value` 以 `+`/`-` 开头时自动着色 |
| `series.close` | 否 | 收盘价序列，用于内联 SVG 走势图；≥2 个点才渲染 |
| `sections` | 是 | 章节列表，`title` + `md`。**结论段不要放进 sections**，它由 `verdict` 自动生成 |
| `sources` | 是 | 来源表；闸门 A4 会用台账核对数字 |
| `disclaimer` | 否 | 缺省用固定文本；不建议自定义 |

## sections 的 Markdown 子集

渲染器只支持以下语法，超出部分按普通段落输出，不会报错但会丢格式：

- `#` `##` `###` 标题（会降一级嵌入，因为报告标题已是 h1）
- `- ` 无序列表、`1. ` 有序列表
- `| a | b |` 表格，第二行 `|---|` 为分隔行
- `> ` 引用块
- `**粗体**`、`*斜体*`、`` `代码` ``
- 空行分段

## 与闸门的配合

- `verdict.falsify` 为空 → 人工检查 B1 不通过。
- `sources` 为空或台账对不上 → A4 匹配率下降，可能打回。
- `data_as_of` 早于今天却在正文写"今日" → A5 打回。
- 派生数字（区间上下限、增速）也要以 `estimated` 条目登记进台账，否则 A4 会把它们算作无出处。
