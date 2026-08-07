"""Argus self-maintenance vertical.

Core supplies orchestration, durable state, role execution, review, and recovery.
This vertical owns repository-specific architecture policy, audit tooling,
Skills, stages, and evidence requirements for changing Argus itself.
"""
from __future__ import annotations

from ...skills.stage_machine import ChecklistItem

STAGE_ORDER = ["scope", "audit", "change", "verify", "report"]
CHECKLIST_STAGE_ORDER = tuple(STAGE_ORDER)
CHECKLIST_OPTIONAL_STAGES: tuple[str, ...] = ()
WORKFLOW_MODE = "staged"
MISSION_KIND = "software"
GROUND_BEFORE_HANDOFF = True
REQUIRE_INDEPENDENT_REVIEW = True
COMPLETION_CONTRACT_VERSION = 1
completion_gate = "none"

_TOOL = (
    "${ARGUS_SKILL_PYTHON:-python} -m "
    "argus_skill.verticals.argus_maintenance.architecture_audit"
)

STAGE_CHECKS: dict[str, list[tuple[str, str]]] = {
    "scope": [
        ("Maintenance scope exists", f"{_TOOL} require research/MAINTENANCE_SCOPE.md"),
    ],
    "audit": [
        ("Architecture audit is valid", f"{_TOOL} validate --report research/ARCHITECTURE_AUDIT.json"),
        ("Finding decisions exist", f"{_TOOL} require research/MAINTENANCE_DECISIONS.md"),
    ],
    "change": [
        ("Change plan exists", f"{_TOOL} require research/MAINTENANCE_PLAN.md"),
        ("Patch has no whitespace errors", "git diff --check"),
    ],
    "verify": [
        ("Verification record exists", f"{_TOOL} require research/VERIFICATION.md"),
    ],
    "report": [
        ("Maintenance report exists", f"{_TOOL} require MAINTENANCE_REPORT.md"),
    ],
}

_MANAGER_SKILL = "manager/argus-maintenance-grounding.md"
_PLANNER_SKILL = "planner/argus-maintenance-planning.md"
_ENGINEER_SKILL = "engineer/argus-maintenance-execution.md"
_REVIEWER_SKILL = "reviewer/argus-maintenance-review.md"

REVIEWER_CHECKLISTS: dict[str, tuple[str, str, list[str]]] = {
    "scope": (
        _PLANNER_SKILL,
        "Confirm the requested behavior, real call path, closest reusable analogue, affected public contracts, explicit non-goals, and core/vertical ownership before approving edits.",
        ["research/MAINTENANCE_SCOPE.md"],
    ),
    "audit": (
        _ENGINEER_SKILL,
        "Inspect the machine-readable audit and the maintainer's dispositions. Heuristic matches are not defects: every relevant assert, digest, fallback, wrapper, literal, or coupling finding must be tied to a real call path and classified keep, simplify, move, or remove.",
        ["research/ARCHITECTURE_AUDIT.json", "research/MAINTENANCE_DECISIONS.md"],
    ),
    "change": (
        _ENGINEER_SKILL,
        "Require the smallest coherent implementation. Shared behavior belongs behind a narrow reusable contract; domain tools, Skills, checklists, stages, and workflow stay in the vertical. Reject behavior-free aliases, duplicated state, speculative compatibility, and silent fallback chains.",
        ["research/MAINTENANCE_PLAN.md", "research/ARCHITECTURE_AUDIT.json"],
    ),
    "verify": (
        _REVIEWER_SKILL,
        "Independently run the narrow regression, affected package suite, architecture-boundary tests, type/build checks, and relevant failure-path probes. Preserve authentication, authorization, sandboxing, secret protection, idempotency, crash recovery, and data integrity.",
        ["research/VERIFICATION.md"],
    ),
    "report": (
        _REVIEWER_SKILL,
        "Require a concise before/after architecture account, exact commands and results, compatibility impact, remaining debt, and evidence-bounded claims. Generated release artifacts must match the final source when shipped files changed.",
        ["MAINTENANCE_REPORT.md", "research/VERIFICATION.md"],
    ),
}

