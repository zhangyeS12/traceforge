# Demo Agent Run

This directory contains a tiny scenario that behaves like an agent fixing a bug.

Files:

- `buggy_math.py` starts with a broken `divide` function.
- `test_buggy_math.py` checks expected behavior.
- `agent_fix.py` simulates an agent patching the bug.

Try it from the repository root:

```bash
cd examples/demo_agent_run
git init
git add .
git commit -m "init demo"
traceforge init
traceforge run --live -- python test_buggy_math.py
traceforge run --live -- python agent_fix.py
traceforge run --live -- python test_buggy_math.py
traceforge dashboard
```

Then compare the failing and passing test runs in the dashboard.
