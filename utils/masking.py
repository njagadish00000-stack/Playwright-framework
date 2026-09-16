"""Sensitive-data masking for logs, Allure attachments and dashboard output."""

from __future__ import annotations

import copy
import re

MASK = "***MASKED***"

SENSITIVE_KEYS = {
    "password",
    "passwd",
    "pwd",
    "secret",
    "token",
    "api_token",
    "api-key",
    "apikey",
    "api_key",
    "authorization",
    "auth",
    "access_token",
    "refresh_token",
    "sessionid",
    "session_id",
    "cookie",
    "set-cookie",
    "client_secret",
    "private_key",
}

_SENSITIVE_RE = re.compile(
    r"(password|passwd|pwd|secret|token|api[-_]?key|authorization|access_token|"
    r"refresh_token|sessionid|session_id)",
    re.IGNORECASE,
)


def mask_secret(value: object) -> str:
    """Mask a single secret value, keeping first/last char hints when long."""
    if value is None:
        return ""
    text = str(value)
    if not text:
        return ""
    if len(text) <= 4:
        return MASK
    return f"{text[0]}***{text[-1]}"


def mask_sensitive_data(data: object) -> object:
    """Recursively mask sensitive keys in dicts/lists; mask secrets in text."""
    if isinstance(data, dict):
        masked: dict = {}
        for key, value in data.items():
            if isinstance(key, str) and (
                key.lower() in SENSITIVE_KEYS or _SENSITIVE_RE.search(key)
            ):
                masked[key] = MASK
            else:
                masked[key] = mask_sensitive_data(value)
        return masked
    if isinstance(data, (list, tuple)):
        return [mask_sensitive_data(item) for item in data]
    if isinstance(data, str):
        # Mask "Authorization: Bearer <...>" style fragments.
        text = re.sub(
            r"(?i)(authorization['\"\s:=]+(?:bearer\s+)?)[^\s'\",;]+",
            r"\1" + MASK,
            data,
        )
        text = re.sub(
            r"(?i)(password['\"\s:=]+)[^\s'\",;&]+",
            r"\1" + MASK,
            text,
        )
        return text
    return copy.deepcopy(data)
