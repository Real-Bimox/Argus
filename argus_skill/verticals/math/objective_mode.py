"""What "done" means for a mathematics project — a choice, not a default.

Two kinds of work get run through the same vertical and need opposite
completion rules:

``targeted``
    One named goal: prove this conjecture, or refute it. Everything else —
    lemmas, computations, ruled-out methods — is progress only insofar as it
    shrinks the gap to that goal. Ruling out a sufficient criterion is not
    solving the problem, and a project that drifts into perfecting such a
    refutation has stopped working on what it was asked to work on.

``exploratory``
    A direction rather than a target: find what is true near here, produce
    partial results, bounds, counterexamples, or structure worth reporting.
    There is no single G to close, so demanding one would reject genuinely
    useful work.

Guessing between them makes one of the two behave badly, so the operator
picks. An unset mode is reported rather than assumed: the two have different
completion bars, and silently choosing either is wrong in one direction.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "MATH_OBJECTIVE_MODES",
    "MODE_COMPLETION",
    "MathObjective",
    "normalize_mode",
    "resolve_objective",
    "set_objective",
]

MATH_OBJECTIVE_MODES = ("targeted", "exploratory")

#: What completion requires under each mode. Injected verbatim, so it is
#: written to be read by a reviewer deciding `done`.
MODE_COMPLETION = {
    "targeted": (
        "the named goal is proved or refuted; partial results and ruled-out "
        "methods are progress only if they shrink the gap to it"
    ),
    "exploratory": (
        "a substantive, correctly-scoped mathematical result in the stated "
        "direction; no single named goal has to close"
    ),
}

_STATE_RELPATH = ("research", "PIPELINE_STATE.json")


def normalize_mode(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    return text if text in MATH_OBJECTIVE_MODES else None


@dataclass(frozen=True)
class MathObjective:
    """The selected mode and, for ``targeted``, the goal it must close."""

    mode: str | None
    goal: str = ""
    resolved: bool = True
    note: str = ""

    @property
    def is_targeted(self) -> bool:
        return self.mode == "targeted"

    @property
    def completion_rule(self) -> str:
        return MODE_COMPLETION.get(self.mode or "", "")

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "goal": self.goal,
            "resolved": self.resolved,
            "note": self.note,
        }


def _read_state(project_root: object) -> dict[str, Any]:
    path = Path(str(project_root)).joinpath(*_STATE_RELPATH)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def resolve_objective(project_root: object) -> MathObjective:
    """Read the selected mode, or report that nobody has chosen one."""
    payload = _read_state(project_root)
    mode = normalize_mode(payload.get("math_objective_mode"))
    goal = str(payload.get("math_goal") or "").strip()
    if mode is None:
        return MathObjective(
            mode=None,
            goal=goal,
            resolved=False,
            note=(
                "no math objective mode selected; a targeted project and an "
                "exploratory one have different completion bars, so ask the "
                "operator which this is instead of assuming"
            ),
        )
    if mode == "targeted" and not goal:
        return MathObjective(
            mode=mode,
            goal="",
            resolved=False,
            note=(
                "targeted mode needs the goal it must close; without it there is "
                "nothing to measure the gap against and the project will drift "
                "into whichever subproblem is most tractable"
            ),
        )
    return MathObjective(mode=mode, goal=goal)


def set_objective(
    project_root: object, *, mode: Any, goal: str = ""
) -> MathObjective:
    """Persist the operator's choice into the Manager-owned pipeline state."""
    normalized = normalize_mode(mode)
    if normalized is None:
        raise ValueError(
            f"unknown math objective mode {mode!r}; expected one of "
            f"{', '.join(MATH_OBJECTIVE_MODES)}"
        )
    if normalized == "targeted" and not goal.strip():
        raise ValueError(
            "targeted mode requires the goal statement it must prove or refute"
        )
    root = Path(str(project_root))
    payload = _read_state(root)
    payload["math_objective_mode"] = normalized
    if goal.strip():
        payload["math_goal"] = goal.strip()
    path = root.joinpath(*_STATE_RELPATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return resolve_objective(root)
