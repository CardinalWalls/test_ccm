from __future__ import annotations

import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from manager.config import (
    BASE_WORKER_PORT,
    DEFAULT_BASE_BRANCH,
    DEFAULT_MAX_TURNS_IMPLEMENT,
    DEFAULT_MAX_TURNS_REPAIR,
    DEFAULT_MAX_WORKERS,
    ManagerPaths,
    TASK_WALL_CLOCK_TIMEOUT,
)
from manager.dispatcher import build_worker_prompt, dispatch_streaming_claude
from manager.stream_monitor import DispatchError, StreamSummary
from manager.experience import append_learning, extract_relevant_lessons, load_events, summarize_events
from manager.git_ops import cleanup_worktree, create_pr, create_worktree, push_branch
from manager.runtime import locked_json_update, now_iso, run_cmd


@dataclass
class TaskTimeline:
    task_id: str
    step_timestamps: dict[str, str] = field(default_factory=dict)
    counters: dict[str, int] = field(default_factory=dict)
    dispatches: list[dict[str, Any]] = field(default_factory=list)
    merge_attempts: list[dict[str, Any]] = field(default_factory=list)
    rebase_attempts: list[dict[str, Any]] = field(default_factory=list)

    def mark(self, step: str, ts: str | None = None) -> None:
        self.step_timestamps[step] = ts or now_iso()

    def bump(self, key: str) -> None:
        self.counters[key] = int(self.counters.get(key, 0)) + 1

    def record_dispatch(
        self,
        *,
        stage: str,
        summary: StreamSummary,
        return_code: int,
        prompt_preview: str | None = None,
        test_passed: bool | None = None,
        test_output: str | None = None,
        merge_output: str | None = None,
        rebase_output: str | None = None,
        rebase_conflict: bool | None = None,
        commit_hash: str | None = None,
        commit_files: list[str] | None = None,
    ) -> None:
        rec: dict[str, Any] = {
            "ts": now_iso(),
            "stage": stage,
            "return_code": return_code,
            "healthy": summary.is_healthy,
            "events": summary.events,
            "turns": summary.turns,
            "error_events": summary.error_events,
            "input_tokens": summary.input_tokens,
            "output_tokens": summary.output_tokens,
            "estimated_cost_usd": round(summary.estimated_cost_usd, 6),
            "tool_counts": dict(summary.tool_counts),
        }
        if prompt_preview is not None:
            rec["prompt_preview"] = prompt_preview[:200]
        if test_passed is not None:
            rec["test_passed"] = test_passed
        if test_output is not None:
            rec["test_output"] = test_output[:2000]
        if merge_output is not None:
            rec["merge_output"] = merge_output[:2000]
        if rebase_output is not None:
            rec["rebase_output"] = rebase_output[:2000]
        if rebase_conflict is not None:
            rec["rebase_conflict"] = rebase_conflict
        if commit_hash is not None:
            rec["commit_hash"] = commit_hash
        if commit_files is not None:
            rec["commit_files"] = commit_files
        self.dispatches.append(rec)

    def update_last_dispatch(self, **kwargs: Any) -> None:
        if not self.dispatches:
            return
        for k, v in kwargs.items():
            if v is not None:
                self.dispatches[-1][k] = v

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "step_timestamps": self.step_timestamps,
            "counters": self.counters,
            "dispatches": self.dispatches,
            "merge_attempts": self.merge_attempts,
            "rebase_attempts": self.rebase_attempts,
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


def _run_tests(worktree: Path) -> tuple[bool, str]:
    cp = run_cmd(["npm", "test"], cwd=worktree, timeout=600, check=False)
    output = (cp.stdout or "") + (cp.stderr or "")
    return cp.returncode == 0, output


def _check_deadline(task_id: str, started_at: float) -> None:
    elapsed = time.monotonic() - started_at
    if elapsed > TASK_WALL_CLOCK_TIMEOUT:
        raise TimeoutError(
            f"task {task_id}: exceeded wall-clock timeout ({TASK_WALL_CLOCK_TIMEOUT}s)"
        )


def _merge_and_test(worktree: Path, base_branch: str) -> tuple[bool, str]:
    _stash_artifacts(worktree)
    run_cmd(["git", "fetch", "origin", base_branch], cwd=worktree, check=False)
    cp = run_cmd(["git", "merge", f"origin/{base_branch}"], cwd=worktree, check=False)
    merge_out = (cp.stdout or "") + (cp.stderr or "")
    if cp.returncode != 0:
        run_cmd(["git", "merge", "--abort"], cwd=worktree, check=False)
        return False, merge_out
    passed, test_out = _run_tests(worktree)
    return passed, f"merge_ok\n---test---\n{test_out}"


