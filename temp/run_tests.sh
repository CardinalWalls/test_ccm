#!/bin/bash
# Run best-practice tests and record exit codes. Timeout 90s per test.
cd /home/indows/claude-learning
TO=90
run() {
  local id=$1
  shift
  echo "=== $id START ==="
  timeout $TO npx claude "$@" 2>&1 | tee "temp/${id}.out"
  echo "=== $id EXIT:${PIPESTATUS[0]} ==="
}

run T1 -p "Say hello in one sentence"
run T2 -p "Return a JSON object with key greeting and value hello" --output-format json
run T3 -p "Describe this project in structured form" --output-format json --json-schema '{"type":"object","properties":{"title":{"type":"string"},"steps":{"type":"array","items":{"type":"string"}}},"required":["title","steps"]}'
run T4 -p "List 3 programming languages" --output-format stream-json --verbose
# T5: max-turns not in CLI help; skip or use max-budget
run T5 -p "Count from 1 to 5" --max-budget-usd 0.01
run T6 -p "Read TASK.md and output an implementation plan" --permission-mode plan --tools "Read,Grep,Glob" --output-format json --json-schema '{"type":"object","properties":{"title":{"type":"string"},"steps":{"type":"array","items":{"type":"string"}},"risks":{"type":"array","items":{"type":"string"}}},"required":["title","steps"]}'
run T7 -p "Read package.json and tell me the dependencies" --allowedTools "Read,Glob"
run T8 -p "echo hello from claude" --dangerously-skip-permissions
run T9 -p "What files are in this project?" --output-format stream-json --verbose --include-partial-messages 2>/dev/null
echo "=== DONE ==="
