---
name: czl-site-build
description: |
  Gate W4-W6: build pages, make them indexable, and pass accessibility plus weight audits with bundled scripts.
  TRIGGER when: pages must be written or repaired; titles, descriptions, canonical, JSON-LD, robots.txt or sitemap.xml are missing;
  images lack alt text, forms lack labels, or the bundle is heavier than the budget.
  DO NOT TRIGGER when: the brief is not locked yet, or the job is purely deployment.
description_zh: "页面实现、索引资料与无障碍体积体检"
description_en: "Page build, indexing assets and a11y/weight audit"
version: 1.0.0
license: "SEE LICENSE IN LICENSE.txt"
metadata:
  category: engineering
  owner: 虫志龙
---

# 闸门 W4–W6：页面、索引、体检

这三道闸的交界处是最容易糊弄的地方。页面看着能开，但搜不到、读屏读不出、手机打开要等五秒——这些都是"能开但不合格"。

**规矩：每写完一页就跑一次体检，不要等全站写完。** 一页的问题改起来五分钟，二十页同样的问题改起来一天。

---

## 何时用

- 骨架能跑，要往里填内容和样式
- 页面做完了，要检查能不能被搜到、被读屏读出来、够不够轻
- 用户说"我这站怎么百度搜不到""手机上打开很慢"

---

## W4 · 页面

顺序不能颠倒：**语义结构 → 样式 → 交互 → 内容微调**。先写样式再补结构，语义一定丢。

### 结构四条

1. 一页一个 `<h1>`，写这页到底讲什么；`<h2>` 是分块，不能跳级
2. 用 `<header> <nav> <main> <footer>` 圈区，而不是一堆 `<div>`
3. 按钮用 `<button>`，跳转用 `<a href>`。用 `<div onclick>` 的，键盘按不动
4. 表单每个字段有 `<label for>`；占位符 `placeholder` 不是标签

### 样式三条

1. 移动优先：先写手机样式，再用 `min-width` 往上加
2. 视口高度用 `100dvh`，不用 `100vh`（手机浏览器地址栏会让 100vh 溢出）
3. 正文行宽 45–75 字符，行高 1.5–1.8；小于这个范围读起来累

### 交互三条

1. 所有交互有反馈：悬停、按下、加载中、失败，四态缺一不可
2. 表单提交前校验，提交后给明确结果（成功/失败/正在发）
3. 异步失败要有兜底文案，不能只 `console.log`

代码规范细则见 `references/code-rules.md`。

---

## W5 · 索引

搜索看得见，靠的不是关键词堆砌，是四样东西齐不齐。

| 要素 | 写法 | 阈值 |
|---|---|---|
| `<title>` | 页面主题 + 品牌，不做标题党 | 10–60 字符，每页唯一 |
| `meta description` | 这页能解决什么，一句人话 | 50–160 字符 |
| `link rel=canonical` | 指向这页的唯一正式地址 | 每页一条，绝对 URL |
| `og:title/description/image` | 分享到微信/社交平台时的样子 | 图片 1200×630 |

再加三样：

- **结构化数据**：企业站用 `Organization` + `LocalBusiness`，文章用 `Article`，商品用 `Product`。写在 `<script type="application/ld+json">` 里，字段只写真实存在的（没有评分就别写评分，写了会被判作弊）。
- **robots.txt**：允许抓取，指向 sitemap。测试环境必须 `Disallow: /`，见过太多测试站被收录。
- **sitemap.xml**：只放要收录的页面，404 和后台页不放。

生成与校验用脚本，不要手写：

```bash
python scripts/seo_files.py <产物目录> --base-url https://example.com          # 先看
python scripts/seo_files.py <产物目录> --base-url https://example.com --write  # 落盘
```

---

## W6 · 无障碍与体积

两个脚本，一个管"能不能用"，一个管"够不够轻"。

```bash
python scripts/audit_html.py <目录或单页> --fail-on high
python scripts/budget_check.py <产物目录>
```

`audit_html.py` 的规则编号分四档：

| 档位 | 含义 | 处理 |
|---|---|---|
| BLOCKER | 读屏器/键盘用户直接无法使用 | 必须改，改完重跑 |
| HIGH | 明显影响可用性或收录 | 必须改 |
| MEDIUM | 影响体验或分享效果 | 本轮尽量改 |
| LOW | 规范建议 | 记录，不阻塞 |

`budget_check.py` 用 gzip 后的真实体积对比预算（默认：JS ≤ 200KB、CSS ≤ 60KB、单图 ≤ 250KB、首屏合计 ≤ 500KB）。超了就看它列出的最大文件，通常前三个就能砍掉一半。

### 修的顺序

1. 先改 BLOCKER（alt、label、标题层级、lang）
2. 再砍体积（换 WebP、删未用字体、拆大图、去重复依赖）
3. 最后处理 MEDIUM/LOW

### 脚本管不了、必须人看的三件事

- **对比度**：脚本能算出你写的颜色对，但算不出叠加半透明和图片背景后的实际效果。给用户颜色对，让他用浏览器 DevTools 的对比度检查器确认。
- **焦点顺序**：Tab 键一路按下去是否跟视觉顺序一致。这个只能按。
- **真实设备**：手机真机上的字号、点击区域（≥44×44px）。模拟器不算。

---

## 判断条件

| 体检结果 | 判断 | 动作 |
|---|---|---|
| 有 BLOCKER | 不可交付 | 改完重跑，直到 0 条 |
| 只有 MEDIUM/LOW | 可交付 | 列清单交给用户决定改不改 |
| 体积超预算 < 20% | 可上线 | 给出优化清单，下一轮处理 |
| 体积超预算 > 50% | 不可上线 | 先优化再谈上线，尤其是移动端流量站 |
| 图片是设计给的 PSD/JPG 大图 | 阻塞 | 先转 WebP + 按显示尺寸裁切，不要"先上线再优化" |

---

## 输出格式

```
体检结论：<通过 / 有条件通过 / 不通过>

阻塞项（必须改）
B1 [H010] index.html:42  <img> 缺 alt —— 修法：写清图片内容；装饰图写 alt=""
B2 ...

待改项（本轮建议）
H1 [H024] about.html  h1 有 2 个 —— 修法：把第二个降为 h2

体积
JS 132KB / 200KB ✅ ｜ CSS 41KB / 60KB ✅ ｜ 最大单图 318KB / 250KB ❌
超预算主因：hero.jpg 318KB

未验证
- 对比度：需在浏览器确认（颜色对 #777 on #fff）
- 焦点顺序：需人工 Tab 走查
```

---

## 异常处理

- **图片确实无法加 alt**（纯装饰）：写 `alt=""`，不是删掉属性。删掉属性读屏器会念文件名。
- **标题必须两个才符合设计**：视觉两个标题、语义一个 `<h1>`，另一个用 `<p class="...">` 加样式。
- **字体文件很大**：先子集化（只留用到的字），再考虑 `font-display: swap`。中文字体整包 5–10MB，直接引就是灾难。
- **用户不同意改结构**（"设计就这样"）：把 BLOCKER 折算成具体后果说给他听（"读屏用户听不到这张图是什么，等于这张图对他们是空的"），让他决定，不要擅自改设计。
- **脚本报了你认为是误报**：先确认，再记录到报告"已知误报"一节。不许直接忽略不写。

---

## 与其他技能的关系

- 上游：`czl-site-brief` 给立项单与骨架
- 下游：`czl-site-ship` 接收体检报告，把 BLOCKER 清零后才准上线
- 归因：老站问题先看 `references/failure-catalog.md`，按症状定位到具体闸
