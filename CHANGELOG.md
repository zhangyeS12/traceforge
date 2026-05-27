# Changelog

## 0.6.0

- Reworked README into a GitHub-ready project landing page with clearer positioning, Quick Start, dashboard workflow, architecture, roadmap, and resume description.
- Added `docs/demo-script.md` for creating clean dashboard screenshots and demos.
- Added `docs/github-readiness.md` as a pre-publish checklist.
- Added `docs/assets/` placeholder directory for README images and demo GIFs.
- Updated package version to 0.6.0.


## 0.5.0

- Added `traceforge selftest`, an end-to-end smoke test that creates a temporary Git project, records a command, verifies Git diff capture, generates an HTML report, and exports JSON.
- Added `traceforge release-check` for validating local source trees and release zip layout before publishing.
- Added JSON output for selftest and release-check so CI can consume results.
- Added CI workflow that runs release-check and selftest on push and pull requests.

## 0.4.2

- Fixed dashboard command runner startup failures on Windows by normalizing subprocess argv, cwd, and environment values before calling `subprocess.Popen`.
- Dashboard API now returns a clean validation error instead of a raw traceback when command startup fails.

## 0.4.1

- Fixed release archive layout so extracting to `C:\Projects` correctly updates `C:\Projects\traceforge`.

# Changelog

## 0.4.0

- Added browser-driven command execution from the local dashboard.
- Added `POST /api/runs` for creating recorded runs through the local HTTP API.
- Added a dashboard command runner with optional shell mode, loading state, and automatic run selection after completion.
- Improved dashboard error reporting for invalid, blocked, or missing commands.

## 0.3.2

- Fixed dashboard JavaScript rendering bug caused by an incorrectly escaped diff line splitter.
- Added HTTP error handling for dashboard run loading.
- Removed duplicate run metadata row in the run list.


## 0.3.1

Dashboard polish release.

- Added top-level summary cards for total runs, success rate, failed runs, changed files, risky runs, and average duration.
- Added run filters: All, Success, Failed, Changed, Risky.
- Improved patch display with diff-style highlighting for additions, deletions, file headers, and hunks.
- Improved timeline styling and empty states.
- Added copy button for currently selected artifact.

## 0.3.0

- Added `traceforge dashboard` / `traceforge ui` for a local browser dashboard.
- Added a standard-library local HTTP server for dashboard APIs.
- Added `/api/runs`, `/api/runs/<run_id>`, and `/api/health` endpoints.
- Dashboard now shows run list, metrics, command, artifacts, changed files, timeline, security notes, and full JSON view.


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
