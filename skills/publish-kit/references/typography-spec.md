<!--
来源：作者（虫志龙）自有多账号实战规范，经桌面端 + 手机端验证。
本文件是「排版规则」的唯一权威来源。render_wechat.py 的 Token、组件、黑名单均按此实现；
改规范必须同步改脚本，改脚本也必须回写这里。

本副本已做去品牌处理：原规范中的作者账号名与本领域专有表述均已替换为通用说法，
避免使用者生成的内容被绑到某个具体账号上。原文的规则内容（黑名单、Token、组件、
自检清单）一字未改；如日后从原始文件重新同步，需再次执行同样的去品牌替换。

同步版本：2026-10-26 修订（新增 §4「配色方案库（5 套）」；布局改为「外层 table +
容器 table + 每区块一个 tr>td」；图片改走本地 assets/ 相对路径）

配套脚本：
  scripts/render_wechat.py    按本规范生成 HTML（含 5 套配色，默认随机）
  scripts/check_wx_html.py    按本规范的黑名单与自检清单做自动校验
  scripts/fetch_images.py     图片下载到本地 assets/
-->

# 微信公众号图文 HTML 排版规范（AI 可直接复用）

> 目标：产出一个 
>
> `.html`
>
>  文件，浏览器打开后 
>
> **Ctrl+A 全选 → Ctrl+C → 粘贴到公众号后台正文区**
>
> ，颜色、卡片、表格、图片、重点高亮全部保留，无需在后台重新排版。
> 本规范来自多账号实战，含一次 "时间线在公众号失效" 的踩坑复盘，全部结论均在桌面端 + 手机端截图验证。



***

## 0. 一句话核心

**所有样式一律内联写在元素的&#x20;**`style=""`**&#x20;里；布局只用 table（外层 table + 容器 table，每个区块一个&#x20;**`tr>td`**）；不写 JS、不依赖 class、不依赖外部 CSS / 字体；图片下载到本地&#x20;**`assets/`**&#x20;用相对路径。**

公众号编辑器粘贴时：**保留内联样式，丢弃&#x20;**`<style>`**&#x20;里的 class、丢弃&#x20;**`<script>`**、过滤 grid/flex/ 定位等现代布局**。这是全部规则的根。



***

## 1. 五条铁律



1. **单文件、全内联**：每个标签的视觉都写在它自己的 `style` 属性里。正文绝不能依赖 class 生效。

2. **无 JS**：公众号正文不执行 JavaScript。不做 tab、折叠、点击交互；需要分块就全部平铺展开。

3. **布局只用 table**：外层背景 table、容器 table、区块 `tr>td`；多列、数据、卡片一律嵌套 table。圆点、小标签可用 `display:inline-block`。

4. **不依赖外部资源**：

* 字体：每个元素 `font-family` 必须带**系统字体 fallback 栈**（见 §4），网络字体 `<link>` 只供浏览器预览，粘贴后会被剥。

* 图片：外链图会过期 / 防盗链。**必须先下载到本地&#x20;**`assets/`**，用相对路径&#x20;**`assets/xxx.jpg`（见 §7）。

1. **容器自适应居中**：容器 `width:100%;max-width:680px`，外层 `td align="center"`；手机上靠 `width:100%` 自适应。



***

## 2. 黑名单：这些写法公众号会过滤（务必避开）



| 写法                                         | 后果                  | 替代方案                                       |
| ------------------------------------------ | ------------------- | ------------------------------------------ |
| `display:grid` / `grid-template-columns`   | 布局直接崩、元素错位（时间线翻车主因） | 用 `table` 做多列                              |
| `display:flex`                             | 支持极差，手机端尤其不稳        | 用 `table` 或 `inline-block`                 |
| `position:absolute/relative/fixed`         | 定位被剥，元素回到文档流乱排      | table 单元格 + `vertical-align`               |
| `transform: translate(...)`                | 居中 / 位移失效           | `text-align:center`、`margin:auto`、table 居中 |
| 伪元素 `::before / ::after`                   | 完全不生成               | 用真实的 `span` 元素                             |
| `class` / `id` 选择器（写在 `<style>`）           | 粘贴后不作用              | 全部改成内联 `style`                             |
| `<script>`、事件属性 `onclick`                  | 不执行 / 被剥            | 不做交互，内容平铺                                  |
| 负 `margin`                                 | 常被过滤，对齐失效           | 重新设计列宽，不靠负边距压线                             |
| CSS 变量 `var(--x)`、`calc()`                 | 支持不稳 / 被剥           | 写死具体数值                                     |
| `float`                                    | 支持不稳、易错位            | 用 `table`                                  |
| 网络字体 `<link href=...googleapis/miaoda...>` | 粘贴后被剥               | 系统字体 fallback 兜底                           |
| 外链 CSS/JS、外链图片                             | 不加载 / 裂图            | 全部内联；图片下载本地                                |
| `linear-gradient` 渐变                       | 部分支持、易变色            | 纯色 `background` 最稳                         |
| `box-shadow`                               | 可能丢失                | 用 `border` 描边代替                            |

