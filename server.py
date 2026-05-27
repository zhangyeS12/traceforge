from __future__ import annotations

import json
import os
import shlex
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import __version__
from .core import run_command
from .report import generate_index, generate_report, read_limited
from .storage import Paths, connect, get_events, get_file_changes, get_run, init_workspace, list_runs, load_config


class DashboardServer:
    """Small local HTTP server used by `traceforge dashboard`.

    This deliberately uses only the Python standard library. The public dashboard
    should be easy to run on any developer machine without installing a separate
    Node/Next.js frontend.
    """

    def __init__(self, paths: Paths, host: str = "127.0.0.1", port: int = 8787):
        self.paths = paths
        self.host = host
        self.port = port
        handler = make_handler(paths)
        self.httpd = ThreadingHTTPServer((host, port), handler)
        self.url = f"http://{host}:{self.httpd.server_address[1]}"

    def serve_forever(self) -> None:
        self.httpd.serve_forever()

    def shutdown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


def serve_dashboard(
    *,
    host: str = "127.0.0.1",
    port: int = 8787,
    open_browser: bool = True,
) -> int:
    paths = init_workspace()
    try:
        server = DashboardServer(paths, host=host, port=port)
    except OSError as exc:
        print(f"Could not start dashboard on {host}:{port}: {exc}")
        return 1

    if open_browser:
        try:
            webbrowser.open(server.url)
        except Exception:
            pass

    print(f"TraceForge dashboard running at {server.url}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard...")
    finally:
        server.shutdown()
    return 0


def make_handler(paths: Paths) -> type[BaseHTTPRequestHandler]:
    class TraceForgeHandler(BaseHTTPRequestHandler):
        server_version = f"TraceForgeDashboard/{__version__}"

        def do_GET(self) -> None:  # noqa: N802 - stdlib API name
            parsed = urlparse(self.path)
            route = parsed.path.rstrip("/") or "/"

            try:
                if route == "/":
                    self._send_html(render_dashboard_html())
                    return
                if route == "/api/health":
                    self._send_json({"ok": True, "version": __version__, "root": str(paths.root)})
                    return
                if route == "/api/runs":
                    query = parse_qs(parsed.query)
                    limit = _parse_int(query.get("limit", ["100"])[0], default=100, minimum=1, maximum=500)
                    self._send_json(api_runs(paths, limit=limit))
                    return
                if route.startswith("/api/runs/"):
                    run_id = route.removeprefix("/api/runs/")
                    payload = api_run_detail(paths, run_id)
                    if payload is None:
                        self._send_json({"error": "run not found", "run_id": run_id}, status=404)
                    else:
                        self._send_json(payload)
                    return
                self._send_json({"error": "not found", "path": parsed.path}, status=404)
            except Exception as exc:  # public dashboard should show a useful error, not a broken socket
                self._send_json({"error": exc.__class__.__name__, "message": str(exc)}, status=500)

        def do_POST(self) -> None:  # noqa: N802 - stdlib API name
            parsed = urlparse(self.path)
            route = parsed.path.rstrip("/") or "/"
            try:
                if route == "/api/runs":
                    body = self._read_json_body()
                    payload, status = api_create_run(paths, body)
                    self._send_json(payload, status=status)
                    return
                self._send_json({"error": "not found", "path": parsed.path}, status=404)
            except Exception as exc:
                self._send_json({"error": exc.__class__.__name__, "message": str(exc)}, status=500)

        def log_message(self, fmt: str, *args: Any) -> None:
            # Keep the CLI quiet. Browser requests are not useful for normal users.
            return

        def _read_json_body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length) if length else b"{}"
            if not raw:
                return {}
            try:
                data = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON body: {exc}") from exc
            if not isinstance(data, dict):
                raise ValueError("JSON body must be an object")
            return data

        def _send_html(self, text: str, status: int = 200) -> None:
            data = text.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_json(self, payload: Any, status: int = 200) -> None:
            data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return TraceForgeHandler