def _commit_task(
    worktree: Path, task_id: str, base_branch: str = DEFAULT_BASE_BRANCH
) -> tuple[bool, str | None, list[str]]:
    ARTIFACT_PREFIXES = ("data/", "node_modules")

    status = run_cmd(["git", "status", "--porcelain"], cwd=worktree, check=False)
    changed_files = [line[3:] for line in status.stdout.strip().splitlines() if line.strip()]
    source_changes = [f for f in changed_files if not any(f.startswith(p) for p in ARTIFACT_PREFIXES)]

    if source_changes:
        run_cmd(["git", "add", "-A"], cwd=worktree)
        for prefix in ARTIFACT_PREFIXES:
            run_cmd(["git", "reset", "HEAD", "--", prefix], cwd=worktree, check=False)
        run_cmd(
            ["git", "commit", "-m", f"feat({task_id}): implement approved plan"],
            cwd=worktree,
            check=False,
        )
        hash_cp = run_cmd(["git", "rev-parse", "HEAD"], cwd=worktree, check=False)
        return True, hash_cp.stdout.strip() or None, source_changes

    new_commits = run_cmd(
        ["git", "log", f"origin/{base_branch}..HEAD", "--oneline"],
        cwd=worktree,
        check=False,
    )
    if new_commits.stdout.strip():
        first_line = new_commits.stdout.strip().splitlines()[0]
        commit_hash = first_line.split()[0] if first_line else None
        diff_cp = run_cmd(["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"], cwd=worktree, check=False)
        files = [f for f in diff_cp.stdout.strip().splitlines() if f and not any(f.startswith(p) for p in ARTIFACT_PREFIXES)]
        return True, commit_hash, files

    return False, None, []


def _stash_artifacts(worktree: Path) -> None:
    """Checkout artifact paths so symlink typechanges don't block rebase/merge."""
    for path in ("data", "node_modules"):
        run_cmd(["git", "checkout", "--", path], cwd=worktree, check=False)


def _rebase_branch(worktree: Path, base_branch: str) -> tuple[bool, bool, str]:
    _stash_artifacts(worktree)
    run_cmd(["git", "fetch", "origin", base_branch], cwd=worktree, check=False)
    cp = run_cmd(["git", "rebase", f"origin/{base_branch}"], cwd=worktree, check=False)
    out = (cp.stdout or "") + (cp.stderr or "")
    if cp.returncode == 0:
        return True, False, out
    has_conflict = "CONFLICT" in out
    return False, has_conflict, out


def _resolve_rebase_conflict(
    worktree: Path,
    task: dict[str, Any],
    paths: ManagerPaths,
    *,
    worker_port: int,
) -> tuple[bool, int, StreamSummary]:
    prompt = (
        "Resolve active git rebase conflicts in this repository.\n"
        "Follow protocol: git status -> edit conflict files -> git add -> git rebase --continue.\n"
        "Then run npm test and fix failures.\n"
    )
    rc, summary = dispatch_streaming_claude(
        max_turns=DEFAULT_MAX_TURNS_REPAIR,
        worktree=worktree,
        task=task,
        prompt=prompt,
        logs_dir=paths.logs_dir,
        worker_port=worker_port,
    )
    if rc != 0:
        return False, rc, summary
    rebase_state = (worktree / ".git" / "rebase-merge").exists() or (worktree / ".git" / "rebase-apply").exists()
    test_passed, _ = _run_tests(worktree)
    return (not rebase_state and test_passed), rc, summary