> 经验：凡是 "需要元素脱离正常文档流、或需要浏览器计算位置" 的写法，默认在公众号里不可靠。



***

## 3. 白名单：放心使用（内联形式）



* `table`**&#x20;/&#x20;**`tr`**&#x20;/&#x20;**`td`**&#x20;/&#x20;**`th`：布局、多列、数据表、卡片的首选，支持最好

* 块级：`section`、`div`、`p`、`h1~h4`（推荐全 table，div 仅作内部补充）

* `display:inline-block`：圆点、胶囊标签、编号圆牌

* 盒模型与文字：`color`、`font-size`、`font-weight`、`font-family`、`line-height`、`text-align`、`letter-spacing`

* 背景与边框：`background`（纯色）、`border`、`border-radius`、`border-collapse:collapse`、`table-layout:fixed`

* 间距：`padding`、`margin`（**正值**）、`width`、`height`、`max-width`、`vertical-align`

* 图片：`<img src="assets/xxx.jpg" width="100%" style="display:block;width:100%;height:auto;">`

* 内联强调：`<strong>`、`<b>`、`<span style="color:...">`



***

## 4. 视觉 Token（系列统一，直接抄）

### 配色



```
墨绿(主色/章节/结构)   #1F5A50
枣红(强调/重点/标题)    #9E3B2E
奖牌金(金句/最关键处)   #C29A4B
奶油底(正文容器)       #FBF9F5
外层背景             #EDEAE3
卡片白               #FFFFFF
正文文字             #2b2b26
次要说明文字          #6a6a62
边框/浅分隔          #E8E2D6
浅金卡片底           #F7F0E3
浅金卡片边           #E8DEC8
```

**用法克制**：墨绿管 "结构 / 章节"，枣红管 "重点 / 关键标题"，金色只点在最关键的 1–2 处；强调色不超过这三个。

### 配色方案库（5 套，可整套替换，均为低饱和纯色、粘贴可靠）

> 每套都含：主色(章节/结构)、强调色(重点)、点缀色(最克制)、容器底、外层背景、正文、次要、边框、卡片浅底/边。整套替换时，把组件里的色值一一对应换掉即可。

**方案 A · 墨绿书卷（当前默认，中式沉稳，百搭）**

```text
主色 墨绿   #1F5A50      强调 枣红   #9E3B2E      点缀 金     #C29A4B
容器底       #FBF9F5      外层背景    #EDEAE3      正文        #2b2b26
次要         #6a6a62      边框        #E8E2D6      卡片浅底/边 #F7F0E3 / #E8DEC8
气质：中式、书卷、沉稳；适合硬新闻、盘点、深度，最稳。
```

**方案 B · 藏青学术（理性、可信赖，适合政策/数据解读）**

```text
主色 藏青   #23395B      强调 赭橙   #C5673F      点缀 哑金   #B8924E
容器底       #FAF8F4      外层背景    #E9ECEF      正文        #262A30
次要         #67707A      边框        #E2E6EA      卡片浅底/边 #F1EEE7 / #E4DFD4
气质：学术、理性、权威；适合政策、规则、数据图表。
```

**方案 C · 黛蓝烟雨（清雅、江南、有温度）**

```text
主色 黛蓝   #2F5D62      强调 胭脂   #A85A6A      点缀 淡金   #C9A86A
容器底       #F8F6F2      外层背景    #EAEAE5      正文        #2A2E2E
次要         #656E6C      边框        #E3E6E0      卡片浅底/边 #F0EDE6 / #E3DED2
气质：清雅、温柔、留白感；适合随笔、教育理念、慢话题。
```

**方案 D · 栗棕暖陶（温暖、亲子，适合情感类）**

