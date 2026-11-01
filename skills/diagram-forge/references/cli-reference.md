# 命令行参考

入口：`skills/diagram-forge/scripts/dg.mjs`，运行环境 Node.js ≥ 18，无第三方依赖。

```
node dg.mjs <命令> [参数...]
```

## render

渲染模型，产出文件。

```bash
node dg.mjs render <model.json> [选项]
```

| 选项 | 默认 | 说明 |
|---|---|---|
| `--out <dir>` | `./out` | 输出目录，不存在会自动创建 |
| `--theme <name>` | 模型里的 `theme` 或 `graphite` | 主题名，见 `dg themes` |
| `--format <list>` | `svg,mmd,html` | 逗号分隔，可选 `svg,html,mmd,ascii,model` |
| `--name <slug>` | 标题或文件名 | 输出文件名（不含扩展名） |
| `--all-themes` | 关 | HTML 内嵌全部 12 套主题，可现场切换 |
| `--json` | 关 | 额外打印机器可读的结果摘要 |

退出码：`0` 成功；`2` 模型不合法或主题不存在。

输出文件：

| 后缀 | 内容 |
|---|---|
| `.svg` | 矢量图，含生成标记与 `<title>` |
| `.html` | 单文件交互预览（主题切换、缩放、平移），无外部依赖 |
| `.mmd` | Mermaid 源码 |
| `.txt` | ASCII 文本图 |
| `.model.json` | 规范化后的模型（默认不输出，需显式指定） |

示例：

```bash
node dg.mjs render templates/flow-approval.json --out dist --theme midnight --format svg,html
```

## check

校验模型或 Mermaid 源码，不产出文件。

```bash
node dg.mjs check <file.json|file.mmd>
```

- `.json`：走模型校验，输出 error 与 warning，并附质量分摘要
- `.mmd`：走语法体检，输出「行号 + 原因」

退出码：`0` 通过；`1` 语法错误；`2` 模型错误。

## review

只做质量评分，输出结构指标与改进项。

```bash
node dg.mjs review <model.json>
```

输出内容：图表类型、总分与等级、结构指标（节点数、边数、密度、最大扇出、层级深度、分组数等）、逐条改进项与扣分。

## themes

列出全部主题及底色、强调色。

```bash
node dg.mjs themes
```

## new

打印指定类型的可运行模板，用于快速起步。

```bash
node dg.mjs new <flow|state|class|er|sequence|gantt|mindmap|timeline|pie|quadrant|xy>
```

## spec

打印模型字段规范（JSON 格式），适合程序化读取。

```bash
node dg.mjs spec
```

## 自检

```bash
node scripts/tools/selftest.mjs [--out <dir>]
```

逐模板执行：模型校验 → 场景构建 → SVG → Mermaid 导出并回检 → HTML → ASCII → 评分，另有全主题矩阵渲染与非法输入测试。全部通过时退出码为 0。

## 头像体检（可选）

```bash
python scripts/tools/avatar_check.py check <专家目录>
python scripts/tools/avatar_check.py fix <输入.png> <输出.png> [--size 512] [--max-kb 480]
```

检查 `plugin.json` 的 `avatar` 是否指向真实存在、格式合法、512×512、≤500KB 的图片；`fix` 会裁成正方形、降采样并重新编码 PNG。

## 常见报错

| 报错 | 含义 | 处理 |
|---|---|---|
| `未知主题 "xxx"` | 主题名不在列表 | `dg themes` 查准确名 |
| `模型校验未通过` | 字段缺失 / 悬空边 / 类型不符 | 按「字段路径: 原因」逐条修 |
| `JSON 解析失败` | 文件不是合法 JSON | 检查多余逗号、中文引号 |
| `无法读取文件` | 路径错或文件不存在 | 用绝对路径重试 |
| `括号未闭合` | `.mmd` 语法错误 | 按行号补括号或引号 |
