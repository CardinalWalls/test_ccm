from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from manager.config import (
    BASE_WORKER_PORT,
    DEFAULT_BASE_BRANCH,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_MAX_WORKERS,
    MAX_MERGE_RETRIES,
    ManagerPaths,
)
from manager.dispatcher import build_worker_prompt, dispatch_streaming_claude
from manager.experience import append_learning, extract_relevant_lessons, load_events, summarize_events
from manager.git_ops import cleanup_worktree, create_pr, create_worktree, delete_remote_branch, push_branch
from manager.runtime import locked_json_update, now_iso, run_cmd


@dataclass
class TaskTimeline:
    task_id: str
    step_timestamps: dict[str, str] = field(default_factory=dict)
    counters: dict[str, int] = field(default_factory=dict)

    def mark(self, step: str, ts: str | None = None) -> None:
        self.step_timestamps[step] = ts or now_iso()

    def bump(self, key: str) -> None:
        self.counters[key] = int(self.counters.get(key, 0)) + 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "step_timestamps": self.step_timestamps,
            "counters": self.counters,
        }


def _save_timeline(paths: ManagerPaths, timeline: TaskTimeline) -> None:
    task_dir = paths.logs_dir / timeline.task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "timeline.json").write_text(json.dumps(timeline.as_dict(), indent=2) + "\n", encoding="utf-8")


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


def _merge_and_test(worktree: Path, base_branch: str) -> bool:
    run_cmd(["git", "fetch", "origin", base_branch], cwd=worktree, check=False)
    cp = run_cmd(["git", "merge", f"origin/{base_branch}"], cwd=worktree, check=False)
    if cp.returncode != 0:
        run_cmd(["git", "merge", "--abort"], cwd=worktree, check=False)
        return False
    return _run_tests(worktree)


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


def _resolve_rebase_conflict(
    worktree: Path,
    task: dict[str, Any],
    paths: ManagerPaths,
    *,
    worker_port: int,
) -> bool:
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
        worker_port=worker_port,
    )
    if rc != 0:
        return False
    rebase_state = (worktree / ".git" / "rebase-merge").exists() or (worktree / ".git" / "rebase-apply").exists()
    return not rebase_state and _run_tests(worktree)


def _repair_merge_or_test_gate(
    worktree: Path,
    task: dict[str, Any],
    paths: ManagerPaths,
    *,
    worker_port: int,
) -> bool:
    prompt = (
        "You are at lifecycle step 5 (merge + test).\n"
        "If merge is unfinished or conflicted, resolve it fully.\n"
        "Then run npm test and fix failures until tests are green.\n"
    )
    rc, _ = dispatch_streaming_claude(
        worktree=worktree,
        task=task,
        prompt=prompt,
        logs_dir=paths.logs_dir,
        worker_port=worker_port,
    )
    return rc == 0


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
    worker_port = BASE_WORKER_PORT + worker_id
    timeline = TaskTimeline(task_id=task_id)
    timeline.mark("step1_claimed", task.get("claimed_at") or now_iso())
    _save_timeline(paths, timeline)
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
        timeline.mark("step2_worktree_created")
        _save_timeline(paths, timeline)

        # Worktree setup symlinks node_modules when available; otherwise bootstrap dependencies.
        if not (paths.repo_root / "node_modules").exists():
            run_cmd(["npm", "ci"], cwd=worktree, timeout=1200, check=False)

        success = False
        timeline.mark("step3_implement_started")
        _save_timeline(paths, timeline)
        while iterations < DEFAULT_MAX_ITERATIONS:
            iterations += 1
            timeline.bump("step3_iterations")
            prompt = build_worker_prompt(task=task, plan=plan, lessons=lessons)
            rc, _summary = dispatch_streaming_claude(
                worktree=worktree,
                task=task,
                prompt=prompt,
                logs_dir=paths.logs_dir,
                worker_port=worker_port,
            )
            if rc == 0 and _run_tests(worktree):
                success = True
                break
        if not success:
            raise RuntimeError("task did not pass tests within max iterations")
        timeline.mark("step3_implement_done")
        _save_timeline(paths, timeline)

        _commit_task(worktree, task_id=task_id)
        timeline.mark("step4_committed")
        _save_timeline(paths, timeline)

        merged_and_rebased = False
        for _ in range(MAX_MERGE_RETRIES):
            timeline.bump("step5_6_attempts")
            if not _merge_and_test(worktree, base_branch=DEFAULT_BASE_BRANCH):
                _repair_merge_or_test_gate(
                    worktree=worktree,
                    task=task,
                    paths=paths,
                    worker_port=worker_port,
                )
                continue
            timeline.mark("step5_merge_test_passed")
            _save_timeline(paths, timeline)

            rebased, conflict = _rebase_branch(worktree, base_branch=DEFAULT_BASE_BRANCH)
            if rebased:
                timeline.mark("step6_rebase_passed")
                _save_timeline(paths, timeline)
                merged_and_rebased = True
                break

            if conflict:
                had_conflict = True
                timeline.bump("step6_conflicts")
                if _resolve_rebase_conflict(
                    worktree,
                    task=task,
                    paths=paths,
                    worker_port=worker_port,
                ):
                    timeline.mark("step6_rebase_passed")
                    _save_timeline(paths, timeline)
                    merged_and_rebased = True
                    break
            _repair_merge_or_test_gate(
                worktree=worktree,
                task=task,
                paths=paths,
                worker_port=worker_port,
            )
        if not merged_and_rebased:
            raise RuntimeError("merge/rebase failed after retry loop")

        push_branch(worktree=worktree, branch=branch)
        timeline.mark("step6_pushed")
        _save_timeline(paths, timeline)
        pr_url = create_pr(
            repo_root=paths.repo_root,
            title=f"feat({task_id}): {task.get('title', '').strip()}",
            body=_pr_body(plan, lessons),
            head_branch=branch,
            base_branch=DEFAULT_BASE_BRANCH,
        )
        timeline.mark("step6_pr_created")
        _save_timeline(paths, timeline)
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
        timeline.mark("step7_marked_done")
        _save_timeline(paths, timeline)
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
        if branch and worktree:
            # Best-effort step-8 remote cleanup; ignored when branch cannot be removed yet.
            delete_remote_branch(paths.repo_root, branch)
            cleanup_worktree(paths.repo_root, branch, worktree)
            timeline.mark("step8_cleaned")
            _save_timeline(paths, timeline)
        timeline.mark("step9_learning_started")
        _save_timeline(paths, timeline)
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
        timeline.mark("step9_learning_recorded")
        _save_timeline(paths, timeline)


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

