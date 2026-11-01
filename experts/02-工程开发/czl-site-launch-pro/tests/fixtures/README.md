# 测试夹具说明

这些文件只用于自测脚本，不参与专家运行时。

| 目录 | 用途 | 预期结果 |
|---|---|---|
| `good-site/` | 结构规范的小型静态站 | `audit_html.py` 无阻塞/高；`budget_check.py` 通过；`deploy_preflight.py` 无阻塞 |
| `bad-site/` | 集中触犯多条规则 | `audit_html.py` 退出码 2，至少命中 H001/H009/H011/H013 |
| `leaky-app/` | 产物含假密钥、localhost、sourcemap | `deploy_preflight.py` 退出码 2，命中 P03/P05/P12，且输出中密钥被脱敏 |

`over-budget/` 不落盘，由 `run_tests.py` 在临时目录里生成（避免仓库里放几百 KB 的垃圾文件）。
