#!/usr/bin/env bash
# Thin wrapper → the cross-platform Python launcher (run_all.py).
# Kept so existing Linux/macOS muscle memory works. The real logic is portable.
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PYTHON:-python3}"
exec "$PY" "$ROOT/run_all.py" "$@"
