# 图表模型规范（model.json）

模型是本工具的唯一事实来源。所有输出格式都由模型派生，改图就是改模型。

## 通用字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `kind` | string | ✅ | 图表类型，见下表 |
| `title` | string | | 标题，绘制在左上角 |
| `subtitle` | string | | 副标题，一句话说明这张图回答什么问题 |
| `direction` | string | | `TB` / `LR` / `BT` / `RL`；不填则由引擎按结构自动选择 |
| `theme` | string | | 主题名，可被命令行 `--theme` 覆盖 |
| `footnote` | string | | 脚注，用于放口径说明、假设、图例补充 |

`kind` 取值：`flow` `state` `class` `er` `sequence` `gantt` `mindmap` `timeline` `pie` `quadrant` `xy`

## 角色（role）与语义配色

| role | 含义 | 典型用法 |
|---|---|---|
| `primary` | 主流程 / 主体 | 默认值 |
| `decision` | 判断 / 分支点 | 菱形节点 |
| `data` | 数据 / 存储 | 数据库、报文、中间结果 |
| `external` | 外部系统 | 第三方接口、外部平台 |
| `success` | 正常终点 | 成功结束、完成态 |
| `danger` | 异常分支 | 失败、退回、告警 |
| `neutral` | 中性 / 其他 | 起止符、说明节点 |

## 节点形状（shape）

`rect` 矩形 · `round` 圆角 · `stadium` 胶囊 · `circle` 圆形 · `diamond` 菱形 · `hex` 六边形 · `cylinder` 圆柱 · `parallelogram` 平行四边形 · `subroutine` 子程序 · `note` 便签

---

## flow / state

```json
{
  "kind": "flow",
  "title": "费用报销审批",
  "nodes": [
    { "id": "start", "label": "发起报销", "shape": "stadium", "role": "primary" },
    { "id": "check", "label": "金额是否超 5000 元", "shape": "diamond", "role": "decision" }
  ],
  "edges": [
    { "from": "start", "to": "check", "label": "" }
  ],
  "groups": [
    { "id": "emp", "label": "员工端", "members": ["start", "check"] }
  ]
}
```

| 字段 | 说明 |
|---|---|
| `nodes[].id` | 唯一，建议语义化英文（`submit`、`order_service`） |
| `nodes[].label` | 显示文字，建议 ≤ 12 字 |
| `nodes[].note` | 节点下方的补充说明（小字） |
| `nodes[].emphasis` | `true` 时节点使用实心强调色 |
| `edges[].style` | `solid`（默认）/ `dashed`（异常或回退）/ `thick`（主路径强调） |
| `edges[].arrow` | `end`（默认）/ `both` / `none` / `open` |
| `groups[].members` | 节点 id 数组；一个节点只归属第一个分组 |

`state` 与 `flow` 结构完全相同，默认形状为圆角，适合状态机。起止状态建议用 `circle`。

## class

```json
{
  "kind": "class",
  "classes": [
    {
      "id": "orderService",
      "name": "OrderService",
      "stereotype": "interface",
      "role": "data",
      "members": [
        { "text": "+ create(cmd): Order", "kind": "method" },
        { "text": "- repo: OrderRepository", "kind": "field" }
      ]
    }
  ],
  "relations": [
    { "from": "impl", "to": "orderService", "kind": "inherit" }
  ]
}
```

`relations[].kind`：`inherit` 继承 · `compose` 组合 · `aggregate` 聚合 · `assoc` 关联 · `depend` 依赖

可选 `fromCard` / `toCard` 标注基数（如 `1`、`0..*`）。

## er

```json
{
  "kind": "er",
  "entities": [
    {
      "id": "order",
      "name": "订单 order",
      "role": "data",
      "attributes": [
        { "name": "id", "type": "bigint", "key": "pk" },
        { "name": "user_id", "type": "bigint", "key": "fk" },
        { "name": "amount", "type": "decimal(12,2)" }
      ]
    }
  ],
  "relations": [
    { "from": "user", "to": "order", "card": "1-n", "label": "下单" }
  ]
}
```

`key`：`pk` 主键 / `fk` 外键 / 留空为普通字段。`card`：`1-1` / `1-n` / `n-n`。

## sequence

