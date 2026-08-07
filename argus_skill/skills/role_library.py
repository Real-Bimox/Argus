"""Agent-native, on-demand Skill discovery.

Roles receive ordered library paths and decide what to inspect with their own
tools. The runtime does not parse, match, rank, rewrite, or inject Skill bodies.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..core.event_catalog import EventType
from .store import ROLE_CROSS_READ_POOLS, ROLE_SKILL_POOLS


@dataclass
class RoleSkillLibraries:
    role: str
    library_roots: list[Path] = field(default_factory=list)
    own_paths: list[Path] = field(default_factory=list)
    reference_paths: list[Path] = field(default_factory=list)
    native_paths: list[Path] = field(default_factory=list)
    block: str = ""


def skill_library_roots(skill_store: object | None) -> list[Path]:
    if skill_store is None:
        return []
    resolver = getattr(skill_store, "library_roots", None)
    if callable(resolver):
        roots = [Path(item).resolve() for item in resolver()]
    else:
        value = getattr(skill_store, "skills_dir", None)
        roots = [Path(value).resolve()] if value is not None else []
    return list(dict.fromkeys(roots))


def _pool_paths(roots: list[Path], pools: frozenset[str]) -> list[Path]:
    paths: list[Path] = []
    for root in roots:
        for pool in sorted(pools):
            path = root if pool == "general" else root / pool
            if pool == "general" and not any(
                item.is_file() and item.name.casefold() != "index.md"
                for item in root.glob("*.md")
            ):
                continue
            if path.exists() and path not in paths:
                paths.append(path)
    return paths


def render_skill_library_paths(skill_store: object | None, *, role: str) -> str:
    roots = skill_library_roots(skill_store)
    if not roots:
        return ""
    own_pools = ROLE_SKILL_POOLS.get(role, frozenset({role}))
    reference_pools = ROLE_CROSS_READ_POOLS.get(role, frozenset())
    lines = []
    for index, root in enumerate(roots, 1):
        own = ", ".join(
            "root" if pool == "general" else pool for pool in sorted(own_pools)
        )
        references = ", ".join(sorted(reference_pools)) or "none"
        lines.append(
            f"{index}. `{root}` (OWN: {own}; REFERENCE only: {references})"
        )
    return (
        "## Skill libraries (on-demand)\n"
        f"Role: {role}. Order: project → vertical/domain → global; OWN > REFERENCE.\n"
        + "\n".join(lines)
        + "\n\nBefore the first repository tool, make one Skill relevance decision from "
        "native-loader descriptions. Read every clearly matching body first. If "
        "descriptions are unavailable, do one targeted filename/frontmatter search "
        "in OWN paths. On a miss, open no body. Never scan all bodies or open a "
        "neighbor because another matched. A wrong Skill is worse than none. Task, evidence, "
        "and role boundaries override Skills. These paths are the portable fallback; "
        "bodies are not injected. Re-probe mutable facts before use."
    )


def role_skill_libraries(
    skill_store: object | None,
    *,
    role: str,
    on_event: Callable[[dict], None] | None = None,
) -> RoleSkillLibraries:
    roots = skill_library_roots(skill_store)
    own_paths = _pool_paths(roots, ROLE_SKILL_POOLS.get(role, frozenset({role})))
    reference_paths = _pool_paths(
        roots, ROLE_CROSS_READ_POOLS.get(role, frozenset())
    )
    if on_event is not None and roots:
        on_event(
            {
                "type": EventType.SKILL_LIBRARY_AVAILABLE,
                "role": role,
                "paths": [str(path) for path in roots],
                "own_paths": [str(path) for path in own_paths],
                "reference_paths": [str(path) for path in reference_paths],
                "precedence": "project,vertical,global",
                "discovery": "native-or-path-fallback",
                "text": "Skill library paths supplied for on-demand discovery",
            }
        )
    return RoleSkillLibraries(
        role=role,
        library_roots=roots,
        own_paths=own_paths,
        reference_paths=reference_paths,
        native_paths=own_paths,
        block=render_skill_library_paths(skill_store, role=role),
    )


__all__ = [
    "RoleSkillLibraries",
    "render_skill_library_paths",
    "role_skill_libraries",
    "skill_library_roots",
]
