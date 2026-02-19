from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from subprocess import Popen
from typing import Any, TextIO

from manager.runtime import now_iso


@dataclass
class StreamSummary:
    task_id: str
    events: int = 0
    parse_errors: int = 0
    error_events: int = 0
    turns: int = 0
    estimated_cost_usd: float = 0.0
    tool_counts: dict[str, int] = field(default_factory=dict)


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:  # noqa: BLE001
        return 0.0


def _detect_tool_name(event: dict[str, Any]) -> str | None:
    for key in ("tool_name", "toolName", "tool"):
        value = event.get(key)
        if isinstance(value, str) and value:
            return value
    payload = event.get("payload")
    if isinstance(payload, dict):
        for key in ("tool_name", "toolName", "tool"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def _is_error_event(event: dict[str, Any]) -> bool:
    event_type = str(event.get("type", "")).lower()
    if "error" in event_type:
        return True
    for key in ("error", "is_error"):
        value = event.get(key)
        if value:
            return True
    return False


def _extract_turn_increment(event: dict[str, Any]) -> int:
    event_type = str(event.get("type", "")).lower()
    if event_type in {"assistant_message", "assistant", "turn"}:
        return 1
    return 0


def _extract_cost(event: dict[str, Any]) -> float:
    direct_cost = event.get("cost_usd")
    if direct_cost is not None:
        return _safe_float(direct_cost)
    usage = event.get("usage")
    if isinstance(usage, dict):
        for key in ("cost_usd", "usd", "cost"):
            if key in usage:
                return _safe_float(usage.get(key))
    return 0.0


def _write_jsonl_line(out: TextIO, record: dict[str, Any]) -> None:
    out.write(json.dumps(record, ensure_ascii=True) + "\n")
    out.flush()


def monitor_process(task_id: str, proc: Popen[str], logs_root: Path) -> StreamSummary:
    task_dir = logs_root / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    events_path = task_dir / "events.jsonl"
    stderr_path = task_dir / "stderr.log"

    summary = StreamSummary(task_id=task_id)

    with events_path.open("a", encoding="utf-8") as events_file:
        if proc.stdout is not None:
            for line in proc.stdout:
                line = line.rstrip("\n")
                if not line:
                    continue
                summary.events += 1
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    summary.parse_errors += 1
                    _write_jsonl_line(
                        events_file,
                        {
                            "ts": now_iso(),
                            "task_id": task_id,
                            "type": "non_json_line",
                            "raw": line,
                        },
                    )
                    continue

                if _is_error_event(event):
                    summary.error_events += 1
                summary.turns += _extract_turn_increment(event)
                summary.estimated_cost_usd += _extract_cost(event)

                tool_name = _detect_tool_name(event)
                if tool_name:
                    summary.tool_counts[tool_name] = summary.tool_counts.get(tool_name, 0) + 1

                _write_jsonl_line(
                    events_file,
                    {"ts": now_iso(), "task_id": task_id, "event": event},
                )

    stderr_output = ""
    if proc.stderr is not None:
        stderr_output = proc.stderr.read()
    if stderr_output:
        stderr_path.write_text(stderr_output, encoding="utf-8")

    return summary

