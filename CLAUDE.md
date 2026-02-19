# CLAUDE.md

This repository is managed by Claude Code Manager (`ccm`).

## Worktree Architecture (Mandatory)

Each Claude Code worker runs in an isolated git worktree bound to one task branch.

- Worktree path format: `../<repo>-worktrees/task-<task-id>`
- Task branch format: `task/<task-id>-<slug>`
- Isolated runtime data directory: `<worktree>/data/`
- Shared queue/lock files via symlink:
  - `<worktree>/data/dev-tasks.json` -> `<repo>/data/dev-tasks.json`
  - `<worktree>/data/dev-tasks.lock` -> `<repo>/data/dev-tasks.lock`
- Shared dependencies for fast startup:
  - `<worktree>/node_modules` -> `<repo>/node_modules` (when available)
- Dedicated port per worker:
  - `PORT = 5200 + worker_id`

Do not symlink progress journals. `PROGRESS.md` and `LEARNINGS.md` stay in the repo root and are managed by the manager process.

## Full Task Lifecycle (9 Steps — Worker Role)

The manager handles steps 1, 2, 4–9 automatically. **You (the worker) only handle step 3.**

1. **Claim task** — *manager*
2. **Create worktree** — *manager*
3. **Implement** — **YOUR JOB**: use Read/Write/Edit/Bash tools to implement the feature and make tests pass.
4. **Commit on task branch** — *manager*
5. **Merge + test gate** — *manager*
6. **Rebase to main** — *manager*
7. **Mark done** — *manager*
8. **Cleanup** — *manager*
9. **Experience accumulation** — *manager*

**What you MUST do (step 3):**
- Read source files to understand the codebase.
- Write/Edit source and test files to implement the feature.
- Run `npm test` and fix failures until all tests pass.
- Commit your changes: `git add -A && git commit -m 'feat(<task-id>): <description>'`

**What you must NOT do:**
- Do NOT create or remove worktrees.
- Do NOT merge, rebase, push, or create PRs.
- Do NOT modify files under `data/` or `node_modules`.
- Do NOT mark tasks as done/failed in `dev-tasks.json`.

**Never give up**: If tests fail, keep fixing until they pass. Problems must be solved, not abandoned.

## Conflict Handling Protocol

If rebase fails:

1. If error is unstaged changes, commit or stash first.
2. Run `git status` to list conflict files.
3. Read each conflict file and understand both sides.
4. Resolve files and remove conflict markers.
5. Run `git add <resolved-files>`.
6. Run `git rebase --continue`.
7. Repeat until rebase finishes cleanly.

## Test Failure Protocol

If tests fail:

1. Run the test command.
2. Analyze the error output.
3. Fix the failing behavior.
4. Re-run tests.
5. Repeat until all tests pass.
6. Commit fixes with `fix({task-id}): ...` when needed.




## Commit Conventions

- Feature work: `feat({task-id}): <short description>`
- Fix during execution: `fix({task-id}): <short description>`

## Boundaries

- Stay within task scope.
- Do not directly mutate queue state unless manager workflow requires it.
- Do not push, merge, or close PRs manually unless explicitly instructed.
- Keep stdout machine-readable when manager expects structured output.

The manager handles orchestration, PR flow, and reflective updates.

## Learning Loop

Before execution, read relevant items from `LEARNINGS.md` and apply them.

Every meaningful issue should produce a lesson that includes:

- what happened
- how it was solved
- prevention rule
- commit id reference

The same mistake should not repeat.

## Learned Rules

This section is maintained by `ccm reflect` and evolves over time.

