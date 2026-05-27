# TraceForge Knowledge Notes

This document explains the knowledge used by the MVP.

## 1. CLI design

TraceForge is a command-line tool. The CLI is the user's entry point:

```bash
traceforge run -- npm test
```

Key ideas:

- Parse command arguments.
- Support subcommands such as `init`, `run`, `list`, `show`, and `diff`.
- Make the tool useful even before a web UI exists.

In the MVP, CLI parsing uses Python's standard `argparse` and manual dispatch.

## 2. Subprocess monitoring

The core operation is running another command and recording its behavior.

TraceForge uses:

- `subprocess.run(...)`
- `stdout=subprocess.PIPE`
- `stderr=subprocess.PIPE`
- `exit_code`
- elapsed time from `time.monotonic()`

This teaches process management: a program can start and observe another program.

## 3. Git-based code-change capture

Before running the command, TraceForge records:

- current Git HEAD
- `git status --porcelain`

After running the command, it records:

- new Git status
- `git diff --patch --binary HEAD`
- `git diff --stat HEAD`

This lets us answer: "What did the agent or command change?"

## 4. Trace data model

A trace is represented as several entities:

- `runs`: one full execution
- `events`: timeline events inside that execution
- `file_changes`: files changed by the run

This is similar to observability systems. Later versions can evolve toward OpenTelemetry-style traces and spans.

## 5. SQLite local storage

TraceForge stores data locally in `.traceforge/traceforge.db`.

SQLite is suitable because:

- no server is required
- it is fast enough for local traces
- it keeps the project easy to install
- it supports structured queries later

## 6. HTML report generation

The MVP generates static HTML reports. This is simpler than a full web app but still demo-friendly.

The report includes:

- metadata
- timeline
- changed files
- risk notes
- stdout
- stderr
- patch diff

This gives the project a visible result that can be shown in a README GIF.

## 7. Security policy

The first version does not implement a real sandbox. It implements a warning/block policy:

- risky command substrings
- sensitive file name patterns
- security notes in reports

This creates a foundation for future Docker sandboxing and network control.

## 8. Why this is relevant to AI coding agents

An AI coding agent is essentially an automated developer that reads files, edits code, and runs commands.

TraceForge records those effects from the outside. That means it can work even before integrating deeply with a specific agent.

This is the "black-box" approach:

- do not trust the agent's explanation
- record actual filesystem and command effects
- make the run reproducible and reviewable

## 9. What to learn next

After understanding this MVP, learn in this order:

1. Rust or Go CLI development
2. file-system watchers
3. async process streaming
4. Docker sandboxing
5. network policy controls
6. MCP protocol basics
7. Next.js dashboard
8. OpenTelemetry trace/span concepts
9. AI-generated report analysis
