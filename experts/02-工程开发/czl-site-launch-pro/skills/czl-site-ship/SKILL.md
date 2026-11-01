---
name: czl-site-ship
description: |
  Gate W7-W8: run the deploy preflight, ship to a host, and watch the first 72 hours with a rollback plan ready.
  TRIGGER when: a site is about to go live; keys may leak into the bundle; localhost URLs or missing 404 pages must be caught;
  a host, DNS record, HTTPS certificate or cache policy must be configured; something broke after release and rollback must be decided.
  DO NOT TRIGGER when: pages are still being written or the audit still has blockers.
description_zh: "上线预检、部署执行与 72 小时观察"
description_en: "Deploy preflight, release and 72-hour watch"
version: 1.0.0
license: "SEE LICENSE IN LICENSE.txt"
metadata:
  category: engineering
  owner: 虫志龙
---

# 闸门 W7–W8：预检、上线、观察

上线的本质不是"把文件传上去"，是**做一个可以撤销的动作**。

没有回滚方案的上线请求，应该被拒绝——包括用户说"就改一个字，直接传吧"的那种。

---

## 何时用

- 站要上线了，做最后一次体检
- 要选托管方案、绑域名、配 HTTPS
- 上线后白屏、404、证书报错、样式丢失
- 要交一份"以后出事照着做"的手册

---

## W7 · 上线预检

先跑脚本，再谈部署。脚本查 15 项，其中 5 项是硬阻塞。

```bash
python skills/czl-site-ship/scripts/deploy_preflight.py <项目目录> [--dist 产物目录]
```

| 编号 | 检查 | 档位 | 不过怎么办 |
|---|---|---|---|
| P01 | 构建产物存在且非空 | BLOCKER | 先跑构建，别传源码目录 |
| P02 | `.env` / 密钥文件出现在产物或仓库根 | BLOCKER | 移出并加 `.gitignore`，已提交的要轮换密钥 |
| P03 | 私钥、云厂商令牌、支付密钥出现在前端文件 | BLOCKER | 立即吊销并轮换，再改代码 |
| P04 | 硬编码密码/密钥赋值 | BLOCKER | 改为环境变量 + 服务端注入 |
| P05 | 产物中残留 `localhost` / `127.0.0.1` | BLOCKER | 换成正式域名或相对路径 |
| P06 | 产物中 `http://` 资源引用 | HIGH | 改 https，否则浏览器拦混合内容 |
| P07 | 缺 404 页面 | HIGH | 加 `404.html`，静态托管才能接管 |
| P08 | 缺 robots.txt / sitemap.xml | MEDIUM | 用 `seo_files.py --write` 生成 |
| P09 | 缺 favicon | LOW | 加 32×32 与 180×180 |
| P10 | 单文件 > 2MB | HIGH | 压缩或拆分 |
| P11 | 代码引用的环境变量未在 `.env.example` 声明 | MEDIUM | 补声明，否则部署平台配不全 |
| P12 | 产物里有 `.map` 源映射 | MEDIUM | 生产关掉 sourcemap，或限制访问 |
| P13 | `console.log` 残留 | LOW | 生产构建剥离 |
| P14 | 无缓存策略配置 | MEDIUM | 加 `_headers` / `vercel.json` / `netlify.toml` |
| P15 | 无版本号或发布标识 | LOW | 打 tag 或写 `RELEASE`，否则回滚不知道退回哪 |

退出码 0 = 可上线，2 = 有阻塞。**BLOCKER 未清零时，不给上线命令。**

### 平台怎么选

| 情形 | 选 | 理由 |
|---|---|---|
| 纯静态、无服务端 | 对象存储 + CDN（或静态托管） | 便宜、抗压、几乎不会挂 |
| 需要预览环境、PR 预览 | 托管平台（Vercel/Netlify/Cloudflare Pages） | 每次提交自动出预览链接 |
| 需要后端、定时任务 | 云服务器 + 反向代理 | 控制力强，运维成本也高 |
| 主用户在境内 | 境内云 + 备案 | 备案是前置条件，不是上线后再补 |

对比细节与备案要求见 `references/deploy-matrix.md`。**境内服务器必须备案，这一步在买服务器之前就要确认**，不是上线前才想起来。

