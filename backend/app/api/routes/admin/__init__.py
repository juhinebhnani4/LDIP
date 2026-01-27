"""Admin routes package."""

from app.api.routes.admin.pipeline import router as pipeline_router
from app.api.routes.admin.quota import router as quota_router

__all__ = ["pipeline_router", "quota_router"]
