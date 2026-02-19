#!/usr/bin/env bash
# =============================================================================
# CCM Experiment Reset Script
# =============================================================================
# Purpose: Bring the repo to a clean, reproducible baseline before each
#          experiment run. Safe to call repeatedly.
#
# Usage:
#   bash scripts/reset.sh [--tag-only] [--no-push]
#
#   --tag-only   Only (re)tag EXPERIMENT_BASELINE, skip state/worktree cleanup.
#   --no-push    Don't push to remote (useful for offline iteration).
#
# What this does:
#   1. Resets main branch to EXPERIMENT_BASELINE tag (if it exists).
#   2. Clears all experiment state: dev-tasks.json, LEARNINGS.md, PROGRESS.md,
#      plans/, logs/.
#   3. Removes all task worktrees from ../claude-learning-worktrees/.
#   4. Restores seed source files from git HEAD.
#   5. Tags EXPERIMENT_BASELINE at current HEAD and pushes.
# =============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKTREE_ROOT="${REPO_ROOT}/../$(basename "${REPO_ROOT}")-worktrees"
TAG_ONLY=0
NO_PUSH=0

for arg in "$@"; do
    case "$arg" in
        --tag-only) TAG_ONLY=1 ;;
        --no-push)  NO_PUSH=1 ;;
        *) echo "Unknown argument: $arg" >&2; exit 1 ;;
    esac
done

cd "$REPO_ROOT"

echo "=== CCM Experiment Reset ==="
echo "Repo: $REPO_ROOT"
echo ""

# ── 1. Remove all task worktrees ──────────────────────────────────────────────
if [ "$TAG_ONLY" -eq 0 ]; then
    echo "[1/5] Cleaning worktrees..."
    # Remove via git worktree first (safe)
    while IFS= read -r wt_path; do
        if [[ "$wt_path" == *"-worktrees/"* ]]; then
            echo "  removing worktree: $wt_path"
            git worktree remove --force "$wt_path" 2>/dev/null || true
        fi
    done < <(git worktree list --porcelain | grep "^worktree " | awk '{print $2}')
    # Remove leftover directories
    if [ -d "$WORKTREE_ROOT" ]; then
        rm -rf "$WORKTREE_ROOT"
        echo "  removed $WORKTREE_ROOT"
    fi
    # Clean up dangling task branches
    git branch | grep "task/" | xargs git branch -D 2>/dev/null || true
    echo "  worktrees clean"
fi

# ── 2. Clear experiment state files ──────────────────────────────────────────
if [ "$TAG_ONLY" -eq 0 ]; then
    echo "[2/5] Clearing experiment state..."
    echo '[]' > data/dev-tasks.json
    echo '# LEARNINGS.md' > LEARNINGS.md
    printf '' > PROGRESS.md
    rm -rf plans/ logs/
    mkdir -p plans logs
    echo "  state files reset"
fi

# ── 3. Restore seed source files ─────────────────────────────────────────────
if [ "$TAG_ONLY" -eq 0 ]; then
    echo "[3/5] Restoring seed source files..."
    git checkout HEAD -- \
        src/math.ts \
        src/greet.ts \
        tests/math.test.ts \
        tests/greet.test.ts \
        2>/dev/null || true
    echo "  seed files restored"
fi

# ── 4. Commit reset state ─────────────────────────────────────────────────────
if [ "$TAG_ONLY" -eq 0 ]; then
    echo "[4/5] Committing reset state..."
    git add -A
    if git diff --cached --quiet; then
        echo "  nothing to commit (already clean)"
    else
        git commit -m "chore(reset): clean experiment baseline $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    fi
fi

# ── 5. Tag EXPERIMENT_BASELINE ───────────────────────────────────────────────
echo "[5/5] Tagging EXPERIMENT_BASELINE..."
git tag -f EXPERIMENT_BASELINE HEAD
echo "  tagged EXPERIMENT_BASELINE at $(git rev-parse --short HEAD)"

if [ "$NO_PUSH" -eq 0 ]; then
    git push origin main 2>/dev/null || true
    git push origin EXPERIMENT_BASELINE --force 2>/dev/null || true
    echo "  pushed to origin"
else
    echo "  (--no-push: skipped remote push)"
fi

echo ""
echo "=== Reset complete. Ready for next experiment run. ==="
echo ""
echo "Next steps:"
echo "  conda activate base && ccm init ."
echo "  ccm add --title '...' '...'"
echo "  ccm plan --workers 3"
echo "  ccm run --workers 2"
echo "  ccm worklog && ccm reflect && ccm status"
echo "  bash scripts/verify.sh"
