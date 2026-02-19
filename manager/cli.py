from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from manager.config import DEFAULT_MAX_WORKERS, ManagerPaths, build_paths, ensure_runtime_dirs
from manager.experience import reflect_rules_with_claude, update_claude_md_rules
from manager.git_ops import delete_remote_branch, list_prs
from manager.plan_farm import plan_all
from manager.runtime import now_iso
from manager.worker import run_workers


console = Console()


def _repo_from_arg(repo_path: str | None) -> Path:
    return Path(repo_path).resolve() if repo_path else Path.cwd().resolve()


def _load_tasks(paths: ManagerPaths) -> list[dict[str, Any]]:
    if not paths.tasks_path.exists():
        return []
    return json.loads(paths.tasks_path.read_text(encoding="utf-8"))


def _save_tasks(paths: ManagerPaths, tasks: list[dict[str, Any]]) -> None:
    paths.tasks_path.write_text(json.dumps(tasks, indent=2) + "\n", encoding="utf-8")


def _sync_plan_status_to_tasks(paths: ManagerPaths, planned: list[dict[str, Any]]) -> None:
    by_id = {str(item["task_id"]): item for item in planned}
    tasks = _load_tasks(paths)
    for task in tasks:
        task_id = str(task.get("id"))
        if task_id not in by_id:
            continue
        item = by_id[task_id]
        task["plan_status"] = item.get("status")
        task["plan_reason"] = item.get("review_reason") or item.get("error", "")
        task["planned_at"] = item.get("generated_at", now_iso())
        task["approved"] = bool(item.get("approved"))
    _save_tasks(paths, tasks)


def _table_for_plans(plans: list[dict[str, Any]]) -> Table:
    table = Table(title="Plan Results")
    table.add_column("Task")
    table.add_column("Status")
    table.add_column("Approved")
    table.add_column("Reason")
    for item in sorted(plans, key=lambda p: str(p.get("task_id"))):
        table.add_row(
            str(item.get("task_id", "")),
            str(item.get("status", "")),
            "yes" if item.get("approved") else "no",
            str(item.get("review_reason") or item.get("error") or ""),
        )
    return table


