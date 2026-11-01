# 功能测试报告

- **被测版本**：`czl-uae-growth-marketing-pro` v1.0.1
- **测试日期**：2026-10-28
- **测试环境**：Windows 10/11 · Python 3.13.12 · WorkBuddy 5.8.4
- **测试方式**：本地实际执行，结果由脚本输出，非人工填写

> **声明**：本报告只记录**实际跑过**的测试。未执行的验证项单列在最后一节，不标记为通过。

---

## 一、结果总览

| 层级 | 用例数 | 通过 | 失败 | 执行命令 |
|------|-------|------|------|---------|
| 单元测试 | 67 | 67 | 0 | `python -m unittest discover -s tests` |
| 集成测试 | 24 | 24 | 0 | `python tests/run_integration.py` |
| 包自检 | 33 | 33（33 PASS + 0 WARN） | 0 | `python bin/package_check.py` |

```
Ran 67 tests in 3.180s
OK

合计：24 PASS · 0 FAIL

合计：PASS 33 · WARN 0 · FAIL 0
结论：通过
```

---

## 二、单元测试明细

### 2.1 `tests/test_plan.py` — 预算模型（15 项，全通过）

```
Ran 15 tests in 0.026s
OK
```

| 用例 | 验证内容 |
|------|---------|
| `test_allocation_sums_exactly_to_working_budget` | 7 档预算 × 4 种目标 = 28 组组合，分配之和恒等于可投放预算 |
| `test_shares_sum_to_about_hundred` | 占比合计为 100%（以可投放预算为分母） |
| `test_reserve_zero_allocates_whole_budget` | 测试预留为 0 时全额分配 |
| `test_channel_count_respects_budget_tier` | 2 万/5 万/30 万/80 万分别不超过 2/4/4/6 个渠道 |
| `test_large_budget_keeps_a_trust_channel` | 30 万预算必含信任层渠道 |
| `test_conversion_objective_keeps_conversion_channel` | 转化目标在 3 档预算下均保留转化层 |
| `test_awareness_objective_keeps_discovery_channel` | 声量目标保留发现层 |
| `test_no_channel_below_its_minimum_budget` | 任一渠道分配不低于其起投门槛 |
| `test_avoided_channels_are_never_selected` | 美妆行业不会选出户外广告（行业备注中标为回避） |
| `test_impression_band_is_ordered` | 13 个渠道的曝光/触达区间上下界有序 |
| `test_assumptions_are_always_attached` | 输出必带 ≥4 条建模假设 |
| `test_markdown_output_carries_the_disclaimer` | Markdown 输出含"平台实时报价"校准提示 |
| `test_bad_budget_rejected` / `test_bad_reserve_rejected` | 非法入参返回退出码 2 |
| `test_valid_run_returns_zero` | 合法入参返回 0 |

### 2.2 `tests/test_compliance.py` — 合规扫描（12 项，全通过）

```
Ran 12 tests in 0.015s
OK
```

| 用例 | 验证内容 |
|------|---------|
| `test_absolute_claim_is_high_risk` | "第一品牌 + 100% 保证有效"命中 CLM-01、CLM-02，结论为阻断 |
| `test_clean_copy_passes` | 正常营业文案无 High，结论为通过 |
| `test_gambling_blocked` | 博彩类命中 SUB-01，阻断 |
| `test_sector_scoping_excludes_other_sectors` | 教育类规则不对美妆生效，仅对教育生效 |
| `test_ascii_pattern_uses_word_boundary` | `roi` 不会误命中 `android` 内部 |
| `test_findings_sorted_by_severity` | 结果按 High→Medium→Low 排序 |
| `test_context_snippet_present` | 每条命中都带上下文片段 |
| `test_high_risk_returns_exit_1` | High 风险退出码 1 |
| `test_clean_text_returns_exit_0` | 干净文案退出码 0 |
| `test_empty_text_rejected` / `test_missing_file_rejected` | 空输入、文件不存在返回 2 |
| `test_json_format_is_parseable` | JSON 输出可被解析且结论正确 |

### 2.3 `tests/test_calendar.py` — 节点日历（18 项，全通过）

```
Ran 18 tests in 0.002s
OK
```

