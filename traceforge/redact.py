from __future__ import annotations

import re
from typing import Any

REDACTION = "[REDACTED]"

TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)(openai_api_key|api[_-]?key|token|secret|password|passwd)\s*([:=])\s*(['\"]?)[^'\"\s,;]{8,}"),
    re.compile(r"(?i)(authorization:\s*bearer\s+)[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"(?i)(aws_secret_access_key\s*=\s*)[A-Za-z0-9/+=]{20,}"),
]

PATH_PATTERNS = [
    re.compile(r"C:\\Users\\[^\\\s]+"),
    re.compile(r"/Users/[^/\s]+"),
    re.compile(r"/home/[^/\s]+"),
]


def redact_text(value: str) -> str:
    text = value
    for pattern in TEXT_PATTERNS:
        if pattern.groups >= 2:
            text = pattern.sub(lambda m: f"{m.group(1)}{m.group(2)}{m.group(3) if pattern.groups >= 3 else ''}{REDACTION}", text)
        elif pattern.groups == 1:
            text = pattern.sub(lambda m: f"{m.group(1)}{REDACTION}", text)
        else:
            text = pattern.sub(REDACTION, text)
    for pattern in PATH_PATTERNS:
        text = pattern.sub(REDACTION, text)
    return text


def redact_payload(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_payload(item) for item in value]
    if isinstance(value, tuple):
        return [redact_payload(item) for item in value]
    if isinstance(value, dict):
        return {str(key): redact_payload(item) for key, item in value.items()}
    return value
