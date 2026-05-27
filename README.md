# TraceForge

**TraceForge is a black-box recorder for AI coding agents and shell commands.**

It records what happened during a run: command, stdout, stderr, exit code, duration, Git status, changed files, patch diff, security warnings, and an HTML replay report.

TraceForge is designed for a world where developers use AI coding agents such as Codex, Claude Code, Cline, Cursor, OpenHands, and custom shell-based automation. The goal is simple:

> Make agentic coding reproducible, auditable, and easy to review.

## Why this project exists

AI coding agents are useful, but they are hard to debug:

- What files did the agent change?
- Which command failed?
- What patch did the run produce?
- Did it touch sensitive files?
- How do two agent runs differ?
- Can I export a run for review or bug reports?

TraceForge gives every run a local, reviewable trace.

## Features

### V0.3 current features

- Dashboard polish: summary cards, filters, and highlighted patch diffs

- `traceforge run -- <command>` records a command execution.
- `--live` streams stdout/stderr while still recording it.
- Shellless execution by default, which avoids Windows quoting bugs.
- `--shell` when you explicitly need shell features like `&&`, pipes, or redirects.
- Captures stdout, stderr, exit code, duration, and environment metadata.
- Captures Git HEAD, Git status, changed files, diff stat, and patch.
- Stores trace data in local SQLite under `.traceforge/`.
- Generates self-contained HTML reports.
- `traceforge dashboard` starts a local browser dashboard at `http://127.0.0.1:8787`.
- Dashboard shows run list, run detail, metrics, timeline, changed files, stdout, stderr, patch diff, and JSON.
- Provides run listing, run details, basic run comparison, and a local report index.
- `traceforge doctor` checks your local environment.
- `traceforge export <run_id>` exports a full run as JSON.
- `traceforge clean --yes` clears recorded local traces.
- Includes a simple security warning layer for risky commands and sensitive file names.

## Install locally

From this repository:

```bash
python -m pip install -e .
```

Then run:

```bash
traceforge init
traceforge doctor
traceforge run -- python hello.py
traceforge list
traceforge open
traceforge dashboard
```

Without installing, from the repository root:

```bash
python -m traceforge init
python -m traceforge run -- python hello.py
```

## Quick start

Create a tiny test script:

```bash
python -c "open('hello.py', 'w').write('print(\"hello from traceforge\")\\n')"
```

Record it:

```bash
traceforge init
traceforge run --live -- python hello.py
traceforge open
```

On PowerShell, creating the file can also be done with:

```powershell
Set-Content hello.py 'print("hello from traceforge")'
```

## Example: record a test run

Inside any Git project:

```bash
traceforge init
traceforge run --live -- npm test
```

or:

```bash
traceforge run --live -- python -m pytest
```

After the command finishes, TraceForge writes files like:

```text
.traceforge/
  traceforge.db
  config.json
  runs/
    20260526-120000-a1b2c3d4/
      stdout.txt
      stderr.txt
      patch.diff
      trace.json
  reports/
    index.html
    latest.html
    20260526-120000-a1b2c3d4.html
```

## CLI

```bash
traceforge init
traceforge doctor [--json]
traceforge run [--live] [--shell] [--no-propagate-exit] -- <command>
traceforge list --limit 20
traceforge show <run_id>
traceforge report <run_id>
traceforge open [run_id]
traceforge dashboard [--host 127.0.0.1] [--port 8787] [--no-open]
traceforge diff <run_a> <run_b>
traceforge export <run_id> [--out trace.json]
traceforge clean [--yes] [--all]
traceforge demo [path]
traceforge version
```

## Dashboard

Start the local web UI:

```bash
traceforge dashboard
```

This opens a local browser page, usually:

```text
http://127.0.0.1:8787
```

The dashboard reads your local `.traceforge/traceforge.db`; it does not upload your traces anywhere. Press `Ctrl+C` in the terminal to stop the server.

For a terminal-only machine:

```bash
traceforge dashboard --no-open
```

## Shellless vs shell mode

By default TraceForge runs commands without a shell:

```bash
traceforge run -- python hello.py
```

This is safer and avoids Windows quoting issues.

Use `--shell` only when you need shell syntax:

```bash
traceforge run --shell -- "npm test && npm run lint"
```

## Security policy

The initial config is stored at:

```text
.traceforge/config.json
```

Example:

```json
{
  "security": {
    "mode": "warn",
    "deny_command_substrings": ["rm -rf /", "sudo rm -rf", "mkfs"],
    "sensitive_file_patterns": [".env", "id_rsa", ".ssh/"]
  }
}
```

Set `mode` to `block` if risky commands should be blocked instead of only reported.

## Architecture

```text
CLI command
   ↓
Security pre-check
   ↓
Git snapshot before
   ↓
Subprocess execution
   ↓
stdout/stderr live stream and capture
   ↓
Git snapshot after + patch diff
   ↓
SQLite trace storage
   ↓
HTML report + optional JSON export
```

## Roadmap

### V0.1

- CLI recorder
- subprocess capture
- Git patch capture
- SQLite trace store
- HTML reports
- basic risk warnings

### V0.2

- Real-time streaming while the command is running
- Windows-safe shellless execution by default
- Environment doctor command
- JSON export format
- Clean command for local traces
- Better CLI help and versioning

### V0.3

- Local browser dashboard
- JSON API for runs and run details
- Visual run list, metrics, timeline, changed files, artifacts, and patch viewer

### V0.4

- File-system watcher instead of only before/after Git snapshots
- Better side-by-side diff viewer UI
- Selftest and GitHub Actions CI
- Test-result parser for pytest/npm/jest
- Run tags and notes
- Configurable retention policy

### V0.4

- Docker sandbox execution
- Network allow/deny policy
- MCP tool-call recorder
- Agent adapters for Codex, Claude Code, Cline, OpenHands
- Run replay and richer run comparison

### V0.5

- AI-generated failure analysis report
- Agent benchmark mode
- OpenTelemetry-style trace/span model
- Hosted documentation site and release workflow

## Resume description

> Built TraceForge, a black-box recorder for AI coding agents and shell commands. Implemented a CLI that captures subprocess output, Git patches, changed files, runtime metadata, security warnings, and stores execution traces in SQLite with self-contained HTML replay reports and JSON exports.

## Contributing

This project is intentionally small and readable. Good first contributions:

- Add a test-result parser.
- Improve HTML diff rendering.
- Add support for tags and run notes.
- Add Docker sandbox execution.
- Add adapters for common coding agents.


### Run commands from the dashboard

After starting the dashboard, you can type a command directly in the browser:

```bash
traceforge dashboard
```

Then enter a command such as:

```bash
python modify_hello.py
```

TraceForge will run it locally, record stdout/stderr, capture Git diff, refresh the run list, and open the new run detail automatically.

## Public-readiness checks

TraceForge includes two commands that are useful before publishing or debugging user environments:

```bash
traceforge selftest
traceforge release-check
traceforge release-check --zip traceforge_v0_5.zip
```

`selftest` creates a temporary Git project and verifies the full record → diff → report → JSON flow.
`release-check` catches packaging mistakes before a zip or release is shared.
