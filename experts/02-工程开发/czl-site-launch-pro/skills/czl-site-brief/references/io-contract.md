# 输入输出契约

本文件定义"什么算是完整的输入"和"什么算是合格的输出"。脚本的 JSON 结构与本文一致，
文档与代码对不上的地方，以脚本实际输出为准，并需要同步修本文。

---

## 一、输入契约

### S0 最小输入（可直接开工）

| 字段 | 类型 | 必填 | 示例 |
|---|---|---|---|
| `goal` | string | 是 | 让来店里的人先看到案例，再打电话 |
| `audience` | string | 是 | 成都开小店的人，30–45 岁，自己看店 |
| `action` | string | 是 | 打电话 / 加微信 |
| `scope_hint` | string | 是 | 先做 3 页：首页、案例、联系 |
| `project_path` | path | 否 | 已有项目时给出，没有就新建目录 |

S0 齐了就能进 W1。缺 `action`（看完要做什么）时不要开工——这是最常见的返工来源。

### S1 完整输入（一次做到位）

在 S0 基础上补：

| 字段 | 类型 | 说明 |
|---|---|---|
| `domain` | string | 正式域名，用于 canonical / sitemap |
| `channels` | string[] | 搜索、朋友圈、名片二维码、线下物料 |
| `devices` | string | 手机为主 / 桌面为主 |
| `deadline` | date | 硬期限 |
| `materials` | object | `{copy, images, logo, hosting, icp}` 五项，各标 有/无 |
| `maintainer` | string | 以后谁改内容，会不会改代码 |
| `needs` | string[] | 登录 / 支付 / 表单收信 / 多语言 |
| `out_of_scope` | string[] | 本期不做的事（必填，不能为空） |

### 输入不完整时的处理

| 缺什么 | 后果 | 处理 |
|---|---|---|
| `action` | 页面无转化目标 | 停在 W1，给三个选项让用户选 |
| 文案 | 页面全是占位 | 用占位先跑结构，交付时标红"占位" |
| 图片 | 用低质图硬撑 | 用色块占位，尺寸写死，避免上线后跳版 |
| 域名 | 无法生成 canonical/sitemap | 先跑相对配置，上线前补 |
| 备案 | 境内无法上线 | 在 W7 前明确告知，不当成上线后的事 |

---

## 二、输出契约

### 通用四段结构（每次交付都必须有）

```
结论：<能不能上 / 还缺什么，一句话>
证据：<脚本原始输出、截图、命令返回，可复现>
改动：<文件路径 + 一句话职责，逐个列>
未解决：<没验的、验不了的、等用户提供的>
```

"未解决"为空时必须写"无"，不许省略这一段。省略等于宣称全部验证过。

### 各工作流的产出物

| 工作流 | 产出 | 文件形态 |
|---|---|---|
| W1 | 立项单 | `brief.md`（结构见模板） |
| W2 | 选型结论 + 骨架 | 三句话结论 + 目录树 |
| W3 | 可运行空壳 | 代码 + `README.md` |
| W4 | 页面代码 | `.html/.css/.js` 或框架组件 |
| W5 | 索引资料 | 每页元信息 + `sitemap.xml` + `robots.txt` |
| W6 | 体检报告 | `audit.md` + 脚本 JSON |
| W7 | 上线手册 | `runbook.md` + 部署记录 |
| W8 | 观察表与复盘 | `watch.md` |

产出物统一放在用户项目的 `docs/` 下（若用户没有指定），命名不加日期后缀，靠版本号区分。

---

## 三、脚本 JSON 契约

### project_scan.py

