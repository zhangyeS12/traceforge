# Release checklist

Before publishing a TraceForge release:

```bash
traceforge release-check
traceforge selftest
```

Then validate the zip package:

```bash
traceforge release-check --zip traceforge_v1_0_rc1.zip
```

Recommended release steps:

1. Update `pyproject.toml`.
2. Update `traceforge/__init__.py`.
3. Update README badge.
4. Update CHANGELOG.
5. Run release-check and selftest.
6. Create a Git tag.
7. Create a GitHub Release.
8. Confirm GitHub Actions is green.

Current release candidate tag suggestion:

```text
v1.0.0-rc1
```