| 用例 | 验证内容 |
|------|---------|
| `test_known_year_matches_table` | 2027 斋月 02-08、开斋节 03-10 与锚点表一致 |
| `test_unknown_year_drifts_backwards` | 表外年份（2033）按每年约 11 天向前漂移 |
| `test_ramadan_window_is_about_thirty_days` | 斋月窗口 28~30 天 |
| `test_override_shifts_every_hijri_node` | 官方日期覆盖后，斋月与开斋节同步平移 4 天 |
| `test_gregorian_nodes_do_not_shift` | 国庆日与元旦不随伊斯兰历平移 |
| `test_windows_sorted_by_start` | 窗口按起始日排序 |
| `test_ramadan_prep_precedes_ramadan` | 备货窗口在斋月之前 |
| `test_caveats_always_present` | 输出必含"官方观月"提示 |
| `test_milestones_anchor_on_a_high_priority_window` | 倒推里程碑锚定高优先级商业窗口 |
| `test_saturday/sunday/friday_moves_back_to_thursday` | 周五、周六、周日截止日回退至周四 |
| `test_shift_never_moves_later` | 连续 14 天验证回退只会提前不会延后 |
| `test_ics_structure` | ICS 首尾标记正确，事件成对且 ≥5 个 |
| `test_markdown_contains_caveat` | Markdown 含"以官方观月为准" |
| `test_cli_rejects_out_of_range_year` / `accepts_valid_year` | 年份越界返回 2，合法年份返回 0 |

### 2.4 `tests/test_package.py` — 包完整性（13 项，全通过）

```
Ran 13 tests in 3.678s
OK
```

| 用例 | 验证内容 |
|------|---------|
| `test_name_is_prefixed_and_kebab` | 包名以 `czl-` 开头且为 kebab-case |
| `test_plugin_field_matches_name` | `plugin` 与 `name` 一致 |
| `test_author_is_the_developer` | 作者为虫志龙 / 47190078@qq.com |
| `test_exactly_three_tags_and_prompts` | tags 与 quickPrompts 均为 3 个 |
| `test_default_prompt_matches_first_quick_prompt` | 默认引导语与第一条推荐提示一致 |
| `test_agent_file_matches_agent_name` | agentName 对应 MD 文件存在 |
| `test_declared_skills_exist` | 3 个声明的技能均有 SKILL.md |
| `test_avatar_is_square_png_within_budget` | 头像为正方形 PNG、≥512px、<500KB |
| `test_package_check_passes` | 包自检零 FAIL |
| `test_channel_catalog_is_consistent` | 13 个渠道 id 唯一、角色合法、均有采买口径或 retainer 模式 |
| `test_every_sector_bias_points_to_a_real_channel` | 12 个行业的渠道引用全部指向真实渠道 |
| `test_audience_segments_have_basis` | 5 个人群层均带合法 basis |
| `test_risk_rules_are_well_formed` | 22 条规则 id 唯一、等级合法、均有替代表达 |

### 2.5 `tests/test_avatar.py` — PNG 工具链（9 项，全通过）

```
Ran 9 tests in 3.387s
OK
```

| 用例 | 验证内容 |
|------|---------|
| `test_roundtrip_of_shipped_avatar` | 成品头像可被解码，尺寸 512×512，像素数正确 |
| `test_rejects_non_png` | 非 PNG 输入抛 `PngError`，不静默出错 |
| `test_crop_dimensions_and_content` | 裁剪尺寸正确，首像素与源图对应坐标一致 |
| `test_crop_clamps_to_bounds` | 越界裁剪自动收敛到图像边界（500,500 + 9999 → 12×12） |
| `test_flatten_emits_rgb` | `--flatten` 输出 PNG colour type 2（RGB），非 RGBA |
| `test_rounded_mask_makes_corners_transparent` | 圆角蒙版四角 alpha=0，中心 alpha=255 |
| `test_flatten_rejects_bad_colour` | 非法颜色值抛异常 |
| `test_avatar_meets_platform_rules` | 成品：正方形、≥512、8bit、colour type ∈ {2,6}、<500KB |
| `test_normalize_writes_requested_size` | 指定 size=256 时输出确为 256×256 |

---

## 三、集成测试明细

命令：`python tests/run_integration.py`（通过 subprocess 真实调用 CLI，校验退出码与输出）

| # | 检查项 | 结果 |
|---|--------|------|
| 1 | `uae_plan` 基础调用 | PASS |
| 2 | 输出含渠道表 | PASS |
| 3 | 输出含建模假设 | PASS |
| 4 | JSON 模式且分配精确 | PASS |
| 5 | 拒绝非法预算（exit=2） | PASS |
| 6 | 16 组预算×目标全通过 | PASS |
| 7 | `uae_compliance` High 风险返回 1 | PASS |
| 8 | 输出阻断结论 | PASS |
| 9 | 干净文案返回 0 | PASS |
| 10 | 行业规则生效（EDU-01） | PASS |
| 11 | 文件模式扫描 | PASS |
| 12 | `uae_campaign_calendar` 基础调用 | PASS |
| 13 | 含斋月窗口 | PASS |
| 14 | 含官方观月提示 | PASS |
| 15 | 官方日期覆盖生效 | PASS |
| 16 | ICS 导出结构正确 | PASS |
| 17 | 拒绝越界年份（exit=2） | PASS |
| 18 | `intel_query` 人群查询 | PASS |
| 19 | `intel_query` 渠道查询 | PASS |
| 20 | `intel_query` 行业渠道排序（13 条且有序） | PASS |
| 21 | `intel_query` 拒绝未知 id（exit=2） | PASS |
| 22 | `package_check` 自检通过 | PASS |
| 23 | 包自检零 FAIL | PASS |
| 24 | `avatar_tool` 可重新归一化 | PASS |