### 域名与证书

顺序不能错：解析 → 生效 → 签证书 → 强制 HTTPS。反过来做必然失败。

```bash
dig +short example.com            # 看解析是否生效（或 nslookup）
curl -I https://example.com       # 看证书与跳转
curl -I http://example.com        # 应 301 到 https
```

---

## W8 · 上线后 72 小时

上线不是终点。前 72 小时是问题暴露最集中的窗口。

| 时点 | 看什么 | 异常阈值 | 动作 |
|---|---|---|---|
| 立刻 | 首页 200、关键页 200、404 页正常 | 任一 5xx | 立即回滚 |
| 立刻 | 静态资源加载（CSS/JS/图）全部 200 | 任一 404 | 修路径或回滚 |
| +1 小时 | 表单/联系入口能收到 | 收不到 | 查后端或第三方服务 |
| +24 小时 | 错误日志、慢请求 | 5xx > 1% 或首屏 > 3s | 定位，不改主链路 |
| +72 小时 | 收录提交状态、真实设备抽查 | 收录 0 且 robots 正常 | 提交 sitemap，等 |

### 回滚三种方式（按优先级）

1. **平台回滚**：托管平台保留历史部署，点一下回上一版。最快，优先用。
2. **产物回滚**：保留上一版产物目录，替换后刷新 CDN。需要上线前留一份。
3. **代码回滚**：`git revert` 后重新构建部署。最慢，只在 1、2 都不可用时用。

**回滚命令必须在上线前写下来，并且真的执行过一次。** 没演练过的回滚方案等于没有。

### 事故处理顺序

止血 → 恢复 → 查因 → 防复发。顺序不能颠倒：不要在用户访问不了的时候研究根因。

---

## 判断条件

| 情形 | 判断 | 动作 |
|---|---|---|
| BLOCKER > 0 | 不可上线 | 清零再谈，不给部署命令 |
| 仅 MEDIUM/LOW | 可上线 | 列清单，约定下一轮 |
| 首次上线且无回滚演练 | 有条件上线 | 先演练一次回滚，或先发到预览环境 |
| 只改文案 | 可简化预检 | 跳过 P11/P12，P01–P07 仍要跑 |
| 上线后 5xx | 立即回滚 | 先恢复，再查因 |
| 证书报错 | 不可上线 | 多半是 DNS 未生效或证书域名不匹配，先查这两个 |

---

## 输出格式（上线手册）

```
上线结论：可上线 / 有条件上线（条件：…） / 不可上线（原因：…）

预检
P01 ✅ P02 ❌（.env 在产物根目录）… 共 15 项：过 13 / 阻塞 2

部署步骤
1. <命令>　验证：<怎么确认成功>
2. ...

回滚
命令：<可直接复制>
已验证：<在什么环境演练过，结果>

72 小时观察
<表：时点 / 看什么 / 阈值 / 谁盯>
```

模板见 `templates/runbook.md`。

---

## 异常处理

- **构建在平台侧失败但本地成功**：九成是环境差异（Node 版本、大小写敏感、环境变量缺失）。让用户贴平台构建日志，按日志改，不要猜。
- **域名解析不生效**：先 `dig` 看是否返回目标 IP，再看 TTL。改完 DNS 等 10 分钟到 48 小时是正常的，别反复改记录。
- **HTTPS 证书签发失败**：检查 80 端口是否可达（很多验证方式要求）、是否有 CDN 代理挡着、域名是否已正确解析。
- **上线后样式全丢**：路径问题（绝对路径 vs 相对路径）或 CDN 缓存了旧 HTML。先强刷验证，再查 `base` 配置。
- **用户坚持不演练回滚**：在手册里写明"回滚未演练，风险自担"，并把这句话原文交给用户确认。不替他承担这个决定。

---

## 与其他技能的关系

- 上游：`czl-site-build` 的体检报告（BLOCKER 必须为 0）
- 上游：`czl-site-brief` 的渠道信息（决定要不要做多语言/多落地页）
- 下游：上线后发现问题 → 回到 `czl-site-build` 修，修完重跑 W6，再走 W7