```json
{
  "root": "绝对路径",
  "kind": "static | next | nuxt | astro | vue | react | vite | svelte | node-other | unknown",
  "evidence": ["package.json:next@14.2.3"],
  "version": "next@14.2.3 或 null",
  "dependencies": ["依赖名，最多 40 个"],
  "entry_files": ["index.html"],
  "counts": {
    "html": {"files": 3, "bytes": 12000},
    "css": {"files": 1, "bytes": 4000},
    "js": {"files": 1, "bytes": 900},
    "img": {"files": 1, "bytes": 8000},
    "font": {"files": 0, "bytes": 0},
    "other": {"files": 2, "bytes": 300},
    "total_bytes": 25200
  },
  "build_outputs": [{"dir": "dist", "files": 12, "bytes": 250000}],
  "serve_dir": "dist 或 .",
  "artifacts": {
    "robots_txt": true, "sitemap_xml": false, "page_404": true, "favicon": true,
    "dotenv_in_repo": false, "dotenv_example": true, "gitignore": true,
    "gitignore_covers_env": true, "configs": ["vercel.json"]
  }
}
```

### audit_html.py

```json
{
  "root": "...",
  "files": {"index.html": 2},
  "findings": [{
    "rule": "H011",
    "severity": "blocker | high | medium | low",
    "file": "index.html",
    "count": 3,
    "lines": [42, 51, 66],
    "first_note": "assets/img/a.jpg",
    "message": "规则说明",
    "fix": "具体修法"
  }],
  "counts": {"blocker": 1, "high": 2, "medium": 0, "low": 1},
  "verdict": "通过 | 有改进项 | 不通过",
  "failed": true,
  "unverified": ["对比度（需浏览器实际渲染）", "焦点顺序（需人工 Tab）", "真机字号与点击区域"]
}
```

`verdict` 判定：有 blocker 或 high → 不通过；否则有任意 finding → 有改进项；否则通过。
退出码由 `--fail-on`（默认 high）决定，与 `verdict` 是两件事，不要混用。

### budget_check.py

```json
{
  "root": "...",
  "budget": {"js_gzip_kb": 200, "css_gzip_kb": 60, "image_total_kb": 1200, "single_image_kb": 250,
             "font_total_kb": 300, "total_gzip_kb": 500, "single_file_kb": 2048, "html_gzip_kb": 60},
  "groups_kb": {"html": 12.3, "css": 4.1, "js": 132.0, "image": 318.0, "font": 0.0, "other": 0.4},
  "total_kb": 466.8,
  "over": ["图片（原始）318KB / 1200KB…"],
  "top_files": [{"path": "assets/img/hero.jpg", "kb": 318.0}],
  "verdict": "通过 | 超预算",
  "file_count": 18
}
```

文本类资源（html/css/js/json/xml）按 gzip 后计，图片字体按原始大小计——这是浏览器实际下载量的近似。

### seo_files.py

```json
{
  "base_url": "https://example.com",
  "pages": [{
    "file": "index.html",
    "url": "https://example.com/",
    "title": "...", "description": "...", "canonical": "https://example.com/",
    "robots": "", "excluded": false
  }],
  "indexed_count": 2,
  "warnings": ["about.html: 缺 canonical"],
  "written": false
}
```

### deploy_preflight.py

```json
{
  "project": "...",
  "serve_root": ".../dist",
  "findings": [{
    "id": "P03",
    "severity": "blocker",
    "message": "Stripe 生产密钥 出现在 dist/app.js:2",
    "evidence": "sk_l*****"
  }],
  "counts": {"blocker": 1, "high": 0, "medium": 2, "low": 3},
  "verdict": "可上线 | 有条件上线 | 不可上线",
  "failed": true
}
```

判定：有 blocker → 不可上线；有 high → 有条件上线；否则可上线。
`evidence` 中的凭据一律脱敏，只留前 4 位。

---

## 四、退出码约定（五个脚本统一）

| 码 | 含义 |
|---|---|
| 0 | 达到阈值之上没有问题，可继续 |
| 1 | 用法错误或路径不存在（用户要改的是命令） |
| 2 | 有达到阈值的问题（要改的是项目） |

脚本退出码只表达"要不要停"，不表达"哪条最严重"——严重程度看输出里的档位。

---

## 五、语言规范

- 报告用中文，代码注释用中文，变量名用英文。
- 结论句不超过 40 字，先给判断再给理由。
- 不写"建议进一步优化"这类空话，写"把 hero.jpg 从 318KB 压到 120KB 以下"。
- 数字带单位，阈值写清来源（本目录的阈值表）。
