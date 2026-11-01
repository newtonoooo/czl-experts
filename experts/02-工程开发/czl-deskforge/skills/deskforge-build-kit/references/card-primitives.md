# 五种卡片 · 参数、结构与画法

> 所有模块都由这五种原语拼出来。参数调对，就不需要第六种卡。

---

## 通用约定

- 每块卡片外层：`<section class="card" data-module="n">`，`data-module` 用于体检脚本计数。
- 卡片内部三段：`<header>`（标题 + 一个主操作）、`<div class="body">`、`<footer>`（可选，放合计/说明）。
- 空状态必须有：`<div class="empty">还没有记录 + 一个主操作按钮</div>`。
- 卡片之间不共享 DOM，只共享数据层。

---

## 一、清单卡 `list`

| 参数 | 取值 | 说明 |
|---|---|---|
| `statusEnum` | 数组，如 `["todo","doing","done"]` | 决定状态色与切换顺序 |
| `sortKey` | 字段名 + 方向 | 常见：`done↑ priority↑ due↑` |
| `checkable` | 布尔 | 是否可一键勾完成 |
| `groupBy` | 字段名或 `null` | 需要"今天/逾期"两条泳道时用 |
| `rowActions` | `["done","edit","del"]` | 行内操作，最多 3 个 |

**数据结构**

```js
{ id:"t_1758361200_81", title:"整理错题本", due:"2026-10-25", done:false, priority:"P0" }
```

**HTML 骨架**

```html
<section class="card" data-module="1">
  <header><h2>今日待办</h2><button class="btn primary" data-act="add">加一条</button></header>
  <div class="body" id="m1-body"></div>
</section>
```

**渲染要点**

```js
function renderM1(){
  const rows = state.tasks;
  const box = document.getElementById('m1-body');
  if(!rows.length){ box.innerHTML = emptyHTML('还没有待办','加一条'); return; }
  box.innerHTML = rows.map(t => `
    <div class="row ${t.done?'is-done':''} ${isOverdue(t)?'is-late':''}">
      <button class="tick" data-act="toggle" data-id="${t.id}" aria-label="完成"></button>
      <span class="t">${esc(t.title)}</span>
      <span class="d">${fmtDate(t.due)}</span>
    </div>`).join('');
}
```

**易错点**：`title` 必须转义（用户可能粘进来 `<script>`）；逾期判定要和"今天"同源，不要各算各的。

---

## 二、矩阵卡 `matrix`

| 参数 | 取值 | 说明 |
|---|---|---|
| `rows` | 稳定集合（习惯、科目、技能） | 会每天新增的维度不要放行 |
| `cols` | 时间粒度：日 / 周 | 日一般显示 7–30 列 |
| `valueFn` | `(row, col) => number` | 0/1 或累计值 |
| `levels` | 色阶阈值数组 | 如 `[0,1,3,5]` |

**渲染要点**

```js
const cell = v => `<span class="cell" data-lv="${lvOf(v)}" title="${v}"></span>`;
// 色阶用 CSS 变量控制，不要在 JS 里拼颜色字符串
```

```css
.cell{width:18px;height:18px;border-radius:4px;background:var(--l0)}
.cell[data-lv="1"]{background:var(--l1)}
.cell[data-lv="2"]{background:var(--l2)}
.cell[data-lv="3"]{background:var(--l3)}
```

**易错点**：列数多时 `18px` 会溢出窄屏，必须允许横向滚动**容器内部**，页面整体不许横滚。

---

## 三、表单卡 `form`

| 参数 | 取值 | 说明 |
|---|---|---|
| `fields` | 字段数组（名/类型/校验/默认） | 类型映射到 `<input type>` |
| `submitTo` | 目标实体 | 提交后落到哪张表 |
| `afterSubmit` | `clear` / `keep` | 连续录入用 `keep` |

**渲染要点**

```html
<form class="f" id="m3-form">
  <label>金额<input type="number" inputmode="decimal" step="0.01" name="amount" required></label>
  <label>分类<select name="cat">…</select></label>
  <button class="btn primary" type="submit">记一笔</button>
</form>
```

- 数字用 `type="number"` 或 `inputmode="decimal"`（唤起数字键盘）。
- 校验只在提交时做，不要边输边骂人。
- 提交成功后给一行轻提示（"已记 12.50 元"），不要弹窗。

**易错点**：`font-size` 小于 16px 时 iOS 会自动放大整页；`select` 也要设 16px。

---

## 四、指标卡 `metric`

| 参数 | 取值 | 说明 |
|---|---|---|
| `kpi` | `sum` / `count` / `avg7` / `ratio` | **必须写清口径** |
| `display` | `ring` / `bar` / `line` | 图形类型 |
| `target` | 数值或 `null` | 有目标才画进度环，否则只显示数字 |
| `compare` | `prevPeriod` / `null` | 环比时写明对比区间 |

**环（进度）画法**

```html
<svg viewBox="0 0 120 120" class="ring">
  <circle cx="60" cy="60" r="52" class="track"/>
  <circle cx="60" cy="60" r="52" class="bar"
          stroke-dasharray="326.7" stroke-dashoffset="326.7"/>
</svg>
```

```js
// r=52 → 周长 2πr ≈ 326.7；进度 p（0–1）
bar.setAttribute('stroke-dashoffset', (326.7 * (1 - p)).toFixed(1));
```

**折线画法**

```js
const pts = data.map((v,i)=>`${i*step},${H - v/max*H}`).join(' ');
polyline.setAttribute('points', pts);
```

**易错点**：除以 0（数据全 0 时 `max=0`）；口径写成"完成率"却没说是按条数还是按权重。

---

## 五、时间卡 `time`

| 参数 | 取值 | 说明 |
|---|---|---|
| `mode` | `countdown` / `calendar` / `bucket` | 倒计时 / 日历格 / 今天本周分组 |
| `anchor` | 目标日期或起始日 | 倒计时用目标日，日历用当月 |
| `carryOver` | 布尔 | 未完成是否自动滚到今天 |
| `granularity` | `day` / `week` | 分组粒度 |

**倒计时要点**

```js
const days = Math.ceil((new Date(target) - startOfToday()) / 86400000);
```

- 用 `startOfToday()` 而不是 `new Date()`，否则上午下午算出来差一天。
- 跨年、跨月都靠 `Date` 自己做，不要手写"这个月 30 天"。

**易错点**：`carryOver` 必须是"移动视图"而不是"改数据"——把日期改掉会污染历史记录。正确做法：计算时把 `done=false && due<今天` 归入今日泳道。

---

## 六、卡片组合速查

| 场景 | 组合 |
|---|---|
| 备考打卡 | `list`（今日任务）+ `form`（记刷题）+ `metric`（近 14 天折线）+ `time`（倒计时） |
| 记账 | `form`（记一笔）+ `metric`（预算环）+ `list`（本月明细） |
| 习惯 | `matrix`（月热力）+ `metric`（连续天数）+ `list`（今日待打卡） |
| 家长/孩子 | `list`（任务）+ `metric`（积分）+ `form`（兑换申请）+ 双视图切换 |
| 项目管理 | `list`（按状态分组）+ `metric`（完成率）+ `time`（里程碑） |

> 组合超过 4 块 → 回工序 ① 压规模。
