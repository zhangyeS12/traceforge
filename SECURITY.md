# Security Policy

TraceForge is a local-first developer tool. It records command runs and Git changes inside your project directory and stores data under `.traceforge/`.

## Supported versions

| Version | Supported |
| --- | --- |
| 1.3.x | Yes |
| 1.2.x | Yes |
| 1.1.x | Yes |
| 1.0.x | Best effort |
| 0.x | Unsupported or best effort |

## Reporting a vulnerability

Please do not publish exploit details in a public issue.

For now, open a private report if GitHub security advisories are enabled, or contact the maintainer through the repository owner profile. Include:

- operating system
- TraceForge version
- command that triggered the issue
- whether `.traceforge/` contains sensitive output
- minimal reproduction steps

## Current security model

TraceForge is not a sandbox yet. It records and audits commands, but it does not fully isolate them from your machine.

Current protections:

- risky command substring warnings
- sensitive-looking file and patch scanning
- dependency and CI workflow change detection
- local-only dashboard by default on `127.0.0.1`
- no remote upload of traces by default

Current limitations:

- commands still run with your user permissions
- dashboard command runner can execute local commands
- network access is not blocked
- file reads/writes are not yet sandboxed
- MCP/tool-call recording is not implemented yet

Recommended usage:

- run TraceForge inside a throwaway branch or test repository when evaluating unknown agents
- review risk reports before accepting patches
- do not commit `.traceforge/`
- avoid sharing traces that contain secrets, private source code, or proprietary logs
