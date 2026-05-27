# Changelog

## 0.2.1

- Fixed `traceforge doctor` crashing on Windows when optional tools such as npm are missing or launched through `.cmd` shims.
- `doctor` now reports tool execution errors as warnings instead of tracebacks.

## 0.2.0

- Added `traceforge doctor` for environment checks.
- Added `traceforge export <run_id>` for JSON run export.
- Added `traceforge clean --yes` for cleaning local run data.
- Added `traceforge version`.
- Added `traceforge run --live` to stream command output while recording.
- Changed default command execution to shellless mode to avoid Windows quoting bugs.
- Added `traceforge run --shell` for explicit shell usage.
- Improved CLI help and README.

## 0.1.0

- Initial MVP: CLI recorder, Git diff capture, SQLite storage, HTML reports, basic risk warnings.
