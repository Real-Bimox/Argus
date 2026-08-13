"""The write path into the research-math kernel, and the one thing it refuses.

``argus_skill/research_math/`` can express everything a mathematics project
believes and derive what that adds up to. Until this module there was no way to
put anything into it from a real run: the package had a store, an assessment,
and no writer, so ``research/MATH_STATE.json`` was a file that only tests ever
created. This is the writer.

**The rule this module exists to enforce.** ``MathState.add_evidence`` takes any
tier, because a legitimate producer of each one has to be able to reach it. That
makes the *command surface* the place where tiers are decided, and it decides
them like this:

    A tier may only be written by a program that performed a check of that kind.

``judgement`` is the one tier whose checker is the agent, so it is the one tier
an agent-facing command writes. ``mechanical`` is written by
``record_lean_evidence`` below, which is reachable only from a command path that
compiles the source first — the tier is chosen by the code that read the
compiler's answer, never by an argument. ``computational`` and ``literature``
have no producer in this tree yet, so no command writes them; when a verifier
for either exists, it becomes the producer, exactly as ``lean_evidence`` is the
producer here.

Withholding ``literature`` is the choice that needs defending, because unlike
the other two it confers nothing: it is in none of ``KERNEL_TIERS``,
``DISCHARGING_TIERS``, or ``REFUTING_TIERS``, so an agent-written literature
record could not promote or refute anything. Banning it buys no status
protection. What it protects is the tier's meaning. The entire content of
``literature`` is the claim that a channel *independent of the model's
reasoning* answered — and when an agent types it, the party asserting the
independence is the party whose independence is in question. That is precisely
the failure the principles document reports as surviving every retrieval
harness: the paper exists, and the theorem it is said to contain is not in it,
or its hypotheses were quoted wrong. Recorded as ``judgement``, that same
finding is honest and loses nothing, since neither tier confers status; recorded
as ``literature``, it is an opinion wearing the label of the one channel that is
not one. And there is no way back: ``EvidenceRecord`` has no timestamp and
``produced_by`` is free text, so a citation verifier arriving later could not
tell its own records from the ones typed before it existed. Cheap to withhold,
unfalsifiable to un-mix.

**Where this lives, and why not in the kernel.** ``argparse`` is standard
library, so this CLI could have lived inside ``research_math/`` and travelled
with it. Two things decided against it. The first is the lock: every command
below is a read-modify-write over one JSON file, so without one, two rounds
writing at once lose one of the two writes — and the only lock in this
repository is ``core/file_lock.py``, which ``research_math/`` may not import
without giving up the property its whole design is built on. A hand-rolled
``fcntl``/``msvcrt`` fork inside the kernel would be a second, weaker copy of
something this repository already has one of, and the kernel's own store
docstring says that adding a lock before the writer existed would be guessing at
its shape. The writer now exists; it is this module; the guess is unnecessary.
The second is that the tier rule above is *policy about this host's agents*, and
the kernel is deliberately policy-free about who writes what — it has to be, or
``lean_evidence`` could not write ``mechanical`` through the same API. Policy
belongs on the vertical side, next to ``lean_evidence`` and
``literature_ledger``, which is also where a reader looking for "how does a math
agent record a claim" will look.

The kernel loses nothing by having no CLI: a library lifted into another
repository arrives with that repository's own entry points, whereas a CLI that
cannot lock would be a defect it inherits.

**Reads take no lock.** ``show`` and ``check`` call ``load_state`` directly.
``save_state`` publishes through ``os.replace``, so a reader sees either the
whole previous state or the whole next one, never a torn file; paying for a lock
to serialize against a write that is already atomic would only make the common
operation slower.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...core.file_lock import exclusive_file_lock
from ...research_math import (
    STATE_RELPATH,
    ClaimVersion,
    ContextVersion,
    EvidenceRecord,
    EvidenceTier,
    ExternalAssumption,
    MathState,
    MathStateError,
    ProofRoute,
    SubjectRef,
    Verdict,
    content_digest,
    load_state,
    normalize_text,
    save_state,
    state_path,
)

__all__ = [
    "AGENT_WRITABLE_TIERS",
    "LeanRecording",
    "locked_state",
    "main",
    "record_lean_evidence",
]

#: The tiers a command may take from an agent. Exactly the one whose checker is
#: the agent. Widening this set is the change that would make ``closed_kernel``
#: reachable by typing, so it is asserted by name in
#: ``tests/research_math/test_math_state_cli.py``.
AGENT_WRITABLE_TIERS = frozenset({EvidenceTier.JUDGEMENT})

#: Where the state file lives, rendered the way a message should refer to it.
_STATE_REF = "/".join(STATE_RELPATH)

#: Issue codes from ``lean_evidence`` that mean the recorded compiler answer is
#: not usable as evidence *about anything* — a forged, stale, unreadable, or
#: unexplained result. They are kept apart from the codes that mean the compiler
#: ran and the proof did not go through, because those two call for opposite
#: responses: the first records nothing, the second records an honest
#: ``inconclusive``.
_INADMISSIBLE_LEAN_CODES = frozenset({
    "lean_fidelity_changed",
    "lean_fidelity_empty",
    "lean_fidelity_missing",
    "lean_fidelity_unlinked",
    "lean_fidelity_unreadable",
    "lean_result_invalid",
    "lean_result_missing",
    "lean_result_stale",
    "lean_result_unreadable",
    "lean_source_external",
    "lean_source_unreadable",
})

#: Pulled out of a toolchain banner such as
#: ``Lean (version 4.34.0-rc1, x86_64-unknown-linux-gnu, commit 3447a66, Release)``.
#: The whole token is taken, prerelease suffix included: ``4.34.0-rc1`` is not
#: ``4.34.0``, and a producer string that says otherwise names a kernel that did
#: not answer.
_VERSION = re.compile(r"version\s+([^\s,)]+)")

#: Said on every kernel-status claim that carries Lean evidence. Not a defect,
#: so it is not an issue; not derivable from the records, so it cannot be a
#: kernel note. It is the standing caveat of the whole formal channel.
_FIDELITY_CAVEAT = (
    "a proof kernel established the formal statement recorded on this claim; "
    "nothing has checked that the formal statement says what the natural "
    "statement says, and no tier in this schema encodes that it has"
)


# -- serialized writes -------------------------------------------------------

@contextmanager
def locked_state(project_root: Path | str) -> Iterator[MathState]:
    """Read, mutate, and publish the state as one indivisible step.

    The lock is taken on a sibling ``.lock`` file rather than on the state file
    itself, and that is not fussiness: ``save_state`` publishes with
    ``os.replace``, which swaps the inode. A lock held on the old inode would
    still be held after the write, on a file that is no longer the state, so two
    writers could each hold "the lock" on a different generation of it.

    Nothing is written when the body raises. A command that refuses has to leave
    the file exactly as it found it, or a rejected write would still be half a
    write.
    """
    root = Path(str(project_root))
    path = state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".lock")
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(lock_path, flags, 0o600)
    with os.fdopen(descriptor, "a+b") as handle:
        with exclusive_file_lock(handle, lock_name=f"{_STATE_REF} lock"):
            state = load_state(root)
            yield state
            save_state(root, state)


# -- the tier gate -----------------------------------------------------------

def _agent_evidence(
    state: MathState,
    *,
    subject: SubjectRef,
    tier: EvidenceTier,
    verdict: Verdict,
    produced_by: str,
    artifact: str = "",
) -> tuple[EvidenceRecord, bool]:
    """The only way a command-line argument reaches ``add_evidence``.

    Every agent-facing write funnels through here so the tier rule is one
    comparison in one place rather than a habit spread over nine subcommands. A
    later ``--tier``, ``--force``, or environment override would still have to
    pass this line, which is what makes the guard an invariant rather than a
    description of today's flags.
    """
    if tier not in AGENT_WRITABLE_TIERS:
        raise MathStateError(
            f"{tier.value} evidence cannot be recorded from a command line. "
            "The tiers that confer kernel status are written by the program "
            "that ran the checker — mechanical by "
            "`lean_evidence verify --claim`, and nothing else. A tier typed by "
            "the agent whose work is being checked is the agent's opinion, "
            "which is what `judgement` is for"
        )
    record = EvidenceRecord(
        evidence_id=_evidence_id(
            tier.value, subject, tier, verdict, produced_by, artifact
        ),
        subject=subject,
        tier=tier,
        verdict=verdict,
        produced_by=produced_by,
        artifact=artifact,
    )
    return _append_evidence(state, record)


def _evidence_id(
    prefix: str,
    subject: SubjectRef,
    tier: EvidenceTier,
    verdict: Verdict,
    produced_by: str,
    artifact: str,
) -> str:
    """Derived from everything the record says, so re-recording is idempotent.

    An agent that repeats a command — and it will, since retrying is how an
    autonomous loop recovers — must not turn one opinion into two producers of
    the same opinion. Two ids differ exactly when the two answers differ, which
    is the reading ``assessment`` already puts on ``produced_by``.
    """
    digest = content_digest(
        {
            "subject": subject.as_dict(),
            "tier": tier.value,
            "verdict": verdict.value,
            "produced_by": normalize_text(produced_by),
            "artifact": normalize_text(artifact),
        }
    )
    return f"{prefix}-{subject.subject_id}-{digest[:12]}"


def _append_evidence(
    state: MathState, record: EvidenceRecord
) -> tuple[EvidenceRecord, bool]:
    existing = next(
        (item for item in state.evidence if item.evidence_id == record.evidence_id),
        None,
    )
    if existing is not None:
        if existing == record:
            return existing, False
        raise MathStateError(
            f"evidence {record.evidence_id!r} already names a different answer; "
            "the id is derived from the answer, so this is a digest collision "
            "and not a repeat"
        )
    state.add_evidence(record)
    return record, True


# -- Lean, the one real producer of mechanical evidence ----------------------

@dataclass(frozen=True)
class LeanRecording:
    """What became of one attempt to turn a compiler run into kernel evidence."""

    record: EvidenceRecord | None = None
    changed: bool = False
    refusals: tuple[str, ...] = ()
    statement_fidelity: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "recorded": self.record.as_dict() if self.record is not None else None,
            "changed": self.changed,
            "refusals": list(self.refusals),
            "statement_fidelity": {
                "document": self.statement_fidelity,
                "verified_by": None,
                "note": _FIDELITY_CAVEAT,
            },
        }


def record_lean_evidence(
    project_root: Path | str,
    *,
    claim_id: str,
    source: Path | str,
    expect_result: dict[str, Any] | None = None,
) -> LeanRecording:
    """Turn one compiler run into an ``EvidenceRecord``, or explain why not.

    This is where ``closed_kernel`` becomes reachable, and therefore where the
    conditions on reaching it have to be complete. Four of them, and each closes
    a specific way a record could certify something nobody checked:

    *The result has to be admissible.* Every check ``lean_evidence`` already
    performs is re-run against the filesystem — proof holes, the recorded
    result's schema, the source digest, and the fidelity document — and any
    finding in ``_INADMISSIBLE_LEAN_CODES`` records nothing at all. A
    ``lean_check.json`` that says ``success`` and does not agree with itself is
    the cheapest forgery available, and it must not become the most expensive
    status in the schema.

    *The claim has to record the text that was compiled.* Lean's answer is about
    the file it read. ``ClaimVersion.formal_statement`` is inside the claim's
    digest, so requiring the two to agree is what makes a later retranslation
    cost the certificate: editing the Lean file and restating the claim mints a
    new digest and the old record stops binding. Skipping this check would let a
    proof of one formal statement certify a claim carrying another.

    *The fidelity document has to exist, say something, name the declaration it
    describes, and be the one that was in force when the compiler ran.* The
    first three are ``lean_evidence``'s own checks; the fourth is the digest
    recorded by ``verify_lean_source``. None of them establishes that the
    document is *true* — nothing in this tree does, and the honest consequence
    is that no field anywhere says fidelity was verified. What they establish is
    that a specific, unedited statement of intent accompanies the certificate,
    so the unproved half of the argument is written down and pinned rather than
    absent. Without one, the compiler's answer is not evidence about a
    natural-language claim at all, and nothing is recorded.

    *A failed compile is ``inconclusive``, never ``refutes``.* Lean failing to
    derive a statement is not a proof that the statement is false, and
    ``REFUTING_TIERS`` includes ``mechanical`` — so writing ``refutes`` here
    would let a broken proof, a timeout, or a missing Mathlib mark a true
    theorem false. ``Verdict.INCONCLUSIVE`` is in the schema for exactly this:
    a checker that ran and could not decide has said something, and it is not
    what a checker that never ran said.

    ``expect_result`` pins the record to the run the caller just performed: the
    artifact lock is released once ``verify_lean_source`` returns, and between
    then and here another process could publish a different answer to the same
    path.
    """
    from .lean_evidence import source_evidence  # noqa: PLC0415 — avoids a cycle

    root = Path(str(project_root)).expanduser().resolve()
    source_path = Path(str(source)).expanduser().resolve()

    try:
        source_text = source_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return LeanRecording(refusals=(f"the Lean source cannot be read: {exc}",))

    evidence = source_evidence(source_path, root)
    fidelity = (
        _project_relative(evidence.fidelity, root)
        if evidence.fidelity is not None
        else ""
    )
    refusals = [
        issue.rendered()
        for issue in evidence.issues
        if issue.code in _INADMISSIBLE_LEAN_CODES
    ]
    result = evidence.result
    if result is None:
        return LeanRecording(
            refusals=tuple(refusals) or ("no compiler result was recorded",),
            statement_fidelity=fidelity,
        )
    if expect_result is not None and result != expect_result:
        refusals.append(
            "the recorded compiler result changed between the compile and this "
            "record, so it describes a run this command did not perform"
        )
    if not isinstance(result.get("statement_fidelity_sha256"), str) or not result[
        "statement_fidelity_sha256"
    ].strip():
        refusals.append(
            "the recorded result does not carry the digest of the statement "
            "fidelity document it was compiled against, so the unchecked half "
            "of this proof is not pinned to anything; re-run "
            "`lean_evidence verify`"
        )
    if refusals:
        return LeanRecording(
            refusals=tuple(refusals), statement_fidelity=fidelity
        )

    with locked_state(root) as state:
        claim = state.latest_claim(claim_id)
        if claim is None:
            return LeanRecording(
                refusals=(
                    f"no claim {claim_id!r} in {_STATE_REF}; record the claim "
                    "before recording a proof of it",
                ),
                statement_fidelity=fidelity,
            )
        if normalize_text(claim.formal_statement) != normalize_text(source_text):
            return LeanRecording(
                refusals=(
                    f"claim {claim_id!r} records a different formal statement "
                    "than the file that was compiled, so this result certifies "
                    "text the claim does not carry; run `math_state "
                    f"revise-claim --id {claim_id} --formal-file "
                    f"{_project_relative(source_path, root)}` first, which "
                    "restates the claim and drops the evidence bound to the "
                    "previous formalization",
                ),
                statement_fidelity=fidelity,
            )

        verdict = (
            Verdict.SUPPORTS
            if evidence.verified
            else Verdict.INCONCLUSIVE
        )
        artifact = _project_relative(
            evidence.result_path
            if evidence.result_path is not None
            else source_path.parent / "lean_check.json",
            root,
        )
        produced_by = _lean_producer(result)
        record = EvidenceRecord(
            evidence_id=_evidence_id(
                "lean",
                claim.ref(),
                EvidenceTier.MECHANICAL,
                verdict,
                produced_by,
                artifact,
            ),
            subject=claim.ref(),
            tier=EvidenceTier.MECHANICAL,
            verdict=verdict,
            produced_by=produced_by,
            artifact=artifact,
        )
        stored, changed = _append_evidence(state, record)

    return LeanRecording(
        record=stored, changed=changed, statement_fidelity=fidelity
    )


def _lean_producer(result: dict[str, Any]) -> str:
    """Name the proof kernel that answered, and nothing that varies per host.

    Always the ``lean`` entry, never ``tool`` — ``tool`` is ``lake`` whenever
    the compile went through a Lake workspace, and Lake is a build driver, not
    a kernel. The same Lean run twice, once bare and once under Lake, is one
    checker answering twice; ``produced_by`` is the independence key and is
    grouped on verbatim by ``assessment._producers_by_tier``, so recording the
    driver would let a re-run through a different front end look like a second
    independent confirmation.

    For the same reason the commit hash and build triple in the banner are
    dropped and the version is kept whole: ``4.34.0-rc1`` and ``4.34.0`` are
    different kernels and must not collapse together.
    """
    tools = result.get("tools")
    info = tools.get("lean") if isinstance(tools, dict) else None
    banner = str(info.get("version") or "") if isinstance(info, dict) else ""
    match = _VERSION.search(banner)
    return f"lean_evidence/lean {match.group(1)}" if match else "lean_evidence/lean"


def _project_relative(path: Path, project_root: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except (ValueError, OSError):
        return str(path)


# -- reading -----------------------------------------------------------------

def _claim_payload(state: MathState, claim: ClaimVersion) -> dict[str, Any]:
    assessment = state.assess(claim.claim_id)
    payload = assessment.as_dict()
    payload["formal_statement_recorded"] = bool(claim.formal_statement.strip())
    payload["standing_on"] = [
        item.as_dict() for item in state.effective_assumptions(claim.claim_id)
    ]
    if assessment.is_kernel:
        payload["caveats"] = [_FIDELITY_CAVEAT]
    return payload


def _show(project_root: Path, claim_id: str) -> dict[str, Any]:
    state = load_state(project_root)
    if claim_id:
        claim = state.latest_claim(claim_id)
        if claim is None:
            raise MathStateError(f"no claim {claim_id!r} in {_STATE_REF}")
        return {"ok": True, "claim": _claim_payload(state, claim)}
    return {
        "ok": True,
        "claims": [
            _claim_payload(state, claim) for claim in state.current_claims()
        ],
        "open_assumptions": {
            key: [item.assumption_id for item in items]
            for key, items in sorted(state.open_assumptions().items())
        },
        "issues": [issue.as_dict() for issue in state.validate()],
    }


# -- the commands ------------------------------------------------------------

def _pair(raw: str, what: str) -> tuple[str, str]:
    name, separator, body = str(raw).partition("=")
    if not separator or not name.strip():
        raise MathStateError(f"{what} must be written NAME=VALUE, not {raw!r}")
    return name.strip(), body


def _require_context(state: MathState, context_id: str) -> ContextVersion:
    context = state.latest_context(context_id)
    if context is None:
        raise MathStateError(
            f"no context {context_id!r}; record the problem statement its terms "
            "are defined against before stating a claim about it"
        )
    return context


def _require_claim(state: MathState, claim_id: str) -> ClaimVersion:
    claim = state.latest_claim(claim_id)
    if claim is None:
        raise MathStateError(f"no claim {claim_id!r} in {_STATE_REF}")
    return claim


def _formal_statement(args: argparse.Namespace) -> str | None:
    if getattr(args, "formal_file", None) is not None:
        path = Path(str(args.formal_file)).expanduser()
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise MathStateError(f"{path} cannot be read: {exc}") from exc
    if getattr(args, "formal", None) is not None:
        return str(args.formal)
    return None


def _cmd_context(state: MathState, args: argparse.Namespace) -> dict[str, Any]:
    definitions = dict(_pair(item, "a definition") for item in args.define)
    proposed = ContextVersion(
        context_id=args.id, version=1, statement=args.statement, definitions=definitions
    )
    current = state.latest_context(args.id)
    if current is not None:
        if current.content_hash == proposed.content_hash:
            return {"ok": True, "unchanged": True, "context": current.as_dict()}
        raise MathStateError(
            f"context {args.id!r} already says something else. Use "
            "`revise-context`, which mints the next version and leaves every "
            "claim pointing at the version it was actually stated against"
        )
    return {"ok": True, "context": state.add_context(proposed).as_dict()}


def _cmd_revise_context(state: MathState, args: argparse.Namespace) -> dict[str, Any]:
    current = _require_context(state, args.id)
    definitions = dict(current.definitions)
    definitions.update(dict(_pair(item, "a definition") for item in args.define))
    for name in args.forget:
        definitions.pop(name, None)
    revised = state.revise_context(
        args.id,
        statement=args.statement,
        definitions=definitions,
    )
    return {
        "ok": True,
        "context": revised.as_dict(),
        "note": (
            "claims stated against the previous version still point at it; "
            "`check` lists them, and restating one against this version costs "
            "the evidence bound to its previous statement"
        ),
    }


def _cmd_claim(state: MathState, args: argparse.Namespace) -> dict[str, Any]:
    context = _require_context(state, args.context)
    proposed = ClaimVersion(
        claim_id=args.id,
        version=1,
        context=context.ref(),
        natural_statement=args.statement,
        formal_statement=_formal_statement(args) or "",
    )
    current = state.latest_claim(args.id)
    if current is not None:
        if current.content_hash == proposed.content_hash:
            return {"ok": True, "unchanged": True, "claim": current.as_dict()}
        raise MathStateError(
            f"claim {args.id!r} already states something else. Use "
            "`revise-claim`: restating a theorem is a new version, and the "
            "evidence recorded about the previous statement does not follow it"
        )
    return {"ok": True, "claim": state.add_claim(proposed).as_dict()}


def _standing_on(state: MathState, claim_id: str) -> tuple[ExternalAssumption, ...]:
    """What the claim carries, which is not always what its last version lists.

    ``revise_claim`` demands a written reason for every carried assumption the
    new version drops, and "carried" walks the whole history — so a revision
    built from ``latest_claim(...).external_assumptions`` would be refused as a
    silent deletion whenever an earlier version had listed something this one
    inherited. Building every revision from the carried set means a plain
    restatement never drops a dependency by accident, and re-lists an inherited
    one explicitly, which is the repair the store documents.
    """
    return state.effective_assumptions(claim_id)


def _cmd_revise_claim(state: MathState, args: argparse.Namespace) -> dict[str, Any]:
    current = _require_claim(state, args.id)
    context = None
    if args.use_current_context:
        context = _require_context(state, current.context.subject_id).ref()
    retirements = dict(_pair(item, "a retirement") for item in args.retire)
    revised = state.revise_claim(
        args.id,
        context=context,
        natural_statement=args.statement,
        formal_statement=_formal_statement(args),
        external_assumptions=tuple(
            item
            for item in _standing_on(state, args.id)
            if item.assumption_id not in retirements
        ),
        retire_assumptions=retirements or None,
    )
    payload: dict[str, Any] = {"ok": True, "claim": revised.as_dict()}
    if revised.content_hash != current.content_hash:
        payload["note"] = (
            "this version says something different, so it carries a different "
            "digest and the evidence recorded about the previous statement no "
            "longer binds to it; `show` reports those records as stale rather "
            "than dropping them"
        )
    return payload


def _cmd_assume(state: MathState, args: argparse.Namespace) -> dict[str, Any]:
    _require_claim(state, args.claim)
    assumption = ExternalAssumption(
        assumption_id=args.id, statement=args.statement, source=args.source
    )
    kept = [
        item
        for item in _standing_on(state, args.claim)
        if item.assumption_id != args.id
    ]
    revised = state.revise_claim(
        args.claim, external_assumptions=(*kept, assumption)
    )
    return {
        "ok": True,
        "claim": revised.as_dict(),
        "note": (
            "assumptions sit outside the claim's digest, so recording one keeps "
            "any proof already bound to this statement — and holds the claim at "
            "conditional_kernel until a proof kernel discharges it"
        ),
    }


def _cmd_route(state: MathState, args: argparse.Namespace) -> dict[str, Any]:
    goal = _require_claim(state, args.goal)
    obligations = tuple(
        _require_claim(state, claim_id).ref() for claim_id in args.obligation
    )
    route = state.add_route(
        ProofRoute(
            route_id=args.id,
            goal=goal.ref(),
            obligations=obligations,
            retired_because=args.retired_because or "",
        )
    )
    return {
        "ok": True,
        "route": route.as_dict(),
        "note": (
            "a route records a plan and confers no status on its goal: nothing "
            "has checked that these obligations imply it, so finishing all of "
            "them leaves the goal exactly where the evidence put it"
        ),
    }


def _cmd_judge(state: MathState, args: argparse.Namespace) -> dict[str, Any]:
    claim = _require_claim(state, args.claim)
    if args.assumption:
        assumption = claim.assumption(args.assumption)
        if assumption is None:
            raise MathStateError(
                f"claim {args.claim!r} is not standing on assumption "
                f"{args.assumption!r}"
            )
        subject = assumption.ref()
    else:
        subject = claim.ref()
    produced_by = str(args.by).strip()
    if not produced_by:
        raise MathStateError(
            "a judgement needs a producer: independence is a fact about who "
            "answered, and six records from one referee are one check"
        )
    record, changed = _agent_evidence(
        state,
        subject=subject,
        tier=EvidenceTier.JUDGEMENT,
        verdict=Verdict(args.verdict),
        produced_by=produced_by,
        artifact=str(args.artifact or ""),
    )
    return {
        "ok": True,
        "changed": changed,
        "evidence": record.as_dict(),
        "note": (
            "a judgement is an opinion and is recorded as one: it can reach "
            "`supported`, and no number of them reaches a kernel status or "
            "discharges an assumption"
        ),
    }


_WRITERS = {
    "context": _cmd_context,
    "revise-context": _cmd_revise_context,
    "claim": _cmd_claim,
    "revise-claim": _cmd_revise_claim,
    "assume": _cmd_assume,
    "route": _cmd_route,
    "judge": _cmd_judge,
}


# -- CLI ---------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name: str, help_text: str) -> argparse.ArgumentParser:
        child = sub.add_parser(name, help=help_text)
        child.add_argument("--project-root", type=Path, default=Path("."))
        return child

    context = add("context", "record the problem statement claims are stated against")
    context.add_argument("--id", required=True)
    context.add_argument("--statement", required=True)
    context.add_argument("--define", action="append", default=[], metavar="NAME=BODY")

    revise_context = add("revise-context", "mint the next version of a context")
    revise_context.add_argument("--id", required=True)
    revise_context.add_argument("--statement")
    revise_context.add_argument("--define", action="append", default=[], metavar="NAME=BODY")
    revise_context.add_argument("--forget", action="append", default=[], metavar="NAME")

    claim = add("claim", "record one mathematical assertion")
    claim.add_argument("--id", required=True)
    claim.add_argument("--context", required=True)
    claim.add_argument("--statement", required=True)
    claim.add_argument("--formal-file", type=Path, help="a Lean source whose text is the formalization")
    claim.add_argument("--formal", help="the formalization inline, when it is one line")

    revise_claim = add("revise-claim", "mint the next version of a claim")
    revise_claim.add_argument("--id", required=True)
    revise_claim.add_argument("--statement")
    revise_claim.add_argument("--formal-file", type=Path)
    revise_claim.add_argument("--formal")
    revise_claim.add_argument(
        "--use-current-context",
        action="store_true",
        help="restate this claim against the newest version of its context",
    )
    revise_claim.add_argument(
        "--retire",
        action="append",
        default=[],
        metavar="ID=WHY",
        help="stop standing on an assumption, with the reason the proof does not need it",
    )

    assume = add("assume", "record a result this proof takes from elsewhere")
    assume.add_argument("--claim", required=True)
    assume.add_argument("--id", required=True)
    assume.add_argument("--statement", required=True)
    assume.add_argument("--source", required=True)

    route = add("route", "record one decomposition of a goal into obligations")
    route.add_argument("--id", required=True)
    route.add_argument("--goal", required=True)
    route.add_argument("--obligation", action="append", default=[], metavar="CLAIM_ID")
    route.add_argument("--retired-because", help="why this route was abandoned")

    judge = add("judge", "record a referee's opinion about a claim or an assumption")
    judge.add_argument("--claim", required=True)
    judge.add_argument("--assumption", help="judge this assumption of the claim instead")
    judge.add_argument(
        "--verdict", required=True, choices=[item.value for item in Verdict]
    )
    judge.add_argument("--by", required=True, help="who answered; the independence key")
    judge.add_argument("--artifact", help="a file holding the reasoning behind the opinion")

    show = add("show", "report what the records add up to")
    show.add_argument("--claim", default="")

    add("check", "report structural defects in the recorded state")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    root = args.project_root.expanduser().resolve()

    try:
        if args.command == "check":
            issues = load_state(root).validate()
            print(
                json.dumps(
                    {"ok": not issues, "issues": [item.as_dict() for item in issues]},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 1 if issues else 0
        if args.command == "show":
            payload = _show(root, args.claim)
        else:
            with locked_state(root) as state:
                payload = _WRITERS[args.command](state, args)
    except (MathStateError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
