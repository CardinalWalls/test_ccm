# Claude Code Best Practice - Full Coverage Report

Date: 2026-02-18  
Source: `docs/best-practice.md`  
Claude Code: 2.1.45  
Environment: WSL2 Ubuntu, Node 22.19.0, npm 10.9.3, Git 2.43.0

---

## Executive Summary

The first pass only covered CLI-level features (A/B/E/F surface).  
This pass completed missing workflow coverage for:

- **Area C:** Ralph loop lifecycle + Stop hook gating + queue-style loop semantics
- **Area D:** Git worktree parallel execution and merge-back
- **Area E (deep):** Hook stdin/audit evidence (`transcript_path`, `stop_hook_active`) and block/allow behavior
- **Area F (deep):** Concurrent plan farm with parallel `claude -p` calls

Final status: **19/19 tests passed**.

---

## Critical Operational Finding

For non-interactive/headless automation, always provide EOF on stdin:

- Shell: `npx claude -p "..." </dev/null`
- Python: `subprocess.check_output(..., stdin=subprocess.DEVNULL)`

Without this, `-p` can block waiting for stdin.

---

## Preconditions

Completed:

- `jq` verified at `/usr/bin/jq`
- `ralph-loop` plugin installed and enabled
- project `.claude/settings.json` created for hook tests
- worktree parent directory created: `../claude-learning-worktrees`
- base project initialized as git repo (from earlier run)

---

## Tests

## T1-T10 (CLI Coverage) - PASS

Already completed and reconfirmed:

- T1 Basic `-p`
- T2 `--output-format json`
- T3 `--json-schema`
- T4 `--output-format stream-json --verbose`
- T5 fuse (`--max-budget-usd` used; `--max-turns` absent in 2.1.45 help)
- T6 plan mode + tools restriction + schema
- T7 `--allowedTools`
- T8 `--dangerously-skip-permissions`
- T9 stream-json + verbose + partial messages
- T10 Python subprocess integration

Status: **10/10 PASS**.

---

## T11-T19 (Missing Workflow Coverage)

### T11: Install and verify ralph-loop plugin - PASS

Command:

```bash
npx claude plugin install ralph-loop
npx claude plugin list
```

Result:

- Installed: `ralph-loop@claude-plugins-official`
- Status: enabled

---

### T12: Ralph loop Stop hook blocks exit and iterates - PASS

Setup:

- Created `.claude/ralph-loop.local.md` with:
  - `iteration: 1`
  - `max_iterations: 3`
  - `completion_promise: "DONE"`
  - prompt to create `hello.txt`

Run:

```bash
npx claude -p "Start working on the task described in .claude/ralph-loop.local.md" \
  --dangerously-skip-permissions --max-budget-usd 1.00 </dev/null
```

Evidence:

- `hello.txt` created with `Hello World`
- output: `<promise>DONE</promise>`
- `.claude/ralph-loop.local.md` removed automatically after completion

---

### T13: transcript audit evidence - PASS

Transcript found at:

- `~/.claude/projects/-home-indows-claude-learning/a039f3c3-e75a-405f-8917-6444393e2c9c.jsonl`

Evidence in transcript includes:

- user prompt
- assistant `Read` tool call on `.claude/ralph-loop.local.md`
- assistant `Write` tool call creating `hello.txt`
- final assistant text `<promise>DONE</promise>`

This confirms persistent JSONL audit trail for the loop run.

---

### T14: Custom Stop hook quality gate + hook input fields - PASS

Configured project hook in `.claude/settings.json`:

- On `Stop`, command logs hook stdin to `temp/T14_hook_input.json`
- If `hello.txt` missing: returns `{"decision":"block",...}`
- If present: allows stop

Run (starting with missing `hello.txt`):

```bash
npx claude -p "Reply with OK and then finish." --dangerously-skip-permissions --max-budget-usd 1.00 </dev/null
```

Evidence:

- `temp/T14_hook_events.log` shows:
  - `blocked`
  - `allow`
- `temp/T14_hook_input.json` captured:
  - `transcript_path`
  - `hook_event_name: "Stop"`
  - `stop_hook_active: true`
  - `permission_mode: "bypassPermissions"`
- `hello.txt` recreated with correct content

This directly validates E3/E4 and C4 behavior.

---

### T15: Git worktree create/isolate - PASS

Commands:

```bash
git worktree add -b task/greet ../claude-learning-worktrees/task-greet
cd ../claude-learning-worktrees/task-greet
npm install
```

Result:

- new branch/worktree created and isolated
- separate working directory with shared repo history

---

### T16: Parallel claude sessions across worktrees - PASS

Ran two jobs concurrently:

- Worker 1 (worktree): create `src/greet.ts`
- Worker 2 (main): create `src/farewell.ts`

Both exited 0.

Artifacts:

- `src/greet.ts` in worktree branch
- `src/farewell.ts` in main repo
- outputs confirm completion in both sessions

---

### T17: Merge back to main - PASS

Commands:

```bash
# in worktree branch
git add src/greet.ts
git commit -m "add greet utility in worktree branch"

# in main
git merge task/greet
```

Result:

- fast-forward merge succeeded
- `src/greet.ts` now in `master`
- no merge conflict

---

### T18: Concurrent plan farm (3 parallel processes) - PASS

Implemented multiprocessing script (`temp/t18_plan_farm_retry.py`):

- 3 tasks in parallel:
  - add logging
  - add error handling
  - add input validation
- each uses:
  - `--permission-mode plan`
  - `--tools "Read,Grep,Glob"`
  - `--output-format json`
  - `--json-schema ...`
- includes retry up to 3 attempts per task

Result file: `temp/T18_results.json`

Outcome:

- all 3 tasks returned success (`ok: true`)
- all succeeded on first attempt in final run

---

### T19: Task queue loop with exit condition - PASS

Created `tasks.json` with two pending tasks and loop script `temp/t19_queue_loop.sh`:

Loop behavior:

1. select next pending task
2. execute via `npx claude -p ... --dangerously-skip-permissions </dev/null`
3. mark task `done` in JSON
4. exit when queue empty

Execution log (`temp/T19_loop.log`):

- `RUN task_id=1 ...` -> `DONE task_id=1`
- `RUN task_id=2 ...` -> `DONE task_id=2`
- `QUEUE_EMPTY -> EXIT`

Final `tasks.json` shows both tasks `done`; files created:

- `README.md`
- `.editorconfig`

---

## Coverage Mapping vs `best-practice.md`

- **A (headless subprocess):** covered (T1-T4, T10)
- **B (permissions):** covered (T6-T8)
- **C (Ralph loop lifecycle + gate):** covered (T12, T14, T19)
- **D (worktree parallel):** covered (T15-T17)
- **E (monitor/audit/hooks):** covered (T9, T13, T14)
- **F (batch plan kickoff/review):** covered (T6, T18)

---

## Final Score

- Previous: 10/10 (CLI-only subset)
- Added: 9/9 (Ralph/worktree/hooks/plan-farm/queue)
- **Overall: 19/19 PASS**

---

## Notes / Caveats

1. `--max-turns` is referenced in the doc but not exposed in `npx claude --help` for 2.1.45; `--max-budget-usd` is available and used as fuse.
2. For strict structured outputs, retries may be needed in heavy prompts (observed once during T18 before adding retry wrapper).
3. Keeping hook logic in project `.claude/settings.json` is effective for local quality gates and auditable behavior.
