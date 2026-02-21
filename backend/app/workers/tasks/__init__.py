"""Celery tasks module.

Celery autodiscovery loads tasks from this package. We keep task modules
split by domain (`document_tasks`, `engine_tasks`) so that routing works.
"""

__all__ = [
    "act_validation_tasks",
    "document_tasks",
    "engine_tasks",
    "evaluation_tasks",
    "library_tasks",
    "maintenance_tasks",
    "summary_tasks",
    "table_extraction_tasks",
    "verification_tasks",
]
