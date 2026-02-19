from __future__ import annotations

import json
import re
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
    return branch, worktree


def cleanup_worktree(repo_root: Path, branch: str, worktree: Path) -> None:
    run_cmd(["git", "worktree", "remove", "--force", str(worktree)], cwd=repo_root, check=False)
    run_cmd(["git", "branch", "-D", branch], cwd=repo_root, check=False)


def push_branch(worktree: Path, branch: str) -> None:
    run_cmd(["git", "push", "-u", "origin", branch], cwd=worktree, timeout=300, check=True)


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

