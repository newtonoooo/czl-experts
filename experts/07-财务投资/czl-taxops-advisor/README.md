# 财税全流程专家（czl-taxops-advisor）

面向中国中小微企业主、个体经营者和新财务的财税顾问型专家。核心是**一条连续的链路**：票据 → 账务 → 报表 → 申报 → 分析 → 内控，中间不断档。

开发者：虫志龙 · 47190078@qq.com

## 它解决什么问题

财税类问答最常见的两种失败：一种是听起来都对、落不了地；另一种是数字看着专业、其实口径就错了。这个专家用三件事应对：

1. **先校准再分析**。给数据就先把勾稽关系跑一遍，不平就不往下分析，把差异金额和可能原因说清楚。
2. **数字可复算**。自带一个纯标准库计算工具，比率、杜邦、量价拆分、申报日历都能算给你看，不是模型心算。
3. **缺口直说**。信息不全就出待补清单，标明"补哪一项最划算"，不用模糊表述填满篇幅。

## 六个阶段

| 阶段 | 做什么 | 不满足就不放行 |
| --- | --- | --- |
| G0 接单与脱敏 | 定身份、期间、口径、任务目标 | 身份或期间不明 |
| G1 数据校准 | 单位统一、三表勾稽、表内合计 | 勾稽差异未解释 |
| G2 经营诊断 | 结构、比率、现金流质量、趋势 | 结论指不回数据 |
| G3 税务判定 | 身份→行为→税种，优惠适用性四态 | 缺适用前提 |
| G4 方案成型 | 每条动作有责任人、时限、验收方式 | 出现"加强管理"类表述 |
| G5 交付与留痕 | 结论、数据、待补、风险台账、口径声明 | 无口径声明 |

## 自带的计算工具

```bash
python skills/czl-taxops-pipeline/scripts/toolkit.py check    --file samples/demo-2026-09.json
python skills/czl-taxops-pipeline/scripts/toolkit.py ratios   --file samples/demo-2026-09.json --capex 20000
python skills/czl-taxops-pipeline/scripts/toolkit.py variance --file samples/variance-demo.json
python skills/czl-taxops-pipeline/scripts/toolkit.py calendar --year 2026 --month 10
python skills/czl-taxops-pipeline/scripts/toolkit.py selftest
```

纯 Python 标准库，无第三方依赖，可离线运行。

## 目录结构

```
czl-taxops-advisor/
├─ .codebuddy-plugin/plugin.json     专家清单（元数据、头像引用、推荐提问）
├─ agents/czl-taxops-advisor.md      主提示词：角色、六阶段、纪律、边界
├─ avatars/avatar-512.png            原创头像 512×512
├─ skills/czl-taxops-pipeline/
│  ├─ SKILL.md                       技能入口：何时用哪段、放行条件、自检
│  ├─ references/01—07              七份流程与口径文件
│  └─ scripts/toolkit.py             计算工具
├─ samples/                          两份示例输入
├─ README.md  CHANGELOG.md  LICENSE
├─ docs/                             交付文档（装进专家时不需要，随 zip 一并交付）
└─ dev/                              开发与打包工具（不随包分发）
```

发布包 `dist/czl-taxops-advisor-v1.0.0.zip` 内只含 18 个文件：清单、主提示词、头像、技能包（含七份参考与脚本）、示例、README、CHANGELOG、LICENSE、manifest.yaml。`docs/` 与 `dev/` 不装入专家，避免把开发过程文件塞进用户环境。

## 安装

在 WorkBuddy 的专家中心导入 `dist/czl-taxops-advisor-v1.0.0.zip`，或将本目录放入专家插件目录后重启。导入后请在专家列表确认头像正常显示（本包已按平台解析规则校验，见 `docs/功能测试报告.md`）。

## 边界

提供知识框架与计算辅助，不构成税务筹划建议、审计鉴证或法律意见；不代客户申报、不索取密码与网银信息。政策口径以国家税务总局、财政部及主管税务机关最新发布为准。

## 许可

商业许可，详见 `LICENSE`。未经书面许可不得转售、再分发或用于制作衍生产品。
