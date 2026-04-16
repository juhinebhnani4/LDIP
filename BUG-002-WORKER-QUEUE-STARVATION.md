# BUG-002: Worker Queue Starvation — Complete Engineering Plan

**Created**: 2026-03-02
**Status**: PLANNED (not yet implemented)
**Severity**: CRITICAL / SCALABILITY
**Estimated Effort**: Phases 1-4 (~45 min) | Phase 5 (~2-3 hours additional)

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Root Cause Analysis](#2-root-cause-analysis)
3. [Industry Research Summary](#3-industry-research-summary)
4. [Architecture Decision: 3 Approaches Compared](#4-architecture-decision)
5. [Implementation Plan (5 Phases)](#5-implementation-plan)
6. [Phase 1: Celery Config Tuning](#phase-1-celery-config-tuning)
7. [Phase 2: Dual Worker Process](#phase-2-dual-worker-process)
8. [Phase 3: Per-Matter Concurrency Cap](#phase-3-per-matter-concurrency-cap)
9. [Phase 4: Update All Dispatch Points](#phase-4-update-all-dispatch-points)
10. [Phase 5: Task Chunking with Manual Redis Counter](#phase-5-task-chunking)
11. [Files Affected (Complete List)](#files-affected)
12. [Database Migrations](#database-migrations)
13. [Industry Patterns Reference](#industry-patterns-reference)
14. [Verification Plan](#verification-plan)
15. [Rollback Plan](#rollback-plan)
16. [Sources](#sources)

---

## 1. Problem Statement

**Symptom**: New user uploads a document. It gets stuck at 42-70% for 10+ minutes because the worker is busy processing `entity_alias_resolution_batch` for another user's matter (`91a4a4db` — a matter with 35 documents and 8000+ entity mentions).

**Impact**: In production with multiple users, one large matter's document upload blocks ALL other users' processing. No concurrency isolation, no priority queue, no per-user fairness.

**Reproduction**: Upload a document as User A (large matter). While alias resolution runs, upload a document as User B. User B's tasks are queued behind User A's alias resolution.

---

## 2. Root Cause Analysis

### 2.1 Current Architecture

| Component | Value | Source |
|-----------|-------|--------|
| Worker replicas | 1 | `backend/railway.worker.toml:14` |
| Worker pool | gevent | `backend/start-worker.sh:43` |
| Concurrency | 50 greenlets | `backend/start-worker.sh:44` |
| Queues consumed | ALL 4 (default,llm,heavy,low) | `backend/start-worker.sh:48` |
| Prefetch multiplier | 4 | `backend/app/workers/celery.py:55` |
| resolve_aliases queue | llm | `backend/app/workers/celery.py:92` |
| resolve_aliases soft timeout | 1800s (30 min) | `backend/app/workers/tasks/document_tasks.py:4773` |
| resolve_aliases hard timeout | 1860s (31 min) | `backend/app/workers/tasks/document_tasks.py:4774` |
| Gemini concurrent limit | 3 | `backend/app/services/mig/entity_resolver.py:177` |
| Gemini batch size | 10 pairs | `backend/app/services/mig/entity_resolver.py:174` |
| Per-matter doc limit | 3 concurrent | `backend/app/core/config.py:326` |

### 2.2 Root Cause Chain

1. **Prefetch hoarding**: `worker_prefetch_multiplier=4` × `concurrency=50` = **200 tasks buffered** in worker memory. Worker grabs 200 tasks from Redis before processing. New tasks can't be picked up until buffer drains.

2. **No queue isolation**: Single worker consumes all 4 queues. `resolve_aliases` (routed to `llm` queue) competes directly with critical-path tasks like `embed_chunks` and `extract_entities` (also on `llm` queue).

3. **Long-running alias task**: For a matter with 1000 entities and 500 from the current document:
   - Phase 1 (similarity matching): O(500 × 1000) = 500K comparisons, ~5-10 seconds
   - Phase 2 (Gemini analysis): 50-200 medium-confidence pairs → 5-20 batches of 10 → 3 concurrent Gemini calls → 10-60 seconds per round → **5-30 minutes total**
   - Phase 3 (transitive closure): <1 second

4. **Per-matter limit doesn't help cross-matter**: `max_concurrent_docs_per_matter=3` only limits within one matter. User A's 3 documents running `resolve_aliases` still starve User B's entire pipeline.

### 2.3 Critical Discovery: Gevent Limitations

| Feature | With Prefork Pool | With Gevent Pool |
|---------|-------------------|------------------|
| `soft_time_limit` | Works (sends SIGUSR1) | **SILENTLY IGNORED** |
| `worker_max_tasks_per_child` | Works (restarts child process) | **NO-OP** (no child processes) |
| `worker_max_memory_per_child` | Works | **NO-OP** |
| Hard time limit | Works (sends SIGKILL) | **Only works if task yields to event loop** |
| CPU-bound work | Each child gets own process | **Blocks entire event loop** (all 50 greenlets) |

**Source**: [Celery Issue #1958](https://github.com/celery/celery/issues/1958), [Celery Gevent Pool Docs](https://docs.celeryq.dev/en/main/userguide/concurrency/gevent.html)

### 2.4 Why `resolve_aliases` is Slow

**File**: `backend/app/services/mig/entity_resolver.py`

Three-phase algorithm:

1. **Phase 1 — High Similarity (>0.85)**: Lines 763-813
   - For each source entity, calls `find_potential_aliases(entity, type_entities)`
   - Jaro-Winkler string similarity + name component matching
   - Pure CPU, no I/O
   - Incremental mode: only compares document entities against all matter entities (O(k×N))

2. **Phase 2 — Medium Similarity (0.60-0.85)**: Lines 815-889
   - Batches medium-confidence pairs into groups of `CONTEXT_ANALYSIS_BATCH_SIZE=10`
   - Creates `asyncio.Semaphore(ALIAS_CONCURRENT_LIMIT=3)` for throttling
   - Calls `analyze_batch_context()` for each batch → Gemini API call
   - Each Gemini call: 2-10 seconds (includes rate limiting, retries)
   - **This is the bottleneck**: 100 medium pairs = 10 batches × ~5s each = 50+ seconds
   - For large matters: 500+ medium pairs = 50 batches = **5-30 minutes**

3. **Phase 3 — Transitive Closure**: Lines 891-892
   - Union-Find algorithm over all edges
   - If A=B and B=C, create A=C edge
   - Pure CPU, <1 second

---

## 3. Industry Research Summary

### How Production Systems Solve This

| Company/Project | Pattern | Details |
|-----------------|---------|---------|
| **Sentry** | Dedicated workers per queue | Dozens of workers, each consuming specific queues. Long tasks on dedicated pools. |
| **Wolt** | Short tasks + queue isolation | "Short tasks are better than long ones." Route by type, multiple worker pools. |
| **Nautobot** | Dedicated Celery queues | Separate queues for `default`, `webhooks`, `custom_fields` with dedicated workers. |
| **Inngest** | 3-level tiered queue | Per-function queues → priority index → shared-nothing workers with weighted random selection. |
| **Holistics** | PostgreSQL SKIP LOCKED | Custom scheduler with per-tenant slot limits. |
| **AWS SQS** | Fair Queues (2025) | Native multi-tenant fairness with round-robin across message groups. |
| **Sidekiq** | Fair tenant gem | Track per-tenant activity, reroute heavy tenants to throttled queues. |

### Key Insights from Research

1. **Prefetch multiplier = 1 is the universal recommendation** for mixed short/long task workloads. Every Celery scaling guide says this. (Source: [Celery Optimizing Docs](https://docs.celeryq.dev/en/latest/userguide/optimizing.html))

2. **Dedicated workers per queue type is the industry standard**. Wolt, Sentry, Nautobot all use this pattern. Single worker consuming all queues is explicitly warned against in production guides.

3. **Task decomposition (fan-out/fan-in)** is the gold standard for long-running tasks. Break into 1-2 minute chunks using Celery chord or manual Redis counters.

4. **Per-tenant rate limiting** prevents "noisy neighbor" problem. Implemented via Redis counters or dynamic priority degradation.

5. **`-Ofair` is default since Celery 4.0** for prefork, but gevent behavior is less documented. Setting `worker_prefetch_multiplier=1` is more reliable.

---

## 4. Architecture Decision

### Three Approaches Evaluated

#### Approach 1: Config-Only Tuning (~15 min)
- Prefetch=1, reroute aliases to `low` queue, add rate limit
- **Impact**: Moderate (60-70% improvement)
- **Limitation**: Still single worker, no hard isolation

#### Approach 2: Dual Worker + Per-Matter Cap (~45 min) ← **RECOMMENDED MINIMUM**
- All of Approach 1 + two worker processes + Redis concurrency semaphore
- **Impact**: High (90%+ improvement)
- **Limitation**: Individual alias tasks still 10-30 min

#### Approach 3: Full Solution with Task Chunking (~3 hours) ← **LONG-TERM BEST**
- All of Approach 2 + decompose `resolve_aliases` into 2-min fan-out/fan-in batches
- **Impact**: Very high (99%+ improvement, true multi-tenant fairness)
- **Max task duration**: 30 min → 2 min

### Decision: Implement in Phases

Phases 1-4 ship the dual worker + per-matter cap (Approach 2).
Phase 5 adds task chunking (Approach 3) as a follow-up.

Each phase is independently deployable and provides incremental improvement.

---

## 5. Implementation Plan (5 Phases)

### Files Modified Summary

| # | File | Phases | Change Type |
|---|------|--------|-------------|
| 1 | `backend/app/workers/celery.py` | 1 | Config tuning |
| 2 | `backend/start-worker.sh` | 2 | Rewrite: dual worker |
| 3 | `backend/app/core/config.py` | 3 | New setting |
| 4 | `backend/app/services/distributed_lock.py` | 3 | New lock class |
| 5 | `backend/app/workers/tasks/document_tasks.py` | 1,3,4 | Task decorator + dispatch + concurrency guard |
| 6 | `backend/app/workers/tasks/maintenance_tasks.py` | 4 | Recovery dispatch queue |
| 7 | `backend/app/services/job_recovery.py` | 4 | Recovery dispatch queue |
| 8 | `backend/dispatch_queued_jobs.py` | 4 | Script dispatch queue |
| 9 | `backend/app/services/mig/entity_resolver.py` | 5 | Refactor for batch support |
| 10 | `backend/app/workers/tasks/document_tasks.py` | 5 | New fan-out/fan-in tasks |

### Database Migrations: NONE

All changes are worker infrastructure. No schema changes required.

---

## Phase 1: Celery Config Tuning

**File**: `backend/app/workers/celery.py`
**Effort**: 5 minutes

### Change 1.1: Reduce prefetch multiplier

**Line 55**:
```python
# BEFORE
worker_prefetch_multiplier=4,

# AFTER
worker_prefetch_multiplier=1,  # 1 per greenlet = 50 total buffered.
                                # Prevents task hoarding. Celery docs:
                                # "If you have long-duration tasks, set to 1."
                                # Previous: 4 × 50 = 200 tasks buffered — caused starvation.
```

**Why**: With prefetch=4, the worker pre-fetches 200 tasks from Redis. If many are long-running alias tasks, new short tasks from other users can't be picked up. With prefetch=1, the worker only buffers 50 tasks (1 per greenlet), so new tasks get interleaved as greenlets free up.

### Change 1.2: Re-route resolve_aliases to `low` queue

**Line 92**:
```python
# BEFORE
"app.workers.tasks.document_tasks.resolve_aliases": {"queue": "llm"},

# AFTER
"app.workers.tasks.document_tasks.resolve_aliases": {"queue": "low"},  # BUG-002: Decoupled from job chain — doesn't gate completion
```

**Why**: `resolve_aliases` is independent of the job completion chain (citations → contradictions → mark_job_completed). Moving it to `low` queue separates it from critical-path LLM tasks like `embed_chunks` and `extract_entities`.

### Change 1.3: Remove no-op gevent settings + add connection limit

**Lines 61-62** (REMOVE):
```python
# REMOVE — both are silently ignored with gevent pool (no child processes):
worker_max_tasks_per_child=1000,
worker_max_memory_per_child=400000,
```

**Add** (after line 56):
```python
broker_pool_limit=10,  # Cap Redis connections per worker process (~7 needed with gossip disabled)
```

**Why**: `worker_max_tasks_per_child` and `worker_max_memory_per_child` only work with prefork pool. With gevent, they create false confidence — you think you have memory protection, but you don't. Removing them makes the limitation explicit. `broker_pool_limit=10` caps Redis connections (important when running 2 workers = ~17 total connections).

### Change 1.4: Update comments

**Lines 52-56**: Update the comment block to reflect new settings:
```python
# Worker settings — gevent pool for I/O-bound tasks (LLM API calls)
# prefetch_multiplier=1: fetch 1 task per greenlet. Prevents task hoarding
# that causes queue starvation when long-running tasks (alias resolution)
# occupy the buffer. See BUG-002 for details.
worker_prefetch_multiplier=1,
worker_concurrency=50,
broker_pool_limit=10,
```

---

## Phase 2: Dual Worker Process

**File**: `backend/start-worker.sh`
**Effort**: 15 minutes

### Full Rewrite

```bash
#!/bin/bash
# Start Celery beat scheduler + two specialized workers as background processes.
#
# WORKER ARCHITECTURE (BUG-002 fix):
# Fast worker (-Q default,llm): Critical-path document processing
#   - process_document, validate_ocr, chunk_document, extract_tables
#   - embed_chunks, extract_entities, extract_citations, extract_dates
#   - summary generation, verification processing
#   - 40 greenlets — ensures new users always get served
#
# Slow worker (-Q heavy,low): Background & heavy computation
#   - resolve_aliases (alias resolution — can take 10-30 min per task)
#   - detect_contradictions (O(n^2) — can take 5-20 min)
#   - All maintenance tasks (recovery, cleanup, sync)
#   - act validation, evaluations, emails, reasoning archives
#   - 10 greenlets — physically isolated from fast worker
#
# Traps SIGTERM/SIGINT (sent by Railway on deploy) and forwards to all,
# giving workers time to finish in-flight tasks before exiting.
#
# Railway drain timeout should be set to 120s via Dashboard:
#   Settings → Deploy → Drain Timeout
#
# Beat uses RedBeat (Redis-backed scheduler with distributed locking).
# Multiple replicas can each start beat — RedBeat's Redis lock ensures
# only one fires tasks at a time, with automatic failover if the leader dies.
#
# MEMORY BUDGET (~730 MB total):
#   Fast worker (40 greenlets): ~350 MB
#   Slow worker (10 greenlets): ~300 MB
#   Beat scheduler:             ~80 MB
#   Ensure Railway service has ≥1 GB RAM.

# --- Graceful shutdown handler ---
cleanup() {
    echo "[shutdown] SIGTERM received, draining all processes..."
    if [ -n "$FAST_PID" ]; then
        kill -TERM $FAST_PID 2>/dev/null
    fi
    if [ -n "$SLOW_PID" ]; then
        kill -TERM $SLOW_PID 2>/dev/null
    fi
    if [ -n "$BEAT_PID" ]; then
        kill -TERM $BEAT_PID 2>/dev/null
    fi
    # Wait for all processes to drain
    if [ -n "$FAST_PID" ]; then
        wait $FAST_PID 2>/dev/null
    fi
    if [ -n "$SLOW_PID" ]; then
        wait $SLOW_PID 2>/dev/null
    fi
    if [ -n "$BEAT_PID" ]; then
        wait $BEAT_PID 2>/dev/null
    fi
    echo "[shutdown] All processes drained, exiting"
    exit 0
}

trap cleanup SIGTERM SIGINT

# --- Start beat scheduler (RedBeat handles leader election via Redis lock) ---
celery -A app.workers.celery:celery_app beat \
    --loglevel=info &
BEAT_PID=$!

# --- Fast worker: critical-path document processing ---
# Queues: default (OCR, chunking, validation) + llm (embedding, entities, citations, dates, summaries)
# Concurrency: 40 greenlets (reduced from 50 to leave headroom for slow worker)
celery -A app.workers.celery:celery_app worker \
    --loglevel=info \
    --pool=gevent \
    --concurrency=40 \
    --without-gossip \
    --without-mingle \
    --without-heartbeat \
    -n fast@%h \
    -Q default,llm &
FAST_PID=$!

# --- Slow worker: background & heavy tasks ---
# Queues: heavy (contradictions) + low (alias resolution, maintenance, evaluations, emails)
# Concurrency: 10 greenlets (sufficient for background work, prevents resource monopolization)
celery -A app.workers.celery:celery_app worker \
    --loglevel=info \
    --pool=gevent \
    --concurrency=10 \
    --without-gossip \
    --without-mingle \
    --without-heartbeat \
    -n slow@%h \
    -Q heavy,low &
SLOW_PID=$!

# Wait for fast worker (blocked until it exits or signal received)
wait $FAST_PID
```

### Memory Impact

| Process | Concurrency | Estimated RAM |
|---------|-------------|---------------|
| Fast worker | 40 greenlets | ~350 MB |
| Slow worker | 10 greenlets | ~300 MB |
| Beat scheduler | — | ~80 MB |
| **Total** | **50 greenlets** | **~730 MB** |

Previous: Single worker (50 greenlets) + beat = ~430 MB.
Increase: ~300 MB (one additional Python process with loaded modules).

### Redis Connection Impact

Each worker process opens ~7 Redis connections (with gossip/mingle/heartbeat disabled):
- Fast worker: ~7 connections
- Slow worker: ~7 connections
- Beat: ~3 connections
- **Total**: ~17 connections

Upstash Redis supports 10,000+ concurrent connections on all plans. No concern.

---

## Phase 3: Per-Matter Concurrency Cap

**Effort**: 20 minutes

### 3.1 New Config Setting

**File**: `backend/app/core/config.py`

Add alongside `max_concurrent_docs_per_matter` (line ~326):
```python
# Per-matter concurrency for alias resolution (BUG-002)
# Prevents one matter's 35 alias tasks from monopolizing the slow worker's 10 greenlets.
# When at capacity, tasks are deferred with 30s backoff and retry up to 10 times.
max_concurrent_alias_tasks_per_matter: int = 2  # MAX_CONCURRENT_ALIAS_TASKS_PER_MATTER
```

### 3.2 New Lock Class: AliasResolutionSlot

**File**: `backend/app/services/distributed_lock.py`

Add after `PipelineLock` class (after line 228):

```python
# Per-matter concurrency limiter for alias resolution (BUG-002)
ALIAS_SLOT_KEY = "alias_slots:{matter_id}"
ALIAS_SLOT_TIMEOUT = 1800  # 30 min safety TTL (auto-cleanup if task dies without releasing)


class AliasResolutionSlot:
    """Per-matter concurrency limiter for alias resolution tasks.

    BUG-002: Prevents one matter's 35 alias tasks from monopolizing
    the slow worker's 10 greenlets. Uses Redis INCR/DECR with atomic
    check-and-increment.

    Pattern:
    - acquire() increments counter. If > max_slots, decrements and returns False.
    - release() decrements counter (floored at 0).
    - TTL auto-expires the key if task dies without releasing.

    Example:
        >>> slot = AliasResolutionSlot("matter-123", max_slots=2)
        >>> if slot.acquire():
        ...     try:
        ...         resolve_aliases(...)
        ...     finally:
        ...         slot.release()
        ... else:
        ...     self.retry(countdown=30)  # Deferred — at capacity
    """

    def __init__(self, matter_id: str, max_slots: int = 2):
        self.matter_id = matter_id
        self.max_slots = max_slots
        self.slot_key = ALIAS_SLOT_KEY.format(matter_id=matter_id)
        self._client = get_sync_redis_client()
        self._acquired = False

    def acquire(self) -> bool:
        """Atomically try to acquire a slot. Returns False if at capacity."""
        try:
            pipe = self._client.pipeline()
            pipe.incr(self.slot_key)
            pipe.expire(self.slot_key, ALIAS_SLOT_TIMEOUT)
            results = pipe.execute()
            current_count = results[0]

            if current_count > self.max_slots:
                # At capacity — release the slot we just took
                self._client.decr(self.slot_key)
                logger.info(
                    "alias_slot_at_capacity",
                    matter_id=self.matter_id,
                    current=current_count - 1,
                    max_slots=self.max_slots,
                )
                return False

            self._acquired = True
            logger.debug(
                "alias_slot_acquired",
                matter_id=self.matter_id,
                current=current_count,
                max_slots=self.max_slots,
            )
            return True

        except redis.RedisError as e:
            logger.error(
                "alias_slot_acquire_error",
                matter_id=self.matter_id,
                error=str(e),
            )
            # Fail open: allow task to proceed if Redis is down
            self._acquired = True
            return True

    def release(self):
        """Release the slot. Safe to call multiple times."""
        if not self._acquired:
            return
        try:
            new_count = self._client.decr(self.slot_key)
            # Floor at 0 to prevent negative counts from double-release
            if new_count < 0:
                self._client.set(self.slot_key, 0, ex=ALIAS_SLOT_TIMEOUT)
            self._acquired = False
            logger.debug(
                "alias_slot_released",
                matter_id=self.matter_id,
            )
        except redis.RedisError as e:
            logger.warning(
                "alias_slot_release_error",
                matter_id=self.matter_id,
                error=str(e),
            )
            self._acquired = False
```

### 3.3 Guard in resolve_aliases Task

**File**: `backend/app/workers/tasks/document_tasks.py`

**Change 3.3a** — Update task decorator (line 4765):
```python
# BEFORE
@celery_app.task(
    name="app.workers.tasks.document_tasks.resolve_aliases",
    bind=True,
    autoretry_for=(AliasResolutionError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=120,
    max_retries=3,
    retry_jitter=True,
    soft_time_limit=1800,  # 30 minutes
    time_limit=1860,       # 31 minutes
)

# AFTER
@celery_app.task(
    name="app.workers.tasks.document_tasks.resolve_aliases",
    bind=True,
    autoretry_for=(AliasResolutionError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=120,
    max_retries=3,
    retry_jitter=True,
    rate_limit='6/m',       # BUG-002: Max 6 alias tasks per minute across the worker
    soft_time_limit=600,    # 10 min (reduced from 30 — gevent ignores this anyway)
    time_limit=660,         # 11 min hard kill
)
```

**Change 3.3b** — Add per-matter concurrency guard (after line ~4867, after `matter_id` is resolved):
```python
        # BUG-002: Per-matter concurrency limit for alias resolution
        # Prevents one matter's 35 alias tasks from monopolizing the slow worker
        from app.services.distributed_lock import AliasResolutionSlot
        from app.core.config import get_settings as _get_settings
        _alias_settings = _get_settings()
        slot = AliasResolutionSlot(
            matter_id,
            max_slots=_alias_settings.max_concurrent_alias_tasks_per_matter,
        )
        if not slot.acquire():
            # At capacity — defer with backoff
            logger.info(
                "resolve_aliases_deferred",
                document_id=doc_id,
                matter_id=matter_id,
                reason="per_matter_concurrency_limit",
            )
            raise self.retry(countdown=30, max_retries=10)
```

**Change 3.3c** — Release slot in ALL exit paths:

In success path (after line ~5030):
```python
        slot.release()
```

In every `except` block (lines 5044, 5075, 5093, 5109):
```python
        slot.release()
```

**Important**: Use try/finally in the main flow to guarantee release:
```python
        slot = AliasResolutionSlot(matter_id, max_slots=...)
        if not slot.acquire():
            raise self.retry(countdown=30, max_retries=10)

        try:
            # ... existing task logic ...
        finally:
            slot.release()
```

### 3.4 Explicit queue="low" in dispatch

**File**: `backend/app/workers/tasks/document_tasks.py`

**Line 4728-4734** (`_dispatch_post_entity_tasks`):
```python
# BEFORE
celery_app.send_task(
    "app.workers.tasks.document_tasks.resolve_aliases",
    kwargs={
        "document_id": document_id,
    },
    queue="default",
)

# AFTER
celery_app.send_task(
    "app.workers.tasks.document_tasks.resolve_aliases",
    kwargs={
        "document_id": document_id,
    },
    queue="low",  # BUG-002: Explicit low queue — runs on slow worker
)
```

---

## Phase 4: Update All Dispatch Points

**Effort**: 5 minutes

Every place that dispatches `resolve_aliases` must use `queue="low"` for consistency with the routing change in Phase 1.

### 4.1 Complete Dispatch Point Inventory

| # | File | Line | Dispatch Method | Change |
|---|------|------|-----------------|--------|
| 1 | `document_tasks.py` `_dispatch_post_entity_tasks()` | 4728 | `celery_app.send_task()` | Add `queue="low"` ← Done in Phase 3.4 |
| 2 | `maintenance_tasks.py` `dispatch_stuck_queued_jobs()` | ~382 | `resolve_aliases.apply_async()` | Add `queue="low"` |
| 3 | `job_recovery.py` `_redispatch_job()` | ~374 | `resolve_aliases.apply_async()` | Add `queue="low"` |
| 4 | `dispatch_queued_jobs.py` (manual script) | ~58 | `resolve_aliases.apply_async()` | Add `queue="low"` |
| 5 | `admin/pipeline.py` (admin endpoint) | N/A | Uses `send_task()` via TASK_MAPPING | **No change needed** — goes through `task_routes` which we already updated |
| 6 | `trigger_task.py` (test script) | ~32 | Uses `.s()` in chain | **No change needed** — test script, not production |

### 4.2 Specific Changes

**File**: `backend/app/workers/tasks/maintenance_tasks.py` (line ~382):
```python
# BEFORE
elif stage == "alias_resolution":
    resolve_aliases.apply_async(
        kwargs={"document_id": doc_id},
        countdown=2,
    )

# AFTER
elif stage == "alias_resolution":
    resolve_aliases.apply_async(
        kwargs={"document_id": doc_id},
        countdown=2,
        queue="low",  # BUG-002: runs on slow worker
    )
```

**File**: `backend/app/services/job_recovery.py` (line ~374):
```python
# BEFORE
elif stage == "alias_resolution":
    resolve_aliases.apply_async(
        kwargs={"document_id": document_id},
        countdown=5,
    )

# AFTER
elif stage == "alias_resolution":
    resolve_aliases.apply_async(
        kwargs={"document_id": document_id},
        countdown=5,
        queue="low",  # BUG-002: runs on slow worker
    )
```

**File**: `backend/dispatch_queued_jobs.py` (line ~58):
```python
# BEFORE
elif stage == 'alias_resolution':
    resolve_aliases.apply_async(
        kwargs={"document_id": doc_id},
        countdown=1,
    )

# AFTER
elif stage == 'alias_resolution':
    resolve_aliases.apply_async(
        kwargs={"document_id": doc_id},
        countdown=1,
        queue="low",  # BUG-002: runs on slow worker
    )
```

---

## Phase 5: Task Chunking

**Status**: FUTURE — Implement after Phases 1-4 are deployed and validated
**Effort**: 2-3 hours

### 5.1 The Problem Phase 5 Solves

After Phases 1-4:
- Slow worker has 10 greenlets for `heavy` + `low` queues
- Per-matter cap = 2 concurrent alias tasks
- **But**: Each alias task still runs 10-30 minutes
- If 5 different matters each have 2 alias tasks = 10 greenlets busy
- **Max starvation within slow worker**: ~10 minutes (one round of Gemini batches)

Phase 5 reduces max task duration from 10-30 minutes to ~2 minutes by decomposing alias resolution into fan-out/fan-in batches.

### 5.2 Industry Patterns for Fan-Out/Fan-In with Dependencies

**The pattern**: A → [B1, B2, ..., Bn] → C

Where:
- A = Phase 1 (high similarity, produces medium_confidence_pairs)
- B1..Bn = Phase 2 batches (Gemini analysis, each processes ~20 pairs)
- C = Phase 3 (transitive closure, needs ALL edges from A + B1..Bn)

#### Pattern 1: Celery Chord (Native)

```python
# chord = group of parallel tasks + callback when ALL complete
chord(
    [phase2_batch.s(batch, matter_id) for batch in batches],
    phase3_callback.s(phase1_edges=phase1_edges)
)
```

**Internally**: Redis atomic INCR. Each batch completion increments counter. Last batch triggers callback.

**Requires**: `ignore_result=False` on all chord participants.
**Already used**: `chunked_document_tasks.py` uses chords for parallel chunk processing.
**Gotcha**: If ANY batch fails, callback never fires (default behavior). Needs monkey-patch for partial success.

#### Pattern 2: Manual Redis Counter (DIY Chord) ← **RECOMMENDED**

Same atomic counter pattern as chords, but you control result storage:

```python
# Each Phase 2 batch on completion:
pipe = redis.pipeline()
pipe.rpush(f"resolve:{matter_id}:results", json.dumps(edges))
completed = pipe.incr(f"resolve:{matter_id}:counter")
pipe.execute()

if completed >= total_batches:
    _trigger_phase3(matter_id)  # Collect all results, dispatch Phase 3
```

**Advantages**:
- Works with `task_ignore_result=True` (your global default)
- Built-in partial failure tolerance (no monkey-patch)
- Results persist in Redis → collected by Phase 3
- Pattern already exists in `chunked_document_tasks.py` (auto-finalization check)
- Easier to debug (inspect Redis keys directly)

#### Pattern 3: self.replace() with Dynamic Chord

Phase 1 runs inline, then replaces itself with a chord:

```python
@celery_app.task(bind=True, ignore_result=False)
def resolve_aliases(self, ...):
    phase1_result = run_phase1(...)
    raise self.replace(
        chord(
            [phase2_batch.s(...) for batch in batches],
            phase3_callback.s(phase1_result=phase1_result)
        )
    )
```

**Advantage**: If task is in a chain, chain continues after chord completes.
**Disadvantage**: Requires `ignore_result=False`, more complex error handling.

#### Pattern 4: Temporal.io (Reference)

Single durable workflow function with `asyncio.gather()`. Automatic replay on failure. No counter management. Requires new infrastructure (Temporal server). Overkill for this use case.

### 5.3 Recommended Implementation: Manual Redis Counter

This pattern is the most robust for our constraints (gevent pool, `task_ignore_result=True`, partial failure tolerance needed).

### 5.4 Entity Resolver Refactoring

**File**: `backend/app/services/mig/entity_resolver.py`

The `resolve_aliases()` method (lines 720-900) must be split into 3 callable phases:

#### New method: `run_phase1_high_similarity()`
```python
async def run_phase1_high_similarity(
    self,
    matter_id: str,
    entities: list[EntityNode],
    entity_contexts: dict[str, str] | None = None,
    document_entity_ids: set[str] | None = None,
) -> dict:
    """Phase 1: High-similarity auto-linking + collect medium-confidence pairs.

    Returns:
        {
            "high_confidence_edges": list[dict],  # Serializable edge data
            "medium_confidence_pairs": list[dict],  # Serializable pair data for Gemini
            "result_counters": {
                "entities_processed": int,
                "alias_pairs_found": int,
                "high_confidence_links": int,
                "skipped_low_confidence": int,
            },
        }
    """
    # Existing Phase 1 logic (lines 753-813):
    # - Group entities by type
    # - For each type: find_potential_aliases()
    # - Separate into high_confidence_pairs and medium_confidence_pairs
    # - Create edges for high-confidence pairs
    # Return serializable dicts (not dataclass instances)
```

#### New method: `run_phase2_gemini_batch()`
```python
async def run_phase2_gemini_batch(
    self,
    pairs: list[dict],
    matter_id: str,
) -> list[dict]:
    """Phase 2: Gemini analysis for a batch of medium-confidence pairs.

    Args:
        pairs: List of {pair_id, name1, context1, name2, context2, similarity_score, ...}
        matter_id: For cost tracking.

    Returns:
        List of edge dicts for pairs that passed the confidence threshold.
    """
    # Existing Phase 2 logic (lines 815-889):
    # - Call analyze_batch_context() for each sub-batch (10 pairs per Gemini call)
    # - Apply CONTEXT_CONFIDENCE_THRESHOLD filter
    # - Return serializable edge dicts
```

#### New method: `run_phase3_transitive_closure()`
```python
def run_phase3_transitive_closure(
    self,
    all_edges: list[dict],
    matter_id: str,
) -> list[dict]:
    """Phase 3: Compute transitive closure over all edges.

    Returns:
        Complete list of edges (original + transitive).
    """
    # Existing Phase 3 logic (line 891-892):
    # - Call _apply_transitive_closure()
    # Return serializable edge dicts
```

### 5.5 New Celery Tasks

**File**: `backend/app/workers/tasks/document_tasks.py`

#### Task: `resolve_aliases_phase1`
```python
@celery_app.task(
    name="app.workers.tasks.document_tasks.resolve_aliases_phase1",
    bind=True,
    max_retries=3,
    soft_time_limit=120,   # 2 min (Phase 1 is CPU-only, fast)
    time_limit=180,
)
def resolve_aliases_phase1(self, document_id, matter_id=None, job_id=None):
    """Phase 1: High-similarity matching + dispatch Phase 2 batches.

    Runs Phase 1 inline (fast, CPU-only), then dispatches Phase 2 batches
    to the low queue. Last batch to complete triggers Phase 3.

    Uses Manual Redis Counter pattern for fan-out/fan-in coordination.
    """
    # 1. Load entities and contexts (same as current resolve_aliases lines 4880-4927)
    # 2. Call resolver.run_phase1_high_similarity()
    # 3. Persist high-confidence edges immediately
    # 4. Store Phase 1 metadata in Redis:
    #    - Key: f"alias_resolve:{matter_id}:{document_id}:phase1" → JSON of high_conf_edges
    #    - Key: f"alias_resolve:{matter_id}:{document_id}:total" → number of Phase 2 batches
    #    - Key: f"alias_resolve:{matter_id}:{document_id}:counter" → 0 (completed batch count)
    #    - TTL: 7200 (2 hours safety)
    # 5. Dispatch Phase 2 batch tasks (each handles ~20 medium-confidence pairs)
    # 6. If no medium pairs, dispatch Phase 3 directly
```

#### Task: `resolve_aliases_phase2_batch`
```python
@celery_app.task(
    name="app.workers.tasks.document_tasks.resolve_aliases_phase2_batch",
    bind=True,
    max_retries=3,
    retry_backoff=True,
    soft_time_limit=120,   # 2 min per batch (~20 pairs, 2 Gemini calls)
    time_limit=180,
    rate_limit='10/m',     # Max 10 batch tasks per minute
)
def resolve_aliases_phase2_batch(
    self, batch_index, batch_pairs, document_id, matter_id, job_id=None
):
    """Phase 2 batch: Gemini analysis for a subset of medium-confidence pairs.

    Each batch handles ~20 pairs. Last batch to complete triggers Phase 3
    via atomic Redis counter increment.
    """
    # 1. Call resolver.run_phase2_gemini_batch(batch_pairs, matter_id)
    # 2. Store results in Redis:
    #    - RPUSH f"alias_resolve:{matter_id}:{document_id}:results" → JSON batch result
    # 3. Atomically increment counter:
    #    - INCR f"alias_resolve:{matter_id}:{document_id}:counter"
    # 4. If counter == total → dispatch Phase 3 task
    # 5. If counter < total → done (other batches will eventually trigger Phase 3)
```

#### Task: `resolve_aliases_phase3`
```python
@celery_app.task(
    name="app.workers.tasks.document_tasks.resolve_aliases_phase3",
    bind=True,
    max_retries=2,
    soft_time_limit=60,    # 1 min (transitive closure is fast)
    time_limit=120,
)
def resolve_aliases_phase3(self, document_id, matter_id, job_id=None):
    """Phase 3: Transitive closure + persistence + cleanup.

    Collects all results from Redis, computes transitive closure,
    persists edges to database, cleans up Redis keys.
    """
    # 1. Collect Phase 1 edges from Redis
    # 2. Collect all Phase 2 batch results from Redis (LRANGE)
    # 3. Call resolver.run_phase3_transitive_closure(all_edges, matter_id)
    # 4. Persist all edges to database (graph_service.create_alias_edge)
    # 5. Update canonical entity aliases
    # 6. Broadcast completion (WebSocket)
    # 7. Update job stage (alias_resolution complete)
    # 8. Cleanup Redis keys
    # 9. Release AliasResolutionSlot
```

### 5.6 Redis Key Schema

```
alias_resolve:{matter_id}:{document_id}:phase1    → JSON: high_confidence_edges list
alias_resolve:{matter_id}:{document_id}:total      → Integer: number of Phase 2 batches
alias_resolve:{matter_id}:{document_id}:counter    → Integer: completed Phase 2 batch count
alias_resolve:{matter_id}:{document_id}:results    → Redis List: JSON batch results (RPUSH)
alias_resolve:{matter_id}:{document_id}:context    → JSON: entity_contexts dict (shared across batches)

TTL on all keys: 7200 seconds (2 hours — safety net for stuck resolutions)
```

### 5.7 Stuck Resolution Recovery

Add to `maintenance_tasks.py`:

```python
# In beat_schedule:
"cleanup-stale-alias-resolutions": {
    "task": "app.workers.tasks.maintenance_tasks.cleanup_stale_alias_resolutions",
    "schedule": 3600,  # Every hour
    "options": {"queue": "low"},
}
```

The cleanup task scans for Redis keys matching `alias_resolve:*:counter` where:
- TTL is expired (keys are stale)
- Counter < total (never completed)
- Log warning and clean up orphaned keys

### 5.8 Migration Path: resolve_aliases → resolve_aliases_phase1

The existing `resolve_aliases` task must be replaced by `resolve_aliases_phase1` in all dispatch points. Since we can't rename a Celery task without updating all references, the cleanest approach:

1. Keep `resolve_aliases` task but make it a thin wrapper that dispatches `resolve_aliases_phase1`
2. OR: Rename all dispatch points to use the new task name

**Recommended**: Keep `resolve_aliases` as a wrapper for backward compatibility:
```python
@celery_app.task(name="app.workers.tasks.document_tasks.resolve_aliases", ...)
def resolve_aliases(self, prev_result=None, document_id=None, ...):
    """Wrapper: dispatches the 3-phase pipeline."""
    # Extract doc_id, matter_id (same as current)
    # Dispatch resolve_aliases_phase1 and return immediately
    resolve_aliases_phase1.apply_async(
        kwargs={"document_id": doc_id, "matter_id": matter_id, "job_id": job_id},
        queue="low",
    )
    return {"status": "alias_resolution_dispatched", "document_id": doc_id}
```

This means ALL existing dispatch points (maintenance, recovery, admin) continue to work without changes.

### 5.9 Data Serialization

The `AliasCandidate` dataclass must be serialized to JSON for Redis storage:

```python
def _serialize_candidate(candidate: AliasCandidate) -> dict:
    return {
        "entity_id": candidate.entity_id,
        "entity_name": candidate.entity_name,
        "candidate_entity_id": candidate.candidate_entity_id,
        "candidate_name": candidate.candidate_name,
        "similarity_score": candidate.similarity_score,
        "name_similarity": candidate.name_similarity,
        "component_similarity": candidate.component_similarity,
        "initial_match_score": candidate.initial_match_score,
        "context_confidence": candidate.context_confidence,
        "is_auto_linked": candidate.is_auto_linked,
    }

def _deserialize_candidate(data: dict) -> AliasCandidate:
    return AliasCandidate(**data)
```

---

## Files Affected (Complete List)

### Phases 1-4 (Ship First)

| File | Changes |
|------|---------|
| `backend/app/workers/celery.py` | prefetch=1, route aliases→low, broker_pool_limit, remove no-op settings |
| `backend/start-worker.sh` | Full rewrite: 2 workers + signal handling |
| `backend/app/core/config.py` | Add `max_concurrent_alias_tasks_per_matter` setting |
| `backend/app/services/distributed_lock.py` | Add `AliasResolutionSlot` class |
| `backend/app/workers/tasks/document_tasks.py` | rate_limit, reduced timeout, per-matter guard, queue="low" dispatch |
| `backend/app/workers/tasks/maintenance_tasks.py` | queue="low" for alias dispatch |
| `backend/app/services/job_recovery.py` | queue="low" for alias dispatch |
| `backend/dispatch_queued_jobs.py` | queue="low" for alias dispatch |

### Phase 5 (Future Follow-Up)

| File | Changes |
|------|---------|
| `backend/app/services/mig/entity_resolver.py` | Split `resolve_aliases()` into 3 phase methods |
| `backend/app/workers/tasks/document_tasks.py` | 3 new tasks (phase1, phase2_batch, phase3), wrapper task |
| `backend/app/workers/celery.py` | New task routes for phase tasks, new beat schedule entry |
| `backend/app/workers/tasks/maintenance_tasks.py` | Stale alias resolution cleanup task |

### Files NOT Touched

- `pipeline_chains.py` — No change (aliases are dispatched by extract_entities, not in the chain)
- `chunked_document_tasks.py` — No change (uses create_post_ocr_chain which calls extract_entities)
- `railway.toml` / `railway.worker.toml` — No change (same service, same replica count)
- `Dockerfile` — No change
- Any frontend files — No change
- Any migration files — No change

---

## Database Migrations

**None.** Zero database changes required across all 5 phases. This is purely worker infrastructure.

---

## Verification Plan

### After Phases 1-4

**1. Local startup test**:
```bash
cd backend
bash start-worker.sh
# Verify in logs:
# - "[celery@fast] ready" with -Q default,llm
# - "[celery@slow] ready" with -Q heavy,low
# - Beat scheduler started
```

**2. Queue isolation test**:
```bash
# In Python shell:
from app.workers.celery import celery_app
# Verify routing:
route = celery_app.amqp.router.route({}, "app.workers.tasks.document_tasks.resolve_aliases")
assert route["queue"].name == "low"  # Should be "low", not "llm"
```

**3. Production deploy**:
```bash
railway up -s LDIP          # API
railway up -s ldip-worker   # Worker (both fast + slow)
```

**4. Functional test**:
1. Upload document to large matter (User A) — triggers alias resolution
2. While running, upload document as User B (new/small matter)
3. **Expected**: User B's document processes normally (fast worker handles embed/entities/citations)
4. **Verify logs**: `fast@%h` handles User B, `slow@%h` handles alias resolution
5. **Check Redis**: `KEYS alias_slots:*` shows ≤2 per matter

**5. Per-matter cap test**:
1. Upload 5 documents to the same matter rapidly
2. **Expected**: Only 2 alias tasks run concurrently per matter
3. **Verify logs**: "resolve_aliases_deferred" messages for tasks 3-5 with 30s countdown
4. Tasks 3-5 eventually complete after slots free up

### After Phase 5

**6. Task decomposition test**:
1. Upload document to matter with 100+ entities
2. **Expected**: Phase 1 completes fast (~5s), dispatches N Phase 2 batches
3. Phase 2 batches complete independently (~2 min each)
4. Last Phase 2 batch triggers Phase 3
5. **Verify Redis**: Counter reaches total, keys cleaned up
6. **Verify DB**: Alias edges created correctly

---

## Rollback Plan

### Phase 1 (Config): Revert celery.py to previous values
### Phase 2 (Dual worker): Revert start-worker.sh to single worker (1-line change)
### Phase 3 (Per-matter cap): Remove slot guard from resolve_aliases (feature flag: set max_slots=999)
### Phase 4 (Dispatch points): Revert queue parameter (or leave — routing handles it)
### Phase 5 (Task chunking): Keep old resolve_aliases task, remove wrapper

All phases are independently reversible. No data migration means no backward-compatibility concerns.

---

## Sources

### Celery Documentation
- [Celery Optimizing Guide](https://docs.celeryq.dev/en/latest/userguide/optimizing.html) — prefetch multiplier recommendations
- [Celery Canvas (Chord/Group)](https://docs.celeryq.dev/en/stable/userguide/canvas.html) — fan-out/fan-in patterns
- [Celery Gevent Pool](https://docs.celeryq.dev/en/main/userguide/concurrency/gevent.html) — soft_time_limit limitation
- [Celery Issue #1958](https://github.com/celery/celery/issues/1958) — gevent ignores soft/hard timeout
- [Celery Issue #4537](https://github.com/celery/celery/issues/4537) — prefetching with acks_late

### Production Engineering Blogs
- [Wolt: 5 Tips for Production Celery Tasks](https://careers.wolt.com/en/blog/tech/5-tips-for-writing-production-ready-celery-tasks)
- [Celery: 63% RAM Reduction with Gevent](https://dev.to/davidbern/celery-63-ram-reduction-and-100x-concurrency-with-gevent-9g4)
- [Running Celery at Scale in Production](https://maheshmahadevan.substack.com/p/running-celery-at-scale-in-production)
- [Nautobot Celery Task Queues](https://docs.nautobot.com/projects/core/en/stable/user-guide/administration/guides/celery-queues/)
- [Doing Big Automation with Celery (OVHcloud)](https://blog.ovhcloud.com/doing-big-automation-with-celery/)

### Multi-Tenant Fairness
- [AWS Builders Library: Fairness in Multi-Tenant Systems](https://aws.amazon.com/builders-library/fairness-in-multi-tenant-systems/)
- [Inngest Queue: Fairness & Multi-Tenancy](https://www.inngest.com/blog/building-the-inngest-queue-pt-i-fairness-multi-tenancy)
- [Holistics: Multi-Tenant Job Queue with PostgreSQL](https://www.holistics.io/blog/how-we-built-a-multi-tenant-job-queue-system-with-postgresql-ruby/)
- [Ensuring Fair Processing with Celery](https://dev.to/ykimura/ensuring-fair-processing-with-celery-part-ii-3jm9)
- [Evil Martians: Fair Multi-Tenant Sidekiq](https://evilmartians.com/chronicles/fair-multi-tenant-prioritization-of-sidekiq-jobs-and-our-gem-for-it)

### Fan-Out/Fan-In Patterns
- [How Celery Chord Synchronization Works](https://blog.untrod.com/2015/03/how-celery-chord-synchronization-works.html)
- [The Fanout Pattern Explained (Better Simple)](https://www.better-simple.com/django/2023/12/06/fanout-pattern-explained/)
- [Chord Error Handling (danidee10)](https://danidee10.github.io/2019/07/09/celery-chords.html)
- [Celery Redis Backend Implementation (DeepWiki)](https://deepwiki.com/celery/celery/6.2-backend-implementations)

### Railway Deployment
- [Railway: Graceful Shutdown of Celery Workers](https://station.railway.com/questions/graceful-shutdown-of-celery-workers-duri-7445b567)
- [Railway: FastAPI + Celery Template](https://railway.com/deploy/fastapi-celery-beat-worker-flower)
- [Docker: Run Multiple Processes in a Container](https://docs.docker.com/engine/containers/multi-service_container/)
- [Zapier: 40% RAM Reduction with jemalloc](https://zapier.com/engineering/celery-python-jemalloc/)
