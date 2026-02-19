# Advanced Patterns: Agent Teams, Worktree vs Containers, Plan-Review Workflow

Date: 2026-02-19
Companion to: `best-practice.md`, `test-report.md`, `orchestrator/run.py`

---

## 1. The Four Untested Items -- Are They Important?

The previous audit identified 4 items from `best-practice.md` that were not tested locally. Here is what each one actually does, whether you need it, and what replaces it when you don't have it.

### B5: Organization-level managed settings

**What it is.** Claude Code settings support a `managed-only` tier where an organization administrator locks down hooks, permission rules, and tool access centrally. Individual users cannot override these settings.

**When it matters.** Enterprise teams where compliance requires that every Claude session enforces the same rules (e.g. "never run `rm -rf`", "always run linter before commit"). If you are a solo developer or a small team, project-level `.claude/settings.json` does the same job.

**Verdict: low priority for you.** Project-level hooks (which we tested in T14 and used in the orchestrator) give you the same quality-gate behavior. Org-level is only needed when you cannot trust every team member to keep the project config intact.

### C7: TeammateIdle hook

**What it is.** When using Agent Teams (see section 2 below), each teammate can go "idle" after finishing its assigned work. The `TeammateIdle` hook fires at that moment. If the hook exits with code 2, the teammate is forced to keep working -- useful for enforcing "don't idle until tests pass" or "don't idle until PROGRESS.md is updated".

**When it matters.** Only when running Agent Teams. It is the multi-agent equivalent of the `Stop` hook we tested in T12/T14. If you use the external orchestrator (`orchestrator/run.py`), the orchestrator itself enforces the quality gate (run tests, retry on failure) so the hook is redundant.

**Verdict: medium priority.** You said you want Agent Teams. Once you enable them, `TeammateIdle` becomes your quality gate. See section 2.

### D11: Container isolation

**What it is.** Instead of git worktrees on the same host, each agent runs inside its own Docker container with an isolated filesystem, network, and process space. The worktree is mounted into the container.

**When it matters.** When tasks involve dangerous operations (arbitrary shell commands, network access, installing unknown packages) and you need a hard security boundary. Also useful when tasks need different system-level dependencies (Python 3.10 vs 3.12, different OS packages).

**Can worktree replace it?** Partially. See section 3 below for a detailed comparison.

**Verdict: low priority now.** Worktrees give you the isolation you need for parallel coding tasks. Containers add value only when you need security sandboxing or heterogeneous environments.

### F4: Agent Teams + tmux mode

**What it is.** The built-in Agent Teams feature (section 2 below) with a tmux split-pane UI where each teammate gets its own terminal pane, visible simultaneously.

**When it matters.** This is what you said you want. Read section 2 carefully.

**Verdict: high priority. This is your next step.**

---

## 2. Agent Teams: What You Want

### What Agent Teams Actually Are

Agent Teams is an experimental Claude Code feature where one session (the "lead") spawns multiple independent Claude Code instances ("teammates"). Each teammate has its own context window and works in parallel. They coordinate through:

- A **shared task list** stored at `~/.claude/tasks/{team-name}/`
- A **mailbox system** where teammates send messages to each other directly
- **Self-coordination**: teammates claim unassigned tasks on their own

This is fundamentally different from our `orchestrator/run.py` approach:

```
Our orchestrator:          Agent Teams:
                           
Python script              Claude Code lead session
  |                          |
  +-- claude -p (worker 1)   +-- Teammate A (full Claude session)
  +-- claude -p (worker 2)   +-- Teammate B (full Claude session)
                              +-- Teammate C (full Claude session)
  Workers are headless.       Teammates talk to each other.
  No inter-worker comms.      Shared task list.
  Orchestrator controls.      Lead coordinates, but teammates self-manage.
```

### How to Enable

