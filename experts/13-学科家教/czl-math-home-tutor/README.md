# 卓识教育-高中数学学习辅导专家 —— 陆九章

一个**先诊断再讲题**的高中数学家庭辅导专家。由虫志龙开发（47190078@qq.com），独立实现，非任何现有专家的改名版本。

- 包名：`czl-math-home-tutor`
- 版本：1.0.0
- 类型：Agent 型（单专家）
- 分类：`15-Education`

## 它解决什么问题

家长最常见的三句话：

1. "考了 90 分，不知道问题出在哪。"
2. "这题讲过了，下次还是错。"
3. "时间不够，后面大题根本没看。"

这三句话对应三个真实缺口：**没有定位手段、没有复现机制、没有取舍策略**。这个专家按这三个缺口建了四条流水线，而不是再写一份题型大全。

## 四环工作流

```
定位 ──▶ 拆解 ──▶ 训练 ──▶ 复盘
diagnose  decompose  drill   ledger
                    └── examroom（考场取舍，随时可插入）
```

| 环节 | 技能 | 产出 |
|---|---|---|
| 定位 | `czl-math-diagnose` | 断点排序表 + C/M/A/W/R 错因码 + 带时长的处方 |
| 拆解 | `czl-math-decompose` | 解题卡（条件编号 / 路线淘汰理由 / 缺口 / 三验） |
| 训练 | `czl-math-drill` | 同型 / 换皮 / 换轴三档变式 + 时间盒 + 停止条件 |
| 复盘 | `czl-math-ledger` | 错题台账 + 1/3/7/21/45 天复现 + 周报 |
| 取舍 | `czl-math-examroom` | 目标分 → 分题型目标 → 每题时间上限 → 放弃线 |

## 三个别人没有的东西

1. **错因五码（C/M/A/W/R）**：把"粗心""基础差"换成可训练的判断。每个码配一个动作、一个时长、一个验收标准。
2. **降级表**：学生说"没思路"时，不说第二遍，按表往下退一格（只圈数字 → 换小例子 → 只写三条路 → 只做缺口）。
3. **可执行的脚本**：诊断排序、训练配比、复现排期、考场计划，四个脚本纯标准库，离线可跑，产出 CSV/Markdown 可直接打印。

## 安装

### 方式一：放进专家目录（推荐，头像能正常显示）

```bash
# 解压后把整个 czl-math-home-tutor 目录放到：
#   Windows: %USERPROFILE%\.workbuddy\plugins\marketplaces\my-experts\plugins\
#   macOS/Linux: ~/.workbuddy/plugins/marketplaces/my-experts/plugins/
python tools/install.py            # 自动复制 + 校验 + 写入 marketplace.json
```

然后重启 WorkBuddy，在「专家中心 → 我的专家」里选择「陆九章」。

### 方式二：导入 zip

`dist/czl-math-home-tutor-1.0.0.zip` 可用平台的专家导入功能直接导入。

> **导入后如果头像显示成一个字（"陆"），看 `docs/头像显示异常排查.md`。** 这是路径解析问题，不是图片坏了。

## 自检

```bash
python tools/check_package.py --verbose
```

检查 38 项：字段完整性、name/agentName/skill 名称一致性、tags 与 quickPrompts 数量、头像尺寸与真实编码格式、脚本语法、文档齐备。

## 脚本

| 脚本 | 用途 | 示例 |
|---|---|---|
| `skills/czl-math-diagnose/scripts/diagnose.py` | 卷面 → 断点排序 + 处方 | `python diagnose.py scores.csv --top 4` |
| `skills/czl-math-decompose/scripts/verify.py` | 三验的数值工具 | `python verify.py --expr "x^2-3x+2" --zero 1,2` |
| `skills/czl-math-drill/scripts/drill.py` | 单次训练配比 | `python drill.py --weak "导数:M" --minutes 45` |
| `skills/czl-math-ledger/scripts/ledger.py` | 错题台账 + 排期 | `python ledger.py due --csv err.csv` |
| `skills/czl-math-examroom/scripts/scoreplan.py` | 考场得分计划 | `python scoreplan.py --target 120` |
| `tools/check_package.py` | 发布前自检 | `python tools/check_package.py` |
| `tools/png_resize.py` | 头像裁剪/压缩（无 Pillow 也能用） | `python png_resize.py in.png out.png --size 512` |

全部脚本仅依赖 Python 3.8+ 标准库。

## 目录

```
czl-math-home-tutor/
├── .codebuddy-plugin/plugin.json   专家元数据
├── agents/czl-math-home-tutor.md   主提示词
├── avatars/expert.png              512×512 PNG，214 KB
├── skills/                         5 个工作流（各含 SKILL.md / scripts / templates）
├── materials/                      7 份资料（知识树、公式、方法卡、错因表、卷面、家长手册）
├── tools/                          自检与安装工具
├── docs/                           规格、文案、使用说明、开发记录、测试报告、风险清单
├── dist/                           发布包
├── README.md / CHANGELOG.md / LICENSE
```

## 边界

- 不代写作业、不代做整卷、不押题、不预测考点。
- 不承诺提分数字。
- 不评价孩子能力、天赋、态度。
- 不收录教材原文与高考真题原文（版权原因，见 `materials/README.md`）。

## 许可

专有软件，商业分发需授权。详见 `LICENSE`。
