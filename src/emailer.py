from __future__ import annotations

import mimetypes
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable

from src.settings import Settings


class EmailConfigurationError(RuntimeError):
    pass


REQUIRED_SMTP_FIELDS = (
    "smtp_host",
    "smtp_username",
    "smtp_password",
    "email_from",
)


def send_results_email(
    settings: Settings,
    to_address: str,
    subject: str,
    body: str,
    attachments: Iterable[Path],
) -> None:
    """Send an email with one or more PDF files attached directly (no zip).

    Tries two methods in order:
      1. SMTP_SSL on port 465  — implicit TLS, most reliable on cloud hosts.
      2. SMTP + STARTTLS on configured port — standard fallback.
    """
    missing = [field for field in REQUIRED_SMTP_FIELDS if not getattr(settings, field)]
    if missing:
        raise EmailConfigurationError("Missing email settings: " + ", ".join(missing))

    message = _build_message(settings, to_address, subject, body, attachments)
    smtp_timeout = max(settings.request_timeout_seconds, 60)

    # Try port 465 (SMTP_SSL) first — bypasses STARTTLS negotiation issues
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(settings.smtp_host, 465, timeout=smtp_timeout, context=context) as server:
            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
        return
    except Exception:
        pass  # fall through to STARTTLS

    # Fallback: SMTP + STARTTLS on configured port (587 by default)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=smtp_timeout) as server:
        if settings.smtp_use_starttls:
            server.starttls()
        server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)


def _build_message(
    settings: Settings,
    to_address: str,
    subject: str,
    body: str,
    attachments: Iterable[Path],
) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.email_from
    message["To"] = to_address
    message.set_content(body)

    for attachment in attachments:
        if not attachment.exists():
            continue
        data = attachment.read_bytes()
        mime_type, _ = mimetypes.guess_type(attachment.name)
        maintype, subtype = (mime_type or "application/octet-stream").split("/", 1)
        message.add_attachment(
            data, maintype=maintype, subtype=subtype, filename=attachment.name
        )

    return message
