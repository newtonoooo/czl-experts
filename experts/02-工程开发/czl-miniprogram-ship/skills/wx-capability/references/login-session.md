# 登录态：从 code 到自己的 token

> 微信接口名、参数与返回字段以官方「登录态 / wx.login / code2Session」文档为准。本文讲的是**工程上怎么摆才不出安全事故**。

## 一、正确链路（一张图看完）

```
小程序                你的服务端                    微信服务器
  |                       |                            |
  |-- wx.login() -------->|                            |
  |   得到 code            |                            |
  |-- POST /login(code) ->|                            |
  |                       |-- code + appid + secret -->|
  |                       |<-- openid + session_key ---|
  |                       |                            |
  |                       | 生成自己的 token           |
  |<-- { token, expires }-|                            |
  |                       |                            |
  |-- 业务请求 + token -->|  校验 token → 取 openid     |
```

**关键点：`session_key` 永远不出服务端。** 前端拿到它等于把用户身份钥匙交给客户端。

## 二、前端代码

```js
// utils/auth.js
const TOKEN_KEY = 'app_token';
const EXPIRE_KEY = 'app_token_expire';

function getToken() {
  return wx.getStorageSync(TOKEN_KEY) || '';
}

function isExpired() {
  const exp = wx.getStorageSync(EXPIRE_KEY) || 0;
  return Date.now() > exp - 60 * 1000;   // 提前一分钟算过期，避免请求途中失效
}

async function login() {
  const { code } = await new Promise((resolve, reject) =>
    wx.login({ success: resolve, fail: reject })
  );
  const res = await wx.request({
    url: 'https://your-api.example.com/login',   // 需在后台配置 request 合法域名
    method: 'POST',
    data: { code },
  });
  const { token, expiresIn } = res.data || {};
  if (!token) throw new Error('login failed');
  wx.setStorageSync(TOKEN_KEY, token);
  wx.setStorageSync(EXPIRE_KEY, Date.now() + expiresIn * 1000);
  return token;
}

async function ensureLogin() {
  if (getToken() && !isExpired()) return getToken();
  return login();
}

module.exports = { getToken, ensureLogin, login };
```

请求封装里统一带 token，并在 401 时重登一次（**只重试一次**，避免死循环）：

```js
// utils/request.js
const { ensureLogin, getToken } = require('./auth');

async function request(options, retried) {
  const token = await ensureLogin();
  const res = await wx.request({
    ...options,
    header: { ...(options.header || {}), Authorization: 'Bearer ' + token },
  });
  if (res.statusCode === 401 && !retried) {
    return request(options, true);
  }
  return res;
}
```

## 三、服务端职责（伪代码，落到你的语言/框架）

```text
POST /login
  1. 收到 code
  2. 调微信接口换 openid / session_key（用 appid + secret，secret 只存在环境变量）
  3. 若需 unionid，按官方文档要求处理
  4. upsert 用户表：openid 为唯一键
  5. 签发 token：payload = { uid, openid, exp }，密钥来自环境变量
  6. 返回 { token, expiresIn }
  ⚠️ 不要把 session_key 返回给前端
  ⚠️ 不要用 openid 当 token（可被猜测/复用）
```

## 四、五个必须做对的地方

1. **code 只能用一次**，且有时效。前端缓存 code 复用一定失败。
2. **登录态过期要有兜底**：静默重登 + 失败时给"重新进入"提示。
3. **`openid` 不能当身份凭证**发给前端当 token——它不防伪造。
4. **多端/多环境要隔离**：测试与正式用不同 AppID，用户表不要混。
5. **手机号能力是独立能力**，不要把它当登录。登录用 openid 就够，手机号是"额外采集的信息"，需要单独说明用途。

## 五、常见故障对照

| 现象 | 大概率原因 |
|---|---|
| 一直重登，请求死循环 | 401 重试没有次数限制 |
| 生产偶发登录失败 | AppSecret 在测试/正式环境混用 |
| 换手机后登录态丢了 | token 只存了 localStorage 且没做跨设备逻辑（这通常是预期行为，确认产品预期） |
| 用户表出现重复用户 | 用昵称或手机号当唯一键；应以 openid 为唯一键 |
| 解密手机号失败 | `session_key` 过期，需重新 `wx.login` |
