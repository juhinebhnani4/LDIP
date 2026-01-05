"""Audit logging service for security events.

This module provides comprehensive audit logging for:
- Matter access attempts (success and failure)
- RLS policy violations
- Security-related operations
- User actions requiring audit trail

All security events are logged both to structured logs (for monitoring)
and optionally to the audit_logs database table (for compliance).
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

import structlog
from pydantic import BaseModel

logger = structlog.get_logger(__name__)


# =============================================================================
# Audit Event Types
# =============================================================================


class AuditEventType(str, Enum):
    """Types of auditable security events."""

    # Matter access events
    MATTER_ACCESS_GRANTED = "matter_access_granted"
    MATTER_ACCESS_DENIED = "matter_access_denied"
    MATTER_CREATED = "matter_created"
    MATTER_DELETED = "matter_deleted"

    # Member management events
    MEMBER_INVITED = "member_invited"
    MEMBER_REMOVED = "member_removed"
    MEMBER_ROLE_CHANGED = "member_role_changed"

    # Document events
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_DELETED = "document_deleted"
    DOCUMENT_ACCESSED = "document_accessed"

    # Security violation events
    RLS_POLICY_VIOLATION = "rls_policy_violation"
    CROSS_MATTER_ATTEMPT = "cross_matter_attempt"
    INVALID_UUID_ATTEMPT = "invalid_uuid_attempt"
    SQL_INJECTION_ATTEMPT = "sql_injection_attempt"
    UNAUTHORIZED_ACCESS_ATTEMPT = "unauthorized_access_attempt"

    # Authentication events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    PASSWORD_RESET_REQUESTED = "password_reset_requested"
    PASSWORD_CHANGED = "password_changed"

    # Export events
    EXPORT_GENERATED = "export_generated"
    EXPORT_DOWNLOADED = "export_downloaded"

    # Finding verification events
    FINDING_VERIFIED = "finding_verified"
    FINDING_REJECTED = "finding_rejected"


class AuditResult(str, Enum):
    """Result of an auditable action."""

    SUCCESS = "success"
    DENIED = "denied"
    ERROR = "error"
    BLOCKED = "blocked"


# =============================================================================
# Audit Log Models
# =============================================================================


class AuditLogEntry(BaseModel):
    """Structured audit log entry."""

    event_type: AuditEventType
    user_id: str | None
    matter_id: str | None
    action: str
    result: AuditResult
    ip_address: str | None
    user_agent: str | None
    path: str | None
    method: str | None
    details: dict[str, Any] | None
    timestamp: datetime

    model_config = {"use_enum_values": True}


# =============================================================================
# Audit Service
# =============================================================================


class AuditService:
    """Service for recording and querying audit logs."""

    def __init__(self, db_client: Any = None):
        """Initialize the audit service.

        Args:
            db_client: Optional Supabase client for database logging.
                      If None, only structured logging is used.
        """
        self.db_client = db_client

    async def log_event(
        self,
        event_type: AuditEventType,
        action: str,
        result: AuditResult,
        user_id: str | None = None,
        matter_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        path: str | None = None,
        method: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log an audit event.

        This method logs to both structured logs and optionally to the database.

        Args:
            event_type: Type of the audit event.
            action: Human-readable action description.
            result: Result of the action.
            user_id: ID of the user performing the action.
            matter_id: ID of the matter being accessed (if applicable).
            ip_address: Client IP address.
            user_agent: Client user agent string.
            path: Request path.
            method: HTTP method.
            details: Additional event-specific details.
        """
        entry = AuditLogEntry(
            event_type=event_type,
            user_id=user_id,
            matter_id=matter_id,
            action=action,
            result=result,
            ip_address=ip_address,
            user_agent=user_agent,
            path=path,
            method=method,
            details=details,
            timestamp=datetime.now(timezone.utc),
        )

        # Always log to structured logs
        self._log_to_structured(entry)

        # Optionally log to database
        if self.db_client is not None:
            await self._log_to_database(entry)

    def _log_to_structured(self, entry: AuditLogEntry) -> None:
        """Log entry to structured logging system."""
        log_data = entry.model_dump(exclude_none=True)

        # Use appropriate log level based on result
        if entry.result == AuditResult.SUCCESS:
            logger.info("audit_event", **log_data)
        elif entry.result == AuditResult.DENIED:
            logger.warning("audit_event", **log_data)
        elif entry.result in (AuditResult.ERROR, AuditResult.BLOCKED):
            logger.error("audit_event", **log_data)

    async def _log_to_database(self, entry: AuditLogEntry) -> None:
        """Log entry to audit_logs database table."""
        try:
            await self.db_client.table("audit_logs").insert(
                {
                    "event_type": entry.event_type,
                    "user_id": entry.user_id,
                    "matter_id": entry.matter_id,
                    "action": entry.action,
                    "result": entry.result,
                    "ip_address": entry.ip_address,
                    "user_agent": entry.user_agent,
                    "path": entry.path,
                    "method": entry.method,
                    "details": entry.details,
                    "created_at": entry.timestamp.isoformat(),
                }
            ).execute()
        except Exception as e:
            # Don't fail the request if audit logging fails
            logger.error(
                "audit_database_log_failed",
                error=str(e),
                event_type=entry.event_type,
                user_id=entry.user_id,
            )

    # =========================================================================
    # Convenience Methods for Common Events
    # =========================================================================

    async def log_matter_access(
        self,
        user_id: str,
        matter_id: str,
        action: str,
        granted: bool,
        ip_address: str | None = None,
        path: str | None = None,
        reason: str | None = None,
    ) -> None:
        """Log a matter access attempt.

        Args:
            user_id: ID of the user attempting access.
            matter_id: ID of the matter being accessed.
            action: The action being attempted (view, edit, delete, etc.).
            granted: Whether access was granted.
            ip_address: Client IP address.
            path: Request path.
            reason: Reason for denial (if applicable).
        """
        event_type = (
            AuditEventType.MATTER_ACCESS_GRANTED
            if granted
            else AuditEventType.MATTER_ACCESS_DENIED
        )
        result = AuditResult.SUCCESS if granted else AuditResult.DENIED

        details = None
        if reason:
            details = {"reason": reason}

        await self.log_event(
            event_type=event_type,
            action=f"matter_{action}",
            result=result,
            user_id=user_id,
            matter_id=matter_id,
            ip_address=ip_address,
            path=path,
            details=details,
        )

    async def log_security_violation(
        self,
        violation_type: AuditEventType,
        user_id: str | None,
        ip_address: str | None,
        path: str | None,
        details: dict[str, Any],
    ) -> None:
        """Log a security violation attempt.

        Args:
            violation_type: Type of security violation.
            user_id: ID of the user (if authenticated).
            ip_address: Client IP address.
            path: Request path.
            details: Details about the violation attempt.
        """
        await self.log_event(
            event_type=violation_type,
            action="security_violation",
            result=AuditResult.BLOCKED,
            user_id=user_id,
            ip_address=ip_address,
            path=path,
            details=details,
        )

    async def log_rls_violation(
        self,
        user_id: str,
        matter_id: str,
        table_name: str,
        operation: str,
        ip_address: str | None = None,
    ) -> None:
        """Log an RLS policy violation.

        Args:
            user_id: ID of the user.
            matter_id: ID of the matter they tried to access.
            table_name: Database table where violation occurred.
            operation: Database operation (SELECT, INSERT, etc.).
            ip_address: Client IP address.
        """
        await self.log_event(
            event_type=AuditEventType.RLS_POLICY_VIOLATION,
            action=f"rls_violation_{operation.lower()}",
            result=AuditResult.BLOCKED,
            user_id=user_id,
            matter_id=matter_id,
            ip_address=ip_address,
            details={
                "table": table_name,
                "operation": operation,
            },
        )

    async def log_cross_matter_attempt(
        self,
        user_id: str,
        authorized_matter_id: str,
        attempted_matter_id: str,
        ip_address: str | None = None,
        path: str | None = None,
    ) -> None:
        """Log a cross-matter access attempt.

        Args:
            user_id: ID of the user.
            authorized_matter_id: Matter the user is authorized for.
            attempted_matter_id: Matter they tried to access.
            ip_address: Client IP address.
            path: Request path.
        """
        await self.log_event(
            event_type=AuditEventType.CROSS_MATTER_ATTEMPT,
            action="cross_matter_access",
            result=AuditResult.BLOCKED,
            user_id=user_id,
            matter_id=attempted_matter_id,
            ip_address=ip_address,
            path=path,
            details={
                "authorized_matter_id": authorized_matter_id,
                "attempted_matter_id": attempted_matter_id,
            },
        )

    async def log_document_access(
        self,
        user_id: str,
        matter_id: str,
        document_id: str,
        action: str,
        ip_address: str | None = None,
    ) -> None:
        """Log document access.

        Args:
            user_id: ID of the user.
            matter_id: ID of the matter.
            document_id: ID of the document.
            action: Action performed (view, download, etc.).
            ip_address: Client IP address.
        """
        await self.log_event(
            event_type=AuditEventType.DOCUMENT_ACCESSED,
            action=f"document_{action}",
            result=AuditResult.SUCCESS,
            user_id=user_id,
            matter_id=matter_id,
            ip_address=ip_address,
            details={"document_id": document_id},
        )

    async def log_finding_verification(
        self,
        user_id: str,
        matter_id: str,
        finding_id: str,
        verified: bool,
        notes: str | None = None,
    ) -> None:
        """Log finding verification.

        Args:
            user_id: ID of the verifying attorney.
            matter_id: ID of the matter.
            finding_id: ID of the finding.
            verified: Whether the finding was verified or rejected.
            notes: Verification notes.
        """
        event_type = (
            AuditEventType.FINDING_VERIFIED
            if verified
            else AuditEventType.FINDING_REJECTED
        )

        await self.log_event(
            event_type=event_type,
            action="finding_verification",
            result=AuditResult.SUCCESS,
            user_id=user_id,
            matter_id=matter_id,
            details={
                "finding_id": finding_id,
                "verified": verified,
                "notes": notes,
            },
        )


