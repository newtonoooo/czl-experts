# 故障归因目录

用法：先照"看什么"跑命令，**用证据定位，不要用猜测定位**。排在前面的原因出现概率更高，
按顺序排除，不必跳着猜。

归因结论写清三样：现象、证据、落回的闸门（W4 页面 / W5 索引 / W6 体检 / W7 预检 / W8 观察）。

---

## 1. 上线后整页白屏

| 顺序 | 可能原因 | 怎么验证 | 修法 | 闸门 |
|---|---|---|---|---|
| 1 | 资源 404（路径错/大小写） | 浏览器 Network 面板，看红色项；`curl -I https://域名/assets/js/app.js` | 改相对路径或部署路径；文件名统一小写 | W7 |
| 2 | JS 运行时异常 | Console 第一条报错 | 修代码；加错误边界 | W4 |
| 3 | 构建产物没上传完整 | 对比本地 `dist` 与服务端文件数 | 重传，校验文件数 | W7 |
| 4 | CDN 缓存了旧 HTML | `curl -I` 看 `age` 与 `etag` | 刷新 CDN，HTML 设短缓存 | W7 |

## 2. 上线后样式全丢

- 优先查 `base` / `publicPath` 配置（构建工具默认按站点根目录拼路径，部署在子目录就全错）
- 再查 MIME：CSS 被当 `text/plain` 返回时浏览器会拒绝生效（`curl -I` 看 `content-type`）
- 最后查缓存：强刷（Ctrl+Shift+R）能好就是缓存策略问题

## 3. 手机上排版错位

| 顺序 | 原因 | 验证 | 修法 |
|---|---|---|---|
| 1 | 缺 viewport meta | 看 head | 加 `width=device-width, initial-scale=1` |
| 2 | 固定宽度（`width: 1200px`） | 搜 CSS | 改 `max-width` + 百分比 |
| 3 | 用 `100vh` 做整屏 | 搜 CSS | 改 `100dvh` |
| 4 | 点击区域 < 44px | 真机按 | 加大 padding 或最小高度 |

## 4. 百度/谷歌搜不到

按这个顺序查，**不要一上来就写文章**：

1. `robots.txt` 是否 `Disallow: /`（测试环境配置带上了生产）
2. 页面是否有 `<meta name="robots" content="noindex">`
3. `sitemap.xml` 是否存在且包含该页
4. 页面是否由 JS 渲染（源码里 `<body>` 是空的 → 爬虫可能看不到内容）
5. 是否刚上线（新站收录要几天到几周，不是当天）
6. 域名是否被惩罚（查站长平台，不是猜）

对应闸门 W5。修复后主动提交 sitemap，不要等。

## 5. 打开很慢

| 顺序 | 原因 | 验证 | 修法 |
|---|---|---|---|
| 1 | 首图过大（>500KB） | `budget_check.py` 看 top_files | 压到 250KB 以下，改 WebP |
| 2 | 中文字体整包 | 看 font 分组体积 | 子集化或改系统字体 |
| 3 | JS 阻塞首屏 | `audit_html.py` 的 H017 | 加 `defer` |
| 4 | 没开 gzip/brotli | `curl -I` 看 `content-encoding` | 服务器开压缩 |
| 5 | 没设缓存头 | 看 `cache-control` | 静态资源长缓存 + 文件名带 hash |

对应闸门 W6。

## 6. 图片不显示

- 路径大小写（`Img/A.jpg` vs `img/a.jpg`）
- 后缀与实际格式不符（把 webp 存成 jpg 扩展名）
- 防盗链（第三方图床）
- `srcset` 里写了不存在的尺寸

## 7. 表单提交收不到

| 原因 | 验证 | 修法 |
|---|---|---|
| 前端只 `preventDefault` 没发请求 | Network 面板有无请求 | 补 `fetch` |
| 接口跨域被拦 | Console 有 CORS 报错 | 服务端加 `Access-Control-Allow-Origin`（客户端改不了） |
| 邮箱进了垃圾箱 | 换邮箱测 | 配 SPF/DKIM，或改用表单服务 |
| 提交到测试地址 | 查 API 常量 | 改生产地址 |

跨域是服务端问题，这一点不要让用户去改前端。

## 8. HTTPS 证书报错

| 现象 | 原因 | 修法 |
|---|---|---|
| `ERR_CERT_COMMON_NAME_INVALID` | 证书域名与实际访问域名不一致（带不带 www） | 重签含两个域名的证书 |
| `ERR_CERT_DATE_INVALID` | 过期 | 续期，配自动续期 |
| 签发一直失败 | 80 端口不可达 / CDN 代理挡住验证 / 解析未生效 | 先 `dig`，再临时关代理 |
| 部分资源仍 http | 混合内容 | 全站改 https，加 `upgrade-insecure-requests` |

## 9. 上线后 404 循环

- 静态托管把 `/about` 当目录找 `about/index.html`，实际文件是 `about.html`
- SPA 的 history 路由没有回退到 `index.html` 的规则
- 尾斜杠策略不一致（`/about/` vs `/about`）

修法：定一种 URL 形态，全站统一，其余 301 过去。

## 10. 中文乱码

- 缺 `<meta charset="utf-8">`
- 服务器返回 `content-type` 里 charset 写的是 gbk
- 文件本身不是 UTF-8 保存（Windows 记事本默认 ANSI）

三者排查顺序按上表，别一上来改代码。

## 11. 分享到微信没有卡片

- 缺 `og:title` / `og:description` / `og:image`
- 图片不是绝对 URL，或尺寸不是 1200×630
- 微信缓存了旧信息（换参数强制刷新）

对应闸门 W5。

## 12. 部署平台构建失败、本地成功

| 顺序 | 原因 | 验证 |
|---|---|---|
| 1 | Node 版本不同 | 看平台构建日志第一行的版本 |
| 2 | 大小写敏感（Linux vs Windows） | 搜 import 路径与实际文件名 |
| 3 | 环境变量没配 | 对比 `.env.example` 与平台变量列表 |
| 4 | 依赖锁文件与 `package.json` 不一致 | 删 `node_modules` 重装后看锁文件变化 |
| 5 | 构建内存超限 | 日志里有 OOM 字样 |

按日志改，不要靠改配置试错。
