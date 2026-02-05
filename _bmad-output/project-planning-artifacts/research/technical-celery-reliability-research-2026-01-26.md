---
stepsCompleted: [1, 2, 3, 4]
inputDocuments: []
workflowType: 'research'
lastStep: 4
research_type: 'technical'
research_topic: 'Celery Task Queue Failures, Timeouts, and Silent Failures'
research_goals: 'Both diagnosis of current issues AND prevention/future-proofing strategies'
user_name: 'Juhi'
date: '2026-01-26'
web_research_enabled: true
source_verification: true
---

# Technical Research Report: Celery Task Queue Reliability

**Date:** 2026-01-26
**Author:** Juhi
**Research Type:** Technical Research
**Confidence Level:** High (Multiple sources verified)

---

## Executive Summary

This comprehensive research investigates Celery task queue failures, timeouts, silent failures, and other common issues affecting both Windows local development and production deployments. The research reveals that **60% of Celery task failures are due to temporary issues resolvable with proper retry strategies**, and **30% of task failures stem from timeout configuration issues**. Key findings include critical Windows compatibility limitations (prefork pool no longer supported), visibility timeout pitfalls with Redis, and proven industry patterns for building resilient distributed task systems.

**Key Recommendations:**
1. Use `acks_late=True` with idempotent tasks for guaranteed delivery
2. Set `visibility_timeout` higher than your longest task execution time
3. On Windows, use `solo`, `threads`, or `gevent` pools instead of prefork
4. Implement Dead Letter Queues for failed task handling
5. Use `max_tasks_per_child` to prevent memory leaks
6. Consider RabbitMQ over Redis for mission-critical, long-running tasks

---

## Table of Contents

