from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Any

from . import __version__
from .core import run_command
from .report import generate_index, generate_report
from .storage import (
    connect,
    get_events,
    get_file_changes,
    get_run,
    init_workspace,
    list_runs,
    paths_for,
)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print_help()
        return 0

    cmd = argv[0]
    if cmd == "init":
        paths = init_workspace()
        print(f"Initialized TraceForge workspace at {paths.trace_dir}")
        print("Next: traceforge run -- python hello.py")
        return 0
    if cmd == "run":
        return cmd_run(argv[1:])
    if cmd == "list":
        return cmd_list(argv[1:])
    if cmd == "show":
        return cmd_show(argv[1:])
    if cmd == "report":
        return cmd_report(argv[1:])
    if cmd == "open":
        return cmd_open(argv[1:])
    if cmd == "diff":
        return cmd_diff(argv[1:])
    if cmd == "export":
        return cmd_export(argv[1:])
    if cmd == "doctor":
        return cmd_doctor(argv[1:])
    if cmd == "clean":
        return cmd_clean(argv[1:])
    if cmd == "demo":
        return cmd_demo(argv[1:])
    if cmd in {"-V", "--version", "version"}:
        print(f"traceforge {__version__}")
        return 0
    if cmd in {"-h", "--help", "help"}:
        print_help()
        return 0

    print(f"Unknown command: {cmd}")
    print_help()
    return 2


def cmd_run(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="traceforge run", description="Record a command execution.")
    parser.add_argument("--live", action="store_true", help="stream stdout/stderr while recording")
    parser.add_argument("--shell", action="store_true", help="run through the system shell; useful for pipes and redirects")
    parser.add_argument("--no-propagate-exit", action="store_true", help="always exit traceforge with 0 even if the recorded command fails")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="command to run; use -- before it")
    ns = parser.parse_args(args)

    command_args = list(ns.command)
    if command_args and command_args[0] == "--":
        command_args = command_args[1:]
    if not command_args:
        print("Usage: traceforge run [--live] [--shell] -- <command>")
        return 2

    if ns.shell:
        command: str | list[str] = " ".join(command_args)
    else:
        command = command_args

    result = run_command(command, live=ns.live, shell=ns.shell)
    paths = paths_for()
    report_path = generate_report(paths, result.run_id)
    generate_index(paths)
    print(f"Run recorded: {result.run_id}")
    print(f"Exit code: {result.exit_code}")
    print(f"Duration: {result.duration_ms} ms")
    print(f"STDOUT: {result.stdout_path}")
    print(f"STDERR: {result.stderr_path}")
    print(f"Patch:  {result.patch_path}")
    print(f"Report: {report_path}")
    return 0 if ns.no_propagate_exit else result.exit_code


def cmd_list(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="traceforge list")
    parser.add_argument("--limit", type=int, default=20)
    ns = parser.parse_args(args)
    paths = init_workspace()
    with connect(paths) as conn:
        runs = list_runs(conn, ns.limit)
    if not runs:
        print("No runs recorded yet.")
        return 0
    for run in runs:
        print(f"{run['id']} | exit={run['exit_code']} | {run['duration_ms']}ms | risk={run['risk_level']} | {run['command']}")
    return 0


def cmd_show(args: list[str]) -> int:
    if not args:
        print("Usage: traceforge show <run_id>")
        return 2
    run_id = args[0]
    paths = init_workspace()
    with connect(paths) as conn:
        run = get_run(conn, run_id)
        changes = get_file_changes(conn, run_id)
        events = get_events(conn, run_id)
    if run is None:
        print(f"Run not found: {run_id}")
        return 1
    print(f"Run: {run['id']}")
    print(f"Command: {run['command']}")
    print(f"Exit code: {run['exit_code']}")
    print(f"Duration: {run['duration_ms']} ms")
    print(f"Started: {run['started_at']}")
    print(f"Risk: {run['risk_level']}")
    notes = json.loads(run["risk_notes"] or "[]")
    if notes:
        print("Security notes:")
        for note in notes:
            print(f"  - {note}")
    print("Events:")
    for ev in events:
        print(f"  - {ev['kind']}: {ev['message']}")
    print("Changed files:")
    if changes:
        for change in changes:
            print(f"  {change['status']:>2} {change['path']}")
    else:
        print("  none")
    print(f"Report: {paths.reports_dir / (run_id + '.html')}")
    return 0


