#!/usr/bin/env python3
"""Start Celery worker with optimized configuration.

Usage:
    python scripts/start_worker.py                    # Default: gevent pool, 50 concurrency
    python scripts/start_worker.py --solo             # Solo mode for debugging
    python scripts/start_worker.py --concurrency 20  # Custom concurrency
    python scripts/start_worker.py --prefork         # Prefork pool (for CPU-bound tasks)
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Ensure we're in the backend directory
BACKEND_DIR = Path(__file__).parent.parent
os.chdir(BACKEND_DIR)

# Add backend to path for imports
sys.path.insert(0, str(BACKEND_DIR))


def main():
    parser = argparse.ArgumentParser(description="Start Celery worker with optimized settings")
    parser.add_argument(
        "--solo",
        action="store_true",
        help="Use solo pool (single-threaded, for debugging)",
    )
    parser.add_argument(
        "--prefork",
        action="store_true",
        help="Use prefork pool (for CPU-bound tasks)",
    )
    parser.add_argument(
        "--concurrency",
        "-c",
        type=int,
        default=50,
        help="Number of concurrent workers (default: 50 for gevent, 4 for prefork)",
    )
    parser.add_argument(
        "--loglevel",
        "-l",
        default="info",
        choices=["debug", "info", "warning", "error"],
        help="Log level (default: info)",
    )
    parser.add_argument(
        "--queues",
        "-Q",
        default="default,high,low",
        help="Queues to consume from (default: default,high,low)",
    )
    args = parser.parse_args()

    # Determine pool type
    if args.solo:
        pool = "solo"
        concurrency = 1
        print("Starting worker in SOLO mode (single-threaded, for debugging)")
    elif args.prefork:
        pool = "prefork"
        concurrency = min(args.concurrency, os.cpu_count() or 4)
        print(f"Starting worker with PREFORK pool ({concurrency} processes)")
    else:
        pool = "gevent"
        concurrency = args.concurrency
        print(f"Starting worker with GEVENT pool ({concurrency} greenlets)")

    # Build command
    cmd = [
        sys.executable, "-m", "celery",
        "-A", "app.workers.celery:celery_app",
        "worker",
        f"--loglevel={args.loglevel}",
        f"--pool={pool}",
        f"--concurrency={concurrency}",
        f"--queues={args.queues}",
    ]

    print(f"Command: {' '.join(cmd)}")
    print("-" * 60)

    # Execute
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\nWorker stopped.")
    except subprocess.CalledProcessError as e:
        print(f"Worker exited with error: {e.returncode}")
        sys.exit(e.returncode)


if __name__ == "__main__":
    main()
