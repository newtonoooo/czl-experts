# 主题与配色

12 套内置主题，6 浅 6 深。主题只决定颜色令牌，不改变布局，因此换主题不需要重新排版。

## 令牌结构

| 令牌 | 作用 |
|---|---|
| `bg` | 画布底色 |
| `surface` | 节点 / 卡片填充 |
| `surfaceAlt` | 次级填充（表头、条纹） |
| `fg` | 主文字 |
| `muted` | 次要文字（标签、脚注） |
| `line` | 连线与坐标轴 |
| `border` | 分隔线与描边 |
| `accent` | 强调色（分组框、激活态） |
| `palette[7]` | 角色色板，顺序对应 primary / decision / data / external / success / danger / neutral |

节点填充不是直接用色板色，而是 `mix(surface, 角色色, 0.11)`，描边用角色色本身。这样同一套色板在深浅底上都保持克制、不刺眼。

## 浅色主题

| 名称 | 中文 | 底色 | 强调色 | 适用 |
|---|---|---|---|---|
| `graphite` | 石墨·浅 | `#ffffff` | `#2f6fed` | 通用文档、README（默认） |
| `paper` | 纸白·暖 | `#fdfcf8` | `#b0521c` | 打印、正式报告 |
| `ocean` | 海雾·浅 | `#f8fbfd` | `#0a6ca3` | 技术文档、方案书 |
| `mint` | 薄荷·浅 | `#f9fbfa` | `#0f8360` | 数据类、健康/增长主题 |
| `sand` | 砂砾·浅 | `#fdfaf4` | `#9c6a10` | 复盘、总结类报告 |
| `sakura` | 樱粉·浅 | `#fdf9fb` | `#ad3765` | 创意、品牌向材料 |

## 深色主题

| 名称 | 中文 | 底色 | 强调色 | 适用 |
|---|---|---|---|---|
| `midnight` | 午夜·深 | `#12141a` | `#6ea8fe` | 默认深色，投影与 PPT |
| `carbon` | 碳灰·深 | `#17181a` | `#f0a92c` | 高对比、暗色 UI 截图 |
| `nordic` | 北境·深 | `#0f1620` | `#58c4dd` | IDE / 开发者文档 |
| `forest` | 深林·深 | `#0f1714` | `#4ec9a0` | 运维、稳定性主题 |
| `plum` | 深紫·深 | `#15111c` | `#b98bff` | 创意、发布会 |
| `slate` | 青岩·深 | `#101317` | `#7fb2e5` | 中性偏冷的技术材料 |

## 怎么选

| 场景 | 推荐 |
|---|---|
| 文档 / README / 知识库 | `graphite` |
| 打印 / PDF 归档 | `paper` |
| 投影 / 发布会 | `midnight` 或 `plum` |
| 与深色 IDE 并排 | `nordic` |
| 数据看板截图 | `mint` 或 `slate` |
| 需要极强对比 | `carbon` |

## 用法

```bash
# 命令行指定
node dg.mjs render my.json --theme midnight

# 模型里指定（可被命令行覆盖）
{ "kind": "flow", "theme": "nordic", ... }

# HTML 内嵌全部主题，现场切换
node dg.mjs render my.json --format html --all-themes
```

## 自定义配色

在模型里写 `theme` 为任意名称是无效的——主题必须来自内置列表。需要品牌色时，直接改 `themes.mjs` 里某个主题的令牌，或复制一份新增：

```js
brandblue: {
  name: 'brandblue', label: '品牌蓝', mode: 'light',
  bg: '#ffffff', surface: '#f2f6fd', surfaceAlt: '#e6eefb',
  fg: '#0d1b2a', muted: '#5a6b80',
  line: '#8fa3bd', border: '#d3e0f0', accent: '#1a5fd0',
  palette: ['#1a5fd0', '#b26a00', '#0f7f8c', '#6a4fc0', '#1a7f45', '#c0392b', '#5a6b80'],
},
```

只需保证：`bg` 与 `fg` 对比度足够（浅底深字 / 深底浅字），`palette` 里 7 个颜色互相可区分且都能在 `surface` 上读清。

## 对比度自查

- 浅色主题：`fg` 与 `bg` 的亮度差应足够大；`muted` 不要低于 `#777` 一档。
- 深色主题：`fg` 建议 ≥ `#e0e0e0`；`muted` 不要低于 `#8a8a8a`，否则小字会糊。
- 语义色（success / danger）在深底上要提亮，否则红色会发黑。

## 色板映射

| 角色 | 索引 | 语义 |
|---|---|---|
| primary | 0 | 主流程 / 主体 |
| decision | 1 | 判断 / 分支 |
| data | 2 | 数据 / 存储 |
| external | 3 | 外部系统 |
| success | 4 | 正常终点 |
| danger | 5 | 异常分支 |
| neutral | 6 | 中性 / 起止 |

一张图里出现的语义色建议不超过 4 种，否则主次会被稀释。
