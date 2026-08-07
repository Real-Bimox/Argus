"""Framework-owned interface implemented by every vertical.

Core defines the contract but never imports a concrete vertical.  The vertical
loader resolves a provider and converts it once; consumers use this immutable
view instead of probing module attributes or branching on vertical names.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

VERTICAL_CONTRACT_VERSION = 1
_COMPLETION_GATES = frozenset({"none", "metric", "certified"})
_WORKFLOW_MODES = frozenset({"staged", "direct", "proportional"})


class VerticalContractError(ValueError):
    """A vertical is present but does not implement the framework contract."""


@dataclass(frozen=True)
class VerticalContract:
    name: str
    stage_order: tuple[str, ...]
    checklist_items: dict[str, Any]
    completion_gate: str
    role_guidance: Callable[[str], str] | None = None
    evidence_schema: Any = None
    requires_independent_review: bool = False
    completion_contract_version: int = 0
    research_target_levels: tuple[str, ...] = ()
    workflow_mode: str = "staged"
    checklist_optional_stages: frozenset[str] = frozenset()
    stage_aliases: dict[str, str] | None = None
    search_altitude: Callable[[object], str] | None = None
    mission_prelude: Callable[[str, Path, Path], str] | None = None

    def banner(self, role: str) -> str:
        if self.role_guidance is None:
            return ""
        value = self.role_guidance(role)
        return value if isinstance(value, str) else ""

    def altitude(self, project_root: object) -> str:
        if self.search_altitude is None:
            return ""
        value = self.search_altitude(project_root)
        return value if isinstance(value, str) else ""

    def prepare_mission(
        self,
        *,
        stage: str,
        project_root: Path,
        state_root: Path,
    ) -> str:
        if self.mission_prelude is None:
            return ""
        value = self.mission_prelude(stage, project_root, state_root)
        return value if isinstance(value, str) else ""


def vertical_contract(name: str, provider: Any) -> VerticalContract:
    """Validate one provider and return its immutable framework view."""
    stage_order = tuple(
        str(stage).strip()
        for stage in (getattr(provider, "CHECKLIST_STAGE_ORDER", ()) or ())
        if str(stage).strip()
    )
    checklist_items = getattr(provider, "CHECKLIST_ITEMS", None)
    gate = str(getattr(provider, "completion_gate", "") or "").strip().lower()
    if not stage_order:
        raise VerticalContractError(f"vertical {name!r} declares no stage order")
    if not isinstance(checklist_items, dict):
        raise VerticalContractError(f"vertical {name!r} declares no checklist items")
    if gate not in _COMPLETION_GATES:
        raise VerticalContractError(
            f"vertical {name!r} has unsupported completion gate {gate!r}"
        )
    optional_stages = frozenset(
        str(stage).strip().lower()
        for stage in (getattr(provider, "CHECKLIST_OPTIONAL_STAGES", ()) or ())
        if str(stage).strip()
    )
    missing = [
        stage
        for stage in stage_order
        if stage not in checklist_items and stage not in optional_stages
    ]
    if missing:
        raise VerticalContractError(
            f"vertical {name!r} has no checklist for: {', '.join(missing)}"
        )
    mode = str(getattr(provider, "WORKFLOW_MODE", "staged") or "staged").strip().lower()
    if mode not in _WORKFLOW_MODES:
        raise VerticalContractError(
            f"vertical {name!r} has unsupported workflow mode {mode!r}"
        )
    aliases = getattr(provider, "STAGE_ALIASES", {})
    aliases = {
        str(source).strip().lower(): str(target).strip().lower()
        for source, target in aliases.items()
        if str(source).strip() and str(target).strip()
    } if isinstance(aliases, dict) else {}
    return VerticalContract(
        name=str(name or "").strip().lower(),
        stage_order=stage_order,
        checklist_items=checklist_items,
        completion_gate=gate,
        role_guidance=(
            getattr(provider, "role_banner")
            if callable(getattr(provider, "role_banner", None))
            else None
        ),
        evidence_schema=getattr(provider, "EVIDENCE_SCHEMA", None),
        requires_independent_review=bool(
            getattr(provider, "REQUIRE_INDEPENDENT_REVIEW", False)
        ),
        completion_contract_version=max(
            0, int(getattr(provider, "COMPLETION_CONTRACT_VERSION", 0) or 0)
        ),
        research_target_levels=tuple(
            str(level).strip().lower()
            for level in (getattr(provider, "RESEARCH_TARGET_LEVELS", ()) or ())
            if str(level).strip()
        ),
        workflow_mode=mode,
        checklist_optional_stages=optional_stages,
        stage_aliases=aliases,
        search_altitude=(
            getattr(provider, "search_altitude_context")
            if callable(getattr(provider, "search_altitude_context", None))
            else None
        ),
        mission_prelude=(
            getattr(provider, "prepare_mission")
            if callable(getattr(provider, "prepare_mission", None))
            else None
        ),
    )


__all__ = [
    "VERTICAL_CONTRACT_VERSION",
    "VerticalContract",
    "VerticalContractError",
    "vertical_contract",
]
