#!/usr/bin/env bash
# =============================================================================
# CCM Experiment Verification Script
# =============================================================================
# Reads timeline.json and plans/*.json to produce a Pass/Fail matrix for
# the 9 acceptance checkpoints defined in docs/experiment-log.md.
#
# Usage:
#   bash scripts/verify.sh [--logs-dir logs/] [--plans-dir plans/]
#
# Exit code:
#   0  All checks pass
#   1  One or more checks fail
# =============================================================================

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGS_DIR="${REPO_ROOT}/logs"
PLANS_DIR="${REPO_ROOT}/plans"
LEARNINGS="${REPO_ROOT}/LEARNINGS.md"
CLAUDE_MD="${REPO_ROOT}/CLAUDE.md"

PASS=0
FAIL=0

c_green='\033[0;32m'
c_red='\033[0;31m'
c_yellow='\033[0;33m'
c_reset='\033[0m'

pass() { echo -e "  ${c_green}PASS${c_reset}  $1"; ((PASS++)); }
fail() { echo -e "  ${c_red}FAIL${c_reset}  $1"; ((FAIL++)); }
warn() { echo -e "  ${c_yellow}WARN${c_reset}  $1"; }

echo ""
echo "=== CCM Experiment Verification ==="
echo "Logs:   $LOGS_DIR"
echo "Plans:  $PLANS_DIR"
echo ""

