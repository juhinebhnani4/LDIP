"""Celery tasks related to engine execution.

These are intentionally minimal placeholders for the foundation story.
Future stories will implement calling engine modules and persisting results.
"""

import structlog

from app.workers.celery import celery_app

logger = structlog.get_logger(__name__)

@celery_app.task(name="app.workers.tasks.engine_tasks.run_engine")  # type: ignore[untyped-decorator]
def run_engine(matter_id: str, engine: str) -> dict[str, str]:
    """Placeholder task for running a specific engine against a matter.

    Args:
        matter_id: Matter identifier.
        engine: Engine name (e.g., "citation", "timeline", "contradiction").

    Returns:
        Task result payload.
    """
    logger.info("engine_task_placeholder", task="run_engine", matter_id=matter_id, engine=engine)
    return {"status": "not_implemented", "matter_id": matter_id, "engine": engine}


