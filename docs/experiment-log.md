# CCM Experiment Log

This file records each experiment iteration in H/V/R/C format:
- **H** (Hypothesis): what we expected this configuration to prove
- **V** (Variables): configuration choices made for this run
- **R** (Results): what `scripts/verify.sh` and timeline evidence showed
- **C** (Conclusions + next hypotheses): what we learned and what to change

---

## Experiment 1 — 2026-02-19

### H: Hypotheses

1. The CCM architecture (plan farm → worktrees → manager review loop → LEARNINGS) can execute 5 tasks end-to-end, including deliberate merge conflict (tasks 1+2) and forced test failure (task 3).
2. The Stop hook will block Claude from stopping until tests pass, making task 3 exercise the retry loop.
3. LEARNINGS.md will accumulate meaningful lessons from round 1, and tasks 4+5 will receive injected lessons.
4. `ccm reflect` will distill lessons into actionable rules in CLAUDE.md.

### V: Configuration Variables

| Variable | Value |
|---|---|
| Workers (round 1) | 2 |
| Workers (round 2) | 1 |
| `--max-turns` (implement) | 50 |
| `--max-turns` (repair) | 20 |
| Stop hook type | `TaskCompleted` (wrong) |
| Worktree path formula | `worktree_root / f"task-{task_id}"` (double-prefix bug) |
| Conflict pair files | both modify `src/math.ts` `divide()` |
| Forced-test-fail design | Claude changes impl + test simultaneously |
| `is_api_error` logic | `and not self.tool_counts` (correct) |

### R: Results

`scripts/verify.sh` output (run post-experiment):

| Check | Result | Evidence |
|---|---|---|
| [1] Plan farm | **PASS** | 5/5 tasks approved with plan_reason in `plans/*.json` |
| [2] Worktree isolation | **PASS** | 5/5 tasks have `step2_worktree_created` in timeline |
| [3] Stop hook fires | **PASS** (accidental) | task-1 had `test_passed=false` dispatches — but this was from repeated unhealthy dispatches (28/35 had 0 tools), not the Stop hook |
| [4] Conflict detection | **FAIL** | No `rebase_attempts[].conflict=true` in any timeline; task-1 failed before rebase due to worktree path bug `task-task-1` |
| [5] Conflict resolution | WARN (skipped) | Depends on check 4 |
| [6] LEARNINGS injection | **FAIL** | `extract_relevant_lessons` returned empty for all tasks; lessons were "clean run" / not keyword-matched |
| [7] ccm reflect | **PASS** | `CLAUDE.md` has content under `## Learned Rules` |
| [8] Token audit | **PASS** | 55 dispatches all have `input_tokens > 0` |
| [9] Cost sanity | **PASS** | Total cost $0.61 |

**Score: 6/9 pass (2 fail, 1 warn)**

#### Key observations

**task-1 (conflict-alpha)**
- 35 dispatches total; 28 were unhealthy (0 file-modifying tools)
- After worktree path bug was introduced (`task-task-1` instead of `task-1`), cleanup failed: `"reason": "unexpected-manager-error: [Errno 2] No such file or directory: '.../task-task-1'"`
- Claude did eventually work (7 healthy dispatches, 5 with `test_passed: False`), but tests never passed — likely because the implementation was attempting to add `Number.isFinite()` check to `divide()` which had race conditions with task-2 already having modified that function

**task-2 (conflict-beta)**
- Completed cleanly: 2 dispatches, both healthy, tests passed. PR #9 created.
- Merged first, so no rebase conflict triggered for task-2 itself.

**task-3 (forced-test-fail)**
- `step3_iterations: 1` — no retry. Claude updated both `src/greet.ts` and `tests/greet.test.ts` simultaneously, bypassing the intended test-failure scenario.
- Root cause: no frozen test protection. Claude can modify test files.

**LEARNINGS injection**
- `extract_relevant_lessons()` uses keyword matching between task text and lesson text.
- All lessons were "clean run" or generic — no keyword overlap with task-4/5 prompts.
- Result: injection returned empty list for all tasks.

### C: Conclusions and Next Iteration Hypotheses

#### What we proved works

