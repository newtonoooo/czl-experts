# NOTICE · 来源与第三方声明

本文件说明「三棱镜·专业数据分析专家」v1.0.0 各组成部分的来源，
供商业发布前的权利核查使用。

---

## 一、原创内容（版权归虫志龙所有）

| 组件 | 说明 |
|---|---|
| `agents/czl-triprism-analyst.md` | 独立撰写。六道工序、三视职责划分、证据分级、异常处理均为本项目设计 |
| `skills/czl-triprism-playbook/` | 独立撰写。6 份方法参考 + 2 张表单模板 |
| `tools/*.py`（11 个模块） | 独立实现。CSV/XLSX 读写、体检、口径校验、三视分析、复算、HTML/XLSX 渲染、PNG 处理、发布自检、打包 |
| `avatars/expert.png` | 由开发者自有品牌图（三棱镜棱镜分光徽标）裁切缩放而来，视觉概念为原创 |
| `docs/*`、`README.md`、`CHANGELOG.md` | 独立撰写 |

---

## 二、第三方代码依赖

**无。**

全部 Python 代码只使用标准库：

```
argparse csv datetime hashlib html io json math os py_compile re
statistics struct sys tempfile time traceback zipfile zlib xml.etree.ElementTree
```

标准库随 Python 发布，适用 PSF License，允许商业使用与再分发。
因此本产品**不包含任何需要单独授权、署名或开源披露的第三方代码**。

---

## 三、运行时外部依赖

| 依赖 | 性质 | 说明 |
|---|---|---|
| Python 3.9+ | 运行环境 | WorkBuddy 自带受管 Python，无需用户安装 |
| WorkBuddy 平台 PPT 能力 | 可选 | 仅当需要 `.pptx` 时，由本专家把 `deck_spec.json` 交给平台内置 PPT 技能生成；本包不打包该能力 |
| 中文字体 | 渲染 | HTML 使用系统字体，不内嵌字体文件，无字体授权问题 |

---

## 四、平台字段与规范

`plugin.json` 中的字段名（`expertType`、`agentName`、`agents`、`avatar`、
`displayName`、`quickPrompts`、`tags` 等）属于 WorkBuddy 平台的接口约定，
使用这些字段名是平台兼容性要求，不构成对任何第三方作品的复制。

---

## 五、与同作者另一产品的关系

本产品与「三棱镜·专业数据分析专家团」（包名 `czl-triprism-data-team`）为同一作者的两个形态：

- 共用同一套本地工具链与分析纪律
- 本产品为 Agent 型单专家；另一产品为 Team 型多成员
- 两者代码与文档各自独立成包，可分别安装、分别上架

两者之间不涉及第三方权利，也不存在互相复制他人作品的问题。

---

## 六、明确未使用的内容

本产品在开发过程中**未使用**以下任何内容：

- 其他作者专家包的提示词、工作流定义、代码、文档原文
- 其他作者专家包的头像、品牌图像、宣传文案
- 任何需要授权才能商用的数据集、模型权重、图标库
- 任何未公开的第三方接口或私有 SDK

---

## 七、示例数据声明

`tests/fixtures/` 下的 CSV 由 `make_fixtures.py` 程序化合成，
不含任何真实企业、真实客户或真实个人信息，仅用于功能测试。

---

## 八、联系

虫志龙 · 47190078@qq.com