```text
主色 栗棕   #7A5230      强调 陶土红 #B5573D      点缀 暖金   #C9A24B
容器底       #FAF6EF      外层背景    #ECE6DD      正文        #2E2A25
次要         #6E655B      边框        #E7E0D5      卡片浅底/边 #F4EBDD / #E7DCC7
气质：温暖、接地气、像家里的灯光；适合亲子、情感、成长故事。
```

**方案 E · 石墨青（现代、简洁、有力，适合观点类）**

```text
主色 石墨青 #264653      强调 赤陶   #E76F51      点缀 暖黄   #E9C46A
容器底       #FFFFFF      外层背景    #EDEFEF      正文        #23282A
次要         #5F6A6E      边框        #E4E8E9      卡片浅底/边 #F2F5F4 / #DFE6E5
气质：现代、干净、有力量；适合观点、评论、年轻化表达。
```

**配色通用规则（换哪套都成立）**

1. 一套只用 **1 个主色 + 1 个强调色 + 1 个点缀色**，不再加别的彩色。
2. 主色管章节条/编号块/结构，强调色管重点词和关键标题，点缀色只点最关键的 1–2 处。
3. 容器底用**暖白/米白**（比纯白更有质感），正文色要够深（保证可读）。
4. 同一篇/同一系列尽量固定一套，别中途换色，保持系列识别度。
5. 拿不准就用方案 A；数据多用 B，情感多用 D，年轻观点用 E。

### 字体（必须带系统 fallback）



```
/* 标题（衬线，有书卷气） */
font-family:'Noto Serif SC','Songti SC','SimSun',serif;
/* 正文（无衬线，好读） */
font-family:'Noto Sans SC','PingFang SC','Microsoft YaHei',sans-serif;
```

> 每个元素都要写完整 fallback，粘贴到公众号后由系统字体接管，版面才不塌。

### 字号 / 间距 / 圆角（680px 容器下，已验证的舒展版）



```
主标题        28px / 900 / 墨绿 / line-height 1.42
副标题        18px / 700 / 枣红 / line-height 1.6
章节编号方块   20px（墨绿或枣红底白字）
章节标题       22px / 700 / 墨绿
正文          17px / line-height 1.95 / #2b2b26
图片图注       13px / 次要色 / 居中
金句卡片正文   16px / line-height 1.9
数据大数字     28px / 900 / 枣红
数据说明       13px / 次要色
署名账号名     20px / 900 / 衬线 / 墨绿
署名 slogan   14px / 次要色
来源标题       13px / 700；来源正文 12.5px / line-height 1.85
左右内边距     32px（手机可保持，不会挤）
常规圆角       卡片 6–8px；图片 4px
区块间距       章节块前 40px；同区块内图文间 20px
```



***

## 5. 标准骨架（全 table，复制即起步）



```
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>文章标题</title>
</head>
<body style="margin:0;padding:0;background:#EDEAE3;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;background:#EDEAE3;">
<tr><td align="center" style="padding:24px 12px;">

  <!-- 正文容器 -->
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;background:#FBF9F5;max-width:680px;border-radius:6px;">

    <!-- 每个区块都是一个 tr>td，按需往下排 -->
    <tr><td style="padding:30px 32px 0 32px;">……</td></tr>

  </table>

</td></tr>
</table>
</body>
</html>
```

> 关键：
>
> `cellpadding="0" cellspacing="0" border="0"`
>
>  每个 table 都要写；
>
> `border-collapse:collapse`
>
> ；区块统一用 
>
> `padding:上 32px 下 32px`
>
> ，需要上边距就加大第一个值。



***

## 6. 实战组件库（直接复制改字）

### 6.1 顶部双标签（一个实心 + 一个描边）



```
<tr><td style="padding:30px 32px 0 32px;">
<table cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;">
<tr>
<td style="background:#1F5A50;color:#fff;font-size:13px;font-weight:700;padding:5px 12px;letter-spacing:1px;font-family:'Noto Sans SC','PingFang SC','Microsoft YaHei',sans-serif;">479观察</td>
<td style="background:#fff;color:#1F5A50;font-size:13px;font-weight:700;padding:5px 12px;border:1px solid #1F5A50;letter-spacing:1px;font-family:'Noto Sans SC','PingFang SC','Microsoft YaHei',sans-serif;">校园青春</td>
</tr>
</table>
</td></tr>
```

### 6.2 主标题 + 副标题