- Plan farm: parallel `ccm plan --workers 3` generates structured plans + manager Claude review
- Worktree isolation: each task gets its own branch, `data/` symlinks, `node_modules` symlink
- Manager review loop: unhealthy dispatches (0 tools) are detected and re-dispatched automatically
- Token audit: all 55 dispatches have correct token counts
- Stream-json monitoring: `events.jsonl` and `timeline.json` capture full execution trace
- PR creation: tasks 2, 3, 4, 5 all produced PRs on GitHub

#### What failed and why

| Failure | Root cause | Fix status |
|---|---|---|
| Conflict detection (check 4) | worktree path double-prefix `task-task-1` blocked task-1 | **Fixed**: `worktree_root / task_id` (not `f"task-{task_id}"`) |
| Forced-test-fail bypass (check 3) | Claude modified tests simultaneously with implementation | **Fixed**: Stop hook now restores `tests/greet.test.ts` before vitest |
| Stop hook not firing | `TaskCompleted` hook type is not a real Claude Code event | **Fixed**: changed to `Stop` event type |
| LEARNINGS injection (check 6) | Lessons were "clean run", no keyword overlap | **Fixed**: lesson now includes `dispatch_count`, `unhealthy_count`, `test_fail_count` |

---

## Experiment 2 — Next Run (Planned)

### H: Hypotheses for Next Run

1. With `Stop` hook enabled, task-3 (forced-test-fail) will NOT pass on the first dispatch because `tests/greet.test.ts` will be restored before vitest runs, forcing Claude to keep working until it finds the correct approach.
2. With worktree path fixed (`task-task-id` → `task-id`), task-1 will reach the rebase step, and the conflict with task-2 will be properly detected and resolved.
3. With richer lessons (`dispatch_count`, `unhealthy_count`), `extract_relevant_lessons` will find keyword matches for learning-consumer task, and the injection will be non-empty.
4. `scripts/verify.sh` will score 9/9.

### V: Configuration Variables for Next Run

| Variable | Value | Change from Exp 1 |
|---|---|---|
| Workers (round 1) | 2 | same |
| Workers (round 2) | 1 | same |
| `--max-turns` (implement) | 50 | same |
| Stop hook type | `Stop` | **changed** |
| Stop hook anti-recursion | yes (reads `stop_hook_active`) | **added** |
| Stop hook frozen test restore | yes (`git checkout -- tests/greet.test.ts`) | **added** |
| Worktree path formula | `worktree_root / task_id` | **fixed** |
| Lesson quality | includes dispatch_count, unhealthy_count, test_fail_count | **improved** |
| Conflict pair design | tasks 1+2 both modify `divide()` in `src/math.ts` | same |
| `MAX_IMPL_DISPATCHES` | not set (still wall-clock only) | unchanged |

### Pre-run checklist

Before running experiment 2:
- [ ] `bash scripts/reset.sh` — cleans state and re-tags EXPERIMENT_BASELINE
- [ ] Verify `.claude/settings.json` has `"Stop"` hook (not `TaskCompleted`)
- [ ] Verify `git_ops.py` uses `worktree_root / task_id` (not `f"task-{task_id}"`)
- [ ] Verify `experience.py` lesson includes `unhealthy_dispatches`, `test_fail_dispatches`
- [ ] `ccm init .` to copy updated templates
- [ ] Add 5 tasks via `ccm add`
- [ ] `ccm plan --workers 3` and review `plans/*.json`
- [ ] `ccm run --workers 2` (round 1: tasks 1,2,3)
- [ ] `ccm run --workers 1` (round 2: tasks 4,5)
- [ ] `ccm worklog && ccm reflect && ccm status`
- [ ] `bash scripts/verify.sh` — expect 9/9

### Open questions for experiment 2

1. Does the `Stop` hook actually fire in `npx claude -p` headless mode? (It fires in interactive sessions; behavior in `-p` mode needs verification.)
2. Will task-1's repeated-unhealthy-dispatch pattern recur? If so, what does `MAX_IMPL_DISPATCHES` need to be?
3. Does conflict resolution (`_resolve_rebase_conflict`) actually work when called? The dispatch exists in code but has never been observed in a timeline.

---

## Document Conventions

| Field | Format |
|---|---|
| Experiment date | YYYY-MM-DD |
| verify.sh score | X/9 pass |
| Hypotheses | numbered, stated before run |
| Variables | table with "Change from ExpN" column |
| Results | verify.sh table + key observations |
| Conclusions | what proved, what failed, what changed |
