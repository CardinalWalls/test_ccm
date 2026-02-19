# Orchestrator End-to-End Report

Date: 2026-02-18
Environment: WSL2 Ubuntu, Python 3.13, Node 22.19, Git 2.43, Claude Code 2.1.45 via Routin API

---

## Architecture

`orchestrator/run.py` (357 lines) implements the full task lifecycle from `docs/best-practice.md`:

```
claim_task -> create_worktree -> execute_task -> run_tests -> rebase_onto_master -> merge_to_master -> mark_done -> cleanup -> log_experience
```

Key components:

| Component | Mechanism |
|---|---|
| Task queue | `data/dev-tasks.json`, atomic via `fcntl.flock` on `data/dev-tasks.lock` |
| Parallelism | `ProcessPoolExecutor` with 2 workers |
| Isolation | `git worktree add` per task, `npm ci` in each worktree |
| Execution | `npx claude -p ... --dangerously-skip-permissions --max-budget-usd 1.00` with `stdin=DEVNULL` |
| Quality gate | `npx vitest run` must pass before merge is attempted |
| Ralph retry | Up to 3 iterations of execute+test per task |
| Merge serialization | Second lock file `data/merge.lock` prevents concurrent merges |
| Conflict resolution | Claude invoked headless to resolve rebase conflicts and `git rebase --continue` |
| Status ordering | `mark_task_done` before `cleanup_worktree` (prevents data loss on kill) |
| Experience log | `PROGRESS.md` with commit IDs and conflict annotations |

---

## Task Queue

4 tasks, first 2 deliberately targeting the same file (`src/math.ts`) to guarantee a merge conflict:

| ID | Title | Conflict risk |
|---|---|---|
| task-1 | Add subtract and divide to math module | HIGH (math.ts) |
| task-2 | Add multiply and power to math module | HIGH (math.ts) |
| task-3 | Create string utilities | None (new file) |
| task-4 | Create array utilities | None (new file) |

---

## Run 1: Failures and Root Causes

### Failure 1: Symlinked `data/dev-tasks.json` blocked merge

The orchestrator symlinked the task queue file into worktrees so all workers could share it. When merging a task branch back to master, git refused because the symlink target already existed as an untracked file:

```
error: The following untracked working tree files would be overwritten by merge:
    data/dev-tasks.json
```

**Fix:** Removed the symlink step entirely. The queue file lives only in the main repo; workers access it via the absolute path through `locked_json_update`.

### Failure 2: `package-lock.json` conflict during merge

Each worktree ran `npm install`, which regenerated `package-lock.json` with slight differences. When the second task branch merged, git saw a content conflict in the lockfile:

```
CONFLICT (content): Merge conflict in package-lock.json
Automatic merge failed
```

A failed merge left the main repo index dirty. The next worker could not `git checkout master`:

```
error: you need to resolve your current index first
```

**Fix (two changes):**
1. Changed worktree dependency install from `npm install` to `npm ci` (installs from lockfile without modifying it).
2. Added `git merge --abort` on merge failure so the index is always left clean for the next worker.

---

## Run 2: Successful End-to-End

After applying both fixes, tasks 2 and 4 (which failed in run 1) were reset to `pending` and the orchestrator was re-executed.

### Timeline

| Time (UTC) | Worker | Event |
|---|---|---|
| 14:06:09 | 1 | Claimed task-1 (subtract/divide) |
| 14:06:09 | 2 | Claimed task-2 (multiply/power) |
| 14:06:09 | 1,2 | Created worktrees, ran `npm ci` |
| 14:06:40 | 1 | Claude implemented task-1, tests passed |
| 14:06:41 | 2 | Claude implemented task-2, tests passed |
| 14:06:42 | 1 | Rebase clean, merged to master |
| 14:06:42 | 2 | **Rebase conflict detected** in `src/math.ts` |
| 14:06:52 | 1 | task-1 done at `37d1d9f` |
| 14:06:53 | 1 | Claimed task-3 (string utils) |
| 14:07:20 | 2 | Claude resolved conflict (attempt 1), rebase finished |
| 14:07:21 | 2 | Post-resolution tests passed |
| 14:07:41 | 1 | task-3 done at `dfbfe09` |
| 14:07:41 | 1 | Claimed task-4 (array utils) |
| 14:07:49 | 2 | task-2 merge failed (lockfile conflict from run 1 residue) |
| 14:09:48 | 2 | Re-claimed task-2 (retry run) |
| 14:09:48 | 1 | Re-claimed task-4 (retry run) |
| 14:10:33 | 2 | task-2 done at `43fafec` |
| 14:10:34 | 1 | task-4 done at `4c4d772` |

