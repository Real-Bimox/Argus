"""What one mission needs to know about one claim, and nothing else.

A mathematics project accumulates state that no agent can be handed whole: a
few hundred claim versions, every verdict ever recorded against them, and the
routes that were tried and abandoned. Handing an Engineer the state file, or
the event log, or a summary of "the project so far", fails in both directions
at once — it is too long to read and it still does not say which of those
claims this particular task is about.

So this projects. Given the backlog item the supervisor just claimed, it finds
the claim that item is about and renders that claim's *neighbourhood*: the
statement and its version, the definitions it names, the external results it is
still taking on faith, the evidence that binds to this exact statement, the
immediate proof obligations, the routes already retired, and what would have to
happen for its status to move. Nothing transitive, and nothing about any other
claim.

Three properties are load-bearing, and each has a test that fails when it stops
holding:

**Bounded by the claim, not by the project.** Only depth-1 dependencies appear.
A second hop would pull in the obligations' obligations, and in a project with a
real proof tree that is the whole tree — which is the thing this module exists
not to send. One hop is also what a single mission can act on: it is the set of
statements whose status could change as a result of this round.

**Deterministic.** The same store and the same mission render byte-identical
text. No timestamps, no host paths, no reliance on ``dict`` order. The fragment
carries a digest of its own content so two of them can be told apart without
diffing prose — and so a reader who sees the same digest twice knows nothing
moved, rather than assuming it.

**It never raises into a mission.** A missing store means "this project does no
recorded mathematics" and produces nothing at all; a corrupt one produces a
short block that says the state could not be read. The difference matters: an
empty fragment from a broken file would tell the Engineer that a project with a
hundred recorded proofs believes nothing.

This module is an adapter and lives on the vertical side deliberately.
``argus_skill/research_math/`` imports nothing from Argus so it can be lifted
out; a projector that reads ``BacklogItem`` is exactly the Argus-shaped code
that would stop it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...research_math import (
    DISCHARGING_TIERS,
    KERNEL_TIERS,
    REFUTING_TIERS,
    STATE_RELPATH,
    ClaimStatus,
    ClaimVersion,
    ContextVersion,
    MathState,
    MathStateError,
    assess_route,
    content_digest,
    load_state,
)

__all__ = [
    "MISSION_TARGET_FIELDS",
    "MissionTarget",
    "project_mission_context",
    "resolve_target",
]

#: Where the state lives, as the mission should refer to it: project-relative.
#: An absolute path would differ per host and per worktree, which would break
#: the determinism this module promises and put a machine-specific string into
#: a prompt that gets compared across runs.
_STATE_REF = "/".join(STATE_RELPATH)

#: The mission fields consulted for the target claim, most decisive first.
#:
#: These are the *only* three the Planner authors that reach a ``BacklogItem``:
#: ``roles/prompts/planner.py`` gives it ``TASK_TITLE``, ``TASK_OBJECTIVE``,
#: ``TASK_ACCEPTANCE_CHECK`` and ``TASK_NON_GOALS`` and says outright that the
#: host owns everything else. ``tags`` are a closed host-authored vocabulary
#: (``_planning_context._planner_task_tags``) and ``context_refs`` are dropped
#: unless they name an existing file (``planner.hydrate_task_context_refs``), so
#: neither can carry a claim id however convenient that would have been.
#:
#: ``non_goals`` is deliberately absent: a claim named there is the one the
#: mission was told *not* to work on, and projecting it would aim the whole
#: fragment at the excluded statement.
MISSION_TARGET_FIELDS = ("acceptance_check", "title", "objective")

#: Characters that unambiguously continue an identifier. Used as a boundary so
#: that a claim called ``lemma-a`` is not found inside ``lemma-a-prime``: ids in
#: this schema are chosen by whoever recorded the claim, and prefix
#: relationships between them are the normal case rather than a strange one.
_ID_CORE = r"[A-Za-z0-9_\-]"

#: ``.`` is the hard case and needs its own rule. It is a legitimate id
#: character (``thm.3.1``), so treating it as a boundary would find ``thm.3``
#: inside ``thm.3.1``. But it is also how English ends a sentence, and an
#: acceptance check that reads "Prove udist-main." is the ordinary way a
#: mission names its claim -- treating it as an id character there makes the
#: single most common phrasing invisible. So a dot continues an id only when
#: something else follows it that continues an id too.
_LEFT = rf"(?<!{_ID_CORE})(?<!{_ID_CORE}\.)"
_RIGHT = rf"(?!{_ID_CORE})(?!\.{_ID_CORE})"

#: One statement, clipped. A claim statement is written by an agent and is
#: claim-sized by nature; this is a backstop against a pasted proof, not a
#: summarization policy, so it is generous and marked when it fires.
_MAX_TEXT = 600

#: A shorter clip for text that appears once per neighbour rather than once per
#: fragment.
_MAX_NEIGHBOUR_TEXT = 220

#: Rows per list. The neighbourhood rule already bounds these; this is the
#: backstop for one claim with a pathological number of routes or verdicts, and
#: it reports what it withheld rather than truncating in silence.
_MAX_ROWS = 12


@dataclass(frozen=True)
class MissionTarget:
    """Which claim a mission is about, or why that could not be decided."""

    claim_id: str = ""
    field: str = ""
    candidates: tuple[str, ...] = ()

    @property
    def ambiguous(self) -> bool:
        return not self.claim_id and bool(self.candidates)


def _mentions(text: str, name: str, *, fold_case: bool = False) -> bool:
    if not name.strip():
        return False
    pattern = rf"{_LEFT}{re.escape(name)}{_RIGHT}"
    return re.search(pattern, text, re.IGNORECASE if fold_case else 0) is not None


def resolve_target(mission: Any, claim_ids: tuple[str, ...]) -> MissionTarget:
    """Find the claim this mission is about by the ids its own text names.

    A claim id is matched literally and case-sensitively: ids are identifiers,
    and folding case would let a mission that says "the main result" target a
    claim someone named ``main``.

    Fields are consulted most-decisive first, and the first field that names any
    claim decides. ``acceptance_check`` leads because it is the one field whose
    declared job is to say what this mission has to make true. If that field
    names two claims the search *stops* rather than falling through to the
    title: letting a vaguer field break a tie the decisive one could not is
    guessing, and a fragment aimed at the wrong theorem is worse than no
    fragment — the Engineer cannot tell it is wrong, because it is internally
    consistent and about a real claim.
    """
    for field_name in MISSION_TARGET_FIELDS:
        text = str(getattr(mission, field_name, "") or "")
        if not text.strip():
            continue
        named = tuple(
            sorted({claim_id for claim_id in claim_ids if _mentions(text, claim_id)})
        )
        if len(named) == 1:
            return MissionTarget(claim_id=named[0], field=field_name)
        if named:
            return MissionTarget(field=field_name, candidates=named)
    return MissionTarget()


def project_mission_context(*, project_root: Path | str, mission: Any) -> str:
    """Render this mission's claim neighbourhood, or nothing.

    Returns ``""`` for the overwhelmingly common case: a project with no
    recorded mathematical state, or a mission that names no claim in it. A math
    mission must run normally in a project that has never written this file.
    """
    try:
        state = load_state(project_root)
    except MathStateError as exc:
        return _unreadable(exc, project_root)
    except Exception as exc:  # noqa: BLE001 - never raise into a mission
        return _unreadable(exc, project_root)

    try:
        claim_ids = tuple(claim.claim_id for claim in state.current_claims())
        if not claim_ids:
            return ""
        target = resolve_target(mission, claim_ids)
        if target.ambiguous:
            return _ambiguous(target)
        if not target.claim_id:
            return ""
        return _render(_payload(state, target))
    except Exception as exc:  # noqa: BLE001 - see the module docstring
        # A defect in this module must not take the mission down with it, and
        # must not look like "the project believes nothing" either.
        return _unreadable(exc, project_root)


# -- degraded readings -------------------------------------------------------

def _scrub(text: str, project_root: Path | str) -> str:
    """Strip the host's absolute paths out of a message bound for a prompt.

    ``research_math`` formats its errors with the real path, which differs by
    host and by worktree. Leaving it in would make two identical failures render
    differently and would leak the operator's directory layout into the prompt.
    """
    root = str(Path(str(project_root)))
    return str(text).replace(f"{root}/", "").replace(root, ".")


def _unreadable(exc: BaseException, project_root: Path | str) -> str:
    return (
        "## Mathematical state unavailable\n"
        f"- `{_STATE_REF}` exists but could not be read: "
        f"{_scrub(exc, project_root) or type(exc).__name__}\n"
        "- Treat the recorded claim/evidence state as unknown, not as empty. "
        "Repair or report the file before recording anything into it; writing "
        "over an unreadable state loses every proof it held."
    )


def _ambiguous(target: MissionTarget) -> str:
    listed = ", ".join(f"`{claim_id}`" for claim_id in target.candidates[:_MAX_ROWS])
    return (
        "## Mathematical state not projected\n"
        f"- This mission's {target.field} names several recorded claims: {listed}.\n"
        "- No claim state is shown, because picking one of them would aim this "
        "context at a statement the mission may not be about, and the mistake "
        f"would be invisible. Read `{_STATE_REF}` directly, or restate the "
        "acceptance check so it names the single claim this round must move."
    )


# -- the projection ----------------------------------------------------------

def _clip(text: object, limit: int = _MAX_TEXT) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + " […clipped]"


def _rows(items: list[Any]) -> tuple[list[Any], int]:
    return items[:_MAX_ROWS], max(0, len(items) - _MAX_ROWS)


def _tiers(names: frozenset) -> str:
    return " or ".join(sorted(tier.value for tier in names))


def _named_definitions(
    context: ContextVersion | None, claim: ClaimVersion
) -> tuple[list[list[str]], list[str], int]:
    """Only the definitions the claim actually names, plus what was withheld.

    ``ContextVersion`` was written with this in mind — its docstring says the
    mapping exists "so that a later context projection can ship a claim only the
    definitions it names" — and it is what keeps this section's size a property
    of the claim rather than of the problem statement. Matched case-insensitively
    because a definition name is prose ("unit distance") and appears capitalized
    at the start of a sentence; claim ids, which are identifiers, are not.

    The match is still exact, so a definition the claim names in an inflected
    form ("unit distances") is withheld. That is why the withheld ones are
    *named* rather than counted: the reader can see that the definition exists
    and go read it, instead of being told the context is smaller than it is.
    Naming them is still bounded, by ``_MAX_ROWS``.
    """
    if context is None:
        return [], [], 0
    statement = f"{claim.natural_statement}\n{claim.formal_statement}"
    named: list[list[str]] = []
    withheld: list[str] = []
    for name, body in sorted(context.definitions.items()):
        if _mentions(statement, name, fold_case=True):
            named.append([name, _clip(body, _MAX_NEIGHBOUR_TEXT)])
        else:
            withheld.append(name)
    shown, more = _rows(withheld)
    return named, shown, more


def _payload(state: MathState, target: MissionTarget) -> dict[str, Any]:
    """Everything the fragment says, as plain data, so the digest covers it all.

    The rendering below reads only this mapping. That is what makes the digest
    honest: it cannot go stale against text that was assembled somewhere else,
    and ``content_digest`` sorts keys, so it cannot depend on insertion order.
    """
    claim_id = target.claim_id
    claim = state.latest_claim(claim_id)
    assert claim is not None  # target ids come from ``current_claims``
    assessment = state.assess(claim_id)
    everything = state.assess_all()
    current = claim.ref()

    context = next(
        (item for item in state.contexts if item.ref() == claim.context), None
    )
    latest_context = state.latest_context(claim.context.subject_id)
    definitions, withheld, further_withheld = _named_definitions(context, claim)

    open_ids = set(assessment.undischarged)
    standing = state.effective_assumptions(claim_id)
    open_assumptions = [
        {
            "assumption_id": item.assumption_id,
            "statement": _clip(item.statement, _MAX_NEIGHBOUR_TEXT),
            "source": _clip(item.source, _MAX_NEIGHBOUR_TEXT),
        }
        for item in standing
        if item.assumption_id in open_ids
    ]
    # Discharged assumptions are named but not restated: they are settled, and
    # what the mission needs from them is that they exist and are covered.
    discharged = [
        item.assumption_id for item in standing if item.assumption_id not in open_ids
    ]

    bound_evidence = [
        {
            "evidence_id": record.evidence_id,
            "tier": record.tier.value,
            "verdict": record.verdict.value,
            "produced_by": record.produced_by,
            "artifact": record.artifact,
        }
        for record in sorted(state.evidence, key=lambda item: item.evidence_id)
        if record.binds_to(current)
    ]

    live_routes: list[dict[str, Any]] = []
    retired_routes: list[dict[str, Any]] = []
    for route in sorted(state.routes, key=lambda item: item.route_id):
        if route.goal.subject_id != claim_id:
            continue
        appraisal = assess_route(route, everything)
        if route.retired_because.strip():
            retired_routes.append(
                {
                    "route_id": route.route_id,
                    "reason": _clip(route.retired_because, _MAX_NEIGHBOUR_TEXT),
                }
            )
            continue
        obligations, more_obligations = _rows(
            [
                _obligation_row(state, obligation, everything)
                for obligation in route.obligations
            ]
        )
        live_routes.append(
            {
                "route_id": route.route_id,
                "status": appraisal.status.value,
                "aims_at_current_statement": route.goal == current,
                "obligations": obligations,
                "further_obligations": more_obligations,
                "outstanding": list(appraisal.outstanding),
                "stale_obligations": list(appraisal.stale_obligations),
                "issues": list(appraisal.issues),
            }
        )

    live_rows, more_routes = _rows(live_routes)
    retired_rows, more_retired = _rows(retired_routes)
    evidence_rows, more_evidence = _rows(bound_evidence)
    return {
        "claim_id": claim_id,
        "version": claim.version,
        "status": assessment.status.value,
        "targeted_by": target.field,
        "natural_statement": _clip(claim.natural_statement),
        "formal_statement": _clip(claim.formal_statement),
        "context": {
            "context_id": claim.context.subject_id,
            "version": context.version if context is not None else 0,
            "recorded": context is not None,
            "current": (
                latest_context is not None and latest_context.ref() == claim.context
            ),
            "statement": _clip(context.statement) if context is not None else "",
            "definitions": definitions,
            "withheld_definitions": withheld,
            "further_withheld_definitions": further_withheld,
        },
        "open_assumptions": open_assumptions,
        "discharged_assumptions": discharged,
        "evidence": evidence_rows,
        "further_evidence": more_evidence,
        "stale_evidence": list(assessment.stale_evidence),
        "issues": list(assessment.issues),
        "routes": live_rows,
        "further_routes": more_routes,
        "retired_routes": retired_rows,
        "further_retired_routes": more_retired,
        "transitions": _transitions(assessment.status, bool(open_assumptions), claim),
    }


def _obligation_row(
    state: MathState, obligation: Any, everything: dict
) -> dict[str, Any]:
    """One dependency, as it stands now — depth 1 and no further.

    The statement shown is the *current* version's, not the one the route was
    built on, because that is the lemma anyone would go and work on. When the
    two differ the row says so: the route is still an idea, but it is no longer
    a plan for the claims it names.
    """
    latest = state.latest_claim(obligation.subject_id)
    appraisal = everything.get(obligation)
    return {
        "claim_id": obligation.subject_id,
        "status": (
            appraisal.status.value
            if appraisal is not None
            else "restated or removed since this route was recorded"
        ),
        "statement": (
            _clip(latest.natural_statement, _MAX_NEIGHBOUR_TEXT)
            if latest is not None
            else ""
        ),
    }


def _transitions(
    status: ClaimStatus, has_open_assumptions: bool, claim: ClaimVersion
) -> list[str]:
    """What could move this claim, phrased from the kernel's own gate sets.

    The tier names are read out of ``KERNEL_TIERS`` / ``DISCHARGING_TIERS`` /
    ``REFUTING_TIERS`` rather than written out here, so this text cannot drift
    away from the rule the assessment actually applies. If those sets ever
    widen, the sentence widens with them.
    """
    lines: list[str] = []
    if status is ClaimStatus.REFUTED:
        lines.append(
            "This claim is refuted. A refutation binds to this exact statement: "
            "restating the claim mints a new version and the refutation does not "
            "follow it, so a revision must be a real change of mathematics, not "
            "a way to get out from under the counterexample."
        )
        return lines
    if status is ClaimStatus.CLOSED_KERNEL:
        lines.append(
            "This claim is a closed kernel: nothing is left on faith. Any edit "
            "to its statement or formalization mints a new version with no "
            "evidence, so do not touch either without intending to re-prove it."
        )
        return lines
    if status in (ClaimStatus.PROPOSED, ClaimStatus.SUPPORTED):
        if not claim.formal_statement.strip():
            lines.append(
                "kernel status is unreachable while this claim has no formal "
                f"statement: {_tiers(KERNEL_TIERS)} evidence would have nothing "
                "to have checked, and is refused rather than counted."
            )
        lines.append(
            f"to conditional_kernel: record {_tiers(KERNEL_TIERS)} evidence that "
            "supports this exact statement, with an artifact that can be re-run."
        )
        lines.append(
            "to closed_kernel: the same, with every external assumption below "
            f"discharged by {_tiers(DISCHARGING_TIERS)} evidence."
        )
    if status is ClaimStatus.CONDITIONAL_KERNEL:
        lines.append(
            "to closed_kernel: discharge every open assumption below with "
            f"{_tiers(DISCHARGING_TIERS)} evidence addressed to that assumption. "
            "Deleting the assumption instead does not work and is refused: an "
            "assumption a claim has ever carried is carried until a revision "
            "records in writing why the proof does not need it."
        )
    lines.append(
        f"to refuted: {_tiers(REFUTING_TIERS)} evidence may say this is false, "
        "and outranks any amount of support. A referee's opinion may not."
    )
    return lines


# -- rendering ---------------------------------------------------------------

def _render(payload: dict[str, Any]) -> str:
    digest = content_digest(payload)
    context = payload["context"]
    lines = [
        f"## Mathematical state — claim `{payload['claim_id']}` "
        f"v{payload['version']} ({payload['status']})",
        "",
        f"Projected from `{_STATE_REF}`; fragment digest `{digest[:16]}`. This is "
        "one claim's neighbourhood, not the project: the definitions it names, "
        "what it still takes on faith, the verdicts recorded against this exact "
        "statement, and its immediate obligations. Other claims and retired "
        "branches are deliberately absent — do not infer from their absence that "
        "they do not exist.",
        "",
        f"- targeted by this mission's {payload['targeted_by']}",
        f"- statement: {payload['natural_statement'] or '(none recorded)'}",
    ]
    if payload["formal_statement"]:
        lines.append(f"- formalized as: {payload['formal_statement']}")
    else:
        lines.append("- formalized as: (nothing recorded)")
    for issue in payload["issues"]:
        lines.append(f"- ISSUE: {issue}")

    lines.append("")
    if not context["recorded"]:
        lines.append(
            f"### Context `{context['context_id']}` — not in this state\n"
            "The version this claim is stated against is not recorded, so what "
            "its terms mean is written down nowhere. Do not guess the "
            "definitions."
        )
    else:
        freshness = "current" if context["current"] else "SUPERSEDED"
        lines.append(
            f"### Context `{context['context_id']}` v{context['version']} "
            f"({freshness})"
        )
        if not context["current"]:
            lines.append(
                "This claim is stated against definitions the project has since "
                "revised. It is not wrong; it is undecided whether it survives "
                "the new ones."
            )
        lines.append(f"- problem: {context['statement'] or '(none recorded)'}")
        for name, body in context["definitions"]:
            lines.append(f"- `{name}`: {body}")
        if context["withheld_definitions"]:
            withheld = ", ".join(
                f"`{name}`" for name in context["withheld_definitions"]
            )
            tail = (
                f" and {context['further_withheld_definitions']} more"
                if context["further_withheld_definitions"]
                else ""
            )
            lines.append(
                f"- also defined here, not named by the claim, withheld: "
                f"{withheld}{tail}."
            )

    lines.append("")
    if payload["open_assumptions"]:
        lines.append(
            f"### Taken on faith ({len(payload['open_assumptions'])} open)"
        )
        for item in payload["open_assumptions"]:
            lines.append(
                f"- `{item['assumption_id']}`: {item['statement']} "
                f"[source: {item['source']}]"
            )
    else:
        lines.append("### Taken on faith: nothing open")
    if payload["discharged_assumptions"]:
        lines.append(
            "- discharged (still listed, still covered): "
            + ", ".join(f"`{item}`" for item in payload["discharged_assumptions"])
        )

    lines.append("")
    lines.append("### Evidence bound to this exact statement")
    if payload["evidence"]:
        for record in payload["evidence"]:
            artifact = record["artifact"] or "no artifact recorded"
            lines.append(
                f"- `{record['evidence_id']}` {record['tier']}/{record['verdict']} "
                f"by `{record['produced_by']}` — {artifact}"
            )
    else:
        lines.append("- none. Nothing has checked this statement as it now stands.")
    if payload["further_evidence"]:
        lines.append(f"- and {payload['further_evidence']} more, not listed here.")
    if payload["stale_evidence"]:
        lines.append(
            "- recorded against an EARLIER version of this claim, and therefore "
            "not evidence for it: "
            + ", ".join(f"`{item}`" for item in payload["stale_evidence"])
        )

    lines.append("")
    lines.append("### Immediate proof obligations (one hop)")
    if payload["routes"]:
        for route in payload["routes"]:
            head = f"- route `{route['route_id']}` ({route['status']})"
            if not route["aims_at_current_statement"]:
                head += " — aims at an earlier version of this claim"
            lines.append(head)
            for obligation in route["obligations"]:
                row = f"  - `{obligation['claim_id']}`: {obligation['status']}"
                if obligation["statement"]:
                    row += f" — {obligation['statement']}"
                lines.append(row)
            if route["further_obligations"]:
                lines.append(
                    f"  - and {route['further_obligations']} more obligation(s)."
                )
            for issue in route["issues"]:
                lines.append(f"  - ISSUE: {issue}")
    else:
        lines.append(
            "- no route recorded for this claim. There is no plan on file; "
            "producing one is legitimate work."
        )
    if payload["further_routes"]:
        lines.append(f"- and {payload['further_routes']} more route(s), not listed.")

    if payload["retired_routes"]:
        lines.append("")
        lines.append("### Already retired — do not retry without new reason")
        for route in payload["retired_routes"]:
            lines.append(f"- `{route['route_id']}`: {route['reason']}")
        if payload["further_retired_routes"]:
            lines.append(
                f"- and {payload['further_retired_routes']} more retired route(s)."
            )

    lines.append("")
    lines.append("### What can change this claim's status")
    lines.extend(f"- {line}" for line in payload["transitions"])
    return "\n".join(lines)
