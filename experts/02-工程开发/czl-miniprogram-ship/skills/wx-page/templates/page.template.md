# 页面四件套模板

> 复制这四个文件，把 `{{name}}` / `{{title}}` 换掉即可编译。三态已内置，别删。

## `{{name}}.js`

```js
Page({
  data: {
    status: 'loading',     // loading | empty | error | ok
    list: [],
    errorMsg: '',
    page: 1,
    loadingMore: false,
    noMore: false,
  },

  onLoad(options) {
    // 入参: options  ·  验收条目见 docs/交付台账.md
    this.loadPage(1);
  },

  onUnload() {
    // 清理定时器与 wx.onXxx 监听
    // clearInterval(this._timer);
  },

  onReachBottom() {
    if (this.data.loadingMore || this.data.noMore) return;
    this.loadPage(this.data.page + 1);
  },

  async loadPage(page) {
    if (page === 1) this.setData({ status: 'loading' });
    else this.setData({ loadingMore: true });

    try {
      const res = await this.fetch(page);                       // 换成真实请求
      const list = page === 1 ? res.list : this.data.list.concat(res.list);
      this.setData({
        list,
        page,
        status: list.length ? 'ok' : 'empty',
        noMore: res.list.length < 20,
        loadingMore: false,
      });
    } catch (e) {
      this.setData({
        status: page === 1 ? 'error' : 'ok',
        errorMsg: page === 1 ? '网络不太好，点一下重试' : '',
        loadingMore: false,
      });
    }
  },

  fetch(page) {
    // 请求成功时还要校验登录态失效、业务错误码，不要只看 http 200
    return Promise.resolve({ list: [], total: 0 });
  },

  onRetry() {
    this.loadPage(1);
  },
});
```

## `{{name}}.json`

```json
{
  "navigationBarTitleText": "{{title}}",
  "usingComponents": {},
  "enablePullDownRefresh": false
}
```

## `{{name}}.wxml`

```xml
<view class="{{name}}-page">
  <view wx:if="{{status === 'loading'}}" class="state">加载中…</view>

  <view wx:elif="{{status === 'empty'}}" class="state">
    还没有内容
    <button size="mini" bindtap="onRetry">刷新试试</button>
  </view>

  <view wx:elif="{{status === 'error'}}" class="state">
    {{errorMsg}}
    <button size="mini" bindtap="onRetry">重试</button>
  </view>

  <block wx:else>
    <view wx:for="{{list}}" wx:key="id" class="item">
      <!-- 主内容：字段名与数据契约保持一致 -->
    </view>
    <view class="more">{{loadingMore ? '加载中…' : (noMore ? '没有更多了' : '')}}</view>
  </block>
</view>
```

## `{{name}}.wxss`

```css
.{{name}}-page {
  min-height: 100vh;
  padding: 24rpx;
  box-sizing: border-box;
  background: #f6f7f8;
}

.state {
  padding: 160rpx 0;
  text-align: center;
  color: #8a8f99;
  font-size: 28rpx;
}

.state button {
  margin-top: 24rpx;
}

.item {
  display: flex;
  padding: 24rpx;
  margin-bottom: 16rpx;
  background: #fff;
  border-radius: 16rpx;
}

.more {
  padding: 32rpx 0;
  text-align: center;
  color: #b0b4bb;
  font-size: 24rpx;
  padding-bottom: calc(32rpx + env(safe-area-inset-bottom));
}
```

## 交付前替换清单

- [ ] `{{name}}` / `{{title}}` 已替换
- [ ] `fetch()` 换成真实请求，并处理登录态失效
- [ ] 列表字段名与数据契约一致
- [ ] `wx:key` 用稳定唯一值，不用 index
- [ ] 有定时器/监听的话，`onUnload` 里清掉
- [ ] 跑 `wx_doctor.py scan`，确认四件套齐全
