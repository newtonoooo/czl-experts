---
name: wx-page
description: 小程序页面与组件开发技能。先定数据契约再写四件套（js/json/wxml/wxss），组件先定 properties/events/slots 接口再实现，强制覆盖加载/空/错误三态。当要写页面、封装组件、改列表或表单、或页面报错白屏时使用。
---

# 页面与组件（W2）

## 什么时候用

- 写新页面、改现有页面
- 封装或重构自定义组件
- 列表、表单、弹窗、骨架屏这类常见形态
- 页面白屏、数据不渲染、样式错乱

## 输入

| 输入 | 必需 | 说明 |
|---|---|---|
| 条目 ID | 是 | 没有条目不开工（见 W0） |
| 数据来源 | 是 | 接口字段、mock 数据、或本地数据 |
| 设计稿/截图/文案 | 否 | 没有就给文字版布局描述并标注待确认 |
| 资源额度 | 否 | 从 W1 预算表来，图片超额度先处理 |

## 步骤

1. **先写数据契约**（不写代码）。四行就说清：

   ```
   data.list: Array<{id, name, price, coverUrl}>   ← 列表数据
   data.status: 'loading' | 'empty' | 'error' | 'ok' ← 页面状态机
   onTapItem(e) → 跳详情，带 id
   fetchList(page) → GET /goods?page=n
   ```

   契约不定就写 WXML，最后一定要返工——模板里的字段名会到处漏。

2. **出四件套**。四个文件缺一不可：

   | 文件 | 内容 | 常见漏项 |
   |---|---|---|
   | `.js` | Page/Component 逻辑 | 忘写 `onUnload` 清理 |
   | `.json` | 标题、`usingComponents` | 组件路径写错（工具报 `SCAN-030`） |
   | `.wxml` | 结构 | 三态没写，只有正常态 |
   | `.wxss` | 样式 | 用了 px 而不是 rpx |

3. **三态必须都有**：加载中 / 空 / 出错。空态要给人下一步该点哪，错误态要给重试。

4. **组件先定接口**，见 `references/component-contract.md`。三样必须写清：`properties`（入参类型与默认值）、`events`（触发名与 payload）、`slots`（插槽位置）。接口定了再写实现，否则改一次接口要改所有调用点。

5. **数据更新用局部路径**：

   ```js
   // 反例：整包刷新，卡顿主因
   this.setData(this.data);
   // 正例：只改一条
   this.setData({ [`list[${index}].selected`]: true });
   ```

6. **回写台账**：条目绑文件，改成 `done`，跑 `scan` 确认四件套齐全。

## 判断条件

| 情况 | 动作 |
|---|---|
| 条目没绑文件 | 不算完成，不许改 `done`（`ledger.py` 会拒） |
| 页面有 `setData` 整包刷新 | 改局部路径再交（工具报 `SCAN-070`） |
| 列表超过 100 条 | 上分页或虚拟列表，不要一次全渲染 |
| 组件被 3 个以上页面用 | 抽成自定义组件，别复制代码 |
| 有 `setInterval` / `wx.onXxx` | 必须在 `onUnload` / `detached` 里清（工具报 `SCAN-071`） |

## 输出

1. 四件套代码（可编译）
2. 数据契约（贴在交付说明里）
3. 组件接口表（properties / events / slots）
4. 台账回写 + `scan` 输出

## 异常处理

| 异常 | 处理 |
|---|---|
| 白屏 | 按 `wx-doctor/references/troubleshooting.md` 的排查树走，先看 console 第一行错 |
| 数据不渲染 | 先查 `setData` 的键名与 WXML 里绑定的名字是否一致，再查是否在 `onLoad` 之前就渲染 |
| 样式不生效 | 查组件样式隔离（默认 isolated）、查是否有 `!important` 覆盖、查 rpx 与 px 混用 |
| 设计稿缺失 | 给文字版布局，标注"版式待设计确认"，不假装已经定稿 |

## 依赖

- `references/page-recipes.md`（列表/表单/弹窗/骨架屏的实现要点与坑）
- `references/component-contract.md`（组件接口设计）
- `templates/page.template.md`（页面四件套，含三态骨架）
- `templates/component.template.md`（组件四件套，含接口表）
- `scripts/wx_doctor.py scan`

## 与其它工作流的关系

- 上游：W1 骨架（页面路径已存在）
- 并行：W3 能力接入（页面里的登录/支付/授权点）
- 下游：W5 体检（四件套与体积复核）

## 自检

- [ ] 数据契约先于代码
- [ ] 四件套齐全，`.json` 里组件路径可解析
- [ ] 三态都有，空态有引导、错误态有重试
- [ ] 没有 `setData` 整包刷新
- [ ] 定时器与监听在卸载时清理
- [ ] 尺寸用 rpx，图片有 `mode` 与兜底
