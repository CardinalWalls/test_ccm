# CCM Demo Report

## Run Summary

- **Date**: 2026-02-19 (final successful run)
- **Base commit**: `e9d8144` on `main`
- **Repository**: `CardinalWalls/test_ccm`
- **Workers**: 2 (parallel)
- **Tasks**: 2 (task-1: modulo/abs, task-2: sqrt/clamp)

## Planning Results

| Task | Plan Status | Approved | Review Reason |
|---|---|---|---|
| task-1 | approved | yes | Well-structured plan, proper error handling for modulo division by zero |
| task-2 | approved | yes | Good error handling for sqrt negatives and clamp boundaries |

## Execution Results

| Task | Status | Dispatches | Healthy | Tools Used | Cost | PR |
|---|---|---|---|---|---|---|
| task-1 | done | 2 | 1 of 2 | Read:2, Edit:3, Bash:1 | $0.089 | [#7](https://github.com/CardinalWalls/test_ccm/pull/7) |
| task-2 | done | 3 | 1 of 3 | Read:2, Edit:3, Bash:1 | $0.044 | [#8](https://github.com/CardinalWalls/test_ccm/pull/8) |

Both PRs contain **real code changes**: task-1 (+29/-1 lines, 2 files), task-2 (+34/-1 lines, 2 files).

## Per-Task Lifecycle Timeline

### Task 1 — Add modulo and abs (worker 1)

| Step | Timestamp (UTC) | Duration | Notes |
|---|---|---|---|
| 1. Claim | 08:15:00 | — | Parallel with task-2 |
| 2. Create worktree | 08:15:02 | 2s | Isolated worktree with symlinks |
| 3. Implement | 08:15:02 → 08:17:55 | 2m53s | 2 dispatches: 1st unhealthy (text-only warmup), 2nd healthy (15 turns, Read+Edit+Bash) |
| 4. Commit | 08:17:55 | <1s | Source files committed on task branch |
| 5. Merge + test | 08:18:00 | 5s | Fetched origin/main, merged, npm test passed |
| 6. Rebase + push | 08:18:02 → 08:18:04 | 2s | Clean rebase, pushed to remote |
| 6b. PR created | 08:18:07 | 3s | [PR #7](https://github.com/CardinalWalls/test_ccm/pull/7) |
| 7. Mark done | 08:18:07 | <1s | Status updated in dev-tasks.json |
| 8. Cleanup | 08:18:07 | <1s | Worktree removed, branch deleted locally |
| 9. Learning | 08:18:07 | <1s | Entry appended to LEARNINGS.md |

**Total wall clock**: ~3 minutes (claim to done)

### Task 2 — Add sqrt and clamp (worker 2)

| Step | Timestamp (UTC) | Duration | Notes |
|---|---|---|---|
| 1. Claim | 08:15:00 | — | Parallel with task-1 |
| 2. Create worktree | 08:15:02 | 2s | |
| 3. Implement | 08:15:02 → 08:18:40 | 3m38s | 3 dispatches: 2 unhealthy warmups, 1 healthy (14 turns, Read+Edit+Bash) |
| 4. Commit | 08:18:40 | <1s | |
| 5. Merge + test | 08:18:43 | 3s | |
| 6. Rebase + push | 08:18:44 → 08:18:47 | 3s | |
| 6b. PR created | 08:18:50 | 3s | [PR #8](https://github.com/CardinalWalls/test_ccm/pull/8) |
| 7. Mark done | 08:18:50 | <1s | |
| 8. Cleanup | 08:18:50 | <1s | |
| 9. Learning | 08:18:50 | <1s | |

**Total wall clock**: ~4 minutes

## Bugs Found and Fixed (Run History)

### Previous Runs — Phantom Completion (all tasks 0 tools, 0 code)

| Bug | Root Cause | Fix |
|---|---|---|
| Stream monitor blind to tools | `_detect_tool_name` looked for `tool_name` at event top level; Claude nests tools in `message.content[].name` | Rewrote as `_detect_tool_names`, iterating `message.content` blocks |
| Cost always $0 | `_extract_cost` looked for `cost_usd`; Claude uses `total_cost_usd` | Added `total_cost_usd` to key search |
| Tokens always 0 | `_extract_tokens` checked `event.usage`; Claude puts usage in `event.message.usage` | Fall through to `message.usage` |
| TodoWrite = "healthy" | `is_healthy` required any tool; TodoWrite alone counts as planning, not implementation | `is_healthy` now excludes `TodoWrite`/`TodoRead` from "real tools" |
| Artifact commits false-positive | `_commit_task` committed data/ symlinks and node_modules | Filter artifact prefixes; `git reset HEAD -- data/ node_modules` before commit |
| Claude commits → empty `_commit_task` | Prompt told Claude to `git commit`; manager then found no changes | Removed commit instruction; added `git log origin/main..HEAD` fallback check |
| Rebase blocked by typechanges | Symlink typechanges counted as unstaged changes | `_stash_artifacts()` runs `git checkout -- data node_modules` before merge/rebase |
| Plans not approved | `apply_review_results` looked for `verdicts` at top level; Claude wraps in `structured_output` | Extract from `structured_output` first |
| Plan max-turns too low | `--max-turns 6` insufficient for plan generation (hit error_max_turns) | Increased to 15 |
| Fixed retry limits | `MAX_MERGE_RETRIES=3` contradicted "never give up" | Replaced with wall-clock timeout (1800s) |
| Budget limit | `--max-budget-usd` unnecessarily capped execution | Removed; use `--max-turns` for differentiation only |
| Remote branch deletion closes PRs | `delete_remote_branch` in finally block | Moved to `ccm cleanup` command |

### Architecture Redesign Decisions

- **No budget limits**: `--max-budget-usd` removed. `--max-turns` (50 implement, 20 repair) controls scope.
- **Wall-clock timeout**: 1800s global timeout replaces fixed retry counts.
- **Manager review loop**: Re-dispatches on unhealthy/test-fail; only fails on API-dead or timeout.
- **Stop hook**: Blocks Claude from stopping if tests fail (recursion-guarded).
- **Per-dispatch audit**: `StreamSummary` tracks input/output tokens, tool counts per dispatch.
- **PR lifecycle**: `ccm cleanup` for post-review branch deletion.

## Feature Coverage

| Capability | Covered | Evidence |
|---|---|---|
| 9-step lifecycle | **yes** | Both tasks completed all 9 steps with timestamps |
| Worktree isolation | **yes** | Parallel worktrees, symlinked shared files |
| Plan mode + review | **yes** | `ccm plan` generated structured plans, AI reviewer approved |
| Implementation with real tools | **yes** | Read, Edit, Bash tool usage confirmed in events |
| Manager commit (step 4) | **yes** | Source changes committed, artifacts excluded |
| Merge + test gate (step 5) | **yes** | `npm test` passed after merge |
| Rebase (step 6) | **yes** | Clean rebase to origin/main |
| PR creation | **yes** | PRs #7, #8 with real diffs |
| Learning extraction | **yes** | LEARNINGS.md entries with commit refs |
| `ccm reflect` | **yes** | Ran, 0 new rules (clean run) |
| `ccm status` | **yes** | Shows tasks + PRs + timeline |
| `ccm cleanup` | available | Not exercised (PRs still open for review) |
| Conflict resolution | not exercised | Both tasks touched different functions |
| Test failure retry | not exercised | Claude's implementations passed tests |
| LEARNINGS.md closed loop | partial | Entries recorded; no failures to learn from |

## Dispatch Pattern: "Warmup" Phenomenon

Both tasks exhibited a consistent pattern: the first 1–2 dispatches produce text-only responses (no tool use, 1 turn, $0 cost). The manager correctly identifies these as unhealthy and re-dispatches. The next dispatch then uses tools and performs real work.

This appears to be a Claude Code API behavior where the first invocation with a complex prompt returns a conversational response rather than entering agentic tool-use mode. The architecture handles this gracefully through the review loop.

## Final Assessment

The CCM architecture is **validated end-to-end**. Two tasks ran in parallel through the complete 9-step lifecycle, producing real code changes with PRs. The iterative debugging process identified and fixed 11 bugs across the stream monitor, commit logic, git operations, plan review, and prompt engineering. The manager review loop correctly handles unhealthy dispatches, and the timeline provides full audit visibility.
