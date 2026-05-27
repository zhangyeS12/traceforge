from __future__ import annotations

from pathlib import Path
from typing import Any

from .storage import Paths, connect, get_events, get_file_changes, get_run


def compare_runs(paths: Paths, run_a: str, run_b: str) -> dict[str, Any] | None:
    """Build a stable comparison payload for two recorded runs."""
    with connect(paths) as conn:
        a = get_run(conn, run_a)
        b = get_run(conn, run_b)
        if a is None or b is None:
            return None
        a_events = [dict(ev) for ev in get_events(conn, run_a)]
        b_events = [dict(ev) for ev in get_events(conn, run_b)]
        a_changes = [dict(ch) for ch in get_file_changes(conn, run_a)]
        b_changes = [dict(ch) for ch in get_file_changes(conn, run_b)]

    a_run = dict(a)
    b_run = dict(b)
    a_files = {row["path"] for row in a_changes}
    b_files = {row["path"] for row in b_changes}
    common = sorted(a_files & b_files)
    only_a = sorted(a_files - b_files)
    only_b = sorted(b_files - a_files)

    a_artifacts = _artifact_sizes(paths, a_run)
    b_artifacts = _artifact_sizes(paths, b_run)
    a_metrics = _metrics(a_run, a_changes, a_events, a_artifacts)
    b_metrics = _metrics(b_run, b_changes, b_events, b_artifacts)

    return {
        "schema_version": 1,
        "run_a": {"run": a_run, "metrics": a_metrics, "file_changes": a_changes},
        "run_b": {"run": b_run, "metrics": b_metrics, "file_changes": b_changes},
        "diff": {
            "exit_code_changed": a_run.get("exit_code") != b_run.get("exit_code"),
            "duration_delta_ms": _num(b_run.get("duration_ms")) - _num(a_run.get("duration_ms")),
            "changed_files_delta": len(b_files) - len(a_files),
            "event_count_delta": len(b_events) - len(a_events),
            "patch_size_delta_chars": b_artifacts["patch_chars"] - a_artifacts["patch_chars"],
            "stdout_size_delta_chars": b_artifacts["stdout_chars"] - a_artifacts["stdout_chars"],
            "stderr_size_delta_chars": b_artifacts["stderr_chars"] - a_artifacts["stderr_chars"],
            "common_files": common,
            "only_a": only_a,
            "only_b": only_b,
            "status_changes": _status_changes(a_changes, b_changes),
        },
    }


def _metrics(run: dict[str, Any], changes: list[dict[str, Any]], events: list[dict[str, Any]], artifacts: dict[str, int]) -> dict[str, Any]:
    return {
        "id": run.get("id"),
        "command": run.get("command"),
        "exit_code": run.get("exit_code"),
        "duration_ms": run.get("duration_ms"),
        "risk_level": run.get("risk_level") or "low",
        "changed_files_count": len({row["path"] for row in changes}),
        "event_count": len(events),
        "started_at": run.get("started_at"),
        **artifacts,
    }


def _artifact_sizes(paths: Paths, run: dict[str, Any]) -> dict[str, int]:
    return {
        "stdout_chars": _read_len(paths, run.get("stdout_path")),
        "stderr_chars": _read_len(paths, run.get("stderr_path")),
        "patch_chars": _read_len(paths, run.get("patch_path")),
    }


def _read_len(paths: Paths, rel_path: str | None) -> int:
    if not rel_path:
        return 0
    path = paths.root / rel_path
    try:
        return len(path.read_text(encoding="utf-8", errors="replace")) if path.exists() else 0
    except OSError:
        return 0


def _status_changes(a_changes: list[dict[str, Any]], b_changes: list[dict[str, Any]]) -> list[dict[str, str]]:
    a_map = {row["path"]: row["status"] for row in a_changes}
    b_map = {row["path"]: row["status"] for row in b_changes}
    rows: list[dict[str, str]] = []
    for path in sorted(set(a_map) | set(b_map)):
        a_status = a_map.get(path, "")
        b_status = b_map.get(path, "")
        if a_status != b_status:
            rows.append({"path": path, "a_status": a_status, "b_status": b_status})
    return rows


def _num(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0
