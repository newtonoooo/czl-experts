# 第三方组件与来源说明（NOTICE）

本文件如实说明本专家包内每一项内容的来源，供平台审核与商业发布前的尽调使用。

## 一、原创内容（无第三方权利负担）

| 内容 | 位置 | 说明 |
|---|---|---|
| 角色设定与七条工作流提示词 | `agents/czl-a-share-trading-desk.md` | 独立撰写 |
| 数据引擎全部源码 | `skills/a-share-tape-desk/scripts/`（12 个 `.py`） | 独立编写，仅使用 Python 标准库 |
| 离线测试用例 | `skills/a-share-tape-desk/tests/selftest.py` | 独立编写，25 个用例 |
| 参考文档与模板 | `skills/a-share-tape-desk/references/`、`templates/` | 独立撰写 |
| 头像 | `avatars/czl-a-share-trading-desk.png` | 由图像生成模型按自拟提示词生成，后经裁切、缩放、颜色量化处理；无第三方素材 |
| 构建工具 | `tools/png_crop.py` | 独立编写，零依赖 |
| 文档 | `README.md`、`docs/`、`CHANGELOG.md` | 独立撰写 |

## 二、运行期依赖

**无。** 运行本专家只需要 Python 3.8 及以上版本的标准库，
不引入 pip 包、不引入 npm 包、不下载任何二进制、不加载外部脚本。

这意味着：不存在需要核实"商业使用许可"的第三方库。

## 三、外部数据接口（非代码依赖，但有使用风险）

本专家运行时会访问以下公开行情接口读取数据：

| 接口 | 域名 | 用途 |
|---|---|---|
| 腾讯行情 | `qt.gtimg.cn` | 实时快照（主源） |
| 腾讯日线 | `web.ifzq.gtimg.cn` | 前复权日线（主源） |
| 新浪行情 | `hq.sinajs.cn` | 实时快照与指数（备源） |
| 新浪数据中心 | `vip.stock.finance.sina.com.cn` | 全市场分页、行业/概念板块 |
| 东方财富 | `push2his.eastmoney.com` | 日线（备源） |

**必须知晓**：
1. 这些接口是行情页面公开使用的查询地址，开发者**未取得任何书面授权或数据许可协议**。
2. 它们没有 SLA、没有稳定性承诺，且存在频率限制（实测连续高频请求会被临时断流）。
3. 若本产品上架后需要规模化商业运营，**应当另行取得合规行情数据授权**（交易所行情授权或持牌数据商）。
   这一点在 `docs/商业发布风险清单.md` 中列为高风险项，未解决前不建议以"数据服务"名义单独售卖。

## 四、未使用的内容（明确声明）

为避免审核时产生疑问，明确声明本包内**不存在**以下内容：

- 任何第三方专家包的提示词、代码、文档、头像或其改写版本
- 任何开源项目的源码副本（包括 MIT / Apache / GPL 等各类许可证下的代码）
- 任何付费数据库、付费研报、未公开数据
- 任何品牌标识、他人肖像、他人商标

## 五、图像生成说明

头像由图像生成模型按以下自拟提示词生成（原文）：

```
Professional cartoon-style illustration avatar, a male China A-share intraday trading analyst
in his early thirties, sharp short black hair, clean-shaven, youthful sharp appearance,
wearing a crisp white dress shirt with sleeves rolled up to the forearms and a slim dark navy
waistcoat, one hand lightly adjusting his cuff, arms relaxed, calm confident half-smile,
focused alert eyes looking straight at the viewer, no glasses, modern energetic vibe.
Background: deep navy blue gradient with one thin gold price line arcing upward and a few
minimal candlestick silhouettes, faint thin grid lines, subtle gold accent glow.
Bust shot, facing forward, centered composition, shoulders visible.
Clean simple dark blue with gold accent background. High quality, professional, natural,
square avatar illustration.
```

生成结果含平台水印，已裁切右下角 80px 并由 `tools/png_crop.py` 缩放至 512×512、量化至每通道 6 位，
最终文件 234 KB（＜500 KB）。原始 1024×1024 图另存于项目工作区 `build/avatar_raw/`，未纳入发布包。

生成模型的服务条款请以该模型提供方的约定为准；若平台要求提供生成凭证，可提供生成时间与提示词原文（如上）。
