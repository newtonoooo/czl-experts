# app.json 配置要点（易错清单）

> 字段语义与可用取值以微信官方 `app.json` 全局配置文档为准；本文只讲**容易写错的地方**和**写错之后的症状**。

## 一、pages

```json
"pages": ["pages/index/index", "pages/mine/mine"]
```

- 路径**不带扩展名**，不带前导 `/`，第一项是启动页。
- 写错一个页面，编译不报错但跳转白屏，属于最难查的一类问题。
- tabBar 里出现的页面**必须**在 pages 里，否则工具报 `SCAN-011`。

## 二、subpackages

```json
"subpackages": [
  {
    "name": "goods",
    "root": "packages/goods",
    "pages": ["detail/detail", "search/search"]
  }
]
```

- `root` 是**目录**，`pages` 里写的是**相对 root 的页面路径**，两者拼起来才是真实路径。
- 常见错误：`pages` 里又写了一遍 root（`packages/goods/detail/detail`），结果路径变成 `packages/goods/packages/goods/...`。
- `root` 不能与主包页面目录重叠；一个目录只能属于一个包。
- `independent: true` 的独立分包，内部**不能依赖主包的组件/工具**（除了少数基础能力），写之前先确认依赖关系。

## 三、preloadRule

```json
"preloadRule": {
  "pages/index/index": { "network": "all", "packages": ["goods"] }
}
```

- 键必须是**已声明的页面路径**（主包页面）。
- `packages` 里写分包 `root` 或分包 `name`；写 `__DEFAULT__` 表示默认预下载策略。
- 预下载会消耗用户流量，`network: "all"` 表示不限网络，谨慎用。
- 预下载不是越多越好：给所有分包都配，等于把首屏加载变成全量加载。

## 四、tabBar

```json
"tabBar": {
  "list": [
    { "pagePath": "pages/index/index", "text": "首页",
      "iconPath": "assets/icons/home.png",
      "selectedIconPath": "assets/icons/home-active.png" }
  ]
}
```

易错点：
- `iconPath` 是**相对小程序根目录**的路径，不是相对 pages。
- 图标文件不存在 → 工具报 `SCAN-012`；真机上该 tab 会没有图标但依然能点，很容易漏测。
- 图标体积建议压到很小（官方对尺寸与大小有建议值，以 `app.json` 文档为准），四个 tab 八张图很容易吃掉几十 KB。
- tabBar 项数常规是 2 到 5 项，少于 2 项或多于 5 项都要重新考虑信息架构。

## 五、permission 与 requiredPrivateInfos

```json
"permission": {
  "scope.userLocation": { "desc": "用于显示附近门店，不会用于其它用途" }
},
"requiredPrivateInfos": ["getLocation", "chooseLocation"]
```

- 这两项是**两件事**：`permission` 是弹窗里给用户看的用途说明，`requiredPrivateInfos` 是告知平台你用了哪些隐私接口。
- 调了接口却没声明 → 接口直接失败，且提审会被驳回（工具报 `SCAN-040`）。
- `desc` 要写"用来干什么"，不要写"需要获取您的位置"这种复述接口名的话，审核会问用途。

## 六、其它常被忽略的字段

| 字段 | 作用 | 不写会怎样 |
|---|---|---|
| `lazyCodeLoading: "requiredComponents"` | 按需注入组件代码 | 启动时加载全部组件，启动包体偏大 |
| `sitemapLocation` | 指定搜索索引配置 | 搜不到，或用了默认策略不符合预期 |
| `style: "v2"` | 启用新版组件样式 | 老样式在新基础库下表现不一致 |
| `requiredBackgroundModes` | 声明后台能力（如音频） | 后台播放会被中断 |
| `usingComponents`（全局） | 全局注册组件 | 每个页面都要重复声明 |

## 七、project.config.json 关键项

- `miniprogramRoot`：小程序代码所在子目录。工具靠它定位根目录，写错会扫不到 `app.json`。
- `appid`：提审前必须换成**正式 AppID**。用测试号或占位符提审会失败。
- `setting.urlCheck`：本地调试可临时关，**提审前必须打开**，否则上线后请求被拦。
- `packOptions.ignore`：把 `node_modules`、设计稿源文件、`.md` 文档排除掉，这一步经常能省下几百 KB。

## 八、配置写完的自检顺序

1. `wx_doctor.py scan` → P0 清零
2. `wx_doctor.py budget` → 主包占比有数字
3. 开发者工具编译 → 看有没有 warning
4. 真机预览 → tabBar 图标、页面跳转、授权弹窗各点一遍
