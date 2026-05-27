"""
scripts/start_all.py
~~~~~~~~~~~~~~~~~~~~~
Process manager — starts the Backend API and OCR Service simultaneously.

Usage:
    python scripts/start_all.py

Ctrl+C to stop all services.
"""

import os
import sys
import signal
import subprocess
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
log = logging.getLogger("start_all")

# Resolve project root
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(ROOT)

# Determine Python interpreter
PYTHON = sys.executable

# Service definitions
SERVICES = [
    {
        "name": "OCR Service",
        "command": [PYTHON, "-m", "uvicorn", "ocr_service:app",
                    "--host", "127.0.0.1", "--port", "8001",
                    "--log-level", "warning"],
        "process": None,
    },
    {
        "name": "OCR Worker",
        "command": [PYTHON, "-m", "ocr_worker.run"],
        "process": None,
    },
    {
        "name": "Backend API",
        "command": [PYTHON, "-m", "uvicorn", "backend.main:app",
                    "--host", "127.0.0.1", "--port", "8000",
                    "--reload", "--log-level", "info"],
        "process": None,
    },
]


def start_services():
    """Start all services as subprocesses."""
    log.info("=" * 60)
    log.info("  ANPR.OS — Starting All Services")
    log.info("=" * 60)

    # Check Redis connectivity
    try:
        import redis
        r = redis.Redis(host="localhost", port=6379, socket_connect_timeout=2)
        r.ping()
        log.info("Redis connectivity: OK")
    except Exception as e:
        log.critical("Redis is NOT running on localhost:6379! Please start Redis before running start_all.py. Error: %s", e)
        sys.exit(1)

    for svc in SERVICES:
        log.info("Starting: %s", svc["name"])
        log.info("  Command: %s", " ".join(svc["command"]))
        try:
            svc["process"] = subprocess.Popen(
                svc["command"],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            log.info("  PID: %d", svc["process"].pid)
        except Exception as e:
            log.error("Failed to start %s: %s", svc["name"], e)

    log.info("-" * 60)
    log.info("All services started. Press Ctrl+C to stop.")
    log.info("-" * 60)


def stop_services():
    """Stop all running services."""
    log.info("Stopping all services...")
    for svc in SERVICES:
        if svc["process"] and svc["process"].poll() is None:
            log.info("Stopping: %s (PID %d)", svc["name"], svc["process"].pid)
            svc["process"].terminate()
            try:
                svc["process"].wait(timeout=10)
            except subprocess.TimeoutExpired:
                log.warning("Force killing: %s", svc["name"])
                svc["process"].kill()
    log.info("All services stopped.")


def monitor_services():
    """Monitor services and log if any crash."""
    try:
        while True:
            for svc in SERVICES:
                if svc["process"] and svc["process"].poll() is not None:
                    exit_code = svc["process"].returncode
                    log.warning(
                        "%s exited with code %d — restarting...",
                        svc["name"], exit_code,
                    )
                    svc["process"] = subprocess.Popen(
                        svc["command"],
                        cwd=ROOT,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                    )
                    log.info("  Restarted %s (PID %d)", svc["name"], svc["process"].pid)
            time.sleep(5)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    # Handle Ctrl+C gracefully
    signal.signal(signal.SIGINT, lambda *_: None)

    start_services()

    try:
        monitor_services()
    except KeyboardInterrupt:
        pass
    finally:
        stop_services()
