"""Minimal dynamic-path vertical for mathematical research.

The stages are deliberately coarse. Background retrieval, examples and
counterexamples, computation, natural-language proof, and Lean formalization are
methods selected for the problem at hand, not mandatory pipeline stages.
"""
from __future__ import annotations

from pathlib import Path

from ...skills.stage_machine import ChecklistItem

STAGE_ORDER = ("scope", "solve", "review")
CHECKLIST_STAGE_ORDER = STAGE_ORDER
WORKFLOW_MODE = "proportional"
RESEARCH_TARGET_LEVELS = ("exploratory", "publishable", "doctoral")

# A proof is the one deliverable whose author cannot certify it. Every sibling
# research vertical already declares this (``research``, ``materials``,
# ``chip_design``); math was the omission, and defaulting to ``False`` is what
# let a testbed run close an open conjecture on the Engineer's own verdict:
# "Engineer reported the requested milestone complete; independent review was
# not required for this mission." One round, no Reviewer, no artifact, no proof
# graph — and the claim was simply believed.
#
# Deliberately declared here rather than argued per mission: unlike the paper /
# completion-gate checks, ``_independent_review_required_for_project_root``
# reads this contract with no ``workflow_mode == "direct"`` exemption, so a
# Manager that collapses a proof to a single direct work package still cannot
# collapse away its verification.
REQUIRE_INDEPENDENT_REVIEW = True

# Math has no ``research`` stage, so the framework's default live-search stage
# never fires here: without this declaration the Engineer would do literature
# work from recall alone. ``scope`` needs the literature to state the problem
# and its known status; ``solve`` needs it to find existing techniques,
# counterexamples, and prior results. ``review`` is deliberately excluded: it is
# independent verification of an argument already in hand, and the Reviewer
# (which always runs with live search) owns the source checks there.
ENGINEER_LIVE_SEARCH_STAGES = frozenset({"scope", "solve"})

# Math missions end through the ordinary reviewer-certified final-stage path.
# They are neither paper-submission missions nor metric-optimization campaigns.
completion_gate = "none"
COMPLETION_CONTRACT_VERSION = 1
PROTECTED_ITEM_IDS = frozenset({"review.goal-achieved"})

_PIPELINE_CHECK = (
    "Pipeline state present",
    "test -f research/PIPELINE_STATE.json",
)

STAGE_CHECKS: dict[str, list[tuple[str, str]]] = {
    stage: [_PIPELINE_CHECK] for stage in STAGE_ORDER
}


def stage_completion_issues(stage: str, project_root: Path) -> tuple[str, ...]:
    """Validate objective identity, Lean evidence, and the policy-required graph."""
    from ...core.verification_policy import resolve_policy
    from .lean_evidence import lean_evidence_issues
    from .objective_mode import resolve_objective
    from .proof_graph import graph_required_for, load_graph

    stage_name = (stage or "").strip().lower()
    objective = resolve_objective(project_root)
    if stage_name not in STAGE_ORDER:
        return (f"unknown math stage {stage_name!r}",)
    if not objective.resolved:
        return (objective.note,)
    if stage_name == "scope":
        return ()

    policy = resolve_policy(
        project_root,
        stage=stage_name,
        vertical="math",
    )
    # Formalization stays optional: a project with no `.lean` file gets an
    # empty tuple here and never loads the checker. Once one is present it is a
    # claim, and every claim must be redeemable — so the source must show a
    # current, hash-bound compiler result that says the proof went through.
    # A failure the environment caused (no toolchain, no Mathlib) is worded
    # differently from a broken proof, because the reviewer needs to tell them
    # apart, but it does not pass: an unverified formalization is not evidence
    # however good the excuse. The escape hatch is not committing the source.
    # This never runs a compiler; it reads what one already recorded.
    issues = list(lean_evidence_issues(project_root))
    issues.extend(_math_state_issues(project_root))
    # Only at the last stage. Citation checking runs out of band and lands when
    # it lands; blocking `solve` on it would stop the reasoning to wait for a
    # registry, which is the one thing the asynchronous design exists to avoid.
    # `review` is where the work is handed over, and nothing is handed over
    # standing on a source nobody went and read.
    if stage_name == "review":
        issues.extend(_citation_delivery_issues(project_root))
    if not graph_required_for(policy.profile, objective.mode):
        return tuple(issues)
    graph = load_graph(project_root)
    if graph is None:
        issues.append(
            "targeted math under develop/certify requires "
            "research/PROOF_GRAPH.json"
        )
        return tuple(issues)
    issues.extend(graph.validate())
    if graph.goal != objective.goal:
        issues.append(
            "proof graph goal does not match the Manager-owned math_goal"
        )
    return tuple(issues)


