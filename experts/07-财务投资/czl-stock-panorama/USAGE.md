# 使用说明

## 一、安装

**方式 A：导入 zip（推荐给最终用户）**

自己用 → `dist/czl-stock-panorama-1.0.1-local.zip`；提交上架 → `dist/czl-stock-panorama-1.0.1.zip`。
两者差异见第七节，选错会出现"图标变文字"或"格式不支持：无扩展名"。
zip 内只有一个顶层目录 `czl-stock-panorama/`，与平台要求一致。

**方式 B：放入自建市场目录（推荐给开发者）**

```bash
cp -r czl-stock-panorama ~/.workbuddy/plugins/marketplaces/my-experts/plugins/
```

重启后出现在专家列表。若列表里看不到，检查 `.codebuddy-plugin/plugin.json` 是否被完整复制（该目录以点开头，某些解压工具会跳过）。

## 二、三种用法

### 1. 一句话速览

> 600519 现在什么状态，能不能拿？

给：档位结论 + 三条支撑 + 三条风险 + 关键位 + 置信度，300 字以内。

### 2. 完整体检

> 帮我把宁德时代从头到尾诊断一遍，每个维度都要给依据。

给：七节报告（结论摘要 / 六维评分 / 关键价位 / 同业对标 / 多空证据 / 事件与治理 / 数据体检）。

### 3. 横向对比

> 用同一套标准对比五粮液和泸州老窖，告诉我分差出在哪个分项。

给：各自六维分 + 对比矩阵 + 差异归因 + 条件式结论（什么情况下选谁）。

## 三、它能工作，前提是有数据

专家本身不带数据。取数有两条路：

**路 A：已连接行情/财务类 MCP 工具**
直接说股票代码即可，它会按 `references/data_adapters.md` 的映射去取。
当前支持的映射以通达信类工具为例（`tdx_quotes` / `tdx_kline` / `tdx_indicator_select` / `tdx_api_data` / `tdx_screener` / `wenda_news_query` / `wenda_notice_query`）。换数据源只改这张表。

**路 B：你自己给数据**
把行情页、财报页截图发给它，或贴一段数据。它会逐项抄录并回读确认（`PE 18.5 / ROE 17.1% / 净利同比 18%，对吗？`），图上看不到的字段留空，不猜。

> 数据不够时它不会硬给结论，而是给一张缺数清单（`templates/intake_form.md`），一次问完。

## 四、自己跑引擎（不经过对话）

适合批量处理、或想验证它的算法。

```bash
cd skills/stock-panorama-core/scripts

# 1. 体检：单位、缺失、时效
python -m panorama.cli check --input my.json

# 2. 打分：输出六维 JSON
python -m panorama.cli score --input my.json --out score.json

# 3. 出报告
python -m panorama.cli report --input my.json --out report.md

# 4. 只算关键价位
python -m panorama.cli levels --input my.json
```

环境要求：Python 3.9+，**无第三方依赖**（不需要 numpy/pandas）。

### 输入 JSON 怎么写

最小可用：

```json
{
  "meta": {"code": "600519", "name": "贵州茅台", "as_of": "2026-10-27",
            "adjust": "前复权", "report_period": "2026-06-30"},
  "valuation": {"pe_ttm": 21.5, "pb": 7.2},
  "profitability": {"roe_ttm": 24.1, "net_margin": 50.3},
  "series": {"closes": [..], "highs": [..], "lows": [..], "volumes": [..]}
}
```

完整结构见 `examples/sample_input.json`，字段说明见 `references/scoring_rules.md`。

三个容易踩的点：

1. **百分数写 24.1 还是 0.241**：ROE、毛利率、净利率、负债率、商誉占比、质押比例这几项，引擎会把 ≤1.5 的值自动当小数换算；其它字段（增速、资金占比）不做自动换算，只提醒你确认。要统一按小数口径，在 meta 里写 `"units": {"percent_format": "decimal"}`。
2. **复权方式**：不写就按前复权处理，但报告会标注"未声明"，置信度封顶为中。
3. **K 线序列**：给了 `series` 就本地复算全部技术指标；只给 `technical` 里的现成数值也能跑，但报告会注明"未复算"。

## 五、输出怎么读

报告头七项先看：**数据截止日、财务报告期、复权方式、置信度、覆盖率、总分、档位**。
其中置信度和覆盖率决定了这份报告能信几分：

