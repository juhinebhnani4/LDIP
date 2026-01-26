"""Celery tasks module.

Celery autodiscovery loads tasks from this package. We keep task modules
split by domain (`document_tasks`, `engine_tasks`) so that routing works.
"""

__all__ = [
    "document_tasks",
    "engine_tasks",
    "library_tasks",
    "verification_tasks",
    "maintenance_tasks",
    "table_extraction_tasks",
    "evaluation_tasks",
    "act_validation_tasks",
]
