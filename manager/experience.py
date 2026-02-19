from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from manager.runtime import now_iso


def load_events(events_path: Path) -> list[dict[str, Any]]:
    if not events_path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def _extract_cost_from_event(event: dict[str, Any]) -> float:
    for key in ("total_cost_usd", "cost_usd"):
        v = event.get(key)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    usage = event.get("usage")
    if isinstance(usage, dict):
        for key in ("cost_usd", "usd", "cost"):
            if key in usage:
                try:
                    return float(usage[key])
                except (TypeError, ValueError):
                    pass
    msg = event.get("message")
    if isinstance(msg, dict):
        usage = msg.get("usage")
        if isinstance(usage, dict) and "cost_usd" in usage:
            try:
                return float(usage["cost_usd"])
            except (TypeError, ValueError):
                pass
    return 0.0


def _extract_tools_from_event(event: dict[str, Any]) -> list[str]:
    tools: list[str] = []
    for key in ("tool_name", "toolName", "tool"):
        v = event.get(key)
        if isinstance(v, str) and v:
            tools.append(v)
    msg = event.get("message")
    if isinstance(msg, dict):
        content = msg.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    name = block.get("name")
                    if isinstance(name, str) and name:
                        tools.append(name)
    return tools


def summarize_events(task_id: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    tool_counts: dict[str, int] = {}
    turns = 0
    cost = 0.0
    conflict = False
    errors = 0

    for wrapper in events:
        event = wrapper.get("event", wrapper)
        if not isinstance(event, dict):
            continue
        event_str = json.dumps(event, ensure_ascii=True).lower()
        if "conflict" in event_str or "rebase" in event_str:
            conflict = True
        event_type = str(event.get("type", "")).lower()
        if "error" in event_type or event.get("error"):
            errors += 1
        if event_type in {"assistant_message", "assistant", "turn"}:
            turns += 1
        cost += _extract_cost_from_event(event)
        for tool in _extract_tools_from_event(event):
            tool_counts[tool] = tool_counts.get(tool, 0) + 1

    top_issue = "clean run"
    if conflict:
        top_issue = "merge/rebase conflict detected"
    elif errors > 0:
        top_issue = "runtime/tool errors detected"

    return {
        "task_id": task_id,
        "turns": turns,
        "cost": round(cost, 4),
        "tool_counts": tool_counts,
        "conflict": conflict,
        "errors": errors,
        "lesson": top_issue,
    }


def append_learning(
    learnings_path: Path,
    summary: dict[str, Any],
    *,
    commit_id: str | None,
    title: str | None = None,
    iterations: int | None = None,
    cost_override: float | None = None,
    dispatches: list[dict[str, Any]] | None = None,
) -> None:
    """Write a structured learning entry to LEARNINGS.md.

    The ``dispatches`` argument (from timeline.json) enriches the lesson with
    per-dispatch quality metrics: how many dispatches were unhealthy, how many
    had failing tests, and whether any produced a conflict.  These metrics give
    future workers concrete patterns to learn from rather than generic labels.
    """
    learnings_path.parent.mkdir(parents=True, exist_ok=True)
    heading = title or summary["task_id"]
    tool_str = ", ".join(
        f"{tool}({count})" for tool, count in sorted(summary["tool_counts"].items())
    )
    if not tool_str:
        tool_str = "none"
    cost_val = cost_override if cost_override is not None else summary["cost"]

    # Compute dispatch-level quality metrics from timeline dispatches.
    dispatch_count = len(dispatches) if dispatches else (iterations or 1)
    unhealthy_count = sum(1 for d in (dispatches or []) if not d.get("healthy", True))
    test_fail_count = sum(
        1 for d in (dispatches or []) if d.get("test_passed") is False
    )
    conflict = summary.get("conflict", False) or any(
        d.get("rebase_conflict") for d in (dispatches or [])
    )

    # Build a descriptive lesson string that is actionable for future workers.
    if unhealthy_count > 0 and test_fail_count > 0:
        lesson = (
            f"{unhealthy_count}/{dispatch_count} dispatches unhealthy (no tools); "
            f"{test_fail_count} dispatch(es) had test failures"
        )
    elif unhealthy_count > 0:
        lesson = f"{unhealthy_count}/{dispatch_count} dispatches unhealthy (no file-modifying tools used)"
    elif test_fail_count > 0:
        lesson = f"tests failed in {test_fail_count} dispatch(es) before final pass"
    elif conflict:
        lesson = "merge/rebase conflict encountered and resolved"
    elif summary.get("errors", 0) > 0:
        lesson = "runtime/tool errors detected"
    else:
        lesson = "clean run"

    lines = [
        f"## {summary['task_id']}: {heading} ({now_iso()[:10]})",
        f"- commit: {commit_id or 'n/a'}",
        f"- cost: ${cost_val:.4f}, {dispatch_count} dispatch(es), {summary['turns']} turns",
        f"- tools: {tool_str}",
        f"- conflict: {'yes' if conflict else 'none'}",
        f"- unhealthy_dispatches: {unhealthy_count}",
        f"- test_fail_dispatches: {test_fail_count}",
        f"- lesson: {lesson}",
        "",
    ]
    with learnings_path.open("a", encoding="utf-8") as file:
        file.write("\n".join(lines))


def extract_relevant_lessons(learnings_path: Path, task: dict[str, Any], max_items: int = 3) -> list[str]:
    if not learnings_path.exists():
        return []
    content = learnings_path.read_text(encoding="utf-8")
    sections = [section.strip() for section in content.split("\n## ") if section.strip()]
    task_text = f"{task.get('title', '')} {task.get('prompt', '')}".lower()
    scored: list[tuple[int, str]] = []
    for section in sections:
        normalized = section.lower()
        score = 0
        for token in re.findall(r"[a-z0-9_-]+", task_text):
            if len(token) > 3 and token in normalized:
                score += 1
        lesson_line = next((line for line in section.splitlines() if line.startswith("- lesson:")), "")
        if lesson_line:
            scored.append((score, lesson_line.replace("- lesson:", "").strip()))
    scored.sort(key=lambda item: item[0], reverse=True)
    lessons = [text for _, text in scored if text][:max_items]
    return lessons


def _fallback_rules_from_learnings(learnings_path: Path, max_rules: int = 5) -> list[str]:
    if not learnings_path.exists():
        return []
    lines = learnings_path.read_text(encoding="utf-8").splitlines()
    lesson_lines = [
        line.replace("- lesson:", "").strip()
        for line in lines
        if line.startswith("- lesson:")
    ]
    unique: list[str] = []
    for item in lesson_lines:
        if item and item not in unique:
            unique.append(item)
    return unique[:max_rules]


def reflect_rules_with_claude(repo_root: Path, learnings_path: Path, max_rules: int = 5) -> list[str]:
    if not learnings_path.exists():
        return []
    prompt = (
        "You are improving team execution rules from historical task learnings.\n"
        "Return concise actionable rules as JSON.\n\n"
        f"LEARNINGS.md content:\n{learnings_path.read_text(encoding='utf-8')[:24000]}"
    )
    schema = {
        "type": "object",
        "properties": {
            "rules": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["rules"],
    }
    command = [
        "npx",
        "claude",
        "-p",
        prompt,
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(schema, ensure_ascii=True),
        "--max-turns",
        "4",
    ]
    try:
        cp = subprocess.run(
            command,
            cwd=str(repo_root),
            text=True,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            timeout=300,
            check=True,
        )
        payload = json.loads(cp.stdout)
        rules = payload.get("rules", [])
        if isinstance(rules, list):
            return [str(rule).strip() for rule in rules if str(rule).strip()][:max_rules]
    except Exception:  # noqa: BLE001
        pass
    return _fallback_rules_from_learnings(learnings_path, max_rules=max_rules)


def update_claude_md_rules(claude_md_path: Path, rules: list[str]) -> None:
    if not claude_md_path.exists() or not rules:
        return
    content = claude_md_path.read_text(encoding="utf-8")
    marker = "## Learned Rules"
    if marker not in content:
        content = content.rstrip() + "\n\n## Learned Rules\n\n"
    before, _, _ = content.partition(marker)
    updated = before.rstrip() + f"\n\n{marker}\n\n"
    for rule in rules:
        updated += f"- {rule}\n"
    updated += "\n"
    claude_md_path.write_text(updated, encoding="utf-8")

