#!/usr/bin/env python3
"""Start Celery worker with optimized configuration.

Usage:
    python scripts/start_worker.py                    # Default: gevent pool, 50 concurrency
    python scripts/start_worker.py --solo             # Solo mode for debugging
    python scripts/start_worker.py --concurrency 20   # Custom concurrency
    python scripts/start_worker.py --prefork          # Prefork pool (for CPU-bound tasks)
    python scripts/start_worker.py --threads          # Threads pool (Windows-compatible)

Windows Compatibility Notes:
============================
Celery dropped Windows support in version 4. The prefork pool does NOT work on Windows
because Windows doesn't support process forking (only spawning).

Recommended Windows options:
1. --solo     : Single-threaded, reliable, good for debugging (spawn multiple workers for parallelism)
2. --threads  : Uses OS threads, good for I/O-bound tasks, stable on Windows
3. --gevent   : Uses greenlets, works on Windows but may have issues with Python 3.11+
                (fix: pip install greenlet>=3.0)

For production-like development on Windows, consider:
- Docker Desktop with Linux containers
- WSL2 (Windows Subsystem for Linux)

Pool Performance Characteristics:
=================================
- gevent (default): Best for I/O-bound tasks (API calls, database queries). High concurrency with low overhead.
- threads: Good for I/O-bound tasks. Uses OS threads, affected by GIL for CPU work.
- prefork: Best for CPU-bound tasks. Uses separate processes. NOT available on Windows.
- solo: Single-threaded. No concurrency. Use for debugging or spawn multiple workers.
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
        help="Use prefork pool (for CPU-bound tasks, NOT available on Windows)",
    )
    parser.add_argument(
        "--threads",
        action="store_true",
        help="Use threads pool (Windows-compatible, good for I/O-bound tasks)",
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
        # Warn about Windows incompatibility
        if sys.platform == "win32":
            print("WARNING: Prefork pool does NOT work on Windows!")
            print("         Use --threads or --solo instead, or use Docker/WSL2.")
            print("-" * 60)
        print(f"Starting worker with PREFORK pool ({concurrency} processes)")
    elif args.threads:
        pool = "threads"
        concurrency = min(args.concurrency, 20)  # Reasonable default for threads
        print(f"Starting worker with THREADS pool ({concurrency} threads)")
        print("  - Windows-compatible, good for I/O-bound tasks")
    else:
        pool = "gevent"
        concurrency = args.concurrency
        print(f"Starting worker with GEVENT pool ({concurrency} greenlets)")
        if sys.platform == "win32":
            print("  - If you see issues on Windows, try: pip install greenlet>=3.0")
            print("  - Or use --threads for better Windows compatibility")

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
