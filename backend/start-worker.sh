#!/bin/bash
# Start Celery beat scheduler and TWO worker processes as background tasks.
# WPS-001 Phase 2: physical isolation of fast vs heavy queues.
#
#   beat         — periodic task scheduler (default PersistentScheduler)
#   fast worker  — default+llm queues, 40 greenlets  (API-facing, latency-sensitive)
#   heavy worker — heavy+low queues,   10 greenlets  (OCR, embedding, long-running)
#
# Traps SIGTERM/SIGINT (sent by Railway on deploy) and forwards to all three,
# giving workers time to finish in-flight tasks before exiting.
#
# Railway drain timeout should be set to 120s via Dashboard:
#   Settings → Deploy → Drain Timeout
# Celery warm shutdown finishes current tasks before exiting.
#
# Beat runs in a restart loop — if it crashes (e.g., transient Redis disconnect),
# it auto-recovers after 10 seconds. CELERY_BEAT_ONLY=true skips heavy task
# module imports (~1GB RAM savings — beat only needs schedule config, not task code).

# --- Graceful shutdown handler ---
cleanup() {
    echo "[shutdown] SIGTERM received, draining workers..."
    # Send TERM to all processes (Celery warm shutdown finishes in-flight tasks)
    for pid in $WORKER_FAST_PID $WORKER_HEAVY_PID $BEAT_PID; do
        if [ -n "$pid" ]; then
            kill -TERM $pid 2>/dev/null
        fi
    done
    # Wait for workers to drain (heavy tasks may take longer)
    for pid in $WORKER_FAST_PID $WORKER_HEAVY_PID $BEAT_PID; do
        if [ -n "$pid" ]; then
            wait $pid 2>/dev/null
        fi
    done
    echo "[shutdown] All workers drained, exiting"
    exit 0
}

trap cleanup SIGTERM SIGINT

# --- Start beat scheduler with auto-restart ---
# Uses Celery's default PersistentScheduler (local shelve file).
# Schedule is static config in celery.py — file loss on restart is harmless.
# CELERY_BEAT_ONLY=true makes celery.py skip heavy task module imports.
(
    trap 'exit 0' TERM
    while true; do
        CELERY_BEAT_ONLY=true celery -A app.workers.celery:celery_app beat \
            --loglevel=info \
            -s /tmp/celerybeat-schedule
        EXIT_CODE=$?
        echo "[beat] Beat exited with code $EXIT_CODE, restarting in 10s..."
        sleep 10
    done
) &
BEAT_PID=$!

# --- Start fast worker (default + llm queues) ---
# Handles: document validation, chunking, entity extraction, citations, dates
# 40 greenlets — high concurrency for quick API-bound tasks
celery -A app.workers.celery:celery_app worker \
    --loglevel=info \
    --pool=gevent \
    --concurrency=40 \
    --without-gossip \
    --without-mingle \
    --without-heartbeat \
    -n fast@%h \
    -Q default,llm &
WORKER_FAST_PID=$!

# --- Start heavy worker (heavy + low queues) ---
# Handles: OCR, embedding, large document processing
# 10 greenlets — fewer slots so heavy tasks don't exhaust memory/connections
celery -A app.workers.celery:celery_app worker \
    --loglevel=info \
    --pool=gevent \
    --concurrency=10 \
    --without-gossip \
    --without-mingle \
    --without-heartbeat \
    -n heavy@%h \
    -Q heavy,low &
WORKER_HEAVY_PID=$!

# Wait for either worker to exit (signal handler takes care of the rest)
wait $WORKER_FAST_PID $WORKER_HEAVY_PID