### Merge Conflict Detail

Worker 1 merged `task/task-1` first, adding `subtract()` and `divide()` to `src/math.ts`.
Worker 2 had independently added `multiply()` and `power()` to the same file.
When Worker 2 ran `git rebase master`, git produced a conflict in `src/math.ts`.
Claude was invoked headless to resolve it: it identified the conflict markers, kept all functions from both sides, ran `git add` and `git rebase --continue`. Tests passed after resolution.

---

## Final State

### Task queue (`data/dev-tasks.json`)

All 4 tasks: `status: "done"` with `commit_id` and `completed_at` timestamps.

### Git history

```
4c4d772 merge(task-4): integrate worktree result
8b64d6b feat(task-4): implement task changes
43fafec merge(task-2): integrate worktree result
87d8832 feat(task-2): implement task changes
dfbfe09 merge(task-3): integrate worktree result
2def2d2 feat(task-3): implement task changes
37d1d9f merge(task-1): integrate worktree result
7b5dc63 feat(task-1): implement task changes
672484a chore: create orchestrator baseline project scaffold
```

### Test suite

```
 3 test files passed (3)
24 tests passed (24)
```

### Source files produced by Claude

| File | Functions |
|---|---|
| `src/math.ts` | `add`, `subtract`, `divide`, `multiply`, `power` |
| `src/string-utils.ts` | `capitalize`, `reverse` |
| `src/array-utils.ts` | `unique`, `flatten` |

### Progress log (`PROGRESS.md`)

4 entries with commit IDs. `task-2` annotated with `had_conflict: True`.

### Worktrees

All cleaned up. `git worktree list` shows only the main working tree.

---

## Best Practice Coverage

| Best practice area | Covered | Evidence |
|---|---|---|
| A. Headless subprocess (`claude -p`) | Yes | All task execution uses `claude -p` with `stdin=DEVNULL` |
| B. Permission control | Partial | Uses `--dangerously-skip-permissions`; `--allowedTools` not used |
| C. Ralph loop (retry until quality gate) | Yes | Worker loop retries up to `MAX_ITERATIONS` until tests pass |
| C. Task queue with exit condition | Yes | `claim_task` returns `None` when queue empty; worker exits |
| C. Status before cleanup | Yes | `update_task_status` called before `cleanup_worktree` |
| D. Git worktree isolation | Yes | One worktree per task, `npm ci`, independent branches |
| D. Parallel execution | Yes | 2 workers via `ProcessPoolExecutor` |
| D. Merge conflict handling | Yes | Rebase + Claude-driven resolution + post-resolution test |
| E. Audit trail | Partial | `PROGRESS.md` with commit IDs; transcript JSONL exists but not consumed |
| F. Plan batch kickoff | Not in scope | Orchestrator focuses on execution, not plan-then-review |

---

## Lessons Learned

1. **Symlinks in worktrees cause merge failures.** Shared files should be accessed by absolute path, not symlinked into worktree directories that get merged.
2. **`npm install` in worktrees mutates `package-lock.json`**, creating spurious merge conflicts. Use `npm ci` instead.
3. **Failed merges must be aborted.** A dirty index from a failed `git merge` blocks all subsequent git operations in that repo until `git merge --abort` is called.
4. **`stdin=subprocess.DEVNULL` remains mandatory** for all headless `claude -p` calls, consistent with the finding from the earlier CLI test suite.
5. **Claude resolves real merge conflicts reliably.** In the observed run, a `src/math.ts` conflict (two branches adding different functions) was resolved correctly on the first attempt.
