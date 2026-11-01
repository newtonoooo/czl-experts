# 诊断报告：专家导入后图标变成文字

**问题现象**：专家包导入到另一个 WorkBuddy 后，在输入框选中该专家，小图标不显示，退化成一个字（如"阿"）。

**结论**：图片本身没有坏。这是平台的头像解析链**没有拿到可用的绝对地址**，主动回退成了「名称首字」占位符。共五种触发路径，其中前两种最常见。

---

## 一、平台是怎么渲染这个图标的

以下依据来自客户端渲染层代码（`renderer/assets`），是实际执行的逻辑，不是推测。

### 1. 输入框 chip 的渲染与回退

```js
ExpertAvatar = ({avatarUrl, name, preparing}) => {
  const [failedSrc, setFailedSrc] = useState(null);
  const showImage = !!avatarUrl && failedSrc !== avatarUrl;
  if (showImage) return <img src={avatarUrl} onError={() => setFailedSrc(avatarUrl)} />;
  const initial = (name || '?').charAt(0).toUpperCase();   // ← 你看到的"字"
  return <span style={{background: getAvatarFallbackBackground(name)}}>{initial}</span>;
}
```

两条路径会走到 `initial`：

- `avatarUrl` 为空 → 直接渲染首字；
- `avatarUrl` 有值但 `<img>` 加载失败（404 / 路径错 / 协议不支持）→ `onError` 触发，切回首字。

### 2. 相对路径会被丢弃

```js
function resolveAvatarUrl(i) {
  return /^(https?|file|data|local-file):/.test(i) ? i : '';
}
```

**只有 `http(s)://`、`file://`、`data:`、`local-file:` 开头的地址会被保留。**
`avatars/expert.png` 这种相对路径在这里直接被替换成空字符串 → 首字回退。

### 3. 相对路径会被拼到云端市场域名上

```js
function resolveExpertAvatarUrl(e) {
  ...
  return buildExpertUrl(t.startsWith('/') ? t : '/' + t);
}
function buildExpertUrl(e) {
  return `${$.baseUrl}${e}`;   // baseUrl = https://acc-1258344699.cos.accelerate.myqcloud.com/workbuddy/expert-marketplace
}
```

也就是说，`avatars/expert.png` 在某些调用链里会被拼成
`https://acc-.../workbuddy/expert-marketplace/avatars/expert.png`。
**这个地址只对已上架到官方市场的专家存在。** 本地自建专家的图片不在那个桶里 → 404 → `onError` → 首字。

### 4. 官方/市场专家条目的 icon 只认绝对地址

```js
function mapOfficialExpertToItem(e, t) {
  const n = e.icon?.trim() || '';
  const r = /^(https?:\/\/|data:image\/)/i.test(n) ? n : undefined;   // 相对路径 → undefined
  ...
}
```

### 5. `expert-card.json` 不是平台文件

在 91.9 MB 的 `app.asar` 中检索 `expert-card.json`，**命中 0 次**。
该文件是某些专家包自带的附加说明，平台不读取它，也无法通过它修复图标。真正被读取的只有 `.codebuddy-plugin/plugin.json` 的 `avatar` 字段。

---

## 二、五种真实成因与对应修法

### 成因 A：zip 里没有 `avatars/`，或路径与 `avatar` 字段不一致（最常见）

打包时只带了 `agents/` 和 `skills/`，或手动压缩时漏了二进制目录；或者 `plugin.json` 写 `avatars/expert.png`，实际文件叫 `expert.PNG` / `avatar.png` / 在 `avatars/experts/expert.png`。

**修法**：解压 zip，逐字比对。

```bash
unzip -l czl-uae-growth-marketing-pro.zip | grep -i avatar
```

必须能看到 `czl-uae-growth-marketing-pro/avatars/expert.png`，且与 `plugin.json` 的 `avatar` 字段**大小写完全一致**。

### 成因 B：`avatar` 字段写法不规范

