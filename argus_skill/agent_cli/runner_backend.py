from __future__ import annotations

import shutil
from pathlib import Path
from typing import Literal

RunnerBackend = Literal["codex", "claude", "copilot", "opencode", "pi", "grok"]

BACKEND_CODEX: RunnerBackend = "codex"
BACKEND_CLAUDE: RunnerBackend = "claude"
BACKEND_COPILOT: RunnerBackend = "copilot"
BACKEND_OPENCODE: RunnerBackend = "opencode"
BACKEND_PI: RunnerBackend = "pi"
BACKEND_GROK: RunnerBackend = "grok"
DEFAULT_RUNNER_BACKEND: RunnerBackend = BACKEND_CODEX


def normalize_runner_backend(raw: str | None) -> RunnerBackend:
    value = str(raw or "").strip().lower()
    if value == BACKEND_CLAUDE:
        return BACKEND_CLAUDE
    if value == BACKEND_COPILOT:
        return BACKEND_COPILOT
    if value in (BACKEND_OPENCODE, "opencod"):
        return BACKEND_OPENCODE
    if value == BACKEND_PI:
        return BACKEND_PI
    if value == BACKEND_GROK:
        return BACKEND_GROK
    return BACKEND_CODEX


def default_runner_bin(backend: RunnerBackend) -> str:
    if backend == BACKEND_CLAUDE:
        return "claude"
    if backend == BACKEND_COPILOT:
        return "copilot"
    if backend == BACKEND_OPENCODE:
        return "opencode"
    if backend == BACKEND_PI:
        return "pi"
    if backend == BACKEND_GROK:
        return "grok"
    return "codex"


def _resolve_explicit_candidate(candidate: Path) -> str | None:
    return shutil.which(str(candidate))


def resolve_runner_bin(
    backend: RunnerBackend | str | None,
    configured: str | None = None,
) -> str | None:
    """Resolve a CLI independently of service-manager PATH omissions."""
    chosen = normalize_runner_backend(backend)
    requested = str(configured or default_runner_bin(chosen)).strip()
    if not requested:
        return None
    expanded = str(Path(requested).expanduser())
    resolved = shutil.which(expanded)
    if resolved:
        return resolved
    if Path(expanded).parent != Path("."):
        return None
    if chosen == BACKEND_OPENCODE:
        opencode_home = Path.home() / ".opencode" / "bin" / expanded
        resolved = _resolve_explicit_candidate(opencode_home)
        if resolved:
            return resolved
    user_local = Path.home() / ".local" / "bin" / expanded
    resolved = _resolve_explicit_candidate(user_local)
    if resolved:
        return resolved
    return None


def resolve_available_runner(
    backend: RunnerBackend | str | None,
    configured: str | None = None,
) -> tuple[RunnerBackend, str]:
    """Resolve the requested CLI, falling back only when Codex is absent."""
    raw = str(backend or "").strip().lower()
    chosen = normalize_runner_backend(backend)
    resolved = resolve_runner_bin(chosen, configured)
    if resolved:
        return chosen, resolved
    if chosen == BACKEND_CODEX and raw in ("", BACKEND_CODEX):
        copilot = resolve_runner_bin(BACKEND_COPILOT)
        if copilot:
            return BACKEND_COPILOT, copilot
    return chosen, str(configured or default_runner_bin(chosen)).strip()
