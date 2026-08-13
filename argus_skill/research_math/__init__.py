"""A reusable state kernel for research mathematics.

This package owns one question: *what does this project currently believe, on
what evidence, and is that evidence still about what it says it is about?* It
answers that with four record types (``ContextVersion``, ``ClaimVersion``,
``EvidenceRecord``, ``ProofRoute``), one value object that carries the
math-specific part (``ExternalAssumption``), and derived status — nothing in
here can be asserted into being true.

**It imports nothing from Argus, and nothing outside the standard library.**
Not by coincidence: this is meant to lift out into its own repository without
edits, and the roles it would otherwise reach for (Manager, Planner, Engineer,
Reviewer, the backlog, the supervisor) are exactly the orchestration that a
different host would replace. ``tests/research_math/test_research_math_kernel.py``
enforces both with an AST sweep, the same technique
``tests/core/test_vertical_contract.py`` uses to keep core free of vertical
imports.

Deliberately absent, and each for a reason rather than for lack of time:

*Verifiers.* No Lean, code, literature, or citation checker lives here yet.
``EvidenceRecord`` is the envelope they will fill; writing the envelope and the
letters at once would fix the envelope's shape from guesses.

*``MechanismVersion``.* The proposal that this package model reusable proof
mechanisms is the one part of it with no run-time support at all — the goal
document itself lists "does the agent reliably produce mechanisms" as an open
question that only a real problem answers. Fixing a schema for it now would
answer that question by assertion.

*Argus adapters, prompts, backlog wiring, context projection.* Later PRs, on
the other side of the boundary this package exists to draw.
"""
from __future__ import annotations

from .assessment import (
    DISCHARGING_TIERS,
    ESTABLISHED_STATUSES,
    KERNEL_TIERS,
    REFUTING_TIERS,
    ClaimAssessment,
    ClaimStatus,
    RouteAssessment,
    RouteStatus,
    assess_claim,
    assess_route,
    assess_routes,
    route_cycles,
)
from .models import (
    ARTIFACT_REQUIRED_TIERS,
    ClaimVersion,
    ContextVersion,
    EvidenceRecord,
    EvidenceTier,
    ExternalAssumption,
    ProofRoute,
    RetiredAssumption,
    SubjectKind,
    SubjectRef,
    Verdict,
    content_digest,
    normalize_text,
)
from .store import (
    SCHEMA_VERSION,
    STATE_RELPATH,
    MathState,
    MathStateError,
    StateIssue,
    load_state,
    save_state,
    state_path,
)

__all__ = [
    "ARTIFACT_REQUIRED_TIERS",
    "DISCHARGING_TIERS",
    "ESTABLISHED_STATUSES",
    "KERNEL_TIERS",
    "REFUTING_TIERS",
    "SCHEMA_VERSION",
    "STATE_RELPATH",
    "ClaimAssessment",
    "ClaimStatus",
    "ClaimVersion",
    "ContextVersion",
    "EvidenceRecord",
    "EvidenceTier",
    "ExternalAssumption",
    "MathState",
    "MathStateError",
    "ProofRoute",
    "RetiredAssumption",
    "RouteAssessment",
    "RouteStatus",
    "StateIssue",
    "SubjectKind",
    "SubjectRef",
    "Verdict",
    "assess_claim",
    "assess_route",
    "assess_routes",
    "content_digest",
    "load_state",
    "normalize_text",
    "route_cycles",
    "save_state",
    "state_path",
]
