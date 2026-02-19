from __future__ import annotations

import json
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from manager.config import PLAN_REVIEW_SCHEMA, PLAN_SCHEMA, schema_json
from manager.runtime import now_iso


def _parse_json_payload(payload: str) -> dict[str, Any]:
    text = payload.strip()
    if not text:
        raise ValueError("Empty JSON output")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or start >= end:
            raise
        return json.loads(text[start : end + 1])


def _run_claude_json(command: list[str], cwd: Path, timeout: int) -> dict[str, Any]:
    cp = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        timeout=timeout,
    )
    if cp.returncode != 0:
        raise RuntimeError(
            "Claude command failed: "
            + " ".join(command)
            + f"\nstdout:\n{cp.stdout}\nstderr:\n{cp.stderr}"
        )
    return _parse_json_payload(cp.stdout)


def _plan_prompt(task: dict[str, Any]) -> str:
    return (
        "You are planning implementation only. Do not edit files.\n"
        f"Task ID: {task['id']}\n"
        f"Title: {task.get('title', '')}\n"
        f"Prompt: {task.get('prompt', '')}\n"
        "Return only JSON matching the schema."
    )


def generate_plan_for_task(task: dict[str, Any], repo_path: Path) -> dict[str, Any]:
    command = [
        "npx",
        "claude",
        "-p",
        _plan_prompt(task),
        "--permission-mode",
        "plan",
        "--tools",
        "Read,Grep,Glob",
        "--json-schema",
        schema_json(PLAN_SCHEMA),
        "--output-format",
        "json",
        "--max-turns",
        "15",
    ]
    plan = _run_claude_json(command, cwd=repo_path, timeout=600)
    return {
        "task_id": task["id"],
        "task_title": task.get("title", ""),
        "generated_at": now_iso(),
        "status": "planned",
        "plan": plan,
    }


def generate_plans(tasks: list[dict[str, Any]], repo_path: Path, max_workers: int = 3) -> list[dict[str, Any]]:
    plans: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_map = {
            pool.submit(generate_plan_for_task, task, repo_path): task["id"]
            for task in tasks
            if task.get("status") in {"pending", "in_progress"}
        }
        for future in as_completed(future_map):
            task_id = future_map[future]
            try:
                plans.append(future.result())
            except Exception as exc:  # noqa: BLE001
                plans.append(
                    {
                        "task_id": task_id,
                        "generated_at": now_iso(),
                        "status": "plan_failed",
                        "error": str(exc),
                    }
                )
    return plans


def review_plans_with_manager(plans: list[dict[str, Any]], repo_path: Path) -> dict[str, Any]:
    prompt = (
        "You are a senior engineering manager reviewing implementation plans.\n"
        "For each plan, evaluate completeness, conflict risk with other plans, "
        "risk realism, and acceptance testability.\n"
        "Return only JSON matching schema.\n\n"
        f"Plans JSON:\n{json.dumps(plans, ensure_ascii=True)}"
    )
    command = [
        "npx",
        "claude",
        "-p",
        prompt,
        "--json-schema",
        schema_json(PLAN_REVIEW_SCHEMA),
        "--output-format",
        "json",
        "--max-turns",
        "8",
    ]
    return _run_claude_json(command, cwd=repo_path, timeout=900)


def save_plan(plan: dict[str, Any], plans_dir: Path) -> Path:
    plans_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plans_dir / f"{plan['task_id']}.json"
    plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    return plan_path


def apply_review_results(
    plans: list[dict[str, Any]],
    review_result: dict[str, Any],
) -> list[dict[str, Any]]:
    so = review_result.get("structured_output") or review_result
    verdict_by_id: dict[str, dict[str, Any]] = {
        item["task_id"]: item for item in so.get("verdicts", [])
    }
    updated: list[dict[str, Any]] = []
    for plan in plans:
        verdict = verdict_by_id.get(plan["task_id"])
        if verdict:
            plan["reviewed_at"] = now_iso()
            plan["approved"] = bool(verdict.get("approved"))
            plan["review_reason"] = verdict.get("reason", "")
            if "suggested_order" in verdict:
                plan["suggested_order"] = verdict["suggested_order"]
            plan["status"] = "approved" if plan["approved"] else "rejected"
        updated.append(plan)
    return updated


def plan_all(tasks: list[dict[str, Any]], repo_path: Path, plans_dir: Path, max_workers: int = 3) -> list[dict[str, Any]]:
    plans = generate_plans(tasks=tasks, repo_path=repo_path, max_workers=max_workers)
    planned_ok = [p for p in plans if p.get("status") == "planned"]
    if planned_ok:
        review = review_plans_with_manager(plans=planned_ok, repo_path=repo_path)
        plans = apply_review_results(plans, review)
    for plan in plans:
        save_plan(plan, plans_dir=plans_dir)
    return plans

