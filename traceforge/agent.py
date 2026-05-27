from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from .storage import load_config, paths_for


@dataclass(frozen=True)
class AgentAdapter:
    """A small command template for a coding-agent CLI.

    TraceForge intentionally keeps adapters thin: the adapter only turns a task
    or command into a local process invocation. The existing recorder still owns
    stdout/stderr capture, Git diff capture, timeline events, compare, and risk.
    """

    name: str
    executable: str | None
    description: str
    prompt_mode: str
    example: str


@dataclass(frozen=True)
class AgentCommand:
    adapter: str
    command: str | list[str]
    shell: bool
    prompt: str
    executable: str | None
    available: bool
    note: str


BUILTIN_ADAPTERS: dict[str, AgentAdapter] = {
    "shell": AgentAdapter(
        name="shell",
        executable=None,
        description="Passthrough adapter for any local command; useful for testing TraceForge agent flows.",
        prompt_mode="argv",
        example="traceforge agent run shell -- python modify_hello.py",
    ),
    "codex": AgentAdapter(
        name="codex",
        executable="codex",
        description="Generic Codex CLI wrapper. The prompt is passed as one task argument.",
        prompt_mode="prompt-arg",
        example='traceforge agent run codex -- "fix the failing tests"',
    ),
    "claude": AgentAdapter(
        name="claude",
        executable="claude",
        description="Generic Claude Code CLI wrapper. The prompt is passed as one task argument.",
        prompt_mode="prompt-arg",
        example='traceforge agent run claude -- "refactor this module"',
    ),
    "aider": AgentAdapter(
        name="aider",
        executable="aider",
        description="Aider wrapper using --message for non-interactive task prompts.",
        prompt_mode="aider-message",
        example='traceforge agent run aider -- "fix the bug in parser.py"',
    ),
    "opencode": AgentAdapter(
        name="opencode",
        executable="opencode",
        description="Generic opencode CLI wrapper. The prompt is passed as one task argument.",
        prompt_mode="prompt-arg",
        example='traceforge agent run opencode -- "add unit tests"',
    ),
}


def list_agent_adapters() -> list[dict[str, Any]]:
    rows = []
    for adapter in BUILTIN_ADAPTERS.values():
        exe = adapter.executable
        found = shutil.which(exe) if exe else None
        rows.append({
            "name": adapter.name,
            "executable": exe,
            "available": True if exe is None else bool(found),
            "path": found,
            "description": adapter.description,
            "example": adapter.example,
        })
    return rows


def load_agent_config() -> dict[str, Any]:
    """Load optional adapter overrides from .traceforge/config.json.

    Expected optional shape:
    {
      "agents": {
        "my-agent": {"command": ["my-agent", "--task", "{prompt}"]}
      }
    }
    """
    try:
        return load_config(paths_for()).get("agents", {})
    except Exception:
        return {}


def build_agent_command(adapter_name: str, args: Sequence[str], *, shell: bool = False) -> AgentCommand:
    name = adapter_name.strip().lower()
    values = [str(a) for a in args if a is not None]
    if values and values[0] == "--":
        values = values[1:]
    if not values:
        raise ValueError("agent run requires a prompt or command after --")

    custom = load_agent_config().get(name)
    if custom:
        prompt = " ".join(values)
        template = custom.get("command")
        if isinstance(template, list):
            command = [str(part).replace("{prompt}", prompt) for part in template]
            executable = command[0] if command else None
            available = bool(executable and shutil.which(executable))
            return AgentCommand(name, command, shell=False, prompt=prompt, executable=executable, available=available, note="custom adapter from config.json")
        if isinstance(template, str):
            command = template.replace("{prompt}", prompt)
            return AgentCommand(name, command, shell=True, prompt=prompt, executable=None, available=True, note="custom shell adapter from config.json")
        raise ValueError(f"custom adapter {name!r} must define command as string or list")

    if name not in BUILTIN_ADAPTERS:
        available = ", ".join(sorted(BUILTIN_ADAPTERS))
        raise ValueError(f"unknown agent adapter {adapter_name!r}; available: {available}")

    adapter = BUILTIN_ADAPTERS[name]
    if name == "shell":
        if shell:
            command: str | list[str] = " ".join(values)
        else:
            command = values
        return AgentCommand(
            adapter=name,
            command=command,
            shell=shell,
            prompt=" ".join(values),
            executable=values[0] if values else None,
            available=True,
            note="passthrough shell adapter",
        )

    prompt = " ".join(values)
    executable = adapter.executable or name
    found = shutil.which(executable)
    if adapter.prompt_mode == "aider-message":
        command = [executable, "--message", prompt]
    else:
        command = [executable, prompt]
    return AgentCommand(
        adapter=name,
        command=command,
        shell=False,
        prompt=prompt,
        executable=executable,
        available=bool(found),
        note="builtin adapter",
    )


def agent_metadata(agent_command: AgentCommand) -> dict[str, Any]:
    command = agent_command.command
    return {
        "adapter": agent_command.adapter,
        "prompt": agent_command.prompt,
        "executable": agent_command.executable,
        "available": agent_command.available,
        "shell": agent_command.shell,
        "note": agent_command.note,
        "command": command if isinstance(command, str) else list(command),
    }


def adapters_json() -> str:
    return json.dumps({"adapters": list_agent_adapters()}, indent=2, ensure_ascii=False)
