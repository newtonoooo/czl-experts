# 功能测试报告

- 被测版本：czl-rival-teardown-pro 1.0.0
- 测试日期：2026-10-28
- 测试环境：Windows（win32），Python 3.13.12，WorkBuddy 桌面端（本地专家目录）
- 测试执行：虫志龙
- 结论：**包结构与工具链测试全部通过；端到端对话效果与市场审核未验证（见第五节）**

---

## 一、测试范围

| 编号 | 测试项 | 类型 | 结果 |
|---|---|---|---|
| T01 | 官方校验脚本 validate_expert.py | 结构 | PASS |
| T02 | 发布前完整性检查 package_qa.py（37 项） | 结构 | PASS |
| T03 | 工具箱内置回归测试 selftest（13 个断言组） | 功能 | PASS |
| T04 | parse 子命令（URL/裸 ASIN/短链/纯文本/空输入） | 功能 | PASS |
| T05 | ledger 子命令（CSV 骨架生成） | 功能 | PASS |
| T06 | score 子命令（加权计算与档位判定） | 功能 | PASS |
| T07 | scaffold 子命令（15 章骨架生成） | 功能 | PASS |
| T08 | check 子命令（骨架应失败 / 填充后应通过） | 功能 | PASS |
| T09 | 样例报告质检通过 | 功能 | PASS |
| T10 | 脚本语法编译检查 | 质量 | PASS |
| T11 | 打包与解包结构还原 | 结构 | PASS |
| T12 | 专家注册到 marketplace.json | 集成 | PASS |
| T13 | data-URI 兼容版构建 | 功能 | PASS |
| T14 | 端到端对话产出质量 | 体验 | 未验证 |
| T15 | 市场审核与上架展示 | 平台 | 未验证 |

---

## 二、详细执行记录

### T01 官方校验

```
$ python3 validate_expert.py <专家目录>
🔍 Validating expert package: .../czl-rival-teardown-pro
✅ Expert package is valid!
```

0 error、0 warning。

### T02 发布前完整性检查

```
$ python3 tools/package_qa.py
共 37 项，通过 37 项，失败 0 项
```

覆盖：name kebab-case、czl- 前缀、plugin 与 name 一致、语义化版本、作者信息、
四个 i18n 字段中英齐全、displayDescription 中文 47 字（40-50 区间）、categoryId 合法性、
tags=3、quickPrompts=3、defaultInitPrompt 与第一条一致、agentName 对应 MD 存在、
frontmatter name 一致、frontmatter 无 tools 字段、agents/skills 路径、skill 三个子目录、
头像存在/389.1KB/512×512/ASCII 路径、README/CHANGELOG/LICENSE、无 hooks 与 commands、
脚本仅依赖标准库。

> 首轮测试曾失败 1 项：displayDescription 中文 51 字（超上限）。已改为 47 字后复测通过。
> 这属于真实缺陷被测试拦截，不是形式化通过。

### T03 内置回归测试

```
$ python3 teardown_toolkit.py selftest
SELFTEST PASSED  (0 failures)  toolkit v1.0.0
  parse: 6 cases | score: 4 cases | scaffold+check: 2 cases | ledger: 1 case
```

覆盖：URL 提取 ASIN、站点识别、裸 ASIN、gp/product 路径、短链标记、纯文本、空输入、
加权总分精度、档位边界、最弱层识别、越界分数报错、骨架章节完整性、骨架质检应失败、
填充后质检应通过、台账行数与表头。

> 首轮测试曾失败 2 项：加权总分期望值写错（实为 78.3，测试写了 77.8）、
> 证据编号去重导致填充后仍不足 3 个。均已修正测试与实现后通过。

### T04 parse 实测

```
$ python3 teardown_toolkit.py parse "https://www.amazon.com/dp/B08N5WRWNW?ref_=abc"
{
  "input_type": "url",
  "asin": "B08N5WRWNW",
  "site": "US",
  "domain": "amazon.com",
  "url": "https://www.amazon.com/dp/B08N5WRWNW",
  "needs_expand": false,
  "missing_fields": ["评分与评论数", "价格与优惠形式", "主图与副图内容描述"],
  "notes": []
}
```

### T05 ledger 实测

```
$ python3 teardown_toolkit.py ledger --asin B08N5WRWNW --out 证据台账-B08N5WRWNW-2026-10-28.csv
台账已生成：...证据台账-B08N5WRWNW-2026-10-28.csv（23 个字段，全部标记为未获取/U）
```

### T06 score 实测

```
$ python3 teardown_toolkit.py score --positioning 78 --message 85 --visual 90 --voice 72 --arena 65
| L1 需求定位 | 20% | 78 | 15.6 |
| L2 表达     | 20% | 85 | 17.0 |
| L3 视觉     | 20% | 90 | 18.0 |
| L4 口碑     | 25% | 72 | 18.0 |
| L5 格局     | 15% | 65 | 9.8  |
| **加权总分** | 100% | — | **78.3** |

强度档位：可战
建议打法：单点突破：选一层做到明显超过他，其余层跟住不落后
最强层：L3 视觉｜最弱层：L5 格局｜层间极差：25
```

人工复核：78×0.2 + 85×0.2 + 90×0.2 + 72×0.25 + 65×0.15 = 15.6+17+18+18+9.75 = 78.35 → 78.3，一致。

### T07 scaffold 实测

```
$ python3 teardown_toolkit.py scaffold --asin B08N5WRWNW --date 2026-10-28 --out 竞品拆解.md --name "折叠收纳箱"
骨架已生成：...（3611 字符，待填项用 <!-- FILL --> 标记）
```

### T08 check 双态验证

未填充骨架（应失败）：

