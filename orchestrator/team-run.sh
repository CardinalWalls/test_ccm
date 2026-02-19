#!/usr/bin/env bash
set -euo pipefail

cd /home/indows/claude-learning

tmux kill-session -t agent-teams 2>/dev/null || true
tmux new-session -d -s agent-teams

PROMPT='Create an agent team with 3 teammates to implement features in parallel.
Read data/team-tasks.md for the task list.
Each teammate owns one task and its corresponding file.
Require plan approval before any teammate makes changes.
Use --dangerously-skip-permissions for all teammates.
When all tasks are done, clean up the team.'

tmux send-keys -t agent-teams "claude --dangerously-skip-permissions" Enter
sleep 5
tmux send-keys -t agent-teams "$PROMPT" Enter

echo "Agent team session started in tmux."
echo "Attach with: tmux attach -t agent-teams"
echo "Monitor with: tmux capture-pane -t agent-teams -p"