def _math_state_issues(project_root: Path) -> tuple[str, ...]:
    """Structural defects in the claim ledger, when the project keeps one.

    The same rule as the Lean sources above, for the same reason. A project with
    no ``research/MATH_STATE.json`` pays nothing: ``load_state`` reads a missing
    file as an empty state, and an empty state has no defects, so absence needs
    no special case here. A project that does keep a ledger has to keep one that
    holds together — a claim stated against a superseded context, or evidence
    bound to a statement the claim no longer carries, is exactly the kind of
    drift that makes a status mean less than it reads.

    Until this call the ledger was advisory: ``research_math`` derived
    ``closed_kernel`` and ``conditional_kernel`` and nothing consulted the
    answer, so a project could finish a stage with a ledger contradicting
    itself. ``StateIssue.rendered()`` was written for this — it produces the
    same ``path: message`` shape ``lean_evidence`` and ``literature_ledger``
    already emit, so all three render alike here.

    What this deliberately does *not* do is let a claim's derived status decide
    whether the mission is complete. That question belongs with the objective
    mode and the requested bar below, it is a policy judgement rather than a
    structural one, and conflating the two would make "the ledger is consistent"
    and "the mathematics is finished" the same check when they are not.

    An unreadable ledger is reported as a defect rather than raised. Letting
    ``MathStateError`` escape would take down the completion gate for every
    other check with it, and a gate that reports nothing is indistinguishable
    from a gate that found nothing wrong.

    ``certificate_issues`` is asked alongside the kernel's own ``validate``
    because the kernel does not know what a Lean certificate is, and the defect
    it catches — a fidelity verdict still standing after the reading it approved
    was replaced — is precisely one a stage must not complete over. Both render
    the same way, so the caller cannot tell which found what, and does not need
    to.
    """
    from ...research_math import MathStateError, load_state, state_path
    from .math_state import certificate_issues

    try:
        state = load_state(project_root)
    except MathStateError as exc:
        return (f"{state_path(project_root).name}: {exc}",)
    return tuple(
        item.rendered()
        for item in (*state.validate(), *certificate_issues(state))
    )


def _citation_delivery_issues(project_root: Path) -> tuple[str, ...]:
    """Every imported result has to have been looked up before anything ships.

    The half of research mathematics no proof checker touches. Lean can verify
    that a theorem follows from its hypotheses and say nothing about whether the
    hypothesis imported as "Theorem 3.2 of [K]" is in [K] at all — and a
    fabricated or misquoted citation is not a formatting defect, it is a proof
    that does not exist, wearing a reference. So this is asked once, here, and it
    is the only citation gate: ``scope`` and ``solve`` complete with citations in
    any state, because a checker that interrupted the mathematics to wait on a
    registry would simply be turned off.

    ``confirmed`` and ``uncited`` are the two states that pass, and the second is
    not a loophole. An assumption that records prose and no locator has said
    plainly that it leans on something unciteable — a private communication, an
    unpublished note — which a reader can weigh. What must not pass is the
    citation that *looks* checkable and was never checked, and its neighbour: a
    ``disputed`` one, where somebody did go and found the proposition missing.
    That is settled work and it still must not ship, which is why this asks a
    narrower question than ``CitationAssessment.is_settled``.

    Both remedies work with no network, because a gate whose only remedy needs
    one is a gate that traps an offline run: a reader who has the paper records
    what it says with ``citation_check attribute``, and a source that genuinely
    cannot be obtained is restated in prose, which drops the claim to ``uncited``
    and says so in the open rather than leaving a lookup nobody can perform.
    """
    from ...research_math import MathStateError, load_state, state_path
    from .citation_check import DELIVERABLE_STATUSES

    try:
        state = load_state(project_root)
    except MathStateError as exc:
        return (f"{state_path(project_root).name}: {exc}",)
    where = "/".join(state_path(project_root).parts[-2:])
    issues: list[str] = []
    for claim in state.current_claims():
        for citation in state.citations(claim.claim_id):
            if citation.status in DELIVERABLE_STATUSES:
                continue
            issues.append(
                f"{where}: claim {claim.claim_id} stands on "
                f"{citation.assumption_id} ({citation.cited_proposition}), "
                f"whose citation is {citation.status.value}. Record what a "
                "reader found at that proposition with `python -m "
                "argus_skill.verticals.math.citation_check attribute --claim "
                f"{claim.claim_id} --assumption {citation.assumption_id} "
                "--excerpt-file <what you read> --verdict ... --by you`, or, if "
                "the source cannot be obtained, restate the assumption without "
                "--source-id/--locator so it reads as the prose citation it is"
            )
    return tuple(issues)


