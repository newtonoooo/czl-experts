# 编码规矩

只收"不遵守就一定会出事"的条目。每条写清：为什么、错在哪、怎么改。

---

## 一、HTML

**1. 一个页面一个 `<h1>`，写这页在说什么。**
读屏器用标题跳读，搜索用标题判断主题。两个 h1 等于告诉机器"这页有两个主题"。

```html
<!-- 错：视觉上两个大标题，语义上也两个 -->
<h1>青禾设计</h1>
<h1>只做小店面的装修</h1>

<!-- 对：一个是标题，一个用段落加样式 -->
<h1>只做小店面的装修</h1>
<p class="lede">青禾设计 · 成都</p>
```

**2. 按钮和链接不要混用。**
`<a>` 是去别的地方，`<button>` 是就地做事。用 `<div onclick>` 的，键盘按不动、读屏念不出。

**3. 表单字段必须有可访问名称。**
`placeholder` 不是名称——输入后它就消失了，读屏器也读不到。

```html
<label for="phone">手机号</label>
<input id="phone" name="phone" type="tel" autocomplete="tel">
```

**4. 图片写 `width`/`height`。**
不是为了排版，是为了让浏览器提前留出位置。不写就会跳版（CLS 的直接来源）。

**5. 装饰图写 `alt=""`，不是删掉 alt。**
删掉属性，读屏器会念出文件名 `hero-final-v3.jpg`。

---

## 二、CSS

**6. 先建变量，再写样式。**
颜色、间距、字号各一套变量，改版时只改一处。

```css
:root {
  --ink: #1d1d1f;
  --muted: #5b5b60;
  --gap: 16px;
  --radius: 6px;
}
```

**7. 移动优先，断点从少到多。**
先写手机样式，再用 `min-width` 加。反过来写（桌面优先 + `max-width`）会让覆盖关系越来越乱。

**8. 高度用 `100dvh`，不用 `100vh`。**
手机浏览器地址栏伸缩时，`100vh` 会超出可视区，底部按钮被推到屏幕外。

**9. `z-index` 只在定位元素上生效。**
写了 `z-index` 没反应，九成是忘了 `position`。

**10. `calc()` 里运算符两侧必须留空格。**
`calc(100%-20px)` 无效，`calc(100% - 20px)` 才对。

**11. 不靠 `!important` 打架。**
出现第三个 `!important` 时，说明选择器层级已经失控，该重构而不是继续加。

---

## 三、JavaScript

**12. `===` 而不是 `==`。**
`'0' == false` 为真，这类隐式转换是线上 bug 的常见来源。

**13. `querySelector` 结果先判空。**
元素不存在时是 `null`，直接取属性就白屏。

```js
const form = document.querySelector('form');
if (!form) return;
```

**14. `forEach` 不等异步。**
需要按顺序等待就用 `for...of`，需要并行就 `Promise.all`。

```js
// 错：三个请求并发，但循环在请求回来前就结束了
items.forEach(async (id) => { await save(id); });

// 对
for (const id of items) { await save(id); }
```

**15. 不要把用户输入塞进 `innerHTML`。**
用 `textContent`，或建节点。`innerHTML` 等于给注入开门。

**16. 交互要有四态：默认、悬停/聚焦、加载中、失败。**
只做前两个的交互，用户点了没反应就会连点，然后重复提交。

**17. 事件绑在容器上，不绑在每一项上。**
列表可能动态增加，绑在容器上（事件委托）不会漏。

---

## 四、资源

**18. 图片按显示尺寸出图，不靠 CSS 缩小。**
4000px 的图显示成 400px，用户下载了 10 倍不该下载的数据。

**19. 优先 WebP/AVIF，保留回退。**
```html
<picture>
  <source srcset="hero.avif" type="image/avif">
  <source srcset="hero.webp" type="image/webp">
  <img src="hero.jpg" alt="..." width="1200" height="800">
</picture>
```

**20. 中文字体不要整包引。**
整包 5–10MB。要么子集化，要么用系统字体栈。

**21. 首屏关键 CSS 内联，其余异步。**
小站直接把 CSS 放一个文件里，别拆太碎——每个文件都是一次往返。

---

## 五、安全

**22. 前端没有秘密。**
`NEXT_PUBLIC_`、`VITE_`、`PUBLIC_` 前缀的变量都会进浏览器。密钥只放服务端。

**23. 外链加 `rel="noopener"`。**
`target="_blank"` 不加，新页面能通过 `window.opener` 操作原页面。

**24. 提交前扫一遍产物。**
`deploy_preflight.py` 会查密钥、localhost、sourcemap。上线前跑，不要靠记性。

**25. 表单提交要有服务端校验。**
前端校验只是体验，不是安全边界。

---

## 六、文件与命名

**26. 文件名用小写加连字符。**
`case-list.html` 而不是 `CaseList.html`。某些服务器大小写敏感，本地能跑线上 404。

**27. 一个文件一个职责。**
`site.css` 管全站，`page-contact.css` 只管联系页。出现 `style2.css` 就该合并。

**28. 注释写"为什么"，不写"做了什么"。**
```js
// 错：给按钮加点击事件
// 对：这里必须用 click 而不是 submit，否则校验失败时浏览器会先跳走
```

**29. 每个项目根目录一份 README，写三件事。**
怎么改、怎么发、改坏了怎么退。没有这份文件的项目，三个月后没人敢动。
