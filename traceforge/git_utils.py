from __future__ import annotations

import difflib
import hashlib
import subprocess
from pathlib import Path
from typing import NamedTuple

MAX_PATCH_FILE_BYTES = 512_000


class GitSnapshot(NamedTuple):
    is_repo: bool
    commit: str | None
    status: str
    file_hashes: dict[str, str]
    file_contents: dict[str, str | None]


class WorktreeText(NamedTuple):
    exists: bool
    text: str | None
    reason: str


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def is_git_repo(cwd: Path) -> bool:
    result = _git(cwd, "rev-parse", "--is-inside-work-tree")
    return result.returncode == 0 and result.stdout.strip() == "true"


def snapshot(cwd: Path) -> GitSnapshot:
    """Capture the current Git working-tree state.

    Besides the porcelain status text, TraceForge records lightweight content
    fingerprints for files that are dirty at snapshot time. This lets a run tell
    apart pre-existing dirty files from files that were actually changed during
    the recorded command.
    """
    if not is_git_repo(cwd):
        return GitSnapshot(False, None, "", {}, {})
    head = _git(cwd, "rev-parse", "--short", "HEAD")
    commit = head.stdout.strip() if head.returncode == 0 else None
    status = _git(cwd, "status", "--porcelain=v1", "-uall").stdout
    paths = [path for _, path in parse_porcelain_status(status)]
    file_hashes = {path: file_fingerprint(cwd, path) for path in paths}
    file_contents = {path: read_worktree_text(cwd, path) for path in paths}
    return GitSnapshot(True, commit, status, file_hashes, file_contents)


def diff(cwd: Path) -> str:
    """Return the final working-tree diff against HEAD.

    Kept for compatibility. New run recording uses diff_for_run(), which only
    includes files attributable to the recorded run and includes untracked file
    contents.
    """
    if not is_git_repo(cwd):
        return ""
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
        if " -> " in path:
            # Porcelain v1 rename/copy format: old -> new. For attribution and
            # reports, the destination path is the one users normally inspect.
            path = path.split(" -> ", 1)[1]
        changes.append((code, path))
    return changes


def changed_files_after(before: str | GitSnapshot, after: str | GitSnapshot) -> list[tuple[str, str]]:
    """Return files changed by this run, not merely dirty after the run.

    Older TraceForge versions returned parse_porcelain_status(after), which meant
    pre-existing dirty files were attributed to the current run. When snapshots
    are provided, this function compares before/after status and content
    fingerprints so unchanged dirty files are excluded.
    """
    if isinstance(before, str) or isinstance(after, str):
        return _changed_files_from_status_text(str(before), str(after))

    before_map = {path: status for status, path in parse_porcelain_status(before.status)}
    after_map = {path: status for status, path in parse_porcelain_status(after.status)}
    paths = sorted(set(before_map) | set(after_map))
    changes: list[tuple[str, str]] = []

    for path in paths:
        before_status = before_map.get(path)
        after_status = after_map.get(path)
        before_hash = before.file_hashes.get(path)
        after_hash = after.file_hashes.get(path)

        if before_status is None and after_status is not None:
            changes.append((after_status, path))
            continue
        if before_status is not None and after_status is None:
            # A dirty file became clean during the run. This is still a run
            # change even though the final working tree no longer lists it.
            changes.append(("reverted", path))
            continue
        if before_status is not None and after_status is not None:
            if before_status != after_status or before_hash != after_hash:
                changes.append((after_status, path))

    return changes


def _changed_files_from_status_text(before: str, after: str) -> list[tuple[str, str]]:
    before_map = {path: status for status, path in parse_porcelain_status(before)}
    after_map = {path: status for status, path in parse_porcelain_status(after)}
    changes: list[tuple[str, str]] = []
    for path in sorted(set(before_map) | set(after_map)):
        if before_map.get(path) != after_map.get(path):
            changes.append((after_map.get(path) or "reverted", path))
    return changes


def file_fingerprint(cwd: Path, rel_path: str) -> str:
    path = (cwd / rel_path).resolve()
    try:
        if not _is_inside(path, cwd.resolve()):
            return "OUTSIDE"
        if not path.exists():
            return "MISSING"
        if path.is_dir():
            return "DIR"
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return "sha256:" + h.hexdigest()
    except OSError as exc:
        return "ERROR:" + exc.__class__.__name__


