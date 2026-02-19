from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from manager.stream_monitor import DispatchError, StreamSummary, monitor_process


def build_worker_prompt(
    task: dict[str, Any],
    *,
    plan: dict[str, Any] | None,
    lessons: list[str],
) -> str:
    plan_block = ""
    if plan:
        plan_block = (
            "Approved plan context (follow this plan strictly):\n"
            + json.dumps(plan.get("plan", {}), indent=2, ensure_ascii=True)
            + "\n"
        )
    lesson_block = ""
    if lessons:
        lesson_block = "Relevant lessons from LEARNINGS.md:\n- " + "\n- ".join(lessons) + "\n"
    return (
        "You are executing one coding task inside a managed git worktree.\n"
        "The manager handles git operations (worktree, merge, rebase, PR, cleanup).\n"
        "Your ONLY job: implement the feature using tools, make tests pass, and commit.\n\n"
        f"Task ID: {task['id']}\n"
        f"Task title: {task.get('title', '')}\n"
        f"Task prompt: {task.get('prompt', '')}\n\n"
        f"{plan_block}"
        f"{lesson_block}"
        "MANDATORY EXECUTION STEPS — do these NOW, in order:\n"
        "1. Read existing source files to understand the codebase.\n"
        "2. Write/Edit source files to implement the requested feature.\n"
        "3. Write/Edit test files to add comprehensive tests.\n"
        "4. Run `npm test` via Bash and fix failures until all tests pass.\n"
        "5. Run `git add -A && git commit -m 'feat({task_id}): <description>'`.\n\n"
        "CRITICAL RULES:\n"
        "- You MUST use Read, Write, Edit, and Bash tools. Text-only responses are useless.\n"
        "- Do NOT create worktrees, merge branches, push, or clean up — the manager does that.\n"
        "- Do NOT modify files under data/ or node_modules.\n"
        "- Commit message format: feat({task_id}): <short description>\n"
    )


def dispatch_streaming_claude(
    worktree: Path,
    task: dict[str, Any],
    *,
    prompt: str,
    logs_dir: Path,
    worker_port: int | None = None,
    max_turns: int,
    timeout: int = 1200,
) -> tuple[int, StreamSummary]:
    command = [
        "npx",
        "claude",
        "-p",
        prompt,
        "--dangerously-skip-permissions",
        "--output-format",
        "stream-json",
        "--verbose",
        "--max-turns",
        str(max_turns),
    ]
    env = os.environ.copy()
    if worker_port is not None:
        env["PORT"] = str(worker_port)
    proc = subprocess.Popen(
        command,
        cwd=str(worktree),
        text=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    summary = monitor_process(task_id=str(task["id"]), proc=proc, logs_root=logs_dir)
    return_code = proc.wait(timeout=timeout)
    if summary.is_api_error:
        raise DispatchError(
            f"API-level failure for {summary.task_id}: "
            f"{summary.error_events} errors, 0 cost, 0 tools"
        )
    return return_code, summary

