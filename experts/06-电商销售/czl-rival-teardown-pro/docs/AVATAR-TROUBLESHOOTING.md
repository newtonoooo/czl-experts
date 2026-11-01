# 头像显示为文字的原因与修复

## 现象

把专家包导入到另一个 WorkBuddy 后，专家卡片/对话头像不显示图片，而是显示一个文字块
（通常是名字首字）。同一份包在本机看起来正常，换机器或换版本后变成文字。

本文基于对 WorkBuddy 桌面端实际代码的阅读，说明加载链路、可能的失败点、排查步骤与修复方案。

---

## 一、已核实的加载链路（代码依据）

WorkBuddy 渲染专家头像走两条路，任一条失败都会退化成文字块。

### 路径 1：主进程把本地文件转成 URL

`ExpertPluginService` 读取专家目录下的 `plugin.json`，取 `avatar` 字段后调用：

```js
async resolveAvatarUrl(avatar, expertRootDir) {
  if (!avatar) return '';
  if (/^(https?|data):/.test(avatar)) return avatar;      // 已内联/远程，直接用
  const rel = avatar.replace(/^\.\//, '');
  const abs = path.resolve(expertRootDir, rel);
  if (!abs.startsWith(path.resolve(expertRootDir) + path.sep)) return '';  // 越界即丢弃
  const st = await fs.stat(abs);
  if (st.size > 5242880) { warn('avatar file is too large'); return ''; }  // 5MB 上限
  return toLocalFileUrl(abs);                              // local-file://local/<编码后的绝对路径>
}
```

`toLocalFileUrl` 的实现是逐段 `encodeURIComponent`，所以 Windows 盘符的冒号会变成 `%3A`：

```
local-file://local/C%3A/Users/%E4%B8%9B%E8%87%AA%E9%BE%99/.workbuddy-ai/.../avatars/expert.png
```

**这条路上的三个丢弃条件**：文件不存在 / 文件超过 5MB / 解析后路径逃出专家根目录。
任一命中 → 返回空字符串 → 前端拿不到图 → 显示文字。

### 路径 2：前端对非 URL 字符串的兜底

如果 `avatar` 传过来时仍然是相对路径（没有经过路径 1 转换），前端会走：

```js
function resolveExpertAvatarUrl(avatar) {
  ...
  return /^(https?|file|data|blob|local-file):/i.test(s) ? s : buildExpertUrl('/' + avatar);
}
// buildExpertUrl(x) => 'https://acc-1258344699.cos.accelerate.myqcloud.com/workbuddy/expert-marketplace' + x
```

也就是说：**相对路径会被拼成市场 CDN 地址**。对私有专家而言这个地址必然 404，
图片加载失败 → 显示文字。

### 路径 3：导入流程只登记三件事

导入 zip 时（`installExpertZipFromPath`）：

1. 解压 → 找 `.codebuddy-plugin/plugin.json`
2. 用 `plugin.json.name` 作为目录名（必须匹配 `^[a-zA-Z0-9._-]+$`）搬到
   `plugins/marketplaces/my-experts/plugins/<name>/`
3. 在 `my-experts/.codebuddy-plugin/marketplace.json` 里只写 `{name, source, description}`

**头像不会写进 marketplace.json**，每次渲染都依赖 `plugin.json.avatar` 指向的文件真实存在。
所以：包内缺图、路径写错、文件名大小写不一致，都会直接变成文字块。

---

## 二、可能的失败点（按概率排序）

| # | 失败点 | 依据 | 判断方法 |
|---|---|---|---|
| 1 | zip 里没有头像文件，或路径与 `plugin.json` 不一致 | 路径 3：只认文件真实存在 | 解压后检查 `avatars/expert.png` 是否存在 |
| 2 | 头像超过 5MB | 路径 1 有 5242880 字节硬上限 | 看文件大小 |
| 3 | 头像文件名大小写/编码不一致（如 `Expert.PNG`） | 大小写敏感环境下解析失败 | 逐字比对 `plugin.json.avatar` |
| 4 | `avatar` 用了相对路径但前端先于主进程拿到数据 | 路径 2：相对路径被拼成 CDN 地址 | 看 `assistant-display` 快照里 avatarUrl 是否为 `https://acc-...` |
| 5 | 版本差异导致 `local-file://` 协议或 `%3A` 解码不兼容 | 路径 1 生成的是编码过的盘符路径 | 换版本复现，观察是否只在某个版本出现 |

