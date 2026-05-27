"""
ocr_worker/run.py
~~~~~~~~~~~~~~~~~
Entrypoint script for the OCR Worker service.
Supports running multiple worker threads and handles SIGINT/SIGTERM gracefully.
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import threading
import time

# Ensure project root is in path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.config import settings
from ocr_worker.processor import OCRProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
log = logging.getLogger("ocr_worker")


def main():
    log.info("=" * 60)
    log.info("  ANPR.OS — Starting OCR Worker Service")
    log.info("=" * 60)

    # Load configurations
    worker_count = getattr(settings, "OCR_WORKER_COUNT", 1)
    log.info("Starting %d OCR processor thread(s)...", worker_count)

    processors: list[OCRProcessor] = []
    threads: list[threading.Thread] = []

    # Shutdown flag/lock
    shutdown_event = threading.Event()

    def handle_shutdown(signum, frame):
        log.info("Received signal %d. Shutting down OCR workers...", signum)
        shutdown_event.set()
        for p in processors:
            p.stop()

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Start workers
    for i in range(worker_count):
        proc = OCRProcessor()
        processors.append(proc)
        t = threading.Thread(
            target=proc.start,
            name=f"OCRWorkerThread-{i+1}",
            daemon=True,
        )
        t.start()
        threads.append(t)
        log.info("Started thread %s", t.name)

    log.info("OCR Worker Service fully started. Press Ctrl+C to exit.")

    # Keep main thread alive until shutdown event is set
    try:
        while not shutdown_event.is_set():
            # Check if any threads died
            for t in threads:
                if not t.is_alive() and not shutdown_event.is_set():
                    log.error("Worker thread %s died unexpectedly!", t.name)
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass

    log.info("OCR Worker Service stopped.")


if __name__ == "__main__":
    main()
