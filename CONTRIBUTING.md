# Contributing to TraceForge

TraceForge is a black-box recorder for AI coding agents and shell commands.

## Development setup

```bash
python -m pip install -e .
traceforge doctor
```

## Local smoke test

```bash
traceforge init
traceforge run --live -- python -c "print('hello')"
traceforge list
traceforge open
```

On Windows PowerShell, prefer creating a script file when testing quoting-sensitive commands:

```powershell
Set-Content hello.py 'print("hello")'
traceforge run --live -- python hello.py
```

## Project style

- Keep the core dependency-free when possible.
- Prefer clear code over clever code.
- Every public command should have a useful error message.
- Do not record secrets in default reports.
- Keep `.traceforge/` local and out of Git.
