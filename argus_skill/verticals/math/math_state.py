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
    StateIssue,
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
    "certificate_issues",
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

#: Where a recorded certificate is copied to, relative to the directory the
#: compiler artifacts were published in. A subdirectory rather than a sibling so
#: the archive travels with the proof it certifies, and so the canonical names
#: ``verify`` rewrites on every run stay exactly where the Engineer doc says
#: they are.
_CERTIFICATE_DIRNAME = "certificates"

#: The shape of one archived certificate. Nothing in this repository reads it;
#: the reviewer the record points at does, and a payload that cannot say which
#: shape it is is a payload that cannot be changed later.
_CERTIFICATE_SCHEMA = 1

#: A claim id is free text and part of a filename here, so anything outside this
#: set is folded away. Uniqueness comes from the digest beside it, never from
#: the name, which is why folding is safe and traversal is not possible.
_UNSAFE_IN_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")

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
    # One referee has one current opinion about one statement. Judging the same
    # claim again from a different document is a re-read, not a second voice —
    # and it is the remedy `certificate_issues` names, which only works if the
    # new verdict replaces the one that cited the retired certificate rather
    # than sitting beside it.
    state.retire_superseded_evidence(record)
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
    #: Certificates this run replaced: the same compiler answering about the
    #: same statement from a different reading of it. Non-empty means the
    #: fidelity note was rewritten, so anyone who approved the old reading was
    #: approving a document this claim no longer stands on.
    retired: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "recorded": self.record.as_dict() if self.record is not None else None,
            "changed": self.changed,
            "refusals": list(self.refusals),
            "statement_fidelity": {
                "document": self.statement_fidelity,
                "verified_by": None,
                "note": _FIDELITY_CAVEAT,
            },
        }
        if self.retired:
            payload["retired_certificates"] = list(self.retired)
            payload["retired_note"] = (
                "the statement fidelity note was rewritten, so this run "
                "certifies the same proof under a different reading of the "
                "theorem and the certificates above are no longer what this "
                "claim stands on. Any judgement recorded against one of them "
                "was made about a reading that is no longer in force; "
                "`math_state check` reports each one until it is judged again"
            )
        return payload


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

    *And the citation has to keep naming this run.* ``expect_result`` closes the
    window before the record is written; nothing closed the one after it.
    ``verify`` publishes to fixed names — ``Main.lean``, ``lean_check.json``,
    ``statement_fidelity.md`` — so the next claim formalized in the same
    directory, which is what the Engineer doc teaches, overwrites the previous
    claim's certificate in place. The status stayed honest, because the record
    binds to the claim's own ``content_hash`` and a real compile of that text
    did happen; the *pointer* did not, because ``EvidenceRecord.artifact`` is a
    bare path with no digest, and a reviewer sent to it now reads a different
    theorem with nothing anywhere saying so. So the certificate is archived to a
    path derived from the record it belongs to before the record is written, and
    that archive is what ``artifact`` names. Failing to archive records nothing:
    an unarchived record is exactly the dangling citation this exists to
    prevent, and a silent one is worse than a refusal.
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
        produced_by = _lean_producer(result)
        subject = claim.ref()
        artifact_dir = source_path.parent
        name = _certificate_name(
            subject,
            EvidenceTier.MECHANICAL,
            verdict,
            produced_by,
            str(result.get("statement_fidelity_sha256") or ""),
        )
        artifact = _project_relative(
            artifact_dir / _CERTIFICATE_DIRNAME / name, root
        )
        evidence_id = _evidence_id(
            "lean",
            subject,
            EvidenceTier.MECHANICAL,
            verdict,
            produced_by,
            artifact,
        )
        try:
            _archive_certificate(
                artifact_dir,
                name,
                {
                    "schema_version": _CERTIFICATE_SCHEMA,
                    "evidence_id": evidence_id,
                    "subject": subject.as_dict(),
                    "tier": EvidenceTier.MECHANICAL.value,
                    "verdict": verdict.value,
                    "produced_by": produced_by,
                    "lean_check": result,
                    "lean_source": {
                        "path": _project_relative(source_path, root),
                        "text": source_text,
                    },
                    "statement_fidelity": {
                        "path": fidelity,
                        "text": _fidelity_text(evidence.fidelity),
                    },
                },
            )
        except (OSError, UnicodeError, ValueError) as exc:
            return LeanRecording(
                refusals=(
                    f"the compiler result could not be archived to {artifact}, "
                    "so the only path this record could cite is the one "
                    "`verify` overwrites on its next run — the next claim "
                    "formalized here would silently replace this proof's "
                    f"certificate; nothing was recorded: {exc}",
                ),
                statement_fidelity=fidelity,
            )
        record = EvidenceRecord(
            evidence_id=evidence_id,
            subject=subject,
            tier=EvidenceTier.MECHANICAL,
            verdict=verdict,
            produced_by=produced_by,
            artifact=artifact,
        )
        retired = state.retire_superseded_evidence(record)
        stored, changed = _append_evidence(state, record)

    return LeanRecording(
        record=stored,
        changed=changed,
        statement_fidelity=fidelity,
        retired=tuple(item.artifact for item in retired),
    )


