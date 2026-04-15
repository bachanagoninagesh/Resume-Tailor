from __future__ import annotations

import mimetypes
import smtplib
import socket
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
    """Send an email with one or more PDF files attached directly (no zip)."""
    missing = [field for field in REQUIRED_SMTP_FIELDS if not getattr(settings, field)]
    if missing:
        raise EmailConfigurationError("Missing email settings: " + ", ".join(missing))

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

    # Resolve to IPv4 explicitly — avoids [Errno 101] Network is unreachable
    # on cloud hosts (e.g. Render) where IPv6 is not routed.
    host = settings.smtp_host
    try:
        host = socket.getaddrinfo(host, settings.smtp_port, socket.AF_INET)[0][4][0]
    except (socket.gaierror, IndexError):
        pass  # fall back to original hostname if resolution fails

    # Use 60s timeout for SMTP — cloud platforms can be slow on initial
    # TCP + TLS handshake; 25s (the Anthropic API timeout) is too short.
    smtp_timeout = max(settings.request_timeout_seconds, 60)

    with smtplib.SMTP(host, settings.smtp_port, timeout=smtp_timeout) as server:
        if settings.smtp_use_starttls:
            server.starttls()
        server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)