```
<tr><td style="padding:22px 32px 0 32px;">
<h1 style="margin:0;font-family:'Noto Serif SC','Songti SC','SimSun',serif;font-size:28px;font-weight:900;line-height:1.42;color:#1F5A50;">主标题第一行</h1>
<p style="margin:14px 0 0 0;font-family:'Noto Serif SC','Songti SC','SimSun',serif;font-size:18px;font-weight:700;line-height:1.6;color:#9E3B2E;">副标题，枣红色</p>
</td></tr>
```

### 6.3 分隔线



```
<tr><td style="padding:24px 32px 0 32px;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;">
<tr><td style="border-bottom:1px solid #E8E2D6;font-size:0;line-height:0;">&nbsp;</td></tr>
</table>
</td></tr>
```

### 6.4 正文段落



```
<tr><td style="padding:20px 32px 0 32px;">
<p style="margin:0 0 14px 0;font-size:17px;line-height:1.95;color:#2b2b26;font-family:'Noto Sans SC','PingFang SC','Microsoft YaHei',sans-serif;">第一段，注意段末用 margin-bottom 拉开。</p>
<p style="margin:0;font-size:17px;line-height:1.95;color:#2b2b26;font-family:'Noto Sans SC','PingFang SC','Microsoft YaHei',sans-serif;">最后一段 margin 设为 0。句内重点用 <span style="font-weight:700;color:#9E3B2E;">这样标</span>。</p>
</td></tr>
```

### 6.5 章节编号块（墨绿 / 枣红方块 + 标题）



```
<tr><td style="padding:40px 32px 0 32px;">
<table cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;">
<tr>
<td style="background:#1F5A50;color:#fff;font-family:'Noto Serif SC','Songti SC','SimSun',serif;font-size:20px;font-weight:700;padding:8px 16px;">01</td>
<td style="padding-left:14px;font-family:'Noto Serif SC','Songti SC','SimSun',serif;font-size:22px;font-weight:700;color:#1F5A50;">章节标题</td>
</tr>
</table>
</td></tr>
```

> 需要重点 / 警示章节时，把编号方块的 
>
> `background`
>
>  换成枣红 
>
> `#9E3B2E`
>
> 。

### 6.6 图片 + 居中图注



```
<tr><td style="padding:20px 32px 0 32px;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;">
<tr><td><img src="assets/xxx.jpg" alt="图片说明" width="100%" style="display:block;width:100%;height:auto;border-radius:4px;"></td></tr>
<tr><td align="center" style="padding:8px 0 0 0;"><p style="margin:0;font-size:13px;color:#6a6a62;font-family:'Noto Sans SC','PingFang SC','Microsoft YaHei',sans-serif;">图注，居中，次要色</p></td></tr>
</table>
</td></tr>
```

### 6.7 墨绿金句卡片（含金句 / 核心观点）



```
<tr><td style="padding:6px 32px 0 32px;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;background:#1F5A50;border-radius:8px;">
<tr><td style="padding:18px 22px;">
<p style="margin:0;font-size:16px;line-height:1.9;color:#FBF9F5;font-family:'Noto Sans SC','PingFang SC','Microsoft YaHei',sans-serif;">金句正文，<span style="font-weight:700;color:#C29A4B;">最关键的半句用金色</span>。</p>
</td></tr>
</table>
</td></tr>
```

### 6.8 浅金数据卡片（2 列 / 3 列 / 4 列）



```
<tr><td style="padding:6px 32px 0 32px;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;table-layout:fixed;">
<colgroup><col style="width:50%"><col style="width:50%"></colgroup>
<tr>
<td style="background:#F7F0E3;border:1px solid #E8DEC8;padding:14px 10px;text-align:center;border-right:1px solid #E8DEC8;">
<p style="margin:0;font-family:'Noto Serif SC','Songti SC','SimSun',serif;font-size:28px;font-weight:900;color:#9E3B2E;line-height:1;">7 条</p>
<p style="margin:8px 0 0 0;font-size:13px;color:#6a6a62;line-height:1.5;font-family:'Noto Sans SC','PingFang SC','Microsoft YaHei',sans-serif;">数据说明</p>
</td>
<td style="background:#F7F0E3;border:1px solid #E8DEC8;padding:14px 10px;text-align:center;">
<p style="margin:0;font-family:'Noto Serif SC','Songti SC','SimSun',serif;font-size:28px;font-weight:900;color:#9E3B2E;line-height:1;">3 个</p>
<p style="margin:8px 0 0 0;font-size:13px;color:#6a6a62;line-height:1.5;font-family:'Noto Sans SC','PingFang SC','Microsoft YaHei',sans-serif;">数据说明</p>
</td>
</tr>
</table>
</td></tr>
```

