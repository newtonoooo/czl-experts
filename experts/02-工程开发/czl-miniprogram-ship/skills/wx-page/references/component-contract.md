# 自定义组件：接口契约设计

> 组件的问题八成不在实现，在**接口没定清楚就开写**。改一次接口，所有调用点都要改。所以先定契约，再写实现。

## 一、契约要写清的六件事

| 项 | 写什么 | 示例 |
|---|---|---|
| `properties` | 每个入参的类型、默认值、是否必填 | `value: { type: String, value: '' }` |
| `events` | 触发名、何时触发、payload 结构 | `change: { value, index }` |
| `slots` | 有几个插槽、分别放什么 | 默认插槽 = 内容区；`footer` = 底部操作区 |
| 样式隔离 | `isolated` / `apply-shared` / `shared` | 默认 `isolated`，外部改不到内部样式 |
| 外部样式 | `externalClasses` 允许外部改哪些 | `custom-class` |
| 副作用 | 是否有定时器、是否发请求、是否存本地 | 组件默认不发请求 |

## 二、命名约定

- **属性用小驼峰**（`maxLength`），WXML 里写连字符（`max-length="{{20}}"`）。
- **事件名用动词或过去式**（`change` / `submit` / `tap-item`），不用 `onXxx`（会和原生写法混）。
- **属性不要叫 `data`**，会和组件内部 data 混淆。

## 三、一个完整组件示例（可运行）

`components/price-tag/index.js`

```js
Component({
  options: {
    styleIsolation: 'isolated',
  },

  properties: {
    price: { type: Number, value: 0 },        // 单位：元
    origin: { type: Number, value: 0 },       // 划线原价，0 表示不显示
    size: { type: String, value: 'normal' },  // normal | large
  },

  data: {
    intPart: '0',
    decPart: '00',
    showOrigin: false,
  },

  observers: {
    'price, origin'(price, origin) {
      const fixed = (Number(price) || 0).toFixed(2);
      const [i, d] = fixed.split('.');
      this.setData({
        intPart: i,
        decPart: d,
        showOrigin: Number(origin) > Number(price),
      });
    },
  },

  methods: {
    onTap() {
      this.triggerEvent('tap-price', { price: this.data.price });
    },
  },
});
```

`components/price-tag/index.json`

```json
{ "component": true, "usingComponents": {} }
```

`components/price-tag/index.wxml`

```xml
<view class="price price-{{size}}" bindtap="onTap">
  <text class="symbol">¥</text>
  <text class="int">{{intPart}}</text>
  <text class="dec">.{{decPart}}</text>
  <text class="origin" wx:if="{{showOrigin}}">¥{{origin}}</text>
</view>
```

`components/price-tag/index.wxss`

```css
.price { display: inline-flex; align-items: baseline; color: #e4393c; }
.symbol { font-size: 24rpx; }
.int { font-size: 36rpx; font-weight: 600; }
.dec { font-size: 24rpx; }
.price-large .int { font-size: 48rpx; }
.origin { margin-left: 12rpx; color: #999; text-decoration: line-through; font-size: 22rpx; }
```

调用方：

```json
{ "usingComponents": { "price-tag": "/components/price-tag/index" } }
```

```xml
<price-tag price="{{item.price}}" origin="{{item.originPrice}}" bind:tap-price="onPriceTap" />
```

## 四、三个高频设计错误

### 1. 用 `properties` 传整个对象

```js
// 反例
item: { type: Object, value: {} }
```

问题：对象里的字段变化不会触发观察者（浅比较），且调用方不知道要传哪些字段。
**改法**：拆成具体字段；确实要传对象就明确写"整块替换才生效"。

### 2. 组件里偷偷发请求

组件发请求会让调用方无法控制时机，也无法统一处理错误与登录态。
**改法**：组件只接收数据、只抛事件，请求由页面负责。

### 3. 用 `selectComponent` 从父级改子组件内部状态

```js
// 反例
this.selectComponent('#card').setData({ selected: true });
```

问题：把子组件内部实现暴露给父级，改一次内部结构就崩。
**改法**：父级改自己的 data，通过 `properties` 传下去。

## 五、组件的测试最小集

交付组件前，至少手动过这五项：

1. 不传任何属性 → 有合理默认值，不报错
2. 传空数组/空字符串 → 不白屏
3. 长文本 → 不撑破布局（截断或换行策略明确）
4. 快速连点 → 不重复触发（必要时组件内防抖）
5. 卸载后 → 定时器清掉，事件解绑