其中 1-3 属于包本身的问题，4-5 属于环境/版本问题。

---

## 三、排查步骤（3 分钟）

**第 1 步 看包**

```bash
# 解压 zip 后
ls -l czl-rival-teardown-pro/avatars/
python -c "import json;print(json.load(open('czl-rival-teardown-pro/.codebuddy-plugin/plugin.json',encoding='utf-8'))['avatar'])"
```

两者必须一致，且文件必须是 512×512 PNG、小于 500KB。

**第 2 步 看安装结果**

```
<配置目录>/plugins/marketplaces/my-experts/plugins/czl-rival-teardown-pro/avatars/expert.png
```

不存在 → 是导入时文件丢失，重新打包再导入。

**第 3 步 看渲染快照**

```
<配置目录>/assistant-display/<session-id>.json
```

找 `avatarUrl` 字段：

- `local-file://local/...` → 路径解析成功，问题在渲染端（版本/协议）
- `https://acc-...myqcloud.com/...` → 走了路径 2 兜底，说明主进程没解析到本地文件
- 空字符串 → 命中了路径 1 的三个丢弃条件之一

**第 4 步 看日志**

```
<配置目录>/logs/main.log
```

搜 `avatar file is too large`、`resolveAvatarUrl`、`ExpertPluginService`。

---

## 四、修复方案

### 方案 A 重新导入完整包（首选）

用 `python3 scripts/package_expert.py <专家目录>` 重新打包。该脚本会把 `avatars/` 一并写入
zip，且保持 `<专家名>/...` 的目录层级。不要用会跳过点文件或二进制的压缩工具手工打包
（`.codebuddy-plugin` 是点目录，部分工具会漏掉）。

### 方案 B 用 data-URI 兼容版（针对环境/版本问题）

`plugin.json` 的 `avatar` 如果写成 `data:image/png;base64,...`，两条路径都会**原样返回**，
完全绕过文件系统解析，也就不存在路径、编码、版本兼容问题。

本包提供了构建命令：

```bash
python3 tools/package_qa.py --portable dist/czl-rival-teardown-pro-portable.zip
```

生成的兼容版 `plugin.json` 体积会增大约 1/3（头像 base64 内联），但导入后不会再退化成文字块。
适合「同一个包在 A 机器正常、B 机器变文字」这类环境问题。

注意：上架市场时建议仍用标准路径版（`avatar: avatars/expert.png`），data-URI 版本作为
分发/交付给客户的兼容包使用。

### 方案 C 手工替换头像

把任意 512×512 PNG 覆盖到 `avatars/expert.png`（文件名保持不变），重启 WorkBuddy 即可。
这是最快的临时验证手段：如果换图后仍然显示文字，说明问题不在图片本身，而在路径或渲染端。

---

## 五、本包已做的预防措施

| 措施 | 目的 |
|---|---|
| 头像路径 `avatars/expert.png`，纯 ASCII、全小写 | 避免大小写与编码问题 |
| 512×512 PNG，约 389KB | 远低于 5MB 上限，也低于 500KB 规范建议值 |
| `tools/package_qa.py` 内置 30 项检查，含头像规格与路径校验 | 发布前自动拦截 |
| 提供 `--portable` 构建开关 | 环境兼容兜底 |
| 打包使用官方 `package_expert.py` | 保证目录层级与文件完整性 |

---

## 六、仍待验证的事项

以下结论属于推断，未在本机复现，需要在目标环境实测确认：

1. 「换版本后 `local-file://` 解码失败」是否真实存在——需要在两个不同版本的 WorkBuddy 上
   用同一个包对照测试。
2. 市场审核是否接受 data-URI 形式的 `avatar` 字段——未提交审核，无法确认。
3. 云同步（experts.cloudSync）链路下头像的取值方式——代码中只看到本地与 CDN 两种来源，
   云同步场景未实测。