def prepare_mission(  # noqa: ARG001 - see the docstring on stage/state_root
    *,
    stage: str,
    project_root: Path,
    state_root: Path,
    mission: object,
) -> str:
    """Give this mission the state of the claim it is about, and nothing else.

    Keyword-only because the framework forwards this hook by keyword; the
    parameter names are the contract.

    ``stage`` is unread: what is recorded about a claim is the same fact in
    `scope`, `solve`, and `review`, and a projection that changed with the
    stage would be telling three different stories about one statement.
    ``state_root`` is unread because the mathematical state is project state —
    it sits in the project's `research/` directory beside `PROOF_GRAPH.json`,
    not in the per-session runtime root.

    Imported lazily: a project with no `research/MATH_STATE.json` never touches
    the state kernel, exactly as it never touches the Lean checker.
    """
    from .context_projection import project_mission_context

    return project_mission_context(project_root=project_root, mission=mission)


REVIEWER_CHECKLISTS: dict[str, tuple[str, str, list[str]]] = {
    "scope": (
        "reviewer/math-research-review.md",
        "Confirm what problem is being solved, what would count as success, and "
        "that the known status of the problem has been established here rather "
        "than left for the solve stage to rediscover once per worker. Do not "
        "require a planning artifact.",
        [],
    ),
    "solve": (
        "reviewer/math-research-review.md",
        "Review the mathematical result itself and the argument or real computation "
        "supporting it. Do not grade the presence of process documents.",
        [],
    ),
    "review": (
        "reviewer/math-research-review.md",
        "Independently decide whether the result is correct, answers the original "
        "question, and is described without overclaiming.",
        [],
    ),
}