def read_worktree_text(cwd: Path, rel_path: str) -> str | None:
    return read_worktree_text_state(cwd, rel_path).text


def read_worktree_text_state(cwd: Path, rel_path: str) -> WorktreeText:
    path = (cwd / rel_path).resolve()
    try:
        if not _is_inside(path, cwd.resolve()):
            return WorktreeText(False, None, "outside-root")
        if not path.exists():
            return WorktreeText(False, None, "missing")
        if path.is_dir():
            return WorktreeText(True, None, "directory")
        data = path.read_bytes()
    except OSError as exc:
        return WorktreeText(False, None, f"error:{exc.__class__.__name__}")
    text = _decode_patchable_bytes(data)
    if text is None:
        if len(data) > MAX_PATCH_FILE_BYTES:
            return WorktreeText(True, None, "too-large")
        if b"\x00" in data:
            return WorktreeText(True, None, "binary")
        return WorktreeText(True, None, "not-text")
    return WorktreeText(True, text, "text")


def read_head_text(cwd: Path, rel_path: str) -> str | None:
    result = _git(cwd, "show", f"HEAD:{rel_path}")
    if result.returncode != 0:
        return None
    # `git show` through _git already decoded with replacement. If the object is
    # binary, keep the output out of textual patches.
    if "\x00" in result.stdout:
        return None
    return result.stdout


def diff_for_run(cwd: Path, before: GitSnapshot, after: GitSnapshot, file_changes: list[tuple[str, str]]) -> str:
    """Build a run-attributed patch.

    The patch is generated only for file_changes and includes untracked new file
    contents. This is intentionally a TraceForge patch, not a raw `git diff HEAD`:
    it answers "what changed during this run?" even when the worktree was dirty
    before the run started.
    """
    if not before.is_repo or not after.is_repo or not file_changes:
        return ""

    chunks: list[str] = []
    for status, path in file_changes:
        before_text = _before_text_for_change(cwd, before, status, path)
        after_state = read_worktree_text_state(cwd, path)
        chunks.append(_unified_file_patch(path, before_text, after_state, status))
    return "\n".join(chunk for chunk in chunks if chunk).rstrip() + ("\n" if chunks else "")


def diff_stat_for_changes(patch: str, file_changes: list[tuple[str, str]]) -> str:
    if not file_changes:
        return ""
    additions = sum(1 for line in patch.splitlines() if line.startswith("+") and not line.startswith("+++"))
    deletions = sum(1 for line in patch.splitlines() if line.startswith("-") and not line.startswith("---"))
    return f"{len(file_changes)} file(s), {additions} insertion(+), {deletions} deletion(-)"


def _before_text_for_change(cwd: Path, before: GitSnapshot, status: str, path: str) -> str | None:
    if path in before.file_contents:
        return before.file_contents[path]
    if status == "??":
        return None
    return read_head_text(cwd, path)


def _unified_file_patch(path: str, before_text: str | None, after_state: WorktreeText, status: str) -> str:
    before_lines = [] if before_text is None else before_text.splitlines(keepends=True)
    after_lines = [] if after_state.text is None else after_state.text.splitlines(keepends=True)

    header = [f"diff --git a/{path} b/{path}"]
    if before_text is None and after_state.text is not None:
        header.append("new file mode 100644")
        fromfile = "/dev/null"
        tofile = f"b/{path}"
    elif before_text is not None and not after_state.exists:
        header.append("deleted file mode 100644")
        fromfile = f"a/{path}"
        tofile = "/dev/null"
    elif before_text is not None and after_state.text is None:
        header.append(f"# TraceForge could not capture textual content for {path!r} (status={status}, reason={after_state.reason}).")
        return "\n".join(header) + "\n"
    else:
        fromfile = f"a/{path}"
        tofile = f"b/{path}"

    if before_text is None and after_state.text is None:
        header.append(f"# TraceForge could not capture textual content for {path!r} (status={status}, reason={after_state.reason}).")
        return "\n".join(header) + "\n"

    diff_lines = list(difflib.unified_diff(before_lines, after_lines, fromfile=fromfile, tofile=tofile, lineterm=""))
    if not diff_lines:
        return ""
    return "\n".join([*header, *diff_lines]) + "\n"


def _decode_patchable_bytes(data: bytes) -> str | None:
    if len(data) > MAX_PATCH_FILE_BYTES:
        return None
    if b"\x00" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace")


def _is_inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
