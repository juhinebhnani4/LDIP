"""Celery application configuration."""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

# Create Celery application
celery_app = Celery(
    "ldip_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

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
        "app.workers.tasks.engine_tasks.*": {"queue": "default"},
    },
)

# Auto-discover tasks from the tasks submodule
celery_app.autodiscover_tasks(["app.workers.tasks"])
