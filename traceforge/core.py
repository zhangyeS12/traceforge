from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from . import git_utils
from .report import generate_index, generate_report
from .security import inspect_changed_files, inspect_command
from .storage import connect, init_workspace, insert_events, insert_file_changes, insert_run, load_config


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@dataclass
class RunResult:
    run_id: str
    exit_code: int
    duration_ms: int
    stdout_path: Path
    stderr_path: Path
    patch_path: Path


def display_command(command: str | Sequence[str]) -> str:
    if isinstance(command, str):
        return command
    if os.name == "nt":
        return subprocess.list2cmdline(list(command))
    return " ".join(_shell_quote(part) for part in command)


def _shell_quote(value: str) -> str:
    # Small local alternative to shlex.quote, kept explicit for teaching and portability.
    if not value:
        return "''"
    safe = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_@%+=:,./-")
    if all(ch in safe for ch in value):
        return value
    return "'" + value.replace("'", "'\\''") + "'"


def run_command(
    command: str | Sequence[str],
    cwd: Path | None = None,
    *,
    live: bool = False,
    shell: bool = False,
) -> RunResult:
    """Run a command and record it as a TraceForge run.

    v0.7 upgrades the run from a simple final result into a replayable timeline:
    command start, security check, stdout/stderr chunks, process exit, artifact
    writes, Git diff capture, changed files, and security warnings are all saved
    as structured events.
    """
    paths = init_workspace(cwd)
    config = load_config(paths)
    timeline_config = config.get("timeline", {})
    max_output_events = int(timeline_config.get("max_output_chunk_events", 80))
    max_output_chars = int(timeline_config.get("max_output_chunk_chars", 600))

    command_text = display_command(command)
    decision = inspect_command(command_text, config)
    if not decision.allowed:
        raise SystemExit("Blocked by TraceForge security policy: " + "; ".join(decision.notes))

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    run_dir = paths.runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    stdout_path = run_dir / "stdout.txt"
    stderr_path = run_dir / "stderr.txt"
    patch_path = run_dir / "patch.diff"

    before = git_utils.snapshot(paths.root)
    events: list[dict[str, Any]] = []
    output_event_count = 0
    event_lock = threading.Lock()

    started_at = utc_now()
    start_monotonic = time.monotonic()

    def add(kind: str, message: str, data: dict[str, Any] | None = None) -> None:
        payload = dict(data or {})
        payload.setdefault("offset_ms", int((time.monotonic() - start_monotonic) * 1000))
        with event_lock:
            events.append(event(run_id, kind, message, payload))

    add("run.started", f"Started command: {command_text}", {
        "cwd": str(paths.root),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "git_before": before.commit,
        "security_notes": decision.notes,
        "live": live,
        "shell": shell,
    })
    add("command.started", command_text, {"argv": list(command) if not isinstance(command, str) else command_text, "shell": shell})
    add("security.checked", "Command security policy checked", {"allowed": decision.allowed, "notes": decision.notes})
    add("git.snapshot.before", "Captured Git snapshot before command", {
        "commit": before.commit,
        "status": before.status,
        "dirty": bool(before.status.strip()),
    })

    proc_args: str | Sequence[str]
    if shell:
        proc_args = command_text
    else:
        proc_args = command if not isinstance(command, str) else _split_for_shellless(command)

    proc_args = _normalize_popen_args(proc_args, shell=shell)

    proc = subprocess.Popen(
        proc_args,
        cwd=str(paths.root),
        shell=shell,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_safe_environ(),
        bufsize=1,
    )

    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []

    def read_stream(stream: Any, chunks: list[str], target: Any, stream_name: str, prefix: str = "") -> None:
        nonlocal output_event_count
        try:
            for line in iter(stream.readline, ""):
                chunks.append(line)
                stripped = line.rstrip("\r\n")
                if stripped:
                    with event_lock:
                        can_record = output_event_count < max_output_events
                        if can_record:
                            output_event_count += 1
                    if can_record:
                        preview = stripped[:max_output_chars]
                        add(f"{stream_name}.chunk", preview, {
                            "stream": stream_name,
                            "chars": len(stripped),
                            "truncated": len(stripped) > max_output_chars,
                        })
                if live:
                    if prefix:
                        target.write(prefix)
                    target.write(line)
                    target.flush()
        finally:
            try:
                stream.close()
            except Exception:
                pass

    stdout_thread = threading.Thread(target=read_stream, args=(proc.stdout, stdout_chunks, sys.stdout, "stdout", ""), daemon=True)
    stderr_thread = threading.Thread(target=read_stream, args=(proc.stderr, stderr_chunks, sys.stderr, "stderr", ""), daemon=True)
    stdout_thread.start()
    stderr_thread.start()
    exit_code = proc.wait()
    stdout_thread.join(timeout=2)
    stderr_thread.join(timeout=2)

    duration_ms = int((time.monotonic() - start_monotonic) * 1000)
    finished_at = utc_now()

    stdout = "".join(stdout_chunks)
    stderr = "".join(stderr_chunks)
    stdout_path.write_text(stdout, encoding="utf-8", errors="replace")
    stderr_path.write_text(stderr, encoding="utf-8", errors="replace")

    add("process.exited", f"Command exited with code {exit_code}", {
        "exit_code": exit_code,
        "duration_ms": duration_ms,
        "stdout_bytes": len(stdout.encode("utf-8", errors="replace")),
        "stderr_bytes": len(stderr.encode("utf-8", errors="replace")),
        "stdout_lines": len(stdout.splitlines()),
        "stderr_lines": len(stderr.splitlines()),
    })
    add("artifact.written", "Captured stdout and stderr artifacts", {
        "stdout_path": str(stdout_path.relative_to(paths.root)),
        "stderr_path": str(stderr_path.relative_to(paths.root)),
    })

    after = git_utils.snapshot(paths.root)
    add("git.snapshot.after", "Captured Git snapshot after command", {
        "commit": after.commit,
        "status": after.status,
        "dirty": bool(after.status.strip()),
    })

    patch = git_utils.diff(paths.root)
    patch_path.write_text(patch, encoding="utf-8", errors="replace")
    stat = git_utils.diff_stat(paths.root)

    file_changes = git_utils.changed_files_after(before.status, after.status)
    add("git.diff.captured", f"Captured Git diff with {len(file_changes)} changed file(s)", {
        "patch_path": str(patch_path.relative_to(paths.root)),
        "diff_stat": stat,
        "changed_files_count": len(file_changes),
    })

    for status, file_path in file_changes:
        add("file.changed", f"{status} {file_path}", {"status": status, "path": file_path})

    changed_paths = [path for _, path in file_changes]
    file_risk_notes = inspect_changed_files(changed_paths, config)
    all_risk_notes = [*decision.notes, *file_risk_notes]
    risk_level = "high" if all_risk_notes else "low"

    if all_risk_notes:
        add("security.warning", "Security policy produced warning(s)", {"notes": all_risk_notes})

    # `run.finished` is intentionally inserted after `report.generated` below.
    # A black-box timeline should end only after all artifacts are persisted and
    # the replay report has been generated.

    run_record = {
        "id": run_id,
        "command": command_text,
        "cwd": str(paths.root),
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": duration_ms,
        "exit_code": exit_code,
        "git_before": before.commit,
        "git_after": after.commit,
        "status_before": before.status,
        "status_after": after.status,
        "stdout_path": str(stdout_path.relative_to(paths.root)),
        "stderr_path": str(stderr_path.relative_to(paths.root)),
        "patch_path": str(patch_path.relative_to(paths.root)),
        "diff_stat": stat,
        "risk_level": risk_level,
        "risk_notes": json.dumps(all_risk_notes, ensure_ascii=False),
    }

    with connect(paths) as conn:
        insert_run(conn, run_record)
        insert_events(conn, events)
        insert_file_changes(conn, [
            {"run_id": run_id, "status": status, "path": file_path}
            for status, file_path in file_changes
        ])

    report_path = paths.reports_dir / f"{run_id}.html"
    with connect(paths) as conn:
        insert_events(conn, [
            event(run_id, "report.generated", "Generated HTML report", {
                "report_path": str(report_path.relative_to(paths.root)),
                "offset_ms": int((time.monotonic() - start_monotonic) * 1000),
            }),
            event(run_id, "run.finished", f"Run finished in {duration_ms} ms", {
                "exit_code": exit_code,
                "duration_ms": duration_ms,
                "risk_level": risk_level,
                "changed_files_count": len(file_changes),
                "event_count": len(events) + 2,
                "offset_ms": int((time.monotonic() - start_monotonic) * 1000),
            }),
        ])
    generate_report(paths, run_id)
    generate_index(paths)

    return RunResult(
        run_id=run_id,
        exit_code=exit_code,
        duration_ms=duration_ms,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        patch_path=patch_path,
    )


