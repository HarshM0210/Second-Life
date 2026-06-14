#!/usr/bin/env bash
# Launch all 5 Second Life Commerce module services + the pipeline gateway,
# each from its own working directory on its aligned port.
#
#   Module 1 Grading        :8000      Module 4 Green Coin   :8002
#   Module 2 Recommend      :8001      Module 3 Prevention   :8003
#   Module 5 P2P            :8005      Gateway               :8080
#
# Usage:  ./run_all.sh          (start everything, wait for health)
#         ./stop_all.sh         (stop everything)
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PYTHON:-python3}"
LOG_DIR="$ROOT/logs"
PID_FILE="$ROOT/.pids"
mkdir -p "$LOG_DIR"
: > "$PID_FILE"

# Module 3 and the gateway must resolve sibling services; defaults already point
# at the aligned ports, but we export them explicitly for clarity/overrides.
export CUSTOMER_PROFILE_BASE_URL="${CUSTOMER_PROFILE_BASE_URL:-http://localhost:8001}"
export GREEN_COIN_BASE_URL="${GREEN_COIN_BASE_URL:-http://localhost:8002}"

start() {
  local name="$1" dir="$2" app="$3" port="$4" extra_pythonpath="$5"
  local log="$LOG_DIR/${name}.log"
  echo "  starting ${name} on :${port} (cwd: ${dir})"
  (
    cd "$ROOT/$dir" || exit 1
    if [ -n "$extra_pythonpath" ]; then export PYTHONPATH="$extra_pythonpath:${PYTHONPATH:-}"; fi
    exec "$PY" -m uvicorn "$app" --host 0.0.0.0 --port "$port" >"$log" 2>&1
  ) &
  echo "${name}:$!" >> "$PID_FILE"
}

echo "Starting Second Life Commerce services..."
start "module1_grading"    "Module 1/backend" "app.main:app"                 8000 ""
start "module2_recommend"  "Module-2"         "recommend.service:app"        8001 ""
start "module4_greencoin"  "Module-4"         "green_coin.main:app"          8002 ""
start "module3_prevention" "Module 3"         "return_prevention.main:app"   8003 ""
start "module5_p2p"        "Module-5"         "p2p.service:app"              8005 ""
start "gateway"            "."                "orchestrator.gateway:app"     8080 "$ROOT"

echo ""
echo "Waiting for services to become healthy (up to 90s; ML models load lazily)..."
declare -A HEALTH=(
  [8000]="/health" [8001]="/health" [8002]="/health" [8005]="/health" [8080]="/health"
)
deadline=$(( $(date +%s) + 90 ))
for port in 8000 8001 8002 8005 8080; do
  url="http://localhost:${port}${HEALTH[$port]}"
  until curl -fsS "$url" >/dev/null 2>&1; do
    if [ "$(date +%s)" -ge "$deadline" ]; then
      echo "  [WARN] :${port} not healthy yet — check $LOG_DIR"
      break
    fi
    sleep 1
  done
  curl -fsS "$url" >/dev/null 2>&1 && echo "  [OK] :${port} healthy"
done
# Module 3 exposes no /health; a 422 from risk-score proves it is up.
until curl -fsS -o /dev/null -X POST http://localhost:8003/api/v1/risk-score \
        -H 'content-type: application/json' -d '{}' --write-out '%{http_code}' 2>/dev/null \
        | grep -qE '422|200'; do
  [ "$(date +%s)" -ge "$deadline" ] && { echo "  [WARN] :8003 not healthy yet"; break; }
  sleep 1
done
echo "  [OK] :8003 (return prevention) responding"

echo ""
echo "All services launched. Logs: $LOG_DIR/  ·  PIDs: $PID_FILE"
echo "Run the end-to-end demo:  $PY -m orchestrator.run_demo"
