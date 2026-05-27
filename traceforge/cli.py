from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import tomllib
import webbrowser
import zipfile
from pathlib import Path
from typing import Any

from . import __version__
from .compare import compare_runs
from .core import event, run_command
from .report import generate_index, generate_report
from .risk import assess_run
from .server import serve_dashboard
from .storage import (
    connect,
    get_events,
    get_file_changes,
    get_run,
    init_workspace,
    insert_event,
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
    if cmd == "timeline":
        return cmd_timeline(argv[1:])
    if cmd == "compare":
        return cmd_compare(argv[1:])
    if cmd == "risk":
        return cmd_risk(argv[1:])
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
    if cmd == "selftest":
        return cmd_selftest(argv[1:])
    if cmd in {"release-check", "release_check"}:
        return cmd_release_check(argv[1:])
    if cmd in {"dashboard", "ui"}:
        return cmd_dashboard(argv[1:])
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
    report_path = paths_for().reports_dir / f"{result.run_id}.html"
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


def cmd_timeline(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="traceforge timeline")
    parser.add_argument("run_id")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    ns = parser.parse_args(args)

    paths = init_workspace()
    with connect(paths) as conn:
        run = get_run(conn, ns.run_id)
        events = get_events(conn, ns.run_id)
    if run is None:
        print(f"Run not found: {ns.run_id}")
        return 1

    rows = []
    for ev in events:
        data = safe_json(ev["data"], {})
        rows.append({
            "ts": ev["ts"],
            "kind": ev["kind"],
            "message": ev["message"],
            "offset_ms": data.get("offset_ms"),
            "data": data,
        })

    if ns.json:
        print(json.dumps({"run_id": ns.run_id, "events": rows}, indent=2, ensure_ascii=False))
        return 0

    print(f"Timeline: {ns.run_id}")
    print(f"Command: {run['command']}")
    for row in rows:
        offset = row["offset_ms"]
        offset_text = f"+{offset:>5}ms" if isinstance(offset, int) else "       "
        print(f"{offset_text}  {row['kind']:<22} {row['message']}")
    return 0


def safe_json(value: str | None, fallback: Any) -> Any:
    try:
        return json.loads(value or "{}")
    except Exception:
        return fallback


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
    """Backward-compatible alias for the richer compare command."""
    return cmd_compare(args)


def cmd_compare(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="traceforge compare", description="Compare two recorded runs.")
    parser.add_argument("run_a")
    parser.add_argument("run_b")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    ns = parser.parse_args(args)

    paths = init_workspace()
    payload = compare_runs(paths, ns.run_a, ns.run_b)
    if payload is None:
        print("One or both runs were not found.")
        return 1

    if ns.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    a = payload["run_a"]["metrics"]
    b = payload["run_b"]["metrics"]
    d = payload["diff"]

    print("TraceForge compare")
    print(f"Run A: {a['id']}")
    print(f"  command: {a['command']}")
    print(f"Run B: {b['id']}")
    print(f"  command: {b['command']}")
    print("")
    print("Outcome")
    print(f"  Exit code:      A={a['exit_code']}  B={b['exit_code']}  changed={d['exit_code_changed']}")
    print(f"  Duration:       A={a['duration_ms']}ms  B={b['duration_ms']}ms  delta={d['duration_delta_ms']}ms")
    print(f"  Changed files:  A={a['changed_files_count']}  B={b['changed_files_count']}  delta={d['changed_files_delta']}")
    print(f"  Events:         A={a['event_count']}  B={b['event_count']}  delta={d['event_count_delta']}")
    print(f"  Patch chars:    A={a['patch_chars']}  B={b['patch_chars']}  delta={d['patch_size_delta_chars']}")
    print("")
    _print_file_bucket("Common files", d["common_files"])
    _print_file_bucket("Only in A", d["only_a"])
    _print_file_bucket("Only in B", d["only_b"])
    if d["status_changes"]:
        print("Status changes:")
        for row in d["status_changes"]:
            print(f"  {row['path']}: A={row['a_status'] or '-'} B={row['b_status'] or '-'}")
    return 0


def _print_file_bucket(title: str, files: list[str]) -> None:
    print(f"{title}:")
    if not files:
        print("  none")
        return
    for path in files:
        print(f"  {path}")



def cmd_risk(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="traceforge risk", description="Generate a security risk report for a recorded run.")
    parser.add_argument("run_id")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    ns = parser.parse_args(args)

    paths = init_workspace()
    payload = assess_run(paths, ns.run_id)
    if payload is None:
        print(f"Run not found: {ns.run_id}")
        return 1

    if ns.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    print("TraceForge risk report")
    print(f"Run: {payload['run_id']}")
    print(f"Command: {payload.get('command')}")
    print(f"Exit code: {payload.get('exit_code')}")
    print(f"Risk level: {payload['risk_level']}")
    summary = payload.get("summary", {})
    print(f"Findings: total={summary.get('total', 0)} high={summary.get('high', 0)} medium={summary.get('medium', 0)} low={summary.get('low', 0)}")
    findings = payload.get("findings", [])
    if not findings:
        print("No notable security findings.")
    else:
        print("Findings:")
        for item in findings:
            print(f"  [{item['severity'].upper():<6}] {item['rule']:<18} {item['title']}")
            if item.get("detail"):
                print(f"           {item['detail']}")
    print(f"Recommendation: {payload.get('recommendation')}")
    return 0


def cmd_export(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="traceforge export")
    parser.add_argument("run_id")
    parser.add_argument("--out", type=Path, default=None, help="output JSON path")
    ns = parser.parse_args(args)

    paths = init_workspace()
    try:
        out = export_run(paths, ns.run_id, ns.out)
    except KeyError:
        print(f"Run not found: {ns.run_id}")
        return 1
    print(out)
    return 0


def export_run(paths: Any, run_id: str, out: Path | None = None) -> Path:
    """Export one run as a stable JSON artifact.

    Kept as a helper so both `traceforge export` and `traceforge selftest`
    exercise the same implementation.
    """
    with connect(paths) as conn:
        run = get_run(conn, run_id)
        if run is None:
            raise KeyError(run_id)
        events = get_events(conn, run_id)
        changes = get_file_changes(conn, run_id)

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
    target = out or (paths.runs_dir / run_id / "trace.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        with connect(paths) as conn:
            insert_event(conn, event(run_id, "json.exported", "Exported run as JSON trace", {"path": str(target.relative_to(paths.root)) if target.is_relative_to(paths.root) else str(target)}))
    except Exception:
        pass
    return target


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




def cmd_selftest(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="traceforge selftest", description="Run an end-to-end TraceForge smoke test in a temporary Git project.")
    parser.add_argument("--keep-temp", action="store_true", help="keep the temporary project for debugging")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    ns = parser.parse_args(args)

    results: list[dict[str, Any]] = []
    root = Path(tempfile.mkdtemp(prefix="traceforge-selftest-")).resolve()

    def record(name: str, ok: bool, detail: str = "") -> None:
        results.append({"name": name, "ok": ok, "detail": detail})

    try:
        record("create_temp_project", root.exists(), str(root))
        (root / "app.py").write_text('print("before")\n', encoding="utf-8")
        (root / "modify_app.py").write_text(
            'from pathlib import Path\n'
            'Path("app.py").write_text(\'print("after")\\n\', encoding="utf-8")\n'
            'print("app.py modified")\n',
            encoding="utf-8",
        )

        git = shutil.which("git")
        record("git_available", bool(git), git or "git not found")
        if not git:
            return _finish_selftest(results, ns.json, root, ns.keep_temp)

        _quiet([git, "init"], cwd=root)
        _quiet([git, "config", "user.name", "TraceForge Selftest"], cwd=root)
        _quiet([git, "config", "user.email", "selftest@example.invalid"], cwd=root)
        _quiet([git, "add", "."], cwd=root)
        commit = _quiet([git, "commit", "-m", "init"], cwd=root)
        record("initial_commit", commit.returncode == 0, (commit.stderr or commit.stdout).strip())

        paths = init_workspace(root)
        record("workspace_initialized", paths.db_path.exists(), str(paths.db_path))

        result = run_command([sys.executable, "modify_app.py"], cwd=root, live=False, shell=False)
        record("command_exit_zero", result.exit_code == 0, f"exit={result.exit_code}, run_id={result.run_id}")
        record("artifacts_exist", result.stdout_path.exists() and result.stderr_path.exists() and result.patch_path.exists(), str(result.stdout_path.parent))

        with connect(paths) as conn:
            run = get_run(conn, result.run_id)
            changes = get_file_changes(conn, result.run_id)
            events = get_events(conn, result.run_id)
        record("run_saved", run is not None, result.run_id)
        changed_paths = [row["path"] for row in changes]
        record("captured_app_py_change", "app.py" in changed_paths, ", ".join(changed_paths) or "no changes")
        event_kinds = {row["kind"] for row in events}
        record("events_saved", len(events) >= 8, f"events={len(events)}")
        record("timeline_has_stdout_chunk", "stdout.chunk" in event_kinds, ", ".join(sorted(event_kinds)))
        record("timeline_has_file_change", "file.changed" in event_kinds, ", ".join(sorted(event_kinds)))
        record("timeline_has_diff_capture", "git.diff.captured" in event_kinds, ", ".join(sorted(event_kinds)))
        ordered_kinds = [row["kind"] for row in events]
        if "report.generated" in ordered_kinds and "run.finished" in ordered_kinds:
            report_i = ordered_kinds.index("report.generated")
            finish_i = ordered_kinds.index("run.finished")
            record("timeline_report_before_finish", report_i < finish_i, f"report={report_i}, finish={finish_i}")
        else:
            record("timeline_report_before_finish", False, ", ".join(ordered_kinds))

        patch = result.patch_path.read_text(encoding="utf-8", errors="replace")
        record("patch_contains_diff", '-print("before")' in patch and '+print("after")' in patch, "patch.diff")

        report_path = generate_report(paths, result.run_id)
        generate_index(paths)
        record("report_generated", report_path.exists(), str(report_path))

        trace_path = export_run(paths, result.run_id)
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        record("json_export_generated", trace.get("run", {}).get("id") == result.run_id, str(trace_path))

        comparison = compare_runs(paths, result.run_id, result.run_id)
        compare_ok = bool(comparison and comparison["diff"]["changed_files_delta"] == 0 and comparison["run_a"]["metrics"]["event_count"] >= 1)
        record("compare_generated", compare_ok, "self-compare" if comparison else "missing comparison")

        risk_payload = assess_run(paths, result.run_id)
        record("risk_report_generated", bool(risk_payload and risk_payload["risk_level"] == "low"), risk_payload["risk_level"] if risk_payload else "missing risk report")

        status = _quiet([git, "status", "--porcelain=v1"], cwd=root)
        record("git_status_detects_change", "app.py" in status.stdout, status.stdout.strip())
    finally:
        if not ns.keep_temp:
            shutil.rmtree(root, ignore_errors=True)

    return _finish_selftest(results, ns.json, root, ns.keep_temp)


def _finish_selftest(results: list[dict[str, Any]], as_json: bool, root: Path, keep_temp: bool) -> int:
    ok = all(item["ok"] for item in results)
    if as_json:
        print(json.dumps({"ok": ok, "temp_project": str(root), "kept": keep_temp, "checks": results}, indent=2, ensure_ascii=False))
    else:
        print("TraceForge selftest")
        for item in results:
            mark = "OK" if item["ok"] else "FAIL"
            print(f"[{mark:4}] {item['name']:<28} {item['detail']}")
        print("\nResult:", "PASS" if ok else "FAIL")
        if keep_temp:
            print(f"Temporary project kept at: {root}")
    return 0 if ok else 1


def cmd_release_check(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="traceforge release-check", description="Validate the local source tree or a release zip before publishing.")
    parser.add_argument("--zip", dest="zip_path", type=Path, default=None, help="validate a release zip file")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    ns = parser.parse_args(args)

    checks = _check_release_zip(ns.zip_path) if ns.zip_path else _check_release_tree(Path.cwd())
    ok = all(item["ok"] for item in checks)

    if ns.json:
        print(json.dumps({"ok": ok, "checks": checks}, indent=2, ensure_ascii=False))
    else:
        title = f"TraceForge release-check ({ns.zip_path})" if ns.zip_path else "TraceForge release-check"
        print(title)
        for item in checks:
            mark = "OK" if item["ok"] else "FAIL"
            print(f"[{mark:4}] {item['name']:<28} {item['detail']}")
        print("\nResult:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def _check_release_tree(root: Path) -> list[dict[str, Any]]:
    required = [
        "pyproject.toml",
        "README.md",
        "LICENSE",
        "CHANGELOG.md",
        "SECURITY.md",
        "CONTRIBUTING.md",
        ".github/workflows/ci.yml",
        ".github/ISSUE_TEMPLATE/bug_report.yml",
        ".github/ISSUE_TEMPLATE/feature_request.yml",
        ".github/ISSUE_TEMPLATE/agent_adapter.yml",
        "docs/install.md",
        "docs/release.md",
        "examples/demo_agent_run/README.md",
        "examples/demo_agent_run/buggy_math.py",
        "examples/demo_agent_run/test_buggy_math.py",
        "examples/demo_agent_run/agent_fix.py",
        "traceforge/__init__.py",
        "traceforge/cli.py",
        "traceforge/core.py",
        "traceforge/compare.py",
        "traceforge/risk.py",
        "traceforge/storage.py",
        "traceforge/server.py",
    ]
    checks: list[dict[str, Any]] = []
    for rel in required:
        checks.append({"name": f"exists:{rel}", "ok": (root / rel).exists(), "detail": str(root / rel)})

    pyproject = root / "pyproject.toml"
    init_py = root / "traceforge" / "__init__.py"
    project_version = _read_pyproject_version(pyproject) if pyproject.exists() else None
    package_version = _read_init_version(init_py) if init_py.exists() else None
    checks.append({"name": "version_consistency", "ok": bool(project_version and project_version == package_version == __version__), "detail": f"pyproject={project_version}, package={package_version}, runtime={__version__}"})
    checks.append({"name": "working_directory", "ok": (root / "pyproject.toml").exists() and (root / "traceforge").is_dir(), "detail": str(root)})
    return checks


def _check_release_zip(zip_path: Path) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    checks.append({"name": "zip_exists", "ok": zip_path.exists(), "detail": str(zip_path)})
    if not zip_path.exists():
        return checks

    try:
        with zipfile.ZipFile(zip_path) as zf:
            names = [name for name in zf.namelist() if name and not name.endswith("/")]
            top_levels = {name.split("/", 1)[0] for name in names}
            expected_prefix = "traceforge/"
            checks.append({"name": "single_top_level_dir", "ok": top_levels == {"traceforge"}, "detail": ", ".join(sorted(top_levels))})
            required = [
                "traceforge/pyproject.toml",
                "traceforge/README.md",
                "traceforge/LICENSE",
                "traceforge/CHANGELOG.md",
                "traceforge/SECURITY.md",
                "traceforge/CONTRIBUTING.md",
                "traceforge/.github/workflows/ci.yml",
                "traceforge/.github/ISSUE_TEMPLATE/bug_report.yml",
                "traceforge/.github/ISSUE_TEMPLATE/feature_request.yml",
                "traceforge/.github/ISSUE_TEMPLATE/agent_adapter.yml",
                "traceforge/docs/install.md",
                "traceforge/docs/release.md",
                "traceforge/examples/demo_agent_run/README.md",
                "traceforge/examples/demo_agent_run/buggy_math.py",
                "traceforge/examples/demo_agent_run/test_buggy_math.py",
                "traceforge/examples/demo_agent_run/agent_fix.py",
                "traceforge/traceforge/__init__.py",
                "traceforge/traceforge/cli.py",
                "traceforge/traceforge/core.py",
                "traceforge/traceforge/compare.py",
                "traceforge/traceforge/risk.py",
                "traceforge/traceforge/server.py",
            ]
            name_set = set(names)
            for rel in required:
                checks.append({"name": f"zip_has:{rel}", "ok": rel in name_set, "detail": rel})

            py_version = None
            init_version = None
            if "traceforge/pyproject.toml" in name_set:
                py_data = tomllib.loads(zf.read("traceforge/pyproject.toml").decode("utf-8", errors="replace"))
                py_version = py_data.get("project", {}).get("version")
            if "traceforge/traceforge/__init__.py" in name_set:
                init_version = _parse_version_text(zf.read("traceforge/traceforge/__init__.py").decode("utf-8", errors="replace"))
            checks.append({"name": "zip_version_consistency", "ok": bool(py_version and py_version == init_version), "detail": f"pyproject={py_version}, package={init_version}"})
    except zipfile.BadZipFile as exc:
        checks.append({"name": "zip_readable", "ok": False, "detail": str(exc)})
    return checks


def _quiet(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _read_pyproject_version(path: Path) -> str | None:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        return data.get("project", {}).get("version")
    except Exception:
        return None


def _read_init_version(path: Path) -> str | None:
    try:
        return _parse_version_text(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _parse_version_text(text: str) -> str | None:
    for line in text.splitlines():
        if line.strip().startswith("__version__") and "=" in line:
            return line.split("=", 1)[1].strip().strip('"\'')
    return None

def cmd_dashboard(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="traceforge dashboard")
    parser.add_argument("--host", default="127.0.0.1", help="host to bind, default: 127.0.0.1")
    parser.add_argument("--port", type=int, default=8787, help="port to bind, default: 8787")
    parser.add_argument("--no-open", action="store_true", help="do not open the browser automatically")
    ns = parser.parse_args(args)
    return serve_dashboard(host=ns.host, port=ns.port, open_browser=not ns.no_open)

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
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        else:
            completed = subprocess.run(
                run_cmd,
                text=True,
                encoding="utf-8",
                errors="replace",
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
            encoding="utf-8",
            errors="replace",
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
  traceforge selftest [--keep-temp] [--json]
  traceforge release-check [--zip path] [--json]
  traceforge dashboard [--host 127.0.0.1] [--port 8787] [--no-open]
  traceforge run [--live] [--shell] [--no-propagate-exit] -- <command>
  traceforge list [--limit 20]
  traceforge show <run_id>
  traceforge timeline <run_id> [--json]
  traceforge compare <run_a> <run_b> [--json]
  traceforge risk <run_id> [--json]
  traceforge report <run_id>
  traceforge open [run_id]
  traceforge diff <run_a> <run_b>   # alias of compare
  traceforge export <run_id> [--out trace.json]
  traceforge clean [--yes] [--all]
  traceforge demo [path]
  traceforge version

Examples:
  traceforge run -- python hello.py
  traceforge run --live -- npm test
  traceforge run --shell -- "npm test && npm run lint"
  traceforge timeline <run_id>
  traceforge compare <run_a> <run_b>
  traceforge risk <run_id>
  traceforge dashboard

Without installing:
  python -m traceforge run -- <command>
""".strip()
    )


if __name__ == "__main__":
    raise SystemExit(main())
