# 功能测试日志

执行时间：2026-10-26 16:03:32
被测包：C:\Users\丛自龙\.workbuddy\plugins\marketplaces\my-experts\plugins\czl-data-evidence
Python：3.13.14

## 通过（62）

- [x] period_compare 退出码为 0
- [x] period_compare 基期合计 40,000
- [x] period_compare 对比期合计 36,000
- [x] period_compare 变化 -4,000 与 -10.0%
- [x] period_compare 件数 400 → 280
- [x] period_compare 三因子：量 -12,000
- [x] period_compare 三因子：价 +11,428.57
- [x] period_compare 三因子：交互 -3,428.57
- [x] period_compare 分解校验残差为 0
- [x] period_compare 分组：线上 -12,000
- [x] period_compare 分组：门店 +8,000
- [x] period_compare 分组校验残差 <1%
- [x] funnel 退出码为 0
- [x] funnel 各步人数正确
- [x] funnel 单步率 32.0% / 46.9% / 65.3%
- [x] funnel 换算出金额
- [x] funnel 基期模式退出码 0
- [x] funnel 基期相对跌幅 -15.8%（加购）
- [x] cohort 退出码为 0
- [x] cohort 2026-07 群 60.0% / 40.0%
- [x] cohort 2026-08 群 50.0%
- [x] cohort 不可观测期标「—」
- [x] cohort 均值 55.0%（只算可观测群）
- [x] segment 退出码为 0
- [x] segment 总额 76,000
- [x] segment 主体数 20
- [x] segment 三层都出现
- [x] segment RFM 退出码为 0
- [x] segment RFM 出分群表
- [x] ab 退出码为 0
- [x] ab 两组比例 5.10% / 7.80%
- [x] ab 绝对差 +2.70 个百分点
- [x] ab z 值 2.458
- [x] ab p 值 0.0140
- [x] ab 区间 [+0.55, +4.85]
- [x] ab 结论用词为「显著」
- [x] ab 明细表模式退出码 0
- [x] ab 明细表模式算出 51 / 78
- [x] profile 退出码为 0
- [x] profile 行列数 680 × 8
- [x] profile 五维评级齐全
- [x] profile 给出三条影响提示
- [x] profile 无缺失时措辞正确
- [x] doc_export 退出码为 0
- [x] docx 文件已生成
- [x] html 文件已生成
- [x] docx 包结构完整
- [x] docx XML 合法可解析
- [x] docx 含表格
- [x] docx 中文未丢失
- [x] html 含表格与标题
- [x] html 声明 UTF-8
- [x] 异常-文件不存在：退出码 2
- [x] 异常-文件不存在：中文提示
- [x] 异常-period 写法错：退出码 2
- [x] 异常-period 写法错：给出示例
- [x] 异常-baseline 步数不一致：退出码 2
- [x] 异常-baseline 步数不一致：说明原因
- [x] 异常-空文件：退出码 2
- [x] 异常-空文件：中文提示
- [x] 异常-列名不存在：退出码 2
- [x] 异常-列名不存在：列出可用列

## 结论

全部通过。