def _split_for_shellless(command: str) -> list[str]:
    # Fallback for internal calls that still pass a string.
    # On Windows, shlex-style parsing is not fully cmd-compatible; public CLI passes a list.
    import shlex

    return shlex.split(command, posix=os.name != "nt")


def _normalize_popen_args(proc_args: str | Sequence[str], *, shell: bool) -> str | list[str]:
    if shell:
        if proc_args is None:
            raise ValueError("command cannot be None")
        return str(proc_args)
    if isinstance(proc_args, str):
        return [proc_args]
    normalized: list[str] = []
    for part in proc_args:
        if part is None:
            raise ValueError("command contains an empty argument")
        normalized.append(str(part))
    if not normalized:
        raise ValueError("command cannot be empty")
    return normalized


def _safe_environ() -> dict[str, str]:
    env: dict[str, str] = {}
    for key, value in os.environ.items():
        if key is None or value is None:
            continue
        env[str(key)] = str(value)

    # Hint Python child processes to emit UTF-8. Parent-side decoding still uses
    # errors="replace", so TraceForge should never crash on undecodable bytes.
    env.setdefault("PYTHONIOENCODING", "utf-8:replace")
    return env


def event(run_id: str, kind: str, message: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "ts": utc_now(),
        "kind": kind,
        "message": message,
        "data": json.dumps(data or {}, ensure_ascii=False),
    }
