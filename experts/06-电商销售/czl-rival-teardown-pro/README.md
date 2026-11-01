# 拆敌 · czl-rival-teardown-pro

> 亚马逊竞品拆解专家。给一个竞品，还你一套能执行、能验证的打法。

- **开发者**：虫志龙（47190078@qq.com）
- **版本**：1.0.0
- **类型**：单 Agent 专家（expertType: agent）
- **分类**：07-SalesCommerce 销售商务
- **运行依赖**：无外部服务、无 API Key、无第三方 Python 包

---

## 它解决什么问题

卖家最常见的困境不是「不知道对手是谁」，而是三件事：

1. **看不懂**：对手的 listing 明明很普通，为什么排名比我高？
2. **说不清**：知道对手强，但说不出强在哪一层，团队无法对齐。
3. **落不下**：看完分析很受启发，第二天不知道先改哪一句文案。

拆敌把这三件事串成一条链：**证据 → 分层结论 → 评分 → 单一主攻方向 → 带验证指标的动作清单**。

---

## 和普通「竞品分析」的区别

| 普通做法 | 拆敌的做法 |
|---|---|
| 把对手夸一遍、骂一遍 | 每层只回答三个问题：他做了什么选择 / 服务谁 / 代价是什么 |
| 结论靠感觉 | 每条结论挂证据编号（E1/E2/E3），无编号的降级为「待验证」 |
| 给一堆建议 | 只给 1 个主攻 + 1 个备选，并写明另外几个为什么被淘汰 |
| 建议无法验收 | 每条动作带验证指标与验证周期 |
| 数据缺了就编 | 缺口单列成表，写清影响哪一层的哪个结论 |
| 报告写完就完 | 交付前跑结构质检，未通过不算完成 |

---

## 快速开始

### 1. 最小可用输入

```
拆解这个竞品 B0XXXXXXXX，我要做差异化
```

有链接更好：

```
https://www.amazon.com/dp/B0XXXXXXXX 帮我拆一下，我的产品是 XXX，卖 $XX
```

### 2. 没有抓取能力时

把页面内容贴进来即可，最少给这 6 项：

1. 标题全文
2. 五点描述全文
3. 价格、评分、评论数
4. 主图和副图各在讲什么（一句话一张）
5. 10-30 条评论（好评差评都要）
6. QA 里的前 5 个问题

### 3. 你会拿到什么

| 文件 | 用途 |
|---|---|
| `竞品拆解-{ASIN}-{日期}.md` | 完整报告，15 章，给运营负责人 |
| `打法卡-{ASIN}-{日期}.md` | 一页纸，给老板和跨部门 |
| `文案种子-{ASIN}-{日期}.md` | 3 个角度的标题/五点草稿 |
| `证据台账-{ASIN}-{日期}.csv` | 字段级来源，供复核 |

样例见 `samples/竞品拆解-B0DEMO0001-2026-10-28.md`（虚构数据，仅演示格式）。

---

## 五层拆解框架

| 层 | 回答的问题 | 权重 |
|---|---|---|
| L1 需求定位 | 他在服务哪个场景里的哪类人，放弃了谁 | 20% |
| L2 表达 | 他用什么叙事骨架和词序说服人 | 20% |
| L3 视觉 | 第一眼赢在哪，视觉问答链缺了哪一环 | 20% |
| L4 口碑 | 用户为什么买、为什么退，QA 防线在哪 | 25% |
| L5 格局 | 他在价格带和流量结构里占什么位置 | 15% |

加权总分 → 强度档位 → 建议打法（正面压 / 单点突破 / 侧翼 / 换战场）。

详细定义见 `skills/rival-teardown-playbook/references/framework.md`。

---

## 内置工具

```bash
# 解析用户输入（ASIN / 链接 / 短链 / 纯文本）
python3 skills/rival-teardown-playbook/scripts/teardown_toolkit.py parse "https://www.amazon.com/dp/B08N5WRWNW"

# 生成证据台账骨架
python3 skills/rival-teardown-playbook/scripts/teardown_toolkit.py ledger --asin B08N5WRWNW --out 证据台账.csv

# 计算加权强度分
python3 skills/rival-teardown-playbook/scripts/teardown_toolkit.py score --positioning 78 --message 85 --visual 90 --voice 72 --arena 65

# 生成报告骨架
python3 skills/rival-teardown-playbook/scripts/teardown_toolkit.py scaffold --asin B08N5WRWNW --date 2026-10-28 --out 竞品拆解.md

# 报告结构质检（未通过返回退出码 1）
python3 skills/rival-teardown-playbook/scripts/teardown_toolkit.py check 竞品拆解.md

# 自测
python3 skills/rival-teardown-playbook/scripts/teardown_toolkit.py selftest
```

发布前完整性检查：

```bash
python3 tools/package_qa.py
```

---

## 目录结构

```
czl-rival-teardown-pro/
├── .codebuddy-plugin/plugin.json      专家元数据
├── agents/czl-rival-teardown-pro.md   主 Agent 定义
├── skills/rival-teardown-playbook/    拆解手册（框架/规则/模板/脚本）
├── avatars/expert.png                 头像 512×512
├── samples/                           演示样例
├── tools/package_qa.py                发布前检查
├── docs/                              规格、用法、测试、风险、清单、开发记录
├── README.md  CHANGELOG.md  LICENSE  NOTICE.md
```

---

## 边界与不做的事

- 不抓取非公开数据，不绕过登录、验证码、付费墙。
- 不编造销量、转化率、广告花费；拿不到就标「未获取」。
- 不代写侵权文案，不照抄竞品原文。
- 不承诺效果（不写「照此执行可提升 X%」）。
- 不评价对手团队或人品，只评价策略选择。

---

## 许可

本专家包为虫志龙所有的商业产品，许可条款见 `LICENSE`。第三方组件情况见 `NOTICE.md`。

问题与反馈：47190078@qq.com