> 3 列 / 4 列：改 
>
> `<colgroup>`
>
>  宽度（如三列各 33.3%），并给中间单元格加 
>
> `border-right`
>
> ，最后一列不加。

### 6.9 署名区（居中，衬线）



```
<tr><td style="padding:36px 32px 0 32px;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;">
<tr><td style="border-top:1px solid #E8E2D6;padding-top:24px;" align="center">
<p style="margin:0 0 6px 0;font-family:'Noto Serif SC','Songti SC','SimSun',serif;font-size:20px;font-weight:900;color:#1F5A50;">你的公众号名</p>
<p style="margin:0;font-size:14px;line-height:1.8;color:#6a6a62;font-family:'Noto Sans SC','PingFang SC','Microsoft YaHei',sans-serif;">一个聊学习方法、也聊孩子成长的地方<br>不贩卖焦虑，只说实在话</p>
</td></tr>
</table>
</td></tr>
```

### 6.10 白底来源框



```
<tr><td style="padding:28px 32px 36px 32px;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;background:#fff;border:1px solid #E8E2D6;border-radius:6px;">
<tr><td style="padding:14px 18px;">
<p style="margin:0 0 8px 0;font-size:13px;font-weight:700;color:#6a6a62;font-family:'Noto Sans SC','PingFang SC','Microsoft YaHei',sans-serif;">素材来源</p>
<p style="margin:0;font-size:12.5px;line-height:1.85;color:#6a6a62;font-family:'Noto Sans SC','PingFang SC','Microsoft YaHei',sans-serif;">逐条列出报道名称、媒体、日期……本文为公开报道整理与个人观点。</p>
</td></tr>
</table>
</td></tr>
```

### 6.11 时间轴 / 步骤流（table 版，重点）

**不要画贯穿竖线、不要定位**。每个节点一行三列：`时间 | 圆点 | 标题+说明`。



```
<tr><td style="padding:6px 32px 0 32px;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;background:#fff;border:1px solid #E8E2D6;border-radius:8px;">
<tr>
<td style="width:54px;vertical-align:top;text-align:right;padding:14px 8px 16px 0;">
<span style="font-size:13px;color:#9E3B2E;font-weight:700;">10月</span>
</td>
<td style="width:16px;vertical-align:top;text-align:center;padding:15px 0 16px;">
<span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#1F5A50;"></span>
</td>
<td style="vertical-align:top;padding:14px 0 16px 7px;">
<p style="margin:0;font-size:15px;font-weight:700;color:#2b2b26;line-height:1.5;">节点标题</p>
<p style="margin:3px 0 0;font-size:13px;color:#6a6a62;line-height:1.8;">一句话说明。</p>
</td>
</tr>
<!-- 重复 <tr>；最后一行把 padding-bottom 改小 -->
</table>
</td></tr>
```

> 普通节点圆点墨绿；最关键金色；大考枣红（可设 13px）。圆点必须 
>
> `inline-block`
>
>  \+ 固定宽高 + 
>
> `border-radius:50%`
>
> 。



***

## 7. 图片素材处理（重要）



1. **图片必须下载到本地**：文章目录下建 `assets/`，图片放进去，HTML 里写相对路径 `assets/xxx.jpg`。

2. **来源**：优先真实照片（搜图 / 用户提供），其次 AI 生图；搜图返回的 CDN 链接会过期，不能直接写进 HTML。

3. **下载后必须用读图工具实际看过**：确认内容对得上、清晰、无水印、不是防盗链占位图。

4. **显示**：一律 `width="100%" style="display:block;width:100%;height:auto;"`，不要写死高度，避免变形。

5. **比例**：头图 2.35:1（或 2.4:1）；正文配图横向 3:2 \~ 16:9，避免极端比例（1:5、9:16）。

6. **交付提醒**：HTML 依赖 `assets/`，转发 / 备份时要连文件夹一起发，否则裂图。



***

## 8. 文案风格（去 AI 化，和排版同等重要）

账号语气要求由使用者提供，写进账号配置。**这一项不能预设**——不同账号的语气差别很大，预设等于替别人定人设。

下面是这套规范作者自己的常用语气，仅作填写示例：**大白话、接地气、平和有温度、不贩卖焦虑、不站队、不拉踩、就事论事。**

去 AI 化的具体做法：



1. **句子长短错落**：别每句都一样长、一样工整。偶尔来一句短的，比如 "话是这么说。"" 可我不这么看。"

