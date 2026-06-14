#!/usr/bin/env python3
"""Cross-platform launcher for the Second Life Commerce pipeline.

Starts all five module services plus the orchestrator gateway, each from its own
working directory on its aligned port, using the **same** Python interpreter that
runs this script (``sys.executable``) — so it works identically on Linux, macOS,
and Windows with no bash, no ``lsof``, and no ``python`` vs ``python3`` ambiguity.

    Module 1  Grading / Fraud / Quality   :8000      Module 4  Green Coin   :8002
    Module 2  Recommend (+ Customer Prof) :8001      Module 3  Prevention  :8003
    Module 5  P2P Exchange                :8005      Gateway               :8080

Usage:
    python run_all.py        # start everything, wait for health, then detach
    python stop_all.py       # stop everything (reads .pids.json)

The web UI is started separately:  cd webapp && npm run dev
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "logs"
PID_FILE = ROOT / ".pids.json"
IS_WINDOWS = os.name == "nt"

# name, working dir (relative to ROOT), uvicorn app target, port, health probe
SERVICES = [
    ("module1_grading", "Module 1/backend", "app.main:app", 8000, ("GET", "/health", (200,))),
    ("module2_recommend", "Module-2", "recommend.service:app", 8001, ("GET", "/health", (200,))),
    ("module4_greencoin", "Module-4", "green_coin.main:app", 8002, ("GET", "/health", (200,))),
    # Module 3 exposes no /health; a 422 from risk-score proves it is up.
    ("module3_prevention", "Module 3", "return_prevention.main:app", 8003,
     ("POST", "/api/v1/risk-score", (200, 422))),
    ("module5_p2p", "Module-5", "p2p.service:app", 8005, ("GET", "/health", (200,))),
    ("gateway", ".", "orchestrator.gateway:app", 8080, ("GET", "/health", (200,))),
]

HEALTH_TIMEOUT_SECONDS = 120


def _port_in_use(port: int) -> bool:
    """Cross-platform check (no lsof): can we connect to the port locally?"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _spawn(name: str, cwd: str, app: str, port: int) -> subprocess.Popen:
    env = os.environ.copy()
    env.setdefault("CUSTOMER_PROFILE_BASE_URL", "http://localhost:8001")
    env.setdefault("GREEN_COIN_BASE_URL", "http://localhost:8002")
    # Repo root on PYTHONPATH so the gateway's `orchestrator` package resolves
    # regardless of platform; harmless for the module services.
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    # Force UTF-8 I/O in children (Windows defaults to cp1252 and chokes on ₹/emoji).
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    log_path = LOG_DIR / f"{name}.log"
    log = open(log_path, "w", encoding="utf-8")

    cmd = [sys.executable, "-m", "uvicorn", app,
           "--host", "127.0.0.1", "--port", str(port)]

    kwargs: dict = dict(cwd=str(ROOT / cwd), env=env, stdout=log,
                        stderr=subprocess.STDOUT)
    if IS_WINDOWS:
        # New process group so taskkill /T can tear down the whole tree.
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    else:
        # New session so we can signal the whole group on POSIX.
        kwargs["start_new_session"] = True

    return subprocess.Popen(cmd, **kwargs)


def _probe(port: int, method: str, path: str, expect: tuple[int, ...]) -> bool:
    url = f"http://127.0.0.1:{port}{path}"
    req = urllib.request.Request(url, method=method)
    if method == "POST":
        req.data = b"{}"
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status in expect
    except urllib.error.HTTPError as exc:
        return exc.code in expect
    except Exception:
        return False


def main() -> int:
    LOG_DIR.mkdir(exist_ok=True)

    # Pre-flight: refuse to start if any target port is already in use, so a stale
    # server can't masquerade as a healthy launch. (Cross-platform; no lsof.)
    busy = [port for _, _, _, port, _ in SERVICES if _port_in_use(port)]
    if busy:
        print("Ports already in use: " + ", ".join(str(p) for p in busy))
        print("Another instance may be running. Stop it first:")
        print(f"    {Path(sys.executable).name} stop_all.py")
        return 1

    procs: dict[str, int] = {}

    print("Starting Second Life Commerce services...")
    handles = {}
    for name, cwd, app, port, _ in SERVICES:
        print(f"  starting {name} on :{port}  (cwd: {cwd})")
        p = _spawn(name, cwd, app, port)
        handles[name] = p
        procs[name] = p.pid

    PID_FILE.write_text(json.dumps(procs, indent=2), encoding="utf-8")

    print("\nWaiting for services to become healthy "
          f"(up to {HEALTH_TIMEOUT_SECONDS}s; ML models load lazily)...")
    deadline = time.time() + HEALTH_TIMEOUT_SECONDS
    pending = {(name, port, probe) for name, _, _, port, probe in SERVICES}
    healthy: set[str] = set()

    while pending and time.time() < deadline:
        for item in list(pending):
            name, port, (method, path, expect) = item
            # If the process died, report and stop waiting on it.
            if handles[name].poll() is not None:
                print(f"  [FAIL] {name} exited early — see {LOG_DIR / (name + '.log')}")
                pending.discard(item)
                continue
            if _probe(port, method, path, expect):
                print(f"  [OK] :{port} {name} healthy")
                healthy.add(name)
                pending.discard(item)
        if pending:
            time.sleep(1)

    for name, _, _, port, _ in SERVICES:
        if name not in healthy:
            print(f"  [WARN] :{port} {name} not healthy yet — check {LOG_DIR}")

    print(f"\nLaunched {len(procs)} processes. Logs: {LOG_DIR}{os.sep}  ·  PIDs: {PID_FILE}")
    print(f"Run the end-to-end demo:   {Path(sys.executable).name} -m orchestrator.run_demo")
    print("Start the web UI:          cd webapp && npm run dev")
    return 0 if len(healthy) == len(SERVICES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
