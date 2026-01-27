"""Processing complete email template.

Gap #19: Email Notification on Processing Completion - Task 6

Renders HTML and plain text email content for processing completion notifications.
"""

from __future__ import annotations


def render_processing_complete_email(
    matter_name: str,
    doc_count: int,
    success_count: int,
    failed_count: int,
    workspace_url: str,
) -> tuple[str, str, str]:
    """Render processing complete email content.

    Gap #19: AC #1 - Email content with matter name, document count, status summary.

    Args:
        matter_name: Name of the matter.
        doc_count: Total documents in batch.
        success_count: Successfully processed documents.
        failed_count: Failed documents.
        workspace_url: Deep link to matter workspace.

    Returns:
        Tuple of (subject, html_content, text_content).
    """
    # Build subject
    subject = f"Your documents for {matter_name} are ready"

    # Build status message
    if failed_count == 0:
        status_message = f"{success_count} document{'s' if success_count != 1 else ''} processed successfully"
        status_color = "#22c55e"  # green
    else:
        status_message = f"{success_count} document{'s' if success_count != 1 else ''} processed successfully, {failed_count} need{'s' if failed_count == 1 else ''} attention"
        status_color = "#f59e0b"  # amber

    # Render HTML
    html_content = _render_html_template(
        matter_name=matter_name,
        status_message=status_message,
        status_color=status_color,
        doc_count=doc_count,
        success_count=success_count,
        failed_count=failed_count,
        workspace_url=workspace_url,
    )

    # Render plain text
    text_content = _render_text_template(
        matter_name=matter_name,
        status_message=status_message,
        doc_count=doc_count,
        success_count=success_count,
        failed_count=failed_count,
        workspace_url=workspace_url,
    )

    return subject, html_content, text_content


def _render_html_template(
    matter_name: str,
    status_message: str,
    status_color: str,
    doc_count: int,
    success_count: int,
    failed_count: int,
    workspace_url: str,
) -> str:
    """Render HTML email template.

    Simple, clean design optimized for email clients (Gmail, Outlook).
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Documents Ready - Jaanch</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f9fafb;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" style="width: 100%; max-width: 600px; border-collapse: collapse; background-color: #ffffff; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 32px 32px 24px 32px; border-bottom: 1px solid #e5e7eb;">
                            <h1 style="margin: 0; font-size: 24px; font-weight: 600; color: #111827;">
                                Jaanch
                            </h1>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 32px;">
                            <h2 style="margin: 0 0 16px 0; font-size: 20px; font-weight: 600; color: #111827;">
                                Your documents are ready
                            </h2>

                            <p style="margin: 0 0 24px 0; font-size: 16px; color: #4b5563; line-height: 1.5;">
                                Processing has completed for your upload to <strong>{matter_name}</strong>.
                            </p>

                            <!-- Status Box -->
                            <div style="background-color: #f9fafb; border-radius: 8px; padding: 20px; margin-bottom: 24px;">
                                <p style="margin: 0 0 8px 0; font-size: 14px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em;">
                                    Status
                                </p>
                                <p style="margin: 0; font-size: 18px; font-weight: 600; color: {status_color};">
                                    {status_message}
                                </p>
                            </div>

                            <!-- Summary -->
                            <table role="presentation" style="width: 100%; border-collapse: collapse; margin-bottom: 24px;">
                                <tr>
                                    <td style="padding: 12px 0; border-bottom: 1px solid #e5e7eb;">
                                        <span style="color: #6b7280;">Total documents</span>
                                    </td>
                                    <td style="padding: 12px 0; border-bottom: 1px solid #e5e7eb; text-align: right; font-weight: 600; color: #111827;">
                                        {doc_count}
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 12px 0; border-bottom: 1px solid #e5e7eb;">
                                        <span style="color: #6b7280;">Successful</span>
                                    </td>
                                    <td style="padding: 12px 0; border-bottom: 1px solid #e5e7eb; text-align: right; font-weight: 600; color: #22c55e;">
                                        {success_count}
                                    </td>
                                </tr>
                                {"<tr><td style='padding: 12px 0;'><span style='color: #6b7280;'>Need attention</span></td><td style='padding: 12px 0; text-align: right; font-weight: 600; color: #ef4444;'>" + str(failed_count) + "</td></tr>" if failed_count > 0 else ""}
                            </table>

                            <!-- CTA Button -->
                            <table role="presentation" style="width: 100%; border-collapse: collapse;">
                                <tr>
                                    <td align="center">
                                        <a href="{workspace_url}" style="display: inline-block; padding: 14px 28px; background-color: #2563eb; color: #ffffff; text-decoration: none; font-size: 16px; font-weight: 600; border-radius: 6px;">
                                            View in Jaanch
                                        </a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 24px 32px; border-top: 1px solid #e5e7eb; background-color: #f9fafb; border-radius: 0 0 8px 8px;">
                            <p style="margin: 0 0 8px 0; font-size: 14px; color: #6b7280; text-align: center;">
                                You received this email because you uploaded documents to Jaanch.
                            </p>
                            <p style="margin: 0; font-size: 14px; color: #6b7280; text-align: center;">
                                <a href="{workspace_url.rsplit('/', 2)[0]}/settings" style="color: #2563eb; text-decoration: none;">
                                    Manage notification preferences
                                </a>
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""


def _render_text_template(
    matter_name: str,
    status_message: str,
    doc_count: int,
    success_count: int,
    failed_count: int,
    workspace_url: str,
) -> str:
    """Render plain text email template.

    Fallback for email clients that don't support HTML.
    """
    failed_line = f"\nNeed attention: {failed_count}" if failed_count > 0 else ""

    return f"""Jaanch - Your documents are ready

Processing has completed for your upload to {matter_name}.

STATUS: {status_message}

Summary:
- Total documents: {doc_count}
- Successful: {success_count}{failed_line}

View your documents: {workspace_url}

---

You received this email because you uploaded documents to Jaanch.
To manage notification preferences, visit your account settings.
"""