2. **要有 "我" 的真实感受和具体画面**：从一个场景切入（"昨晚快 12 点了，我还在刷手机……"），而不是上来下定义。

3. **少用大词和套话**：去掉 "赋能"" 闭环 ""值得注意的是"" 综上所述 "这类词；用" 说白了 ""你想想"" 我反倒觉得 "。

4. **观点要具体、别说正确的废话**：宁可讲一个别人没说透的角度，也不要四平八稳地罗列常识。

5. **数字和事实要可追溯**：每个数字来自具体报道或文件，文末列来源；不确定的标注 "待核实"，不编。

6. **落点温和**：可以指出问题，但最后要落到 "家长能做什么"，给人抓手，不制造恐慌。

7. **标题重点醒目**：标题里最有信息量的词，正文里也用对应颜色强调，前后呼应。



***

## 9. 拷贝与发布流程



1. 浏览器（Chrome/Edge）打开 `.html` 文件。

2. 点击正文最开头，`Ctrl+A` 全选，`Ctrl+C` 复制。

3. 公众号后台 → 新建图文 → 点击正文编辑区，`Ctrl+V` 粘贴。

4. 粘贴后逐项核对：标签、标题、章节方块、图片、卡片、表格列宽、重点高亮是否都在。

5. 后台单独填写：**标题、作者、摘要、封面图**。

6. 点「预览」扫码到手机，确认手机端图片不裂、表格不挤、颜色正常，再群发。



***

## 10. 交付前自检清单（AI 写完逐条过）



* [ ] 正文是否**全部内联样式**，不依赖任何 class/id？

* [ ] 是否**零 JS、零交互**，所有内容平铺可见？

* [ ] 是否**没有 grid /flex/position /transform/ 伪元素 / 负 margin /calc/var**？

* [ ] 是否**全 table 布局**，每个 table 都有 `cellpadding=0 cellspacing=0 border=0 border-collapse:collapse`？

* [ ] 多列表格是否有 `table-layout:fixed` + `<colgroup>` 列宽之和 = 100%？

* [ ] 每个 `font-family` 是否带**系统字体 fallback**？

* [ ] 图片是否**下载到本地 assets、用相对路径**，并实际看过？图片路径是否只写在 `src` 里？

* [ ] 容器是否 `width:100%;max-width:680px`，手机端自适应（看手机截图）？

* [ ] 颜色是否克制（墨绿 / 枣红 / 金，不堆砌）、重点是否一眼可见？

* [ ] 文案是否去 AI 化、有 "我"、有画面、语气平和？

* [ ] 是否在桌面端 **和** 手机端各看一遍截图？

> 自检工具：用 html skill 的 
>
> `scripts/shot.py`
>
>  一次产出桌面 + 移动整页截图；favicon 警告可忽略。



***

## 11. 常见翻车排查



| 现象                 | 原因                 | 处理                                                  |
| ------------------ | ------------------ | --------------------------------------------------- |
| 时间线 / 多列在公众号里堆叠或消失 | 用了 grid/flex/ 绝对定位 | 改为 §6.11 的 table 时间轴                                |
| 表格某列特别窄、中文一字一行     | 没固定列宽              | 加 `table-layout:fixed` 和 `<colgroup>`，列宽和 = 100%    |
| 圆点不见或变方块           | 用了伪元素 / 没给宽高       | 真实 `span`，`inline-block`+ 固定宽高 +`border-radius:50%` |
| 粘贴后字体全变样           | 只写网络字体、无 fallback  | 每个元素补系统字体栈                                          |
| 图片裂图 / 过期          | 用了外链地址             | 下载到本地 assets，用相对路径                                  |
| 背景渐变变色 / 丢失        | 渐变支持差              | 改纯色背景                                               |
| 手机端布局错乱、桌面正常       | 双列 / 固定宽未自适应       | table 列 + 百分比宽，看手机截图                                |
| 文章读起来 "像 AI"       | 句子工整、全是大词、没有 "我"   | 按 §8 重写，加具体画面和口语                                    |



***

### 给执行 AI 的提示



* 先判断这篇是否需要 "多列 / 图片 / 对齐"—— 需要就直接上 table，不要先写 grid 再返工。

* 严格按 §4 的 Token 和 §6 的组件，保证系列视觉统一；不要每次重新发明配色。

* 写完用截图工具，桌面 + 手机双端确认，再按 §10 清单逐条核对后交付。

* 排版保证 "格式能完整拷贝"，文案保证 "去 AI 化、有温度"，两者缺一不可。