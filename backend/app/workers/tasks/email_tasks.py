"""Email notification tasks.

Gap #19: Email Notification on Processing Completion

Celery tasks for sending email notifications asynchronously.
Email failures are isolated from the document processing pipeline.
"""

import asyncio

import structlog

from app.workers.celery import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(
    name="app.workers.tasks.email_tasks.send_processing_complete_notification",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
)
def send_processing_complete_notification(
    self,
    matter_id: str,
    user_id: str,
    doc_count: int,
    success_count: int,
    failed_count: int,
) -> dict:
    """Send email notification when document processing completes.

    Gap #19: AC #1 - Email sent when upload batch completes.
    Gap #19: AC #2 - Opt-out respected.
    Gap #19: AC #4 - Email resilience with retries.

    Args:
        matter_id: UUID of the matter.
        user_id: UUID of the user who uploaded documents.
        doc_count: Total documents in the batch.
        success_count: Successfully processed documents.
        failed_count: Documents that failed processing.

    Returns:
        Dictionary with result status.
    """
    from app.core.config import get_settings
    from app.services.email_service import get_email_service
    from app.services.supabase.client import get_service_client

    settings = get_settings()

    logger.info(
        "email_notification_task_started",
        matter_id=matter_id,
        user_id=user_id,
        doc_count=doc_count,
        success_count=success_count,
        failed_count=failed_count,
        task_id=self.request.id,
    )

    # Check global feature flag
    if not settings.email_notifications_enabled:
        logger.info(
            "email_notification_skipped",
            reason="global_feature_disabled",
            matter_id=matter_id,
        )
        return {"status": "skipped", "reason": "Email notifications disabled globally"}

    # Check Resend configuration
    if not settings.resend_api_key:
        logger.info(
            "email_notification_skipped",
            reason="resend_not_configured",
            matter_id=matter_id,
        )
        return {"status": "skipped", "reason": "Resend API key not configured"}

    try:
        client = get_service_client()
        if not client:
            logger.error("email_notification_failed", reason="supabase_not_configured")
            return {"status": "error", "reason": "Supabase not configured"}

        # Get user email and check preference
        user_data = _get_user_data_sync(client, user_id)
        if not user_data:
            logger.warning(
                "email_notification_skipped",
                reason="user_not_found",
                user_id=user_id,
            )
            return {"status": "skipped", "reason": "User not found"}

        user_email = user_data.get("email")
        if not user_email:
            logger.warning(
                "email_notification_skipped",
                reason="no_email",
                user_id=user_id,
            )
            return {"status": "skipped", "reason": "User has no email"}

        # Check user preference (Gap #19: AC #2)
        preferences = _get_user_preferences_sync(client, user_id)
        if preferences and not preferences.get("email_notifications_processing", True):
            logger.info(
                "email_notification_skipped",
                reason="user_opted_out",
                user_id=user_id,
                matter_id=matter_id,
            )
            return {"status": "skipped", "reason": "User opted out of email notifications"}

        # Get matter name
        matter_data = _get_matter_data_sync(client, matter_id)
        matter_name = matter_data.get("title", "Your Matter") if matter_data else "Your Matter"

        # Build workspace URL
        workspace_url = f"{settings.email_base_url}/matters/{matter_id}/documents"

        # Send email
        email_service = get_email_service()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            success = loop.run_until_complete(
                email_service.send_processing_complete_email(
                    user_email=user_email,
                    matter_name=matter_name,
                    doc_count=doc_count,
                    success_count=success_count,
                    failed_count=failed_count,
                    workspace_url=workspace_url,
                )
            )
        finally:
            loop.close()

        if success:
            logger.info(
                "email_notification_sent",
                matter_id=matter_id,
                user_id=user_id,
                user_email=user_email,
                doc_count=doc_count,
            )
            return {"status": "sent", "user_email": user_email}
        else:
            logger.warning(
                "email_notification_failed_to_send",
                matter_id=matter_id,
                user_id=user_id,
            )
            return {"status": "error", "reason": "Failed to send email"}

    except Exception as e:
        logger.error(
            "email_notification_task_error",
            error=str(e),
            error_type=type(e).__name__,
            matter_id=matter_id,
            user_id=user_id,
            task_id=self.request.id,
        )
        # Let Celery retry handle this
        raise


def _get_user_data_sync(client, user_id: str) -> dict | None:
    """Get user data from Supabase Auth (synchronous).

    Args:
        client: Supabase client.
        user_id: User UUID.

    Returns:
        User data dict or None.
    """
    try:
        result = client.auth.admin.get_user_by_id(user_id)
        if result.user:
            return {
                "id": result.user.id,
                "email": result.user.email,
            }
    except Exception as e:
        logger.warning("get_user_data_failed", user_id=user_id, error=str(e))
    return None


def _get_user_preferences_sync(client, user_id: str) -> dict | None:
    """Get user preferences (synchronous).

    Args:
        client: Supabase client.
        user_id: User UUID.

    Returns:
        User preferences dict or None.
    """
    try:
        result = (
            client.table("user_preferences")
            .select("email_notifications_processing")
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        return result.data
    except Exception as e:
        logger.warning("get_user_preferences_failed", user_id=user_id, error=str(e))
    return None


def _get_matter_data_sync(client, matter_id: str) -> dict | None:
    """Get matter data (synchronous).

    Args:
        client: Supabase client.
        matter_id: Matter UUID.

    Returns:
        Matter data dict or None.
    """
    try:
        result = (
            client.table("matters")
            .select("title")
            .eq("id", matter_id)
            .single()
            .execute()
        )
        return result.data
    except Exception as e:
        logger.warning("get_matter_data_failed", matter_id=matter_id, error=str(e))
    return None