CHECKLIST_ITEMS: dict[str, tuple[ChecklistItem, ...]] = {
    "scope": (
        ChecklistItem(
            id="scope.behavior_and_boundary",
            statement=(
                "The requested behavior, current call path, public contracts, closest reusable analogue, core/vertical ownership, non-goals, and acceptance checks are explicit before cleanup begins."
            ),
            evidence_hint="research/MAINTENANCE_SCOPE.md",
        ),
    ),
    "audit": (
        ChecklistItem(
            id="audit.evidence_not_pattern",
            statement=(
                "The repository audit covers runtime asserts, fixed digests and machine/domain literals, silent broad exceptions, fallback chains, thin wrappers, oversized functions, and concrete-vertical coupling; relevant findings have call-path evidence and a keep/simplify/move/remove decision."
            ),
            evidence_hint=(
                "research/ARCHITECTURE_AUDIT.json plus research/MAINTENANCE_DECISIONS.md; collect with `python -m argus_skill.verticals.argus_maintenance.architecture_audit collect`"
            ),
        ),
    ),
    "change": (
        ChecklistItem(
            id="change.concise_reusable_decoupled",
            statement=(
                "The patch removes accidental complexity, reuses one authoritative implementation, keeps core limited to generic orchestration/state/recovery contracts, and keeps domain tools, Skills, stages, checklists, and workflow in their vertical provider."
            ),
            evidence_hint="research/MAINTENANCE_PLAN.md and the complete source diff",
        ),
        ChecklistItem(
            id="change.no_speculative_compatibility",
            statement=(
                "Every retained wrapper, alias, knob, fallback, digest, or compatibility path has an observed consumer and named retirement/ownership rule; otherwise it is removed rather than documented into permanence."
            ),
            evidence_hint="finding dispositions cross-referenced to unchanged callers and tests",
        ),
    ),
    "verify": (
        ChecklistItem(
            id="verify.behavior_and_failures",
            statement=(
                "Tests exercise the changed behavior and decisive failure paths, not implementation-shaped assertions. Build/type checks and affected suites ran, and no zero-test or skipped-build result is reported as passing."
            ),
            evidence_hint="research/VERIFICATION.md with exact commands and result summaries",
        ),
        ChecklistItem(
            id="verify.protected_boundaries",
            statement=(
                "Independent review confirms that simplification did not weaken authentication, authorization, sandboxing, secrets, idempotency, crash recovery, concurrency safety, or data integrity."
            ),
            evidence_hint="reviewer evidence in research/VERIFICATION.md",
        ),
    ),
    "report": (
        ChecklistItem(
            id="report.honest_before_after",
            statement=(
                "The final report states the behavior delivered, architecture before/after, removed and retained complexity with reasons, exact verification, compatibility impact, and unresolved debt without claiming that heuristic count reductions prove quality."
            ),
            evidence_hint="MAINTENANCE_REPORT.md",
        ),
    ),
}


def role_banner(role: str) -> str:
    common = (
        "ARGUS MAINTENANCE VERTICAL — improve Argus itself, not an operator's domain project. "
        "Keep code concise, reusable, and explicit. Core owns only generic self-evolution, "
        "context orchestration, durable long-running execution, review/recovery, and narrow "
        "vertical contracts. Concrete tools, Skills, checklist items, stages, and workflows "
        "belong to vertical providers. Static audit matches are clues, never verdicts: prove a "
        "real call path before changing them. Remove behavior-free wrappers, duplicate state, "
        "stale knobs, speculative compatibility, and silent fallback chains, but preserve "
        "justified security, permission, recovery, concurrency, and integrity boundaries. "
        "Prefer one coherent source of truth, observable failures, small diffs, and tests against "
        "public behavior rather than implementation details.\n"
    )
    if role == "manager":
        return common + "Ground the exact repository path, affected contracts, non-goals, and release obligations before handoff.\n"
    if role == "planner":
        return common + "Plan around call paths and independently testable risks; fold audit, implementation, and focused verification into cohesive nodes instead of creating paperwork-only tasks.\n"
    if role == "reviewer":
        return common + "Review the full diff and run decisive checks independently. A lower heuristic count is not success unless behavior and architecture improve without weakening protected boundaries.\n"
    return common + "Use the vertical audit tool, classify relevant findings, make the smallest reusable change, and record exact verification rather than claiming broad cleanup.\n"


__all__ = [
    "CHECKLIST_ITEMS", "CHECKLIST_STAGE_ORDER", "REVIEWER_CHECKLISTS",
    "STAGE_CHECKS", "STAGE_ORDER", "WORKFLOW_MODE", "completion_gate",
    "role_banner",
]