def cmd_report(args: list[str]) -> int:
    if not args:
        print("Usage: traceforge report <run_id>")
        return 2
    paths = init_workspace()
    out = generate_report(paths, args[0])
    generate_index(paths)
    print(out)
    return 0


def cmd_open(args: list[str]) -> int:
    paths = init_workspace()
    generate_index(paths)
    target = paths.reports_dir / "index.html"
    if args:
        maybe = paths.reports_dir / f"{args[0]}.html"
        if maybe.exists():
            target = maybe
    print(f"Opening {target}")
    try:
        webbrowser.open(target.as_uri())
    except Exception:
        print(f"Open this file manually: {target}")
    return 0


def cmd_diff(args: list[str]) -> int:
    if len(args) != 2:
        print("Usage: traceforge diff <run_a> <run_b>")
        return 2
    a_id, b_id = args
    paths = init_workspace()
    with connect(paths) as conn:
        a = get_run(conn, a_id)
        b = get_run(conn, b_id)
        a_changes = get_file_changes(conn, a_id)
        b_changes = get_file_changes(conn, b_id)
    if a is None or b is None:
        print("One or both runs were not found.")
        return 1
    a_files = {row["path"] for row in a_changes}
    b_files = {row["path"] for row in b_changes}
    print(f"Run A: {a_id} | exit={a['exit_code']} | {a['duration_ms']}ms | files={len(a_files)}")
    print(f"Run B: {b_id} | exit={b['exit_code']} | {b['duration_ms']}ms | files={len(b_files)}")
    print("Only A:")
    for path in sorted(a_files - b_files):
        print(f"  {path}")
    print("Only B:")
    for path in sorted(b_files - a_files):
        print(f"  {path}")
    print("Both:")
    for path in sorted(a_files & b_files):
        print(f"  {path}")
    return 0


