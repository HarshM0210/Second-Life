#!/usr/bin/env bash
# Thin wrapper → the cross-platform Python stopper (stop_all.py).
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PYTHON:-python3}"
exec "$PY" "$ROOT/stop_all.py" "$@"
