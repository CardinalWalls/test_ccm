from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from manager.config import (
    DEFAULT_BASE_BRANCH,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_MAX_WORKERS,
    ManagerPaths,
)
from manager.dispatcher import build_worker_prompt, dispatch_streaming_claude
from manager.experience import append_learning, extract_relevant_lessons, load_events, summarize_events
from manager.git_ops import cleanup_worktree, create_pr, create_worktree, push_branch
from manager.runtime import locked_json_update, now_iso, run_cmd


def _read_plan_for_task(paths: ManagerPaths, task_id: str) -> dict[str, Any] | None:
    plan_path = paths.plans_dir / f"{task_id}.json"
    if not plan_path.exists():
        return None
    try:
        return json.loads(plan_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _claim_approved_task(paths: ManagerPaths) -> dict[str, Any] | None:
    def updater(data: list[dict[str, Any]]) -> dict[str, Any] | None:
        for task in data:
            if task.get("status") != "pending":
                continue
            plan = _read_plan_for_task(paths, str(task["id"]))
            if not plan or not plan.get("approved"):
                continue
            task["status"] = "in_progress"
            task["claimed_at"] = now_iso()
            return task.copy()
        return None

    return locked_json_update(paths.tasks_path, paths.task_lock, updater)


def _update_task(paths: ManagerPaths, task_id: str, status: str, extra: dict[str, Any] | None = None) -> None:
    extra = extra or {}

    def updater(data: list[dict[str, Any]]) -> None:
        for task in data:
            if str(task.get("id")) == str(task_id):
                task["status"] = status
                task.update(extra)
                return
        raise RuntimeError(f"Task not found: {task_id}")

    locked_json_update(paths.tasks_path, paths.task_lock, updater)


def _run_tests(worktree: Path) -> bool:
    cp = run_cmd(["npm", "test"], cwd=worktree, timeout=600, check=False)
    return cp.returncode == 0


def _commit_task(worktree: Path, task_id: str) -> bool:
    status = run_cmd(["git", "status", "--porcelain"], cwd=worktree, check=False)
    if not status.stdout.strip():
        return False
    run_cmd(["git", "add", "-A"], cwd=worktree)
    run_cmd(
        ["git", "commit", "-m", f"feat({task_id}): implement approved plan"],
        cwd=worktree,
        check=False,
    )
    return True


def _rebase_branch(worktree: Path, base_branch: str) -> tuple[bool, bool]:
    run_cmd(["git", "fetch", "origin", base_branch], cwd=worktree, check=False)
    cp = run_cmd(["git", "rebase", f"origin/{base_branch}"], cwd=worktree, check=False)
    if cp.returncode == 0:
        return True, False
    has_conflict = "CONFLICT" in (cp.stdout + cp.stderr)
    return False, has_conflict


def _resolve_rebase_conflict(worktree: Path, task: dict[str, Any], paths: ManagerPaths) -> bool:
    prompt = (
        "Resolve active git rebase conflicts in this repository.\n"
        "Follow protocol: git status -> edit conflict files -> git add -> git rebase --continue.\n"
        "Then run npm test and fix failures.\n"
    )
    rc, _ = dispatch_streaming_claude(
        worktree=worktree,
        task=task,
        prompt=prompt,
        logs_dir=paths.logs_dir,
    )
    if rc != 0:
        return False
    rebase_state = (worktree / ".git" / "rebase-merge").exists() or (worktree / ".git" / "rebase-apply").exists()
    return not rebase_state and _run_tests(worktree)


def _pr_body(plan: dict[str, Any] | None, lessons: list[str]) -> str:
    plan_text = json.dumps((plan or {}).get("plan", {}), indent=2, ensure_ascii=True)
    learnings = "\n".join(f"- {item}" for item in lessons) if lessons else "- none"
    return (
        "## Plan\n"
        "```json\n"
        f"{plan_text}\n"
        "```\n\n"
        "## Relevant Lessons\n"
        f"{learnings}\n"
    )


def execute_one_task(task: dict[str, Any], paths: ManagerPaths, worker_id: int) -> None:
    task_id = str(task["id"])
    plan = _read_plan_for_task(paths, task_id)
    lessons = extract_relevant_lessons(paths.learnings_path, task=task)
    branch = ""
    worktree: Path | None = None
    iterations = 0
    commit_id: str | None = None
    had_conflict = False
    try:
        branch, worktree = create_worktree(
            repo_root=paths.repo_root,
            worktree_root=paths.worktree_root,
            task_id=task_id,
            task_title=task.get("title", task_id),
            base_branch=DEFAULT_BASE_BRANCH,
        )
        run_cmd(["npm", "ci"], cwd=worktree, timeout=1200, check=False)
        success = False
        while iterations < DEFAULT_MAX_ITERATIONS:
            iterations += 1
            prompt = build_worker_prompt(task=task, plan=plan, lessons=lessons)
            rc, _summary = dispatch_streaming_claude(
                worktree=worktree,
                task=task,
                prompt=prompt,
                logs_dir=paths.logs_dir,
            )
            if rc == 0 and _run_tests(worktree):
                success = True
                break
        if not success:
            raise RuntimeError("task did not pass tests within max iterations")

        _commit_task(worktree, task_id=task_id)
        rebased, conflict = _rebase_branch(worktree, base_branch=DEFAULT_BASE_BRANCH)
        if not rebased and conflict:
            had_conflict = True
            if not _resolve_rebase_conflict(worktree, task=task, paths=paths):
                raise RuntimeError("conflict resolution failed")
        push_branch(worktree=worktree, branch=branch)
        pr_url = create_pr(
            repo_root=paths.repo_root,
            title=f"feat({task_id}): {task.get('title', '').strip()}",
            body=_pr_body(plan, lessons),
            head_branch=branch,
            base_branch=DEFAULT_BASE_BRANCH,
        )
        commit_id = run_cmd(["git", "rev-parse", "HEAD"], cwd=worktree).stdout.strip()
        _update_task(
            paths,
            task_id,
            "done",
            {
                "completed_at": now_iso(),
                "commit_id": commit_id,
                "branch": branch,
                "pr_url": pr_url,
                "worker_id": worker_id,
            },
        )
    except Exception as exc:  # noqa: BLE001
        _update_task(
            paths,
            task_id,
            "failed",
            {
                "failed_at": now_iso(),
                "reason": str(exc)[:500],
                "worker_id": worker_id,
            },
        )
    finally:
        events = load_events(paths.logs_dir / task_id / "events.jsonl")
        summary = summarize_events(task_id, events)
        summary["conflict"] = bool(summary.get("conflict")) or had_conflict
        append_learning(
            paths.learnings_path,
            summary,
            commit_id=commit_id,
            title=task.get("title", ""),
            iterations=iterations or 1,
        )
        if branch and worktree:
            cleanup_worktree(paths.repo_root, branch, worktree)


def worker_loop(paths: ManagerPaths, worker_id: int) -> None:
    while True:
        task = _claim_approved_task(paths)
        if not task:
            return
        execute_one_task(task=task, paths=paths, worker_id=worker_id)


def run_workers(paths: ManagerPaths, max_workers: int = DEFAULT_MAX_WORKERS) -> None:
    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(worker_loop, paths, idx + 1) for idx in range(max_workers)]
        for future in as_completed(futures):
            future.result()

