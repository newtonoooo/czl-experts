---
name: publish-kit
description: "Renders a finished Chinese article into a single-file WeChat Official Account HTML that survives copy-paste into the editor: all styles inline, zero JS, layout only via nested tables, no grid/flex/position. Implements a battle-tested typography spec (680px container, numbered chapter blocks, quote cards, stat cards, data tables, timeline, source box, footer) with five low-saturation colour schemes picked at random by default and pinnable via frontmatter, plus an automated compliance linter for the spec's blacklist. Use when a draft needs to look right on a phone before publishing, when pasted HTML loses its formatting, or when a series of articles must stay visually consistent."
version: 1.2.0
---

# 排版交付（publish-kit）

## 这个技能解决什么

公众号排版有一道特殊的坎：**你在浏览器里写好的样式，粘到后台会掉一半**。

掉的原因不是编辑器坏，是它只认一部分 CSS：保留内联样式，丢弃 `<style>` 里的 class，过滤 grid / flex / 定位 / 伪元素。所以"好看"和"能粘贴"经常是两件事。

这个技能把两件事一次做完：**按一套验证过的规范生成 HTML，再用脚本把规范的黑名单反过来查一遍。**

## 什么时候用

| 场景 | 判据 |
|---|---|
| 稿子改完，要发出去 | 需要一份能直接粘贴的 HTML |
| 以前粘过去就掉样式 | 大概率用了 class / grid / flex，跑一遍 linter 就知道 |
| 系列文章要统一视觉 | 用同一套 Token 与组件，不靠每次手动调 |
| 每篇想换点样子 | 五套配色默认随机，想固定就在 frontmatter 写 `theme:` |
| 手机上读着累 | 先看段长与小标题密度，再看字号行高 |
| 文章要有配图 | 下载到本地 → 相对路径引用 → 生成上传清单 |

**不适用**：稿子内容还没定 → 先回质量闸门；需要设计原创版式 → 本技能只套版，不做视觉设计。

## 执行步骤

### 第一步：确认内容已经定稿

排版不修内容。段长超标的地方，先回质量闸门处理，再回来排。

### 第二步：按方言写稿

语法见 `references/markdown-dialect.md`。最常见的三个错：

1. frontmatter 后还写了 `# 一级标题` → 公众号里标题会出现两次
2. 表格第二行忘了写 `| --- |` → 被当成普通段落
3. 时间轴块忘了结尾 `:::` → 后面全部内容被吞进时间轴

### 第三步：渲染

```bash
python scripts/render_wechat.py 定稿.md                    # 配色随机抽一套
python scripts/render_wechat.py 定稿.md --out 预览.html     # 指定输出
python scripts/render_wechat.py 定稿.md --theme b-navy     # 指定配色
python scripts/render_wechat.py 定稿.md --seed 42          # 随机但可复现
python scripts/render_wechat.py --list-themes              # 看五套配色
```

输出单文件 HTML：680px 容器、全内联、无外链、无 JS。

**配色怎么定**：默认**随机**（每篇不一样），优先级是 `--theme` > frontmatter `theme:` > 随机。
随机是**整篇级别**的，不会一章一个色。终端会打印抽到哪套、主色值，以及复现命令：

```
配色：c-dai 黛蓝烟雨（随机）｜ 主色 #2F5D62 强调 #A85A6A 点缀 #C9A86A
      清雅、温柔、留白感；适合随笔、教育理念、慢话题
      想固定这套：下次加 --theme c-dai，或在 frontmatter 写 theme: c-dai
```

五套的适用面（选色时看这个，不要纯看喜好）：

| key | 名称 | 适合 |
|---|---|---|
| `a-ink` | 墨绿书卷 | 硬新闻、盘点、深度；拿不准就用它 |
| `b-navy` | 藏青学术 | 政策、规则、数据解读 |
| `c-dai` | 黛蓝烟雨 | 随笔、教育理念、慢话题 |
| `d-chestnut` | 栗棕暖陶 | 亲子、情感、成长故事 |
| `e-graphite` | 石墨青 | 观点、评论、年轻化表达 |

**一套只用 1 主色 + 1 强调色 + 1 点缀色**，这是规范的硬要求，不要自己加第四种颜色。

### 第四步：跑合规自检（不能跳）

```bash
python scripts/check_wx_html.py 预览.html
```

它按规范的黑名单逐项查：grid / flex / position / transform / 伪元素 / 负 margin / 脚本 / 外链 / 字体缺 fallback / 表格缺列宽 / 圆点缺宽高 / 容器没固定宽。

**exit 0 才算可以粘。** 有 FAIL 就回去改，不要"先粘过去看看"——粘完再改，改的是两份东西。

### 第四步半：配图（需要时）

公众号**不接受外链图片**，粘到后台会裂。所以配图只能这么走：

```bash
# 1. 下载到本地（可批量，带说明会写进 alt 与图注）
python scripts/fetch_images.py --file urls.txt --dir images --prefix 01 --markdown

# 2. 把输出的标记贴进 Markdown，位置由你定
#    ![说明](images/01_1.jpg "图注：会显示在图片下方的小字")

# 3. 渲染（默认同时生成图片上传清单）
python scripts/render_wechat.py 定稿.md
```

