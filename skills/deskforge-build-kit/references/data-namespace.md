# 数据账细则 · 键名、类型、种子、迁移

---

## 一、键名

```
czl_desk_{app}_{entity}_v{n}
```

| 段 | 规则 | 例 |
|---|---|---|
| 前缀 | 固定 `czl_desk_` | — |
| app | 台子短名，小写英文/拼音，不含空格 | `study`、`ledger`、`habit` |
| entity | 实体名 | `tasks`、`entries`、`habits`、`config` |
| 版本 | `v1` 起，结构变更时 +1 | `v2` |

**禁止**

- 裸键名（`tasks`、`data`）——同一浏览器下多个台子会互相覆盖；
- 带日期的键名（`study_20261026`）——会无限增长，到期无法清理；
- 一个键塞多个实体（除 `config` 这类小配置）。

---

## 二、字段类型

| 类型 | 存储形态 | 输入控件 | 校验 |
|---|---|---|---|
| `text` | string | `<input type="text">` / `<textarea>` | 长度上限（默认 200） |
| `number` | number（整数；金额存分） | `<input type="number">` | 范围、非 NaN |
| `date` | `"YYYY-MM-DD"` | `<input type="date">` | 可被 `Date` 解析 |
| `enum` | string，取值受控 | `<select>` | 必须在取值表内 |
| `bool` | true / false | `<input type="checkbox">` | — |

**金额**：一律存"分"的整数（`1250` 表示 ¥12.50），显示时 `(n/100).toFixed(2)`。避免 `0.1+0.2` 类误差。

**日期**：只存 `YYYY-MM-DD`，不要存 `Date` 对象序列化结果（时区会让它漂）。

---

## 三、种子数据

要求：3–5 条，其中 **1 条处于逾期 / 超支 / 断签状态**，且日期用**相对今天的偏移**。

```js
const today = () => new Date().toISOString().slice(0,10);
const shift = d => { const t = new Date(); t.setDate(t.getDate()+d); return t.toISOString().slice(0,10); };

const SEED = [
  { id:'t1', title:'整理错题本',   due: shift(-1), done:false, priority:'P0' }, // 逾期
  { id:'t2', title:'完成数学卷一套', due: shift(0),  done:false, priority:'P0' },
  { id:'t3', title:'背单词 30 个',   due: shift(0),  done:true,  priority:'P1' },
  { id:'t4', title:'复盘周计划',     due: shift(1),  done:false, priority:'P2' }
];
```

**为什么不能用写死日期**：示例半年后全部变成"逾期"，用户一打开就是一片红，直接判定这工具坏了。

**种子必须有"清空示例"入口**：用户填自己数据前，要能一键清掉假数据（不是清空全部）。

---

## 四、读写与备份

```js
const K_MAIN = 'czl_desk_study_tasks_v1';

function load(){
  try { return JSON.parse(localStorage.getItem(K_MAIN)) || null; }
  catch(e){ console.warn('数据损坏，使用种子'); return null; }
}
function save(){ localStorage.setItem(K_MAIN, JSON.stringify(state.tasks)); }

function exportJSON(){
  const blob = new Blob([JSON.stringify({
    app:'study', version:1, exported_at:new Date().toISOString(), data:{ tasks: state.tasks }
  }, null, 2)], {type:'application/json'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `study_${new Date().toISOString().slice(0,10)}.json`;
  a.click(); URL.revokeObjectURL(a.href);
}
```

**导入要做的四件事**

1. 解析失败 → 提示"文件格式不对"，**不动现有数据**；
2. 版本低于当前 → 走迁移；
3. 版本高于当前 → 提示"这个文件来自更新版本"，让用户确认是否强行导入；
4. 导入成功 → 刷新并提示条数（"已导入 42 条"）。

**清空**：二次确认，要求输入"清空"两个字，避免手滑。

---

## 五、迁移

结构变更时：

```
1  旧键 czl_desk_x_tasks_v1 → 新键 czl_desk_x_tasks_v2
2  启动时若 v2 不存在但 v1 存在：读 v1 → 字段映射 → 写 v2 → 标记 v1 已迁移（保留不删）
3  映射不上的字段：写进 _legacy 字段保留，不静默丢弃
4  迁移失败：不写 v2，页面用 v1 数据只读运行，并提示用户导出备份
```

**原则**：宁可留冗余字段，不可丢用户数据。删字段要单独一次（用户确认后）再做。

---

## 六、性能

| 记录量 | 处理 |
|---|---|
| <200 条 | 直接渲染 |
| 200–1000 条 | 列表只渲染前 50 条 + "显示更多" |
| >1000 条 | 按月/按状态分组，默认展开当前组 |

每次 `save()` 都是整表写回，超过几千条后会有卡顿；到那个量级，先提示用户导出归档，只保留近期数据在主表。
