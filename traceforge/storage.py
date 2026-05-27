from __future__ import annotations

import json
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

TRACE_DIR = ".traceforge"
DB_NAME = "traceforge.db"
CONFIG_NAME = "config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "security": {
        "mode": "warn",  # warn | block
        "deny_command_substrings": [
            "rm -rf /",
            "sudo rm -rf",
            ":(){ :|:& };:",
            "mkfs",
            "dd if=",
            "shutdown",
            "reboot",
        ],
        "sensitive_file_patterns": [
            ".env",
            "id_rsa",
            "id_ed25519",
            ".aws/credentials",
            ".ssh/",
        ],
    },
    "report": {
        "max_stdout_chars": 12000,
        "max_stderr_chars": 12000,
        "max_diff_chars": 30000,
    },
    "timeline": {
        "max_output_chunk_events": 80,
        "max_output_chunk_chars": 600,
    },
}


@dataclass(frozen=True)
class Paths:
    root: Path
    trace_dir: Path
    db_path: Path
    config_path: Path
    runs_dir: Path
    reports_dir: Path


def paths_for(cwd: Path | None = None) -> Paths:
    root = (cwd or Path.cwd()).resolve()
    trace_dir = root / TRACE_DIR
    return Paths(
        root=root,
        trace_dir=trace_dir,
        db_path=trace_dir / DB_NAME,
        config_path=trace_dir / CONFIG_NAME,
        runs_dir=trace_dir / "runs",
        reports_dir=trace_dir / "reports",
    )


def init_workspace(cwd: Path | None = None) -> Paths:
    paths = paths_for(cwd)
    paths.trace_dir.mkdir(parents=True, exist_ok=True)
    paths.runs_dir.mkdir(parents=True, exist_ok=True)
    paths.reports_dir.mkdir(parents=True, exist_ok=True)
    if not paths.config_path.exists():
        paths.config_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
    _ensure_git_exclude(paths.root)
    with connect(paths) as conn:
        migrate(conn)
    return paths


def _ensure_git_exclude(root: Path) -> None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=root,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            return
        git_dir = Path(result.stdout.strip())
        if not git_dir.is_absolute():
            git_dir = root / git_dir
        info_dir = git_dir / "info"
        info_dir.mkdir(parents=True, exist_ok=True)
        exclude = info_dir / "exclude"
        current = exclude.read_text(encoding="utf-8", errors="replace") if exclude.exists() else ""
        if ".traceforge/" not in current:
            with exclude.open("a", encoding="utf-8") as f:
                if current and not current.endswith("\n"):
                    f.write("\n")
                f.write(".traceforge/\n")
    except Exception:
        return


def load_config(paths: Paths) -> dict[str, Any]:
    if not paths.config_path.exists():
        init_workspace(paths.root)
    try:
        data = json.loads(paths.config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = {}
    merged = json.loads(json.dumps(DEFAULT_CONFIG))
    _deep_update(merged, data)
    return merged


def _deep_update(base: dict[str, Any], override: dict[str, Any]) -> None:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_update(base[key], value)
        else:
            base[key] = value


def connect(paths: Paths) -> sqlite3.Connection:
    conn = sqlite3.connect(paths.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY,
            command TEXT NOT NULL,
            cwd TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL,
            duration_ms INTEGER NOT NULL,
            exit_code INTEGER NOT NULL,
            git_before TEXT,
            git_after TEXT,
            status_before TEXT,
            status_after TEXT,
            stdout_path TEXT,
            stderr_path TEXT,
            patch_path TEXT,
            diff_stat TEXT,
            risk_level TEXT DEFAULT 'low',
            risk_notes TEXT DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            ts TEXT NOT NULL,
            kind TEXT NOT NULL,
            message TEXT NOT NULL,
            data TEXT DEFAULT '{}',
            FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS file_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            status TEXT NOT NULL,
            path TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
        );
        """
    )
    conn.commit()


def insert_run(conn: sqlite3.Connection, run: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO runs (
            id, command, cwd, started_at, finished_at, duration_ms, exit_code,
            git_before, git_after, status_before, status_after,
            stdout_path, stderr_path, patch_path, diff_stat, risk_level, risk_notes
        ) VALUES (
            :id, :command, :cwd, :started_at, :finished_at, :duration_ms, :exit_code,
            :git_before, :git_after, :status_before, :status_after,
            :stdout_path, :stderr_path, :patch_path, :diff_stat, :risk_level, :risk_notes
        )
        """,
        run,
    )
    conn.commit()


def insert_events(conn: sqlite3.Connection, events: Iterable[dict[str, Any]]) -> None:
    items = list(events)
    if not items:
        return
    conn.executemany(
        "INSERT INTO events (run_id, ts, kind, message, data) VALUES (:run_id, :ts, :kind, :message, :data)",
        items,
    )
    conn.commit()


def insert_event(conn: sqlite3.Connection, event: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO events (run_id, ts, kind, message, data) VALUES (:run_id, :ts, :kind, :message, :data)",
        event,
    )
    conn.commit()


def insert_file_changes(conn: sqlite3.Connection, changes: Iterable[dict[str, Any]]) -> None:
    conn.executemany(
        "INSERT INTO file_changes (run_id, status, path) VALUES (:run_id, :status, :path)",
        list(changes),
    )
    conn.commit()


def get_run(conn: sqlite3.Connection, run_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()


def list_runs(conn: sqlite3.Connection, limit: int = 20) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    )


def get_events(conn: sqlite3.Connection, run_id: str) -> list[sqlite3.Row]:
    return list(conn.execute("SELECT * FROM events WHERE run_id = ? ORDER BY id", (run_id,)).fetchall())


def get_file_changes(conn: sqlite3.Connection, run_id: str) -> list[sqlite3.Row]:
    return list(conn.execute("SELECT * FROM file_changes WHERE run_id = ? ORDER BY path", (run_id,)).fetchall())