```
[PASS] 章节完整性：16 节齐全
[FAIL] 无占位符残留：残留: <!-- FILL
[FAIL] 结论带证据编号：识别到 0 个编号
[FAIL] 口碑层样本量披露：未在 L4 找到「样本量：N 条」
[FAIL] 数据缺口表：缺口表为空或未填
[FAIL] 合规红线小节：缺失或未填
[PASS] 无绝对化用语：未命中
结论：未通过，请修复 FAIL 项
退出码 1
```

填充后的样例报告（应通过）：

```
$ python3 teardown_toolkit.py check samples/竞品拆解-B0DEMO0001-2026-10-28.md
[PASS] 章节完整性：16 节齐全
[PASS] 无占位符残留：无
[PASS] 结论带证据编号：识别到 15 个编号
[PASS] 口碑层样本量披露：已披露
[PASS] 数据缺口表：2 行缺口
[PASS] 合规红线小节：已填写
[PASS] 无绝对化用语：未命中
结论：通过
退出码 0
```

> 首次运行样例时「无绝对化用语」误报：合规小节里列举了「最好」「永久」等违禁词，
> 被扫描器当成正文命中。已改为扫描时排除第 14 节（合规红线）内容，复测通过。

### T10 语法编译

```
$ python3 -m py_compile tools/package_qa.py skills/.../teardown_toolkit.py
PY_COMPILE_OK
```

### T11 打包与解包结构还原

用官方 `package_expert.py` 打包，再用模拟平台导入逻辑的脚本（`build_tools/simulate_import.py`，
复刻「解压 → 定位 plugin.json → 校验专家 id → 检查引用文件」四步）验证：

```
$ python3 package_expert.py <专家目录> <输出目录>
✅ Packaged 25 files ... Size: 468.5 KB

$ python3 simulate_import.py release/czl-rival-teardown-pro.zip
[1] 解压：25 个条目
[2] 找到清单：czl-rival-teardown-pro\.codebuddy-plugin\plugin.json
[3] 专家 id 合法：czl-rival-teardown-pro
[4] 安装目标：my-experts/plugins/czl-rival-teardown-pro/
    [PASS] 头像文件：avatars/expert.png
    [PASS] Agent MD：./agents/czl-rival-teardown-pro.md
    [PASS] Skill 入口：./skills/rival-teardown-playbook
    [PASS] Skill/references / templates / scripts
[5] 头像：389.1 KB
结论：导入结构检查通过
```

> 首轮打包曾把 1.1MB 的原始 1024 图一并打入（包体 1619KB）。已把原图移出包外，
> 复打包后 468.5KB。

### T12 注册

```
$ python3 register_expert.py <专家目录>
✅ Registered 'czl-rival-teardown-pro' in marketplace.json
```

注册后 marketplace.json 中新增条目（name / source / description 三项），与平台行为一致。

### T13 data-URI 兼容版

```
$ python3 tools/package_qa.py --portable release/czl-rival-teardown-pro-portable.zip
兼容版已生成：...（861.9 KB，头像以 data URI 内嵌）

$ python3 simulate_import.py release/czl-rival-teardown-pro-portable.zip
[1] 解压：25 个条目
    [PASS] 头像内联(data URI)：519 KB 内联
结论：导入结构检查通过
```

两个包均通过导入结构检查；标准版 468.5KB，兼容版 861.9KB（头像 base64 内联后体积增大）。

---

## 三、缺陷记录

| 编号 | 现象 | 原因 | 修复 | 状态 |
|---|---|---|---|---|
| D01 | displayDescription 中文 51 字，超出 40-50 规范 | 文案未数字数 | 改写为 47 字 | 已修复 |
| D02 | selftest 加权总分断言失败（期望 77.8，实得 78.3） | 测试期望值手算错误 | 修正为 78.3 | 已修复 |
| D03 | 填充后仍报「证据编号不足」 | 检查项按去重后的编号计数，5 个相同编号只算 1 个 | 测试改为写入不同编号；检查逻辑保持不变（去重计数是正确行为） | 已修复 |
| D04 | 合规小节引用违禁词被误判为正文违规 | 扫描范围包含合规节 | 扫描时排除第 14 节 | 已修复 |

四个缺陷均为开发过程中由测试发现并修复，无遗留。

---

## 四、未覆盖的测试

| 项 | 原因 | 影响 |
|---|---|---|
| 多平台 ASIN 实测（UK/DE/JP 等真实页面） | 未实际抓取真实商品页 | parse 的站点识别仅经单元测试，未在真实页面验证 |
| 大数据量评论（500 条以上）分析质量 | 需要真实竞品评论语料 | 未验证超长文本下的结论稳定性 |
| 与电商数据接口（MCP/连接器）联调 | 当前环境未配置电商数据工具 | 走用户供给通道的流程已验证，接口通道未验证 |

---

## 五、未验证事项（重要）

以下项目**未执行测试**，不得视为通过：

1. **端到端对话效果**：未在真实对话中让专家完整跑完一次「输入 → 四件套交付」，
   因此报告的实际可读性、结论质量、五层框架在真实数据上的表现，均未验证。
   已通过 `samples/` 提供人工撰写的示例报告作为格式基准，但示例非专家自动生成。
2. **市场审核**：未提交 WorkBuddy 专家中心审核，原创性认定、分成规则、
   data-URI 头像是否被接受，均未确认。
3. **跨机器导入的头像渲染**：本地注册已验证；导入到另一台机器/另一版本的渲染效果未实测
   （见 `docs/AVATAR-TROUBLESHOOTING.md` 第六节）。
4. **跨平台运行**：仅在 Windows + Python 3.13 下测试，macOS/Linux 未测试。
5. **Python 3.8/3.9 实机运行**：代码已对 `sys.stdlib_module_names`（3.10+）做降级处理，
   但未在 3.8/3.9 解释器上实际运行验证。
