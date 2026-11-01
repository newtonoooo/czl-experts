---
name: czl-dev-build
description: |
  Implementation conventions for full-stack features: folder layout, configuration, failure handling,
  logging, data access, API contracts, and the wiring between server and client.
  TRIGGER when: scaffolding a new service or module, adding an API endpoint, wiring a client to a server,
  handling config/auth/secrets, designing failure responses, or fixing N+1 and over-fetching problems.
  DO NOT TRIGGER when: pure visual styling, a single-file script, a bug fix with an obvious cause,
  or when the existing codebase already has conventions that should simply be followed.
description_zh: "全栈实现约定：结构、配置、错误、日志、数据、接口、前后端集成"
description_en: "Implementation conventions for full-stack features"
version: 1.0.0
license: "SEE LICENSE IN LICENSE"
metadata:
  category: development
  owner: 虫志龙
---

# 实现约定

这里写的是一套默认约定，不是规范教条。

**优先级：现有代码的写法 > 本文档。** 接手一个已经有自己风格的项目时，跟现有风格走，不要为了符合这套约定去动一片本来能跑的区域。改动的价值必须大于改动带来的风险。

---

## 何时用

- 新起一个服务或模块（决定目录结构、配置方式）
- 加一个接口（决定响应结构、错误码、鉴权位置）
- 前端要接后端（决定 client 层、错误映射）
- 数据查询变慢或有 N+1（决定查询写法）
- 配置散落各处、启动时不该带病跑（决定配置层）

---

## 五个约定

### 一、目录按功能分，不按技术层平铺

```
src/
  orders/            ← 一个功能一个目录
    order.routes.ts    入口，只做参数校验与调用
    order.service.ts   业务规则，不碰 HTTP 对象
    order.repo.ts      数据访问，SQL 只出现在这一层
    order.types.ts      类型与常量
  payments/
  shared/
    config.ts         ← 唯一读环境变量的地方
    errors.ts         ← 错误类型定义
    logger.ts
```

判断依据：**改一个功能，打开的目录应该集中在一处。** 如果改"下单金额计算"要同时打开 `controllers/`、`services/`、`models/`、`utils/` 四个地方，说明结构还是按技术层铺的。

例外：团队已有分层结构且规模不大（< 20 个功能模块）时，不必搬迁。新功能用新结构即可。

### 二、配置集中，启动即校验

- 只有 `config.ts` 一处读 `process.env` / `os.environ`，其他地方 import 配置对象
- 启动时校验必填项，缺了就**立即失败并打印缺哪个**，不做"用默认值凑合"
- 提供 `.env.example`，列出全部键名与格式，值留空或写占位符
- 密钥只从环境变量来，不写进代码、不写进样例文件、不写进日志

判断依据：**换一台机器，只看 `.env.example` 能不能把服务起起来。**

### 三、错误分层，对外只说该说的

| 层 | 内容 | 给谁看 |
|---|---|---|
| 业务错误 | 错误码 + 用户能懂的提示 | 前端与用户 |
| 系统错误 | 类型 + 堆栈 + 上下文 | 日志 |
| 对外响应 | 统一结构，只含错误码与提示 | 客户端 |

硬约束：**外泄检查** —— 响应体里不能出现表名、字段名、文件路径、SQL 片段、依赖库版本、内网地址。做一次故意触发错误的验证，看返回了什么。

### 四、日志一行一条，能追

- 结构化（JSON 或 key=value），不要拼字符串
- 每条带：时间、级别、请求标识、动作、结果
- 敏感字段（密码、令牌、手机号、身份证）不打印原值；需要排查时打印哈希或后四位
- 生产环境默认不打调试级

判断依据：**收到一个用户投诉，能不能凭一条请求标识把整个链路捞出来。**

### 五、查询条件在 SQL 里

这条最容易犯，也最容易查：

```js
// 不要：全表捞出，在应用层筛
const all = await db.query('SELECT * FROM orders');
const mine = all.filter(o => o.userId === uid);

// 要：条件下推
const mine = await db.query('SELECT * FROM orders WHERE user_id = ? LIMIT ? OFFSET ?', [uid, size, offset]);
```

三条纪律：

1. 分页必须在 SQL 层，不允许"查全部再切片"
2. 循环里查库（N+1）要合并成一次 `IN` 查询或 join
3. 改查询前先看实际执行的 WHERE，不要凭函数名猜。参数化，不拼字符串

---

## 接口约定

| 项 | 约定 |
|---|---|
| 成功响应 | `{ "ok": true, "data": ... }` |
| 失败响应 | `{ "ok": false, "code": "ORDER_NOT_FOUND", "message": "订单不存在" }` |
| 状态码 | 参数错 400、未登录 401、无权限 403、不存在 404、冲突 409、限流 429、服务错 500 |
| 分页 | 入参 `page` / `pageSize`（上限 100），出参带 `total` |
| 时间 | 一律 UTC ISO 8601，前端负责本地化 |
| 幂等 | 写操作支持幂等键（请求头或表单字段），重复请求返回同一结果 |
| 校验 | 在入口处校验，进 service 的数据视为已校验 |

---

## 前端集成

- 所有请求走一个 client（统一 baseURL、超时、鉴权头、错误映射）
- 接口地址不写在页面组件里
- 错误统一映射为可读提示；开发环境保留原始错误码便于排查
- 加载态、空态、错误态三态都要有，不能只有成功态
- 表单提交按钮在请求期间禁用，防重复提交；服务端仍要做幂等（前端禁用不可靠）

---

## 深入

| 主题 | 文件 |
|---|---|
| 目录拆分的判断信号、配置层实现、启动自检、构建一致性 | `references/项目结构与配置.md` |
| 幂等的三种实现、分页与深翻页、N+1 改法、索引与迁移、越权检查 | `references/接口与数据约定.md` |
| 错误类型体系、全局处理器、日志字段、脱敏、级别判定 | `references/错误处理与日志.md` |

---

## 自检清单

- [ ] 改一个功能，打开的文件集中在一个目录
- [ ] 只有一处读环境变量；缺配置启动即失败并指明缺哪项
- [ ] `.env.example` 完整，且不含真实值
- [ ] 故意触发一次错误，响应体里没有内部信息
- [ ] 日志能用请求标识串起一次完整调用
- [ ] 列表接口的过滤与分页在 SQL 里
- [ ] 没有循环查库
- [ ] 写接口有幂等处理
- [ ] 页面三态齐全

---

## 常见取舍

| 情况 | 建议 |
|---|---|
| 现有代码结构与本文冲突 | 服从现有结构，新模块用新约定 |
| 框架自带错误处理 | 用它，不要另建一套并行体系 |
| 小脚本 / 一次性任务 | 不必上这套约定，日志和错误处理做到够用即可 |
| 性能与可读性冲突 | 先可读，有实测瓶颈再优化，优化处写注释说明原因 |
