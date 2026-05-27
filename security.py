from __future__ import annotations

from pathlib import Path
from typing import Any


class SecurityDecision:
    def __init__(self, allowed: bool, risk_level: str, notes: list[str]) -> None:
        self.allowed = allowed
        self.risk_level = risk_level
        self.notes = notes


def inspect_command(command: str, config: dict[str, Any]) -> SecurityDecision:
    security = config.get("security", {})
    mode = security.get("mode", "warn")
    denied = security.get("deny_command_substrings", [])
    notes: list[str] = []
    lower_command = command.lower()
    for pattern in denied:
        if str(pattern).lower() in lower_command:
            notes.append(f"Command contains risky pattern: {pattern}")
    risk_level = "high" if notes else "low"
    allowed = not (notes and mode == "block")
    return SecurityDecision(allowed=allowed, risk_level=risk_level, notes=notes)


def inspect_changed_files(paths: list[str], config: dict[str, Any]) -> list[str]:
    security = config.get("security", {})
    patterns = [str(p) for p in security.get("sensitive_file_patterns", [])]
    notes: list[str] = []
    for file_path in paths:
        normalized = file_path.replace("\\", "/")
        for pattern in patterns:
            if pattern in normalized:
                notes.append(f"Sensitive-looking file changed or touched: {file_path}")
                break
    return notes