Add to `~/.claude/settings.json`:

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  },
  "teammateMode": "tmux"
}
```

Then start a tmux session and launch `claude`:

```bash
tmux new-session -s dev
claude
```

Inside Claude, describe your task and ask for a team:

```
Create an agent team with 3 teammates to implement these features in parallel:
1. Add a caching layer to the API
2. Write integration tests for auth
3. Refactor the database queries
Require plan approval before any teammate makes changes.
```

### Agent Teams vs Our Orchestrator

| Dimension | orchestrator/run.py | Agent Teams |
|---|---|---|
| Control model | External Python script drives everything | Lead Claude session coordinates |
| Communication | None between workers | Teammates message each other |
| Task assignment | Atomic claim from JSON queue | Shared task list with self-claim |
| Quality gate | Orchestrator runs tests after each step | `TeammateIdle`/`TaskCompleted` hooks |
| Conflict handling | Orchestrator detects + invokes Claude to resolve | Teammates should own separate files; lead resolves conflicts |
| Cost | Lower (headless, minimal context) | Higher (each teammate is a full Claude session) |
| Isolation | Git worktree per worker | Same repo (or worktrees if you set it up) |
| Audit trail | `PROGRESS.md` + `dev-tasks.json` + git log | Transcript per teammate + task list |
| Best for | Batch processing, CI/CD, overnight runs | Interactive development, research, reviews |

**When to use which:**
- Use the orchestrator for deterministic batch execution (overnight task queues, CI pipelines).
- Use Agent Teams for interactive parallel work where teammates need to discuss, challenge, and coordinate.
- You can combine both: use Agent Teams during the day for interactive work, and the orchestrator overnight to drain a task backlog.

### Quality Gates with TeammateIdle

When a teammate finishes work and goes idle, the `TeammateIdle` hook fires. To enforce "tests must pass before idle":

```json
{
  "hooks": {
    "TeammateIdle": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash -c 'npm test 2>/dev/null || (echo \"{\\\"decision\\\":\\\"block\\\",\\\"reason\\\":\\\"Tests failing. Fix them before going idle.\\\"}\" && exit 2)'"
          }
        ]
      }
    ]
  }
}
```

Similarly, `TaskCompleted` fires when a task is marked complete:

```json
{
  "hooks": {
    "TaskCompleted": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash -c 'npm test 2>/dev/null || exit 2'"
          }
        ]
      }
    ]
  }
}
```

Exit code 2 blocks the action and sends feedback to the teammate.

---

## 3. Worktree vs Container: When Each Matters

### What a Worktree Actually Is

A git worktree is a second (or third, or Nth) working directory that shares the same `.git` object store as your main repo. Each worktree checks out a different branch and has its own index (staging area).

```
Main repo:                     Worktree:
/home/user/project/            /home/user/project-worktrees/task-1/
  .git/  (owns the objects)      .git  (file, points to main .git)
  src/math.ts  (master)         src/math.ts  (task/task-1 branch)
  node_modules/                 node_modules/  (separate copy)
```

Key facts:
- Same git objects, different working directories
- Branches are isolated: committing in one worktree does not affect the other
- **File system is NOT isolated**: both worktrees share the same OS, same user, same network
- `node_modules/` must be installed separately per worktree (or symlinked, but we found this causes lockfile conflicts)

### How Worktree Merge/Review Works (What We Proved)

Our orchestrator demonstrated the full lifecycle. Here is exactly what happened, with real evidence from the run:

```
Timeline:
                                                                          
  master ──────[672484a]──────────────────[37d1d9f]──[dfbfe09]──[43fafec]──[4c4d772]
                  |                           |          |          |          |
                  |  Worker 1 branches        |  merge   |  merge   |  merge   |  merge
                  +-- task/task-1 ────────────+          |          |          |
                  |    (subtract, divide)                |          |          |
                  |                                      |          |          |
                  +-- task/task-2 ───── CONFLICT ────────|──────────+          |
                  |    (multiply, power)  rebase failed  |                     |
                  |    Claude resolved it ───────────────|─────────>           |
                  |                                      |                     |
                  +-- task/task-3 ───────────────────────+                     |
                  |    (string-utils)                                          |
                  |                                                            |
                  +-- task/task-4 ─────────────────────────────────────────────+
                       (array-utils)
```

**Step-by-step with real log evidence:**

1. **Claim**: `[Worker 1] claimed task-1` / `[Worker 2] claimed task-2` (atomic via `fcntl.flock`)
2. **Branch + Worktree**: `git worktree add -b task/task-1 ../claude-learning-worktrees/task-task-1`
3. **Dependencies**: `npm ci` in each worktree (separate `node_modules/`)
4. **Implement**: `claude -p` in worktree, headless. Claude writes source + tests.
5. **Test**: `npx vitest run` -- both passed on iteration 1
6. **Commit**: `git add -A && git commit -m "feat(task-1): implement task changes"`
7. **Rebase**: Worker 1 rebased clean. Worker 2 hit a conflict because Worker 1 merged first:
   - `[Worker 2] rebase conflict detected`
   - `[Worker 2] conflict-resolve attempt=1 exit=0`
   - `[Worker 2] conflicts resolved and rebase finished`
8. **Merge**: Serialized via `merge.lock`. Worker 1 merged first (fast-forward-like). Worker 2 merged after conflict resolution.
9. **Post-merge test**: `npx vitest run` on main repo after each merge.
10. **Mark done**: `update_task_status("task-1", "done", ...)` -- **before** cleanup.
11. **Cleanup**: `git worktree remove --force` + `git branch -D`
12. **Log**: Append to `PROGRESS.md` with commit ID.

**Review**: In the orchestrator model, review happens at two points:
- **Automated review**: post-merge test suite must pass (line 246 in `run.py`)
- **Human review**: `git log --oneline` shows all merge commits; `PROGRESS.md` shows which tasks had conflicts; `data/dev-tasks.json` records timestamps and commit IDs for audit

### Worktree vs Container Comparison

| Dimension | Git Worktree | Docker Container |
|---|---|---|
| Isolation level | Branch-level (same OS, user, network) | OS-level (separate filesystem, network, PIDs) |
| Setup speed | Seconds (`git worktree add` + `npm ci`) | Minutes (build image + start container) |
| Shared state | Same git objects, same env vars, same tools | Nothing shared unless explicitly mounted |
| Security | No sandboxing; agent can access host | Strong sandboxing; agent trapped in container |
| Port conflicts | Possible (shared network) | No (each container gets own network namespace) |
| Dependency isolation | Separate `node_modules/` per worktree | Fully separate OS-level packages |
| Cost | Zero (just disk space for files) | Image storage + container runtime overhead |
| Merge workflow | Native git rebase/merge | Same, but git operations happen inside container |

**When worktrees are enough:**
- Tasks are coding-only (edit files, run tests)
- You trust the AI agent not to damage the host
- Tasks use the same language/toolchain version
- No port conflicts (tasks don't run servers, or you assign ports)

**When you need containers:**
- Tasks run untrusted code or arbitrary shell commands
- Tasks need different system dependencies
- Tasks run long-lived servers that would conflict on ports
- You need reproducible environments across machines

**The hybrid approach (recommended for production):**
Each container gets its own git worktree mounted in:
```bash
docker run -v /host/worktrees/task-1:/workspace -w /workspace my-dev-image \
  npx claude -p "..." --dangerously-skip-permissions </dev/null
