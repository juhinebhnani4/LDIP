"""Send a test email to verify Resend integration.

Usage:
    python send_test_email.py [recipient_email]

If no email provided, uses the test user email from .env
"""

import asyncio
import sys

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from app.core.config import get_settings
from app.services.email_service import get_email_service


async def send_test_email(recipient: str | None = None):
    """Send a test processing complete email."""
    settings = get_settings()

    # Use provided email or default to test user
    to_email = recipient or "kiarabinwani@gmail.com"

    print("Email Configuration:")
    print(f"  - Resend API Key: {'***' + settings.resend_api_key[-4:] if settings.resend_api_key else 'NOT SET'}")
    print(f"  - From Address: {settings.email_from_address}")
    print(f"  - Notifications Enabled: {settings.email_notifications_enabled}")
    print(f"  - Base URL: {settings.email_base_url}")
    print()

    if not settings.resend_api_key:
        print("ERROR: RESEND_API_KEY not configured in .env")
        return False

    service = get_email_service()

    print(f"Sending test email to: {to_email}")
    print()

    try:
        success = await service.send_processing_complete_email(
            user_email=to_email,
            matter_name="Test Matter - Email Verification",
            doc_count=5,
            success_count=4,
            failed_count=1,
            workspace_url=f"{settings.email_base_url}/matters/test-123",
        )

        if success:
            print("SUCCESS: Email sent successfully!")
            print(f"Check inbox at: {to_email}")
        else:
            print("FAILED: Email was not sent (feature may be disabled)")

        return success

    except Exception as e:
        print(f"ERROR: {e}")
        return False


if __name__ == "__main__":
    recipient = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(send_test_email(recipient))
