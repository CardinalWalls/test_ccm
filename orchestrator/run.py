import datetime as dt
import fcntl
import json
import os
import subprocess
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKTREE_ROOT = REPO_ROOT.parent / "claude-learning-worktrees"
DATA_DIR = REPO_ROOT / "data"
TASKS_PATH = DATA_DIR / "dev-tasks.json"
TASK_LOCK = DATA_DIR / "dev-tasks.lock"
MERGE_LOCK = DATA_DIR / "merge.lock"
PROGRESS_PATH = REPO_ROOT / "PROGRESS.md"
MAX_ITERATIONS = 3
WORKER_COUNT = 2


def now_iso() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()


def log(worker_id: int, message: str) -> None:
    print(f"[Worker {worker_id}] {message}", flush=True)


def run_cmd(
    command: list[str],
    cwd: Path | None = None,
    timeout: int = 300,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    cp = subprocess.run(
        command,
        cwd=str(cwd) if cwd else str(REPO_ROOT),
        text=True,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=timeout,
    )
    if check and cp.returncode != 0:
        raise RuntimeError(
            "Command failed: "
            + " ".join(command)
            + f"\nstdout:\n{cp.stdout}\nstderr:\n{cp.stderr}"
        )
    return cp


def locked_json_update(path: Path, lock_path: Path, fn):
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            result = fn(data)
            with path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                f.write("\n")
            return result
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def claim_task() -> dict[str, Any] | None:
    def _claim(data: list[dict[str, Any]]):
        for task in data:
            if task.get("status") == "pending":
                task["status"] = "in_progress"
                task["claimed_at"] = now_iso()
                return task.copy()
        return None

    return locked_json_update(TASKS_PATH, TASK_LOCK, _claim)


def update_task_status(task_id: str, status: str, extra: dict[str, Any] | None = None) -> None:
    extra = extra or {}

    def _update(data: list[dict[str, Any]]):
        for task in data:
            if task.get("id") == task_id:
                task["status"] = status
                task.update(extra)
                return
        raise RuntimeError(f"Task not found: {task_id}")

    locked_json_update(TASKS_PATH, TASK_LOCK, _update)


def create_worktree(task: dict[str, Any], worker_id: int) -> tuple[str, Path]:
    task_id = str(task["id"])
    branch_name = f"task/{task_id}"
    worktree_path = WORKTREE_ROOT / f"task-{task_id}"
    WORKTREE_ROOT.mkdir(parents=True, exist_ok=True)

    if worktree_path.exists():
        run_cmd(["git", "worktree", "remove", "--force", str(worktree_path)], check=False)

    run_cmd(
        [
            "git",
            "-C",
            str(REPO_ROOT),
            "worktree",
            "add",
            "-b",
            branch_name,
            str(worktree_path),
        ]
    )
    log(worker_id, f"created worktree {worktree_path} on {branch_name}")

    # Ensure each worktree has dependencies ready without mutating lockfiles.
    run_cmd(["npm", "ci"], cwd=worktree_path, timeout=600)

    return branch_name, worktree_path


def claude_exec(worktree_path: Path, prompt: str, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    command = [
        "npx",
        "claude",
        "-p",
        prompt,
        "--dangerously-skip-permissions",
        "--max-budget-usd",
        "1.00",
    ]
    return run_cmd(command, cwd=worktree_path, timeout=timeout, check=False)


def execute_task(worktree_path: Path, task: dict[str, Any], iteration: int, worker_id: int) -> None:
    prompt = (
        "You are implementing a real coding task in this repository. "
        f"Task: {task['prompt']}\n"
        "Requirements:\n"
        "1) Implement production code.\n"
        "2) Add or update Vitest tests.\n"
        "3) Run tests and fix failures.\n"
        "4) Do not stop until tests pass for files you changed.\n"
        "5) Keep changes minimal and correct.\n"
        f"This is iteration {iteration}. If prior attempts failed tests, fix them now."
    )
    cp = claude_exec(worktree_path, prompt)
    log(worker_id, f"claude exit={cp.returncode} iteration={iteration}")
    if cp.stdout.strip():
        log(worker_id, f"claude stdout preview: {cp.stdout.strip()[:180]}")
    if cp.stderr.strip():
        log(worker_id, f"claude stderr preview: {cp.stderr.strip()[:180]}")


def run_tests(worktree_path: Path, worker_id: int) -> bool:
    cp = run_cmd(["npx", "vitest", "run"], cwd=worktree_path, timeout=300, check=False)
    passed = cp.returncode == 0
    log(worker_id, f"tests {'passed' if passed else 'failed'}")
    if not passed:
        log(worker_id, f"test stderr preview: {cp.stderr.strip()[:240]}")
        log(worker_id, f"test stdout preview: {cp.stdout.strip()[:240]}")
    return passed


def commit_worktree_changes(worktree_path: Path, task: dict[str, Any], worker_id: int) -> bool:
    status = run_cmd(["git", "status", "--porcelain"], cwd=worktree_path, check=False)
    if not status.stdout.strip():
        log(worker_id, "no changes to commit in worktree")
        return False
    run_cmd(["git", "add", "-A"], cwd=worktree_path)
    run_cmd(
        ["git", "commit", "-m", f"feat({task['id']}): implement task changes"],
        cwd=worktree_path,
        check=False,
    )
    return True


def rebase_onto_master(worktree_path: Path, worker_id: int) -> str:
    cp = run_cmd(["git", "rebase", "master"], cwd=worktree_path, check=False)
    if cp.returncode == 0:
        log(worker_id, "rebase onto master clean")
        return "clean"
    if "CONFLICT" in (cp.stdout + cp.stderr):
        log(worker_id, "rebase conflict detected")
        return "conflict"
    raise RuntimeError(f"rebase failed unexpectedly\nstdout:\n{cp.stdout}\nstderr:\n{cp.stderr}")


def resolve_conflicts(worktree_path: Path, worker_id: int) -> None:
    prompt = (
        "Resolve all active git rebase conflicts in this repository.\n"
        "Steps:\n"
        "1) Run git status to identify conflicted files.\n"
        "2) Edit files to keep all intended behavior from both sides.\n"
        "3) Remove conflict markers.\n"
        "4) git add resolved files.\n"
        "5) git rebase --continue.\n"
        "Repeat until rebase completes.\n"
        "Then run npx vitest run and fix any test failures."
    )
    for attempt in range(1, MAX_ITERATIONS + 1):
        cp = claude_exec(worktree_path, prompt, timeout=900)
        log(worker_id, f"conflict-resolve attempt={attempt} exit={cp.returncode}")
        status = run_cmd(["git", "status", "--porcelain"], cwd=worktree_path, check=False)
        has_conflict_markers = any(line.startswith("UU ") or line.startswith("AA ") for line in status.stdout.splitlines())
        rebase_state_exists = (worktree_path / ".git" / "rebase-merge").exists() or (
            worktree_path / ".git" / "rebase-apply"
        ).exists()
        if not has_conflict_markers and not rebase_state_exists:
            log(worker_id, "conflicts resolved and rebase finished")
            return
    raise RuntimeError("Unable to resolve conflicts after retries")


def with_merge_lock(fn):
    with MERGE_LOCK.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            return fn()
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def merge_to_master(branch_name: str, task: dict[str, Any], worker_id: int) -> str:
    def _merge():
        run_cmd(["git", "-C", str(REPO_ROOT), "checkout", "master"])
        cp = run_cmd(
            [
                "git",
                "-C",
                str(REPO_ROOT),
                "merge",
                "--no-ff",
                branch_name,
                "-m",
                f"merge({task['id']}): integrate worktree result",
            ],
            check=False,
        )
        if cp.returncode != 0 and "Already up to date." not in cp.stdout:
            run_cmd(["git", "-C", str(REPO_ROOT), "merge", "--abort"], check=False)
            raise RuntimeError(f"merge failed\nstdout:\n{cp.stdout}\nstderr:\n{cp.stderr}")
        test_cp = run_cmd(["npx", "vitest", "run"], cwd=REPO_ROOT, check=False, timeout=300)
        if test_cp.returncode != 0:
            raise RuntimeError(
                "post-merge tests failed\n"
                + f"stdout:\n{test_cp.stdout}\n"
                + f"stderr:\n{test_cp.stderr}"
            )
        commit_id = (
            run_cmd(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], check=True).stdout.strip()
        )
        return commit_id

    commit_id = with_merge_lock(_merge)
    log(worker_id, f"merged {branch_name} to master at {commit_id}")
    return commit_id


def cleanup_worktree(branch_name: str, worktree_path: Path, worker_id: int) -> None:
    run_cmd(["git", "-C", str(REPO_ROOT), "worktree", "remove", "--force", str(worktree_path)], check=False)
    run_cmd(["git", "-C", str(REPO_ROOT), "branch", "-D", branch_name], check=False)
    log(worker_id, f"cleaned up {branch_name}")


def log_experience(task: dict[str, Any], result: dict[str, Any]) -> None:
    lines = [
        f"## {task['id']} - {task['title']}",
        f"- completed_at: {now_iso()}",
        f"- iterations: {result.get('iterations')}",
        f"- had_conflict: {result.get('had_conflict')}",
        f"- status: {result.get('status')}",
        f"- commit_id: {result.get('commit_id', 'n/a')}",
        f"- notes: {result.get('notes', '')}",
        "",
    ]
    with PROGRESS_PATH.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines))