def api_runs(paths: Paths, limit: int = 100) -> dict[str, Any]:
    with connect(paths) as conn:
        runs = list_runs(conn, limit=limit)
        items: list[dict[str, Any]] = []
        for run in runs:
            changes = get_file_changes(conn, run["id"])
            item = dict(run)
            item["changed_files_count"] = len(changes)
            items.append(item)
    return {"schema_version": 1, "runs": items}


def api_run_detail(paths: Paths, run_id: str) -> dict[str, Any] | None:
    config = load_config(paths)
    limits = config.get("report", {})
    with connect(paths) as conn:
        run = get_run(conn, run_id)
        if run is None:
            return None
        events = [dict(ev) for ev in get_events(conn, run_id)]
        changes = [dict(change) for change in get_file_changes(conn, run_id)]

    run_dict = dict(run)
    stdout = _read_artifact(paths, run_dict.get("stdout_path"), int(limits.get("max_stdout_chars", 12000)))
    stderr = _read_artifact(paths, run_dict.get("stderr_path"), int(limits.get("max_stderr_chars", 12000)))
    patch = _read_artifact(paths, run_dict.get("patch_path"), int(limits.get("max_diff_chars", 30000)))
    return {
        "schema_version": 1,
        "run": run_dict,
        "events": events,
        "file_changes": changes,
        "artifacts": {"stdout": stdout, "stderr": stderr, "patch": patch},
    }


