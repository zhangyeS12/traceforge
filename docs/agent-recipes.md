# Agent Recipes

TraceForge adapters are intentionally thin. They build a local command, then the core recorder captures stdout, stderr, exit code, Git snapshots, run-attributed patches, timeline events, risk findings, JSON export, and dashboard views.

TraceForge does not yet record internal tool calls from agent frameworks. It records the outer process and the repository effects.

## Check Adapters

```bash
traceforge agent list
traceforge agent doctor
```

`shell` is always available. Other adapters require their executable to be installed and available on `PATH`.

## Shell Passthrough

Use this when you want the agent layer but are wrapping a normal local command:

```bash
traceforge agent run shell -- python modify_hello.py
```

Use shell mode only for shell syntax such as pipes, redirects, or chained commands:

```bash
traceforge agent run shell --shell -- "npm test && npm run lint"
```

## Codex

Preview what TraceForge would run:

```bash
traceforge agent run codex --preview -- "fix the failing tests"
```

Record the run:

```bash
traceforge agent run codex --live -- "fix the failing tests"
```

The built-in Codex adapter passes the prompt as a single argument to the `codex` executable. If your local Codex CLI expects a different shape, use a custom adapter.

## Claude Code

```bash
traceforge agent run claude --preview -- "refactor the parser and run tests"
traceforge agent run claude --live -- "refactor the parser and run tests"
```

The built-in Claude adapter passes the prompt as a single argument to the `claude` executable.

## Aider

```bash
traceforge agent run aider --preview -- "fix the bug in parser.py"
traceforge agent run aider --live -- "fix the bug in parser.py"
```

The built-in Aider adapter uses:

```bash
aider --message "<prompt>"
```

## opencode

```bash
traceforge agent run opencode --preview -- "add unit tests"
traceforge agent run opencode --live -- "add unit tests"
```

## Custom Adapters

Add adapter overrides to `.traceforge/config.json`:

```json
{
  "agents": {
    "my-agent": {
      "command": ["my-agent", "--task", "{prompt}"]
    },
    "my-shell-agent": {
      "command": "my-agent --task \"{prompt}\" --yes"
    }
  }
}
```

Then run:

```bash
traceforge agent run my-agent -- "fix the failing tests"
```

List commands use argv form when possible. String commands run through the shell, so reserve them for tools that require shell syntax.

## Interactive Agents

Some coding agents ask for confirmation or open interactive prompts. TraceForge records stdout and stderr from the wrapped process, but it does not automate interactive choices. Prefer non-interactive agent flags when available, or run a preview first to confirm the command shape.

## Sharing Results

After a run:

```bash
traceforge dashboard
traceforge risk <run_id>
traceforge compare <run_a> <run_b>
traceforge export <run_id> --redact --out trace.redacted.json
```

Use `--redact` before sharing exported traces outside your machine, and review the output manually.
