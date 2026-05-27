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

### V0.2 current features

- `traceforge run -- <command>` records a command execution.
- `--live` streams stdout/stderr while still recording it.
- Shellless execution by default, which avoids Windows quoting bugs.
- `--shell` when you explicitly need shell features like `&&`, pipes, or redirects.
- Captures stdout, stderr, exit code, duration, and environment metadata.
- Captures Git HEAD, Git status, changed files, diff stat, and patch.
- Stores trace data in local SQLite under `.traceforge/`.
- Generates self-contained HTML reports.
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
traceforge diff <run_a> <run_b>
traceforge export <run_id> [--out trace.json]
traceforge clean [--yes] [--all]
traceforge demo [path]
traceforge version
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

- File-system watcher instead of only before/after Git snapshots
- Better diff viewer UI
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
