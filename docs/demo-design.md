# CCM Demo Design

## Goal

This demo is designed to exercise the full `ccm` lifecycle and all major protocols in `CLAUDE.md`, including:

- 9-step task lifecycle visibility
- worktree architecture (`data/` isolation + symlink policy + dedicated port)
- Ralph retry loop on implementation/test failures
- merge/rebase conflict handling with retry back to step 5
- `LEARNINGS.md` closed-loop behavior (`run` -> `learnings` -> `reflect`)

## Demo Task Set (5 Tasks)

### Task A - Conflict Pair Alpha

- Title: `conflict-alpha`
- Intent: modify shared file for deterministic conflict with Task B
- Target: `src/utils.ts` (or equivalent shared utility file)
- Expected behavior:
  - completes via normal implementation loop
  - one of A/B likely rebases cleanly, the other should hit conflict handling

### Task B - Conflict Pair Beta

- Title: `conflict-beta`
- Intent: modify the same lines as Task A with different behavior
- Target: `src/utils.ts` (same region as Task A)
- Expected behavior:
  - rebase conflict path must execute
  - worker follows rebase conflict protocol
  - retry returns to step 5 when needed

### Task C - Forced Test Failure

- Title: `forced-test-failure`
- Intent: guarantee at least one failed test cycle before success
- Method:
  - request a behavior change that initially breaks existing test expectations
  - require test update/fix to restore green state
- Expected behavior:
  - implementation loop runs multiple iterations
  - `LEARNINGS.md` captures concrete test-failure lesson with commit id

### Task D - Learning Consumer

- Title: `learning-consumer`
- Intent: run after A/B/C so prior lessons exist
- Method:
  - prompt overlaps with prior failure/conflict patterns
  - verify injected relevant lessons are present in worker context and PR body
- Expected behavior:
  - measurable lesson reuse from `LEARNINGS.md`

### Task E - Clean Baseline

- Title: `clean-baseline`
- Intent: independent low-risk task with clean pass path
- Expected behavior:
  - single-pass implementation
  - baseline timeline with minimal retries

## Execution Order

Two rounds maximize coverage and make the learning loop observable:

1. Round 1: run `A + B + C` (conflicts + forced retries)
2. Round 2: run `D + E` (lesson consumer + clean baseline)

## Lifecycle Visibility Model

Each task produces `logs/<task-id>/timeline.json` with step timestamps and counters:

- `step1_claimed`
- `step2_worktree_created`
- `step3_implement_started`
- `step3_implement_done`
- `step4_committed`
- `step5_merge_test_passed`
- `step6_rebase_passed`
- `step6_pushed`
- `step6_pr_created`
- `step7_marked_done`
- `step8_cleaned`
- `step9_learning_started`
- `step9_learning_recorded`

This file is the source of truth for per-task lifespan reporting.

## Feature Coverage Matrix

| Feature | Trigger Task(s) | Evidence |
|---|---|---|
| Worktree architecture + symlink policy | All | worktree path + `timeline.json`, runtime behavior |
| Step 5 merge + test gate | All | `step5_merge_test_passed` in `timeline.json` |
| Step 6 conflict protocol + retry | A/B | `step6_conflicts` counter + logs/events |
| Ralph implementation retry loop | C | `step3_iterations` counter + events |
| Task completion before cleanup | All | `step7_marked_done` before `step8_cleaned` |
| Learning accumulation | All | `LEARNINGS.md` entries with commit id |
| Learning reuse | D | prompt/PR "Relevant Lessons" evidence |
| Reflect rule evolution | Post-run | `ccm reflect` + updated `CLAUDE.md` rules |

## Success Criteria

- At least one task shows rebase conflict resolution path
- At least one task shows implementation retries due to failing tests
- All completed tasks have timeline files with ordered lifecycle steps
- `LEARNINGS.md` contains meaningful entries (not placeholders) with commit references
- `ccm reflect` updates `CLAUDE.md` learned rules based on accumulated entries
