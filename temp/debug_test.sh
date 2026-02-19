#!/bin/bash
# Instrumented test to diagnose why `claude -p` times out
LOG="/home/indows/claude-learning/.cursor/debug-88e97e.log"

log_event() {
  local hyp="$1" msg="$2" data="$3"
  echo "{\"sessionId\":\"88e97e\",\"timestamp\":$(date +%s%3N),\"location\":\"debug_test.sh\",\"message\":\"$msg\",\"data\":$data,\"runId\":\"run1\",\"hypothesisId\":\"$hyp\"}" >> "$LOG"
}

# H4: measure npx startup time
log_event "H4" "script_start" "{\"pwd\":\"$(pwd)\"}"

# H4: time just --version (no API call)
T0=$(date +%s%3N)
VER=$(npx claude --version 2>&1)
T1=$(date +%s%3N)
STARTUP_MS=$((T1 - T0))
log_event "H4" "version_complete" "{\"version\":\"$VER\",\"startup_ms\":$STARTUP_MS}"

# H1/H2/H3/H5: run actual -p command with 180s timeout, capture exit code and output size
T2=$(date +%s%3N)
log_event "H1" "api_call_start" "{\"command\":\"claude -p hi\"}"

# Use --output-format stream-json to see if ANY data arrives before full completion (H2)
timeout 180 npx claude -p "Reply with just OK" --output-format stream-json 2>temp/debug_stderr.txt >temp/debug_stdout.txt &
PID=$!
log_event "H2" "process_spawned" "{\"pid\":$PID}"

# Poll every 5s to see if output file grows (H2: buffering vs streaming)
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36; do
  sleep 5
  STDOUT_SIZE=$(wc -c < temp/debug_stdout.txt 2>/dev/null || echo 0)
  STDERR_SIZE=$(wc -c < temp/debug_stderr.txt 2>/dev/null || echo 0)
  ELAPSED=$(( $(date +%s%3N) - T2 ))
  log_event "H2" "poll_${i}" "{\"stdout_bytes\":$STDOUT_SIZE,\"stderr_bytes\":$STDERR_SIZE,\"elapsed_ms\":$ELAPSED}"
  
  # Check if process is still running
  if ! kill -0 $PID 2>/dev/null; then
    wait $PID
    EXIT_CODE=$?
    T3=$(date +%s%3N)
    TOTAL_MS=$((T3 - T2))
    STDOUT_FINAL=$(wc -c < temp/debug_stdout.txt 2>/dev/null || echo 0)
    STDERR_FINAL=$(wc -c < temp/debug_stderr.txt 2>/dev/null || echo 0)
    STDOUT_HEAD=$(head -c 500 temp/debug_stdout.txt 2>/dev/null | tr '\n' ' ' | tr '"' "'")
    STDERR_HEAD=$(head -c 500 temp/debug_stderr.txt 2>/dev/null | tr '\n' ' ' | tr '"' "'")
    log_event "H1" "api_call_done" "{\"exit_code\":$EXIT_CODE,\"total_ms\":$TOTAL_MS,\"stdout_bytes\":$STDOUT_FINAL,\"stderr_bytes\":$STDERR_FINAL}"
    log_event "H5" "output_content" "{\"stdout_head\":\"$STDOUT_HEAD\",\"stderr_head\":\"$STDERR_HEAD\"}"
    log_event "H3" "exit_analysis" "{\"exit_code\":$EXIT_CODE,\"had_output\":$([ $STDOUT_FINAL -gt 0 ] && echo true || echo false)}"
    break
  fi
done

# If still running after 180s
if kill -0 $PID 2>/dev/null; then
  log_event "H1" "still_running_after_180s" "{\"killing\":true}"
  kill $PID 2>/dev/null
  wait $PID 2>/dev/null
fi

log_event "H1" "script_end" "{}"
