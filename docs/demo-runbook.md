# CCM Demo Runbook

## 0) Preconditions

- repository initialized and clean enough to run demo
- `npx claude` available
- `gh` authenticated if PR creation is expected
- `ccm` installed (`pip install -e .` or project equivalent)

## 1) Initialize manager files

```bash
ccm init
```

Expected:

- `CLAUDE.md` exists
- `.claude/settings.json` exists
- `LEARNINGS.md` exists
- `data/dev-tasks.json` exists

## 2) Add 5 demo tasks

Use prompts that map to the design spec:

```bash
ccm add --title "conflict-alpha" "Modify src/utils.ts shared line set A to implement variant alpha behavior with tests."
ccm add --title "conflict-beta" "Modify src/utils.ts same shared line set to implement variant beta behavior with tests."
ccm add --title "forced-test-failure" "Change greeting behavior in a way that initially breaks current tests, then update implementation/tests to green."
ccm add --title "learning-consumer" "Implement a similar change pattern while explicitly applying prior LEARNINGS.md lessons."
ccm add --title "clean-baseline" "Add a small independent utility + tests with minimal risk."
```

Validate:

```bash
ccm status
```

## 3) Batch planning + manager review

```bash
ccm plan --workers 3
```

Expected:

- `plans/task-*.json` produced
- each task has plan status + approved/rejected metadata
- manager review reasons are persisted back to `data/dev-tasks.json`

## 4) Execute round 1 (A/B/C)

Keep only A/B/C approved and pending for first run (or run full queue if workflow already enforces order externally).

```bash
ccm run --workers 2
```

Watch:

- `logs/<task-id>/events.jsonl`
- `logs/<task-id>/timeline.json`
- `LEARNINGS.md` entries appended with commit ids

## 5) Execute round 2 (D/E)

After round 1 completes and `LEARNINGS.md` has entries:

```bash
ccm run --workers 1
```

Expected:

- learning-consumer task includes relevant lessons in prompt/PR context
- clean-baseline shows short lifespan with minimal retries

## 6) Timeline visibility checks

```bash
ccm timeline
ccm status
```

Expected:

- timeline table shows per-task step timestamps
- done/failed states visible with PR links

## 7) Reflection loop

```bash
ccm reflect
```

Expected:

- `CLAUDE.md` "Learned Rules" section updated from `LEARNINGS.md`

## 8) Final demo report

Fill `docs/demo-report.md` using:

- `plans/*.json`
- `data/dev-tasks.json`
- `logs/*/events.jsonl`
- `logs/*/timeline.json`
- `LEARNINGS.md`
- PR links from `ccm status`
