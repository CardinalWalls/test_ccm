from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from manager.config import DEFAULT_BASE_BRANCH
from manager.runtime import run_cmd


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    return text.strip("-") or "task"


def branch_name_for_task(task_id: str, title: str) -> str:
    return f"task/{task_id}-{slugify(title)}"


def _replace_path_with_symlink(target: Path, source: Path) -> None:
    if target.is_symlink() or target.exists():
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        else:
            target.unlink(missing_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(source)


def _prepare_worktree_layout(repo_root: Path, worktree: Path) -> None:
    data_dir = worktree / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Shared queue/lock files for atomic task claiming across workers.
    shared_data_sources = [
        (repo_root / "data" / "dev-tasks.json", data_dir / "dev-tasks.json"),
        (repo_root / "data" / "dev-tasks.lock", data_dir / "dev-tasks.lock"),
    ]
    for source, target in shared_data_sources:
        if source.exists():
            _replace_path_with_symlink(target, source)

    # Optional shared credential file; support legacy/root and data/ locations.
    api_key_candidates = [repo_root / "data" / "api-key.json", repo_root / "api-key.json"]
    api_key_source = next((candidate for candidate in api_key_candidates if candidate.exists()), None)
    if api_key_source:
        _replace_path_with_symlink(data_dir / "api-key.json", api_key_source)

    node_modules = repo_root / "node_modules"
    if node_modules.exists():
        _replace_path_with_symlink(worktree / "node_modules", node_modules)


def create_worktree(
    repo_root: Path,
    worktree_root: Path,
    *,
    task_id: str,
    task_title: str,
    base_branch: str = DEFAULT_BASE_BRANCH,
) -> tuple[str, Path]:
    branch = branch_name_for_task(task_id, task_title)
    worktree = worktree_root / f"task-{task_id}"
    worktree_root.mkdir(parents=True, exist_ok=True)

    if worktree.exists():
        run_cmd(["git", "worktree", "remove", "--force", str(worktree)], cwd=repo_root, check=False)
    run_cmd(["git", "branch", "-D", branch], cwd=repo_root, check=False)
    run_cmd(["git", "fetch", "origin", base_branch], cwd=repo_root, check=False)
    run_cmd(
        ["git", "worktree", "add", "-b", branch, str(worktree), base_branch],
        cwd=repo_root,
        check=True,
    )
    _prepare_worktree_layout(repo_root=repo_root, worktree=worktree)
    return branch, worktree


def cleanup_worktree(repo_root: Path, branch: str, worktree: Path) -> None:
    run_cmd(["git", "worktree", "remove", "--force", str(worktree)], cwd=repo_root, check=False)
    run_cmd(["git", "branch", "-D", branch], cwd=repo_root, check=False)


def push_branch(worktree: Path, branch: str) -> None:
    run_cmd(["git", "push", "-u", "origin", branch], cwd=worktree, timeout=300, check=True)


def delete_remote_branch(repo_root: Path, branch: str) -> None:
    run_cmd(["git", "push", "origin", "--delete", branch], cwd=repo_root, timeout=300, check=False)


def create_pr(
    repo_root: Path,
    *,
    title: str,
    body: str,
    head_branch: str,
    base_branch: str = DEFAULT_BASE_BRANCH,
) -> str:
    cp = run_cmd(
        [
            "gh",
            "pr",
            "create",
            "--title",
            title,
            "--body",
            body,
            "--head",
            head_branch,
            "--base",
            base_branch,
        ],
        cwd=repo_root,
        check=True,
    )
    return cp.stdout.strip()


def auto_merge_pr(repo_root: Path, pr_ref: str) -> None:
    run_cmd(
        ["gh", "pr", "merge", "--auto", "--squash", pr_ref],
        cwd=repo_root,
        check=False,
    )


def list_prs(repo_root: Path) -> list[dict[str, Any]]:
    cp = run_cmd(
        [
            "gh",
            "pr",
            "list",
            "--json",
            "number,title,state,headRefName,baseRefName,url",
        ],
        cwd=repo_root,
        check=False,
    )
    if cp.returncode != 0 or not cp.stdout.strip():
        return []
    try:
        data = json.loads(cp.stdout)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []

