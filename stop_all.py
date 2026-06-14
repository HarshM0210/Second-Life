#!/usr/bin/env python3
"""Cross-platform shutdown for the Second Life Commerce pipeline.

Reads ``.pids.json`` written by ``run_all.py`` and terminates each process tree
in an OS-appropriate way:

  * Windows  ->  ``taskkill /F /T /PID`` (kills the whole child tree)
  * POSIX    ->  ``os.killpg`` on the session group (uvicorn + reload workers)

No ``lsof`` or shell required.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PID_FILE = ROOT / ".pids.json"
IS_WINDOWS = os.name == "nt"


def _kill(pid: int) -> None:
    if IS_WINDOWS:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                       capture_output=True)
        return
    # POSIX: try the whole process group first, then the bare pid.
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass
    except Exception:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass


def main() -> int:
    if not PID_FILE.exists():
        print("No .pids.json found; nothing to stop.")
        return 0

    try:
        procs: dict[str, int] = json.loads(PID_FILE.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"Could not read {PID_FILE}: {exc}")
        return 1

    for name, pid in procs.items():
        print(f"  stopping {name} (pid {pid})")
        _kill(int(pid))

    PID_FILE.unlink(missing_ok=True)
    print("All services stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
