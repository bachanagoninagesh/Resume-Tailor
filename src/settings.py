from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    request_timeout_seconds: int = 120

    # Brevo HTTP API (works on Render — no SMTP port needed)
    brevo_api_key: str = ""

    # SMTP fallback (works locally)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_starttls: bool = True
    email_from: str = ""
    default_email_to: str = ""


def get_settings() -> Settings:
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o"),
        request_timeout_seconds=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "120")),
        brevo_api_key=os.getenv("BREVO_API_KEY", ""),
        smtp_host=os.getenv("SMTP_HOST", ""),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_username=os.getenv("SMTP_USERNAME", ""),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        smtp_use_starttls=os.getenv("SMTP_USE_STARTTLS", "true").lower() == "true",
        email_from=os.getenv("EMAIL_FROM", ""),
        default_email_to=os.getenv("DEFAULT_EMAIL_TO", ""),
    )
