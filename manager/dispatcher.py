from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from manager.config import DEFAULT_MAX_BUDGET_USD
from manager.stream_monitor import StreamSummary, monitor_process


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
        "You are executing one coding task inside a managed worktree.\n"
        "Project has CLAUDE.md. Follow it strictly.\n"
        f"Task ID: {task['id']}\n"
        f"Task title: {task.get('title', '')}\n"
        f"Task prompt: {task.get('prompt', '')}\n\n"
        f"{plan_block}"
        f"{lesson_block}"
        "Requirements:\n"
        "1) Implement requested behavior only.\n"
        "2) Add/update tests.\n"
        "3) Run npm test and keep fixing until green.\n"
        "4) Commit changes once tests pass.\n"
    )


def dispatch_streaming_claude(
    worktree: Path,
    task: dict[str, Any],
    *,
    prompt: str,
    logs_dir: Path,
    max_budget_usd: str = DEFAULT_MAX_BUDGET_USD,
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
        "--max-budget-usd",
        max_budget_usd,
    ]
    proc = subprocess.Popen(
        command,
        cwd=str(worktree),
        text=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    summary = monitor_process(task_id=str(task["id"]), proc=proc, logs_root=logs_dir)
    return_code = proc.wait(timeout=timeout)
    return return_code, summary