| 覆盖率 | 引擎行为 |
|---|---|
| ≥85% | 正常出分，置信度可能为高 |
| 60%–85% | 出分，置信度为中，报告列出待补项 |
| <60% | **不给总分**，档位显示 N/A，只做定性描述 |

六维里任何一维覆盖率 <40%，该维标注"数据不足"，不参与总分——不是 0 分。

## 六、常见问题

**Q：为什么它说"PE 无经济含义"？**
A：标的亏损，PE 为负，估值指标失效。此时看 PB、PS、现金流更靠谱，报告会跳过 PE 评分。

**Q：为什么两个维度都写了"中性偏强"，总分却是 C？**
A：维度分 60–75 都叫"中性偏强"，但 62 和 74 差很多；总分是加权后落档，C 是 55–65 区间。

**Q：同业只有两家，为什么不做排名？**
A：样本少于 3 家时排名没有统计意义，引擎只列数值，不给分位结论。

**Q：它能不能直接告诉我买还是卖？**
A：不能，这是设计边界。它给状态判断、证据链和风险位；买卖是你的风险偏好决定的。

**Q：导入后专家列表里图标变成一个字？**
A：见下面第七节。

## 七、两个包有什么不同（必读）

平台校验对 `plugin.json` 有两条硬规则，它们互相冲突，所以本产品同时出两个包：

| 规则 | 后果 |
|---|---|
| `avatar` 必须是**带扩展名的图片路径**（png/jpg/webp） | 写 data URI 会被判"格式不支持：当前为（无扩展名）" |
| `defaultInitPrompt` 必须与 `quickPrompts[0]` **逐字一致** | 中英任一条不一致都直接解析失败 |

| 包 | 头像字段 | 用途 |
|---|---|---|
| `czl-stock-panorama-1.0.1.zip` | `avatars/expert.png` | 提交平台**上架**（图会随包上传到 CDN） |
| `czl-stock-panorama-1.0.1-local.zip` | 内联 `data:image/png;base64,...` | **本地分发/自用**，导入任意机器都能显示图标 |

两个包除 `avatar` 一个字段外完全相同。选错的表现：

- 拿 local 包上架 → 平台报"格式不支持：无扩展名"；
- 拿 market 包在自己机器上装 → 图标退化成名字首字（原因见下）。

## 八、头像显示为文字的原因与处理

WorkBuddy 渲染专家头像时，会把 `plugin.json` 里的**相对路径**拼到官方 CDN 前缀上：
`avatars/expert.png` → `https://acc-.../workbuddy/expert-marketplace/avatars/expert.png`。
官方市场上架的专家图已在该 CDN 上，所以能显示；本地自建分发的包没有，请求 404，头像组件就退化为渲染名字首字——看起来就是"图标没了，变成一个汉字"。本地文件不会被读取。

所以：

- 只想自己用、想看到图标 → 用 `-local` 包，或 `python tools/set_avatar_mode.py --mode data-uri`；
- 要提交平台上架 → 保持 `avatars/expert.png` 相对路径，或 `--mode path`。

`data:` 协议是被渲染层显式放行的（不会被拼到 CDN 上），这条结论来自对渲染层代码的分析，详见 `docs/开发记录.md` 第 4 节。

## 九、提交上架前的自检

```bash
python tools/verify_package.py                       # 源码目录，按上架标准
python tools/verify_package.py --zip dist/xxx.zip    # 直接验收某个包（解压后全量检查）
python tools/verify_package.py --avatar-mode local   # 按本地分发标准
```

体检覆盖 39–40 项，其中六项是平台解析失败的常见原因，本地先拦住：
头像扩展名、`defaultInitPrompt` 一致性、包名正则、语义化版本、双语字段齐全、快捷词条数。

## 十、自检与打包命令

```bash
python tools/make_avatar.py         # 重新生成头像（需 Pillow）
python tools/set_avatar_mode.py --check          # 当前头像模式
python tools/verify_package.py                   # 包体检
python tools/build_dist.py                       # 一次产出两个包
python tools/build_dist.py --only local          # 只出本地分发版
```

改过评分规则后，务必重跑：

```bash
cd skills/stock-panorama-core/scripts && python ../tests/selftest.py
```

