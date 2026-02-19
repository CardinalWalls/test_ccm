#!/bin/bash
# Round 2: test plain -p and json modes with 180s timeout
LOG="/home/indows/claude-learning/.cursor/debug-88e97e.log"
cd /home/indows/claude-learning

log_event() {
  local hyp="$1" msg="$2" data="$3"
  echo "{\"sessionId\":\"88e97e\",\"timestamp\":$(date +%s%3N),\"location\":\"debug_test2.sh\",\"message\":\"$msg\",\"data\":$data,\"runId\":\"run2\",\"hypothesisId\":\"$hyp\"}" >> "$LOG"
}

run_test() {
  local TESTID="$1"
  shift
  local T0=$(date +%s%3N)
  log_event "H1" "${TESTID}_start" "{\"args\":\"$*\"}"

  timeout 180 npx claude "$@" >temp/${TESTID}_stdout.txt 2>temp/${TESTID}_stderr.txt &
  local PID=$!

  # Poll every 10s
  for i in $(seq 1 18); do
    sleep 10
    local SOUT=$(wc -c < temp/${TESTID}_stdout.txt 2>/dev/null || echo 0)
    local SERR=$(wc -c < temp/${TESTID}_stderr.txt 2>/dev/null || echo 0)
    local EL=$(( $(date +%s%3N) - T0 ))
    log_event "H2" "${TESTID}_poll_${i}" "{\"stdout_bytes\":$SOUT,\"stderr_bytes\":$SERR,\"elapsed_ms\":$EL}"

    if ! kill -0 $PID 2>/dev/null; then
      wait $PID
      local EC=$?
      local TF=$(date +%s%3N)
      local SOUT_F=$(wc -c < temp/${TESTID}_stdout.txt 2>/dev/null || echo 0)
      local SERR_F=$(wc -c < temp/${TESTID}_stderr.txt 2>/dev/null || echo 0)
      local SOUT_H=$(head -c 500 temp/${TESTID}_stdout.txt 2>/dev/null | tr '\n' ' ' | tr '"' "'" | tr '\\' '/')
      local SERR_H=$(head -c 500 temp/${TESTID}_stderr.txt 2>/dev/null | tr '\n' ' ' | tr '"' "'" | tr '\\' '/')
      log_event "H1" "${TESTID}_done" "{\"exit_code\":$EC,\"total_ms\":$((TF-T0)),\"stdout_bytes\":$SOUT_F,\"stderr_bytes\":$SERR_F}"
      log_event "H5" "${TESTID}_stdout" "{\"head\":\"$SOUT_H\"}"
      log_event "H5" "${TESTID}_stderr" "{\"head\":\"$SERR_H\"}"
      return
    fi
  done

  log_event "H1" "${TESTID}_timeout_180s" "{\"killing\":true}"
  kill $PID 2>/dev/null; wait $PID 2>/dev/null
  local SOUT_H=$(head -c 500 temp/${TESTID}_stdout.txt 2>/dev/null | tr '\n' ' ' | tr '"' "'" | tr '\\' '/')
  local SERR_H=$(head -c 500 temp/${TESTID}_stderr.txt 2>/dev/null | tr '\n' ' ' | tr '"' "'" | tr '\\' '/')
  log_event "H5" "${TESTID}_stdout_at_kill" "{\"head\":\"$SOUT_H\"}"
  log_event "H5" "${TESTID}_stderr_at_kill" "{\"head\":\"$SERR_H\"}"
}

# Test A: plain text mode (simplest, like T1)
run_test "TA" -p "Reply with just the word OK"

# Test B: json output mode (like T2)
run_test "TB" -p "Return JSON with key greeting value hello" --output-format json

# Test C: stream-json WITH --verbose (correct flags, like T4)
run_test "TC" -p "Say hi" --output-format stream-json --verbose

log_event "H1" "all_done" "{}"