def _load_timeline_rows(paths: ManagerPaths) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    if not paths.logs_dir.exists():
        return rows
    for timeline_path in sorted(paths.logs_dir.glob("*/timeline.json")):
        try:
            payload = json.loads(timeline_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        task_id = str(payload.get("task_id") or timeline_path.parent.name)
        steps = payload.get("step_timestamps", {})
        if not isinstance(steps, dict):
            continue
        for step, ts in sorted(steps.items()):
            rows.append((task_id, str(step), str(ts)))
    return rows


@click.group()
def main() -> None:
    """Claude Code Manager CLI."""


@main.command("init")
@click.argument("repo_path", required=False)
@click.option("--github", is_flag=True, default=False, help="Initialize GitHub repo and push.")
def init_command(repo_path: str | None, github: bool) -> None:
    repo = _repo_from_arg(repo_path)
    paths = build_paths(repo)
    ensure_runtime_dirs(paths)

    templates = Path(__file__).resolve().parent / "templates"
    if not paths.claude_md_path.exists():
        shutil.copyfile(templates / "CLAUDE.md", paths.claude_md_path)
    if not paths.claude_settings_path.exists():
        paths.claude_settings_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(templates / "settings.json", paths.claude_settings_path)
    if not paths.learnings_path.exists():
        paths.learnings_path.write_text("# LEARNINGS.md\n\n", encoding="utf-8")
    if not paths.tasks_path.exists():
        paths.tasks_path.write_text("[]\n", encoding="utf-8")

    if github:
        from manager.runtime import run_cmd

        run_cmd(["gh", "repo", "create", "--source", str(repo), "--private", "--push"], cwd=repo, check=False)
    console.print(f"Initialized ccm project at [bold]{repo}[/bold]")


@main.command("add")
@click.argument("task_prompt")
@click.option("--title", default="", help="Optional short task title")
@click.option("--repo", "repo_path", default=".", help="Repository path")
def add_command(task_prompt: str, title: str, repo_path: str) -> None:
    repo = _repo_from_arg(repo_path)
    paths = build_paths(repo)
    ensure_runtime_dirs(paths)
    tasks = _load_tasks(paths)
    next_index = len(tasks) + 1
    task_id = f"task-{next_index}"
    tasks.append(
        {
            "id": task_id,
            "title": title or f"Task {next_index}",
            "prompt": task_prompt,
            "status": "pending",
            "created_at": now_iso(),
        }
    )
    _save_tasks(paths, tasks)
    console.print(f"Added {task_id}")


@main.command("plan")
@click.option("--workers", default=DEFAULT_MAX_WORKERS, type=int, show_default=True)
@click.option("--repo", "repo_path", default=".", help="Repository path")
def plan_command(workers: int, repo_path: str) -> None:
    repo = _repo_from_arg(repo_path)
    paths = build_paths(repo)
    ensure_runtime_dirs(paths)
    tasks = _load_tasks(paths)
    planned = plan_all(tasks=tasks, repo_path=repo, plans_dir=paths.plans_dir, max_workers=workers)
    _sync_plan_status_to_tasks(paths, planned)
    console.print(_table_for_plans(planned))


@main.command("run")
@click.option("--workers", default=DEFAULT_MAX_WORKERS, type=int, show_default=True)
@click.option("--repo", "repo_path", default=".", help="Repository path")
def run_command(workers: int, repo_path: str) -> None:
    repo = _repo_from_arg(repo_path)
    paths = build_paths(repo)
    ensure_runtime_dirs(paths)
    run_workers(paths=paths, max_workers=workers)
    console.print("Run complete.")


@main.command("status")
@click.option("--repo", "repo_path", default=".", help="Repository path")
def status_command(repo_path: str) -> None:
    repo = _repo_from_arg(repo_path)
    paths = build_paths(repo)
    ensure_runtime_dirs(paths)
    tasks = _load_tasks(paths)

    task_table = Table(title="Task Status")
    task_table.add_column("ID")
    task_table.add_column("Status")
    task_table.add_column("Plan")
    task_table.add_column("Approved")
    task_table.add_column("PR")
    for task in tasks:
        task_table.add_row(
            str(task.get("id", "")),
            str(task.get("status", "")),
            str(task.get("plan_status", "")),
            "yes" if task.get("approved") else "no",
            str(task.get("pr_url", "")),
        )
    console.print(task_table)

    prs = list_prs(repo)
    pr_table = Table(title="GitHub PRs")
    pr_table.add_column("Number")
    pr_table.add_column("Title")
    pr_table.add_column("State")
    pr_table.add_column("Head")
    pr_table.add_column("URL")
    for pr in prs:
        pr_table.add_row(
            str(pr.get("number", "")),
            str(pr.get("title", "")),
            str(pr.get("state", "")),
            str(pr.get("headRefName", "")),
            str(pr.get("url", "")),
        )
    console.print(pr_table)

    timeline_rows = _load_timeline_rows(paths)
    timeline_table = Table(title="Task Lifecycle Timeline")
    timeline_table.add_column("Task")
    timeline_table.add_column("Step")
    timeline_table.add_column("Timestamp")
    for task_id, step, ts in timeline_rows:
        timeline_table.add_row(task_id, step, ts)
    console.print(timeline_table)


@main.command("reflect")
@click.option("--repo", "repo_path", default=".", help="Repository path")
def reflect_command(repo_path: str) -> None:
    repo = _repo_from_arg(repo_path)
    paths = build_paths(repo)
    ensure_runtime_dirs(paths)
    rules = reflect_rules_with_claude(repo, paths.learnings_path)
    update_claude_md_rules(paths.claude_md_path, rules)
    console.print(f"Updated CLAUDE.md with {len(rules)} learned rule(s).")


@main.command("timeline")
@click.option("--repo", "repo_path", default=".", help="Repository path")
def timeline_command(repo_path: str) -> None:
    repo = _repo_from_arg(repo_path)
    paths = build_paths(repo)
    ensure_runtime_dirs(paths)
    rows = _load_timeline_rows(paths)
    table = Table(title="Task Lifecycle Timeline")
    table.add_column("Task")
    table.add_column("Step")
    table.add_column("Timestamp")
    for task_id, step, ts in rows:
        table.add_row(task_id, step, ts)
    console.print(table)


@main.command("cleanup")
@click.option("--repo", "repo_path", default=".", help="Repository path")
def cleanup_command(repo_path: str) -> None:
    repo = _repo_from_arg(repo_path)
    paths = build_paths(repo)
    ensure_runtime_dirs(paths)
    tasks = _load_tasks(paths)

    removed = 0
    for task in tasks:
        if task.get("status") != "done":
            continue
        branch = str(task.get("branch") or "").strip()
        if not branch:
            continue
        delete_remote_branch(repo, branch)
        removed += 1
    console.print(f"Cleanup complete. Remote branches removed: {removed}")


if __name__ == "__main__":
    main()

