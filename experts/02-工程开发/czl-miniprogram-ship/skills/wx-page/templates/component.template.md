# 自定义组件模板

> 四件套一起给。接口先定，实现后写。`{{name}}` 换成组件名。

## `index.js`

```js
Component({
  options: {
    styleIsolation: 'isolated',   // 外部改不到内部样式，需要时可给 externalClasses
  },

  properties: {
    // 入参：类型 + 默认值 + 一句语义
    title: { type: String, value: '' },
    count: { type: Number, value: 0 },
  },

  data: {
    // 内部状态，不放对外契约
  },

  observers: {
    'count'(v) {
      // 只在需要派生数据时用，别在观察者里发请求
    },
  },

  lifetimes: {
    attached() {},
    detached() {
      // 清定时器、解绑事件
    },
  },

  methods: {
    onTap() {
      this.triggerEvent('tap', { count: this.data.count });
    },
  },
});
```

## `index.json`

```json
{
  "component": true,
  "usingComponents": {}
}
```

## `index.wxml`

```xml
<view class="c-{{name}}" bindtap="onTap">
  <text class="c-title" wx:if="{{title}}">{{title}}</text>
  <slot></slot>
  <slot name="footer"></slot>
</view>
```

## `index.wxss`

```css
.c-{{name}} {
  display: block;
  padding: 24rpx;
  background: #fff;
  border-radius: 16rpx;
}

.c-title {
  display: block;
  margin-bottom: 12rpx;
  font-size: 30rpx;
  color: #23262b;
  font-weight: 600;
}
```

## 调用方

```json
{
  "usingComponents": {
    "my-{{name}}": "/components/{{name}}/index"
  }
}
```

```xml
<my-{{name}} title="标题" count="{{n}}" bind:tap="onComponentTap">
  <view>默认插槽内容</view>
  <view slot="footer">底部插槽内容</view>
</my-{{name}}>
```

## 接口表（交付时必须附）

| 项 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `title` | String | `''` | 标题，空则不显示 |
| `count` | Number | `0` | 计数 |

| 事件 | 触发时机 | payload |
|---|---|---|
| `tap` | 点击组件主体 | `{ count }` |

| 插槽 | 位置 |
|---|---|
| 默认 | 内容区 |
| `footer` | 底部操作区 |
