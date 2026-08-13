"""What the records add up to — and the several things they deliberately do not.

A claim's status is computed here, never stored. Nothing writes
``closed_kernel`` into a file; it is what you get when a mechanical verdict
still binds to the current statement and no external assumption is left
standing. Making it derived rather than declared is what makes the transition
rule unforgeable: there is no field to set.

Three gates decide everything below, and each names the tiers it accepts by
set membership rather than by a threshold on a rank:

``KERNEL_TIERS`` — what makes a claim a kernel claim at all.

``DISCHARGING_TIERS`` — what closes an external assumption.

``REFUTING_TIERS`` — what is allowed to say a claim is false.

They are separate constants because they are separate questions. A finite
counterexample from executed code refutes a universally quantified claim
outright, and the same run establishes nothing about the general case, so
``computational`` belongs in one set and not the other. A referee's opinion
belongs in none of them: the failure the principles document names is a prover
and a critic from the same model family converging on an argument neither can
see through, and any gate an LLM verdict could pass reproduces it exactly.

The consequence is that ``closed_kernel`` is rare and expensive, since it
requires a mechanical discharge of every cited theorem. That is intended. A
``closed_kernel`` that were cheap to reach would carry no information, and the
honest state for most real research-level mathematics is
``conditional_kernel`` — proved, modulo named and citable external results.
Whether ``DISCHARGING_TIERS`` should ever widen is a question for data from a
real run, not for taste; it is one frozenset in one place when that data
arrives.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .models import (
    ClaimVersion,
    EvidenceRecord,
    EvidenceTier,
    ExternalAssumption,
    ProofRoute,
    SubjectRef,
    Verdict,
)

__all__ = [
    "DISCHARGING_TIERS",
    "ESTABLISHED_STATUSES",
    "KERNEL_TIERS",
    "REFUTING_TIERS",
    "ClaimAssessment",
    "ClaimStatus",
    "RouteAssessment",
    "RouteStatus",
    "assess_claim",
    "assess_route",
]

#: An independent implementation whose errors are uncorrelated with the
#: model's. Only a proof kernel qualifies.
KERNEL_TIERS = frozenset({EvidenceTier.MECHANICAL})

#: What discharges a cited theorem. Formalizing it, or nothing — a literature
#: lookup establishes that a paper says something, and an LLM reading
#: establishes that a paper seems to say something, and neither establishes
#: that its hypotheses hold here. That last question is a statement-fidelity
#: question, and the principles document's rule is that the agent doing the
#: work cannot issue its own fidelity certificate.
DISCHARGING_TIERS = frozenset({EvidenceTier.MECHANICAL})

#: What may declare a claim false. Wider than ``KERNEL_TIERS`` on purpose:
#: exhibiting one counterexample is a finite, checkable act, and refusing to
#: hear it until someone formalizes the refutation would keep a claim alive
#: that is already dead.
REFUTING_TIERS = frozenset({EvidenceTier.MECHANICAL, EvidenceTier.COMPUTATIONAL})


class ClaimStatus(str, Enum):
    """Five states, because the fifth and fourth must not be one state.

    The plan this package comes from proposed five orthogonal status
    dimensions. They are collapsed to one here: with no run-time data about
    which distinctions the system actually uses, five independent enums would
    be five schemas to migrate and one to read. The single distinction that is
    not negotiable survives — ``conditional_kernel`` versus ``closed_kernel``,
    which is where every unproved external dependency shows up.

    ``proposed`` — asserted; nothing has checked it.

    ``supported`` — some channel that is not a kernel says yes. This is where
    almost all of a live project sits, and it is not a proof.

    ``refuted`` — a counterexample or a kernel says no. Outranks every support:
    an argument and a counterexample cannot both stand, and preferring the
    argument is how a project keeps working on a dead claim.

    ``conditional_kernel`` — a kernel verdict binding to this exact statement,
    with at least one external assumption still open. Correct *modulo* results
    taken on faith from elsewhere.

    ``closed_kernel`` — the same, with nothing left on faith.
    """

    PROPOSED = "proposed"
    SUPPORTED = "supported"
    REFUTED = "refuted"
    CONDITIONAL_KERNEL = "conditional_kernel"
    CLOSED_KERNEL = "closed_kernel"


#: What a route may treat as an obligation it no longer has to prove. Kernel
#: states only: a route resting on informally supported lemmas has not been
#: discharged, and reporting it as discharged would be the arithmetic that
#: turns a chain of plausible steps into a proof.
ESTABLISHED_STATUSES = frozenset(
    {ClaimStatus.CONDITIONAL_KERNEL, ClaimStatus.CLOSED_KERNEL}
)


class RouteStatus(str, Enum):
    """``retired`` is not a failure state; it is the recorded reason not to retry."""

    OPEN = "open"
    DISCHARGED = "discharged"
    RETIRED = "retired"


@dataclass(frozen=True)
class ClaimAssessment:
    """Everything the records say about one claim, with nothing summed up.

    ``support`` maps each tier to the *distinct producers* that answered in it,
    rather than to a count. Six records from one referee show up as one tier
    with one producer, which is the honest rendering of what happened; a count
    of six would read like six checks.

    ``stale_evidence`` is reported rather than dropped. Silently discarding
    evidence that no longer binds would hide the most interesting event in the
    system — a statement moved under a finished verification — and
    ``lean_evidence`` records what happens to anything routed somewhere nobody
    reads.
    """

    claim_id: str
    version: int
    status: ClaimStatus
    undischarged: tuple[str, ...] = ()
    support: Mapping[EvidenceTier, tuple[str, ...]] = field(default_factory=dict)
    stale_evidence: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()

    @property
    def is_kernel(self) -> bool:
        return self.status in ESTABLISHED_STATUSES

    def as_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "version": self.version,
            "status": self.status.value,
            "undischarged": list(self.undischarged),
            "support": {
                tier.value: list(producers)
                for tier, producers in sorted(
                    self.support.items(), key=lambda item: item[0].value
                )
            },
            "stale_evidence": list(self.stale_evidence),
            "issues": list(self.issues),
        }


def _producers_by_tier(
    records: Iterable[EvidenceRecord],
) -> dict[EvidenceTier, tuple[str, ...]]:
    grouped: dict[EvidenceTier, list[str]] = {}
    for record in records:
        producers = grouped.setdefault(record.tier, [])
        name = record.produced_by.strip() or "<unnamed>"
        if name not in producers:
            producers.append(name)
    return {tier: tuple(sorted(names)) for tier, names in grouped.items()}


def _discharged(
    assumption_ref: SubjectRef, evidence: Iterable[EvidenceRecord]
) -> bool:
    return any(
        record.binds_to(assumption_ref)
        and record.verdict is Verdict.SUPPORTS
        and record.tier in DISCHARGING_TIERS
        for record in evidence
    )


def assess_claim(
    claim: ClaimVersion,
    evidence: Iterable[EvidenceRecord],
    *,
    inherited_assumptions: Iterable[ExternalAssumption] = (),
) -> ClaimAssessment:
    """Derive one claim's status from the records that still bind to it.

    Takes the whole evidence collection rather than a pre-filtered list on
    purpose: which records bind and which have gone stale is the answer this
    function exists to compute, and a caller that filtered first would have had
    to make that judgement already.

    ``inherited_assumptions`` are dependencies an earlier version of this claim
    carried and this version dropped without recording why. They count exactly
    as if they were still listed, which is what stops a deletion from buying a
    ``closed_kernel``. Working that out needs the claim's history, which one
    version does not have, so the caller supplies it —
    ``store.MathState.assess`` does; a caller assessing a single record in
    isolation passes nothing and gets the reading that record supports on its
    own.
    """
    records = list(evidence)
    current = claim.ref()
    fresh = [record for record in records if record.binds_to(current)]
    stale = tuple(
        sorted(
            record.evidence_id
            for record in records
            if not record.binds_to(current)
            and record.subject.kind is current.kind
            and record.subject.subject_id == current.subject_id
        )
    )

    issues: list[str] = []
    own_ids = {item.assumption_id for item in claim.external_assumptions}
    inherited = tuple(
        item
        for item in inherited_assumptions
        if item.assumption_id not in own_ids
    )
    standing = tuple(claim.external_assumptions) + inherited
    undischarged = tuple(
        assumption.assumption_id
        for assumption in standing
        if not _discharged(assumption.ref(), records)
    )

    if inherited:
        # Dropping a dependency is a mathematical assertion that the proof did
        # not need it. Unstated, it is not an assertion, so it does not hold.
        issues.append(
            "this version no longer lists "
            + ", ".join(sorted(item.assumption_id for item in inherited))
            + ", and no revision recorded why; the dependency still counts"
        )

    kernel_supports = [
        record
        for record in fresh
        if record.tier in KERNEL_TIERS and record.verdict is Verdict.SUPPORTS
    ]
    refutations = [
        record
        for record in fresh
        if record.tier in REFUTING_TIERS and record.verdict is Verdict.REFUTES
    ]
    supports = [record for record in fresh if record.verdict is Verdict.SUPPORTS]

    if kernel_supports and any(
        record.tier in KERNEL_TIERS for record in refutations
    ):
        # Two kernels cannot both be right about the same statement. Reporting
        # a winner here would bury the only fact worth acting on.
        issues.append(
            "a proof kernel both supports and refutes this exact statement; one "
            "of the two records is not about the mathematics it names"
        )

    if kernel_supports and not claim.formal_statement.strip():
        # Somebody recorded a kernel verdict about a claim that has no
        # formalization to have been checked. Withholding kernel status is the
        # only safe reading.
        issues.append(
            "kernel evidence is recorded for a claim with no formal statement, "
            "so there is nothing the kernel could have checked"
        )

    if refutations:
        status = ClaimStatus.REFUTED
    elif kernel_supports and claim.formal_statement.strip():
        status = (
            ClaimStatus.CONDITIONAL_KERNEL
            if undischarged
            else ClaimStatus.CLOSED_KERNEL
        )
    elif supports:
        status = ClaimStatus.SUPPORTED
    else:
        status = ClaimStatus.PROPOSED

    return ClaimAssessment(
        claim_id=claim.claim_id,
        version=claim.version,
        status=status,
        undischarged=undischarged,
        support=_producers_by_tier(supports),
        stale_evidence=stale,
        issues=tuple(issues),
    )


@dataclass(frozen=True)
class RouteAssessment:
    """What this route still needs, and whether it is still about this problem."""

    route_id: str
    status: RouteStatus
    outstanding: tuple[str, ...] = ()
    stale_obligations: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id,
            "status": self.status.value,
            "outstanding": list(self.outstanding),
            "stale_obligations": list(self.stale_obligations),
            "issues": list(self.issues),
        }


def assess_route(
    route: ProofRoute, assessments: Mapping[SubjectRef, ClaimAssessment]
) -> RouteAssessment:
    """Which obligations are left, keyed by reference so a moved statement shows.

    ``assessments`` is keyed by ``SubjectRef``, not by claim id, which is what
    makes the second question answerable: an obligation whose id is present but
    whose digest is not means the lemma this route was built on has been
    restated. That route may still be a good idea, but it is no longer a plan
    for the claims it names, and a status of ``open`` alone would not say so.
    """
    outstanding: list[str] = []
    stale: list[str] = []
    issues: list[str] = []

    if route.goal not in assessments:
        issues.append(
            "this route's goal is not a current claim, so it aims at a statement "
            "that has been restated or removed"
        )

    for obligation in route.obligations:
        assessment = assessments.get(obligation)
        if assessment is None:
            stale.append(obligation.subject_id)
        elif assessment.status not in ESTABLISHED_STATUSES:
            outstanding.append(obligation.subject_id)

    if route.retired_because.strip():
        status = RouteStatus.RETIRED
    elif outstanding or stale or issues:
        status = RouteStatus.OPEN
    elif not route.obligations:
        # A route with no obligations asserts the goal follows from nothing.
        issues.append(
            "this route lists no obligations, so it records no plan; a route "
            "that needs nothing proved is not a route"
        )
        status = RouteStatus.OPEN
    else:
        status = RouteStatus.DISCHARGED

    return RouteAssessment(
        route_id=route.route_id,
        status=status,
        outstanding=tuple(sorted(dict.fromkeys(outstanding))),
        stale_obligations=tuple(sorted(dict.fromkeys(stale))),
        issues=tuple(issues),
    )
