# CCM Demo Report

## Run Summary (Full Feature Exercise)

- **Date**: 2026-02-19
- **Base commit**: `44f0df8` on `main`
- **Repository**: `CardinalWalls/test_ccm`
- **Round 1**: 2 workers (task-1 conflict-alpha, task-2 conflict-beta, task-3 forced-test-fail)
- **Round 2**: 1 worker (task-4 learning-consumer, task-5 clean-baseline)
- **Architecture Work Log**: `docs/architecture-worklog.md`

## Planning Results

| Task | Plan Status | Approved | Review Reason |
|---|---|---|---|
| task-1 | approved | yes | conflict-alpha: modulo + divide change; conflicts with task-2 |
| task-2 | approved | yes | conflict-beta: remainder + divide change |
| task-3 | approved | yes | forced-test-fail: greet change; manually approved |
| task-4 | approved | yes | learning-consumer: truncate, padLeft |
| task-5 | approved | yes | clean-baseline: date-utils |

## Execution Results

| Task | Status | Dispatches | Cost | PR |
|---|---|---|---|---|
| task-1 | failed | 35 | $0.32 | — |
| task-2 | done | 2 | $0.12 | [#9](https://github.com/CardinalWalls/test_ccm/pull/9) |
| task-3 | done | 1 | $0.03 | [#10](https://github.com/CardinalWalls/test_ccm/pull/10) |
| task-4 | done | 13 | $0.06 | [#12](https://github.com/CardinalWalls/test_ccm/pull/12) |
| task-5 | done | 4 | $0.08 | [#11](https://github.com/CardinalWalls/test_ccm/pull/11) |

**Evidence trace**: Full per-dispatch flow, merge/rebase records, and learning loop details are in `docs/architecture-worklog.md`.

## Per-Task Lifecycle Timeline

Detailed step-level timelines with dispatches, test output, merge/rebase logs, and commit hashes are in **docs/architecture-worklog.md** (Section 6: Full Lifecycle Waterfall).

Summary:
- **task-2** (conflict-beta): 2 workers parallel; first to merge; clean rebase.
- **task-3** (forced-test-fail): test retry loop exercised; greet changed, tests updated, passed.
- **task-1** (conflict-alpha): 29+ dispatches; Ralph loop on repeated test failures; manually failed.
- **task-5** (clean-baseline): clean run; date-utils added.
- **task-4** (learning-consumer): truncate/padLeft; LEARNINGS.md injected; completed.

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
| 9-step lifecycle | **yes** | tasks 2, 3, 4, 5 completed; timelines in architecture-worklog |
| Worktree isolation | **yes** | Parallel worktrees (round 1), symlinked shared files |
| Plan mode + review | **yes** | 5 plans generated, AI reviewer approved; plans/*.json |
| Implementation with real tools | **yes** | Read, Edit, Bash, Write, Glob in events |
| Manager commit (step 4) | **yes** | commit_hash, commit_files in timeline dispatches |
| Merge + test gate (step 5) | **yes** | merge_attempts, test_output in timeline |
| Rebase (step 6) | **yes** | rebase_attempts, rebase_conflict in timeline |
| PR creation | **yes** | PRs #9, #10, #11, #12 |
| Learning extraction | **yes** | LEARNINGS.md with cost, tools, lessons from all tasks |
| `ccm worklog` | **yes** | docs/architecture-worklog.md from plans/logs/events/learnings |
| `ccm reflect` | **yes** | Ran; CLAUDE.md rules |
| `ccm status` | **yes** | Tasks + PRs + timeline per task |
| Conflict resolution | **partial** | task-2 merged first; task-1 failed before rebase (different order) |
| Test failure retry | **yes** | task-3 forced-test-fail; test retry loop exercised |
| LEARNINGS.md closed loop | **yes** | task-4 (learning-consumer) prompt injected with lessons |

## Dispatch Pattern: "Warmup" Phenomenon

Early dispatches can produce text-only responses (no tool use, 1 turn, $0 cost). The manager identifies these as unhealthy and re-dispatches. The architecture handles this through the review loop.

## Final Assessment

The Full Feature Exercise validated the architecture end-to-end:

- **Manager logging**: Test output, git merge/rebase results, and commit hashes are recorded in timeline dispatches.
- **Experience extraction**: Tool names and cost correctly extracted from stream-monitor events.
- **`ccm worklog`**: Generates `docs/architecture-worklog.md` with plan review, dispatch flow, merge/rebase evidence, learning loop, and lifecycle waterfall.
- **Conflict pair**: task-1/task-2 both modified `divide()`; task-2 merged first; task-1 failed on tests before rebase (Ralph loop exercised).
- **Test retry**: task-3 (forced-test-fail) exercised the test-failure re-dispatch path.
- **Learning loop**: task-4 (learning-consumer) received LEARNINGS.md injections; task-5 demonstrated clean baseline.
