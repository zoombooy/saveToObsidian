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


def note_root(config: dict[str, Any]) -> Path:
    return Path(config["vault_path"]) / Path(config["notes_folder"])


def note_path(config: dict[str, Any], task: dict[str, Any]) -> Path:
    return note_root(config) / f"{task['id']}.md"


def note_relative_path(config: dict[str, Any], task: dict[str, Any]) -> str:
    return str(Path(config["notes_folder"]) / f"{task['id']}.md").replace("\\", "/")


def render_markdown(config: dict[str, Any], task: dict[str, Any], local_task_path: Path) -> str:
    tags: list[str] = []
    for tag in config.get("default_tags", []) + task.get("tags", []) + [task.get("status", "unknown")]:
        if tag and tag not in tags:
            tags.append(tag)

    lines = [
        "---",
        f"id: {yaml_quote(task['id'])}",
        f"title: {yaml_quote(task['title'])}",
        f"status: {yaml_quote(task.get('status', 'in_progress'))}",
        f"created: {yaml_quote(display_time(task.get('created_at')))}",
        f"updated: {yaml_quote(display_time(task.get('updated_at')))}",
        f"completed: {yaml_quote(display_time(task.get('completed_at')))}",
        "tags:",
    ]
    for tag in tags:
        lines.append(f"  - {tag}")

    lines.extend(["---", "", f"# {task['title']}", ""])

    summary = task.get("summary") or first_line(task.get("result", ""), first_line(task.get("goal", ""), ""))
    if summary:
        lines.extend(["## 任务摘要", "", summary, ""])

    lines.extend(["## 任务目标", "", task.get("goal", "").strip() or "未填写。", ""])

    lines.extend(["## 处理过程", ""])
    logs = task.get("logs", [])
    if logs:
        for entry in logs:
            label = KIND_LABELS.get(entry.get("kind", "note"), "记录")
            lines.extend(
                [
                    f"### {display_time(entry.get('time'))} · {label}",
                    "",
                    entry.get("content", "").strip() or "未填写。",
                    "",
                ]
            )
    else:
        lines.extend(["暂无过程记录。", ""])

    lines.extend(["## 最终结果", "", task.get("result", "").strip() or "未填写。", ""])
    lines.extend(
        [
            "## 元信息",
            "",
            f"- 任务 ID：`{task['id']}`",
            f"- 创建时间：{display_time(task.get('created_at'))}",
            f"- 完成时间：{display_time(task.get('completed_at'))}",
            f"- 本地记录：`{local_task_path}`",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def build_index_markdown(tasks: list[dict[str, Any]]) -> str:
    lines = ["# 任务总览", "", f"最后更新：{display_time(now_iso())}", ""]
    synced = [item for item in tasks if item.get("note_relative_path")]
    if not synced:
        lines.append("暂无已同步任务。")
        return "\n".join(lines).strip() + "\n"

    lines.extend(["| 时间 | 标题 | 状态 | 摘要 |", "| --- | --- | --- | --- |"])
    for task in synced:
        title = task.get("title", "").replace("|", "\\|")
        summary = (task.get("summary") or first_line(task.get("result", ""), "")).replace("|", "\\|")
        note_name = Path(task["note_relative_path"]).stem.replace("|", "-")
        lines.append(
            f"| {display_time(task.get('created_at'))} | [[{note_name}|{title}]] | {task.get('status', '-')} | {summary or '-'} |"
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
    index_path.write_text(build_index_markdown(list_tasks(base_dir)), encoding="utf-8")
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
