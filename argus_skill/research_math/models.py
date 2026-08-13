"""The entities a mathematical result is made of, and what binds them together.

Four record types, and one rule that shapes all four.

**The rule: evidence binds to content, never to a version number and never to a
timestamp.** A verifier answers a question about a specific statement. If the
statement later changes, the answer is about something that no longer exists,
and the only way to know that mechanically is to carry the digest of what was
asked. ``verticals/math/lean_evidence.py`` already learned this for one Lean
file (``source_sha256``, and the cache key that had to stop trusting mtime
because ``os.utime`` could forge it). Here the same binding is the schema's
spine rather than one field on one checker.

Three consequences follow, and each is a deliberate design choice rather than
an accident of implementation:

*Revising a claim cannot silently inherit its old certificate.* A new version
recomputes its digest; every evidence record still points at the old one, so it
is visibly stale instead of quietly authoritative. This is the mechanical form
of the goal document's "an old Lean result must not certify a new version".

*A version that says the same thing keeps its evidence.* Version numbers are
not in the digest, so renumbering, reordering, or re-recording a claim whose
mathematics is unchanged does not throw away a proof that took an hour to
compile. Freshness is a question about meaning, not about bookkeeping.

*External assumptions are outside the digest.* Discovering that a proof leans
on an uncited theorem, or discharging that dependency later, changes what is
known *about* the claim, not what the claim asserts. If assumptions were
hashed, discharging one would invalidate the very Lean run it is supposed to
upgrade — the ``conditional_kernel`` to ``closed_kernel`` transition would be
unreachable by construction. Discharge is therefore evidence about the
assumption, addressed by the assumption's own digest, and it never edits the
claim.

That third consequence cuts both ways, and the other edge is sharp: if adding
an assumption cannot disturb a proof, neither can *deleting* one, so a claim
could be promoted to ``closed_kernel`` by removing the line that was holding it
back. ``RetiredAssumption`` and the history walk in ``store.MathState`` close
that path, because it is the direction with a motive behind it.

Nothing here imports anything from Argus. That is checked mechanically by
``tests/research_math/test_research_math_kernel.py``; the package is meant to
be liftable into its own repository unchanged.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

__all__ = [
    "ClaimVersion",
    "ContextVersion",
    "EvidenceRecord",
    "EvidenceTier",
    "ExternalAssumption",
    "ProofRoute",
    "RetiredAssumption",
    "SubjectKind",
    "SubjectRef",
    "Verdict",
    "content_digest",
    "normalize_text",
]


# -- identity ----------------------------------------------------------------

class SubjectKind(str, Enum):
    """What an evidence record or a route can point at.

    One reference type covers all three rather than a ``ClaimRef``/
    ``ContextRef``/``AssumptionRef`` family, because every consumer asks the
    same question of a reference — "does this still describe something that
    exists?" — and three near-identical types would answer it three times.
    """

    CONTEXT = "context"
    CLAIM = "claim"
    ASSUMPTION = "assumption"


@dataclass(frozen=True)
class SubjectRef:
    """A pointer to *what a record was about at the moment it was recorded*.

    The digest is the load-bearing part. ``subject_id`` alone would let an
    answer about one statement attach itself to the next statement wearing the
    same name, which is precisely the failure the version binding exists to
    prevent. Two refs are equal exactly when they name the same thing saying
    the same thing, so freshness is ``==`` and needs no policy.
    """

    kind: SubjectKind
    subject_id: str
    content_hash: str

    def as_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind.value,
            "subject_id": self.subject_id,
            "content_hash": self.content_hash,
        }

    @classmethod
    def from_dict(cls, payload: object) -> SubjectRef:
        if not isinstance(payload, Mapping):
            raise ValueError("a subject reference must be an object")
        return cls(
            kind=SubjectKind(str(payload.get("kind") or "")),
            subject_id=str(payload.get("subject_id") or ""),
            content_hash=str(payload.get("content_hash") or ""),
        )


def normalize_text(text: object) -> str:
    """Fold away formatting that carries no mathematics, and nothing else.

    Trailing whitespace and a trailing newline are the difference between a
    file an editor saved and the same file after a reformat. Letting either
    change a digest would invalidate a compiled proof for a cosmetic edit, and
    a system that cries stale on cosmetic edits gets its staleness signal
    ignored. Interior whitespace is preserved: in a formal statement it can be
    the difference between two terms.
    """
    return "\n".join(line.rstrip() for line in str(text or "").strip().splitlines())


def content_digest(payload: Mapping[str, Any]) -> str:
    """A digest over canonical JSON — stable across processes and orderings.

    Deliberately excludes any schema or release version. A digest that moved
    when this file changed would invalidate every recorded proof on every
    upgrade, which would make the binding worthless exactly when a long-running
    project needs it. What is hashed is the mathematics; how it is stored is
    versioned separately, in the state file.
    """
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _require_kind(ref: SubjectRef, kind: SubjectKind, role: str) -> None:
    if ref.kind is not kind:
        raise ValueError(
            f"{role} must reference a {kind.value}, not a {ref.kind.value}"
        )


# -- the problem ------------------------------------------------------------

@dataclass(frozen=True)
class ContextVersion:
    """The problem statement and definitions every claim is asserted against.

    This exists as a first-class record because a definition change is the
    quietest way for a project to start proving a different theorem than the
    one it set out to prove. A claim references a context *by digest*, so a
    revised definition does not silently reinterpret the claims below it —
    they keep pointing at the version they were stated against, and
    ``store.MathState.validate`` reports each one as standing on a superseded
    context. Restating a claim against the new version changes the claim's own
    digest, which is where its evidence goes stale. Both halves are mechanical;
    neither depends on anyone remembering.

    ``definitions`` is a mapping rather than more prose so that a later context
    projection can ship a claim only the definitions it names. In this package
    the keys have exactly one mechanical job: they are part of the digest, so
    renaming a definition is a change to the problem.
    """

    context_id: str
    version: int
    statement: str
    definitions: dict[str, str] = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        return content_digest(
            {
                "context_id": self.context_id,
                "statement": normalize_text(self.statement),
                "definitions": {
                    str(name): normalize_text(body)
                    for name, body in sorted(self.definitions.items())
                },
            }
        )

    def ref(self) -> SubjectRef:
        """How claims point at this context. Carries no version number.

        Two versions that say the same thing produce the same reference, so a
        revision that only renumbers does not orphan the work below it.
        """
        return SubjectRef(SubjectKind.CONTEXT, self.context_id, self.content_hash)

    def as_dict(self) -> dict[str, Any]:
        return {
            "context_id": self.context_id,
            "version": self.version,
            "statement": self.statement,
            "definitions": dict(self.definitions),
            "content_hash": self.content_hash,
        }

    @classmethod
    def from_dict(cls, payload: object) -> ContextVersion:
        if not isinstance(payload, Mapping):
            raise ValueError("a context version must be an object")
        definitions = payload.get("definitions") or {}
        if not isinstance(definitions, Mapping):
            raise ValueError("context definitions must be an object")
        return cls(
            context_id=str(payload.get("context_id") or ""),
            version=int(payload.get("version") or 0),
            statement=str(payload.get("statement") or ""),
            definitions={str(k): str(v) for k, v in definitions.items()},
        )


# -- what a claim is standing on --------------------------------------------

@dataclass(frozen=True)
class ExternalAssumption:
    """A result imported from outside whose hypotheses are not yet checked here.

    This is the math-specific part of the schema. A proof that cites a theorem
    from the literature is not wrong, but it is not self-contained either, and
    the difference is invisible in prose: "by Theorem 3.1 of [K]" reads exactly
    the same whether or not Theorem 3.1's hypotheses actually hold in this
    setting. Recording it as a record makes the difference queryable, and it is
    what keeps a claim at ``conditional_kernel``.

    There is no ``discharged`` flag. A boolean is four keystrokes, and this
    package's whole reason for existing is that four keystrokes must not be
    able to certify anything. Discharge is an evidence record addressed to
    ``ref()`` — which means the check is "who established this, with what, and
    is that answer still about this statement", and it means discharging never
    edits the claim.

    ``source`` is required rather than decorative: an assumption nobody can
    look up cannot be discharged and cannot be audited, so it is not an
    assumption, it is a gap in the proof wearing a citation's clothes.
    """

    assumption_id: str
    statement: str
    source: str

    @property
    def content_hash(self) -> str:
        return content_digest(
            {
                "assumption_id": self.assumption_id,
                "statement": normalize_text(self.statement),
                "source": normalize_text(self.source),
            }
        )

    def ref(self) -> SubjectRef:
        """Correcting a citation or a statement produces a different reference.

        So a discharge obtained against the wrong theorem number does not
        survive the correction.
        """
        return SubjectRef(
            SubjectKind.ASSUMPTION, self.assumption_id, self.content_hash
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "assumption_id": self.assumption_id,
            "statement": self.statement,
            "source": self.source,
            "content_hash": self.content_hash,
        }

    @classmethod
    def from_dict(cls, payload: object) -> ExternalAssumption:
        if not isinstance(payload, Mapping):
            raise ValueError("an external assumption must be an object")
        return cls(
            assumption_id=str(payload.get("assumption_id") or ""),
            statement=str(payload.get("statement") or ""),
            source=str(payload.get("source") or ""),
        )


@dataclass(frozen=True)
class RetiredAssumption:
    """Why a claim stopped standing on a result it used to stand on.

    This exists to close the one hole the digest design leaves open. Because
    assumptions are outside ``ClaimVersion.content_hash``, removing one leaves
    the digest untouched: a finished kernel verdict keeps binding, the
    dependency disappears, and the claim quietly becomes ``closed_kernel``.
    That is the direction with the motive behind it — ``closed_kernel`` is
    scarce and expensive, and one deleted line would otherwise buy it. It is
    also the exact failure this package exists to prevent, arriving through the
    schema's own front door rather than through a forged field.

    So a removal has to say something. There is one honest reason to drop an
    assumption — the proof turns out not to need it — and that is a
    mathematical judgement, which is the kind of thing this package records
    rather than one it lets a field assignment imply. "It was discharged" is
    *not* a reason to remove it: a discharged assumption stays where it is,
    covered by the evidence that discharged it, or the project loses the
    dependency and the proof of it in the same edit.

    ``content_hash`` names the exact assumption being dropped, so a reason
    written about one statement cannot authorize dropping a different statement
    that inherited the id. ``store.MathState`` reads it, and a retirement that
    matches nothing retires nothing.

    The reason is prose and no machine checks it. What is mechanical is that
    the removal cannot happen in silence — a false reason is a reviewable lie
    in a diff, where a silent deletion was nothing at all.
    """

    assumption_id: str
    content_hash: str
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "assumption_id": self.assumption_id,
            "content_hash": self.content_hash,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, payload: object) -> RetiredAssumption:
        if not isinstance(payload, Mapping):
            raise ValueError("a retired assumption must be an object")
        return cls(
            assumption_id=str(payload.get("assumption_id") or ""),
            content_hash=str(payload.get("content_hash") or ""),
            reason=str(payload.get("reason") or ""),
        )


@dataclass(frozen=True)
class ClaimVersion:
    """One mathematical assertion, as it stood at one point in the project.

    Versions are never edited in place — ``store.MathState.revise_claim`` mints
    the next one — because the history is the only place a project can look to
    answer "what did we believe when we ran that check".

    ``formal_statement`` is the text of the formalization, not a path to it,
    for one reason: it belongs in the digest. A formalization that is silently
    retranslated is the failure mode the principles document calls out (Lean
    will happily prove a mistranslated statement), and holding the text here
    makes a retranslation a new claim version with no evidence, rather than the
    same claim with an unchanged certificate.

    ``status`` is not a field. It is derived in ``assessment.assess_claim``
    from the evidence and the assumptions, so ``closed_kernel`` cannot be
    asserted — it can only be earned. That is what makes the transition rule
    true by construction rather than by a check somebody has to remember to
    call.

    ``retired_assumptions`` records what this revision stopped depending on and
    why. It is the counterweight to keeping assumptions out of the digest: a
    version that drops an assumption without one is not believed to have
    dropped it, and ``store.MathState`` goes on counting it.
    """

    claim_id: str
    version: int
    context: SubjectRef
    natural_statement: str
    formal_statement: str = ""
    external_assumptions: tuple[ExternalAssumption, ...] = ()
    retired_assumptions: tuple[RetiredAssumption, ...] = ()

    def __post_init__(self) -> None:
        _require_kind(self.context, SubjectKind.CONTEXT, "a claim's context")

    @property
    def content_hash(self) -> str:
        """Covers the mathematics and the context. Not the assumptions.

        Assumptions are what the *proof* leans on, not what the claim asserts;
        including them would mean that discharging one invalidated the proof it
        was meant to complete. Retirements are excluded for the same reason and
        one more: they do not accumulate in the digest, so a version that
        retires nothing would hash identically to one before the retirement,
        and evidence would come back from the dead.
        """
        return content_digest(
            {
                "claim_id": self.claim_id,
                "natural_statement": normalize_text(self.natural_statement),
                "formal_statement": normalize_text(self.formal_statement),
                "context_hash": self.context.content_hash,
            }
        )

    def ref(self) -> SubjectRef:
        return SubjectRef(SubjectKind.CLAIM, self.claim_id, self.content_hash)

    def assumption(self, assumption_id: str) -> ExternalAssumption | None:
        for item in self.external_assumptions:
            if item.assumption_id == assumption_id:
                return item
        return None

    def as_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "version": self.version,
            "context": self.context.as_dict(),
            "natural_statement": self.natural_statement,
            "formal_statement": self.formal_statement,
            "external_assumptions": [
                item.as_dict() for item in self.external_assumptions
            ],
            "retired_assumptions": [
                item.as_dict() for item in self.retired_assumptions
            ],
            "content_hash": self.content_hash,
        }

    @classmethod
    def from_dict(cls, payload: object) -> ClaimVersion:
        if not isinstance(payload, Mapping):
            raise ValueError("a claim version must be an object")
        assumptions = payload.get("external_assumptions") or []
        if not isinstance(assumptions, list):
            raise ValueError("external_assumptions must be a list")
        retired = payload.get("retired_assumptions") or []
        if not isinstance(retired, list):
            raise ValueError("retired_assumptions must be a list")
        return cls(
            claim_id=str(payload.get("claim_id") or ""),
            version=int(payload.get("version") or 0),
            context=SubjectRef.from_dict(payload.get("context")),
            natural_statement=str(payload.get("natural_statement") or ""),
            formal_statement=str(payload.get("formal_statement") or ""),
            external_assumptions=tuple(
                ExternalAssumption.from_dict(item) for item in assumptions
            ),
            retired_assumptions=tuple(
                RetiredAssumption.from_dict(item) for item in retired
            ),
        )


# -- evidence ---------------------------------------------------------------

class EvidenceTier(str, Enum):
    """Which *kind* of check produced an answer — not how much it is worth.

    The principles document's sharpest constraint is that ten similar LLM
    judges are not ten independent verifiers: a prover and a critic drawn from
    the same model family share their blind spots, so their agreement is not
    evidence of anything. The schema answers that by keeping the channels
    apart and never letting them be added up. There is no confidence score and
    no rank ladder anywhere in this package; ``assessment`` reports *which*
    channels answered, and the gates in ``assessment`` name the specific tiers
    they require by set membership.

    That is a deliberate departure from the rank ladder in Argus's own
    ``core/project_api.py``, which orders sources from weak to strong and, in
    practice, never rejects anything.

    ``mechanical`` — a proof kernel: an independent implementation whose errors
    are uncorrelated with the model's. Lean.

    ``computational`` — executed code, CAS, SMT. Can refute outright with a
    finite counterexample; can never establish a universally quantified claim,
    however many cases it checks.

    ``literature`` — an assertion about what a source says. Independent of the
    model's reasoning, but only as good as the retrieval, and it answers a
    different question than a proof does.

    ``judgement`` — an LLM referee. Useful for finding conceptual gaps, and the
    one channel whose errors correlate with the producer's, which is why
    nothing in this package lets it reach kernel status or discharge an
    assumption no matter how many records agree.
    """

    MECHANICAL = "mechanical"
    COMPUTATIONAL = "computational"
    LITERATURE = "literature"
    JUDGEMENT = "judgement"


class Verdict(str, Enum):
    """What one channel concluded. ``inconclusive`` is a first-class answer.

    A checker that ran and could not decide has said something different from a
    checker that was never run, and collapsing the two is how a project ends up
    believing an environment failure was a pass.
    """

    SUPPORTS = "supports"
    REFUTES = "refutes"
    INCONCLUSIVE = "inconclusive"


#: Tiers whose records must name an artifact. A mechanical verdict with
#: nothing to re-inspect is an unfalsifiable certificate — the exact shape
#: ``lean_evidence._schema_problems`` exists to reject. A judgement is exempt
#: because it is already labelled as the weakest channel and carries no gate.
ARTIFACT_REQUIRED_TIERS = frozenset(
    {EvidenceTier.MECHANICAL, EvidenceTier.COMPUTATIONAL, EvidenceTier.LITERATURE}
)


@dataclass(frozen=True)
class EvidenceRecord:
    """One channel's answer about one exact statement.

    Shaped to carry a Lean run, a script's output, a literature lookup, or a
    referee's opinion without any of them being able to impersonate another.
    The verifiers that produce these land in later PRs; what is fixed here is
    the envelope they have to fit.

    ``produced_by`` is not decoration. It is the independence key: a claim
    supported by six records from one referee has been checked once, and
    ``assessment`` reports distinct producers per tier so that fact is visible
    instead of being summed into a six.

    There is deliberately no timestamp. Nothing here decides anything from
    recency — staleness is decided by identity, via ``subject`` — and an unread
    time field is an invitation to start reasoning from modification order,
    which is the bug ``lean_evidence`` documents in its cache key.
    """

    evidence_id: str
    subject: SubjectRef
    tier: EvidenceTier
    verdict: Verdict
    produced_by: str
    artifact: str = ""

    def binds_to(self, subject: SubjectRef) -> bool:
        """Whether this answer is still about the thing being asked about."""
        return self.subject == subject

    def as_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "subject": self.subject.as_dict(),
            "tier": self.tier.value,
            "verdict": self.verdict.value,
            "produced_by": self.produced_by,
            "artifact": self.artifact,
        }

    @classmethod
    def from_dict(cls, payload: object) -> EvidenceRecord:
        if not isinstance(payload, Mapping):
            raise ValueError("an evidence record must be an object")
        return cls(
            evidence_id=str(payload.get("evidence_id") or ""),
            subject=SubjectRef.from_dict(payload.get("subject")),
            tier=EvidenceTier(str(payload.get("tier") or "")),
            verdict=Verdict(str(payload.get("verdict") or "")),
            produced_by=str(payload.get("produced_by") or ""),
            artifact=str(payload.get("artifact") or ""),
        )


# -- routes -----------------------------------------------------------------

@dataclass(frozen=True)
class ProofRoute:
    """One way the goal could follow: these obligations, all of them.

    A route is the AND; several routes for the same goal are the OR. Argus's
    backlog cannot express this — ``life/memory.py`` releases an item only once
    *every* dependency is ``done``, so alternatives are literally unsayable
    there — which is why routes live in this package rather than being modelled
    as backlog dependencies.

    Routes confer no status on their goal, and that is a rule rather than a
    gap: a route asserts that these obligations imply this goal, and nothing
    checks the implication. Promoting a goal because its decomposition is
    finished would let an agent mint a kernel status by writing a decomposition
    nobody verified. What a finished route does instead is get *reported* on
    its goal's assessment — see ``assessment.ClaimAssessment.with_routes``,
    which is also the one place to change when a verifier for the
    decomposition step exists.

    ``retired_because`` carries the reason rather than a flag, for the reason
    ``verticals/math/proof_graph.py`` already found the hard way: a route
    retired without a recorded reason gets retried. It is also what makes a
    circular attempt recordable — retired routes are outside the dependency
    graph, so writing down that A-via-B needs A is allowed, while planning it
    is not.
    """

    route_id: str
    goal: SubjectRef
    obligations: tuple[SubjectRef, ...] = ()
    retired_because: str = ""

    def __post_init__(self) -> None:
        _require_kind(self.goal, SubjectKind.CLAIM, "a route's goal")
        for obligation in self.obligations:
            _require_kind(obligation, SubjectKind.CLAIM, "a route's obligation")

    def as_dict(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id,
            "goal": self.goal.as_dict(),
            "obligations": [item.as_dict() for item in self.obligations],
            "retired_because": self.retired_because,
        }

    @classmethod
    def from_dict(cls, payload: object) -> ProofRoute:
        if not isinstance(payload, Mapping):
            raise ValueError("a proof route must be an object")
        obligations = payload.get("obligations") or []
        if not isinstance(obligations, list):
            raise ValueError("route obligations must be a list")
        return cls(
            route_id=str(payload.get("route_id") or ""),
            goal=SubjectRef.from_dict(payload.get("goal")),
            obligations=tuple(SubjectRef.from_dict(item) for item in obligations),
            retired_because=str(payload.get("retired_because") or ""),
        )