```json
{
  "kind": "sequence",
  "participants": [
    { "id": "client", "label": "客户端", "kind": "actor", "role": "primary" },
    { "id": "db", "label": "订单库", "kind": "db" }
  ],
  "steps": [
    { "type": "message", "from": "client", "to": "gw", "text": "POST /orders" },
    { "type": "message", "from": "gw", "to": "client", "text": "201 Created", "style": "return" },
    { "type": "note", "over": ["gw", "db"], "text": "同一事务内更新" },
    { "type": "fragment", "frag": "alt", "label": "成功 / 超时" },
    { "type": "message", "from": "a", "to": "b", "text": "..." },
    { "type": "end" }
  ]
}
```

- `participants[].kind`：`actor` / `service` / `db` / `queue` / `external`（仅影响角标文案）
- `steps[].style`：`sync`（实线实心箭头）/ `async`（细线开放箭头）/ `return`（虚线开放箭头）
- `fragment.frag`：`loop` / `alt` / `opt` / `par`；**不支持嵌套**，必须用 `{ "type": "end" }` 闭合

## gantt

```json
{
  "kind": "gantt",
  "sections": [
    {
      "name": "开发",
      "tasks": [
        { "name": "接口开发", "start": "2026-11-09", "duration": 5, "owner": "后端" },
        { "name": "联调", "start": "2026-11-16", "duration": 2, "critical": true },
        { "name": "上线", "start": "2026-11-21", "milestone": true }
      ]
    }
  ]
}
```

- `start` 支持 `YYYY-MM-DD` 或数字偏移（第 N 天）
- `duration` 单位天；`milestone: true` 时画菱形，忽略工期
- `critical: true` 用警示色标出关键路径
- 也可省略 `sections`，直接给顶层 `tasks` 数组

## mindmap

```json
{
  "kind": "mindmap",
  "root": {
    "label": "数据平台",
    "children": [
      { "label": "数据接入", "children": [{ "label": "业务库 CDC" }] }
    ]
  }
}
```

层级建议 ≤ 4 层、节点 ≤ 45 个。`note` 会显示在节点右侧。

## timeline

```json
{
  "kind": "timeline",
  "events": [
    { "date": "2026 Q1", "label": "内测版发布", "detail": "50 家种子客户" }
  ]
}
```

事件会上下交错排布；超过 10 个会拥挤，建议合并同类项。

## pie

```json
{ "kind": "pie", "slices": [{ "label": "新功能开发", "value": 46 }] }
```

`value` 必须为正数。占比 <3% 的扇区在图上几乎不可见，建议合并为「其他」。

## quadrant

```json
{
  "kind": "quadrant",
  "xAxis": { "low": "低成本", "high": "高成本" },
  "yAxis": { "low": "低价值", "high": "高价值" },
  "quadrants": ["优先做", "谨慎评估", "顺手做", "不做"],
  "points": [{ "label": "一键开票", "x": 0.24, "y": 0.82 }]
}
```

- `x` / `y` 取值 `0~1`，左下角为 `(0,0)`
- **`quadrants` 顺序固定为 `[左上, 右上, 左下, 右下]`**

## xy

```json
{
  "kind": "xy",
  "unit": "万人",
  "xLabels": ["5月", "6月"],
  "series": [
    { "name": "新增用户", "type": "bar", "values": [12.4, 15.1] },
    { "name": "月活用户", "type": "line", "values": [38.2, 41.5] }
  ]
}
```

- `values` 长度必须等于 `xLabels` 长度
- `type`：`bar` / `line` / `area`
- 系列建议 ≤ 4 条

---

## 校验规则速查

`dg check` 会拦下的错误：

- `kind` 不在 11 种之内
- 节点 / 实体 / 参与者 / 类 `id` 缺失或重复
- 边引用了不存在的 id（悬空边）
- 分组 id 与节点 id 冲突，或分组内引用不存在的节点
- `sequence` 的 `fragment` 未闭合或嵌套
- `xy` 的 `values` 与 `xLabels` 长度不一致
- `gantt` 的 `start` 既不是日期也不是数字
- `pie` 的 `value` 非正数

只给警告不拦下的：节点过多、标签过长、孤立节点、占比过小、层级过深等——这些由 `dg review` 计分。
