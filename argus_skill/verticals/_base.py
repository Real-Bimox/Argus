"""Resolve vertical providers through the framework's narrow contract.

Every built-in, data-domain, or entry-point vertical declares stages, checklist
items, completion strength, and optional role/evidence hooks. Missing or broken
providers fail visibly; silently substituting another vertical changes the task.
"""
from __future__ import annotations

import importlib
import logging
import os
from pathlib import Path
from types import ModuleType
from typing import TypeAlias

from ..core.vertical_contract import VerticalContract, vertical_contract
from ._data_domain import DataDomain, load_data_domain

log = logging.getLogger(__name__)

#: The safe fallback vertical: its stages module always imports.
DEFAULT_VERTICAL = "research"
VerticalDefinition: TypeAlias = ModuleType | DataDomain
_VERTICAL_IMPORT_ALIASES = {
    "digital_circuit_benchmark": "digital_circuit.benchmark",
}


def _normalize_vertical_name(name: object) -> str:
    """Lower/strip a vertical name and drop a trailing ``-needed`` sentinel."""
    if not isinstance(name, str):
        return DEFAULT_VERTICAL
    cleaned = name.strip().lower()
    if cleaned.endswith("-needed"):
        cleaned = cleaned[: -len("-needed")]
    return cleaned or DEFAULT_VERTICAL


def load_vertical(name: object, project_root: object = None) -> VerticalDefinition:
    """Resolve one in-tree, plugin, or project-local vertical provider."""
    cleaned = _normalize_vertical_name(name)
    import_name = _VERTICAL_IMPORT_ALIASES.get(cleaned, cleaned)
    module_name = f"argus_skill.verticals.{import_name}.stages"
    stages_path = os.path.join(
        os.path.dirname(__file__), *import_name.split("."), "stages.py"
    )
    if os.path.isfile(stages_path):
        try:
            return importlib.import_module(module_name)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"vertical {cleaned!r} exists but failed to import: {exc}"
            ) from exc

    from ._registry import vertical_plugin

    plugin = vertical_plugin(cleaned)
    if plugin is not None:
        return plugin.module
    if project_root is not None:
        domain = load_data_domain(cleaned, project_root)
        if domain is not None:
            return domain
    raise LookupError(f"unknown vertical: {cleaned}")


def load_vertical_contract(
    name: object,
    project_root: object = None,
) -> VerticalContract:
    cleaned = _normalize_vertical_name(name)
    return vertical_contract(cleaned, load_vertical(cleaned, project_root=project_root))


# --- contract accessors retained for existing callers ---------------------


def _contract(mod: VerticalDefinition) -> VerticalContract:
    name = str(getattr(mod, "__name__", None) or getattr(mod, "name", "vertical"))
    return vertical_contract(name, mod)


def vertical_checklist_stage_order(mod: VerticalDefinition) -> tuple[str, ...]:
    return _contract(mod).stage_order


def vertical_checklist_items(mod: VerticalDefinition) -> dict:
    return _contract(mod).checklist_items


def vertical_checklist_optional_stages(
    mod: VerticalDefinition,
) -> frozenset[str]:
    """Return stages whose checklist is explicitly declared optional."""
    return _contract(mod).checklist_optional_stages


def vertical_stage_aliases(mod: VerticalDefinition) -> dict[str, str]:
    """Return non-canonical stage names mapped to canonical stage names."""
    return dict(_contract(mod).stage_aliases or {})


def vertical_role_banner(mod: VerticalDefinition, role: str) -> str:
    return _contract(mod).banner(role)


def vertical_requires_independent_review(mod: VerticalDefinition) -> bool:
    """Return whether every mission in this vertical requires a Reviewer."""
    return _contract(mod).requires_independent_review


def vertical_completion_gate(mod: VerticalDefinition) -> str:
    return _contract(mod).completion_gate


def vertical_mission_kind(mod: VerticalDefinition) -> str:
    return _contract(mod).mission_kind


def vertical_completion_contract_version(mod: VerticalDefinition) -> int:
    """Return the optional versioned final-stage completion contract."""
    return _contract(mod).completion_contract_version


def vertical_research_target_levels(mod: VerticalDefinition) -> tuple[str, ...]:
    """Return the research target levels supported by this vertical."""
    return _contract(mod).research_target_levels


def vertical_workflow_mode(mod: VerticalDefinition) -> str:
    """Return the vertical's supported workflow mode."""
    return _contract(mod).workflow_mode


def vertical_search_altitude(mod: VerticalDefinition, project_root: object) -> str:
    return _contract(mod).altitude(project_root)


def vertical_prepare_mission(
    mod: VerticalDefinition,
    *,
    stage: str,
    project_root: Path,
    state_root: Path,
) -> str:
    return _contract(mod).prepare_mission(
        stage=stage,
        project_root=project_root,
        state_root=state_root,
    )


def vertical_stage_completion_issues(
    mod: VerticalDefinition,
    *,
    stage: str,
    project_root: Path,
) -> tuple[str, ...]:
    """Run the provider's deterministic pre-completion validator, if any."""
    return _contract(mod).completion_issues(stage, project_root)


__all__ = [
    "DEFAULT_VERTICAL",
    "VerticalContract",
    "VerticalDefinition",
    "load_vertical",
    "load_vertical_contract",
    "vertical_checklist_stage_order",
    "vertical_checklist_items",
    "vertical_checklist_optional_stages",
    "vertical_role_banner",
    "vertical_requires_independent_review",
    "vertical_completion_contract_version",
    "vertical_completion_gate",
    "vertical_mission_kind",
    "vertical_research_target_levels",
    "vertical_prepare_mission",
    "vertical_workflow_mode",
    "vertical_search_altitude",
    "vertical_stage_completion_issues",
]
