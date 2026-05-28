# Changelog

## 1.2.1

- Fixed run-attributed patch rendering for tracked files that become binary, too large, or otherwise non-text during a run.
- Added coverage to ensure non-text tracked modifications are not misreported as deleted files.
- Closed SQLite connections when using `with connect(...)` to avoid ResourceWarning noise in tests and long-running sessions.

## 1.2.0

- Added run-attributed change detection so pre-existing unchanged dirty files are no longer counted as files changed by the current run.
- Added patch capture for untracked new file contents.
- Added focused unittest coverage for dirty-worktree attribution and untracked file patch generation.
- Fixed README version-guard formatting, updated supported versions, refreshed release-check examples, and removed duplicate package keywords.

## 1.1.1

- Added `traceforge reindex` to rebuild the SQLite run index from existing `.traceforge/runs` artifacts and reports.
- Added release packaging guardrails to keep local run data out of release archives.


## 1.1.0

- Added the first agent adapter layer with `traceforge agent list`, `traceforge agent doctor`, and `traceforge agent run <adapter>`.
- Added built-in adapters for `shell`, `codex`, `claude`, `aider`, and `opencode`.
- Added `agent.adapter.selected` timeline events so agent runs are identifiable in replay.
- Added profile pinning and demo GIF documentation to improve public project presentation.

## 1.0.0

- Promoted TraceForge to its first stable public release.
- Finalized the local-first black-box recorder workflow for command runs and AI coding agents.
- Includes dashboard replay, timeline events, run comparison, security risk reports, JSON export, HTML reports, selftest, release-check, and version-check.
- Stabilized public documentation, security policy, issue templates, demo examples, and release metadata validation.

## 1.0.0-rc2

- Added stronger version consistency checks for release workflows.
- `release-check` now validates `pyproject.toml`, `traceforge/__init__.py`, the README version badge, and the top CHANGELOG version together.
- Added `traceforge version-check` as a quick pre-push guard for version metadata.

## 1.0.0-rc1

- Promoted TraceForge to a public release candidate.
- Added SECURITY.md with reporting guidance and current security model.
- Added GitHub issue templates for bugs, feature requests, and agent adapter requests.
- Added installation, release, and demo-agent-run documentation.
- Added an example demo agent run scenario under `examples/demo_agent_run/`.
- Extended release-check to validate public-readiness files and GitHub issue templates.

## 0.9.1

- Added `traceforge risk <run_id>` with JSON output.
- Added security risk reports for risky commands, sensitive-looking files, dependency files, CI workflow files, broad changes, and possible secret material in patches.
- Dashboard run detail now includes a Risk Report section.
- Run recording now stores enhanced low/medium/high risk levels.
- Selftest and release-check now cover the new risk module.

## 0.8.0

- Added `traceforge compare <run_a> <run_b>` for comparing two recorded runs.
- Kept `traceforge diff <run_a> <run_b>` as a compatibility alias for compare.
- Added machine-readable compare output with `--json`.
- Added a dashboard Compare Runs panel with run selectors, outcome deltas, patch-size deltas, event-count deltas, and file overlap buckets.
- Added `traceforge/compare.py` as shared comparison logic for CLI and dashboard APIs.
- Updated `selftest` to verify compare payload generation.
- Updated `release-check` to validate compare module presence.
- Updated package version to 0.8.0.

## 0.7.1

- Moved `report.generated` before `run.finished` so a run timeline now ends only after replay artifacts are ready.
- `traceforge run` and dashboard-created runs now rely on the same core report-generation path, avoiding duplicate timeline events.
- Dashboard now places the Timeline section above Artifacts so the replay view is visible first.
- `selftest` now verifies that report generation happens before run completion in the timeline.
- Updated package version to 0.7.1.

## 0.7.0

- Added fine-grained run timeline events: command start, security check, Git snapshots, stdout/stderr chunks, process exit, artifact writes, Git diff capture, file changes, report generation, and JSON export.
- Added `traceforge timeline <run_id>` for inspecting replay events from the CLI.
- Dashboard now displays event counts, richer timeline rows, event kind badges, offsets, and data previews.
- Dashboard run list now includes event counts for each run.
- `selftest` now verifies stdout chunk, file change, and Git diff capture timeline events.
- Updated package version to 0.7.0.

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