# ── CHECK 1: plan farm ────────────────────────────────────────────────────────
echo "[1] Plan farm: all tasks approved with plan_reason"
approved_count=$(python3 -c "
import json, glob, os
count = 0
for f in glob.glob('${PLANS_DIR}/*.json'):
    try:
        d = json.load(open(f))
        verdict = d.get('verdict') or d.get('approved')
        reason = d.get('plan_reason') or d.get('review_reason') or ''
        if verdict and reason:
            count += 1
    except Exception:
        pass
print(count)
" 2>/dev/null)
plan_files=$(ls "${PLANS_DIR}"/*.json 2>/dev/null | wc -l)
if [ "${plan_files:-0}" -eq 0 ]; then
    fail "no plan files found in $PLANS_DIR"
elif [ "${approved_count:-0}" -eq "${plan_files:-0}" ]; then
    pass "$approved_count/$plan_files tasks have approved plans with reason"
else
    fail "$approved_count/$plan_files tasks approved (expected all)"
fi

# ── CHECK 2: worktree isolation ───────────────────────────────────────────────
echo "[2] Worktree isolation: each task has step2_worktree_created in timeline"
wt_ok=0
wt_total=0
for timeline in "${LOGS_DIR}"/*/timeline.json; do
    [ -f "$timeline" ] || continue
    ((wt_total++))
    step=$(python3 -c "
import json
d = json.load(open('$timeline'))
print('yes' if 'step2_worktree_created' in d.get('step_timestamps', {}) else 'no')
" 2>/dev/null)
    [ "$step" = "yes" ] && ((wt_ok++))
done
if [ "$wt_total" -eq 0 ]; then
    fail "no timeline files found"
elif [ "$wt_ok" -eq "$wt_total" ]; then
    pass "$wt_ok/$wt_total tasks created isolated worktrees"
else
    fail "$wt_ok/$wt_total tasks have step2_worktree_created"
fi

# ── CHECK 3: Stop hook fires (test failure retry) ─────────────────────────────
echo "[3] Stop hook / test retry: at least one task has test_passed=false dispatch"
retry_task=""
for timeline in "${LOGS_DIR}"/*/timeline.json; do
    [ -f "$timeline" ] || continue
    has_fail=$(python3 -c "
import json
d = json.load(open('$timeline'))
has = any(disp.get('test_passed') is False for disp in d.get('dispatches', []))
print('yes' if has else 'no')
" 2>/dev/null)
    if [ "$has_fail" = "yes" ]; then
        retry_task=$(basename "$(dirname "$timeline")")
        break
    fi
done
if [ -n "$retry_task" ]; then
    pass "task $retry_task had test_passed=false dispatch(es) (retry loop exercised)"
else
    fail "no task had a test_passed=false dispatch — Stop hook may not be firing"
fi

# ── CHECK 4: conflict detection ────────────────────────────────────────────────
echo "[4] Conflict detection: at least one task has rebase_attempts[].conflict=true"
conflict_task=""
for timeline in "${LOGS_DIR}"/*/timeline.json; do
    [ -f "$timeline" ] || continue
    has_conflict=$(python3 -c "
import json
d = json.load(open('$timeline'))
has = any(a.get('conflict') for a in d.get('rebase_attempts', []))
print('yes' if has else 'no')
" 2>/dev/null)
    if [ "$has_conflict" = "yes" ]; then
        conflict_task=$(basename "$(dirname "$timeline")")
        break
    fi
done
if [ -n "$conflict_task" ]; then
    pass "task $conflict_task hit a rebase conflict"
else
    fail "no rebase conflict detected — conflict pair task design may need adjustment"
fi

# ── CHECK 5: conflict resolution ──────────────────────────────────────────────
echo "[5] Conflict resolution: conflict task completed (not failed)"
if [ -n "$conflict_task" ]; then
    task_status=$(python3 -c "
import json
tasks = json.load(open('${REPO_ROOT}/data/dev-tasks.json'))
for t in tasks:
    if t.get('id') == '$conflict_task':
        print(t.get('status', 'unknown'))
        break
else:
    print('not_found')
" 2>/dev/null)
    if [ "$task_status" = "done" ]; then
        pass "conflict task $conflict_task resolved and marked done"
    else
        fail "conflict task $conflict_task status=$task_status (not done)"
    fi
else
    warn "skipped — no conflict task identified in check 4"
fi

# ── CHECK 6: LEARNINGS injection ──────────────────────────────────────────────
echo "[6] LEARNINGS injection: later tasks have non-empty lessons in prompt_preview"
injected=0
for timeline in "${LOGS_DIR}"/*/timeline.json; do
    [ -f "$timeline" ] || continue
    has_lessons=$(python3 -c "
import json
d = json.load(open('$timeline'))
for disp in d.get('dispatches', []):
    preview = disp.get('prompt_preview', '')
    if 'Relevant lessons' in preview or 'LEARNINGS' in preview:
        print('yes')
        break
else:
    print('no')
" 2>/dev/null)
    [ "$has_lessons" = "yes" ] && ((injected++))
done
if [ "$injected" -gt 0 ]; then
    pass "$injected task(s) had LEARNINGS.md lessons injected into prompt"
else
    fail "no task had LEARNINGS injection — extract_relevant_lessons may be empty"
fi

# ── CHECK 7: ccm reflect produced rules ───────────────────────────────────────
echo "[7] ccm reflect: CLAUDE.md has non-empty ## Learned Rules section"
if [ -f "$CLAUDE_MD" ]; then
    rules_content=$(python3 -c "
content = open('$CLAUDE_MD').read()
marker = '## Learned Rules'
if marker in content:
    after = content.split(marker, 1)[1].strip()
    # Check for any non-empty bullet or line
    lines = [l.strip() for l in after.splitlines() if l.strip() and l.strip() != '---']
    print('yes' if lines else 'no')
else:
    print('no')
" 2>/dev/null)
    if [ "$rules_content" = "yes" ]; then
        pass "CLAUDE.md ## Learned Rules section has content"
    else
        fail "CLAUDE.md ## Learned Rules is empty — ccm reflect did not run or produced nothing"
    fi
else
    fail "CLAUDE.md not found"
fi

# ── CHECK 8: token audit ──────────────────────────────────────────────────────
echo "[8] Token audit: all dispatches have input_tokens > 0"
zero_token_tasks=0
total_dispatches=0
for timeline in "${LOGS_DIR}"/*/timeline.json; do
    [ -f "$timeline" ] || continue
    result=$(python3 -c "
import json
d = json.load(open('$timeline'))
total = 0
zero = 0
for disp in d.get('dispatches', []):
    total += 1
    if disp.get('input_tokens', 0) == 0:
        zero += 1
print(total, zero)
" 2>/dev/null)
    t=$(echo "$result" | awk '{print $1}')
    z=$(echo "$result" | awk '{print $2}')
    total_dispatches=$((total_dispatches + ${t:-0}))
    zero_token_tasks=$((zero_token_tasks + ${z:-0}))
done
if [ "$total_dispatches" -eq 0 ]; then
    fail "no dispatches found"
elif [ "$zero_token_tasks" -eq 0 ]; then
    pass "all $total_dispatches dispatches have input_tokens > 0"
else
    fail "$zero_token_tasks/$total_dispatches dispatches have input_tokens=0 (API cost tracking broken)"
fi

# ── CHECK 9: cost sanity ──────────────────────────────────────────────────────
echo "[9] Cost sanity: total experiment cost is non-zero"
total_cost=$(python3 -c "
import json, glob
cost = 0.0
for f in glob.glob('${LOGS_DIR}/*/timeline.json'):
    try:
        d = json.load(open(f))
        for disp in d.get('dispatches', []):
            cost += disp.get('estimated_cost_usd', 0)
    except Exception:
        pass
print(f'{cost:.4f}')
" 2>/dev/null)
if python3 -c "import sys; sys.exit(0 if float('${total_cost:-0}') > 0 else 1)" 2>/dev/null; then
    pass "total experiment cost: \$${total_cost}"
else
    fail "total cost is \$0.0000 — cost extraction may be broken"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "=== Verification Summary ==="
echo -e "  ${c_green}PASS${c_reset}: $PASS"
echo -e "  ${c_red}FAIL${c_reset}: $FAIL"
echo ""

if [ "$FAIL" -gt 0 ]; then
    echo "Some checks failed. Review docs/experiment-log.md for next iteration hypotheses."
    exit 1
else
    echo "All checks passed. Update docs/experiment-log.md with results."
    exit 0
fi
