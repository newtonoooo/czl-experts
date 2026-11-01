# 常见页面形态：实现要点与坑

> 这里只写"做过才知道"的部分。WXML/WXSS 语法本身请以官方文档为准。

## 一、列表页

### 要点

1. **分页不是可选**。首屏只渲染 20 条，触底再拉。一次渲染 500 条，低端机上一定卡。
2. **`wx:key` 必须是稳定唯一值**，不要用 `index`。用 index 时，中途插入/删除会让已渲染项错位（表现为"图片串了""勾选跑位"）。
3. **图片给尺寸 + `mode`**：不给高度会导致渲染后跳动（累积布局偏移），列表滚动时更明显。
4. **下拉刷新与触底加载的状态要分开**：`refreshing` 和 `loadingMore` 是两个变量，合成一个会在触底时把列表清空。

### 骨架

```xml
<view class="list">
  <view wx:for="{{list}}" wx:key="id" class="item" bindtap="onTapItem" data-id="{{item.id}}">
    <image class="cover" src="{{item.coverUrl}}" mode="aspectFill" lazy-load />
    <view class="info">
      <text class="name">{{item.name}}</text>
      <text class="price">¥{{item.price}}</text>
    </view>
  </view>
</view>
<view class="more">{{loadingMore ? '加载中…' : (noMore ? '没有更多了' : '')}}</view>
```

```js
onReachBottom() {
  if (this.data.loadingMore || this.data.noMore) return;   // 双闸门，防止重复请求
  this.loadPage(this.data.page + 1);
}
```

### 坑

| 现象 | 原因 |
|---|---|
| 触底连发三次请求 | 没有 `loadingMore` 闸门 |
| 返回列表后位置丢失 | 列表页被 `onUnload` 了，应该用 `onHide` 保留状态 |
| 图片一张张蹦出来 | 没给固定高度，也没有占位背景色 |

## 二、表单页

### 要点

1. **受控输入用 `bindinput` 实时更新**，不要在提交时才读 DOM（小程序没有 DOM）。
2. **校验放在提交前 + 失焦时各一次**：只在提交时校验，用户要来回滚才知道哪错了。
3. **按钮防重复点击**：提交中置 `submitting: true` 并禁用按钮。支付类提交尤其重要。
4. **错误提示贴字段**，不要统一弹 toast——用户不知道哪一行错了。

### 坑

| 现象 | 原因 |
|---|---|
| 输入中文时值丢失 | 用了 `bindblur` 才取值，输入法组字过程中不触发 |
| 提交两次产生两笔订单 | 没做防重，或防重只在前端没做服务端幂等 |
| 键盘挡住提交按钮 | 没处理 `adjust-position`，或用固定定位的按钮没随键盘上移 |

## 三、弹窗（自定义）

### 要点

1. **用 `catchtouchmove` 阻止背景滚动**，否则滑动会穿透到页面。
2. **层级用 `z-index` + 独立节点**，不要嵌在深层节点里（父级 `overflow: hidden` 会裁掉）。
3. **关闭要给三种方式**：点遮罩、点关闭按钮、返回键。只给一种会被用户骂。
4. **动画用 CSS transition**，不要用 `setData` 驱动逐帧（那是性能杀手）。

## 四、骨架屏

### 要点

1. 骨架屏的目的是**减少"白屏焦虑"**，不是炫技。灰块 + 微光足够。
2. **骨架与真实内容尺寸要对齐**，否则内容出来时会跳一下，比白屏更难受。
3. 首屏数据回来就切换，不要为了"展示骨架"人为延时。

## 五、页面状态机（推荐统一写法）

```js
Page({
  data: { status: 'loading', list: [], errorMsg: '' },

  async load() {
    this.setData({ status: 'loading' });
    try {
      const list = await fetchList();
      this.setData({ list, status: list.length ? 'ok' : 'empty' });
    } catch (e) {
      this.setData({ status: 'error', errorMsg: '网络不太好，点一下重试' });
    }
  },

  onRetry() { this.load(); },
});
```

```xml
<view wx:if="{{status === 'loading'}}" class="state">加载中…</view>
<view wx:elif="{{status === 'empty'}}" class="state">
  还没有内容
  <button size="mini" bindtap="onRetry">刷新试试</button>
</view>
<view wx:elif="{{status === 'error'}}" class="state">
  {{errorMsg}}
  <button size="mini" bindtap="onRetry">重试</button>
</view>
<block wx:else><!-- 正常内容 --></block>
```

一个 `status` 管三态，比三个布尔值靠谱——布尔值多了会出现"既 loading 又 error"的矛盾态。

## 六、样式三条硬规矩

1. **尺寸一律 rpx**（750rpx = 屏幕宽），只有 1px 边框、字体用 px 的场景例外。
2. **颜色与圆角走 CSS 变量**，写在 `app.wxss` 的 `page` 选择器里，改主题只改一处。
3. **底部固定元素留安全区**：`padding-bottom: env(safe-area-inset-bottom)`，否则 iPhone 上会被小黑条压住。