CHECKLIST_ITEMS: dict[str, tuple[ChecklistItem, ...]] = {
    "scope": (
        ChecklistItem(
            id="scope.problem-explicit",
            statement=(
                "The problem is understood precisely enough to work on: the relevant "
                "objects, assumptions, quantifiers, and requested conclusion are clear."
            ),
            evidence_hint="the problem statement as actually understood",
        ),
        ChecklistItem(
            id="scope.success-criterion",
            statement=(
                "It is clear whether success means a proof, counterexample, construction, "
                "classification, estimate, or honest progress on an open problem. The "
                "objective mode is recorded, not assumed: `targeted` names one goal to "
                "prove or refute, `exploratory` names a direction whose deliverable is "
                "substantive partial results. The two have different completion bars, so "
                "an unset mode is a scope gap rather than a default."
            ),
            evidence_hint=(
                "the requested outcome and completion bar; math_objective_mode (and "
                "math_goal when targeted) in research/PIPELINE_STATE.json"
            ),
        ),
        ChecklistItem(
            id="scope.known-status-recorded",
            statement=(
                "What is already known about this problem has been established here "
                "and written into the ledger: the results the work will lean on, "
                "recorded as assumptions with their citations, and the approaches "
                "already known to fail. Completeness is not the bar and a literature "
                "survey is not the deliverable. The bar is that the answer exists in "
                "one place before several workers start, because a search performed "
                "in scope is paid once and the same search performed in solve is paid "
                "once per worker. \"Searched and found nothing relevant\" is a "
                "recorded answer, and so is \"no source could be obtained here\", "
                "which states a limitation a reviewer can weigh instead of leaving a "
                "gap that reads like an omission."
            ),
            evidence_hint=(
                "the assumptions recorded in research/MATH_STATE.json with their "
                "sources, or an explicit statement of what was searched and what it "
                "returned"
            ),
        ),
    ),
    "solve": (
        ChecklistItem(
            id="solve.substantive-result",
            statement=(
                "There is a substantive result relevant to the problem, supported by an "
                "argument, a valid witness, or a reproducible computation as appropriate."
            ),
            evidence_hint="the result and the mathematics or real run supporting it",
        ),
        ChecklistItem(
            id="solve.witness-valid",
            statement=(
                "Any counterexample or constructed object satisfies the original conditions; "
                "it is not a circular restatement or an answer to an easier problem."
            ),
            evidence_hint="a direct check of the relevant conditions",
        ),
        ChecklistItem(
            id="solve.support-matches-claim",
            statement=(
                "The strength of the conclusion matches the support: finite computation is "
                "not called a universal proof, and formal compilation is not treated as "
                "evidence for a mistranslated statement."
            ),
            evidence_hint="the actual tested range or compiler run and the stated limitation",
        ),
        ChecklistItem(
            id="solve.gap-reduced",
            statement=(
                "For a targeted project, the round moved the distance to the goal, not "
                "merely produced something new. Extending a finite verification to a wider "
                "range, more moduli, or more primes yields a fresh artifact and no gap "
                "reduction; repeating it at a larger bound buys the same information. Say "
                "which proposition changed status, or that none did. For an exploratory "
                "project this item is satisfied by a substantive, correctly-scoped result."
            ),
            evidence_hint=(
                "the proposition whose status changed; once a targeted route is settled, "
                "research/PROOF_GRAPH.json checked with `python -m "
                "argus_skill.verticals.math.proof_graph_check gap`"
            ),
        ),
    ),
    "review": (
        ChecklistItem(
            id="review.goal-achieved",
            statement=(
                "The completion claim matches the effective scope: project or final-stage "
                "completion requires the requested terminal mathematical outcome to be "
                "achieved. An error-free attempt, correct intermediate lemma, honest partial "
                "result, or unresolved conclusion is not final-stage completion. A bounded "
                "subtask may itself be done, but leave this item unsatisfied unless the "
                "original Goal Gate is achieved."
            ),
            evidence_hint=(
                "a direct mapping from the requested success criterion to the theorem, "
                "counterexample, construction, classification, or estimate actually obtained"
            ),
        ),
        ChecklistItem(
            id="review.statement-fidelity",
            statement=(
                "The natural-language problem and every formal statement are faithfully "
                "equivalent in objects, quantifiers, hypotheses, and conclusion."
            ),
            evidence_hint="a direct comparison with the original question",
        ),
        ChecklistItem(
            id="review.argument-correct",
            statement=(
                "The main argument is independently convincing: important steps are justified, "
                "dependencies are available, and no hidden assumption closes the gap."
            ),
            evidence_hint="the argument itself and any cited dependency",
        ),
        ChecklistItem(
            id="review.outcome-honest",
            statement=(
                "The conclusion says plainly what was proved, disproved, computed, conjectured, "
                "or left open. Novelty is claimed only when an appropriate source check supports "
                "it; otherwise uncertainty is stated without blocking a valid bounded result."
            ),
            evidence_hint="the stated conclusion, limitations, and sources if novelty is claimed",
        ),
    ),
}


def role_banner(role: str) -> str:
    """Load Math context as a Skill for the generic role implementation."""
    role_name = (role or "").strip().lower()
    skill_name = {
        "manager": "manager/math-research-manager.md",
        "planner": "planner/math-research-planning.md",
        "engineer": "engineer/math-research-execution.md",
        "reviewer": "reviewer/math-research-review.md",
        "scientist_create": "scientist/math-research-distillation.md",
        "scientist": "scientist/math-research-adaptation.md",
    }.get(role_name)
    if skill_name is None:
        return ""
    text = (Path(__file__).parent / "skills" / skill_name).read_text(
        encoding="utf-8"
    )
    if text.startswith("---"):
        _frontmatter, _separator, body = text[3:].partition("---")
        return body.strip()
    return text.strip()


__all__ = [
    "CHECKLIST_ITEMS",
    "CHECKLIST_STAGE_ORDER",
    "COMPLETION_CONTRACT_VERSION",
    "ENGINEER_LIVE_SEARCH_STAGES",
    "PROTECTED_ITEM_IDS",
    "REQUIRE_INDEPENDENT_REVIEW",
    "REVIEWER_CHECKLISTS",
    "RESEARCH_TARGET_LEVELS",
    "STAGE_CHECKS",
    "STAGE_ORDER",
    "WORKFLOW_MODE",
    "completion_gate",
    "prepare_mission",
    "role_banner",
    "stage_completion_issues",
]