```
This gives you both git-level isolation (worktree branches) and OS-level isolation (container).

---

## 4. How "Plan Batch Kickoff + Unified Review" Works

This is Section F of `best-practice.md`. The pattern has two phases:

### Phase 1: Plan Farm (parallel, read-only)

Multiple `claude -p` calls run in parallel, each in `--permission-mode plan` (read-only), producing structured JSON plans:

```
                    +-- claude -p "Plan task A" --permission-mode plan --json-schema ... --> plan_A.json
                    |
Orchestrator -------+-- claude -p "Plan task B" --permission-mode plan --json-schema ... --> plan_B.json
(Python/parallel)   |
                    +-- claude -p "Plan task C" --permission-mode plan --json-schema ... --> plan_C.json
```

Each plan output is forced into a schema:
```json
{
  "title": "Add caching layer",
  "steps": ["Identify hot paths", "Add Redis client", "Wrap DB queries", "Add cache invalidation"],
  "risks": ["Cache stampede", "Stale data"],
  "estimate": "2 hours"
}
```

We proved this works in T18 (3 parallel plan processes, all returned valid JSON).

### Phase 2: Unified Review (automated or human)

The collected JSON plans are reviewed. This can be:

**Automated review** (machine reads JSON):
```python
plans = [json.load(open(f)) for f in glob("plans/*.json")]
for plan in plans:
    assert "steps" in plan and len(plan["steps"]) > 0
    assert "risks" in plan
    # Score/rank/filter plans programmatically
    score = len(plan["steps"]) + len(plan.get("risks", []))
    print(f"{plan['title']}: score={score}")
```

**Human review** (diff/compare):
```bash
# Side-by-side comparison
diff <(jq '.steps[]' plan_A.json) <(jq '.steps[]' plan_B.json)
```

**AI review** (Claude reviews the plans):
```bash
claude -p "Review these 3 implementation plans and pick the best one. 
Plans: $(cat plans/*.json)" \
  --permission-mode plan \
  --output-format json \
  --json-schema '{"type":"object","properties":{"winner":{"type":"string"},"reasoning":{"type":"string"}},"required":["winner","reasoning"]}'
```

### Phase 3: Execute Approved Plans

Only after review, execution begins with elevated permissions:

```bash
claude -p "Execute plan: $(cat approved_plan.json)" \
  --dangerously-skip-permissions \
  --max-budget-usd 2.00
```

The key principle: **plan phase is read-only, execution phase is write-enabled**. This prevents the "think and do at the same time" anti-pattern where the model changes its approach mid-implementation.

### How This Connects to Our Orchestrator

Our orchestrator skips the explicit plan phase (tasks go directly to execution). To add a plan-review gate, you would insert a step before `execute_task()`:

```python
# In worker_loop, before execute_task:
plan = generate_plan(worktree_path, task)  # claude -p --permission-mode plan
if not review_plan(plan):                   # automated or human review
    mark_task_failed(task, "plan rejected")
    continue
execute_task(worktree_path, task, ...)     # claude -p --dangerously-skip-permissions
```

This is a design choice. For well-defined tasks (like "add subtract() to math.ts"), direct execution is fine. For ambiguous or risky tasks, adding a plan-review gate reduces wasted tokens and catches bad approaches early.

---

## 5. Recommended Next Steps

1. **Enable Agent Teams** in `~/.claude/settings.json` and try a simple 2-teammate task interactively to see how coordination works.
2. **Add `TeammateIdle` hook** to enforce test-pass-before-idle once you start using teams.
3. **Add a plan phase** to the orchestrator for tasks that are ambiguous or large.
4. **Consider containers** only when you start running tasks that involve untrusted code or need port isolation.
