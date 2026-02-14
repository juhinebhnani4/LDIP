#!/bin/bash
# Start Celery beat scheduler in background, then worker in foreground.
# -B flag is incompatible with gevent pool, so beat runs as a separate process.

celery -A app.workers.celery:celery_app beat --loglevel=info -s /tmp/celerybeat-schedule &
BEAT_PID=$!

# Trap signals to clean up beat when worker exits
trap "kill $BEAT_PID 2>/dev/null" EXIT

celery -A app.workers.celery:celery_app worker \
    --loglevel=info \
    --pool=gevent \
    --concurrency=50 \
    --without-gossip \
    --without-mingle \
    --without-heartbeat
