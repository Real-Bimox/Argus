"""Code-Agent interpretation of sanitized Doctor findings."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import DoctorReport

_SUPPORTED_ADVISORS = (
    "copilot",
    "codex",
    "claude",
    "opencode",
    "pi",
    "grok",
)


def _resolve_advisor(requested: str) -> tuple[str, str] | None:
    from ..agent_cli.runner_backend import (
        normalize_runner_backend,
        resolve_runner_bin,
    )
    from ..core.knobs import resolve_role_backend, resolve_runner_bin_setting

    normalized = str(requested or "auto").strip().lower()
    if normalized == "none":
        return None
    if normalized != "auto" and normalized not in _SUPPORTED_ADVISORS:
        raise ValueError(f"unsupported Doctor advisor: {requested}")
    configured = normalize_runner_backend(resolve_role_backend("manager"))
    candidates = (
        (normalized,)
        if normalized != "auto"
        else tuple(
            item
            for item in (
                configured,
                *[candidate for candidate in _SUPPORTED_ADVISORS if candidate != configured],
            )
            if item != "codex"
        )
    )
    configured_bin = resolve_runner_bin_setting("manager")
    for backend in candidates:
        executable = resolve_runner_bin(
            backend,
            configured_bin if backend == configured else None,
        )
        if executable:
            return backend, executable
    return None


def _advisor_prompt(report: DoctorReport) -> str:
    from ..core.paths import global_root
    from ..core.secret_guard import known_secret_values, redact_secrets_text

    findings = [
        {
            "code": item.code,
            "scope": item.scope,
            "severity": item.severity,
            "ok": item.ok,
            "status": item.status,
            "detail": item.detail,
            "recommendation": item.recommendation,
        }
        for item in report.findings
    ]
    payload = json.dumps(findings, ensure_ascii=False, indent=2)
    private_roots = (
        (str(global_root()), "<ARGUS_SKILL_HOME>"),
        (str(Path.home()), "~"),
    )
    for root, replacement in sorted(private_roots, key=lambda item: len(item[0]), reverse=True):
        if root and root != "/":
            payload = payload.replace(root, replacement)
    payload = redact_secrets_text(payload, known_values=known_secret_values())
    return (
        "You are the read-only Argus Doctor advisor. Analyze only the sanitized "
        "deterministic findings below. Do not use tools, modify files, inspect "
        "credentials, or invent missing facts. Give: (1) root cause in plain "
        "language, (2) the smallest exact commands/checks to run next for this OS, "
        "(3) what success looks like. Distinguish blocking errors from optional "
        "components. Keep the answer concise.\n\n"
        f"FINDINGS:\n{payload}"
    )


def run_doctor_advisor(
    report: DoctorReport,
    *,
    requested: str = "auto",
) -> dict[str, Any]:
    """Ask an installed Code Agent to interpret deterministic Doctor evidence."""
    selection = _resolve_advisor(requested)
    if selection is None:
        status = "disabled" if str(requested).strip().lower() == "none" else "unavailable"
        return {
            "status": status,
            "backend": "",
            "executable": "",
            "analysis": "",
            "error": (
                ""
                if status == "disabled"
                else "no supported Agent CLI was found on PATH"
            ),
        }
    backend, executable = selection
    from ..core.agent_probe import run_read_only_agent_prompt
    from ..core.knobs import resolve_role_model

    probe = run_read_only_agent_prompt(
        backend=backend,
        executable=executable,
        model=resolve_role_model(
            "manager",
            role_env="ARGUS_SKILL_MANAGER_MODEL",
            backend=backend,
        ),
        run_label="doctor-advisor",
        prompt=_advisor_prompt(report),
        disable_tools=True,
    )
    return {
        "status": "completed" if probe.ok else "failed",
        "backend": backend,
        "executable": executable,
        "analysis": probe.output if probe.ok else "",
        "error": probe.error if not probe.ok else "",
    }


__all__ = ["run_doctor_advisor"]
