# GitHub Readiness Checklist

Use this checklist before publishing TraceForge or preparing a public demo.

## Required checks

```bash
traceforge release-check
traceforge selftest
```

For a zip artifact:

```bash
traceforge release-check --zip traceforge_v0_6.zip
```

## Repository page

- README has a clear one-line pitch.
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
- Optional: record a GIF showing dashboard command execution.

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
