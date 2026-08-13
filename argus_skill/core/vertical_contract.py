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
_MISSION_KINDS = frozenset({"custom", "optimize", "research", "software"})


class VerticalContractError(ValueError):
    """A vertical is present but does not implement the framework contract."""


@dataclass(frozen=True)
class VerticalLibraryContext:
    """Core-owned inputs for optional provider-owned Skill preparation."""

    workdir: Path
    stage: str
    objective: str
    direction: str
    workflow_mode: str
    paper_mission: bool
    runner: Any
    model: str | None
    emit: Callable[[dict], None]


@dataclass(frozen=True)
class VerticalContract:
    name: str
    stage_order: tuple[str, ...]
    checklist_items: dict[str, Any]
    completion_gate: str
    mission_kind: str = "custom"
    ground_before_handoff: bool = False
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
    library_preparer: Callable[[VerticalLibraryContext], None] | None = None
    stage_completion_validator: Callable[[str, Path], object] | None = None
    planner_task_validator: Callable[[str, Path, Any], object] | None = None
    stage_checks: dict[str, tuple[tuple[str, str], ...]] | None = None
    stage_primary_deliverables: dict[str, tuple[str, ...]] | None = None
    # Stages whose Engineer round runs with live web search enabled. ``None``
    # means "this vertical declares nothing", which is NOT the same as an
    # explicitly declared empty set ("never search"): the former keeps the
    # framework default, the latter overrides it off.
    engineer_live_search_stages: frozenset[str] | None = None

    @property
    def assurance_level(self) -> str:
        if self.stage_checks or self.stage_completion_validator is not None:
            return "hybrid"
        if self.checklist_optional_stages == frozenset(self.stage_order):
            return "runtime-authored"
        return "reviewer"

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

    def prepare_libraries(self, context: VerticalLibraryContext) -> None:
        if self.library_preparer is not None:
            self.library_preparer(context)

    def primary_deliverables(self, stage: str) -> tuple[str, ...]:
        return tuple((self.stage_primary_deliverables or {}).get(stage, ()))

    def live_search_stages(self, default: frozenset[str]) -> frozenset[str]:
        """Stages in which THIS vertical's Engineer runs with live web search.

        Core owns ``default`` and never enumerates vertical stage names: a
        vertical whose pipeline has no research stage would otherwise never
        reach a live-search stage at all. Stage names are vertical-local, so
        each vertical declares its own set and two verticals sharing a stage
        name (``review``) never leak into each other.
        """
        if self.engineer_live_search_stages is None:
            return default
        return self.engineer_live_search_stages

    def completion_issues(self, stage: str, project_root: Path) -> tuple[str, ...]:
        if self.stage_completion_validator is None:
            return ()
        value = self.stage_completion_validator(stage, project_root)
        if value is None:
            return ()
        if isinstance(value, str):
            raise VerticalContractError(
                f"vertical {self.name!r} completion validator returned a string"
            )
        try:
            return tuple(
                text
                for issue in value
                if (text := str(issue or "").strip())
            )
        except TypeError as exc:
            raise VerticalContractError(
                f"vertical {self.name!r} completion validator returned a non-iterable"
            ) from exc

    def planner_task_issues(self, stage: str, project_root: Path, task: Any) -> tuple[str, ...]:
        if self.planner_task_validator is None:
            return ()
        return tuple(
            str(issue).strip()
            for issue in self.planner_task_validator(stage, project_root, task)
            if str(issue).strip()
        )

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
    if len(set(stage_order)) != len(stage_order):
        raise VerticalContractError(f"vertical {name!r} declares duplicate stages")
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
    unknown_optional = sorted(optional_stages - set(stage_order))
    if unknown_optional:
        raise VerticalContractError(
            f"vertical {name!r} has unknown optional stages: {', '.join(unknown_optional)}"
        )
    unknown_checklists = sorted(set(checklist_items) - set(stage_order))
    if unknown_checklists:
        raise VerticalContractError(
            f"vertical {name!r} has checklists for unknown stages: "
            f"{', '.join(unknown_checklists)}"
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
    empty_required = [
        stage
        for stage in stage_order
        if stage not in optional_stages and not checklist_items.get(stage)
    ]
    if empty_required:
        raise VerticalContractError(
            f"vertical {name!r} has empty required checklists for: "
            f"{', '.join(empty_required)}"
        )
    for stage, items in checklist_items.items():
        if not isinstance(items, (list, tuple)):
            raise VerticalContractError(
                f"vertical {name!r} checklist {stage!r} is not a sequence"
            )
        seen_ids: set[str] = set()
        for item in items:
            item_id = str(getattr(item, "id", "") or "").strip()
            statement = str(getattr(item, "statement", "") or "").strip()
            if not item_id or not statement:
                raise VerticalContractError(
                    f"vertical {name!r} checklist {stage!r} has a malformed item"
                )
            if item_id in seen_ids:
                raise VerticalContractError(
                    f"vertical {name!r} checklist {stage!r} repeats item {item_id!r}"
                )
            seen_ids.add(item_id)
    mode = str(getattr(provider, "WORKFLOW_MODE", "staged") or "staged").strip().lower()
    if mode not in _WORKFLOW_MODES:
        raise VerticalContractError(
            f"vertical {name!r} has unsupported workflow mode {mode!r}"
        )
    mission_kind = str(
        getattr(provider, "MISSION_KIND", "custom") or "custom"
    ).strip().lower()
    if mission_kind not in _MISSION_KINDS:
        raise VerticalContractError(
            f"vertical {name!r} has unsupported mission kind {mission_kind!r}"
        )
    aliases = getattr(provider, "STAGE_ALIASES", {})
    aliases = {
        str(source).strip().lower(): str(target).strip().lower()
        for source, target in aliases.items()
        if str(source).strip() and str(target).strip()
    } if isinstance(aliases, dict) else {}
    stage_completion_validator = getattr(provider, "stage_completion_issues", None)
    if stage_completion_validator is not None and not callable(stage_completion_validator):
        raise VerticalContractError(
            f"vertical {name!r} has a non-callable stage completion validator"
        )
    planner_task_validator = getattr(provider, "planner_task_issues", None)
    if planner_task_validator is not None and not callable(planner_task_validator):
        raise VerticalContractError(
            f"vertical {name!r} has a non-callable planner task validator"
        )
    raw_stage_checks = getattr(provider, "STAGE_CHECKS", {}) or {}
    if not isinstance(raw_stage_checks, dict):
        raise VerticalContractError(f"vertical {name!r} stage checks are not a mapping")
    unknown_stage_checks = sorted(set(raw_stage_checks) - set(stage_order))
    if unknown_stage_checks:
        raise VerticalContractError(
            f"vertical {name!r} has checks for unknown stages: "
            f"{', '.join(unknown_stage_checks)}"
        )
    stage_checks: dict[str, tuple[tuple[str, str], ...]] = {}
    for stage, checks in raw_stage_checks.items():
        if not isinstance(checks, (list, tuple)):
            raise VerticalContractError(
                f"vertical {name!r} checks for {stage!r} are not a sequence"
            )
        normalized_checks: list[tuple[str, str]] = []
        for check in checks:
            if not isinstance(check, (list, tuple)) or len(check) != 2:
                raise VerticalContractError(
                    f"vertical {name!r} check for {stage!r} is not a label-command pair"
                )
            label, command = check
            if not isinstance(label, str) or not label.strip():
                raise VerticalContractError(
                    f"vertical {name!r} check for {stage!r} has an empty label"
                )
            if not isinstance(command, str) or not command.strip():
                raise VerticalContractError(
                    f"vertical {name!r} check for {stage!r} has an empty command"
                )
            normalized_checks.append((label.strip(), command.strip()))
        stage_checks[stage] = tuple(normalized_checks)
    raw_primary_deliverables = (
        getattr(provider, "STAGE_PRIMARY_DELIVERABLES", {}) or {}
    )
    if not isinstance(raw_primary_deliverables, dict):
        raise VerticalContractError(
            f"vertical {name!r} primary deliverables are not a mapping"
        )
    unknown_primary_stages = sorted(
        set(raw_primary_deliverables) - set(stage_order)
    )
    if unknown_primary_stages:
        raise VerticalContractError(
            f"vertical {name!r} has primary deliverables for unknown stages: "
            f"{', '.join(unknown_primary_stages)}"
        )
    stage_primary_deliverables = {
        str(stage): tuple(
            path
            for value in values
            if (path := str(value or "").strip())
        )
        for stage, values in raw_primary_deliverables.items()
    }
    raw_live_search_stages = getattr(provider, "ENGINEER_LIVE_SEARCH_STAGES", None)
    engineer_live_search_stages: frozenset[str] | None = None
    if raw_live_search_stages is not None:
        # Declared-empty ("never search") and absent ("use the caller's
        # baseline") are different answers, so nothing here may silently DROP an
        # element: a stray blank string would otherwise turn a typo into a
        # permanent, unreported "live search off".
        if isinstance(raw_live_search_stages, str) or not isinstance(
            raw_live_search_stages, (list, tuple, set, frozenset)
        ):
            raise VerticalContractError(
                f"vertical {name!r} live search stages are not a collection of stages"
            )
        declared: set[str] = set()
        for stage in raw_live_search_stages:
            if not isinstance(stage, str):
                raise VerticalContractError(
                    f"vertical {name!r} live search stage {stage!r} is not a string"
                )
            normalized = stage.strip().lower()
            if not normalized:
                raise VerticalContractError(
                    f"vertical {name!r} declares a blank live search stage"
                )
            declared.add(normalized)
        engineer_live_search_stages = frozenset(declared)
        unknown_live_search = sorted(engineer_live_search_stages - set(stage_order))
        if unknown_live_search:
            raise VerticalContractError(
                f"vertical {name!r} declares live search for unknown stages: "
                f"{', '.join(unknown_live_search)}"
            )
    return VerticalContract(
        name=str(name or "").strip().lower(),
        stage_order=stage_order,
        checklist_items=checklist_items,
        completion_gate=gate,
        mission_kind=mission_kind,
        ground_before_handoff=bool(
            getattr(provider, "GROUND_BEFORE_HANDOFF", False)
        ),
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
        library_preparer=(
            getattr(provider, "LIBRARY_PREPARER")
            if callable(getattr(provider, "LIBRARY_PREPARER", None))
            else None
        ),
        stage_completion_validator=stage_completion_validator,
        planner_task_validator=planner_task_validator,
        stage_checks=stage_checks,
        stage_primary_deliverables=stage_primary_deliverables,
        engineer_live_search_stages=engineer_live_search_stages,
    )


__all__ = [
    "VERTICAL_CONTRACT_VERSION",
    "VerticalContract",
    "VerticalContractError",
    "VerticalLibraryContext",
    "vertical_contract",
]
