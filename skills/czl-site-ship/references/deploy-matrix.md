# 部署方式对照

选部署先看两件事：**产物是纯静态还是要跑服务**，**主要用户在哪**。

---

## 一、四类方式

| 方式 | 适用 | 成本量级 | 抗压 | 运维负担 | 回滚 |
|---|---|---|---|---|---|
| 静态托管 / Pages | 纯静态站，要 PR 预览 | 低（有免费额度） | 强 | 几乎为零 | 平台内置历史部署，一键回退 |
| 对象存储 + CDN | 纯静态站，流量大，要控成本 | 低 | 最强 | 低 | 保留上一版目录，替换 + 刷新 |
| 云服务器 + 反向代理 | 要跑后端、定时任务 | 中 | 看配置 | 高（补丁、证书、日志） | 换软链 + 重载，或镜像快照 |
| 容器 / 平台服务 | 有团队、要多环境 | 中高 | 强 | 中 | 回滚镜像 tag |

**判断口径：** 只有 HTML/CSS/JS/图片 → 前两类，不要为了"以后可能要后端"先养一台服务器。真有后端再加。

---

## 二、域名解析

| 记录 | 主机 | 指向 | 用途 |
|---|---|---|---|
| A | `@` | 服务器公网 IP | 根域名直连 |
| A | `www` | 同上，或 CNAME 到 CDN | 带 www 访问 |
| CNAME | `www` / 子域 | 托管平台给的地址 | 平台托管 |
| TXT | `@` | 平台验证值 | 域名归属验证 / 邮件 SPF |
| CAA | `@` | 证书颁发机构 | 限制谁能签证书（可选） |

规矩：

- 根域名不能用 CNAME（标准限制），要 CNAME 就用 `www` 或子域
- 解析生效时间看 TTL，改完别反复改，等
- 定一个主域，另一个 301 过去，不要两个都留着

验证：

```bash
dig +short example.com          # 是否返回预期 IP
dig +short www.example.com CNAME
curl -I https://example.com     # 证书与状态码
curl -I http://example.com      # 应 301 到 https
```

---

## 三、HTTPS

| 方式 | 适用 | 注意 |
|---|---|---|
| 平台自动证书 | 托管平台 | 域名解析对了就自动签，最省事 |
| 免费证书（Let's Encrypt 类） | 自建服务器 | 必须配自动续期，否则 90 天后全站报错 |
| 商业证书 | 有合规要求 | 贵，且不会让站更快 |

签发失败的三个常见原因：80 端口不可达、CDN 代理挡住了验证、域名没解析到目标。

强制 HTTPS：服务器 301 跳转，或平台开启 "Always Use HTTPS"。开启后确认没有资源还用 `http://` 引用，否则会被当混合内容拦掉。

---

## 四、缓存策略（静态站通用）

| 资源 | Cache-Control |
|---|---|
| HTML | `public, max-age=0, must-revalidate`（要能立刻更新） |
| 带 hash 的 JS/CSS | `public, max-age=31536000, immutable` |
| 图片/字体 | `public, max-age=31536000` |
| `robots.txt` / `sitemap.xml` | `public, max-age=3600` |

配置文件按平台写：`_headers`（多数静态托管）、`vercel.json`、`netlify.toml`、nginx `location` 段。

nginx 参考：

```nginx
location /assets/ {
    add_header Cache-Control "public, max-age=31536000, immutable";
}
location = /index.html {
    add_header Cache-Control "public, max-age=0, must-revalidate";
}
location / {
    try_files $uri $uri/ /404.html;
}
```

`try_files` 最后那段决定 404 行为，写错会变成"任何不存在的地址都返回首页 + 200"，这是收录上的坑。

---

## 五、各方式的回滚

| 方式 | 回滚动作 | 前提 |
|---|---|---|
| 静态托管 | 控制台选上一个部署 → Promote | 平台保留历史（多数默认保留） |
| 对象存储 + CDN | 把上一版目录覆盖回去 → 刷新 CDN | 上线前把上一版另存一份 |
| 云服务器 | `ln -sfn releases/<上一版> current && nginx -s reload` | 用 releases 目录 + 软链发布 |
| 容器 | 把 tag 指回上一个镜像并重启 | 镜像 tag 不可变 |

服务器发布的最小做法：

```bash
# 发布
rsync -av --delete dist/ user@host:/srv/site/releases/20261027-1/
ssh user@host 'ln -sfn /srv/site/releases/20261027-1 /srv/site/current && nginx -s reload'

# 回滚（把软链指回上一版，不需要重新上传）
ssh user@host 'ln -sfn /srv/site/releases/20261020-1 /srv/site/current && nginx -s reload'
```

软链发布的意义就在这：回滚是一条命令，不用等文件传输。

---

## 六、境内上线的硬前提

- 用境内服务器（含境内对象存储的自定义域名）→ **必须先完成 ICP 备案**，未备案会被阻断
- 备案主体、域名持有者、服务器购买者三者要一致，不一致会被驳回
- 备案期间可以用平台临时域名先看效果，但不要对外宣传正式域名
- 域名实名认证是备案前置条件，通常要等实名生效（几小时到一天）

这些是流程问题，不是技术问题——**在买服务器之前就要确认**，否则钱花了站点上不了线。

---

## 七、上线验证清单（命令级）

```bash
curl -I https://example.com                 # 200，且是 https
curl -I https://example.com/robots.txt      # 200
curl -I https://example.com/sitemap.xml     # 200，content-type 是 xml
curl -I https://example.com/not-exist-page  # 404（不是 200）
curl -s https://example.com | head -20      # 首屏 HTML 里有真实内容
```

最后一条最关键：如果 `curl` 拿到的 HTML 里没有正文（只有一个空的 `<div id="app">`），
说明内容是 JS 渲染的，搜索和分享都拿不到内容——这是收录问题的根源。
