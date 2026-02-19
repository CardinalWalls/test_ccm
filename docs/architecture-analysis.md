# CCM Architecture Analysis

## What Was Designed

```
┌─────────────────────────────────────────────────────────┐
│  ccm CLI (Python)                                       │
│  ┌──────────┐  ┌──────────┐  ┌────────────┐            │
│  │ ccm add  │  │ ccm plan │  │  ccm run   │            │
│  └──────────┘  └──────────┘  └─────┬──────┘            │
│                                    │                    │
│  ┌─────────────────────────────────▼──────────────────┐ │
│  │  worker.py: execute_one_task()                     │ │
│  │                                                    │ │
│  │  1. claim task (atomic, from dev-tasks.json)       │ │
│  │  2. create worktree (git worktree add, symlinks)   │ │
│  │  3. dispatch Claude Code (npx claude -p ...)       │ │
│  │  4. commit                                         │ │
│  │  5. merge + test gate                              │ │
│  │  6. rebase + conflict resolution                   │ │
│  │  7. mark done                                      │ │
│  │  8. cleanup                                        │ │
│  │  9. learning accumulation                          │ │
│  └──────────────┬───────────────────┬─────────────────┘ │
│                 │                   │                    │
│  ┌──────────────▼──┐  ┌────────────▼──────────────┐    │
│  │ StreamSummary   │  │ TaskTimeline               │    │
│  │ (events, turns, │  │ (step timestamps,          │    │
│  │  tools, errors) │  │  iteration counters)       │    │
│  └─────────────────┘  └───────────────────────────┘    │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │ CLAUDE.md (in repo, read by Claude Code workers)  │  │
│  │ - 9-step lifecycle protocol                       │  │
│  │ - worktree architecture rules                     │  │
│  │ - conflict handling protocol                      │  │
│  │ - test failure protocol                           │  │
│  │ - commit conventions                              │  │
│  │ - learning loop directives                        │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │ LEARNINGS.md (closed loop)                        │  │
│  │ run → extract lessons → inject into next prompt   │  │
│  │ → ccm reflect → evolve CLAUDE.md Learned Rules    │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

The design assumes: **Claude Code workers will read CLAUDE.md, follow its protocols, use tools to implement code, run tests, and commit.** Every downstream component (StreamSummary feedback, timeline tracking, merge/rebase gate, learning loop, conflict protocol) depends on this assumption.

## What Actually Happened

### The dispatch

```python
command = [
    "npx", "claude", "-p", prompt,
    "--dangerously-skip-permissions",
    "--output-format", "stream-json", "--verbose",
    "--max-budget-usd", "1.00",
]
```

### The response (identical pattern, all 5 tasks)

```
Event 1: system.init  -- model=claude-sonnet-4, permissionMode=bypassPermissions, tools=[Bash,Read,Write,Edit,...]
Event 2: assistant     -- 1 text block, 0 tool_use blocks, stop_reason=None
Event 3: result        -- is_error=false, num_turns=1, cost=$0, stop_reason=None
```

Claude produced text ("I'll implement the modulo and clamp functions...") and was cut off before using any tools. `stop_reason: None` means the session ended abnormally -- not by Claude choosing to stop (`end_turn`), not by tool use (`tool_use`), not by turn limit (`max_turns`).

### The consequence

```
CLAUDE.md          → never read (Claude never called Read tool)
Worktree isolation → set up correctly, but no code executed inside it
Implementation     → 0 tools, 0 file changes, 0 test runs
_commit_task       → committed symlink layout artifacts (git-visible)
Merge/rebase       → succeeded vacuously (nothing to merge)
Timeline           → accurately recorded the phantom lifecycle
LEARNINGS.md       → "clean run, $0, 0 tools" (truthful but useless)
```

## Why CLAUDE.md Didn't Work

CLAUDE.md is a protocol document for Claude Code workers. It contains detailed instructions for the 9-step lifecycle, conflict handling, test failure recovery, and commit conventions. But it operates on a critical assumption:

**CLAUDE.md only works if Claude Code reads it.** Claude Code reads CLAUDE.md automatically when it starts in a directory that contains one. But "reads" means the content is loaded into context -- Claude still needs to actually use tools to follow the instructions.

In this run, Claude never got past step 0. The dispatch produced a single text response and the session ended. CLAUDE.md was loaded into context but Claude never executed against it.

### Root cause: the dispatch produced 1 turn with `stop_reason: None`

The `stop_reason: None` across all 5 tasks points to a systemic issue with how `npx claude -p` was invoked. Possible causes:

1. **`--max-budget-usd 1.00` may be too low or mis-handled.** If Claude Code's budget tracker pre-empts the response before tool_use blocks are emitted, the session ends with only the text prefix captured. The `total_cost_usd: 0` in all results suggests cost tracking isn't working (Kiro account pool may not report cost), which could confuse the budget enforcer.

2. **Stream-json output may lose tool_use events.** If the model response included tool_use content blocks that were dropped during stream serialization, the session would appear text-only.

3. **Model behavior with large context.** The prompt includes the full task description + approved plan JSON. Combined with CLAUDE.md auto-loaded, the context may be large enough that the model generates a planning response before committing to tool calls, and the session terminates before the second turn.

4. **No `--max-turns` specified.** The dispatch command doesn't set `--max-turns`. Best-practice examples in `docs/best-practice.md` use `--max-turns 6` for plan mode. Without it, Claude Code may use a default that interacts poorly with the budget or session handling.

## Where Each Architectural Layer Failed

### Layer 1: Dispatch (dispatcher.py)

**Design**: Send prompt to Claude Code, get streaming events back, return (exit_code, StreamSummary).

**Reality**: Claude Code returned exit code 0 after a single text-only turn. The dispatch layer faithfully reported what happened but had no mechanism to distinguish "Claude worked" from "Claude said something and stopped."

**Gap**: The dispatch layer treats any non-error exit as success. It doesn't validate that the worker actually engaged with the task (read files, edited code, ran commands).

### Layer 2: Health check (StreamSummary)

**Design**: `StreamSummary` tracks `events`, `error_events`, `turns`, `tool_counts`, `estimated_cost_usd`.

**Reality**: Summary correctly showed: events=3, error_events=0, turns=1, tool_counts={}, cost=$0. All the data needed to detect "no work done" was present.

**Gap (now fixed)**: `is_healthy` didn't check `tool_counts`. A text-only turn with no tools was considered healthy. Fixed to require non-empty `tool_counts`.

### Layer 3: Implementation loop (worker.py)

**Design**: Dispatch Claude, check rc + tests, retry up to 3 times.

**Reality**: `rc == 0` (Claude exited cleanly) and `_run_tests()` passed (existing tests from main). Success on first iteration.

**Gap (now fixed)**: Loop didn't check `_summary.is_healthy`. Fixed to gate on `rc == 0 AND is_healthy AND _run_tests`.

### Layer 4: Commit validation (_commit_task)

**Design**: `git add -A && git commit` if `git status --porcelain` shows changes.

**Reality**: Worktree layout setup created symlinks that appeared as changes. Committed symlink artifacts.

**Gap (now fixed)**: Layout artifacts not excluded from git. Fixed with `.git/info/exclude`.

### Layer 5: CLAUDE.md protocols

**Design**: Claude Code workers read CLAUDE.md and follow the 9-step lifecycle, conflict handling, test failure recovery, etc.

**Reality**: Claude Code loaded CLAUDE.md into context but never acted on it. The session ended after 1 text turn.

**Gap**: CLAUDE.md is a passive document. It relies entirely on the worker executing multiple turns with tool use. If the worker doesn't execute, CLAUDE.md is dead weight. There is no mechanism to verify that the worker read and followed CLAUDE.md.

### Layer 6: Learning loop (LEARNINGS.md)

**Design**: Capture lessons from each task, inject into future prompts, evolve CLAUDE.md via `ccm reflect`.

**Reality**: Lessons captured were "clean run, $0, 0 tools" -- technically accurate but content-free. The learning loop faithfully processed garbage in and produced garbage out.

**Gap**: Learning extraction doesn't distinguish "clean run because task was easy" from "clean run because nothing happened."

## Comparison with best-practice.md

`docs/best-practice.md` (lines 16-35) shows a working Python subprocess dispatch example:

```python
cmd = [
    "claude", "-p", "Read TASK.md and return a plan as JSON matching the schema.",
    "--permission-mode", "plan",
    "--tools", "Read,Grep,Glob",
    "--json-schema", json.dumps({...}),
    "--output-format", "json",
    "--max-turns", "6"
]
```

Key differences from our dispatch:

| Parameter | best-practice.md | Our dispatcher |
|---|---|---|
| `--max-turns` | `6` (explicit) | not set |
| `--tools` / `--allowedTools` | explicit tool whitelist | not set (uses all) |
| `--output-format` | `json` (for plan) | `stream-json` (always) |
| `--max-budget-usd` | not set | `1.00` |
| `--permission-mode` | `plan` (for planning) | not set (`bypassPermissions` via `--dangerously-skip-permissions`) |

The best-practice example explicitly sets `--max-turns 6`, which guarantees Claude Code will attempt multiple turns. Our dispatch doesn't set this, leaving it to the default, which combined with `--max-budget-usd 1.00` may cause premature session termination.

## What Needs to Change

The architecture has two classes of problems:

### Class A: The dispatch doesn't produce work

This is the root cause. If Claude Code doesn't execute tools, everything else is irrelevant. Possible fixes:

1. **Add `--max-turns`** to the dispatch command. Without it, budget limits or model behavior can terminate the session after 1 turn.

2. **Remove or increase `--max-budget-usd`**. $1 may be too low for multi-turn implementation tasks. Or the Kiro account pool's $0 cost reporting confuses the budget enforcer.

3. **Validate dispatch output before proceeding.** The `is_healthy` fix helps, but the root cause is the dispatch itself, not the health check.

4. **Investigate `stop_reason: None`.** This abnormal termination across all 5 tasks suggests a systematic issue with the CLI invocation, not a model behavior issue. Need to test with explicit `--max-turns` and without `--max-budget-usd` to isolate the cause.

### Class B: Downstream layers don't enforce contracts

These are the feedback loop gaps (mostly fixed):

- StreamSummary `is_healthy` now requires tool use
- Layout artifacts excluded from git
- `_commit_task` return value guarded
- `DispatchError` raised on API death

### Class C: CLAUDE.md is passive

CLAUDE.md assumes Claude will read and follow it. There's no enforcement mechanism. If Claude doesn't execute, CLAUDE.md is inert.

Possible approaches:
- Make the worker prompt explicitly reference key CLAUDE.md sections instead of just "follow it strictly"
- Use a stop hook (`.claude/settings.json` TaskCompleted) that verifies CLAUDE.md compliance
- Split CLAUDE.md into machine-enforceable rules (checked by the manager) and worker guidelines (for Claude)

## Open Questions

1. What does `stop_reason: None` mean in Claude Code `stream-json` output? Is it a budget termination, a stream error, or expected behavior for text-only responses?

2. Does `--max-budget-usd` interact with `total_cost_usd: 0` (Kiro pool not reporting cost)? Could the budget enforcer abort when it can't verify remaining budget?

3. Would adding `--max-turns 10` alone fix the 1-turn problem, or is the root cause deeper?

4. Should the dispatcher retry with different parameters when it detects a 1-turn text-only response, or should the architecture not depend on Claude Code being reliable?

## Redesign Decisions (Implemented)

The manager now enforces the lifecycle contract directly, instead of assuming a successful exit code means useful work happened.

1. **Dispatch flags now prioritize completion over budget ceilings**
   - Removed `--max-budget-usd` from worker dispatch.
   - Added explicit `--max-turns`:
     - implementation dispatch: `50`
     - repair/conflict dispatch: `20`
   - Token counts are captured for audit, not used to terminate execution.

2. **Manager review loop replaces fixed retry counters**
   - Removed fixed retry ceilings from implementation and merge/rebase loops.
   - Worker now re-dispatches based on `StreamSummary` outcomes:
     - unhealthy/no-tool dispatches -> re-dispatch
     - tests failing after a healthy dispatch -> re-dispatch
     - merge or rebase problems -> repair dispatch and continue
   - Terminal task failure is now restricted to:
     - API-level dead dispatch (`DispatchError`)
     - wall-clock timeout (`TASK_WALL_CLOCK_TIMEOUT`)

3. **Per-dispatch audit is now first-class**
   - `StreamSummary` now tracks `input_tokens` and `output_tokens`.
   - `timeline.json` now records each dispatch with:
     - stage
     - return code
     - health
     - turns/events/errors
     - token usage
     - tool counts

4. **PR lifecycle no longer auto-closes review work**
   - Removed remote branch deletion from worker `finally`.
   - Added `ccm cleanup` command so branch deletion happens only after review.

5. **Stop hook includes recursion guard**
   - The hook now checks `stop_hook_active` from stdin payload.
   - If active, it allows stop to avoid hook recursion.
   - Otherwise it enforces test gate (`exit 2` blocks stop when tests fail).

## Question Resolution

- **"Never set budget"**: adopted. Budget limit was removed from dispatch control.
- **"Context auto-summary matters for audit"**: adopted. Dispatch-level token data is now recorded in timeline audit logs.
- **"Where is manager review for CLAUDE.md protocol?"**: implemented in `worker.py` as summary-driven re-dispatch logic plus timeout/API-dead terminal gates.
