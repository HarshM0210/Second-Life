#!/usr/bin/env bash
# Stop all services started by run_all.sh.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$ROOT/.pids"

if [ ! -f "$PID_FILE" ]; then
  echo "No .pids file found; nothing to stop."
  exit 0
fi

while IFS=: read -r name pid; do
  [ -z "${pid:-}" ] && continue
  if kill -0 "$pid" 2>/dev/null; then
    echo "  stopping ${name} (pid ${pid})"
    kill "$pid" 2>/dev/null
    # uvicorn spawns the server in the same process; give it a moment, then force.
    ( sleep 3; kill -9 "$pid" 2>/dev/null ) &
  fi
done < "$PID_FILE"

# Also sweep any uvicorn children still bound to our ports.
for port in 8000 8001 8002 8003 8005 8080; do
  pids=$(lsof -ti tcp:"$port" 2>/dev/null || true)
  [ -n "$pids" ] && kill $pids 2>/dev/null && echo "  freed port ${port}"
done

: > "$PID_FILE"
echo "All services stopped."
