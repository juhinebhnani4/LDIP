#!/bin/bash
# Start Celery beat scheduler and worker as background processes.
# Traps SIGTERM/SIGINT (sent by Railway on deploy) and forwards to both,
# giving the worker time to finish in-flight tasks before exiting.
#
# Railway drain timeout should be set to 120s via Dashboard:
#   Settings → Deploy → Drain Timeout
# Celery warm shutdown finishes current tasks before exiting.
#
# Beat uses RedBeat (Redis-backed scheduler with distributed locking).
# Multiple replicas can each start beat — RedBeat's Redis lock ensures
# only one fires tasks at a time, with automatic failover if the leader dies.

# --- Graceful shutdown handler ---
cleanup() {
    echo "[shutdown] SIGTERM received, draining worker..."
    if [ -n "$WORKER_PID" ]; then
        kill -TERM $WORKER_PID 2>/dev/null
    fi
    if [ -n "$BEAT_PID" ]; then
        kill -TERM $BEAT_PID 2>/dev/null
    fi
    if [ -n "$WORKER_PID" ]; then
        wait $WORKER_PID 2>/dev/null
    fi
    if [ -n "$BEAT_PID" ]; then
        wait $BEAT_PID 2>/dev/null
    fi
    echo "[shutdown] Worker drained, exiting"
    exit 0
}

trap cleanup SIGTERM SIGINT

# --- Start beat scheduler (RedBeat handles leader election via Redis lock) ---
celery -A app.workers.celery:celery_app beat \
    --loglevel=info &
BEAT_PID=$!

# --- Start worker ---
celery -A app.workers.celery:celery_app worker \
    --loglevel=info \
    --pool=gevent \
    --concurrency=50 \
    --without-gossip \
    --without-mingle \
    --without-heartbeat \
    -Q default,llm,heavy,low &
WORKER_PID=$!

# Wait for worker (blocked until it exits or signal received)
wait $WORKER_PID
