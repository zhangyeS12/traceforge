from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from .storage import Paths, connect, get_events, get_file_changes, get_run, list_runs, load_config


def read_limited(path: Path, max_chars: int) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        return text[:max_chars] + f"\n\n... truncated, original length {len(text)} chars ..."
    return text


def generate_report(paths: Paths, run_id: str) -> Path:
    config = load_config(paths)
    limits = config.get("report", {})
    with connect(paths) as conn:
        run = get_run(conn, run_id)
        if run is None:
            raise SystemExit(f"Run not found: {run_id}")
        events = get_events(conn, run_id)
        file_changes = get_file_changes(conn, run_id)

    stdout = read_limited(paths.root / run["stdout_path"], int(limits.get("max_stdout_chars", 12000)))
    stderr = read_limited(paths.root / run["stderr_path"], int(limits.get("max_stderr_chars", 12000)))
    patch = read_limited(paths.root / run["patch_path"], int(limits.get("max_diff_chars", 30000)))
    risk_notes = json.loads(run["risk_notes"] or "[]")

    html_text = render_report(run, events, file_changes, stdout, stderr, patch, risk_notes)
    out = paths.reports_dir / f"{run_id}.html"
    out.write_text(html_text, encoding="utf-8")
    latest = paths.reports_dir / "latest.html"
    latest.write_text(html_text, encoding="utf-8")
    return out


def generate_index(paths: Paths, limit: int = 50) -> Path:
    with connect(paths) as conn:
        runs = list_runs(conn, limit=limit)
    rows = []
    for run in runs:
        status_class = "ok" if run["exit_code"] == 0 else "fail"
        rows.append(
            f"<tr>"
            f"<td><a href='{html.escape(run['id'])}.html'>{html.escape(run['id'])}</a></td>"
            f"<td class='{status_class}'>{run['exit_code']}</td>"
            f"<td>{run['duration_ms']} ms</td>"
            f"<td>{html.escape(run['risk_level'] or 'low')}</td>"
            f"<td><code>{html.escape(run['command'])}</code></td>"
            f"<td>{html.escape(run['started_at'])}</td>"
            f"</tr>"
        )
    text = f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>TraceForge Runs</title>
  {style()}
</head>
<body>
  <main>
    <section class="hero">
      <h1>TraceForge Runs</h1>
      <p>Black-box records for commands and AI coding agent executions.</p>
    </section>
    <section class="card">
      <table>
        <thead><tr><th>Run</th><th>Exit</th><th>Duration</th><th>Risk</th><th>Command</th><th>Started</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </section>
  </main>
</body>
</html>
"""
    out = paths.reports_dir / "index.html"
    out.write_text(text, encoding="utf-8")
    return out


def render_report(run: Any, events: list[Any], file_changes: list[Any], stdout: str, stderr: str, patch: str, risk_notes: list[str]) -> str:
    event_items = []
    for ev in events:
        data = json.loads(ev["data"] or "{}")
        event_items.append(
            f"<li><span class='time'>{html.escape(ev['ts'])}</span> "
            f"<strong>{html.escape(ev['kind'])}</strong> — {html.escape(ev['message'])}"
            f"<pre>{html.escape(json.dumps(data, indent=2, ensure_ascii=False))}</pre></li>"
        )
    file_items = [f"<li><code>{html.escape(fc['status'])}</code> {html.escape(fc['path'])}</li>" for fc in file_changes]
    risk_html = "".join(f"<li>{html.escape(note)}</li>" for note in risk_notes) or "<li>No security warnings.</li>"
    status_class = "ok" if run["exit_code"] == 0 else "fail"

    return f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>TraceForge Report {html.escape(run['id'])}</title>
  {style()}
</head>
<body>
  <main>
    <section class="hero">
      <p class="eyebrow">TraceForge Run Report</p>
      <h1>{html.escape(run['id'])}</h1>
      <p><code>{html.escape(run['command'])}</code></p>
    </section>

    <section class="grid">
      <div class="metric"><span>Exit Code</span><strong class="{status_class}">{run['exit_code']}</strong></div>
      <div class="metric"><span>Duration</span><strong>{run['duration_ms']} ms</strong></div>
      <div class="metric"><span>Risk</span><strong>{html.escape(run['risk_level'] or 'low')}</strong></div>
      <div class="metric"><span>Git HEAD</span><strong>{html.escape(str(run['git_before'] or 'n/a'))}</strong></div>
    </section>

    <section class="card">
      <h2>Timeline</h2>
      <ol class="timeline">{''.join(event_items)}</ol>
    </section>

    <section class="card">
      <h2>Changed Files</h2>
      <ul>{''.join(file_items) or '<li>No Git-tracked changes detected.</li>'}</ul>
    </section>

    <section class="card">
      <h2>Security Notes</h2>
      <ul>{risk_html}</ul>
    </section>

    <section class="card">
      <h2>Diff Stat</h2>
      <pre>{html.escape(run['diff_stat'] or 'No diff stat available.')}</pre>
    </section>

    <section class="card">
      <h2>STDOUT</h2>
      <pre>{html.escape(stdout or '(empty)')}</pre>
    </section>

    <section class="card">
      <h2>STDERR</h2>
      <pre>{html.escape(stderr or '(empty)')}</pre>
    </section>

    <section class="card">
      <h2>Patch</h2>
      <pre>{html.escape(patch or '(empty)')}</pre>
    </section>
  </main>
</body>
</html>
"""


def style() -> str:
    return """
<style>
:root { color-scheme: dark; --bg: #0b1020; --panel: #121a2e; --muted: #8fa0bd; --text: #e8eefc; --line: #27324f; --ok: #79d28d; --fail: #ff7f7f; }
* { box-sizing: border-box; }
body { margin: 0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif; background: radial-gradient(circle at top left, #1f2d54, #0b1020 40%); color: var(--text); }
main { max-width: 1180px; margin: 0 auto; padding: 42px 20px; }
.hero { margin-bottom: 24px; }
.eyebrow { color: #91a7ff; text-transform: uppercase; letter-spacing: .14em; font-size: 12px; }
h1 { margin: 0 0 10px; font-size: 38px; }
h2 { margin-top: 0; }
code, pre { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
pre { overflow: auto; background: #080d1a; border: 1px solid var(--line); border-radius: 12px; padding: 14px; line-height: 1.45; max-height: 520px; }
a { color: #a8bdff; }
.grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin: 18px 0; }
.metric, .card { background: color-mix(in srgb, var(--panel) 88%, transparent); border: 1px solid var(--line); border-radius: 18px; padding: 18px; box-shadow: 0 20px 50px rgb(0 0 0 / 20%); }
.metric span { display: block; color: var(--muted); font-size: 13px; margin-bottom: 8px; }
.metric strong { font-size: 24px; }
.card { margin: 16px 0; }
.timeline { padding-left: 22px; }
.timeline li { margin-bottom: 14px; }
.time { color: var(--muted); font-size: 12px; }
.ok { color: var(--ok); }
.fail { color: var(--fail); }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 10px 12px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }
th { color: var(--muted); font-size: 13px; }
@media (max-width: 760px) { .grid { grid-template-columns: 1fr; } h1 { font-size: 28px; } }
</style>
"""
