# GitHub Readiness Checklist

Use this checklist before publishing TraceForge or preparing a public demo.

## Required checks

```bash
traceforge release-check
traceforge version-check
traceforge selftest
```

For a zip artifact:

```bash
traceforge release-check --zip traceforge_v1_3_1.zip
```

## Repository page

- README has a clear one-line pitch.
- README includes a 30-second demo.
- README includes Quick Start.
- README explains local-first privacy.
- README includes CLI reference.
- README includes dashboard workflow.
- README includes roadmap.
- README includes a resume-ready project description.
- LICENSE exists.
- CONTRIBUTING.md exists.
- CHANGELOG.md is updated.
- CI workflow exists.
- `.traceforge/` is ignored.
- `.gitattributes` normalizes line endings.

## Demo assets

- Create a clean demo run using `docs/demo-script.md`.
- Add a dashboard screenshot to `docs/assets/dashboard.png`.
- Add a GIF showing dashboard command execution to `docs/assets/demo.gif`.

## Commit hygiene

Before pushing:

```bash
git status
```

The working tree should be clean.

Avoid committing:

- `.traceforge/`
- temporary run outputs
- local virtual environments
- caches
- machine-specific files
