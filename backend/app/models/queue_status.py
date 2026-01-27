"""Pydantic models for queue status monitoring.

Story 5.6: Queue Depth Visibility Dashboard

Provides response models for the queue status monitoring API endpoints.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class QueueMetrics(BaseModel):
    """Metrics for a single Celery queue."""

    queue_name: str = Field(..., description="Queue identifier", alias="queueName")
    pending_count: int = Field(
        default=0, description="Jobs waiting to be processed", alias="pendingCount"
    )
    active_count: int = Field(
        default=0, description="Jobs currently being processed", alias="activeCount"
    )
    failed_count: int = Field(
        default=0, description="Failed jobs in last 24 hours", alias="failedCount"
    )
    completed_24h: int = Field(
        default=0, description="Jobs completed in last 24 hours", alias="completed24h"
    )
    avg_processing_time_ms: int = Field(
        default=0,
        description="Average processing time in milliseconds",
        alias="avgProcessingTimeMs",
    )
    trend: Literal["increasing", "decreasing", "stable"] = Field(
        default="stable", description="Queue depth trend direction"
    )
    alert_triggered: bool = Field(
        default=False,
        description="True if pending count exceeds threshold",
        alias="alertTriggered",
    )

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "queueName": "default",
                "pendingCount": 25,
                "activeCount": 5,
                "failedCount": 2,
                "completed24h": 150,
                "avgProcessingTimeMs": 45000,
                "trend": "stable",
                "alertTriggered": False,
            }
        },
    )


class QueueStatusData(BaseModel):
    """Aggregated queue status data for all queues."""

    queues: list[QueueMetrics] = Field(
        default_factory=list, description="Metrics for each queue"
    )
    total_pending: int = Field(
        default=0, description="Total pending jobs across all queues", alias="totalPending"
    )
    total_active: int = Field(
        default=0, description="Total active jobs across all queues", alias="totalActive"
    )
    active_workers: int = Field(
        default=0, description="Number of active Celery workers", alias="activeWorkers"
    )
    last_checked_at: str = Field(
        ..., description="ISO timestamp when metrics were collected", alias="lastCheckedAt"
    )
    alert_threshold: int = Field(
        default=100,
        description="Pending job threshold that triggers alerts",
        alias="alertThreshold",
    )
    is_healthy: bool = Field(
        default=True,
        description="False if any queue exceeds alert threshold",
        alias="isHealthy",
    )

    model_config = ConfigDict(
        populate_by_name=True,
    )


class QueueStatusResponse(BaseModel):
    """API response for queue status monitoring endpoint."""

    data: QueueStatusData

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data": {
                    "queues": [
                        {
                            "queueName": "celery",
                            "pendingCount": 25,
                            "activeCount": 5,
                            "failedCount": 2,
                            "completed24h": 150,
                            "avgProcessingTimeMs": 45000,
                            "trend": "stable",
                            "alertTriggered": False,
                        },
                        {
                            "queueName": "high",
                            "pendingCount": 5,
                            "activeCount": 2,
                            "failedCount": 0,
                            "completed24h": 50,
                            "avgProcessingTimeMs": 30000,
                            "trend": "decreasing",
                            "alertTriggered": False,
                        },
                        {
                            "queueName": "low",
                            "pendingCount": 100,
                            "activeCount": 1,
                            "failedCount": 5,
                            "completed24h": 200,
                            "avgProcessingTimeMs": 60000,
                            "trend": "increasing",
                            "alertTriggered": True,
                        },
                    ],
                    "totalPending": 130,
                    "totalActive": 8,
                    "activeWorkers": 3,
                    "lastCheckedAt": "2026-01-27T10:30:00Z",
                    "alertThreshold": 100,
                    "isHealthy": False,
                }
            }
        }
    )


class QueueHealthResponse(BaseModel):
    """Health check response for queue monitoring."""

    data: dict = Field(
        default_factory=dict,
        description="Health check data",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data": {
                    "status": "healthy",
                    "redisConnected": True,
                    "workerCount": 3,
                    "lastCheckedAt": "2026-01-27T10:30:00Z",
                }
            }
        }
    )