def _certificate_name(
    subject: SubjectRef,
    tier: EvidenceTier,
    verdict: Verdict,
    produced_by: str,
    fidelity_sha256: str,
) -> str:
    """The archive's filename, derived from the record that will cite it.

    ``_evidence_id`` hashes (kind, subject, tier, verdict, produced_by,
    artifact), and the artifact is about to be this path, which reads as a
    circle. It is not one, because this digest is taken over *the same
    arguments minus the artifact*, plus the fidelity note's digest::

        artifact    = g(subject, tier, verdict, produced_by, fidelity)
        evidence_id = f(subject, tier, verdict, produced_by, g(...))

    Both are functions of the same free variables, evaluated in that order, so
    nothing waits on itself. What that buys is the property the archive exists
    for: two records with different ids differ in at least one of them, since
    the artifact cannot be the tie-breaker when it is derived from them — so
    ``g`` is injective over records, two of them can never overwrite each
    other, and one record recorded twice lands on the same path. That last part
    is what makes re-verifying idempotent rather than littering the directory
    with a copy per run.

    ``.json``, and deliberately never ``.lean``: ``discover_lean_sources`` finds
    project sources by extension, so an archived copy of the compiled source
    saved under its own name would become a *new* unverified Lean source,
    demanding its own fidelity document and its own compile, and
    ``lean_evidence check`` would start blocking on the evidence it was given.
    The source text is carried inside this file as a string instead, where no
    sweep can mistake it for work in progress.

    ``subject_id`` is free text, so it is folded to one safe path component
    before it becomes a filename; the digest, never the name, is what makes the
    path unique, so folding two ids together costs readability and nothing else.

    **Why the fidelity note is in the key.** ``fidelity_sha256`` is not part of
    the record — the record says which claim, tier, verdict, and checker — so
    including it here splits one record into two whenever only the note was
    rewritten. That is deliberate, and it costs something real: rewording a note
    for clarity mints a fresh certificate, and a reviewer who approved the old
    wording has to be asked again. The alternative was tried first and fails
    quietly. With the note left out, rewriting it and re-verifying the same
    proof landed on this same path and replaced the archived note in place;
    because the record itself was unchanged the command reported
    ``changed: false``, so a reviewer's "the formal statement says what the
    natural statement says" was re-pointed at a reading nobody had read.
    Statement fidelity is the one question no compiler answers, which makes it
    the one verdict that must not be allowed to drift onto text it was never
    given. A note that was right does not need rewriting; when it does get
    rewritten, something about the reading of the theorem changed, and that is
    exactly when a prior approval must stop counting.
    """
    digest = content_digest(
        {
            "subject": subject.as_dict(),
            "tier": tier.value,
            "verdict": verdict.value,
            "produced_by": normalize_text(produced_by),
            "statement_fidelity_sha256": normalize_text(fidelity_sha256),
        }
    )
    stem = _UNSAFE_IN_FILENAME.sub("_", subject.subject_id).strip("._-")
    return f"{stem[:48] or 'claim'}-{digest[:16]}.json"


def _fidelity_text(fidelity: Path | None) -> str:
    """The document that was in force, read the way its digest was taken.

    ``verify_lean_source`` hashes the fidelity note through ``read_text``, and
    ``_fidelity_issues`` has already refused this record if what is on disk no
    longer matches that digest — so the text read here is the text the compile
    was paired with, and a reviewer can check it against
    ``statement_fidelity_sha256`` without trusting the archive. ``None`` cannot
    reach here (a missing note is inadmissible), but a read that fails between
    the check and now must refuse rather than archive a blank.
    """
    if fidelity is None:
        raise ValueError("no statement fidelity document to archive")
    return fidelity.read_text(encoding="utf-8")


def _archive_certificate(
    artifact_dir: Path, name: str, payload: dict[str, Any]
) -> Path:
    """Publish one certificate under the same lock and write that made it.

    Reuses ``lean_check``'s directory lock and atomic write rather than
    repeating either: the lock is the one ``verify_lean_source`` holds while it
    republishes the canonical names, so archiving is serialized against exactly
    the operation that would otherwise be racing it, and ``os.replace`` means a
    reader sees a whole certificate or none.

    Taken while the state lock is held, which is safe because no path takes the
    two in the other order — ``verify_lean_source`` releases the artifact lock
    before ``record_lean_evidence`` ever asks for the state.
    """
    from ...tools.lean_check import (  # noqa: PLC0415 — optional, heavy import
        _artifact_directory_lock,
        _atomic_artifact_write,
    )

    target = artifact_dir / _CERTIFICATE_DIRNAME / name
    rendered = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    with _artifact_directory_lock(artifact_dir):
        _atomic_artifact_write(target, rendered.encode("utf-8"))
    return target


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
    certificates = _certificates(state, claim)
    if certificates:
        payload["certificates"] = certificates
    if assessment.is_kernel:
        payload["caveats"] = [_FIDELITY_CAVEAT]
    return payload


