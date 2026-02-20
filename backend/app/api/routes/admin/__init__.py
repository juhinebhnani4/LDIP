"""Admin routes package."""

from app.api.routes.admin.maintenance import router as maintenance_router
from app.api.routes.admin.monitoring import router as monitoring_router
from app.api.routes.admin.pipeline import router as pipeline_router
from app.api.routes.admin.quota import router as quota_router

__all__ = ["maintenance_router", "monitoring_router", "pipeline_router", "quota_router"]
