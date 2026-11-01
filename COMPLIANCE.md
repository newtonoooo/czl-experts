# 合规自查报告

本报告只记录**内容层面**的合规问题，供上传 WorkBuddy 开放平台前修正。
「专家不在专家目录下」属于发布目录的位置性校验，对 GitHub 仓库无意义，已剔除。

共检查 61 个专家包，其中 20 个存在待修项。

| 包 | 分类 | 待修项 |
|---|---|---|
| `czl-product-strategy-solo` | 01-产品设计 | plugin.json: displayDescription.zh is 95 chars (recommended 40-50) |
| `czl-novel-director` | 05-内容创作 | plugin.json: displayDescription.zh is 77 chars (recommended 40-50) |
| `czl-amazon-listing-growth` | 06-电商销售 | plugin.json: displayDescription.zh is 59 chars (recommended 40-50) |
| `czl-ashare-research-writer` | 07-财务投资 | plugin.json: must have exactly 3 quickPrompts, got 5<br>plugin.json: displayDescription.zh is 86 chars (recommended 40-50) |
| `czl-stock-panorama` | 07-财务投资 | plugin.json: displayDescription.zh is 100 chars (recommended 40-50) |
| `czl-taxops-advisor` | 07-财务投资 | plugin.json: displayDescription.zh is 67 chars (recommended 40-50)<br>plugin.json: defaultInitPrompt.zh should match quickPrompts[0].zh |
| `czl-biology-home-tutor` | 13-学科家教 | plugin.json: invalid categoryId '15-Education' |
| `czl-chemistry-home-tutor` | 13-学科家教 | plugin.json: invalid categoryId '15-Education' |
| `czl-chinese-home-tutor` | 13-学科家教 | plugin.json: invalid categoryId '15-Education' |
| `czl-english-home-tutor` | 13-学科家教 | plugin.json: invalid categoryId '15-Education' |
| `czl-history-home-tutor` | 13-学科家教 | plugin.json: invalid categoryId '15-Education' |
| `czl-math-home-tutor` | 13-学科家教 | plugin.json: invalid categoryId '15-Education' |
| `czl-physics-home-tutor` | 13-学科家教 | plugin.json: invalid categoryId '15-Education' |
| `czl-chem-teaching-suite` | 14-教师教研 | plugin.json: invalid categoryId '15-Education'<br>plugin.json: displayDescription.zh is 81 chars (recommended 40-50) |
| `czl-chinese-teacher-desk` | 14-教师教研 | plugin.json: invalid categoryId '15-Education' |
| `czl-geo-teacher-desk` | 14-教师教研 | plugin.json: invalid categoryId '15-Education' |
| `czl-history-teaching-assistant` | 14-教师教研 | plugin.json: invalid categoryId '15-Education'<br>plugin.json: displayDescription.zh is 94 chars (recommended 40-50) |
| `czl-math-teacher-desk` | 14-教师教研 | plugin.json: invalid categoryId '15-Education' |
| `czl-physics-teacher-desk` | 14-教师教研 | plugin.json: invalid categoryId '15-Education' |
| `czl-politics-teacher-desk` | 14-教师教研 | plugin.json: invalid categoryId '15-Education' |

## 常见修法

- `displayDescription.zh` 超长：压到 40–50 字，保留核心能力与产出。
- `Team 'profession' must equal 'displayName'`：Team 型职业头衔必须与展示名一致。
- `Team type must have settings.json`：补 `{"agent": "<主理人 agentName>"}`。
- `quickPrompts` 必须正好 3 条，`defaultInitPrompt` 必须等于第一条。
- `avatar file not found`：头像不能用 base64 data URI，要落到 `avatars/` 下的实际文件。
