#!/bin/bash
cd /home/indows/claude-learning
LOG="/home/indows/claude-learning/.cursor/debug-88e97e.log"
TO=120

log_event() {
  echo "{\"sessionId\":\"88e97e\",\"timestamp\":$(date +%s%3N),\"location\":\"run_final_tests.sh\",\"message\":\"$1\",\"data\":$2,\"runId\":\"final\",\"hypothesisId\":\"verified\"}" >> "$LOG"
}

run_test() {
  local TID="$1"; shift
  local T0=$(date +%s%3N)
  timeout $TO npx claude "$@" </dev/null >temp/${TID}_stdout.txt 2>temp/${TID}_stderr.txt
  local EC=$?
  local T1=$(date +%s%3N)
  local MS=$((T1-T0))
  local SOUT=$(wc -c < temp/${TID}_stdout.txt 2>/dev/null || echo 0)
  local OUT_HEAD=$(head -c 400 temp/${TID}_stdout.txt 2>/dev/null | tr '\n' '|' | tr '"' "'" | tr '\\' '/')
  local ERR_HEAD=$(head -c 200 temp/${TID}_stderr.txt 2>/dev/null | tr '\n' '|' | tr '"' "'" | tr '\\' '/')
  log_event "${TID}" "{\"exit_code\":$EC,\"ms\":$MS,\"stdout_bytes\":$SOUT,\"stdout_head\":\"$OUT_HEAD\",\"stderr_head\":\"$ERR_HEAD\"}"
  echo "$TID: exit=$EC time=${MS}ms stdout=${SOUT}b"
}

echo "=== T1: Basic print mode ==="
run_test T1 -p "Say hello in one sentence"

echo "=== T2: JSON output ==="
run_test T2 -p "Return a JSON object with key greeting and value hello" --output-format json

echo "=== T3: JSON schema ==="
run_test T3 -p "Describe this project in structured form" \
  --output-format json \
  --json-schema '{"type":"object","properties":{"title":{"type":"string"},"steps":{"type":"array","items":{"type":"string"}}},"required":["title","steps"]}'

echo "=== T4: Stream-JSON ==="
run_test T4 -p "List 3 programming languages" \
  --output-format stream-json --verbose

echo "=== T5: Max budget (fuse) ==="
run_test T5 -p "Count from 1 to 5" --max-budget-usd 0.50

echo "=== T6: Plan mode + tools + schema ==="
run_test T6 -p "Read TASK.md and output an implementation plan" \
  --permission-mode plan \
  --tools "Read,Grep,Glob" \
  --output-format json \
  --json-schema '{"type":"object","properties":{"title":{"type":"string"},"steps":{"type":"array","items":{"type":"string"}},"risks":{"type":"array","items":{"type":"string"}}},"required":["title","steps"]}'

echo "=== T7: Allowed tools ==="
run_test T7 -p "Read package.json and tell me the dependencies" \
  --allowedTools "Read,Glob"

echo "=== T8: Dangerously skip permissions ==="
run_test T8 -p "echo hello from claude" --dangerously-skip-permissions

echo "=== T9: Stream-JSON verbose ==="
run_test T9 -p "What files are in this project?" \
  --output-format stream-json --verbose --include-partial-messages

echo "=== T10: Python subprocess ==="
T10_T0=$(date +%s%3N)
python3 -c "
import json, subprocess
cmd = ['npx', 'claude', '-p', 'Return a plan for testing', '--output-format', 'json',
       '--json-schema', json.dumps({'type':'object','properties':{'title':{'type':'string'},'steps':{'type':'array','items':{'type':'string'}}},'required':['title','steps']})]
out = subprocess.check_output(cmd, text=True, timeout=120, stdin=subprocess.DEVNULL)
plan = json.loads(out)
title = plan.get('result','no-result')[:100]
print('T10_OK:', len(out), 'bytes')
with open('temp/T10_stdout.txt','w') as f: f.write(out)
" 2>temp/T10_stderr.txt
T10_EC=$?
T10_T1=$(date +%s%3N)
T10_MS=$((T10_T1-T10_T0))
T10_RESULT=$(cat temp/T10_stdout.txt 2>/dev/null | head -c 300 | tr '\n' '|' | tr '"' "'" | tr '\\' '/')
log_event "T10" "{\"exit_code\":$T10_EC,\"ms\":$T10_MS,\"stdout_head\":\"$T10_RESULT\"}"
echo "T10: exit=$T10_EC time=${T10_MS}ms"

echo "=== ALL DONE ==="
