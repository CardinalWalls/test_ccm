#!/usr/bin/env bash
set -euo pipefail

cd /home/indows/claude-learning

# Pre-flight: verify API responds (Routin pool may be depleted)
echo "Pre-flight: checking API..."
if ! timeout 45 npx claude -p "Reply: OK" </dev/null 2>/dev/null | grep -q .; then
  echo "WARNING: API check failed or timed out. Pool may be depleted. Proceeding anyway..."
fi

tmux kill-session -t agent-teams 2>/dev/null || true
tmux new-session -d -s agent-teams

PROMPT='Create an agent team with 3 teammates to implement features in parallel.
Read data/team-tasks.md for the task list.
Each teammate owns one task and its corresponding file.
Require plan approval before any teammate makes changes.
Use --dangerously-skip-permissions for all teammates.
When all tasks are done, clean up the team.'

# Use plain claude to avoid blocking "Yes I accept" bypass prompt in detached tmux.
# The prompt asks the lead to use bypass for teammates; lead spawn settings control that.
tmux send-keys -t agent-teams "cd /home/indows/claude-learning && claude" Enter
sleep 8
tmux send-keys -t agent-teams "$PROMPT" Enter

echo "Agent team session started in tmux."
echo "Attach with: tmux attach -t agent-teams"
echo "Monitor with: tmux capture-pane -t agent-teams -p"
