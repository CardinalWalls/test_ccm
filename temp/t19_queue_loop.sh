#!/usr/bin/env bash
set -euo pipefail

TASK_FILE="tasks.json"
LOG_FILE="temp/T19_loop.log"
: > "$LOG_FILE"

while true; do
  NEXT_ID=$(jq -r '.[] | select(.status=="pending") | .id' "$TASK_FILE" | head -1)
  if [[ -z "${NEXT_ID:-}" ]]; then
    echo "QUEUE_EMPTY -> EXIT" | tee -a "$LOG_FILE"
    break
  fi

  NEXT_TASK=$(jq -r ".[] | select(.id==$NEXT_ID) | .task" "$TASK_FILE")
  echo "RUN task_id=$NEXT_ID task=[$NEXT_TASK]" | tee -a "$LOG_FILE"

  timeout 180 npx claude -p "$NEXT_TASK" --dangerously-skip-permissions </dev/null > "temp/T19_task_${NEXT_ID}_stdout.txt" 2> "temp/T19_task_${NEXT_ID}_stderr.txt"

  tmpfile=$(mktemp)
  jq "map(if .id==$NEXT_ID then .status=\"done\" else . end)" "$TASK_FILE" > "$tmpfile"
  mv "$tmpfile" "$TASK_FILE"

  echo "DONE task_id=$NEXT_ID" | tee -a "$LOG_FILE"
done