def worker_loop(worker_id: int) -> None:
    while True:
        task = claim_task()
        if not task:
            log(worker_id, "queue empty; exiting worker")
            return
        task_id = str(task["id"])
        branch_name = ""
        worktree_path = None
        result = {
            "iterations": 0,
            "had_conflict": False,
            "status": "failed",
            "notes": "",
        }
        try:
            log(worker_id, f"claimed {task_id}")
            branch_name, worktree_path = create_worktree(task, worker_id)
            success = False
            for iteration in range(1, MAX_ITERATIONS + 1):
                result["iterations"] = iteration
                execute_task(worktree_path, task, iteration, worker_id)
                if run_tests(worktree_path, worker_id):
                    success = True
                    break
            if not success:
                update_task_status(
                    task_id,
                    "failed",
                    {"failed_at": now_iso(), "reason": "tests_did_not_pass_after_retries"},
                )
                result["notes"] = "tests failed after max iterations"
                log_experience(task, result)
                continue

            commit_worktree_changes(worktree_path, task, worker_id)
            rebase_result = rebase_onto_master(worktree_path, worker_id)
            if rebase_result == "conflict":
                result["had_conflict"] = True
                resolve_conflicts(worktree_path, worker_id)
                if not run_tests(worktree_path, worker_id):
                    raise RuntimeError("tests failed after conflict resolution")

            commit_id = merge_to_master(branch_name, task, worker_id)
            update_task_status(task_id, "done", {"completed_at": now_iso(), "commit_id": commit_id})
            result["status"] = "done"
            result["commit_id"] = commit_id
            result["notes"] = "task merged successfully"
            log_experience(task, result)
        except Exception as exc:
            update_task_status(
                task_id,
                "failed",
                {"failed_at": now_iso(), "reason": str(exc)[:500]},
            )
            result["notes"] = f"exception: {exc}"
            log_experience(task, result)
            log(worker_id, f"task {task_id} failed: {exc}")
            log(worker_id, traceback.format_exc())
        finally:
            if branch_name and worktree_path:
                cleanup_worktree(branch_name, worktree_path, worker_id)


def main() -> None:
    run_cmd(["git", "-C", str(REPO_ROOT), "checkout", "master"], check=True)
    with ProcessPoolExecutor(max_workers=WORKER_COUNT) as pool:
        futures = [pool.submit(worker_loop, i + 1) for i in range(WORKER_COUNT)]
        for future in as_completed(futures):
            future.result()


if __name__ == "__main__":
    main()