`urls.txt` 每行一个地址，可用 `|` 分隔说明：

```
https://example.com/a.jpg | 初三教室全景
https://example.com/b.jpg | 体育考试现场
```

渲染后会生成 **`图片上传清单.md`**：哪张图、什么尺寸、多大、插在哪一节。发布时按这个顺序在后台逐张上传插入。

**两个可选参数**：

| 参数 | 作用 | 什么时候用 |
|---|---|---|
| `--embed` | 把本地图转成 base64 内嵌进 HTML | 想一次粘完不想手动插图时；但 HTML 会变大、后台可能不认 |
| `--manifest 路径` | 指定清单输出位置 | 一次排多篇时分开存 |

**落款的硬规矩**：
1. `footer_name` 只能是用户自己的公众号名。**不许填示例、不许编名字、不许用别人的号。**
2. 用户没给 → 整块落款不输出（`--no-footer` 或不写 `footer_name`），交付时提醒一句"把号名给我，我补上落款"。
3. `footer_slogan` 同理：那是账号定位，不是排版发挥。

**图片的硬规矩**：
1. 禁止外链。你自己预览能看到，粘到后台就是裂图。
2. 下载的图不等于能用。确认授权再上（自制 / 明确可商用 / 已获授权）。
3. 找不到合适的图，宁可用表格、时间轴、色块替代，不要硬凑一张不相关的图。

### 第五步：粘贴与核对

按 `references/preflight-checklist.md` 走：浏览器打开 → Ctrl+A → Ctrl+C → 后台粘贴 → 逐项核对 → 手机预览。

**粘贴后必须用手机预览一次。** 桌面看着正常、手机挤成一团的表格，是这类排版最常见的翻车。

## 组件与 Token（速查）

每套配色只有三个色：**主色**管章节编号块、表格表头、编号圆牌等结构件；**强调色**管时间、重点词、大数字；**点缀色**只点在最关键的 1—2 处（金句高亮、关键节点圆点、提示块竖线）。

常用六个组件：

| 想表达 | 用什么 | 写法 |
|---|---|---|
| 分块 | 章节编号块 | `## 标题`，重点章节写 `## ! 标题`（换强调色） |
| 罗列数据 | 数据表 / 数据卡 | 表格 或 `::: stats` |
| 时间顺序 | 时间轴 | `::: timeline` |
| 一句核心观点 | 金句卡 | `::: quote`（一篇最多一两个） |
| 一句提醒 | 提示块 | `> 内容` |
| 交代出处 | 来源框 | `::: source` |

完整 Token、各组件的标准写法、黑名单表见 `references/typography-spec.md`（这是唯一权威来源）。
**改配色要双写**：`typography-spec.md` §4 与 `render_wechat.py` 的 `SCHEMES` 必须一致，否则文档与实际输出会脱节。

## 输出规范

- 交付时给：HTML 路径 + 自检结果（几项 FAIL / WARN）+ 章节数/表格数 + 图片上传清单路径（有图时）
- 有 WARN 要说明是什么、要不要处理（box-shadow 丢失不影响，外链图片必须换）
- 不说"排版已完成"——说"已生成并通过自检。浏览器打开能看到完整效果；发到公众号时图片位置是空的，按清单在后台逐张上传插入"

## 依赖

- Python 3.8+，仅标准库
- 无需联网、无需图像库

## 异常处理

| 情况 | 处理 |
|---|---|
| 渲染后正文为空 | 检查是否用了 `## 章节` 与普通段落；纯 HTML 输入不支持 |
| 表格中文一字一行 | 列宽未固定 → linter 会报；检查是否漏了分隔行 |
| 粘过去圆点变方块 | 圆点缺 width/height → linter 会报 |
| 字体全变样 | 某处 font-family 没带 fallback → linter 会报 |
| 需要插图 | `fetch_images.py` 下载到本地 → 相对路径引用 → 发布时按清单上传 |
| 图片下载失败 | 报错会说明原因（超时/返回网页/格式不认）；换源或改用手绘色块 |
| 清单报"文件缺失" | 路径写错或文件没下成，补齐或删掉该图片标记，不许留裂图 |
| 用户坚持要渐变/阴影 | 说明风险（可能丢失/变色），让他决定；linter 会保留 WARN |
| 抽到的配色不喜欢 | 换 `--theme` 重跑即可；已发布的别换（同系列中途换色会掉识别度） |
| 报"未知配色" | 只能填 `a-ink`/`b-navy`/`c-dai`/`d-chestnut`/`e-graphite`；旧名 `ink` 仍兼容 |

## References

- `references/typography-spec.md` — 排版规范全文（五套配色、视觉 Token、黑名单、组件库、自检清单）
- `references/markdown-dialect.md` — 本渲染器支持的 Markdown 语法
- `references/preflight-checklist.md` — 粘贴与发布前的核对清单
