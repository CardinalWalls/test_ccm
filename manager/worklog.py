"""Generate docs/architecture-worklog.md from plan/log/events/learnings artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_json(p: Path) -> dict[str, Any] | list[Any] | None:
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _load_events(p: Path) -> list[dict[str, Any]]:
    if not p.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def _safe(d: dict[str, Any] | None, *keys: str, default: str = "") -> str:
    if d is None:
        return default
    for k in keys:
        if k in d and d[k] is not None:
            return str(d[k])
    return default


def generate_worklog(paths: Any) -> str:
    """Generate architecture work log markdown from artifacts."""
    lines: list[str] = []
    lines.append("# Architecture Work Log")
    lines.append("")
    lines.append("This document traces the CCM architecture's decision-making with cited evidence.")
    lines.append("")

    plans_dir = paths.plans_dir
    logs_dir = paths.logs_dir
    learnings_path = paths.learnings_path

    # Section 1: Plan Generation and Review
    lines.append("## 1. Plan Generation and Review")
    lines.append("")
    plan_files = sorted(plans_dir.glob("*.json")) if plans_dir.exists() else []
    for pf in plan_files:
        plan = _load_json(pf)
        if not isinstance(plan, dict):
            continue
        task_id = _safe(plan, "task_id")
        status = _safe(plan, "status")
        approved = plan.get("approved", False)
        reason = _safe(plan, "review_reason")
        plan_data = plan.get("plan", {})
        if isinstance(plan_data, dict):
            so = plan_data.get("structured_output", plan_data)
            steps = so.get("steps", []) if isinstance(so, dict) else []
            acceptance = so.get("acceptance", []) if isinstance(so, dict) else []
            risks = so.get("risks", []) if isinstance(so, dict) else []
        else:
            steps, acceptance, risks = [], [], []

        lines.append(f"### {task_id}")
        lines.append(f"- **Status**: {status} | **Approved**: {bool(approved)}")
        lines.append(f"- **Review reason**: {reason}")
        if steps:
            lines.append("- **Steps**:")
            for s in steps[:8]:
                lines.append(f"  - {s}")
            if len(steps) > 8:
                lines.append(f"  - ... ({len(steps) - 8} more)")
        if acceptance:
            lines.append("- **Acceptance**:")
            for a in acceptance[:5]:
                lines.append(f"  - {a}")
        if risks:
            lines.append("- **Risks**: " + ", ".join(str(r) for r in risks[:3]))
        lines.append("")

    # Section 2: Dispatch Flow per Task
    lines.append("## 2. Dispatch Flow per Task")
    lines.append("")
    timeline_files = sorted(logs_dir.glob("*/timeline.json")) if logs_dir.exists() else []
    for tf in timeline_files:
        task_id = tf.parent.name
        tl = _load_json(tf)
        if not isinstance(tl, dict):
            continue
        dispatches = tl.get("dispatches", [])
        counters = tl.get("counters", {})
        merge_attempts = tl.get("merge_attempts", [])
        rebase_attempts = tl.get("rebase_attempts", [])

        lines.append(f"### {task_id}")
        lines.append(f"- **Iterations**: {counters.get('step3_iterations', 0)}")
        lines.append(f"- **Merge/rebase attempts**: {counters.get('step5_6_attempts', 0)}")
        lines.append(f"- **Conflicts**: {counters.get('step6_conflicts', 0)}")
        lines.append("")
        for i, d in enumerate(dispatches):
            stage = d.get("stage", "?")
            healthy = d.get("healthy", False)
            rc = d.get("return_code", "?")
            tools = d.get("tool_counts", {})
            turns = d.get("turns", 0)
            cost = d.get("estimated_cost_usd", 0)
            prompt_preview = d.get("prompt_preview", "")
            test_passed = d.get("test_passed")
            test_output = d.get("test_output", "")
            commit_hash = d.get("commit_hash")
            commit_files = d.get("commit_files", [])

            lines.append(f"#### Dispatch {i + 1}: {stage}")
            lines.append(f"- **Healthy**: {healthy} | **rc**: {rc} | **turns**: {turns} | **cost**: ${cost:.4f}")
            lines.append(f"- **Tools**: {tools}")
            if prompt_preview:
                lines.append(f"- **Prompt preview**: `{prompt_preview[:100]}...`")
            if test_passed is not None:
                lines.append(f"- **Tests passed**: {test_passed}")
                if test_output and not test_passed:
                    lines.append(f"- **Test output (excerpt)**: ```")
                    lines.append(test_output[:500].replace("```", "`"))
                    lines.append("```")
            if commit_hash:
                lines.append(f"- **Commit**: `{commit_hash}` ({', '.join(commit_files[:5])})")
            lines.append("")

        if merge_attempts:
            lines.append("**Merge attempts**:")
            for j, m in enumerate(merge_attempts):
                lines.append(f"- Attempt {j + 1}: passed={m.get('passed')}")
                out = m.get("output", "")
                if out and not m.get("passed"):
                    lines.append(f"  ```\n  {out[:300]}...\n  ```")
            lines.append("")

        if rebase_attempts:
            lines.append("**Rebase attempts**:")
            for j, r in enumerate(rebase_attempts):
                lines.append(f"- Attempt {j + 1}: passed={r.get('passed')}, conflict={r.get('conflict')}")
                out = r.get("output", "")
                if out and not r.get("passed"):
                    lines.append(f"  ```\n  {out[:300]}...\n  ```")
            lines.append("")

    # Section 3: Ralph Loop Conditions Exercised
    lines.append("## 3. Ralph Loop Conditions Exercised")
    lines.append("")
    lines.append("| Task | Re-dispatch (unhealthy) | Re-dispatch (test fail) | Re-dispatch (empty commit) | Conflict resolution | Merge/test repair |")
    lines.append("|------|-------------------------|-------------------------|----------------------------|--------------------|-------------------|")
    for tf in timeline_files:
        task_id = tf.parent.name
        tl = _load_json(tf)
        if not isinstance(tl, dict):
            continue
        dispatches = tl.get("dispatches", [])
        unhealthy = sum(1 for d in dispatches if not d.get("healthy", True))
        test_fail = sum(1 for d in dispatches if d.get("test_passed") is False)
        empty_commits = tl.get("counters", {}).get("step4_empty_commits", 0)
        conflicts = tl.get("counters", {}).get("step6_conflicts", 0)
        repair_merge = sum(1 for d in dispatches if d.get("stage") == "step5_repair_merge_or_test")
        repair_rebase = sum(1 for d in dispatches if d.get("stage") == "step6_repair_after_failed_rebase")
        resolve_conflict = sum(1 for d in dispatches if d.get("stage") == "step6_resolve_rebase_conflict")

        lines.append(f"| {task_id} | {unhealthy} | {test_fail} | {empty_commits} | {resolve_conflict} | {repair_merge + repair_rebase} |")
    lines.append("")

    # Section 4: Merge/Rebase Evidence
    lines.append("## 4. Merge/Rebase Evidence")
    lines.append("")
    for tf in timeline_files:
        task_id = tf.parent.name
        tl = _load_json(tf)
        if not isinstance(tl, dict):
            continue
        rebase_attempts = tl.get("rebase_attempts", [])
        if rebase_attempts:
            lines.append(f"### {task_id}")
            for j, r in enumerate(rebase_attempts):
                lines.append(f"- Attempt {j + 1}: passed={r.get('passed')}, conflict={r.get('conflict')}")
                out = r.get("output", "")
                if out:
                    lines.append(f"  Output:\n  ```\n  {out[:800]}\n  ```")
            lines.append("")

    # Section 5: Learning Loop Evidence
    lines.append("## 5. Learning Loop Evidence")
    lines.append("")
    if learnings_path.exists():
        content = learnings_path.read_text(encoding="utf-8")
        lines.append("### LEARNINGS.md (excerpt)")
        lines.append("```")
        lines.append(content[:3000])
        if len(content) > 3000:
            lines.append("... (truncated)")
        lines.append("```")
    else:
        lines.append("No LEARNINGS.md found.")
    lines.append("")

    # Section 6: Full Lifecycle Waterfall
    lines.append("## 6. Full Lifecycle Waterfall")
    lines.append("")
    lines.append("| Task | Step 1 | Step 2 | Step 3 done | Step 4 | Step 5 | Step 6 | Step 7 | Step 8 | Step 9 | Cost |")
    lines.append("|------|--------|--------|-------------|--------|--------|--------|--------|--------|--------|------|")
    for tf in timeline_files:
        task_id = tf.parent.name
        tl = _load_json(tf)
        if not isinstance(tl, dict):
            continue
        steps = tl.get("step_timestamps", {})
        total_cost = sum(d.get("estimated_cost_usd", 0) for d in tl.get("dispatches", []))
        s1 = steps.get("step1_claimed", "-")[:19] if steps.get("step1_claimed") else "-"
        s2 = steps.get("step2_worktree_created", "-")[:19] if steps.get("step2_worktree_created") else "-"
        s3 = steps.get("step3_implement_done", "-")[:19] if steps.get("step3_implement_done") else "-"
        s4 = steps.get("step4_committed", "-")[:19] if steps.get("step4_committed") else "-"
        s5 = steps.get("step5_merge_test_passed", "-")[:19] if steps.get("step5_merge_test_passed") else "-"
        s6 = steps.get("step6_pr_created", "-")[:19] if steps.get("step6_pr_created") else "-"
        s7 = steps.get("step7_marked_done", "-")[:19] if steps.get("step7_marked_done") else "-"
        s8 = steps.get("step8_cleaned", "-")[:19] if steps.get("step8_cleaned") else "-"
        s9 = steps.get("step9_learning_recorded", "-")[:19] if steps.get("step9_learning_recorded") else "-"
        lines.append(f"| {task_id} | {s1} | {s2} | {s3} | {s4} | {s5} | {s6} | {s7} | {s8} | {s9} | ${total_cost:.2f} |")
    lines.append("")

    return "\n".join(lines)
