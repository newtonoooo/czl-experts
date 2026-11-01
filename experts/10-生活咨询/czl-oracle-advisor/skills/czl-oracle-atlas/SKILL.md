---
name: czl-oracle-atlas
description: Assembles the deliverable page. Turns a computed chart plus a written reading into one self-contained HTML file that opens offline, prints cleanly and can be forwarded — with a different visual language per divination system (BaZi black-gold, Zi Wei night-blue, Plum Blossom paper-white, Six-Line ink-vermilion, Tarot deep-violet, Almanac bronze-green). Triggers on 出个图, 生成报告, 做成页面, HTML, 可视化, 能发出去的, 打印.
---

# 图册装配

**职责**：把"算出来的盘"和"读出来的话"装进一个能交付的页面。只管装配与质检，不改盘面数据、不另写解读。

## 职责边界

- **做**：选配色、填解读、出单文件 HTML、过质检清单
- **不做**：算盘（`czl-oracle-engine`）、写结论（各 read 模块）

## 输入参数

| 参数 | 必填 | 说明 |
|---|---|---|
| 盘面数据 | 是 | `oracle.py` 产出的 JSON，或直接用 `--html` 让脚本内部生成 |
| 解读 JSON（`--notes`） | 否 | 结构见下。给了就嵌进页面，不给页面只有盘面 |
| 输出路径 | 是 | 建议 `{流派}-{主题}-{标识}.html` |

### 解读 JSON 契约

```json
{
  "summary": "总断，三到五句，一段话",
  "sections": [
    {"title": "盘面依据", "body": "一段连贯说明，不用分号硬凑", "items": []},
    {"title": "事业", "body": "", "items": ["条目一", "条目二"]}
  ],
  "actions": ["具体到能当天做的一条", "第二条"],
  "one_line": "留一句能被记住的话"
}
```

`body` 与 `items` 二选一或并用；`items` 渲染成列表，适合并列要点。

## 执行步骤

1. **定流派**：一个页面只讲一个体系。不要在一个 HTML 里混排八字和塔罗——读者会晕，体例也会打架。
2. **先跑盘**，把 JSON 存到临时文件（`--out-json`），需要复核时不用重算。
3. **写解读 JSON**，按六段式收敛；文案自己写，不要把引擎里的术语原样堆进去。
4. **渲染**：
   ```bash
   python "<引擎目录>/oracle.py" bazi --date ... --gender ... --lon ... \
     --html "out/八字-1990-女.html" --notes "out/notes.json"
   ```
5. **质检**，见下。

## 配色对照（由脚本自动套用，不要手改）

| 体系 | 视觉语言 |
|---|---|
| 八字 | 黑底金边，四柱表 + 五行条 + 大运时间轴 |
| 紫微 | 深蓝紫银河，十二宫格 + 四化徽章（徽章内联跟随宫名，禁止浮层） |
| 梅花 | 素纸水墨，本卦/互卦/变卦三卡 + 体用对照 |
| 六爻 | 墨黑朱砂，爻线 + 六神 + 世应 + 变卦 |
| 塔罗 | 深紫鎏金，牌位卡 + 正逆位标 |
| 择日 | 墨绿古铜，时辰时间轴 + 候选日表 |

## 质检清单（逐条过）

- [ ] 页面顶部有：体系名、英文副题、生辰/起卦时间等 meta
- [ ] 盘面表格数字与 JSON 一致（抽查四柱、命宫、卦名三处）
- [ ] 解读区出现在盘面之后，不是之前
- [ ] 底部有免责声明（脚本已内置，不要删）
- [ ] 页面里没有 `%s`、`None`、`nan` 之类残留
- [ ] 手机窄屏打开不横向溢出（脚本已内置 720px 断点）
- [ ] 文件是单文件，无外链 CSS/JS/图片

## 输出与交付

- 页面生成后必须**告诉用户文件路径**，并说明可以直接双击打开、可打印、可发微信文件。
- 不要只生成不吱声。

## 异常处理

| 情况 | 处理 |
|---|---|
| 渲染报错 | 把报错原文贴出来，降级为对话文字版交付，不要假装已生成 |
| 用户要 PDF | 让用户用浏览器"打印 → 存为 PDF"，本产品不直接产 PDF |
| 用户要 Word | 说明 HTML 可直接复制到文档，或另走文档工具 |