def _repair_merge_or_test_gate(
    worktree: Path,
    task: dict[str, Any],
    paths: ManagerPaths,
    *,
    worker_port: int,
) -> tuple[bool, int, StreamSummary]:
    prompt = (
        "You are at lifecycle step 5 (merge + test).\n"
        "If merge is unfinished or conflicted, resolve it fully.\n"
        "Then run npm test and fix failures until tests are green.\n"
    )
    rc, summary = dispatch_streaming_claude(
        max_turns=DEFAULT_MAX_TURNS_REPAIR,
        worktree=worktree,
        task=task,
        prompt=prompt,
        logs_dir=paths.logs_dir,
        worker_port=worker_port,
    )
    test_passed, _ = _run_tests(worktree)
    return rc == 0 and summary.is_healthy and test_passed, rc, summary


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
    started_at = time.monotonic()
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

        timeline.mark("step3_implement_started")
        _save_timeline(paths, timeline)
        while True:
            _check_deadline(task_id, started_at)
            iterations += 1
            timeline.bump("step3_iterations")
            prompt = build_worker_prompt(task=task, plan=plan, lessons=lessons)
            rc, _summary = dispatch_streaming_claude(
                max_turns=DEFAULT_MAX_TURNS_IMPLEMENT,
                worktree=worktree,
                task=task,
                prompt=prompt,
                logs_dir=paths.logs_dir,
                worker_port=worker_port,
            )
            timeline.record_dispatch(
                stage="step3_implement",
                summary=_summary,
                return_code=rc,
                prompt_preview=prompt[:200],
            )
            _save_timeline(paths, timeline)
            if rc != 0 or not _summary.is_healthy:
                continue
            test_passed, test_output = _run_tests(worktree)
            timeline.update_last_dispatch(test_passed=test_passed, test_output=test_output)
            _save_timeline(paths, timeline)
            if not test_passed:
                continue
            timeline.mark("step3_implement_done")
            _save_timeline(paths, timeline)
            commit_ok, commit_hash, commit_files = _commit_task(worktree, task_id=task_id)
            if commit_ok:
                timeline.update_last_dispatch(commit_hash=commit_hash, commit_files=commit_files)
                _save_timeline(paths, timeline)
                timeline.mark("step4_committed")
                _save_timeline(paths, timeline)
                break
            timeline.bump("step4_empty_commits")
            _save_timeline(paths, timeline)

        while True:
            _check_deadline(task_id, started_at)
            timeline.bump("step5_6_attempts")
            merge_ok, merge_output = _merge_and_test(worktree, base_branch=DEFAULT_BASE_BRANCH)
            timeline.merge_attempts.append({"passed": merge_ok, "output": merge_output[:2000]})
            _save_timeline(paths, timeline)
            if not merge_ok:
                repaired, repair_rc, repair_summary = _repair_merge_or_test_gate(
                    worktree=worktree,
                    task=task,
                    paths=paths,
                    worker_port=worker_port,
                )
                timeline.record_dispatch(
                    stage="step5_repair_merge_or_test",
                    summary=repair_summary,
                    return_code=repair_rc,
                )
                _save_timeline(paths, timeline)
                if not repaired:
                    continue
                timeline.mark("step5_merge_test_passed")
                _save_timeline(paths, timeline)
                continue
            timeline.mark("step5_merge_test_passed")
            _save_timeline(paths, timeline)

            rebased, conflict, rebase_output = _rebase_branch(worktree, base_branch=DEFAULT_BASE_BRANCH)
            timeline.rebase_attempts.append({"passed": rebased, "conflict": conflict, "output": rebase_output[:2000]})
            _save_timeline(paths, timeline)
            if rebased:
                timeline.mark("step6_rebase_passed")
                _save_timeline(paths, timeline)
                break

            if conflict:
                had_conflict = True
                timeline.bump("step6_conflicts")
                resolved, resolve_rc, resolve_summary = _resolve_rebase_conflict(
                    worktree,
                    task=task,
                    paths=paths,
                    worker_port=worker_port,
                )
                timeline.record_dispatch(
                    stage="step6_resolve_rebase_conflict",
                    summary=resolve_summary,
                    return_code=resolve_rc,
                    rebase_output=rebase_output,
                    rebase_conflict=conflict,
                )
                _save_timeline(paths, timeline)
                if resolved:
                    timeline.mark("step6_rebase_passed")
                    _save_timeline(paths, timeline)
                    break
            repaired, repair_rc, repair_summary = _repair_merge_or_test_gate(
                worktree=worktree,
                task=task,
                paths=paths,
                worker_port=worker_port,
            )
            timeline.record_dispatch(
                stage="step6_repair_after_failed_rebase",
                summary=repair_summary,
                return_code=repair_rc,
                rebase_output=rebase_output,
                rebase_conflict=conflict,
            )
            _save_timeline(paths, timeline)
            if not repaired:
                continue

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
    except (DispatchError, TimeoutError) as exc:
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
    except Exception as exc:  # noqa: BLE001
        _update_task(
            paths,
            task_id,
            "failed",
            {
                "failed_at": now_iso(),
                "reason": f"unexpected-manager-error: {str(exc)[:470]}",
                "worker_id": worker_id,
            },
        )
    finally:
        if branch and worktree:
            cleanup_worktree(paths.repo_root, branch, worktree)
            timeline.mark("step8_cleaned")
            _save_timeline(paths, timeline)
        timeline.mark("step9_learning_started")
        _save_timeline(paths, timeline)
        events = load_events(paths.logs_dir / task_id / "events.jsonl")
        summary = summarize_events(task_id, events)
        summary["conflict"] = bool(summary.get("conflict")) or had_conflict
        total_cost = sum(d.get("estimated_cost_usd", 0) for d in timeline.dispatches)
        append_learning(
            paths.learnings_path,
            summary,
            commit_id=commit_id,
            title=task.get("title", ""),
            iterations=iterations or 1,
            cost_override=total_cost,
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

