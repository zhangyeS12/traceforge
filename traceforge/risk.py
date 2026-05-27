from __future__ import annotations

import json
import re
from typing import Any

from .storage import Paths, connect, get_file_changes, get_run

SEVERITY_ORDER = {"low": 1, "medium": 2, "high": 3}

DEPENDENCY_FILES = {
    "pyproject.toml", "requirements.txt", "requirements-dev.txt", "setup.py", "setup.cfg",
    "poetry.lock", "pdm.lock", "package.json", "package-lock.json", "pnpm-lock.yaml",
    "yarn.lock", "Cargo.toml", "Cargo.lock", "go.mod", "go.sum", "Gemfile", "Gemfile.lock",
}

CI_PREFIXES = (
    ".github/workflows/",
    ".gitlab-ci.yml",
    "azure-pipelines.yml",
    "Jenkinsfile",
)

SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----", re.I), "Private key material appears in the patch"),
    (re.compile(r"AWS_SECRET_ACCESS_KEY\s*[=:]", re.I), "AWS secret access key name appears in the patch"),
    (re.compile(r"OPENAI_API_KEY\s*[=:]", re.I), "OpenAI API key name appears in the patch"),
    (re.compile(r"(?i)(password|passwd|secret|token|api[_-]?key)\s*[=:]\s*['\"][^'\"]{8,}"), "Potential hard-coded credential appears in the patch"),
]

SENSITIVE_FILE_MARKERS = (
    ".env", ".ssh/", "id_rsa", "id_ed25519", ".aws/credentials", "credentials.json",
    "secrets.json", "private_key", "secret", "token",
)

DESTRUCTIVE_COMMAND_MARKERS = (
    "rm -rf /", "sudo rm -rf", "del /f", "format ", "mkfs", "dd if=", "shutdown", "reboot",
    "curl ", "wget ", "invoke-webrequest", "powershell -enc",
)


def assess_run(paths: Paths, run_id: str) -> dict[str, Any] | None:
    """Build a security-oriented risk report for a recorded run."""
    with connect(paths) as conn:
        run = get_run(conn, run_id)
        if run is None:
            return None
        changes = [dict(row) for row in get_file_changes(conn, run_id)]
    run_dict = dict(run)
    patch = _read_artifact(paths, run_dict.get("patch_path"))
    stdout = _read_artifact(paths, run_dict.get("stdout_path"))
    stderr = _read_artifact(paths, run_dict.get("stderr_path"))
    existing_notes = _safe_notes(run_dict.get("risk_notes"))
    return assess_static(
        command=run_dict.get("command") or "",
        file_changes=[(row.get("status") or "", row.get("path") or "") for row in changes],
        patch=patch,
        stdout=stdout,
        stderr=stderr,
        existing_notes=existing_notes,
    ) | {"run_id": run_id, "command": run_dict.get("command"), "exit_code": run_dict.get("exit_code")}


def assess_static(
    *,
    command: str,
    file_changes: list[tuple[str, str]],
    patch: str = "",
    stdout: str = "",
    stderr: str = "",
    existing_notes: list[str] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assess risk from command text, changed files, artifacts, and existing warnings."""
    findings: list[dict[str, Any]] = []
    existing_notes = existing_notes or []
    config = config or {}

    for note in existing_notes:
        _add(findings, "high", "security.note", note, "Existing TraceForge security policy warning")

    command_lower = command.lower()
    configured_denies = [str(p).lower() for p in config.get("security", {}).get("deny_command_substrings", [])]
    for marker in sorted(set([*DESTRUCTIVE_COMMAND_MARKERS, *configured_denies])):
        if marker and marker in command_lower:
            severity = "high" if marker in {"rm -rf /", "sudo rm -rf", "mkfs", "dd if=", "format "} else "medium"
            _add(findings, severity, "command.risky", f"Command contains risky marker: {marker}", command)

    paths = [path.replace("\\", "/") for _, path in file_changes]
    for status, path in file_changes:
        normalized = path.replace("\\", "/")
        lower = normalized.lower()
        name = lower.rsplit("/", 1)[-1]

        if any(marker.lower() in lower for marker in SENSITIVE_FILE_MARKERS):
            _add(findings, "high", "file.sensitive", f"Sensitive-looking file changed: {path}", f"status={status}")
        elif name in DEPENDENCY_FILES:
            _add(findings, "medium", "file.dependency", f"Dependency or package-management file changed: {path}", f"status={status}")
        elif lower.startswith(CI_PREFIXES) or lower in CI_PREFIXES:
            _add(findings, "medium", "file.ci", f"CI/CD workflow file changed: {path}", f"status={status}")
        elif name in {".gitignore", ".gitattributes"}:
            _add(findings, "low", "file.repo_config", f"Repository configuration changed: {path}", f"status={status}")

    unique_files = sorted(set(paths))
    if len(unique_files) >= 50:
        _add(findings, "high", "change.large", f"Large change set: {len(unique_files)} files changed", "Review broad patches carefully")
    elif len(unique_files) >= 20:
        _add(findings, "medium", "change.large", f"Large change set: {len(unique_files)} files changed", "Review broad patches carefully")

    for pattern, title in SECRET_PATTERNS:
        if pattern.search(patch):
            _add(findings, "high", "patch.secret", title, "Detected by patch pattern scan")

    if stderr.strip() and "traceback" in stderr.lower():
        _add(findings, "low", "runtime.traceback", "stderr contains a Python traceback", "This may indicate a failed or partial run")

    deduped = _dedupe(findings)
    risk_level = _overall(deduped)
    summary = {
        "total": len(deduped),
        "high": sum(1 for f in deduped if f["severity"] == "high"),
        "medium": sum(1 for f in deduped if f["severity"] == "medium"),
        "low": sum(1 for f in deduped if f["severity"] == "low"),
        "changed_files": len(unique_files),
    }
    return {
        "schema_version": 1,
        "risk_level": risk_level,
        "summary": summary,
        "findings": deduped,
        "recommendation": _recommendation(risk_level, deduped),
    }


def _add(findings: list[dict[str, Any]], severity: str, rule: str, title: str, detail: str = "") -> None:
    findings.append({"severity": severity, "rule": rule, "title": title, "detail": detail})


def _dedupe(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    out: list[dict[str, Any]] = []
    for item in findings:
        key = (item.get("severity", ""), item.get("rule", ""), item.get("title", ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    out.sort(key=lambda f: (-SEVERITY_ORDER.get(f.get("severity", "low"), 1), f.get("rule", ""), f.get("title", "")))
    return out


def _overall(findings: list[dict[str, Any]]) -> str:
    if any(f["severity"] == "high" for f in findings):
        return "high"
    if any(f["severity"] == "medium" for f in findings):
        return "medium"
    return "low"


def _recommendation(risk_level: str, findings: list[dict[str, Any]]) -> str:
    if risk_level == "high":
        return "Review manually before accepting this run. High-risk findings may involve secrets, destructive commands, or sensitive files."
    if risk_level == "medium":
        return "Review dependency, CI, or broad file changes before merging."
    if findings:
        return "Low-risk findings were detected. A quick review is recommended."
    return "No notable security findings were detected by the current rules."


def _read_artifact(paths: Paths, rel_path: str | None) -> str:
    if not rel_path:
        return ""
    path = paths.root / rel_path
    try:
        return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    except OSError:
        return ""


def _safe_notes(value: str | None) -> list[str]:
    try:
        data = json.loads(value or "[]")
        return [str(item) for item in data] if isinstance(data, list) else []
    except Exception:
        return []
