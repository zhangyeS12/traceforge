# TraceForge Demo Script

This document describes a clean demo flow for screenshots, README GIFs, or live demos.

## Goal

Show that TraceForge can record a command, capture stdout, detect a Git diff, and display the result in the dashboard.

## 1. Start from a clean project

```bash
mkdir traceforge-demo
cd traceforge-demo
git init
traceforge init
```

Create a file:

```bash
python -c "open('hello.py', 'w').write('print(\"hello from traceforge\")\\n')"
git add .
git commit -m "demo: initial file"
```

Create a modifier script:

```bash
python -c "open('modify_hello.py', 'w').write('from pathlib import Path\\nPath(\"hello.py\").write_text(\"print(\\\"changed by traceforge command\\\")\\\\n\", encoding=\"utf-8\")\\nprint(\"hello.py modified\")\\n')"
git add modify_hello.py
git commit -m "demo: add modifier"
```

## 2. Record a command

```bash
traceforge run --live -- python modify_hello.py
```

Expected result:

```text
Exit code: 0
Changed files: 1
STDOUT contains: hello.py modified
Patch contains hello.py diff
```

## 3. Open dashboard

```bash
traceforge dashboard
```

Take screenshots of:

- Summary cards.
- Run list.
- Run detail.
- Patch tab.
- Changed files table.
- Timeline.

## 4. Clean up demo mutation

```bash
git restore hello.py
```

## PowerShell notes

If quoting is troublesome, create files with `Set-Content`:

```powershell
Set-Content hello.py 'print("hello from traceforge")'
```
