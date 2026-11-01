# Mermaid 语法速查

Mermaid 是公开的图表标记语言，其语法属于公共技术规范。本文件按本工具实际用到的子集整理，用于**导出检查**与**跨平台兼容**。

> 本工具的渲染不依赖 Mermaid 解析器，模型才是源。此处只解决两件事：导出的 `.mmd` 能被标准渲染器解析；用户给的 `.mmd` 能被体检。

## 1. 流程图 flowchart

```
flowchart TD
    A["开始"] --> B{"是否通过"}
    B -->|"是"| C["处理"]
    B -->|"否"| D["退回"]
    C --> E(["结束"])
```

方向：`TD`/`TB` 自上而下、`LR` 左右、`BT` 自下而上、`RL` 自右向左。

| 形状 | 写法 |
|---|---|
| 矩形 | `id["文字"]` |
| 圆角 | `id("文字")` |
| 胶囊 | `id(["文字"])` |
| 圆形 | `id(("文字"))` |
| 菱形 | `id{"文字"}` |
| 六边形 | `id{{"文字"}}` |
| 圆柱 | `id[("文字")]` |
| 平行四边形 | `id[/"文字"/]` |
| 子程序 | `id[["文字"]]` |
| 非对称 | `id>"文字"]` |

连线：

| 写法 | 含义 |
|---|---|
| `A --> B` | 实线箭头 |
| `A --- B` | 实线无箭头 |
| `A -.-> B` | 虚线箭头 |
| `A ==> B` | 粗线箭头 |
| `A <--> B` | 双向箭头 |
| `A -->\|"标签"\| B` | 带标签 |

子图：

```
subgraph g1["分组名"]
    A --> B
end
```

样式：

```
classDef cPrimary stroke-width:1.5px
class A,B cPrimary
```

**高频坑**

1. 标签里有 `(` `)` `[` `]` `{` `}` 时必须加引号，否则解析失败。
2. `end` 是保留字，节点 id 不能叫 `end`。
3. `subgraph` 与 `end` 必须成对，嵌套时逐层闭合。
4. 节点 id 不要用中文，用英文 id + 中文标签最稳。

## 2. 时序图 sequenceDiagram

```
sequenceDiagram
    participant C as 客户端
    participant S as 服务端
    C->>S: 请求
    S-->>C: 响应
    Note over C,S: 说明
    loop 每分钟
        C->>S: 心跳
    end
```

| 写法 | 含义 |
|---|---|
| `A->>B: 文本` | 实线实心箭头（同步调用） |
| `A-->>B: 文本` | 虚线箭头（异步 / 返回） |
| `A-)B: 文本` | 开放箭头（异步） |
| `Note over A,B: 文本` | 跨参与者注释 |
| `loop` / `alt` / `opt` / `par` … `end` | 逻辑块 |
| `activate A` / `deactivate A` | 激活条 |

**高频坑**：块必须闭合；`participant` 别名用 `as`；参与者顺序按声明顺序从左到右。

## 3. 类图 classDiagram

```
classDiagram
    class OrderService {
        <<interface>>
        +create(cmd): Order
        -repo: OrderRepository
    }
    OrderServiceImpl ..|> OrderService
    Order *-- OrderItem
```

| 写法 | 含义 |
|---|---|
| `A <\|-- B` | B 继承 A |
| `A *-- B` | 组合 |
| `A o-- B` | 聚合 |
| `A --> B` | 关联 |
| `A ..> B` | 依赖 |
| `+` `-` `#` `~` | public / private / protected / package |

## 4. ER 图 erDiagram

```
erDiagram
    USER ||--o{ ORDER : "下单"
    ORDER {
        bigint id PK
        bigint user_id FK
        decimal amount
    }
```

| 写法 | 基数 |
|---|---|
| `\|\|--\|\|` | 一对一 |
| `\|\|--o{` | 一对多 |
| `}o--o{` | 多对多 |

**高频坑**：属性类型不能带括号，`decimal(12,2)` 要写成 `decimal`；实体名建议全大写。

## 5. 状态图 stateDiagram-v2

```
stateDiagram-v2
    [*] --> 待支付
    待支付 --> 已支付 : 支付成功
    已支付 --> [*]
```

`[*]` 表示起点或终点。状态名含空格时用 `state "名称" as id`。

## 6. 甘特图 gantt

```
gantt
    dateFormat YYYY-MM-DD
    axisFormat %m-%d
    section 开发
    接口开发 : t1, 2026-11-09, 5d
    联调 : t2, after t1, 2d
    上线 : milestone, m1, 2026-11-21, 0d
```

## 7. 思维导图 mindmap

```
mindmap
  root((主题))
    分支一
      子项
    分支二
```

靠缩进表达层级，**不要用 Tab 与空格混排**。

## 8. 时间轴 timeline

```
timeline
    title 关键里程碑
    2026 Q1 : 内测发布 : 50 家客户
    2026 Q2 : 商业化上线
```

## 9. 饼图 pie

```
pie showData
    title 工时分布
    "开发" : 46
    "修复" : 21
```

## 10. 四象限 quadrantChart

```
quadrantChart
    title 需求优先级
    x-axis 低成本 --> 高成本
    y-axis 低价值 --> 高价值
    quadrant-1 谨慎评估
    quadrant-2 优先做
    quadrant-3 顺手做
    quadrant-4 不做
    一键开票: [0.24, 0.82]
```

象限编号约定：`quadrant-1` 右上、`quadrant-2` 左上、`quadrant-3` 左下、`quadrant-4` 右下。

> 注意：本工具的 `quadrants` 数组顺序是 `[左上, 右上, 左下, 右下]`，导出时会自动映射为上面的编号。

## 11. 柱线图 xychart-beta

```
xychart-beta
    title "活跃用户"
    x-axis ["5月", "6月"]
    y-axis "万人" 0 --> 100
    bar [12.4, 15.1]
    line [38.2, 41.5]
```

---

## 语法体检能查出什么

`dg check file.mmd` 做的是**静态结构检查**，不渲染：

- 未识别到图表类型声明
- 括号 / 引号未闭合、括号类型错配
- `subgraph` / `loop` / `alt` 等块与 `end` 不配对
- 空标签节点、箭头缺目标、消息缺内容
- 标签含圆括号但未加引号
- ER 关系行的 `o{` / `}|` 会被正确识别为基数符号而非括号

查不出的是**语义问题**（画得对不对），那需要人来判断。