def _certificates(state: MathState, claim: ClaimVersion) -> list[dict[str, str]]:
    """Where to read what each checker actually produced about this claim.

    ``ClaimAssessment`` reports which tiers answered and which producers
    answered in them, which is what a *status* is made of, and deliberately not
    where the answers are kept. But the reviewer skill sends its reader here
    and then asks them to judge whether the formal statement says what the
    natural statement says — a question no status can answer and only the
    compiled source and its fidelity note can. Without this key the only paths
    they could find are the canonical ``Main.lean`` and ``lean_check.json``,
    which describe whichever claim was formalized in that directory *last*. The
    archive stopped one claim's certificate from destroying another's; a
    certificate nobody is told the path of is one the reviewer still cannot
    reach.

    Only evidence bound to the statement this claim carries *now* is listed.
    Records left behind by an earlier version are already reported under
    ``stale_evidence``, and printing a path beside them would invite reading a
    certificate about a statement that has since been restated — the exact
    confusion this whole seam exists to prevent.
    """
    subject = claim.ref()
    return [
        {
            "tier": record.tier.value,
            "produced_by": record.produced_by,
            "verdict": record.verdict.value,
            "artifact": record.artifact,
        }
        for record in state.evidence
        if record.subject == subject and record.artifact
    ]


def certificate_issues(state: MathState) -> tuple[StateIssue, ...]:
    """Judgements that were made about a certificate the claim has moved past.

    A defect the kernel cannot state, because it is about certificates and the
    kernel does not know what one is. Every record here is either a Lean
    certificate this vertical archived or something a reviewer chose to cite;
    only the first kind is checked, by the directory it sits in.

    The shape it catches: a reviewer reads a claim's certificate, judges that
    the formal statement says what the natural statement says, and records that
    with ``judge --artifact <certificate>``. Later the fidelity note is
    rewritten and the proof re-verified. The compiler answers as before, so the
    claim keeps its status — but the reading of the theorem it is paired with is
    a different one, ``retire_superseded_evidence`` has dropped the certificate
    the reviewer read, and their approval is now the only thing standing between
    that new reading and a ``closed_kernel`` nobody has checked. Statement
    fidelity is the one question the compiler does not answer, which is exactly
    why this verdict must not be inherited by a document it was not given.

    Clearable, and cheaply: read the certificate the claim now cites and judge
    again. That matters more than it sounds. A blocking defect whose message
    names a remedy that does not work is worse than no defect at all, because
    the agent it blocks will do what the message says and stay blocked.

    A judgement that cites nothing is not reported. It made no claim about which
    document it was reached from, so there is nothing here to contradict — and
    it is also not protected by this check, which is the reason the reviewer
    skill asks for the citation.
    """
    issues: list[StateIssue] = []
    for claim in sorted(state.current_claims(), key=lambda item: item.claim_id):
        subject = claim.ref()
        current = {
            record.artifact
            for record in state.evidence
            if record.subject == subject
            and record.tier is not EvidenceTier.JUDGEMENT
            and record.artifact
        }
        for record in state.evidence:
            if (
                record.subject != subject
                or record.tier is not EvidenceTier.JUDGEMENT
                or not record.artifact
                or record.artifact in current
                or Path(record.artifact).parent.name != _CERTIFICATE_DIRNAME
            ):
                continue
            issues.append(
                StateIssue(
                    "judgement_certificate_retired",
                    f"$.evidence[{record.evidence_id}].artifact",
                    f"{record.produced_by!r} judged claim {claim.claim_id!r} "
                    f"from {record.artifact}, which is no longer a certificate "
                    "this claim stands on: the statement fidelity note was "
                    "rewritten and the proof re-verified, so the compiler's "
                    "answer is now paired with a different reading of the "
                    "theorem. The compile is unaffected and that verdict is "
                    "not, because it was about the reading. Read the "
                    "certificate this claim cites now — `show` lists it under "
                    "`certificates` — and record the verdict again with "
                    f"`judge --claim {claim.claim_id} --artifact <that path> "
                    f"--by {record.produced_by}`",
                )
            )
    return tuple(issues)


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
    judge.add_argument(
        "--artifact",
        help=(
            "what the opinion was reached from: the certificate that was read, "
            "or a file holding the reasoning. Citing the certificate is what "
            "makes the verdict stop counting if the reading it approved is "
            "later replaced"
        ),
    )

    show = add("show", "report what the records add up to")
    show.add_argument("--claim", default="")

    add("check", "report structural defects in the recorded state")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    root = args.project_root.expanduser().resolve()

    try:
        if args.command == "check":
            state = load_state(root)
            issues = (*state.validate(), *certificate_issues(state))
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
