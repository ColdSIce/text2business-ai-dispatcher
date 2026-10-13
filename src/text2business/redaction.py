from __future__ import annotations

import re
from typing import Any


_SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}\b", re.IGNORECASE),
    re.compile(
        r"\b(?:api[_-]?key|access[_-]?token|password|пароль)\s*[:=]\s*[^\s,;]+",
        re.IGNORECASE,
    ),
)
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE = re.compile(r"(?<!\d)(?:\+7|8)[\s()-]*\d{3}[\s()-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}(?!\d)")


def redact_text(value: str) -> str:
    """Remove common credentials and direct contact details from trace text."""

    redacted = value
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED_SECRET]", redacted)
    redacted = _EMAIL.sub("[REDACTED_EMAIL]", redacted)
    return _PHONE.sub("[REDACTED_PHONE]", redacted)


def sanitize_trace_value(value: Any) -> Any:
    """Recursively sanitize JSON-like values before they enter an immutable trace."""

    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {str(key): sanitize_trace_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_trace_value(item) for item in value]
    return value


def contains_sensitive_value(value: Any) -> bool:
    """Return whether a JSON-like value still contains an unredacted secret or contact detail."""

    if isinstance(value, str):
        return any(pattern.search(value) for pattern in _SECRET_PATTERNS) or bool(
            _EMAIL.search(value) or _PHONE.search(value)
        )
    if isinstance(value, dict):
        return any(contains_sensitive_value(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_sensitive_value(item) for item in value)
    return False
