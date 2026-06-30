#!/usr/bin/env bash
# run_all.sh
# Runs all 7 personas sequentially against the live Stride server.
# Stops the server, resets TinyDB data, restarts server between every persona.
# Run from the ROOT of the Stride project (not inside evaluation/).
#
# Usage:
#   bash evaluation/run_all.sh

set -euo pipefail

PERSONAS=(
    "amaka_eze"
    "tunde_bakare"
    "chiamaka_okafor"
    "ibrahim_suleiman"
    "blessing_nwachukwu"
    "daniel_whitfield"
    "margaret_sully"
)

SERVER_URL="http://localhost:8000"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
EVAL_DIR="$ROOT_DIR/evaluation"
DATA_DIR="$ROOT_DIR/data"
SERVER_PID=""

# ── Helpers ──────────────────────────────────────────────────────────────────

header() {
    echo ""
    echo "============================================================"
    echo "  $1"
    echo "============================================================"
}

stop_server() {
    echo "[server] Stopping uvicorn..."
    # Kill by port 8000 — works regardless of how it was started
    local pid
    pid=$(lsof -ti tcp:8000 2>/dev/null || true)
    if [ -n "$pid" ]; then
        kill "$pid" 2>/dev/null || true
        sleep 2
        echo "[server] Stopped (pid $pid)."
    else
        echo "[server] Nothing running on port 8000."
    fi
}

start_server() {
    echo "[server] Starting uvicorn..."
    cd "$ROOT_DIR"
    uvicorn main:app --reload &>/tmp/stride_server.log &
    SERVER_PID=$!
    echo "[server] Started (pid $SERVER_PID). Waiting for ready..."
    local attempts=0
    local max=20
    until curl -sf "$SERVER_URL/docs" -o /dev/null 2>/dev/null; do
        attempts=$((attempts + 1))
        if [ "$attempts" -ge "$max" ]; then
            echo "[server] Did not respond after $((max * 3))s. Check /tmp/stride_server.log"
            exit 1
        fi
        sleep 3
    done
    echo "[server] Server is up."
}

reset_data() {
    echo "[reset] Deleting TinyDB files..."
    if ls "$DATA_DIR"/*.json 1>/dev/null 2>&1; then
        rm -f "$DATA_DIR"/*.json
        echo "[reset] Deleted."
    else
        echo "[reset] data/ already empty."
    fi

    echo "[reset] Clearing __pycache__..."
    find "$ROOT_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

    # Confirm empty
    if ls "$DATA_DIR"/*.json 1>/dev/null 2>&1; then
        echo "[reset] FAILED — data/ still has files after delete:"
        ls "$DATA_DIR"/*.json
        exit 1
    fi
    echo "[reset] data/ confirmed empty."
}

# Ensure server is stopped if script exits for any reason
cleanup() {
    echo ""
    echo "[cleanup] Stopping server on exit..."
    stop_server
}
trap cleanup EXIT

# ── Main ─────────────────────────────────────────────────────────────────────

header "Stride Evaluation — All Personas"
echo "Personas: ${PERSONAS[*]}"
echo "Logs: evaluation/logs/<persona>/events.jsonl"

# Stop any existing server before we begin
stop_server

failed=()
passed=()

for persona in "${PERSONAS[@]}"; do
    header "Running: $persona"

    reset_data
    start_server

    set +e
    (cd "$EVAL_DIR" && python runner.py "$persona")
    exit_code=$?
    set -e

    stop_server

    if [ "$exit_code" -ne 0 ]; then
        echo ""
        echo "[FAIL] $persona exited with code $exit_code"
        echo "[halt] Stopping — fix the failure before continuing."
        failed+=("$persona")
        break
    else
        echo ""
        echo "[PASS] $persona completed."
        passed+=("$persona")
    fi

    # Brief pause between personas — Gemini free-tier rate limit buffer
    if [ "$persona" != "${PERSONAS[-1]}" ]; then
        echo "[pause] Waiting 15s before next persona..."
        sleep 15
    fi
done

# ── Summary ──────────────────────────────────────────────────────────────────

header "Run Complete"
echo "Passed : ${#passed[@]} — ${passed[*]:-none}"
if [ "${#failed[@]}" -gt 0 ]; then
    echo "Failed : ${#failed[@]} — ${failed[*]}"
    exit 1
fi
echo "All personas completed successfully."
exit 0