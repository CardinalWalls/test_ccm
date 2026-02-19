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

## Full Task Lifecycle (9 Steps, Mandatory)

1. **Claim task**: atomic claim from `data/dev-tasks.json`.
2. **Create worktree**:
   - `git worktree add -b task/... ../...-worktrees/task-...`
   - create isolated `data/`
   - set up required symlinks
   - allocate dedicated `PORT`
3. **Implement**: complete requested behavior in the isolated worktree.
4. **Commit on task branch**: use required commit format.
5. **Merge + test gate**:
   - `git fetch origin && git merge origin/main`
   - run test command
6. **Auto-merge prep to main**:
   - `git fetch origin main`
   - `git rebase origin/main`
   - if rebase fails, resolve conflicts using protocol below
   - if step 6 fails, return to step 5 and continue loop
7. **Mark done**:
   - update task status in `data/dev-tasks.json` before cleanup
8. **Cleanup**:
   - remove worktree
   - delete local task branch
   - delete remote task branch
9. **Experience accumulation**:
   - append lessons to `LEARNINGS.md` with commit reference

**Never give up**: Do not mark a task as failed during conflict resolution or while tests are failing. You must fully resolve all conflicts and ensure all tests pass before proceeding; tasks can only be marked complete after successful resolution. Problems must be fixed—never abandon a task due to mid-process challenges.

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

