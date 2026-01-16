"""Celery application configuration."""

import os
import ssl
from pathlib import Path

from celery import Celery
from dotenv import load_dotenv

# Load .env file to set GOOGLE_APPLICATION_CREDENTIALS before importing settings
# This is needed because Google Cloud SDK reads directly from os.environ
env_file = Path(__file__).parent.parent.parent / ".env"
if env_file.exists():
    load_dotenv(env_file)

from app.core.config import get_settings

settings = get_settings()

# Create Celery application
celery_app = Celery(
    "ldip_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# SSL configuration for Upstash Redis (rediss:// protocol)
# Only apply SSL settings if using TLS connection
_uses_tls = settings.celery_broker_url.startswith("rediss://")
_ssl_config = {"ssl_cert_reqs": ssl.CERT_REQUIRED} if _uses_tls else {}

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Result backend settings
    result_expires=3600,  # 1 hour
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_concurrency=4,
    # Priority queues configuration
    task_queues={
        # Align with architecture convention: high / default / low
        "default": {"exchange": "default", "binding_key": "default"},
        "high": {"exchange": "high", "binding_key": "high"},
        "low": {"exchange": "low", "binding_key": "low"},
    },
    task_default_queue="default",
    # Task routing based on priority
    task_routes={
        # Document ingestion tasks can be long-running; keep in default until
        # we implement true priority routing by story.
        "app.workers.tasks.document_tasks.*": {"queue": "default"},
        "app.workers.tasks.chunked_document_tasks.*": {"queue": "default"},
        "app.workers.tasks.engine_tasks.*": {"queue": "default"},
    },
    # SSL configuration for Upstash Redis (rediss:// protocol)
    # These settings are required for TLS connections to serverless Redis
    broker_use_ssl=_ssl_config if _uses_tls else None,
    redis_backend_use_ssl=_ssl_config if _uses_tls else None,
    # Celery Beat schedule for periodic tasks
    beat_schedule={
        "recover-stale-jobs": {
            "task": "app.workers.tasks.maintenance_tasks.recover_stale_jobs",
            "schedule": settings.job_recovery_scan_interval * 60,  # Convert minutes to seconds
            "options": {"queue": "low"},  # Low priority queue
        },
        "cleanup-stale-chunks": {
            "task": "app.workers.tasks.maintenance_tasks.cleanup_stale_chunks",
            "schedule": 3600,  # Run every hour
            "args": [24],  # 24 hour retention period
            "options": {"queue": "low"},  # Low priority queue
        },
    },
)

# Auto-discover tasks from the tasks submodule
celery_app.autodiscover_tasks(["app.workers.tasks"])

# Explicit imports to ensure tasks are registered
# (autodiscover can be unreliable on Windows)
from app.workers.tasks import (  # noqa: E402, F401
    chunked_document_tasks,
    document_tasks,
    engine_tasks,
    maintenance_tasks,
    verification_tasks,
)
