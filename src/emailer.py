from __future__ import annotations

import base64
import json
import mimetypes
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable

import requests

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
    """Send email with PDF attachments.

    Priority:
      1. Brevo HTTP API  — if BREVO_API_KEY is set (works on Render / any cloud).
      2. SMTP_SSL 465    — implicit TLS fallback.
      3. SMTP STARTTLS   — last resort.
    """
    attachment_paths = [p for p in attachments if p.exists()]

    if settings.brevo_api_key:
        _send_via_brevo(settings, to_address, subject, body, attachment_paths)
        return

    # SMTP fallbacks
    missing = [f for f in REQUIRED_SMTP_FIELDS if not getattr(settings, f)]
    if missing:
        raise EmailConfigurationError("Missing email settings: " + ", ".join(missing))

    message = _build_message(settings, to_address, subject, body, attachment_paths)
    smtp_timeout = max(settings.request_timeout_seconds, 60)

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(settings.smtp_host, 465, timeout=smtp_timeout, context=ctx) as s:
            s.login(settings.smtp_username, settings.smtp_password)
            s.send_message(message)
        return
    except Exception:
        pass

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=smtp_timeout) as s:
        if settings.smtp_use_starttls:
            s.starttls()
        s.login(settings.smtp_username, settings.smtp_password)
        s.send_message(message)


# ── Brevo (HTTP API — works from any cloud host) ───────────────────────────────

def _send_via_brevo(
    settings: Settings,
    to_address: str,
    subject: str,
    body: str,
    attachment_paths: list[Path],
) -> None:
    from_email = settings.email_from or settings.smtp_username

    attachments = []
    for path in attachment_paths:
        mime_type, _ = mimetypes.guess_type(path.name)
        attachments.append({
            "name": path.name,
            "content": base64.b64encode(path.read_bytes()).decode(),
        })

    payload: dict = {
        "sender": {"email": from_email},
        "to": [{"email": to_address}],
        "subject": subject,
        "textContent": body,
    }
    if attachments:
        payload["attachment"] = attachments

    resp = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={
            "api-key": settings.brevo_api_key,
            "Content-Type": "application/json",
        },
        data=json.dumps(payload),
        timeout=30,
    )

    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Brevo error {resp.status_code}: {resp.text[:300]}")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_message(
    settings: Settings,
    to_address: str,
    subject: str,
    body: str,
    attachment_paths: list[Path],
) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.email_from
    message["To"] = to_address
    message.set_content(body)

    for path in attachment_paths:
        data = path.read_bytes()
        mime_type, _ = mimetypes.guess_type(path.name)
        maintype, subtype = (mime_type or "application/octet-stream").split("/", 1)
        message.add_attachment(
            data, maintype=maintype, subtype=subtype, filename=path.name
        )

    return message