# =============================================================================
# Singleton Instance
# =============================================================================

# Global audit service instance (initialized without DB client by default)
_audit_service: AuditService | None = None


def get_audit_service(db_client: Any = None) -> AuditService:
    """Get or create the audit service instance.

    Args:
        db_client: Optional Supabase client for database logging.

    Returns:
        AuditService instance.
    """
    global _audit_service

    if _audit_service is None:
        _audit_service = AuditService(db_client)
    elif db_client is not None and _audit_service.db_client is None:
        # Update with DB client if provided later
        _audit_service.db_client = db_client

    return _audit_service


# =============================================================================
# Database Table Migration (for reference)
# =============================================================================

AUDIT_LOGS_MIGRATION = """
-- Create audit_logs table for compliance and security auditing
-- This should be added to a migration file if database logging is enabled

CREATE TABLE IF NOT EXISTS public.audit_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_type text NOT NULL,
  user_id uuid REFERENCES auth.users(id),
  matter_id uuid REFERENCES public.matters(id),
  action text NOT NULL,
  result text NOT NULL,
  ip_address inet,
  user_agent text,
  path text,
  method text,
  details jsonb,
  created_at timestamptz DEFAULT now()
);

-- Indexes for common queries
CREATE INDEX idx_audit_logs_event_type ON public.audit_logs(event_type);
CREATE INDEX idx_audit_logs_user_id ON public.audit_logs(user_id);
CREATE INDEX idx_audit_logs_matter_id ON public.audit_logs(matter_id);
CREATE INDEX idx_audit_logs_created_at ON public.audit_logs(created_at);
CREATE INDEX idx_audit_logs_result ON public.audit_logs(result);

-- Composite index for security analysis
CREATE INDEX idx_audit_logs_security ON public.audit_logs(event_type, result, created_at)
  WHERE result IN ('denied', 'blocked', 'error');

-- Note: audit_logs should NOT have RLS enabled
-- It should only be accessible via service role for security analysis
"""
