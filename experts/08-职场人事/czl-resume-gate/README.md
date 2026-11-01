# 简锋 · czl-resume-gate

> 简历过筛与投递策略专家 —— WorkBuddy 专家包
> 开发者：虫志龙 ｜ 47190078@qq.com ｜ 版本 1.0.0

## 这是什么

一个把简历当**证据链**来修的专家，不是润色工具。

一份简历要走到面试桌，得连续通过三道闸门，每道闸门的失败原因完全不同：

| 闸门 | 谁在看 | 失败长什么样 |
|---|---|---|
| A 机器解析 | 招聘系统 | 邮箱抓不到、章节归错、表格把内容拆碎 |
| B 六秒扫描 | 招聘方人眼 | 全是职责没有结果，看完不知道这人什么水平 |
| C 追问耐受 | 面试官 | 数字没口径、团队成果写成个人成果、形容词撑不住 |

简锋先判断会死在哪一关，再决定改什么。**不给"整体不错，建议突出亮点"这种话**。

## 四个技能

| 技能 | 干什么 | 关键产出 |
|---|---|---|
| `resume-audit` | 三闸门体检（30/40/30 分） | 评分卡 + 致命项清单（≤6 条，每条带证据和改法） |
| `resume-rewrite` | 要点重写（AORE 框架） | Before→After + 待补数据清单 |
| `jd-tailor` | 岗位定制 | JD 四栏拆解 + 覆盖矩阵 + 差距分级 |
| `resume-export` | 交付 | .docx / A4 打印版 HTML / ATS 纯文本 |

## 会用到的脚本

全部只用 Python 标准库，不需要安装任何依赖。

```bash
# 三闸门机械体检（联系方式、章节、日期、量化率、弱动词、版式风险）
python skills/resume-audit/scripts/resume_audit.py 简历.md --jd JD.md

# 岗位覆盖匹配（必备/加分拆解、可迁移识别、硬门槛对照）
python skills/jd-tailor/scripts/jd_match.py --jd JD.md --resume 简历.md

# 交付三种格式
python skills/resume-export/scripts/md2docx.py 简历.md -o 姓名-岗位.docx
python skills/resume-export/scripts/md2html.py 简历.md -o 简历.html --theme navy
python skills/resume-export/scripts/md2txt.py 简历.md -o 简历.txt

# 包完整性自检
python scripts/selfcheck.py
```

## 三条硬边界

1. **不编数字。** 用户没给的量化数据一律写成 `【待补：…】`，让他自己回填。不做"合理推演"式填空。
2. **不伪造经历。** 学历、在职时间、职级、证书、项目归属，一个字都不动。可以重排、可以换说法、可以只讲相关的。
3. **不做歧视性建议。** 不按性别、年龄、婚育状况给"隐形减分"建议。

## 目录结构

```
czl-resume-gate/
├── .codebuddy-plugin/plugin.json   专家元数据
├── agents/czl-resume-gate.md       主 Agent（角色、路由、输出契约）
├── skills/
│   ├── resume-audit/               体检：SKILL + 评分细则 + 风险目录 + 脚本 + 样例
│   ├── resume-rewrite/             重写：SKILL + AORE + 动词表 + 证据分级 + 工作表
│   ├── jd-tailor/                  定制：SKILL + JD 拆解 + 匹配脚本 + 差距矩阵
│   └── resume-export/              交付：SKILL + 规范 + 三个导出脚本 + 骨架模板
├── avatars/expert.png              原创头像（512×512，约 188 KB）
├── scripts/selfcheck.py            包完整性自检
├── docs/                           产品规格、使用说明、测试报告、风险清单等
├── README.md  CHANGELOG.md  LICENSE
```

## 安装

把整个目录放到专家目录下：

```
%USERPROFILE%\.workbuddy\plugins\marketplaces\my-experts\plugins\czl-resume-gate\
```

然后注册：

```bash
python <expert-manager>/scripts/register_expert.py <上面这个目录>
```

## 版权

本包为独立开发作品，版权归虫志龙所有。未包含任何第三方代码、提示词模板或图像资源，运行时不依赖第三方库。详见 `LICENSE` 与 `docs/商业发布风险清单.md`。
