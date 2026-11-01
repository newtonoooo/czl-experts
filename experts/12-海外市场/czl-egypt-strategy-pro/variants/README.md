# variants · manifest 变体说明

本目录用于存放 `plugin.json` 的临时变体，解决"导入后头像显示成专家名首字"的问题。

## 为什么需要

头像在界面里是 `<img>` 渲染的，加载失败就会回退成名字首字。相对路径在某些导入通道下会被拼成不可达的地址，导致加载失败。`data:` URI 不参与路径拼接，因此是最稳的兜底。

## 怎么用

不要手改 `plugin.json`，用脚本：

```bash
# 切到内联头像（生成 variants/plugin.relative-avatar.json 作为回滚点）
python tools/apply_inline_avatar.py --apply

# 查看当前状态
python tools/apply_inline_avatar.py --status

# 上架官方市场前切回相对路径
python tools/apply_inline_avatar.py --revert
```

## 两种状态的区别

| 状态 | `avatar` 值 | 适用 |
|---|---|---|
| 相对路径（默认，发布用） | `avatars/expert.png` | 上架官方市场、走正规审核 |
| 内联（本地用） | `data:image/png;base64,...`（160px 约 30 KB，256px 约 72 KB） | 本地导入后图标不显示时 |

## 注意

- 本目录下的 `*.json` 是脚本运行时生成的备份，不是发布内容；打包前可删除。
- 内联状态下 `plugin.json` 会明显变大，这是正常现象，不影响加载。