def cmd_export(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="traceforge export")
    parser.add_argument("run_id")
    parser.add_argument("--out", type=Path, default=None, help="output JSON path")
    ns = parser.parse_args(args)

    paths = init_workspace()
    with connect(paths) as conn:
        run = get_run(conn, ns.run_id)
        if run is None:
            print(f"Run not found: {ns.run_id}")
            return 1
        events = get_events(conn, ns.run_id)
        changes = get_file_changes(conn, ns.run_id)

    def read_rel(rel_path: str | None) -> str:
        if not rel_path:
            return ""
        path = paths.root / rel_path
        return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""

    payload: dict[str, Any] = {
        "schema_version": 1,
        "run": dict(run),
        "events": [dict(ev) for ev in events],
        "file_changes": [dict(ch) for ch in changes],
        "artifacts": {
            "stdout": read_rel(run["stdout_path"]),
            "stderr": read_rel(run["stderr_path"]),
            "patch": read_rel(run["patch_path"]),
        },
    }
    out = ns.out or (paths.runs_dir / ns.run_id / "trace.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(out)
    return 0


def cmd_doctor(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="traceforge doctor")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    ns = parser.parse_args(args)

    paths = paths_for()
    checks = [
        _check("python", True, platform.python_version(), sys.executable),
        _tool_check("git", ["git", "--version"]),
        _tool_check("rustc", ["rustc", "--version"]),
        _tool_check("cargo", ["cargo", "--version"]),
        _tool_check("node", ["node", "--version"]),
        _tool_check("npm", ["npm", "--version"]),
        _check("workspace", paths.trace_dir.exists(), "initialized" if paths.trace_dir.exists() else "missing", str(paths.trace_dir)),
        _check("database", paths.db_path.exists(), "exists" if paths.db_path.exists() else "missing", str(paths.db_path)),
        _check("git_repo", _is_git_repo(paths.root), "yes" if _is_git_repo(paths.root) else "no", str(paths.root)),
    ]
    ok = all(c["ok"] for c in checks if c["name"] in {"python", "git"})
    if ns.json:
        print(json.dumps({"ok": ok, "checks": checks}, indent=2, ensure_ascii=False))
    else:
        print("TraceForge doctor")
        for item in checks:
            mark = "OK" if item["ok"] else "WARN"
            print(f"[{mark:4}] {item['name']:<10} {item['version']:<24} {item['detail']}")
        if not paths.trace_dir.exists():
            print("\nWorkspace not initialized. Run: traceforge init")
    return 0 if ok else 1


def cmd_clean(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="traceforge clean")
    parser.add_argument("--yes", action="store_true", help="confirm deletion")
    parser.add_argument("--all", action="store_true", help="remove the entire .traceforge directory, including config")
    ns = parser.parse_args(args)

    paths = paths_for()
    if not paths.trace_dir.exists():
        print("No .traceforge workspace found.")
        return 0
    if not ns.yes:
        print("This will delete recorded runs, reports, and the local database.")
        print("Run again with: traceforge clean --yes")
        return 2
    if ns.all:
        shutil.rmtree(paths.trace_dir, ignore_errors=True)
        print(f"Removed {paths.trace_dir}")
        return 0
    shutil.rmtree(paths.runs_dir, ignore_errors=True)
    shutil.rmtree(paths.reports_dir, ignore_errors=True)
    if paths.db_path.exists():
        paths.db_path.unlink()
    init_workspace(paths.root)
    print("Cleaned runs, reports, and database. Kept config.json.")
    return 0


def cmd_demo(args: list[str]) -> int:
    target = Path(args[0]).resolve() if args else Path.cwd() / "traceforge-demo-project"
    if target.exists():
        print(f"Demo target already exists: {target}")
        return 1
    target.mkdir(parents=True)
    (target / "calculator.py").write_text(
        "def add(a, b):\n    return a + b\n\ndef divide(a, b):\n    return a / b\n",
        encoding="utf-8",
    )
    (target / "test_calculator.py").write_text(
        "from calculator import add, divide\n\nassert add(2, 3) == 5\nassert divide(4, 2) == 2\nprint('tests passed')\n",
        encoding="utf-8",
    )
    if shutil.which("git"):
        subprocess.run(["git", "init"], cwd=target, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        subprocess.run(["git", "add", "."], cwd=target, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        subprocess.run(["git", "commit", "-m", "init"], cwd=target, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    print(f"Created demo project: {target}")
    print("Try:")
    print(f"  cd {target}")
    print("  python -m traceforge init")
    print("  python -m traceforge run --live -- python test_calculator.py")
    return 0


def _check(name: str, ok: bool, version: str, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": ok, "version": version, "detail": detail}


def _tool_check(name: str, cmd: list[str]) -> dict[str, Any]:
    """Check whether an external CLI tool is available.

    Important Windows detail:
    some tools such as npm are launched through .cmd/.bat shims.
    A public-facing `doctor` command must never crash just because an
    optional tool is missing or cannot be executed directly.
    """
    exe = shutil.which(cmd[0])
    if not exe:
        return _check(name, False, "not found", "not on PATH")

    run_cmd = [exe, *cmd[1:]]
    try:
        if os.name == "nt" and Path(exe).suffix.lower() in {".bat", ".cmd"}:
            # Windows batch shims are safer through cmd.exe.
            completed = subprocess.run(
                subprocess.list2cmdline(run_cmd),
                shell=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        else:
            completed = subprocess.run(
                run_cmd,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
    except OSError as exc:
        return _check(name, False, "error", f"{exe} ({exc.__class__.__name__}: {exc})")

    output = (completed.stdout or completed.stderr).strip()
    version = output.splitlines()[0] if output else "found"
    return _check(name, completed.returncode == 0, version, exe)


def _is_git_repo(path: Path) -> bool:
    git = shutil.which("git")
    if not git:
        return False
    try:
        result = subprocess.run(
            [git, "rev-parse", "--is-inside-work-tree"],
            cwd=path,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError:
        return False
    return result.returncode == 0 and result.stdout.strip() == "true"


def print_help() -> None:
    print(
        f"""
TraceForge {__version__} — black-box recorder for AI coding agents and shell commands.

Usage:
  traceforge init
  traceforge doctor [--json]
  traceforge run [--live] [--shell] [--no-propagate-exit] -- <command>
  traceforge list [--limit 20]
  traceforge show <run_id>
  traceforge report <run_id>
  traceforge open [run_id]
  traceforge diff <run_a> <run_b>
  traceforge export <run_id> [--out trace.json]
  traceforge clean [--yes] [--all]
  traceforge demo [path]
  traceforge version

Examples:
  traceforge run -- python hello.py
  traceforge run --live -- npm test
  traceforge run --shell -- "npm test && npm run lint"

Without installing:
  python -m traceforge run -- <command>
""".strip()
    )


if __name__ == "__main__":
    raise SystemExit(main())
