# Contributing to TraceForge

TraceForge is a local black-box recorder for command runs and AI coding agents.

The project is intentionally small and readable. Favor clear code and robust error messages over clever abstractions.

## Development setup

```bash
python -m pip install -e .
traceforge doctor
```

## Required checks before committing

```bash
traceforge release-check
traceforge selftest
```

If you are preparing a zip release, also run:

```bash
traceforge release-check --zip path/to/traceforge_vX_Y.zip
```

## Local smoke test

```bash
traceforge init
traceforge run --live -- python -c "print('hello')"
traceforge list
traceforge dashboard
```

On Windows PowerShell, prefer creating a script file when testing quoting-sensitive commands:

```powershell
Set-Content hello.py 'print("hello")'
traceforge run --live -- python hello.py
```

## Project style

- Keep the core dependency-free when possible.
- Prefer explicit errors over raw tracebacks in user-facing commands.
- Every public command should have useful help text.
- Preserve local-first behavior; do not upload traces by default.
- Do not record secrets in default reports.
- Keep `.traceforge/` local and out of Git.
- Normalize Windows/Linux behavior where possible.

## Good first issues

- Add a test-result parser for pytest, npm, Jest, or cargo test.
- Improve dashboard empty states.
- Improve diff rendering.
- Add run tags and notes.
- Add a config option for retention policy.