def api_create_run(paths: Paths, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
    command_text = str(body.get("command") or "").strip()
    use_shell = bool(body.get("shell", False))
    if not command_text:
        return {"error": "empty command", "message": "Please enter a command to run."}, 400

    try:
        command: str | list[str]
        if use_shell:
            command = command_text
        else:
            command = split_command_text(command_text)
            if not command:
                return {"error": "empty command", "message": "Please enter a command to run."}, 400
        result = run_command(command, cwd=paths.root, live=False, shell=use_shell)
    except SystemExit as exc:
        return {"error": "blocked", "message": str(exc)}, 403
    except FileNotFoundError as exc:
        return {"error": "command not found", "message": str(exc)}, 400
    except (OSError, TypeError, ValueError) as exc:
        return {"error": exc.__class__.__name__, "message": str(exc)}, 400

    generate_report(paths, result.run_id)
    generate_index(paths)
    detail = api_run_detail(paths, result.run_id)
    return {"ok": True, "run_id": result.run_id, "detail": detail}, 201


def split_command_text(command: str) -> list[str]:
    """Split a command typed into the dashboard into argv.

    The CLI path already receives argv directly from the terminal. The dashboard
    receives a single text field, so it needs a small parser. On Windows,
    shlex(posix=False) keeps surrounding quotes; stripping one layer gives the
    expected behavior for common commands such as:

        python -c "print('hello')"
    """
    parts = shlex.split(command, posix=os.name != "nt")
    if os.name == "nt":
        parts = [_strip_matching_quotes(part) for part in parts]
    return parts


def _strip_matching_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _read_artifact(paths: Paths, rel_path: str | None, max_chars: int) -> str:
    if not rel_path:
        return ""
    path = paths.root / rel_path
    return read_limited(path, max_chars)


def _parse_int(value: str, *, default: int, minimum: int, maximum: int) -> int:
    try:
        n = int(value)
    except ValueError:
        return default
    return max(minimum, min(maximum, n))


def render_dashboard_html() -> str:
    # One-file app: still no build step, but now it can also start a recorded run from the browser.
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>TraceForge Dashboard</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #070b16;
      --panel: rgba(16, 24, 43, .86);
      --panel-2: rgba(9, 15, 29, .92);
      --panel-3: rgba(255,255,255,.045);
      --text: #e8eefc;
      --muted: #93a4c3;
      --line: #283451;
      --line-soft: rgba(255,255,255,.08);
      --accent: #8eb5ff;
      --accent-2: #b18cff;
      --ok: #7bd88f;
      --fail: #ff8585;
      --warn: #ffd37a;
      --add-bg: rgba(92, 214, 128, .13);
      --del-bg: rgba(255, 119, 119, .14);
      --add: #91eba5;
      --del: #ff9a9a;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at 12% 0%, rgba(75, 106, 255, .26), transparent 28%),
        radial-gradient(circle at 82% 2%, rgba(177, 140, 255, .20), transparent 30%),
        linear-gradient(180deg, #0b1224, var(--bg));
      min-height: 100vh;
    }
    button, input, label { font: inherit; }
    code, pre { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; }
    .app { max-width: 1480px; margin: 0 auto; padding: 24px; }
    header { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
    .brand h1 { margin: 0; font-size: 32px; letter-spacing: -.04em; }
    .brand p { margin: 6px 0 0; color: var(--muted); }
    .toolbar { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
    .btn {
      border: 1px solid var(--line); background: rgba(255,255,255,.055); color: var(--text);
      border-radius: 12px; padding: 10px 14px; cursor: pointer;
      transition: border-color .15s ease, transform .15s ease, background .15s ease;
    }
    .btn:hover:not(:disabled) { border-color: var(--accent); background: rgba(142,181,255,.10); transform: translateY(-1px); }
    .btn:disabled { opacity: .55; cursor: not-allowed; }
    .btn.primary { background: linear-gradient(135deg, rgba(142,181,255,.22), rgba(177,140,255,.18)); border-color: rgba(142,181,255,.55); }
    .summary { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 12px; margin-bottom: 18px; }
    .summary-card { background: linear-gradient(180deg, rgba(255,255,255,.055), rgba(255,255,255,.025)); border: 1px solid var(--line); border-radius: 18px; padding: 14px; box-shadow: 0 18px 50px rgba(0,0,0,.18); }
    .summary-card span { display: block; color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }
    .summary-card strong { display: block; font-size: 24px; margin-top: 6px; letter-spacing: -.02em; }
    .runner { background: linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,.025)); border: 1px solid var(--line); border-radius: 22px; padding: 16px; margin-bottom: 18px; box-shadow: 0 22px 70px rgba(0,0,0,.18); }
    .runner-title { display: flex; align-items: center; justify-content: space-between; gap: 14px; margin-bottom: 12px; }
    .runner-title h2 { margin: 0; font-size: 15px; color: var(--muted); text-transform: uppercase; letter-spacing: .12em; }
    .runner-form { display: grid; grid-template-columns: 1fr auto auto; gap: 10px; align-items: center; }
    .runner-input { width: 100%; background: var(--panel-2); color: var(--text); border: 1px solid var(--line); border-radius: 13px; padding: 12px; outline: none; }
    .runner-input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(142,181,255,.10); }
    .check { display: flex; align-items: center; gap: 7px; color: var(--muted); white-space: nowrap; }
    .status-bar { margin-top: 10px; color: var(--muted); font-size: 13px; min-height: 20px; }
    .status-bar.ok { color: var(--ok); } .status-bar.fail { color: var(--fail); } .status-bar.warn { color: var(--warn); }
    .layout { display: grid; grid-template-columns: 430px 1fr; gap: 18px; align-items: start; }
    .panel { background: var(--panel); border: 1px solid var(--line); border-radius: 22px; box-shadow: 0 22px 70px rgba(0,0,0,.25); overflow: hidden; backdrop-filter: blur(10px); }
    .panel-head { padding: 16px; border-bottom: 1px solid var(--line); display: flex; justify-content: space-between; align-items: center; gap: 10px; }
    .panel-head h2 { margin: 0; font-size: 15px; color: var(--muted); text-transform: uppercase; letter-spacing: .12em; }
    .search { width: 100%; background: var(--panel-2); color: var(--text); border: 1px solid var(--line); border-radius: 12px; padding: 10px 12px; outline: none; }
    .search:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(142,181,255,.10); }
    .filters { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
    .chip { border: 1px solid var(--line); background: rgba(255,255,255,.035); color: var(--muted); border-radius: 999px; padding: 6px 9px; cursor: pointer; font-size: 12px; }
    .chip.active { color: var(--text); border-color: var(--accent); background: rgba(142,181,255,.13); }
    .runs { max-height: calc(100vh - 420px); overflow: auto; }
    .run-item { width: 100%; display: block; text-align: left; padding: 14px 16px; border: 0; border-bottom: 1px solid var(--line); background: transparent; color: var(--text); cursor: pointer; }
    .run-item:hover, .run-item.active { background: rgba(142, 181, 255, .10); }
    .run-top { display: flex; justify-content: space-between; gap: 10px; align-items: center; }
    .run-id { color: var(--accent); font-size: 12px; word-break: break-all; }
    .cmd { margin-top: 9px; color: var(--text); line-height: 1.45; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .meta { margin-top: 8px; color: var(--muted); font-size: 12px; display: flex; gap: 10px; flex-wrap: wrap; }
    .pill { border: 1px solid var(--line); border-radius: 999px; padding: 3px 8px; font-size: 12px; white-space: nowrap; }
    .ok { color: var(--ok); } .fail { color: var(--fail); } .warn { color: var(--warn); }
    .muted { color: var(--muted); }
    .detail { min-height: 640px; }
    .empty { padding: 60px 24px; color: var(--muted); text-align: center; }
    .metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; padding: 16px; border-bottom: 1px solid var(--line); }
    .metric { background: var(--panel-3); border: 1px solid var(--line); border-radius: 16px; padding: 14px; }
    .metric span { display: block; color: var(--muted); font-size: 12px; margin-bottom: 7px; }
    .metric strong { font-size: 22px; }
    .section { padding: 16px; border-bottom: 1px solid var(--line); }
    .section h3 { margin: 0 0 12px; font-size: 16px; }
    .command { background: #070b15; border: 1px solid var(--line); border-radius: 14px; padding: 12px; overflow: auto; }
    .tabs { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; align-items: center; }
    .tab { border: 1px solid var(--line); background: rgba(255,255,255,.035); color: var(--muted); border-radius: 999px; padding: 7px 10px; cursor: pointer; }
    .tab.active { color: var(--text); border-color: var(--accent); background: rgba(142,181,255,.13); }
    .copy { margin-left: auto; }
    pre, .diff-box { margin: 0; background: #050914; border: 1px solid var(--line); border-radius: 14px; padding: 14px; overflow: auto; max-height: 520px; line-height: 1.5; white-space: pre; }
    .diff-line { display: block; padding: 0 6px; min-height: 20px; }
    .diff-line.add { background: var(--add-bg); color: var(--add); }
    .diff-line.del { background: var(--del-bg); color: var(--del); }
    .diff-line.hunk { color: var(--accent-2); background: rgba(177,140,255,.09); }
    .diff-line.file { color: var(--accent); font-weight: 650; }
    table { width: 100%; border-collapse: collapse; }
    th, td { border-bottom: 1px solid var(--line-soft); padding: 9px 10px; text-align: left; vertical-align: top; }
    th { color: var(--muted); font-size: 12px; }
    .timeline { list-style: none; padding: 0; margin: 0; }
    .timeline li { padding: 0 0 14px 22px; border-left: 1px solid var(--line); position: relative; }
    .timeline li::before { content: ''; position: absolute; left: -5px; top: 5px; width: 9px; height: 9px; border-radius: 99px; background: var(--accent); box-shadow: 0 0 0 4px rgba(142,181,255,.12); }
    .timeline .time { color: var(--muted); font-size: 12px; margin-bottom: 2px; }
    .error { color: var(--fail); padding: 14px 16px; }
    .notice { color: var(--muted); background: rgba(255,255,255,.035); border: 1px solid var(--line); border-radius: 14px; padding: 12px; }
    @media (max-width: 1120px) { .summary { grid-template-columns: repeat(3, minmax(0, 1fr)); } .layout { grid-template-columns: 1fr; } .runs { max-height: 420px; } .runner-form { grid-template-columns: 1fr; } }
    @media (max-width: 680px) { .app { padding: 14px; } header { flex-direction: column; align-items: flex-start; } .summary, .metrics { grid-template-columns: 1fr 1fr; } }
    @media (max-width: 460px) { .summary, .metrics { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <div class="app">
    <header>
      <div class="brand">
        <h1>TraceForge Dashboard</h1>
        <p>Replay command runs, inspect code changes, and audit AI coding agent behavior.</p>
      </div>
      <div class="toolbar">
        <button class="btn" id="refreshBtn">Refresh</button>
      </div>
    </header>

    <section class="summary" id="summary"></section>

    <section class="runner">
      <div class="runner-title">
        <h2>Run a command</h2>
        <span class="muted">Runs in the current project directory and records stdout, stderr, exit code, and Git diff.</span>
      </div>
      <form class="runner-form" id="runForm">
        <input class="runner-input" id="commandInput" placeholder='python modify_hello.py' autocomplete="off" />
        <label class="check" title="Use the system shell. Useful for pipes, redirects, &&, and chained commands.">
          <input type="checkbox" id="shellToggle" /> shell
        </label>
        <button class="btn primary" id="runBtn" type="submit">Run Command</button>
      </form>
      <div class="status-bar" id="runStatus"></div>
    </section>

    <div class="layout">
      <aside class="panel">
        <div class="panel-head">
          <h2>Runs</h2>
          <span class="pill" id="runCount">0</span>
        </div>
        <div class="section">
          <input class="search" id="search" placeholder="Search command or run id..." />
          <div class="filters" id="filters"></div>
        </div>
        <div class="runs" id="runs"></div>
      </aside>

      <main class="panel detail" id="detail">
        <div class="empty">Select a run to inspect stdout, stderr, events, file changes, and patch diff.</div>
      </main>
    </div>
  </div>

<script>
const state = { runs: [], selected: null, detail: null, tab: 'patch', query: '', filter: 'all', running: false };
const filters = [
  ['all', 'All'], ['success', 'Success'], ['failed', 'Failed'], ['changed', 'Changed'], ['risky', 'Risky']
];
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const short = (s, n=14) => String(s ?? '').length > n ? String(s).slice(0,n) + '…' : String(s ?? '');
const num = (v) => Number(v || 0);

async function loadRuns({keepSelection=false} = {}) {
  if (!keepSelection) $('runs').innerHTML = '<div class="empty">Loading runs...</div>';
  const res = await fetch('/api/runs?limit=200');
  if (!res.ok) throw new Error('Failed to load runs: HTTP ' + res.status);
  const data = await res.json();
  state.runs = data.runs || [];
  renderSummary();
  renderFilters();
  renderRuns();
  if (!keepSelection && !state.selected && state.runs.length) selectRun(state.runs[0].id);
}

function renderSummary() {
  const total = state.runs.length;
  const success = state.runs.filter(r => num(r.exit_code) === 0).length;
  const failed = state.runs.filter(r => num(r.exit_code) !== 0).length;
  const changed = state.runs.reduce((acc, r) => acc + num(r.changed_files_count), 0);
  const risky = state.runs.filter(r => (r.risk_level || 'low') !== 'low').length;
  const avg = total ? Math.round(state.runs.reduce((acc, r) => acc + num(r.duration_ms), 0) / total) : 0;
  const rate = total ? Math.round((success / total) * 100) + '%' : '—';
  $('summary').innerHTML = [
    ['Total Runs', total], ['Success Rate', rate], ['Failed', failed], ['Changed Files', changed], ['Risky Runs', risky], ['Avg Duration', avg + 'ms']
  ].map(([label, value]) => `<div class="summary-card"><span>${label}</span><strong>${value}</strong></div>`).join('');
}

function renderFilters() {
  $('filters').innerHTML = filters.map(([key, label]) => `<button class="chip${state.filter === key ? ' active' : ''}" onclick="setFilter('${key}')">${label}</button>`).join('');
}

function setFilter(key) { state.filter = key; renderFilters(); renderRuns(); }

function filteredRuns() {
  const q = state.query.toLowerCase().trim();
  return state.runs.filter(r => {
    const matchesQuery = !q || String(r.id).toLowerCase().includes(q) || String(r.command).toLowerCase().includes(q);
    if (!matchesQuery) return false;
    if (state.filter === 'success') return num(r.exit_code) === 0;
    if (state.filter === 'failed') return num(r.exit_code) !== 0;
    if (state.filter === 'changed') return num(r.changed_files_count) > 0;
    if (state.filter === 'risky') return (r.risk_level || 'low') !== 'low';
    return true;
  });
}

function renderRuns() {
  const items = filteredRuns();
  $('runCount').textContent = items.length;
  if (!items.length) { $('runs').innerHTML = '<div class="empty">No matching runs. Try another filter or run a new command.</div>'; return; }
  $('runs').innerHTML = items.map(r => {
    const cls = num(r.exit_code) === 0 ? 'ok' : 'fail';
    const active = state.selected === r.id ? ' active' : '';
    return `<button class="run-item${active}" onclick="selectRun('${esc(r.id)}')">
      <div class="run-top"><span class="run-id">${esc(r.id)}</span><span class="pill ${cls}">exit ${esc(r.exit_code)}</span></div>
      <div class="cmd"><code>${esc(r.command)}</code></div>
      <div class="meta"><span>${esc(r.duration_ms)}ms</span><span>files ${esc(r.changed_files_count ?? 0)}</span><span>risk ${esc(r.risk_level || 'low')}</span></div>
    </button>`;
  }).join('');
}

async function selectRun(id) {
  state.selected = id;
  renderRuns();
  $('detail').innerHTML = '<div class="empty">Loading run detail...</div>';
  const res = await fetch('/api/runs/' + encodeURIComponent(id));
  if (!res.ok) { $('detail').innerHTML = '<div class="error">Run not found.</div>'; return; }
  state.detail = await res.json();
  state.tab = hasPatch(state.detail) ? 'patch' : 'stdout';
  renderDetail();
}

async function createRun(command, shell) {
  setRunning(true, 'Running command... The dashboard will refresh when it finishes.', 'warn');
  try {
    const res = await fetch('/api/runs', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({command, shell})
    });
    const data = await res.json();
    if (!res.ok || !data.ok) {
      const msg = data.message || data.error || ('HTTP ' + res.status);
      setRunning(false, 'Command failed to start: ' + msg, 'fail');
      return;
    }
    await loadRuns({keepSelection: true});
    await selectRun(data.run_id);
    const exitCode = data.detail?.run?.exit_code;
    const cls = Number(exitCode) === 0 ? 'ok' : 'fail';
    setRunning(false, `Recorded ${data.run_id} with exit code ${exitCode}.`, cls);
  } catch (err) {
    setRunning(false, 'Dashboard request failed: ' + err.message, 'fail');
  }
}

function setRunning(isRunning, message='', level='') {
  state.running = isRunning;
  $('runBtn').disabled = isRunning;
  $('commandInput').disabled = isRunning;
  $('shellToggle').disabled = isRunning;
  $('runStatus').className = 'status-bar ' + level;
  $('runStatus').textContent = message;
}

function hasPatch(detail) { return Boolean((detail?.artifacts || {}).patch || ''); }

function renderDetail() {
  const d = state.detail;
  if (!d) return;
  const r = d.run;
  const exitCls = num(r.exit_code) === 0 ? 'ok' : 'fail';
  const files = d.file_changes || [];
  const events = d.events || [];
  const notes = safeJson(r.risk_notes, []);
  $('detail').innerHTML = `
    <div class="panel-head">
      <h2>Run Detail</h2>
      <span class="pill">${esc(short(r.id, 24))}</span>
    </div>
    <div class="metrics">
      <div class="metric"><span>Exit Code</span><strong class="${exitCls}">${esc(r.exit_code)}</strong></div>
      <div class="metric"><span>Duration</span><strong>${esc(r.duration_ms)}ms</strong></div>
      <div class="metric"><span>Changed Files</span><strong>${files.length}</strong></div>
      <div class="metric"><span>Risk</span><strong class="${r.risk_level === 'high' ? 'warn' : ''}">${esc(r.risk_level || 'low')}</strong></div>
    </div>
    <div class="section">
      <h3>Command</h3>
      <div class="command"><code>${esc(r.command)}</code></div>
    </div>
    <div class="section">
      <h3>Artifacts</h3>
      <div class="tabs">
        ${tabButton('patch', 'Patch')}
        ${tabButton('stdout', 'STDOUT')}
        ${tabButton('stderr', 'STDERR')}
        ${tabButton('json', 'JSON')}
        <button class="tab copy" onclick="copyArtifact()">Copy</button>
      </div>
      ${artifactHtml()}
    </div>
    <div class="section">
      <h3>Changed Files</h3>
      ${renderFiles(files)}
    </div>
    <div class="section">
      <h3>Timeline</h3>
      <ol class="timeline">${events.map(ev => `<li><div class="time">${esc(ev.ts)}</div><strong>${esc(ev.kind)}</strong><div class="muted">${esc(ev.message)}</div></li>`).join('') || '<li>No events recorded.</li>'}</ol>
    </div>
    <div class="section">
      <h3>Security Notes</h3>
      <ul>${notes.length ? notes.map(n => `<li>${esc(n)}</li>`).join('') : '<li>No security warnings.</li>'}</ul>
    </div>
  `;
}

function tabButton(name, label) {
  const active = state.tab === name ? ' active' : '';
  return `<button class="tab${active}" onclick="state.tab='${name}'; renderDetail();">${label}</button>`;
}

function artifactRaw() {
  if (state.tab === 'json') return JSON.stringify(state.detail, null, 2);
  return (state.detail.artifacts || {})[state.tab] || '';
}

function artifactHtml() {
  const raw = artifactRaw();
  if (!raw) return '<div class="notice">This artifact is empty.</div>';
  if (state.tab === 'patch') return renderDiff(raw);
  return `<pre>${esc(raw)}</pre>`;
}

function renderDiff(text) {
  const lines = String(text).split(/\\r?\\n/);
  return `<div class="diff-box">${lines.map(line => {
    let cls = 'diff-line';
    if (line.startsWith('+') && !line.startsWith('+++')) cls += ' add';
    else if (line.startsWith('-') && !line.startsWith('---')) cls += ' del';
    else if (line.startsWith('@@')) cls += ' hunk';
    else if (line.startsWith('diff --git') || line.startsWith('index ') || line.startsWith('---') || line.startsWith('+++')) cls += ' file';
    return `<span class="${cls}">${esc(line || ' ')}</span>`;
  }).join('')}</div>`;
}

function renderFiles(files) {
  if (!files.length) return '<p class="muted">No Git-tracked changes detected.</p>';
  return `<table><thead><tr><th>Status</th><th>Path</th></tr></thead><tbody>${files.map(f => `<tr><td><code>${esc(f.status)}</code></td><td>${esc(f.path)}</td></tr>`).join('')}</tbody></table>`;
}

function safeJson(s, fallback) { try { return JSON.parse(s || '[]'); } catch { return fallback; } }

async function copyArtifact() {
  const raw = artifactRaw();
  try {
    await navigator.clipboard.writeText(raw || '');
  } catch {
    alert('Copy failed. Your browser may block clipboard access on localhost.');
  }
}

$('refreshBtn').addEventListener('click', () => loadRuns({keepSelection: true}));
$('search').addEventListener('input', (e) => { state.query = e.target.value; renderRuns(); });
$('runForm').addEventListener('submit', (e) => {
  e.preventDefault();
  const command = $('commandInput').value.trim();
  if (!command) { setRunning(false, 'Enter a command first.', 'fail'); return; }
  createRun(command, $('shellToggle').checked);
});
loadRuns().catch(err => { $('runs').innerHTML = `<div class="error">${esc(err.message)}</div>`; });
</script>
</body>
</html>"""
