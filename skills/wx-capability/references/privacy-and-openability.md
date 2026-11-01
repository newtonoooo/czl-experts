# 隐私授权与其它开放能力

> 隐私相关接口名称与行为、平台规则以微信官方「用户隐私保护指引」「隐私接口」文档与公众平台后台为准，本文只讲工程摆法与常见驳回原因。

## 一、隐私这件事的三层结构

很多人以为"加个弹窗"就合规了，其实是三层：

```
第 1 层：平台声明（公众平台后台「用户隐私保护指引」）
         —— 你收集什么、用来干什么。没配这个，采集接口直接失败。
第 2 层：代码声明（app.json 的 requiredPrivateInfos / permission）
         —— 告诉框架和用户你用了哪些敏感接口。
第 3 层：用户授权（弹窗/按钮授权，含拒绝分支）
         —— 用户在具体动作时同意。
```

三层缺任何一层都会出问题：只做第 3 层 → 接口调不通；只做第 1、2 层 → 用户没同意就调，审核驳回。

## 二、必须与采集项对应的清单

| 你调用的能力 | 第 1 层（指引） | 第 2 层（app.json） | 第 3 层（用户授权） |
|---|---|---|---|
| 位置 | 说明用途（如"显示附近门店"） | `requiredPrivateInfos: ["getLocation"]` + `permission.scope.userLocation.desc` | 系统弹窗 + 拒绝分支 |
| 选位置 | 同上 | `chooseLocation` | 弹窗 |
| 收货地址 | 说明用于发货 | `chooseAddress` | 弹窗 |
| 相册/拍照 | 说明用途（如"上传头像"） | 一般无需 requiredPrivateInfos | 弹窗 + 拒绝分支 |
| 手机号 | 说明用于账号/通知 | 无（走按钮 `open-type="getPhoneNumber"`） | 用户点击按钮 |
| 剪贴板读取 | 说明用途 | 无 | 建议在交互中触发，不要启动即读 |
| 微信运动 | 说明用途 | 无 | 弹窗 |

> 上表"第 2 层"列的接口名以官方隐私接口文档为准；不同能力是否要求声明可能随平台政策调整，动手前核对一遍。

## 三、代码结构的建议写法

把隐私判断收在一个地方，不要散落在各页面：

```js
// utils/privacy.js
let pendingResolve = null;

// 需要隐私授权时，平台会触发这个回调（接口名与用法以官方文档为准）
if (wx.onNeedPrivacyAuthorization) {
  wx.onNeedPrivacyAuthorization((resolve) => {
    pendingResolve = resolve;
    // 通知页面展示自定义弹窗
    const pages = getCurrentPages();
    const page = pages[pages.length - 1];
    page && page.setData({ showPrivacyDialog: true });
  });
}

function agree() {
  if (pendingResolve) {
    pendingResolve({ event: 'agree', buttonId: 'agree-btn' });
    pendingResolve = null;
  }
}

function disagree() {
  if (pendingResolve) {
    pendingResolve({ event: 'disagree' });
    pendingResolve = null;
  }
}

module.exports = { agree, disagree };
```

页面里的弹窗（节选）：

```xml
<view class="mask" wx:if="{{showPrivacyDialog}}">
  <view class="dialog">
    <view class="title">隐私保护提示</view>
    <view class="desc">
      为了 {{具体用途}}，我们需要获取 {{具体信息}}。
      详见
      <navigator class="link" open-type="openPrivacyContract">《隐私保护指引》</navigator>
    </view>
    <view class="btns">
      <button class="btn ghost" bindtap="onPrivacyDisagree">不同意</button>
      <!-- 同意按钮的 id 要与 resolve 时传的 buttonId 对应 -->
      <button id="agree-btn" class="btn primary" bindtap="onPrivacyAgree">同意</button>
    </view>
  </view>
</view>
```

**拒绝分支必须存在**，且拒绝后不能白屏。合理做法：功能降级 + 说明"开启后才能用某某功能"。

## 四、订阅消息

1. 模板在公众平台后台申请，审核通过后才有模板 ID。
2. 前端在**用户动作之后**调用（比如点了"预约"再问要不要提醒），不要在 `onLoad` 里弹。
3. 一次授权对应一次下发；反复弹会被用户投诉，也会被平台限制。
4. 下发由服务端调用，注意 `access_token` 的缓存与刷新，别每次都取。

## 五、分享

```js
Page({
  onShareAppMessage() {
    return {
      title: '分享标题（要像人写的，不要像广告）',
      path: '/pages/index/index?from=share',
      imageUrl: '',   // 留空则自动截屏
    };
  },
});
```

红线（违反必拒）：
- 分享作为功能前置条件（"分享后才能看"）
- 分享直接给奖励（"分享得 10 元"）
- 强制关注公众号才能用
- 弹窗阻断用户正常操作

合规写法只有一种：**自然引导**，用户想分享就分享，不分享也不影响用。

## 六、小程序码

- 生成在服务端做（需要 access_token），前端只拿图片地址或 base64。
- 码里带的参数有长度限制，复杂参数用短 ID 映射，不要把 JSON 塞进 scene。
- 扫码进入的页面要能处理"未登录""参数失效"，否则用户体验是白屏。

## 七、提审前对着这张表自查

- [ ] 隐私指引里的采集项，与代码里实际调用的接口一一对应（用 `wx_doctor.py preflight` 拉清单）
- [ ] `requiredPrivateInfos` 齐全，`permission.desc` 写的是用途不是接口名
- [ ] 每处授权都有拒绝分支，拒绝后主流程仍可用
- [ ] 没有"启动即弹授权"，授权都发生在用户动作之后
- [ ] 分享无强制、无奖励
- [ ] 有账号注销路径（涉及账号体系时）
