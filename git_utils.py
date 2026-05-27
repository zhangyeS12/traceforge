from __future__ import annotations

import subprocess
from pathlib import Path
from typing import NamedTuple


class GitSnapshot(NamedTuple):
    is_repo: bool
    commit: str | None
    status: str


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def is_git_repo(cwd: Path) -> bool:
    result = _git(cwd, "rev-parse", "--is-inside-work-tree")
    return result.returncode == 0 and result.stdout.strip() == "true"


def snapshot(cwd: Path) -> GitSnapshot:
    if not is_git_repo(cwd):
        return GitSnapshot(False, None, "")
    head = _git(cwd, "rev-parse", "--short", "HEAD")
    commit = head.stdout.strip() if head.returncode == 0 else None
    status = _git(cwd, "status", "--porcelain=v1").stdout
    return GitSnapshot(True, commit, status)


def diff(cwd: Path) -> str:
    if not is_git_repo(cwd):
        return ""
    # Includes staged and unstaged tracked changes. Untracked files are listed by status and shown as names.
    result = _git(cwd, "diff", "--patch", "--binary", "HEAD")
    if result.returncode != 0:
        return result.stderr
    return result.stdout


def diff_stat(cwd: Path) -> str:
    if not is_git_repo(cwd):
        return ""
    result = _git(cwd, "diff", "--stat", "HEAD")
    return result.stdout if result.returncode == 0 else result.stderr


def parse_porcelain_status(status: str) -> list[tuple[str, str]]:
    changes: list[tuple[str, str]] = []
    for raw in status.splitlines():
        if not raw.strip():
            continue
        if raw.startswith("?? "):
            changes.append(("??", raw[3:]))
            continue
        code = raw[:2].strip() or raw[:2]
        path = raw[3:]
        changes.append((code, path))
    return changes


def changed_files_after(before: str, after: str) -> list[tuple[str, str]]:
    # MVP behavior: show the final working tree status. Later versions can compute precise event-level deltas.
    return parse_porcelain_status(after)
