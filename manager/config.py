from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ManagerPaths:
    repo_root: Path
    data_dir: Path
    tasks_path: Path
    task_lock: Path
    merge_lock: Path
    plans_dir: Path
    logs_dir: Path
    worktree_root: Path
    learnings_path: Path
    claude_md_path: Path
    claude_settings_path: Path


DEFAULT_MAX_WORKERS = 2
DEFAULT_MAX_ITERATIONS = 3
MAX_MERGE_RETRIES = 3
DEFAULT_MAX_BUDGET_USD = "1.00"
DEFAULT_BASE_BRANCH = "main"
BASE_WORKER_PORT = 5200

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "steps": {"type": "array", "items": {"type": "string"}},
        "acceptance": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
        "files_to_modify": {"type": "array", "items": {"type": "string"}},
        "estimate": {"type": "string"},
    },
    "required": ["title", "steps", "acceptance"],
}

PLAN_REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "approved": {"type": "boolean"},
                    "reason": {"type": "string"},
                    "suggested_order": {"type": "integer"},
                },
                "required": ["task_id", "approved", "reason"],
            },
        }
    },
    "required": ["verdicts"],
}


def build_paths(repo_root: Path) -> ManagerPaths:
    data_dir = repo_root / "data"
    return ManagerPaths(
        repo_root=repo_root,
        data_dir=data_dir,
        tasks_path=data_dir / "dev-tasks.json",
        task_lock=data_dir / "dev-tasks.lock",
        merge_lock=data_dir / "merge.lock",
        plans_dir=repo_root / "plans",
        logs_dir=repo_root / "logs",
        worktree_root=repo_root.parent / f"{repo_root.name}-worktrees",
        learnings_path=repo_root / "LEARNINGS.md",
        claude_md_path=repo_root / "CLAUDE.md",
        claude_settings_path=repo_root / ".claude" / "settings.json",
    )


def ensure_runtime_dirs(paths: ManagerPaths) -> None:
    for directory in (
        paths.data_dir,
        paths.plans_dir,
        paths.logs_dir,
        paths.worktree_root,
        paths.claude_settings_path.parent,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    paths.task_lock.touch(exist_ok=True)
    paths.merge_lock.touch(exist_ok=True)


def schema_json(schema: dict) -> str:
    return json.dumps(schema, ensure_ascii=True)

