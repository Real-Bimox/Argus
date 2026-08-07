"""Two axes that were doing one field's work.

``research_target_level`` describes what finishing the *project* means:
exploratory, publishable, doctoral. It is also injected into the Planner and
Reviewer prompts every round, where it reads as the bar for *this* round. A
project aiming at a publishable paper therefore gets every early probe judged
against publication readiness, and ideas die before they are formed — not
because the evidence was bad, but because a seed experiment is not a paper.

Separating the two axes fixes that without loosening anything:

``ExplorationPosture``
    How much budget to spend on non-obvious, high-risk, high-upside routes.
    ``conservative`` | ``balanced`` | ``frontier``.

``VerificationProfile``
    What evidence the *current* mission needs to be complete.
    ``explore`` | ``develop`` | ``certify``, or ``adaptive`` to derive it from
    the stage.

A bolder posture must never mean a laxer conclusion, and a lighter profile must
never mean weaker facts. What a profile changes is *what has to be delivered*,
never *whether the evidence is real* — that floor is enforced in code by
:mod:`argus_skill.core.integrity_gate` and
:mod:`argus_skill.core.evidence_status`, not by prose a relaxed profile could
argue with.

Resolution order is deliberate and fail-visible:

1. A final-submission scope forces ``certify``. Nothing overrides this.
2. An explicit operator profile wins over the stage default.
3. ``adaptive`` maps the current stage to a profile.
4. Anything unresolved says so, rather than silently picking the strictest or
   the loosest reading.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "DEFAULT_POSTURE",
    "DEFAULT_PROFILE",
    "EXPLORATION_POSTURES",
    "PROFILE_ORDER",
    "STAGE_PROFILES",
    "VERIFICATION_PROFILES",
    "EffectivePolicy",
    "lowers_the_bar",
    "normalize_posture",
    "normalize_profile",
    "policy_line",
    "profile_for_stage",
    "resolve_policy",
    "stored_policy",
]

EXPLORATION_POSTURES = ("conservative", "balanced", "frontier")
VERIFICATION_PROFILES = ("explore", "develop", "certify")
#: What an operator may configure; ``adaptive`` derives from the stage.
CONFIGURABLE_PROFILES = VERIFICATION_PROFILES + ("adaptive",)

DEFAULT_POSTURE = "balanced"
DEFAULT_PROFILE = "adaptive"

#: Increasing strictness. Used to detect when a change lowers the bar.
PROFILE_ORDER = {"explore": 0, "develop": 1, "certify": 2}

#: Stage → profile, per vertical. Early stages ask whether the direction is
#: real; middle stages ask whether the implementation and comparison hold; the
#: last stages certify the claim.
STAGE_PROFILES: dict[str, dict[str, str]] = {
    "research": {
        "research": "explore",
        "plan": "explore",
        "benchmark": "develop",
        "run": "develop",
        "analysis": "develop",
        "draft": "develop",
        "review": "certify",
        "submission": "certify",
    },
    "kernel_engineering": {
        "scope": "explore",
        "environment": "explore",
        "baseline": "develop",
        "optimize": "develop",
        "validate": "certify",
        "report": "certify",
    },
}

#: One line per profile, for the prompt. Deliberately terse: the reviewer
#: prompt has a hard character budget, and a rule the code enforces does not
#: need to be restated in prose.
_PROFILE_MEANING = {
    "explore": "is the premise real, testable, and worth the next probe",
    "develop": "does the implementation, comparison, and claim scope hold",
    "certify": "full claim coverage, venue compliance, submission-ready",
}

_STATE_RELPATH = ("research", "PIPELINE_STATE.json")
_FINAL_SCOPES = frozenset({"final_submission"})


def normalize_posture(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    return text if text in EXPLORATION_POSTURES else None


def normalize_profile(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    return text if text in CONFIGURABLE_PROFILES else None


def profile_for_stage(stage: Any, vertical: Any = None) -> str | None:
    """Map a stage to its default profile, or ``None`` when unknown."""
    stage_text = str(stage or "").strip().lower()
    if not stage_text:
        return None
    vertical_text = str(vertical or "").strip().lower()
    table = STAGE_PROFILES.get(vertical_text)
    if table is None:
        # Stage names are near-unique across verticals; fall back to any table
        # that defines this stage rather than refusing to resolve.
        for candidate in STAGE_PROFILES.values():
            if stage_text in candidate:
                return candidate[stage_text]
        return None
    return table.get(stage_text)


def lowers_the_bar(current: str, proposed: str) -> bool:
    """Whether moving to *proposed* weakens what completion requires.

    Lowering the bar changes what "done" means for the project, so it belongs
    to the operator. Raising it does not need permission.
    """
    left = PROFILE_ORDER.get(current)
    right = PROFILE_ORDER.get(proposed)
    if left is None or right is None:
        return False
    return right < left


@dataclass(frozen=True)
class EffectivePolicy:
    """The resolved policy plus where each part came from."""

    posture: str
    profile: str
    configured_profile: str
    source: str
    stage: str | None = None
    vertical: str | None = None
    target_level: str | None = None
    resolved: bool = True
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "posture": self.posture,
            "profile": self.profile,
            "configured_profile": self.configured_profile,
            "source": self.source,
            "stage": self.stage,
            "vertical": self.vertical,
            "target_level": self.target_level,
            "resolved": self.resolved,
            "note": self.note,
        }


def stored_policy(project_root: object) -> dict[str, Any]:
    """Read the Manager-owned policy fields. Missing file → empty."""
    path = Path(str(project_root)).joinpath(*_STATE_RELPATH)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {
        "exploration_posture": normalize_posture(payload.get("exploration_posture")),
        "verification_profile": normalize_profile(payload.get("verification_profile")),
    }


def resolve_policy(
    project_root: object,
    *,
    scope: Any = None,
    stage: Any = None,
    vertical: Any = None,
    target_level: Any = None,
) -> EffectivePolicy:
    """Resolve the policy in force for the current mission."""
    stored = stored_policy(project_root)
    posture = stored.get("exploration_posture") or DEFAULT_POSTURE
    configured = stored.get("verification_profile") or DEFAULT_PROFILE
    stage_text = str(stage or "").strip().lower() or None
    vertical_text = str(vertical or "").strip().lower() or None
    target_text = str(target_level or "").strip().lower() or None

    common = {
        "posture": posture,
        "configured_profile": configured,
        "stage": stage_text,
        "vertical": vertical_text,
        "target_level": target_text,
    }

    # 1. A final submission is certified regardless of anything else. Bolder
    #    exploration earlier never buys a laxer final claim.
    if str(scope or "").strip().lower() in _FINAL_SCOPES:
        return EffectivePolicy(profile="certify", source="final_scope", **common)

    # 2. An explicit operator choice.
    if configured in VERIFICATION_PROFILES:
        return EffectivePolicy(profile=configured, source="operator", **common)

    # 3. adaptive → stage.
    mapped = profile_for_stage(stage_text, vertical_text)
    if mapped is not None:
        return EffectivePolicy(profile=mapped, source="stage", **common)

    # 4. Unresolved. Say so instead of silently choosing; a silent strictest
    #    reading is the mis-kill this module exists to remove, and a silent
    #    loosest one would weaken certification.
    return EffectivePolicy(
        profile="develop",
        source="unresolved",
        resolved=False,
        note=(
            f"no profile for stage={stage_text!r} vertical={vertical_text!r}; "
            "using develop and reporting it unresolved"
        ),
        **common,
    )


def policy_line(policy: EffectivePolicy) -> str:
    """One-line policy statement for a role prompt.

    Kept short on purpose: the reviewer prompt is budgeted, and the integrity
    rules this line refers to are enforced in code.
    """
    meaning = _PROFILE_MEANING.get(policy.profile, "")
    suffix = " (unresolved)" if not policy.resolved else ""
    return f"`{policy.profile}`{suffix} — {meaning}" if meaning else f"`{policy.profile}`{suffix}"


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

class PolicyConfirmationRequired(RuntimeError):
    """Raised when a change would weaken completion without operator consent."""


def set_policy(
    project_root: object,
    *,
    posture: Any = None,
    profile: Any = None,
    confirmed: bool = False,
    stage: Any = None,
    vertical: Any = None,
) -> EffectivePolicy:
    """Persist policy changes into the Manager-owned pipeline state.

    Raising the bar applies immediately. Lowering it changes what "done" means
    for the project, so it needs the operator to say so — an Engineer or
    Reviewer must not be able to make its own completion easier.
    """
    root = Path(str(project_root))
    path = root.joinpath(*_STATE_RELPATH)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    if profile is not None:
        new_profile = normalize_profile(profile)
        if new_profile is None:
            raise ValueError(
                f"unknown verification profile {profile!r}; "
                f"expected one of {', '.join(CONFIGURABLE_PROFILES)}"
            )
        before = resolve_policy(root, stage=stage, vertical=vertical)
        after_effective = (
            new_profile
            if new_profile in VERIFICATION_PROFILES
            else (profile_for_stage(stage, vertical) or before.profile)
        )
        if not confirmed and lowers_the_bar(before.profile, after_effective):
            raise PolicyConfirmationRequired(
                f"moving verification from {before.profile!r} to {after_effective!r} "
                "lowers what project completion requires; this is an operator "
                "decision — re-issue with confirmation"
            )
        payload["verification_profile"] = new_profile

    if posture is not None:
        new_posture = normalize_posture(posture)
        if new_posture is None:
            raise ValueError(
                f"unknown exploration posture {posture!r}; "
                f"expected one of {', '.join(EXPLORATION_POSTURES)}"
            )
        payload["exploration_posture"] = new_posture

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return resolve_policy(root, stage=stage, vertical=vertical)