---

## 四、测试中发现并修复的缺陷

测试不是走流程，确实抓到了 5 个真实缺陷，全部已修复并复测通过。

| # | 缺陷 | 影响 | 修复 |
|---|------|------|------|
| 1 | 角色覆盖保证会互相覆盖：先补信任层，再被转化层顶掉 | 声量方案缺信任层，配比结构不完整 | 改为"必需角色优先占位 + 剩余按分数填充" |
| 2 | 渠道分配可能低于自身起投门槛（25 万预算下户外分到 5.25 万，门槛 6 万） | 输出无法执行的方案 | 增加 `allocate_with_floor`，分配后校验并重分配 |
| 3 | 渠道占比以总预算为分母，合计只有 90% | 表格自相矛盾，客户一眼看出问题 | 改为以可投放预算为分母，列头改为"占可投放" |
| 4 | 截止日回退只跳过周六周日，周五仍被当作安全截止日 | 阿联酋周五为政府半日，截止日不可靠 | 改为回退至周一至周四，并补 3 个测试 |
| 5 | `allocate_with_floor` 中元组解包错误 | 全部预算相关用例报错 | 修正为字典查表 |
| 6 | 包自检把 `.pyc` 编译缓存写到源码目录旁边，偶发文件锁冲突导致误报 FAIL | 全量测试偶发 1 个 error（58 项中） | 改为编译到临时目录，连续三轮全量测试稳定通过 |

> 第 6 项是测试稳定性问题，不修会导致"有时过有时不过"，属于必须消除的隐患。修复后连续执行三轮：`58 tests / OK`、`58 tests / OK`、`58 tests / OK`，且源码目录无残留 `__pycache__` 或 `.tmpc`。

---

## 五、性能

| 操作 | 实测耗时 |
|------|---------|
| `uae_plan` 单次建模 | 0.02~0.05 秒 |
| `uae_compliance` 单次扫描 | < 0.02 秒 |
| `uae_campaign_calendar` 生成年度日历 | < 0.01 秒 |
| 全量单元测试（67 项） | 3.2 秒（含 13 次包自检与 PNG 编解码） |

---

## 六、尚未验证的事项

以下项目**没有**执行，不作通过结论。

| # | 未验证项 | 原因 | 建议验证方式 |
|---|---------|------|------------|
| 1 | 在**全新** WorkBuddy 实例中的导入与显示 | 需第二台设备或干净环境 | 按 `docs/ICON_FALLBACK_DIAGNOSIS.md` 第三节四条自查后导入 |
| 2 | 专家中心列表头像的实际渲染效果 | 需在客户端 UI 目视确认 | 导入后看列表卡片与输入框 chip 两处 |
| 3 | 专家对话的实际回答质量 | 需多轮真实对话评估 | 用 `plugin.json` 中 3 条 quickPrompts 各跑一轮 |
| 4 | 阿语文案的母语可读性 | 无母语审校人 | **必须**由阿语母语者终审后再对外使用 |
| 5 | 知识库 CPM 区间与真实账户报价的偏差 | 无真实投放账户数据 | 用客户后台历史数据反算 CPM 后校准 `channel_catalog.json` |
| 6 | 伊斯兰历日期与官方公告的一致性 | 官方按观月公布，无法提前锁定 | 拿到官方日期后用 `--ramadan-start` 覆盖 |
| 7 | 平台审核通过率 | 需实际提交 | 提交后按审核反馈调整 |
| 8 | macOS / Linux 下的路径行为 | 仅在 Windows 测试 | 脚本使用 `pathlib`，理论兼容，但未实测 |

---

## 七、复现方式

```bash
cd czl-uae-growth-marketing-pro

# 单元测试
python -m unittest discover -s tests

# 集成测试
python tests/run_integration.py

# 包自检
python bin/package_check.py
```

全部命令在 Python 3.10+ 下可运行，无第三方依赖。
