from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any


APP_DIR_NAME = ".obsidian_tasker"
TASKS_DIR_NAME = "tasks"
CONFIG_FILE_NAME = "config.json"
CURRENT_TASK_FILE_NAME = "current_task.txt"
DEFAULT_NOTES_FOLDER = "工作记录/AI任务"
DEFAULT_INDEX_NAME = "任务总览.md"
DEFAULT_TAGS = ["task-log", "codex"]
KIND_LABELS = {
    "step": "处理",
    "decision": "决策",
    "issue": "问题",
    "note": "备注",
}
STATUS_LABELS = {
    "in_progress": "进行中",
    "completed": "已完成",
    "blocked": "已阻塞",
    "cancelled": "已取消",
}
STATUS_CALLOUTS = {
    "in_progress": "info",
    "completed": "success",
    "blocked": "warning",
    "cancelled": "failure",
}
KIND_CALLOUTS = {
    "step": "tip",
    "decision": "example",
    "issue": "warning",
    "note": "note",
}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def display_time(value: str | None) -> str:
    if not value:
        return "-"
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return value


def ensure_state_dirs(base_dir: Path) -> None:
    (base_dir / APP_DIR_NAME / TASKS_DIR_NAME).mkdir(parents=True, exist_ok=True)


def config_path(base_dir: Path) -> Path:
    return base_dir / APP_DIR_NAME / CONFIG_FILE_NAME


def tasks_dir(base_dir: Path) -> Path:
    return base_dir / APP_DIR_NAME / TASKS_DIR_NAME


def current_task_path(base_dir: Path) -> Path:
    return base_dir / APP_DIR_NAME / CURRENT_TASK_FILE_NAME


def load_config(base_dir: Path) -> dict[str, Any]:
    path = config_path(base_dir)
    if not path.exists():
        raise SystemExit("尚未初始化，请先运行: python save_to_obsidian.py init")
    return json.loads(path.read_text(encoding="utf-8"))


def save_config(base_dir: Path, data: dict[str, Any]) -> None:
    ensure_state_dirs(base_dir)
    config_path(base_dir).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def task_file(base_dir: Path, task_id: str) -> Path:
    return tasks_dir(base_dir) / f"{task_id}.json"


