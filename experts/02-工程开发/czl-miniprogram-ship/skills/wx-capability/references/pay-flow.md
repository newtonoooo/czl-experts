# 微信支付：下单到回调的完整链路

> 接口名、参数、证书要求与签名算法以**微信支付商户平台文档**为准（小程序 JSAPI 支付章节）。本文只讲链路怎么摆、哪里最容易出事。

## 一、谁做什么（职责划分）

| 环节 | 谁做 | 绝对不要 |
|---|---|---|
| 生成订单 | 服务端 | 前端算价格、传价格 |
| 调统一下单 | 服务端 | 前端直连微信支付接口 |
| 签名 | 服务端 | 前端签名、密钥进包 |
| 唤起支付 | 前端 `wx.requestPayment` | 前端判断"支付成功"后直接发货 |
| 支付结果 | 服务端收回调 | 用前端 `success` 当唯一依据 |
| 幂等 | 服务端 | 回调重复到达时重复发货 |

## 二、时序

```
小程序            服务端                微信支付
  |                 |                     |
  |-- 创建订单 ---->|                     |
  |                 |-- 统一下单 -------->|
  |                 |<-- prepay_id -------|
  |                 | 服务端签名           |
  |<-- 支付参数 ----|                     |
  |-- wx.requestPayment ---------------->|
  |<-- success/fail |                     |
  |-- 查询订单 ---->|                     |
  |                 |<-- 支付回调 --------|
  |                 | 校验签名 → 幂等 → 发货
  |<-- 订单已支付 --|                     |
```

前端 `success` 只做"提示 + 跳转订单页"，真实状态永远回服务端查。

## 三、前端代码

```js
// pages/pay/pay.js
Page({
  data: { paying: false },

  async onPay() {
    if (this.data.paying) return;            // 防重复点击
    this.setData({ paying: true });
    try {
      const order = await this.createOrder();          // 服务端创建订单，返回订单号
      const params = await this.getPayParams(order.id); // 服务端返回已签名参数
      await new Promise((resolve, reject) => {
        wx.requestPayment({
          timeStamp: params.timeStamp,
          nonceStr: params.nonceStr,
          package: params.package,
          signType: params.signType,
          paySign: params.paySign,
          success: resolve,
          fail: reject,
        });
      });
      // ⚠️ 这里只当作"用户完成了支付动作"，真实结果以服务端为准
      const status = await this.queryOrder(order.id);
      if (status === 'paid') {
        wx.redirectTo({ url: '/packages/orders/detail/detail?id=' + order.id });
      } else {
        wx.showToast({ title: '支付结果确认中', icon: 'none' });
      }
    } catch (e) {
      if (e && e.errMsg && e.errMsg.indexOf('cancel') > -1) {
        wx.showToast({ title: '已取消', icon: 'none' });
      } else {
        wx.showToast({ title: '支付没成功，请重试', icon: 'none' });
      }
    } finally {
      this.setData({ paying: false });
    }
  },
});
```

## 四、服务端要点

1. **金额只从服务端取**：前端只传商品 ID 与数量，服务端查价格。
2. **订单号自己生成**，且唯一；不要用时间戳直接当订单号（并发会撞）。
3. **签名用商户密钥/证书**，密钥放环境变量或密钥管理服务，不进代码库。
4. **回调必须校验签名**，并校验金额与订单号与本地一致——只验签名不验金额是常见漏洞。
5. **回调要幂等**：同一笔回调可能重复到达，用订单号 + 状态机挡住。
6. **回调要快速返回成功**，重活（发货、通知）异步做，否则会一直被重推。
7. **主动查单兜底**：回调丢失时用查单接口对齐状态（频率要控，别轮询打爆）。

## 五、退款

- 退款也在服务端发起，前端只展示状态。
- 退款结果同样以回调/查询为准，不要前端"点了退款"就显示已退款。
- 部分退款要记录明细，否则对账时对不上。

## 六、提审相关的两条硬规则

1. **iOS 端虚拟商品不得用微信支付**（会员、课程、虚拟币、内容解锁等）。要么改方案，要么 iOS 隐藏支付入口，要么走苹果允许的路径。实物商品不受此限。
2. **必须能说清退款路径**。审核会问"用户怎么退款"，答不上来会被拒。

> 上述规则的适用范围与最新口径以微信支付商户平台文档、小程序运营规范与苹果相关政策为准，动手前请核实。

## 七、故障对照

| 现象 | 排查顺序 |
|---|---|
| `requestPayment` 报签名错误 | ① 参数顺序与大小写 ② 是否用了正确的密钥/证书 ③ 时间戳单位 ④ 服务端与前端参数是否同一份 |
| 支付成功但订单未支付 | ① 回调地址是否配 ② 回调是否校验失败被丢弃 ③ 幂等逻辑是否把正常回调挡了 |
| 回调重复导致重复发货 | 没有用订单号做幂等键 |
| 用户付了两次 | 前端没防重复点击 + 服务端没做订单唯一性约束 |
