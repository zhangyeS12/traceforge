# Release checklist

Before publishing a TraceForge release, validate every version surface and the runtime behavior:

```bash
traceforge version-check
traceforge release-check
traceforge selftest
```

Then validate the zip package:

```bash
traceforge release-check --zip traceforge_v1_3_2.zip
```

Recommended release steps:

1. Update `pyproject.toml`.
2. Update `traceforge/__init__.py`.
3. Update the README version badge.
4. Update the top CHANGELOG heading.
5. Run `traceforge version-check`, `traceforge release-check`, and `traceforge selftest`.
6. Commit and push.
7. Confirm GitHub Actions is green on `main`.
8. Create and push the Git tag.
9. Confirm the `Publish` workflow created the PyPI release and GitHub Release.

Python package versions use PEP 440 spelling, for example:

```text
1.3.2
```

Git tags and human-facing docs use release spelling:

```text
v1.3.2
```

Current stable release tag suggestion:

```text
v1.3.2
```
