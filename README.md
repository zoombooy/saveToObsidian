# saveToObsidian

把每次任务的目标、处理过程、最终结果整理成 Markdown，并直接写入 Obsidian Vault。

## 功能

- 初始化 Vault 路径
- 创建任务
- 自动维护当前任务
- 追加处理过程
- 完成任务后自动生成更适合 Obsidian 的专业 Markdown
- 自动更新 `任务总览.md`

## 快速开始

```powershell
python .\save_to_obsidian.py init --vault "C:\Users\user\Documents\Obsidian Vault"
python .\save_to_obsidian.py start --title "修复登录问题" --goal "定位并修复登录接口 500"
python .\save_to_obsidian.py log --content "先检查后端日志和用户鉴权逻辑"
python .\save_to_obsidian.py finish --result "已修复 token 过期判断，并完成验证"
```

或者使用 PowerShell 包装：

```powershell
.\obsidian_task.ps1 start --title "修复登录问题" --goal "定位并修复登录接口 500"
```

## 常用命令

```powershell
python .\save_to_obsidian.py current
python .\save_to_obsidian.py list
python .\save_to_obsidian.py use <任务ID>
python .\save_to_obsidian.py clear-current
python .\save_to_obsidian.py sync
python .\save_to_obsidian.py sync <任务ID>
```

## 生成内容

每个任务文档会包含：

- YAML Frontmatter
- 快速导航
- 状态摘要 Callout
- 任务概览统计表
- 执行时间线
- 按类型区分的过程记录
- 最终结果 Callout
- 元信息与总览入口

并附带 YAML Frontmatter，方便在 Obsidian 中搜索、过滤和配合 Dataview 使用。

`任务总览.md` 也会生成更像知识库首页的结构，包括：

- 统计概览
- 最近更新
- 按状态查看
- 本地待同步任务
- 使用建议

此外，总览页会优先使用本地任务记录，并补充扫描 Vault 中已经存在的任务笔记来恢复索引，降低本地缓存丢失后总览缺项的风险。
