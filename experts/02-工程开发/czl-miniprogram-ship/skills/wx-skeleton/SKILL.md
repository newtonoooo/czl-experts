---
name: wx-skeleton
description: 小程序工程骨架与体积预算技能。做目录结构、分包切分、preloadRule、app.json/project.config.json 配置，先用规格文件生成可运行骨架，再用预算脚本核真实字节。当要新建工程、主包快满、要决定哪些页面进分包、或配置项不确定时使用。
---

# 骨架与预算（W1）

## 什么时候用

- 新建工程，要一个能跑起来的骨架
- 主包接近上限，要决定怎么切分包
- `app.json` / `project.config.json` 的字段不知道该怎么写
- 要判断"这个功能上线后会不会撑爆包体"

## 输入

| 输入 | 必需 | 说明 |
|---|---|---|
| 条目表 `acceptance.json` | 是 | 页面清单从条目来，不从想象来 |
| 资源清单 | 否 | 有多少图、多大、要不要放包内 |
| 是否多端 | 否 | 决定要不要跨端框架的目录约定 |

## 步骤

1. **划主包最小集**：只放 tabBar 页 + 首屏必需组件 + `app.js/wxss/json`。原则是"用户第一眼要看到的东西"之外，全部不进主包。

2. **切分包**，按三条规则：
   - 高频但非首屏 → 普通分包 + `preloadRule` 预下载
   - 低频独立功能（如"开票""售后"）→ **独立分包**（`independent: true`），可脱离主包启动
   - 页面间强耦合的放同一个分包，减少跨包跳转

3. **出预算表**：主包上限、各分包上限、单页资源额度、剩余余量。规则见 `references/subpackage-budget.md`。

4. **生成骨架**：

   ```bash
   python <skill>/scripts/wx_doctor.py scaffold --spec spec.json --out ./miniprogram
   ```

   `spec.json` 写法见 `templates/spec.sample.json`。生成完立刻跑：

   ```bash
   python <skill>/scripts/wx_doctor.py budget ./miniprogram
   python <skill>/scripts/wx_doctor.py scan   ./miniprogram
   ```

5. **配置核对**：逐项对 `references/app-config-notes.md` 过一遍易错字段（tabBar 图标路径、分包 root、preloadRule 键、requiredPrivateInfos）。

6. **写预算表进文档**：`docs/预算表.md`，贴脚本真实输出，不写"大概 1.5MB"。

## 判断条件

| 情况 | 动作 |
|---|---|
| 主包实测 / 上限 > 85% | 必须再切一次分包，不留 90% 以上过夜 |
| 单页资源 > 300KB | 图片先处理（压缩/裁剪/CDN），再谈代码优化 |
| 分包之间互相引用页面 | 说明切分错了，合并或抽公共组件 |
| 用了跨端框架 | 预算必须按框架**编译产物**算，不按源码估 |

## 输出

1. 可运行骨架目录
2. `docs/预算表.md`（贴 `budget` 输出）
3. `scan` 输出（页面四件套齐全、无未声明目录）
4. 分包切分理由（一句一个分包）

## 异常处理

| 异常 | 处理 |
|---|---|
| `scaffold` 因路径特殊字符失败 | 手写骨架，台账注明"骨架手工创建" |
| 存量工程目录混乱（页面散落各目录） | 先出"现状地图"，再给迁移方案；不建议一次性大搬迁 |
| 已有 `node_modules` 被算进体积 | 确认 `project.config.json` 的 `packOptions.ignore` 已排除 |
| 用户坚持"先全部放主包，以后再说" | 给出超限后的返工成本（涉及页面要整体搬迁+改路由），让他自己选，但结论写进风险 |

## 依赖

- `scripts/wx_doctor.py`（`scaffold` / `budget` / `scan`）
- `references/app-config-notes.md`
- `references/subpackage-budget.md`
- `templates/spec.sample.json`

## 与其它工作流的关系

- 上游：W0 条目表
- 下游：W2 在骨架上填页面；W5 复用 `budget` 做上线前复核
- 回退：预算过不去时**回到 W0 砍范围**，不要靠"压缩代码"硬顶

## 自检

- [ ] 主包只有 tabBar 页与首屏必需
- [ ] 每个分包都有切分理由
- [ ] `budget` 有真实输出，主包占比有数字
- [ ] tabBar 图标文件存在且不大
- [ ] `preloadRule` 指向真实分包