def load_task(base_dir: Path, task_id: str) -> dict[str, Any]:
    path = task_file(base_dir, task_id)
    if not path.exists():
        raise SystemExit(f"未找到任务: {task_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_task(base_dir: Path, task: dict[str, Any]) -> None:
    ensure_state_dirs(base_dir)
    task["updated_at"] = now_iso()
    task_file(base_dir, task["id"]).write_text(
        json.dumps(task, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_current_task_id(base_dir: Path) -> str | None:
    path = current_task_path(base_dir)
    if not path.exists():
        return None
    value = path.read_text(encoding="utf-8").strip()
    return value or None


def set_current_task_id(base_dir: Path, task_id: str) -> None:
    ensure_state_dirs(base_dir)
    current_task_path(base_dir).write_text(task_id, encoding="utf-8")


def clear_current_task(base_dir: Path) -> None:
    current_task_path(base_dir).unlink(missing_ok=True)


def resolve_task_id(base_dir: Path, task_id: str | None) -> str:
    if task_id:
        return task_id
    current = get_current_task_id(base_dir)
    if current:
        return current
    raise SystemExit("未指定任务 ID，且当前没有活动任务。请先运行 start 或 use。")


def list_tasks(base_dir: Path) -> list[dict[str, Any]]:
    folder = tasks_dir(base_dir)
    if not folder.exists():
        return []
    items: list[dict[str, Any]] = []
    for path in folder.glob("*.json"):
        try:
            items.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return sorted(items, key=lambda item: item.get("created_at", ""), reverse=True)


def normalize_tags(values: list[str] | None) -> list[str]:
    if not values:
        return []
    tags: list[str] = []
    for value in values:
        for item in value.split(","):
            tag = item.strip()
            if tag and tag not in tags:
                tags.append(tag)
    return tags


def slugify(text: str) -> str:
    value = unicodedata.normalize("NFKC", text).strip().lower()
    value = re.sub(r"[\\/:*?\"<>|]", "-", value)
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-.")
    return (value or "task")[:60]


def prompt_single_line(label: str, default: str | None = None, required: bool = True) -> str:
    while True:
        suffix = f" [{default}]" if default else ""
        try:
            value = input(f"{label}{suffix}: ").strip()
        except EOFError as exc:
            raise SystemExit("输入已中断。") from exc
        if value:
            return value
        if default is not None:
            return default
        if not required:
            return ""
        print(f"{label}不能为空，请重新输入。")


def prompt_multiline(label: str, default: str | None = None, required: bool = True) -> str:
    while True:
        print(f"{label}（多行输入，单独输入 .end 结束）:")
        lines: list[str] = []
        while True:
            try:
                line = input()
            except EOFError as exc:
                raise SystemExit("输入已中断。") from exc
            if line.strip() == ".end":
                break
            lines.append(line)
        value = "\n".join(lines).strip()
        if value:
            return value
        if default is not None:
            return default
        if not required:
            return ""
        print(f"{label}不能为空，请重新输入。")


def yaml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def first_line(text: str, fallback: str = "") -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return fallback


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def duration_text(start: str | None, end: str | None) -> str:
    start_dt = parse_time(start)
    end_dt = parse_time(end)
    if not start_dt or not end_dt:
        return "-"

    total_seconds = max(int((end_dt - start_dt).total_seconds()), 0)
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts: list[str] = []
    if days:
        parts.append(f"{days}天")
    if hours:
        parts.append(f"{hours}小时")
    if minutes:
        parts.append(f"{minutes}分钟")
    if not parts:
        parts.append(f"{seconds}秒")
    return "".join(parts[:2])


def note_name_from_relative_path(relative_path: str | None, fallback: str = "任务总览") -> str:
    if not relative_path:
        return fallback
    return Path(relative_path).stem


def preview_text(text: str, limit: int = 72) -> str:
    value = first_line(text, "").replace("|", "\\|")
    if len(value) <= limit:
        return value or "-"
    return value[: limit - 1].rstrip() + "…"


def log_count(task: dict[str, Any], kind: str | None = None) -> int:
    logs = task.get("logs", [])
    if kind is None:
        return len(logs)
    return sum(1 for entry in logs if entry.get("kind") == kind)


def callout_lines(callout_type: str, body_lines: list[str]) -> list[str]:
    lines = [f"> [!{callout_type}]"]
    if not body_lines:
        return lines
    for line in body_lines:
        lines.append(f"> {line}" if line else ">")
    return lines


def quoted_list(values: list[str]) -> list[str]:
    return [f"  - {yaml_quote(value)}" for value in values]


def note_tags(config: dict[str, Any], task: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    for tag in config.get("default_tags", []) + ["ai-task", task.get("status", "unknown")] + task.get("tags", []):
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def note_root(config: dict[str, Any]) -> Path:
    return Path(config["vault_path"]) / Path(config["notes_folder"])


def note_path(config: dict[str, Any], task: dict[str, Any]) -> Path:
    return note_root(config) / f"{task['id']}.md"


def note_relative_path(config: dict[str, Any], task: dict[str, Any]) -> str:
    return str(Path(config["notes_folder"]) / f"{task['id']}.md").replace("\\", "/")


def clean_section_text(section: str) -> str:
    lines: list[str] = []
    for raw_line in section.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped.startswith("> [!"):
            continue
        if stripped.startswith("> "):
            stripped = stripped[2:].strip()
        if stripped.startswith("|"):
            continue
        if stripped.startswith("### "):
            continue
        if stripped in {"---", "--"}:
            continue
        if stripped.startswith("**状态**") or stripped.startswith("**结论**"):
            continue
        lines.append(stripped)
    return first_line("\n".join(lines), "")


def extract_section(markdown: str, heading: str) -> str:
    pattern = re.compile(rf"^## {re.escape(heading)}\s*$([\s\S]*?)(?=^## |\Z)", re.MULTILINE)
    match = pattern.search(markdown)
    if not match:
        return ""
    return match.group(1).strip()


def parse_note_frontmatter(markdown: str) -> dict[str, str]:
    if not markdown.startswith("---"):
        return {}
    match = re.match(r"^---\n([\s\S]*?)\n---\n", markdown)
    if not match:
        return {}

    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line or line.startswith(" ") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"')
    return metadata


def note_entry_from_markdown(config: dict[str, Any], note_path_value: Path) -> dict[str, Any] | None:
    try:
        markdown = note_path_value.read_text(encoding="utf-8")
    except OSError:
        return None

    frontmatter = parse_note_frontmatter(markdown)
    title = frontmatter.get("title") or note_path_value.stem
    task_id = frontmatter.get("task_id") or frontmatter.get("id") or note_path_value.stem
    summary = frontmatter.get("summary", "").strip()
    if not summary:
        summary = clean_section_text(extract_section(markdown, "任务摘要"))
    if not summary:
        summary = clean_section_text(extract_section(markdown, "最终结果"))

    return {
        "id": task_id,
        "title": title,
        "status": frontmatter.get("status", "completed"),
        "created_at": frontmatter.get("created", ""),
        "updated_at": frontmatter.get("updated", frontmatter.get("created", "")),
        "completed_at": frontmatter.get("completed", ""),
        "summary": summary,
        "result": summary,
        "note_relative_path": str(Path(config["notes_folder"]) / note_path_value.name).replace("\\", "/"),
    }


def synced_entries(config: dict[str, Any], tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries_by_path: dict[str, dict[str, Any]] = {}
    for task in tasks:
        if task.get("note_relative_path"):
            entries_by_path[task["note_relative_path"]] = task

    root = note_root(config)
    if root.exists():
        for note_file in root.glob("*.md"):
            if note_file.name == config["index_name"]:
                continue
            relative = str(Path(config["notes_folder"]) / note_file.name).replace("\\", "/")
            if relative in entries_by_path:
                continue
            entry = note_entry_from_markdown(config, note_file)
            if entry:
                entries_by_path[relative] = entry

    def sort_key(item: dict[str, Any]) -> str:
        return item.get("updated_at") or item.get("created_at") or ""

    return sorted(entries_by_path.values(), key=sort_key, reverse=True)


def render_markdown(config: dict[str, Any], task: dict[str, Any], local_task_path: Path) -> str:
    tags = note_tags(config, task)
    status = task.get("status", "in_progress")
    status_label = STATUS_LABELS.get(status, status)
    status_callout = STATUS_CALLOUTS.get(status, "note")
    summary = task.get("summary") or first_line(task.get("result", ""), first_line(task.get("goal", ""), ""))
    summary_text = summary or "暂无摘要。"
    logs = task.get("logs", [])
    index_link_name = Path(config["index_name"]).stem

    lines = [
        "---",
        "aliases:",
        *quoted_list([task["title"], task["id"]]),
        "tags:",
        *quoted_list(tags),
        f"id: {yaml_quote(task['id'])}",
        f"title: {yaml_quote(task['title'])}",
        f"task_id: {yaml_quote(task['id'])}",
        f"status: {yaml_quote(status)}",
        f"status_label: {yaml_quote(status_label)}",
        f"summary: {yaml_quote(summary_text)}",
        f"created: {yaml_quote(display_time(task.get('created_at')))}",
        f"updated: {yaml_quote(display_time(task.get('updated_at')))}",
        f"completed: {yaml_quote(display_time(task.get('completed_at')))}",
        f"duration: {yaml_quote(duration_text(task.get('created_at'), task.get('completed_at') or task.get('updated_at')))}",
        f"source: {yaml_quote('codex-cli')}",
        "---",
        "",
        f"# {task['title']}",
        "",
    ]

    lines.extend(
        callout_lines(
            "abstract",
            [
                "本文记录：任务目标、执行过程、最终结果与关键元信息。",
            ],
        )
    )
    lines.extend(
        [
            "",
            "## 快速导航",
            "",
            "- [[#任务概览]]",
            "- [[#目标与范围]]",
            "- [[#执行时间线]]",
            "- [[#过程记录]]",
            "- [[#最终结果]]",
            "- [[#元信息]]",
            "",
            "## 任务概览",
            "",
        ]
    )

    lines.extend(
        callout_lines(
            status_callout,
            [
                f"**状态**：{status_label}",
                "",
                summary_text,
            ],
        )
    )
    lines.extend(
        [
            "",
            "| 字段 | 内容 |",
            "| --- | --- |",
            f"| 任务 ID | `{task['id']}` |",
            f"| 记录来源 | `codex-cli` |",
            f"| 创建时间 | {display_time(task.get('created_at'))} |",
            f"| 最近更新 | {display_time(task.get('updated_at'))} |",
            f"| 完成时间 | {display_time(task.get('completed_at'))} |",
            f"| 总耗时 | `{duration_text(task.get('created_at'), task.get('completed_at') or task.get('updated_at'))}` |",
            f"| 过程记录数 | `{log_count(task)}` 条 |",
            f"| 决策记录数 | `{log_count(task, 'decision')}` 条 |",
            f"| 问题记录数 | `{log_count(task, 'issue')}` 条 |",
            "",
            "## 目标与范围",
            "",
            task.get("goal", "").strip() or "未填写。",
            "",
            "## 执行时间线",
            "",
        ]
    )

    if logs:
        lines.extend(["| 时间 | 类型 | 内容摘要 |", "| --- | --- | --- |"])
        for entry in logs:
            entry_kind = entry.get("kind", "note")
            lines.append(
                f"| {display_time(entry.get('time'))} | {KIND_LABELS.get(entry_kind, '记录')} | {preview_text(entry.get('content', ''))} |"
            )
    else:
        lines.append("暂无过程记录。")

    lines.extend(["", "## 过程记录", ""])
    if logs:
        for index, entry in enumerate(logs, start=1):
            entry_kind = entry.get("kind", "note")
            label = KIND_LABELS.get(entry_kind, "记录")
            lines.append(f"### {index:02d}. {display_time(entry.get('time'))} · {label}")
            lines.append("")
            lines.extend(
                callout_lines(
                    KIND_CALLOUTS.get(entry_kind, "note"),
                    (entry.get("content", "").strip() or "未填写。").splitlines(),
                )
            )
            lines.append("")
    else:
        lines.append("暂无过程记录。")
        lines.append("")

    lines.extend(["## 最终结果", ""])
    lines.extend(
        callout_lines(
            status_callout,
            [
                f"**结论**：{status_label}",
                "",
                task.get("result", "").strip() or "未填写。",
            ],
        )
    )
    lines.extend(
        [
            "",
            "## 元信息",
            "",
            "| 字段 | 值 |",
            "| --- | --- |",
            f"| 总览入口 | [[{index_link_name}]] |",
            f"| Vault 目录 | `{config['notes_folder']}` |",
            f"| 本地记录 | `{local_task_path}` |",
            f"| 标签 | {' '.join(f'`{tag}`' for tag in tags)} |",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def build_index_markdown(config: dict[str, Any], tasks: list[dict[str, Any]]) -> str:
    synced_tasks = synced_entries(config, tasks)
    in_progress_tasks = [item for item in tasks if item.get("status") == "in_progress"]
    completed_tasks = [item for item in synced_tasks if item.get("status") == "completed"]
    blocked_tasks = [item for item in synced_tasks if item.get("status") == "blocked"]
    cancelled_tasks = [item for item in synced_tasks if item.get("status") == "cancelled"]

    lines = [
        "---",
        "aliases:",
        *quoted_list(["任务总览", "AI任务总览"]),
        "tags:",
        *quoted_list(["task-log", "codex", "ai-dashboard"]),
        "---",
        "",
        "# 任务总览",
        "",
    ]
    lines.extend(
        callout_lines(
            "abstract",
            [
                "这里汇总通过 Codex CLI 同步到 Obsidian 的任务记录，可作为日常工作记录入口。",
            ],
        )
    )
    lines.extend(
        [
            "",
            "## 快速导航",
            "",
            "- [[#统计概览]]",
            "- [[#最近更新]]",
            "- [[#按状态查看]]",
            "- [[#本地待同步]]",
            "- [[#使用建议]]",
            "",
            "## 统计概览",
            "",
            "| 指标 | 数量 |",
            "| --- | --- |",
            f"| 本地任务总数 | `{len(tasks)}` |",
            f"| 已同步笔记 | `{len(synced_tasks)}` |",
            f"| 已完成 | `{len(completed_tasks)}` |",
            f"| 已阻塞 | `{len(blocked_tasks)}` |",
            f"| 已取消 | `{len(cancelled_tasks)}` |",
            f"| 本地进行中 | `{len(in_progress_tasks)}` |",
            f"| 最后更新 | `{display_time(now_iso())}` |",
            "",
            "## 最近更新",
            "",
        ]
    )
    if not synced_tasks:
        lines.append("暂无已同步任务。")
    else:
        lines.extend(["| 时间 | 标题 | 状态 | 摘要 |", "| --- | --- | --- | --- |"])
        for task in synced_tasks[:12]:
            title = task.get("title", "").replace("|", "\\|")
            summary = preview_text(task.get("summary") or task.get("result", ""), 96)
            note_name = note_name_from_relative_path(task.get("note_relative_path")).replace("|", "-")
            status_label = STATUS_LABELS.get(task.get("status", "-"), task.get("status", "-"))
            lines.append(
                f"| {display_time(task.get('updated_at'))} | [[{note_name}|{title}]] | {status_label} | {summary} |"
            )

    lines.extend(["", "## 按状态查看", ""])
    status_sections = [
        ("已完成", completed_tasks),
        ("已阻塞", blocked_tasks),
        ("已取消", cancelled_tasks),
    ]
    for heading, items in status_sections:
        lines.extend([f"### {heading}", ""])
        if items:
            for task in items:
                note_name = note_name_from_relative_path(task.get("note_relative_path")).replace("|", "-")
                lines.append(
                    f"- [[{note_name}|{task.get('title', '')}]] · {display_time(task.get('updated_at'))} · {preview_text(task.get('summary') or task.get('result', ''), 72)}"
                )
        else:
            lines.append("- 暂无")
        lines.append("")

    lines.extend(["## 本地待同步", ""])
    if in_progress_tasks:
        lines.extend(
            callout_lines(
                "info",
                [
                    "以下任务仍在本地进行中，尚未执行 `finish`，因此还没有同步为 Obsidian 笔记。",
                ],
            )
        )
        lines.append("")
        for task in in_progress_tasks:
            lines.append(
                f"- `{task['id']}` · {task.get('title', '')} · 创建于 {display_time(task.get('created_at'))}"
            )
    else:
        lines.append("当前没有待同步的本地任务。")

    lines.extend(
        [
            "",
            "## 使用建议",
            "",
        ]
    )
    lines.extend(
        callout_lines(
            "tip",
            [
                "推荐流程：`start` 创建任务，`log` 追加过程，`finish` 结束并同步到 Obsidian。",
                "如需切换任务，可先执行 `use <任务ID>`，再继续 `log` 或 `finish`。",
            ],
        )
    )
    return "\n".join(lines).strip() + "\n"


def sync_task_to_obsidian(base_dir: Path, config: dict[str, Any], task: dict[str, Any]) -> Path:
    root = note_root(config)
    root.mkdir(parents=True, exist_ok=True)

    local_path = task_file(base_dir, task["id"])
    task["updated_at"] = now_iso()
    task["synced_at"] = now_iso()
    task["note_relative_path"] = note_relative_path(config, task)

    final_note_path = note_path(config, task)
    final_note_path.write_text(
        render_markdown(config, task, local_path),
        encoding="utf-8",
    )

    save_task(base_dir, task)

    index_path = root / config["index_name"]
    index_path.write_text(build_index_markdown(config, list_tasks(base_dir)), encoding="utf-8")
    return final_note_path


def command_init(args: argparse.Namespace, base_dir: Path) -> None:
    ensure_state_dirs(base_dir)
    vault = args.vault or prompt_single_line("请输入 Obsidian Vault 路径")
    config = {
        "workspace": str(base_dir),
        "vault_path": str(Path(vault).expanduser().resolve()),
        "notes_folder": args.notes_folder or DEFAULT_NOTES_FOLDER,
        "index_name": args.index_name or DEFAULT_INDEX_NAME,
        "default_tags": DEFAULT_TAGS,
    }
    save_config(base_dir, config)
    print("初始化完成。")
    print(f"Vault 路径: {config['vault_path']}")
    print(f"同步目录: {Path(config['vault_path']) / config['notes_folder']}")


def command_start(args: argparse.Namespace, base_dir: Path) -> None:
    ensure_state_dirs(base_dir)
    title = args.title or prompt_single_line("任务标题")
    goal = args.goal or prompt_multiline("任务目标")
    task_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{slugify(title)}"
    task = {
        "id": task_id,
        "title": title,
        "goal": goal,
        "summary": args.summary or "",
        "result": "",
        "status": "in_progress",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "completed_at": None,
        "synced_at": None,
        "note_relative_path": None,
        "tags": normalize_tags(args.tags),
        "logs": [],
    }
    save_task(base_dir, task)
    set_current_task_id(base_dir, task_id)
    print(f"任务已创建: {task_id}")
    print(f"当前任务已切换为: {task_id}")
    print(f"本地文件: {task_file(base_dir, task_id)}")


def command_log(args: argparse.Namespace, base_dir: Path) -> None:
    task = load_task(base_dir, resolve_task_id(base_dir, args.task_id))
    task.setdefault("logs", []).append(
        {
            "time": now_iso(),
            "kind": args.kind,
            "content": args.content or prompt_multiline("过程记录"),
        }
    )
    save_task(base_dir, task)
    print(f"已追加记录到任务: {task['id']}")


def command_finish(args: argparse.Namespace, base_dir: Path) -> None:
    config = load_config(base_dir)
    task = load_task(base_dir, resolve_task_id(base_dir, args.task_id))
    result = args.result or prompt_multiline("最终结果")
    task["result"] = result
    task["summary"] = args.summary if args.summary is not None else first_line(result, first_line(task.get("goal", ""), ""))
    task["status"] = args.status
    task["completed_at"] = now_iso()

    final_note_path = sync_task_to_obsidian(base_dir, config, task)
    if get_current_task_id(base_dir) == task["id"]:
        clear_current_task(base_dir)
    print("任务已完成并同步到 Obsidian:")
    print(final_note_path)


def command_sync(args: argparse.Namespace, base_dir: Path) -> None:
    config = load_config(base_dir)
    if args.task_id:
        task = load_task(base_dir, args.task_id)
        note = sync_task_to_obsidian(base_dir, config, task)
        print(f"已同步任务: {task['id']}")
        print(note)
        return

    count = 0
    for task in list_tasks(base_dir):
        if task.get("status") == "in_progress":
            continue
        sync_task_to_obsidian(base_dir, config, task)
        count += 1
    print(f"已重新同步 {count} 个任务。")


def command_list(_: argparse.Namespace, base_dir: Path) -> None:
    tasks = list_tasks(base_dir)
    current_id = get_current_task_id(base_dir)
    if not tasks:
        print("暂无任务记录。")
        return
    for task in tasks:
        current_flag = " current" if task["id"] == current_id else ""
        synced = "yes" if task.get("note_relative_path") else "no"
        print(
            f"{task['id']} | {task.get('status', '-')} | synced={synced} | "
            f"{display_time(task.get('created_at'))} | {task.get('title', '')}{current_flag}"
        )


def command_current(_: argparse.Namespace, base_dir: Path) -> None:
    task_id = get_current_task_id(base_dir)
    if not task_id:
        print("当前没有活动任务。")
        return
    try:
        task = load_task(base_dir, task_id)
    except SystemExit:
        clear_current_task(base_dir)
        print("当前任务指向的记录不存在，已自动清除。")
        return
    print(f"当前任务: {task['id']}")
    print(f"标题: {task.get('title', '')}")
    print(f"状态: {task.get('status', '-')}")
    print(f"创建时间: {display_time(task.get('created_at'))}")


def command_use(args: argparse.Namespace, base_dir: Path) -> None:
    task = load_task(base_dir, args.task_id)
    set_current_task_id(base_dir, task["id"])
    print(f"当前任务已切换为: {task['id']}")
    print(f"标题: {task.get('title', '')}")


def command_clear_current(_: argparse.Namespace, base_dir: Path) -> None:
    clear_current_task(base_dir)
    print("当前任务已清除。")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="记录任务并同步到 Obsidian Vault。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="初始化 Vault 配置")
    init_parser.add_argument("--vault", help="Obsidian Vault 目录")
    init_parser.add_argument("--notes-folder", default=DEFAULT_NOTES_FOLDER, help="Vault 内的文档目录")
    init_parser.add_argument("--index-name", default=DEFAULT_INDEX_NAME, help="任务总览文件名")

    start_parser = subparsers.add_parser("start", help="创建一条新任务")
    start_parser.add_argument("--title", help="任务标题")
    start_parser.add_argument("--goal", help="任务目标")
    start_parser.add_argument("--summary", help="任务摘要")
    start_parser.add_argument("--tags", nargs="*", help="标签，支持空格或逗号分隔")

    log_parser = subparsers.add_parser("log", help="记录任务处理过程")
    log_parser.add_argument("task_id", nargs="?", help="任务 ID；不传则使用当前任务")
    log_parser.add_argument("--kind", choices=sorted(KIND_LABELS.keys()), default="step", help="记录类型")
    log_parser.add_argument("--content", help="记录内容")

    finish_parser = subparsers.add_parser("finish", help="结束任务并同步到 Obsidian")
    finish_parser.add_argument("task_id", nargs="?", help="任务 ID；不传则使用当前任务")
    finish_parser.add_argument("--result", help="最终结果")
    finish_parser.add_argument("--summary", help="文档摘要")
    finish_parser.add_argument(
        "--status",
        choices=["completed", "blocked", "cancelled"],
        default="completed",
        help="最终状态",
    )

    sync_parser = subparsers.add_parser("sync", help="重新同步已完成任务")
    sync_parser.add_argument("task_id", nargs="?", help="可选：仅同步指定任务")

    subparsers.add_parser("list", help="查看本地任务列表")
    subparsers.add_parser("current", help="查看当前任务")

    use_parser = subparsers.add_parser("use", help="切换当前任务")
    use_parser.add_argument("task_id", help="任务 ID")

    subparsers.add_parser("clear-current", help="清除当前任务")
    return parser


def main() -> int:
    base_dir = Path(__file__).resolve().parent
    args = build_parser().parse_args()
    commands = {
        "init": command_init,
        "start": command_start,
        "log": command_log,
        "finish": command_finish,
        "sync": command_sync,
        "list": command_list,
        "current": command_current,
        "use": command_use,
        "clear-current": command_clear_current,
    }
    commands[args.command](args, base_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
