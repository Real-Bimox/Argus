"""Research-only venue and idea preparation hooks."""
from __future__ import annotations

import os

from ...core.vertical_contract import VerticalLibraryContext

_FALSE = frozenset({"0", "false", "no", "off"})
_VENUE_STAGES = frozenset({"research", "plan", "benchmark", "run", "analysis"})


def _enabled(name: str) -> bool:
    return os.environ.get(name, "1").strip().lower() not in _FALSE


def prepare_skill_libraries(context: VerticalLibraryContext) -> None:
    """Prepare live research evidence before Agents inspect their libraries."""
    if context.workflow_mode == "direct" or not context.paper_mission:
        return
    if (
        _enabled("ARGUS_SKILL_VENUE_RESEARCH")
        and context.stage in _VENUE_STAGES
    ):
        from ...skills.venue_research import (
            needs_venue_research,
            research_venue_profile,
        )

        if needs_venue_research(context.workdir):
            context.emit({
                "type": "venue.research.started",
                "text": "live web search: selecting/researching target venue",
            })
            ok = research_venue_profile(
                context.runner,
                context.workdir,
                model=context.model,
            )
            context.emit({
                "type": "venue.research.completed",
                "ok": ok,
                "text": (
                    "built research/VENUE_PROFILE.json"
                    if ok
                    else "venue research produced no profile"
                ),
            })
    if _enabled("ARGUS_SKILL_IDEA_SEARCH") and context.stage == "research":
        from ...skills.idea_search import _already_seeded, augment_idea_candidates

        if not _already_seeded(context.workdir):
            context.emit({
                "type": "idea.search.started",
                "text": "live web search: seeding candidate ideas",
            })
            count = augment_idea_candidates(
                context.runner,
                context.workdir,
                direction=context.direction,
                model=context.model,
            )
            context.emit({
                "type": "idea.search.completed",
                "count": count,
                "text": f"appended {count} candidate idea(s)",
            })
