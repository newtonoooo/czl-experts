# 云函数写法

> `wx-server-sdk` 的初始化方式、`cloud.getWXContext()` 的字段、返回值结构以官方云开发文档为准。本文讲结构与纪律。

## 一、一个云函数的结构（固定四段）

```js
// cloudfunctions/createOrder/index.js
const cloud = require('wx-server-sdk');
cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV });

const db = cloud.database();

exports.main = async (event, context) => {
  // ① 身份：永远用服务端拿到的 openid，绝不信任前端传的
  const { OPENID } = cloud.getWXContext();
  if (!OPENID) return { code: 401, msg: '未登录' };

  // ② 入参校验：类型、范围、必填，一个都不能少
  const items = event.items;
  if (!Array.isArray(items) || items.length === 0) return { code: 400, msg: '商品不能为空' };
  if (items.length > 50) return { code: 400, msg: '单次下单商品过多' };
  for (const it of items) {
    if (typeof it.goodsId !== 'string' || typeof it.qty !== 'number' || it.qty <= 0) {
      return { code: 400, msg: '参数不合法' };
    }
  }

  // ③ 业务：价格从数据库取，不信前端传的金额
  try {
    const ids = items.map(i => i.goodsId);
    const goodsRes = await db.collection('goods')
      .where({ _id: db.command.in(ids), status: 'on', deleted: false })
      .get();
    if (goodsRes.data.length !== ids.length) return { code: 409, msg: '部分商品已下架' };

    let amount = 0;
    const snapshot = [];
    for (const it of items) {
      const g = goodsRes.data.find(x => x._id === it.goodsId);
      amount += g.price * it.qty;
      snapshot.push({ goodsId: g._id, title: g.title, price: g.price, qty: it.qty });
    }

    const orderNo = makeOrderNo(OPENID);
    await db.collection('orders').add({
      data: {
        _openid: OPENID, orderNo, items: snapshot, amount,
        status: 'created', createdAt: db.serverDate(), deleted: false,
      },
    });
    return { code: 0, data: { orderNo, amount } };
  } catch (e) {
    console.error('[createOrder]', e);         // 日志留在服务端
    return { code: 500, msg: '下单失败，请重试' };   // 不给前端堆栈
  }
};

function makeOrderNo(openid) {
  const d = new Date();
  const pad = n => String(n).padStart(2, '0');
  const stamp = `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
  const rand = Math.random().toString(36).slice(2, 6).toUpperCase();
  return `O${stamp}${rand}`;
}
```

## 二、四条纪律

### 1. 身份只从 `getWXContext()` 取

```js
// 反例：前端传什么就用什么
const openid = event.openid;
```

前端参数可以被任意伪造。任何"用户是谁"的判断都必须来自服务端上下文。

### 2. 统一返回结构

```js
{ code: 0, data: {...} }        // 成功
{ code: 400, msg: '...' }       // 参数错
{ code: 401, msg: '...' }       // 未登录
{ code: 403, msg: '...' }       // 无权限
{ code: 500, msg: '...' }       // 服务端错
```

前端只判 `code`，不判 HTTP 状态（云函数返回的是调用结果，不是 http 响应）。

### 3. 不在云函数里做重活

云函数有执行时长上限。批量处理、导出、图像处理这类，拆成多个小任务或用异步触发，不要把长循环塞进一次调用。

### 4. 错误不吐内部信息

`return { msg: e.message }` 会把数据库字段名、集合名、甚至 SQL 级信息暴露给前端。日志写 `console.error`，前端只给一句话。

## 三、支付回调云函数

```js
exports.main = async (event) => {
  // ① 验签（按微信支付文档的验签方法，不要自己发明）
  // ② 幂等：以订单号 + 状态机挡重复
  // ③ 校验金额与本地订单一致
  // ④ 快速返回成功，发货异步做
};
```

四步里最容易漏的是 ② 和 ③：只验签不校验金额，等于让攻击者用小额支付换大额发货。

## 四、定时触发器

- 用云函数的定时触发能力（配置方式以官方文档为准）。
- 定时任务必须**可重入**：这次跑到一半失败，下次跑不能重复处理同一批数据。
- 处理前先"占位"（把状态改成 `processing`），避免并发触发两次。

## 五、前端调用

```js
const res = await wx.cloud.callFunction({
  name: 'createOrder',
  data: { items: [{ goodsId: 'g1', qty: 2 }] },
});
if (res.result.code !== 0) {
  wx.showToast({ title: res.result.msg || '操作失败', icon: 'none' });
  return;
}
```

云函数名写错不会编译报错，只会在运行时 404。**这是个高频低级错误**，交付前用 `wx_doctor.py scan` 对一遍前端调用名与 `cloudfunctions/` 目录名。

## 六、调试建议

| 问题 | 做法 |
|---|---|
| 本地跑不通 | 先确认 `cloud.init` 的 env 与当前环境一致 |
| 线上报权限错 | 查集合安全规则，云函数里操作的是管理权限，规则不生效，别混淆 |
| 偶发超时 | 看是否一次查太多；加分页或改游标 |
| 数据写进去了但读不到 | 查 `_openid` 是否为空（云函数写入时会带，手动构造对象时不带） |
