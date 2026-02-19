# CLAUDE.md

This repository is managed by Claude Code Manager (`ccm`).

## Task Lifecycle (Mandatory)

When a task is assigned, follow this sequence:

1. Claim the task from `data/dev-tasks.json` (the manager provides task ID in prompt).
2. Work in the task worktree only.
3. Implement only the requested scope.
4. Add or update tests for all changed behavior.
5. Run tests and fix failures.
6. Commit your changes using the required format.
7. If rebase conflicts happen, follow the conflict protocol below until clean.
8. Continue until the task is test-green and commit-ready.
9. Record concise lessons in `LEARNINGS.md` through the manager flow.

## Conflict Handling Protocol

If rebase fails:

1. If error is unstaged changes, commit or stash first.
2. Run `git status` to list conflict files.
3. Read each conflict file and understand both sides.
4. Manually resolve the file and remove conflict markers.
5. Run `git add <resolved-files>`.
6. Run `git rebase --continue`.
7. Repeat until rebase finishes.

Do not abandon conflict resolution midway.

## Test Failure Protocol

If tests fail:

1. Run the project test command.
2. Analyze error output.
3. Fix the failing code.
4. Re-run tests.
5. Repeat until all tests pass.
6. Commit fixes with `fix({task-id}): ...` when needed.

Do not mark the task done with failing tests.

## Commit Conventions

- Feature work: `feat({task-id}): <short description>`
- Bug fix during task: `fix({task-id}): <short description>`

## Boundaries

- Do not modify files outside the task scope.
- Do not edit `data/dev-tasks.json` directly unless explicitly instructed by manager prompt.
- Do not push branches.
- Do not merge branches.

The manager handles push/PR/merge.

## Learning Loop

Before coding, read `LEARNINGS.md` and apply relevant lessons.

Every meaningful issue should produce a lesson with:

- what went wrong
- how it was resolved
- how to prevent recurrence
- commit id reference

Never repeat the same mistake twice.

## Learned Rules

This section is maintained by `ccm reflect` and evolves over time.

