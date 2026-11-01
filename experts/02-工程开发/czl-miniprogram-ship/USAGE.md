# 使用说明

这份说明按"你会怎么用"来写，不按功能清单来写。

---

## 场景一：从零开始做一个小程序

### 第 1 步：让它收口需求（W0）

直接说人话就行：

> "我想做个给小区邻居拼团买菜的小程序，先做首版。"

它会做四件事：问清品类/用户/后端/阶段（最多四问）、把需求拆成编号条目、定技术栈、扫类目资质红线。产出两个文件：

- `docs/一页方案.md` —— 一页纸说清做什么、**不做什么**、怎么选型
- `docs/acceptance.json` —— 条目台账，机器可读

如果你说"我要做得好看点、流畅点"，它会把这条打回去，改成 `首页首屏在 iPhone SE 宽度下不出现横向滚动` 这种能判真假的写法。这不是较真，是因为"好看"在交付时无法验收。

### 第 2 步：定骨架、算体积（W1）

给它一句"按条目建骨架"，它会写出一个 `spec.json` 然后跑：

```bash
python skills/wx-doctor/scripts/wx_doctor.py scaffold --spec spec.json --out ./miniprogram
python skills/wx-doctor/scripts/wx_doctor.py budget ./miniprogram
```

生成的骨架不是空文件，页面里已经带了**加载/空/错误三态**和防重复请求的闸门。预算输出会告诉你主包占了多少、谁在吃体积。

**关键判据**：主包超过上限 85%，它会要求再切一次分包。这时候切，比写完二十个页面再切便宜十倍。

### 第 3 步：按条目写页面（W2）

每条需求都带 ID（`A-01`、`A-02`）。写完一条，它会：

```bash
python skills/wx-scope/scripts/ledger.py set docs/acceptance.json --id A-01 --status done
```

注意：**没绑文件的条目，这个命令会直接报错**。这是故意的——没有绑定文件的"完成"是假的。

写页面时它会先给数据契约（`data` 形状、事件名、接口），再给四件套。这个顺序不能反，反了模板里的字段名会到处漏。

### 第 4 步：接登录和支付（W3）

说清你要哪些能力。它会先过四道闸门：

1. 资质（支付要商户号+类目）
2. 隐私（指引要先配）
3. 域名（要备案、要 https）
4. iOS（虚拟商品不能用微信支付）

然后给前端代码 + 云函数/服务端代码 + 后台配置清单 + 官方文档路径。

支付这块有一条它一定会强调：**前端 `success` 只用来跳转，发货以服务端回调为准**。

### 第 5 步：提审前跑预检（W5）

```bash
python skills/wx-doctor/scripts/wx_doctor.py preflight ./miniprogram
```

输出里有四样东西：P0/P1/P2 清单、提审七件材料、采集接口清单（填隐私指引用）、外部域名清单（配白名单用）。

**只有 P0 = 0 才会说"可以提审"。** 它不会说"应该没事"。

### 第 6 步：被拒了怎么办（W6）

把驳回意见**原文照抄**给它。它会：

1. 拆句（一条驳回可能含两三个独立问题）
2. 每条映射到检查项或代码位置
3. 给整改方案（改根因，不做表面遮掩）
4. 给复审说明（改了什么、在哪、怎么验）

转述驳回意见是常见错误——转述会丢掉审核员真正在意的那个词。

---

## 场景二：接手一个半成品

直接说"这是我的工程，帮我看看能不能提审"，然后给路径。它会：

1. 跑 `scan`，出 P0/P1/P2
2. 跑 `budget`，看体积余量
3. 建台账，把现有页面反推成条目（你会看到哪些页面其实没做完）
4. 给"先修什么"的顺序建议

**注意**：如果工程是 uni-app/Taro 的源码目录，结构检查要指向编译产物（`dist/` 或 `unpackage/`），它会在报告里标注降级。

---

## 场景三：只想问一个配置问题

比如"分包怎么配 preloadRule"。不需要走完整流程，直接问，它会给配置片段 + 易错点 + 官方文档路径。这类问题不建台账。

---

## 命令速查

### 体检工具

```bash
D=skills/wx-doctor/scripts/wx_doctor.py

python $D scan      ./miniprogram              # 静态体检
python $D budget    ./miniprogram              # 体积预算
python $D preflight ./miniprogram              # 提审预检
python $D scan      ./miniprogram --json r.json # 附机器可读结果
python $D scan      ./dist --root .             # 手动指定根目录

python $D scaffold --spec spec.json --out ./miniprogram
```

| 参数 | 说明 |
|---|---|
| `--root <子目录>` | 小程序根目录（含 `app.json` 那层） |
| `--out <目录>` | 报告输出位置，默认 `<项目>/docs/体检` |
| `--json <路径>` | 额外输出 JSON |
| `--quiet` | 只出结论行 |

### 台账工具

```bash
L=skills/wx-scope/scripts/ledger.py

python $L init docs/acceptance.json --project 社区团购
python $L add  docs/acceptance.json --title "首页分类跳转" \
       --verify "点分类→进入对应列表，返回后状态保留" \
       --files pages/index/index.js --gate W2
python $L set  docs/acceptance.json --id A-01 --status doing
python $L next docs/acceptance.json      # 下一条该干什么
python $L report docs/acceptance.json    # 进度 + 完整性校验
```

状态只能按 `todo → doing → done → accepted` 走，`done`/`accepted` 必须有绑定文件，否则脚本报错退出（退出码 2）。

---

## 它怎么读体检报告

| 级别 | 处理 |
|---|---|
| **P0** | 必须改完才能提审，一条不留 |
| **P1** | 本次迭代内改掉；改不掉的写进风险表并说明原因 |
| **P2** | 记录、排期，不阻塞提审 |

**"未发现" ≠ "一定没有"**。静态扫描有盲区（动态调用、混淆过的密钥、接口返回的域名），拿不准的它会写成"需人工确认"。

体积有两个数：脚本算的磁盘字节，和开发者工具算的压缩上传体积，差 10%-30% 正常。上线前以开发者工具为准。

---

## 常见问题

**问：能不能不建台账，直接写代码？**
可以，但那就退回成普通的代码助手了。台账解决的是"上次做到哪、还有哪没验"，没有它，第三轮对话一定重复劳动。

**问：脚本报的 P1 我觉得不重要，能跳过吗？**
能，但要写进风险表并写清为什么不改。跳过不等于不存在——出问题时第一个被问的就是这条。

**问：我的项目在 Windows 上，路径有中文/空格，脚本会挂吗？**
不会。所有路径都用 `os.path` 处理；唯一注意的是命令行里给路径要加引号。

**问：能不能扫 uni-app 源码？**
能扫，但页面路径与 `app.json` 的对应关系在编译后才成立，所以结论只作参考。建议扫 `dist/dev/mp-weixin` 或 `unpackage/dist/dev/mp-weixin`。

**问：平台的类目/资质规则变了怎么办？**
它会先说"以公众平台后台为准"再给建议。规则类信息不要以本包为准，以官方为准。