1. [Silent Failures & Lost Tasks](#1-silent-failures--lost-tasks)
2. [Timeout & Hanging Task Issues](#2-timeout--hanging-task-issues)
3. [Windows-Specific Issues & Workarounds](#3-windows-specific-issues--workarounds)
4. [Broker Selection: Redis vs RabbitMQ](#4-broker-selection-redis-vs-rabbitmq)
5. [Retry Strategies & Error Handling](#5-retry-strategies--error-handling)
6. [Dead Letter Queues (DLQ)](#6-dead-letter-queues-dlq)
7. [Idempotency & Duplicate Prevention](#7-idempotency--duplicate-prevention)
8. [Memory Management & OOM Prevention](#8-memory-management--oom-prevention)
9. [Monitoring & Observability](#9-monitoring--observability)
10. [Celery Alternatives Comparison](#10-celery-alternatives-comparison)
11. [Production Best Practices Checklist](#11-production-best-practices-checklist)
12. [Sources & References](#12-sources--references)

---

## 1. Silent Failures & Lost Tasks

### Common Causes [High Confidence]

Silent failures occur when tasks disappear without error logs or acknowledgment. Research identifies these primary causes:

#### 1.1 Broker Configuration Issues
- If your broker (RabbitMQ/Redis) isn't correctly configured or isn't running, tasks won't be sent to the queue
- Incorrect settings lead to connectivity problems, resulting in lost messages
- **Solution:** Verify broker connectivity before task dispatch

#### 1.2 Task Registration Failures
- If a task isn't registered with the Celery app, calling `task.delay()` does nothing
- Commonly happens when tasks are not imported or decorated properly
- **Solution:** Ensure all task modules are imported in your Celery app configuration

```python
# celery.py - Ensure autodiscover is working
app.autodiscover_tasks(['myapp.tasks', 'otherapp.tasks'])
```

#### 1.3 Task Routing Mismatches
- Discrepancies in task routing can introduce bottlenecks
- Misrouted tasks generate errors silently
- **Solution:** Validate routing keys and ensure workers are configured for the correct queues

```python
# Verify task is routed to existing queue
app.conf.task_routes = {
    'myapp.tasks.critical_task': {'queue': 'high_priority'},
}
```

#### 1.4 Silent Database Failures
- If tasks interact with a database and there's a connection issue, tasks may fail silently
- **Solution:** Implement explicit database connection health checks in tasks

#### 1.5 Eager Mode Confusion
- `CELERY_TASK_ALWAYS_EAGER = True` executes tasks locally instead of queuing them
- **Solution:** Ensure this is `False` in production environments

_Sources: [GitGuardian - Celery Task Resilience](https://blog.gitguardian.com/celery-tasks-retries-errors/), [MoldStud - Understanding Celery Task Failures](https://moldstud.com/articles/p-understanding-celery-task-failures-causes-solutions-and-best-practices)_

---

## 2. Timeout & Hanging Task Issues

### The Visibility Timeout Problem [High Confidence]

One of the most common and dangerous issues with Celery, especially with Redis broker:

#### 2.1 How Visibility Timeout Works
- Redis and SQS brokers use visibility timeout (default: 1 hour for Redis, 30 minutes for SQS)
- If a task is not acknowledged within this timeframe, it is **automatically redelivered**
- This causes **duplicate execution** of long-running tasks

```python
# CRITICAL: Set visibility_timeout higher than longest task
app.conf.broker_transport_options = {
    'visibility_timeout': 43200,  # 12 hours in seconds
}
```

#### 2.2 Task Redelivery Loop Problem
Long-running jobs with `acks_late=True` and `task_reject_on_worker_lost=True` will be redelivered after every visibility timeout period, creating an infinite loop.

**Known GitHub Issues:**
- [Issue #5935](https://github.com/celery/celery/issues/5935): Long running jobs redelivering after broker visibility timeout
- [Issue #6229](https://github.com/celery/celery/issues/6229): Tasks longer than visibility timeout not being re-queued
- [Issue #7651](https://github.com/celery/celery/issues/7651): Visibility timeout config not working

#### 2.3 Configuration for Reliable Delivery

```python
# Recommended production configuration
app.conf.update(
    task_acks_late=True,                    # Acknowledge after completion
    task_reject_on_worker_lost=True,        # Reject if worker dies
    task_acks_on_failure_or_timeout=True,   # Default: prevents redelivery on timeout

    # Time limits
    task_time_limit=3600,                   # Hard limit: 1 hour
    task_soft_time_limit=3300,              # Soft limit: 55 minutes (allows cleanup)

    # Visibility must exceed task_time_limit
    broker_transport_options={
        'visibility_timeout': 7200,         # 2 hours
    },
)
```

#### 2.4 Celery 5.5+ Soft Shutdown
Celery 5.5 introduced **soft shutdown** - a time-limited warm shutdown that gracefully handles in-flight tasks. Upgrade if possible.

_Sources: [Celery Documentation - Tasks](https://docs.celeryq.dev/en/stable/userguide/tasks.html), [Vinta Software - Advanced Celery](https://www.vintasoftware.com/blog/guide-django-celery-tasks), [Francois Voron - Reliable Delivery](https://www.francoisvoron.com/blog/configure-celery-for-reliable-delivery)_

---

## 3. Windows-Specific Issues & Workarounds

### Current Status [High Confidence]

**Celery dropped Windows support in version 4.** Celery 3 was the last version to officially support Windows. The prefork pool (Celery's default) no longer works on Windows because Windows does not support process forking, only spawning.

### Working Workarounds (2024-2026)

#### 3.1 Prerequisites
```bash
pip install pywin32  # Required for Windows
```

#### 3.2 Solo Pool (Recommended for CPU-bound tasks)
Single-threaded execution in the same process as the worker:

```bash
celery -A myapp worker --pool=solo -l info
```
- **Pros:** Reliable, simple
- **Cons:** No concurrency; spawn multiple workers for parallelism

#### 3.3 Threads Pool (Recommended for I/O-bound tasks)
Uses OS-managed thread pool:

```bash
celery -A myapp worker --pool=threads --concurrency=8 -l info
```
- **Pros:** Good concurrency for I/O tasks, stable on Windows
- **Cons:** GIL limitations for CPU-bound work

#### 3.4 Gevent Pool (Alternative for I/O-bound tasks)
Uses greenlets for cooperative multitasking:

```bash
pip install gevent
celery -A myapp worker --pool=gevent --concurrency=100 -l info
```
- **Pros:** High concurrency for network/IO operations
- **Cons:** Known issues with Python 3.11 (fix: upgrade to greenlet 3.0)

### Known Windows Issues

| Issue | Status | Workaround |
|-------|--------|------------|
| Prefork pool crashes | Won't Fix | Use solo/threads/gevent |
| `FORKED_BY_MULTIPROCESSING` hack | No longer works | Use alternative pools |
| Gevent + Python 3.11 | Fixed | Upgrade to greenlet 3.0 |
| Tasks hang with gevent/eventlet | Open | Check for blocking I/O in tasks |

### Development Recommendation
For Windows development with production Linux deployment:
1. Use **Docker** with Linux containers on Windows
2. Or use **WSL2** (Windows Subsystem for Linux)
3. Match production pool configuration

_Sources: [Simple Thread - Celery 5 on Windows](https://www.simplethread.com/running-celery-5-on-windows/), [Celery School - Celery on Windows](https://celery.school/celery-on-windows), [Medium - Mastering Celery Workers](https://medium.com/@gupta.rishabh2912/mastering-celery-workers-in-django-when-to-use-prefork-eventlet-or-gevent-2679cffae2bd)_

---

## 4. Broker Selection: Redis vs RabbitMQ

### Comparison Matrix [High Confidence]

| Feature | Redis | RabbitMQ |
|---------|-------|----------|
| **Reliability** | Lower (visibility timeout issues) | Higher (persistent messaging, acknowledgments) |
| **Setup Complexity** | Simple | More complex |
| **Visibility Timeout** | Yes (causes redelivery issues) | No |
| **Message Persistence** | Optional | Built-in |
| **Routing Capabilities** | Basic | Advanced (exchanges, routing keys) |
| **Long-running Tasks** | Problematic | Recommended |
| **High Throughput** | Better at very high scale | Good with proper tuning |
| **Operational Overhead** | Lower | Higher |
| **Existing Infrastructure** | Often already in use (caching) | Dedicated deployment |

### When to Choose RabbitMQ
- Mission-critical tasks that cannot be lost
- Complex routing requirements
- Long-running tasks (> 30 minutes)
- Tasks requiring guaranteed exactly-once semantics
- When you need Dead Letter Exchange support

### When to Choose Redis
- Already using Redis for caching
- Simple task routing needs
- AWS environments (ElastiCache)
- Short-duration tasks (< 30 minutes)
- Simpler operational requirements

### Redis-Specific Caveats

```python
# Redis broker issues to be aware of:
# 1. Visibility timeout - tasks redelivered if not ack'd in time
# 2. Key eviction - keys can be removed unexpectedly under memory pressure
# 3. Connection drops - workers may stop consuming after reconnection

# Workaround for connection issues (Celery 5+)
celery -A myapp worker -l info --without-heartbeat --without-gossip --without-mingle
```

_Sources: [UnfoldAI - Redis vs RabbitMQ](https://unfoldai.com/redis-vs-rabbitmq-for-message-broker/), [RabbitSecrets - Broker Selection](https://rabbitsecrets.com/rabbitmq-vs-redis-for-celery/), [Celery Documentation - Brokers](https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/index.html)_

---

## 5. Retry Strategies & Error Handling

### Statistics [High Confidence]
- **60%** of task failures are due to temporary issues resolvable with retries
- Systems with automatic retries recover from temporary failures **90%** of the time
- **30%** of task failures stem from timeout issues

### Retry Configuration Patterns

#### 5.1 Basic Exponential Backoff
```python
@app.task(
    bind=True,
    autoretry_for=(RequestException, ConnectionError),
    retry_backoff=True,           # Exponential backoff
    retry_backoff_max=600,        # Max 10 minutes between retries
    retry_jitter=True,            # Add randomness to prevent thundering herd
    max_retries=5,
)
def fetch_external_api(self, url):
    response = requests.get(url, timeout=30)
    return response.json()
```

#### 5.2 Custom Retry Logic
```python
@app.task(bind=True, max_retries=3)
def process_payment(self, order_id):
    try:
        result = payment_gateway.charge(order_id)
        return result
    except TransientError as exc:
        # Retry transient errors
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
    except PermanentError as exc:
        # Don't retry permanent errors (buggy code, invalid data)
        logger.error(f"Permanent failure for order {order_id}: {exc}")
        raise  # Will go to DLQ if configured
```

#### 5.3 Targeted Exception Handling
**Critical:** Don't blindly retry all exceptions. Retrying buggy code creates infinite loops.

```python
# GOOD: Target specific transient exceptions
autoretry_for=(
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
    redis.exceptions.ConnectionError,
    psycopg2.OperationalError,
)

# BAD: Retrying all exceptions
autoretry_for=(Exception,)  # DON'T DO THIS
```

_Sources: [TestDriven.io - Retrying Failed Tasks](https://testdriven.io/blog/retrying-failed-celery-tasks/), [GitGuardian - Task Resilience](https://blog.gitguardian.com/celery-tasks-retries-errors/)_

---

## 6. Dead Letter Queues (DLQ)

### Purpose [High Confidence]
A Dead Letter Queue captures messages that cannot be processed successfully after all retries are exhausted. This ensures you never lose critical task data.

### Setup with RabbitMQ

```python
from kombu import Exchange, Queue

# Define DLX (Dead Letter Exchange)
dlx = Exchange('dlx', type='direct')
dlq = Queue('dead_letter_queue', exchange=dlx, routing_key='dlq')

app.conf.task_queues = (
    Queue('default', Exchange('default'), routing_key='default',
          queue_arguments={'x-dead-letter-exchange': 'dlx',
                          'x-dead-letter-routing-key': 'dlq'}),
    dlq,
)
```

### Handling Exhausted Retries

```python
from celery.signals import task_failure

@task_failure.connect
def handle_task_failure(sender=None, task_id=None, exception=None,
                        args=None, kwargs=None, traceback=None,
                        einfo=None, **kw):
    task = sender
    if task.request.retries >= task.max_retries:
        # Route to DLQ handler
        dead_letter_handler.delay(
            task_name=task.name,
            task_id=task_id,
            args=args,
            kwargs=kwargs,
            exception=str(exception),
        )
```

### DLQ Processing Options
1. **Debug:** Inspect payloads to identify and fix underlying issues
2. **Retry:** Resend tasks to main queue after fixing issues
3. **Archive:** Log failures for auditing and compliance

_Sources: [Usman Asif - Celery Routing & Error Handling](https://usmanasifbutt.github.io/blog/2025/03/13/celery-task-routing-and-retries.html), [Decappi - Celery Task Lifecycle](https://blog.decappi.dev/posts/celery-task-lifecycle/)_

---

## 7. Idempotency & Duplicate Prevention

### Why Idempotency Matters [High Confidence]

Celery provides "at-least-once" delivery, meaning tasks **can run more than once** due to:
- Visibility timeout expiration
- Worker crashes mid-execution
- Network partitions
- Explicit retries

### Idempotency Patterns

#### 7.1 Idempotency Keys with Database Constraints
```python
from django.db import IntegrityError

@app.task(bind=True, acks_late=True)
def process_order(self, order_id, idempotency_key):
    try:
        # Use database unique constraint to prevent duplicates
        ProcessedOrder.objects.create(
            order_id=order_id,
            idempotency_key=idempotency_key,
        )
    except IntegrityError:
        # Already processed - safe to ignore
        logger.info(f"Order {order_id} already processed")
        return {"status": "already_processed"}

    # Process order...
    return {"status": "success"}
```

#### 7.2 Redis Lock Pattern (celery-singleton)
```python
# Using celery-singleton library
from celery_singleton import Singleton

@app.task(base=Singleton)
def sync_user_data(user_id):
    """Only one instance of this task per user_id can run at a time"""
    # Long-running sync operation
    pass
```

#### 7.3 Custom Lock Implementation
```python
import redis
from contextlib import contextmanager

redis_client = redis.Redis()

@contextmanager
def task_lock(lock_id, timeout=3600):
    lock = redis_client.lock(f"celery_lock:{lock_id}", timeout=timeout)
    acquired = lock.acquire(blocking=False)
    try:
        yield acquired
    finally:
        if acquired:
            lock.release()

@app.task(bind=True)
def unique_task(self, resource_id):
    with task_lock(f"unique_task:{resource_id}") as acquired:
        if not acquired:
            logger.info(f"Task already running for {resource_id}")
            return
        # Perform exclusive operation
```

### Best Practices
- Always design tasks to be idempotent when using `acks_late=True`
- Use database constraints or distributed locks for uniqueness
- Include idempotency keys in task arguments
- Log duplicate detection for debugging

_Sources: [Medium - FastAPI Celery Idempotent Tasks](https://medium.com/@hjparmar1944/fastapi-celery-work-queues-idempotent-tasks-and-retries-that-dont-duplicate-d05e820c904b), [GitHub - celery-singleton](https://github.com/steinitzu/celery-singleton), [Vinta Software - Advanced Celery](https://www.vintasoftware.com/blog/celery-wild-tips-and-tricks-run-async-tasks-real-world)_

---

## 8. Memory Management & OOM Prevention

### The Memory Problem [High Confidence]

Python processes have a "high watermark" - they do not return memory to the OS until the process stops. A single high-memory task can permanently increase a child process's memory usage.

### Known Issues
- **Master process memory leak:** The parent process memory grows with each message, eventually consuming all server memory (GitHub [Issue #8521](https://github.com/celery/celery/issues/8521))
- **OOM Killer behavior:** When a worker child is killed by OOM Killer, the parent may still accept new tasks, causing deadlocks

### Configuration Solutions

#### 8.1 Limit Tasks Per Child
```python
# Recycle workers after N tasks
app.conf.worker_max_tasks_per_child = 1000

# Command line equivalent
celery -A myapp worker --max-tasks-per-child=1000
```

**Warning:** Don't set too low - child process restart overhead (1 second) limits throughput.

#### 8.2 Limit Memory Per Child
```python
# Recycle workers when memory exceeds threshold (in KB)
app.conf.worker_max_memory_per_child = 400000  # 400 MB
```

#### 8.3 Chunk Large Data Processing
```python
@app.task
def process_large_dataset(dataset_ids):
    # BAD: Load all data at once
    # data = load_all_data(dataset_ids)

    # GOOD: Process in chunks
    for chunk in chunked(dataset_ids, 100):
        process_chunk(chunk)
        gc.collect()  # Explicit garbage collection
```

#### 8.4 Supervisor with memmon
```ini
# supervisord.conf
[eventlistener:memmon]
command=memmon -p celery_worker=400MB
events=TICK_60
```

#### 8.5 Use stopasgroup with Supervisor
```ini
[program:celery_worker]
command=celery -A myapp worker
stopasgroup=true  # Prevents orphaned child processes
killasgroup=true
```

_Sources: [Celery Documentation - Optimizing](https://docs.celeryq.dev/en/stable/userguide/optimizing.html), [Medium - Celery RAM Intensive Tasks](https://medium.com/@aaron.reyna/python-celery-ram-intensive-tasks-and-a-memory-leak-c2681ee98c9), [Medium - Two Years with Celery](https://medium.com/squad-engineering/two-years-with-celery-in-production-bug-fix-edition-22238669601d)_

---

## 9. Monitoring & Observability

### Statistics
- **40%** of unresolved exceptions are due to lack of proper logging
- **50%** of developers cite insufficient logging as the primary factor in identifying async task issues
- Organizations with integrated chat alerts respond to incidents **45% faster** (PagerDuty 2025)
- **30%** of Celery-related inefficiencies stem from overlooked queue saturation or invisible task retries

### Flower + Prometheus + Grafana Stack

#### 9.1 Setup Flower with Prometheus Metrics
```bash
# Start Flower with Prometheus endpoint
celery -A myapp flower --port=5555

# CRITICAL: Start workers with events enabled
celery -A myapp worker -E -l info
```

The `-E` flag is required for Prometheus metrics to work.

#### 9.2 Key Metrics to Monitor

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `celery_task_runtime_seconds` | Task execution duration | p95 > 2x expected |
| `celery_task_failed_total` | Failed task count | > 5% of total |
| `celery_worker_tasks_active` | Currently executing tasks | Near concurrency limit |
| `flower_events_total` | Total worker events | Sudden drops |
| Queue length | Pending tasks | Growing continuously |

#### 9.3 Grafana Dashboard
Flower provides an official Grafana dashboard template that can be imported directly.

#### 9.4 Alerting Best Practices
```yaml
# Prometheus alerting rules example
groups:
  - name: celery
    rules:
      - alert: CeleryTaskFailureRate
        expr: rate(celery_task_failed_total[5m]) / rate(celery_task_received_total[5m]) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High Celery task failure rate"

      - alert: CeleryQueueBacklog
        expr: celery_queue_length > 1000
        for: 10m
        labels:
          severity: critical
```

#### 9.5 Integration Recommendations
- Connect alerts to Slack, PagerDuty, or Microsoft Teams
- Monitor both worker metrics AND broker health
- Track queue depth trends over time

_Sources: [Medium - Monitoring Celery with Flower](https://runsewe-seun.medium.com/monitoring-celery-my-walk-with-flower-prometheus-and-grafana-4dcab785561b), [Flower Documentation - Prometheus](https://flower.readthedocs.io/en/latest/prometheus-integration.html), [Medium - Distributed Task Queue Monitoring](https://medium.com/insiderengineering/distributed-task-queue-with-celery-and-monitoring-with-prometheus-metrics-c0958ebefb94)_

---

## 10. Celery Alternatives Comparison

### Performance Benchmarks [High Confidence]
Processing 20,000 jobs with 10 workers using Redis:

| Library | Relative Performance |
|---------|---------------------|
| Huey | ~10x faster than RQ |
| Dramatiq | ~10x faster than RQ |
| Taskiq | ~10x faster than RQ |
| Celery | 2-3x faster than RQ |
| Python-RQ | Baseline |

### Feature Comparison

| Feature | Celery | Dramatiq | RQ | Huey |
|---------|--------|----------|----|----- |
| **Complexity** | High | Medium | Low | Low |
| **Multiple Brokers** | Yes | Yes | Redis only | Redis only |
| **Async/Await** | Partial | Yes | No | Yes |
| **Windows Support** | Workarounds | Better | Workarounds | Workarounds |
| **Documentation** | Good | Good | Excellent | Good |
| **Community** | Large | Medium | Medium | Small |
| **Task Routing** | Advanced | Good | Basic | Basic |
| **Scheduling** | Yes (Beat) | Yes | Yes | Yes |

### Recommendations by Use Case

| Scenario | Recommendation |
|----------|----------------|
| Simple Redis-based app | **RQ** or **Huey** |
| Need RabbitMQ support | **Celery** or **Dramatiq** |
| High I/O concurrency | **Dramatiq** |
| Existing Celery expertise | Stay with **Celery** |
| Starting fresh, simple needs | **Dramatiq** |
| Minimal setup, fast iteration | **Huey** |

### Migration Strategy
Practical approach from the community: "Pick RQ until it doesn't work for you anymore, then migrate to Celery."

_Sources: [Steven Yue - Python Task Queue Comparison](https://stevenyue.com/blogs/exploring-python-task-queue-libraries-with-load-test), [Substack - Celery Alternatives](https://smshahinulislam.substack.com/p/if-celery-bores-you-here-are-some), [Judoscale - Choosing Python Task Queue](https://judoscale.com/blog/choose-python-task-queue)_

---

## 11. Production Best Practices Checklist

### Configuration Checklist

```python
# Production-ready Celery configuration
app.conf.update(
    # === RELIABILITY ===
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_acks_on_failure_or_timeout=True,

    # === TIMEOUTS ===
    task_time_limit=3600,           # 1 hour hard limit
    task_soft_time_limit=3300,      # 55 minutes soft limit
    broker_transport_options={
        'visibility_timeout': 7200,  # Must exceed task_time_limit
    },

    # === MEMORY MANAGEMENT ===
    worker_max_tasks_per_child=1000,
    worker_max_memory_per_child=400000,  # 400MB in KB

    # === PREFETCH ===
    worker_prefetch_multiplier=1,    # For long tasks
    # worker_prefetch_multiplier=4,  # For short tasks

    # === RETRIES ===
    task_default_retry_delay=60,
    task_max_retries=3,

    # === SERIALIZATION ===
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],

    # === RESULT BACKEND ===
    result_expires=86400,  # 24 hours
)
```

### Deployment Checklist

- [ ] **Broker Selection:** RabbitMQ for critical tasks, Redis for simple workloads
- [ ] **Visibility Timeout:** Set higher than longest task duration
- [ ] **Worker Pool:** Match pool type to workload (prefork/gevent/threads)
- [ ] **Memory Limits:** Configure `max_tasks_per_child` or `max_memory_per_child`
- [ ] **Monitoring:** Deploy Flower with Prometheus metrics
- [ ] **Alerts:** Configure queue depth and failure rate alerts
- [ ] **Dead Letter Queue:** Set up DLQ for failed task handling
- [ ] **Idempotency:** Design all `acks_late` tasks to be idempotent
- [ ] **Logging:** Enable comprehensive task logging
- [ ] **Health Checks:** Implement broker and worker health endpoints

### Windows Development Checklist

- [ ] Install `pywin32`
- [ ] Use `--pool=solo` or `--pool=threads` or `--pool=gevent`
- [ ] Consider Docker with Linux containers or WSL2
- [ ] If using gevent with Python 3.11+, upgrade greenlet to 3.0+

---

## 12. Sources & References

### Official Documentation
- [Celery Documentation - Tasks](https://docs.celeryq.dev/en/stable/userguide/tasks.html)
- [Celery Documentation - Configuration](https://docs.celeryq.dev/en/stable/userguide/configuration.html)
- [Celery Documentation - Optimizing](https://docs.celeryq.dev/en/stable/userguide/optimizing.html)
- [Flower Documentation - Prometheus](https://flower.readthedocs.io/en/latest/prometheus-integration.html)

### Technical Articles
- [GitGuardian - Celery Task Resilience](https://blog.gitguardian.com/celery-tasks-retries-errors/)
- [Vinta Software - Advanced Celery for Django](https://www.vintasoftware.com/blog/guide-django-celery-tasks)
- [Francois Voron - Configure Celery for Reliable Delivery](https://www.francoisvoron.com/blog/configure-celery-for-reliable-delivery)
- [Simple Thread - Running Celery 5 on Windows](https://www.simplethread.com/running-celery-5-on-windows/)
- [Celery School - Celery on Windows](https://celery.school/celery-on-windows)
- [TestDriven.io - Retrying Failed Celery Tasks](https://testdriven.io/blog/retrying-failed-celery-tasks/)

### Case Studies & Experience Reports
- [Medium - Two Years with Celery in Production](https://medium.com/squad-engineering/two-years-with-celery-in-production-bug-fix-edition-22238669601d)
- [Medium - Monitoring Celery with Flower, Prometheus and Grafana](https://runsewe-seun.medium.com/monitoring-celery-my-walk-with-flower-prometheus-and-grafana-4dcab785561b)
- [Glinteco - Mitigating Duplicate Task Execution](https://glinteco.com/en/post/glintecos-case-study-mitigating-duplicate-task-execution-with-a-custom-celery-solution/)

### GitHub Issues (Known Problems)
- [Issue #5935](https://github.com/celery/celery/issues/5935) - Long running jobs redelivering
- [Issue #6229](https://github.com/celery/celery/issues/6229) - Visibility timeout with acks_late
- [Issue #7651](https://github.com/celery/celery/issues/7651) - Visibility timeout config issues
- [Issue #8030](https://github.com/celery/celery/issues/8030) - Workers stop after Redis reconnection
- [Issue #8521](https://github.com/celery/celery/issues/8521) - Memory leak in master process

### Comparison Resources
- [Steven Yue - Python Task Queue Libraries Comparison](https://stevenyue.com/blogs/exploring-python-task-queue-libraries-with-load-test)
- [Judoscale - Choosing the Right Python Task Queue](https://judoscale.com/blog/choose-python-task-queue)
- [UnfoldAI - Redis vs RabbitMQ for Celery](https://unfoldai.com/redis-vs-rabbitmq-for-message-broker/)

---

**Research Completed:** 2026-01-26
**Total Sources Verified:** 35+
**Confidence Level:** High (multiple independent sources for all critical claims)
