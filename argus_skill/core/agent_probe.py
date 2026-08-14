"""Read-only Agent CLI probe shared by setup and Doctor."""
from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentProbeResult:
    backend: str
    executable: str
    ok: bool
    output: str = ""
    error: str = ""


def run_read_only_agent_prompt(
    *,
    backend: str,
    executable: str,
    prompt: str,
    model: str = "",
    run_label: str,
    disable_tools: bool = False,
) -> AgentProbeResult:
    """Run one real, tool-restricted Agent CLI turn."""
    from ..adapters.agent_cli_backend import AgentCliBackend
    from ..agent_cli.runner_backend import normalize_runner_backend
    from .models import RunnerOptions
    from .run_gateway import run_exec

    if disable_tools and normalize_runner_backend(backend) == "codex":
        return AgentProbeResult(
            backend=backend,
            executable=executable,
            ok=False,
            error=(
                "Codex CLI does not expose a tool-free prompt mode; "
                "choose another Doctor advisor"
            ),
        )
    try:
        with tempfile.TemporaryDirectory(prefix="argus-agent-probe-") as workdir:
            runner = AgentCliBackend(
                backend=backend,
                runner_bin=executable,
                default_watchdog_soft_idle_seconds=15,
                default_watchdog_stalled_idle_seconds=45,
                default_watchdog_hard_idle_seconds=90,
            )
            result = run_exec(
                runner,
                prompt=prompt,
                resume_thread_id=None,
                options=RunnerOptions(
                    model=model or None,
                    working_dir=workdir,
                    sandbox_mode="read-only",
                    force_safe_mode=True,
                    disable_tools=disable_tools,
                    skip_git_repo_check=True,
                ),
                run_label=run_label,
            )
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        return AgentProbeResult(
            backend=backend,
            executable=executable,
            ok=False,
            error=f"{type(exc).__name__}: {exc}",
        )

    output = str(getattr(result, "last_agent_message", "") or "").strip()
    if not output:
        messages = list(getattr(result, "agent_messages", None) or ())
        output = next(
            (str(message).strip() for message in reversed(messages) if str(message).strip()),
            "",
        )
    exit_code = int(getattr(result, "exit_code", 1) or 0)
    fatal_error = str(getattr(result, "fatal_error", "") or "").strip()
    turn_completed = getattr(result, "turn_completed", None)
    completion_ok = (
        bool(turn_completed)
        if turn_completed is not None
        else exit_code == 0 and not fatal_error
    )
    ok = (
        exit_code == 0
        and completion_ok
        and bool(output)
        and not bool(getattr(result, "tool_activity_observed", False))
    )
    error = ""
    if not ok:
        if bool(getattr(result, "tool_activity_observed", False)):
            error = "Agent used a tool during the tool-free verification turn"
        else:
            error = fatal_error
        if not error:
            stderr = list(getattr(result, "stderr_lines", None) or ())
            error = str(stderr[-1]).strip() if stderr else ""
        if not error:
            error = (
                f"Agent CLI exited {getattr(result, 'exit_code', 'unknown')} "
                "without a completed assistant reply"
            )
    return AgentProbeResult(
        backend=backend,
        executable=executable,
        ok=ok,
        output=output,
        error=error,
    )


__all__ = ["AgentProbeResult", "run_read_only_agent_prompt"]