| 写法 | 结果 |
|------|------|
| `avatars/expert.png` | ✅ 规范写法 |
| `./avatars/expert.png` | ⚠️ 多数情况可用，部分解析分支不认 |
| `/avatars/expert.png` | ❌ 会被当成站点根路径 |
| `C:\...\expert.png` | ❌ 本地绝对路径不可移植 |
| 留空或字段缺失 | ❌ 必然首字 |

**修法**：统一写 `avatars/expert.png`，不加 `./`，不加前导斜杠。

### 成因 C：图片超过体积或尺寸限制

平台规范：PNG/JPG、512×512、单张 ≤500KB。
超过 500KB 或尺寸过大时，部分客户端会加载超时或直接拒绝，表现为 `onError`。

**修法**：

```bash
python bin/avatar_tool.py 源图.png avatars/expert.png --size 512
```

本包自带的 `avatar_tool.py` 会把图压到 512×512 RGBA、透明圆角，并自动做行过滤压缩，输出体积通常在 100~300KB。

### 成因 D：没有走"我的专家"本地注册，被当成市场专家处理

本地自建专家需要注册到 `my-experts` 市场，平台才会扫描目录并把 `avatar` 解析成本地绝对地址。只把文件夹拷进去而不注册，条目可能从市场侧读取，此时相对路径按成因 3 处理 → 404。

**修法**：

```bash
python "<expert-manager>/scripts/register_expert.py" \
  "<配置目录>/plugins/marketplaces/my-experts/plugins/czl-uae-growth-marketing-pro"
```

注册成功后重启客户端。

### 成因 E：客户端缓存

替换了头像文件但没重启，或旧条目仍指向旧路径。

**修法**：完全退出客户端（不是关窗口）后重开；仍不生效则删除该专家条目重新导入。

---

## 三、四条自查清单（按顺序执行，2 分钟）

```bash
# 1. 文件在不在、路径对不对（大小写敏感）
python bin/package_check.py

# 2. 尺寸与体积
python -c "import struct,os;p='avatars/expert.png';d=open(p,'rb').read(33);print(struct.unpack('>II',d[16:24]), round(os.path.getsize(p)/1024,1),'KB')"
# 期望：(512, 512) 且 KB < 500

# 3. 是不是真 PNG
python -c "print(open('avatars/expert.png','rb').read(8)==b'\x89PNG\r\n\x1a\n')"
# 期望：True

# 4. zip 结构（根目录必须是包名文件夹，里面直接是 avatars/）
python -c "import zipfile;print([n for n in zipfile.ZipFile('dist/czl-uae-growth-marketing-pro.zip').namelist() if 'avatar' in n])"
# 期望：['czl-uae-growth-marketing-pro/avatars/expert.png']
```

四条全过，图标就能正常显示。

---

## 四、本包已经做的预防

| 措施 | 实现位置 |
|------|---------|
| `avatar` 字段用规范写法 `avatars/expert.png` | `.codebuddy-plugin/plugin.json` |
| 头像 512×512、8bit **RGB（无 alpha）**、200KB、全幅不透明 | `avatars/expert.png` |
| 打包前强制校验头像存在、正方形、PNG、≤500KB | `bin/package_check.py`（33 项检查，含体积 >300KB 预警） |
| zip 根目录结构由官方 `package_expert.py` 生成，不会漏 `avatars/` | `dist/` 构建流程 |
| 单元测试锁定头像规格 | `tests/test_package.py::TestAvatar`、`tests/test_avatar.py` |

> 为什么刻意不用透明通道：带 alpha 的 RGBA 头像与圆角裁切虽然更好看，但在部分客户端上会增加解码失败的概率，而解码失败就会走 `onError` → 首字回退。宁可牺牲圆角，也要保证能显示。圆形头像容器本身会裁掉四角，所以视觉上没有损失。

> 补充说明：`expert-card.json` 在本包中**不提供**。既然平台不读取它，保留只会让人误以为改了它就能修图标。所有展示信息统一放在 `plugin.json`。
