# saveToObsidian

把每次任务的目标、处理过程、最终结果整理成 Markdown，并直接写入 Obsidian Vault。

## 功能

- 初始化 Vault 路径
- 创建任务
- 自动维护当前任务
- 追加处理过程
- 完成任务后自动生成 Markdown
- 自动更新 `任务总览.md`

## 快速开始

```powershell
python .\save_to_obsidian.py init --vault "C:\Users\张博艺\Documents\Obsidian Vault"
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

- 任务摘要
- 任务目标
- 处理过程
- 最终结果
- 元信息

并附带 YAML Frontmatter，方便在 Obsidian 中搜索、过滤和配合 Dataview 使用。
