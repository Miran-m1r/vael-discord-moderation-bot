from __future__ import annotations

import os
import re


_SECRET_PATTERNS = (
    (re.compile(r"(?i)\b(?:password|şifre|sifre|token|api[_ -]?key|secret)\s*[:=]\s*\S+"), "[REDACTED_SECRET]"),
    (re.compile(r"\b(?:sk|pk)-[A-Za-z0-9_-]{16,}\b"), "[REDACTED_KEY]"),
    (re.compile(r"(?i)\b(?:authorization\s*:\s*bearer|bearer)\s+[A-Za-z0-9._~+/=-]+"), "[REDACTED_AUTH]"),
)


def external_ai_enabled() -> bool:
    return os.getenv("ALLOW_EXTERNAL_AI", "").strip().lower() in {"1", "true", "yes", "on"}


def redact_sensitive_text(text: str, limit: int = 12000) -> str:
    redacted = text
    for pattern, replacement in _SECRET_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted[:limit]
