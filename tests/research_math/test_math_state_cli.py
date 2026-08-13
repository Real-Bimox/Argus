"""The write path into the kernel, and the tier an agent cannot type.

The kernel could express a project's beliefs and derive what they added up to,
and nothing could put anything into it. This covers the module that closes that
gap, and it is mostly adversarial for one reason: ``MathState.add_evidence``
accepts every tier, because a legitimate producer of each has to reach it. The
tier is therefore decided by the command surface, and the property that makes
the whole schema mean anything is that an agent's command cannot choose one
that confers kernel status.

That property is asserted three ways below — as the constant, as the behaviour
of the funnel every command writes through, and as a sweep of the source that
fails if a later flag routes around either. The third is the one that matters
after this PR: the first two would still pass if somebody added ``--tier`` next
to them.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from argus_skill.research_math import (
    ClaimStatus,
    ClaimVersion,
    EvidenceTier,
    MathState,
    MathStateError,
    SubjectKind,
    SubjectRef,
    Verdict,
    load_state,
)
from argus_skill.tools.lean_check import audit_lean_tools
from argus_skill.verticals.math import math_state
from argus_skill.verticals.math.lean_evidence import validate_lean_evidence
from argus_skill.verticals.math.math_state import (
    AGENT_WRITABLE_TIERS,
    main,
    record_lean_evidence,
)

REPO_ROOT = Path(__file__).parents[2]
MODULE = REPO_ROOT / "argus_skill" / "verticals" / "math" / "math_state.py"

THEOREM = (
    "theorem argus_add_comm (a b : Nat) : a + b = b + a := Nat.add_comm a b\n"
)
FIDELITY = (
    "# Statement fidelity\n\n"
    "`argus_add_comm` formalizes: for all natural numbers a and b, a + b = b + a.\n"
    "Objects: natural numbers. Quantifiers: universal over a and b.\n"
    "Hypotheses: none. Conclusion: commutativity of addition.\n"
)

requires_lean = pytest.mark.skipif(
    not audit_lean_tools().get("lean", {}).get("available"),
    reason="no Lean toolchain on this host",
)


# -- fixtures ---------------------------------------------------------------

def _run(root: Path, *argv: str) -> tuple[int, dict]:
    """One command, as the Engineer types it, with its JSON parsed."""
    import io
    from contextlib import redirect_stdout

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = main([argv[0], "--project-root", str(root), *argv[1:]])
    return code, json.loads(buffer.getvalue())


def _lean_dir(root: Path) -> Path:
    path = root / "research" / "lean"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _source(root: Path, text: str = THEOREM) -> Path:
    path = _lean_dir(root) / "Main.lean"
    path.write_text(text, encoding="utf-8")
    return path


def _fidelity(root: Path, text: str = FIDELITY) -> Path:
    path = _lean_dir(root) / "statement_fidelity.md"
    path.write_text(text, encoding="utf-8")
    return path


def _result(root: Path, **overrides) -> dict:
    """A complete, twice-hash-stamped success, written where verify puts it.

    Synthesized rather than compiled so the refusals below can be provoked one
    at a time; the end-to-end test at the bottom runs the real toolchain.
    """
    source = _lean_dir(root) / "Main.lean"
    note = _lean_dir(root) / "statement_fidelity.md"
    payload = {
        "schema_version": 1,
        "status": "success",
        "source": str(source),
        "tool": "lean",
        "tools": {
            "lean": {
                "available": True,
                "path": "/usr/bin/lean",
                "version": "Lean (version 4.34.0-rc1, x86_64-unknown-linux-gnu, Release)",
            }
        },
        "command": ["/usr/bin/lean", str(source)],
        "cwd": str(_lean_dir(root)),
        "exit_code": 0,
        "stdout": "",
        "stderr": "",
        "proof_holes": [],
        "audit_command": [],
        "audit_exit_code": 0,
        "audit_stdout": "",
        "audit_stderr": "",
        "duration_ms": 10,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "statement_fidelity": str(note),
        "statement_fidelity_sha256": hashlib.sha256(
            note.read_text(encoding="utf-8").encode("utf-8")
        ).hexdigest(),
    }
    payload.update(overrides)
    (_lean_dir(root) / "lean_check.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    return payload


def _proved_project(root: Path) -> Path:
    """A claim whose formalization has compiled — the state before recording."""
    _source(root)
    _fidelity(root)
    _result(root)
    _run(root, "context", "--id", "ctx", "--statement", "Natural numbers.")
    _run(
        root,
        "claim",
        "--id",
        "C1",
        "--context",
        "ctx",
        "--statement",
        "addition of naturals is commutative",
        "--formal-file",
        str(_lean_dir(root) / "Main.lean"),
    )
    return _lean_dir(root) / "Main.lean"


# -- the round trip the Engineer is told to perform -------------------------

def test_a_context_claim_route_assumption_and_judgement_all_read_back(
    tmp_path: Path,
) -> None:
    """The definition of a usable write path: what went in comes back out.

    Every previous PR could describe this state and none could produce it, so
    this is the first test in the repository that exercises the kernel the way
    a run reaches it — through commands rather than through constructors.
    """
    assert _run(tmp_path, "context", "--id", "ctx", "--statement", "Fix n : Nat.",
                "--define", "even=n = 2k for some k")[0] == 0
    for claim_id, text in (("C1", "n + n is even"), ("L1", "2 divides n + n")):
        assert _run(tmp_path, "claim", "--id", claim_id, "--context", "ctx",
                    "--statement", text)[0] == 0
    assert _run(tmp_path, "route", "--id", "R1", "--goal", "C1",
                "--obligation", "L1")[0] == 0
    assert _run(tmp_path, "assume", "--claim", "C1", "--id", "RH",
                "--statement", "The Riemann Hypothesis",
                "--source", "Riemann 1859")[0] == 0
    assert _run(tmp_path, "judge", "--claim", "C1", "--verdict", "supports",
                "--by", "reviewer:alice")[0] == 0

    code, payload = _run(tmp_path, "show", "--claim", "C1")
    assert code == 0
    claim = payload["claim"]
    assert claim["status"] == ClaimStatus.SUPPORTED.value
    assert claim["support"] == {"judgement": ["reviewer:alice"]}
    assert [item["assumption_id"] for item in claim["standing_on"]] == ["RH"]
    assert [route["route_id"] for route in claim["routes"]] == ["R1"]
    assert _run(tmp_path, "check")[0] == 0


def test_a_state_file_written_by_the_cli_is_the_one_the_kernel_reads(
    tmp_path: Path,
) -> None:
    """The commands and the library must not be two dialects of one file.

    Nothing else checks this: the CLI could round-trip through its own reader
    forever while the projector a later PR builds on ``load_state`` saw
    nothing.
    """
    _run(tmp_path, "context", "--id", "ctx", "--statement", "Fix n : Nat.")
    _run(tmp_path, "claim", "--id", "C1", "--context", "ctx", "--statement", "P")
    state = load_state(tmp_path)
    assert [claim.claim_id for claim in state.current_claims()] == ["C1"]
    assert state.validate() == ()


# -- the tier an agent cannot type ------------------------------------------

def test_the_only_tier_a_command_may_take_from_an_agent_is_judgement() -> None:
    """Named, so widening the set is a visible edit to a test that says why."""
    assert AGENT_WRITABLE_TIERS == frozenset({EvidenceTier.JUDGEMENT})
    assert EvidenceTier.MECHANICAL not in AGENT_WRITABLE_TIERS
    assert EvidenceTier.COMPUTATIONAL not in AGENT_WRITABLE_TIERS
    assert EvidenceTier.LITERATURE not in AGENT_WRITABLE_TIERS


@pytest.mark.parametrize(
    "tier",
    [EvidenceTier.MECHANICAL, EvidenceTier.COMPUTATIONAL, EvidenceTier.LITERATURE],
)
def test_the_agent_funnel_refuses_every_tier_it_did_not_check(
    tier: EvidenceTier,
) -> None:
    """``mechanical`` and ``computational`` confer status; ``literature`` claims
    independence from the model, which the model cannot assert about itself."""
    state = MathState()
    with pytest.raises(MathStateError) as caught:
        math_state._agent_evidence(
            state,
            subject=SubjectRef(SubjectKind.CLAIM, "C1", "a" * 64),
            tier=tier,
            verdict=Verdict.SUPPORTS,
            produced_by="agent",
        )
    assert "cannot be recorded from a command line" in str(caught.value)
    assert state.evidence == []


def test_no_agent_command_reaches_add_evidence_except_through_the_funnel() -> None:
    """The invariant, rather than today's absence of a ``--tier`` flag.

    Both tests above would still pass if a later PR added ``--tier`` beside
    them: the constant would be untouched and ``_agent_evidence`` would still
    refuse, while a new subcommand called ``state.add_evidence`` directly. This
    reads the source instead, and fails the moment a second door exists.
    """
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    callers: set[str] = set()
    for function in ast.walk(tree):
        if not isinstance(function, ast.FunctionDef):
            continue
        for node in ast.walk(function):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_evidence"
            ):
                callers.add(function.name)
    assert callers == {"_append_evidence"}, (
        "every write of evidence must pass the tier gate; these functions call "
        f"MathState.add_evidence directly: {sorted(callers)}"
    )

    appenders = {
        function.name
        for function in ast.walk(tree)
        if isinstance(function, ast.FunctionDef)
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_append_evidence"
    }
    assert appenders == {"_agent_evidence", "record_lean_evidence"}


def test_a_kernel_tier_is_named_only_where_a_checker_was_run() -> None:
    """``EvidenceTier.MECHANICAL`` appears in one function, and it compiles first.

    A sweep rather than an assertion about behaviour, because the failure being
    guarded is a future edit: a helper that writes ``MECHANICAL`` from anywhere
    that did not read a compiler's answer is the whole vulnerability, whatever
    it is called.
    """
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    named: dict[str, set[str]] = {}
    for function in ast.walk(tree):
        if not isinstance(function, ast.FunctionDef):
            continue
        for node in ast.walk(function):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "EvidenceTier"
                and node.attr in {"MECHANICAL", "COMPUTATIONAL"}
            ):
                named.setdefault(function.name, set()).add(node.attr)
    assert named == {"record_lean_evidence": {"MECHANICAL"}}


def test_the_agent_command_surface_offers_no_option_that_selects_a_tier() -> None:
    """Read off the parser, so a flag added anywhere in it is caught.

    ``--force``, ``--unsafe``, ``--override`` and friends are named too: the
    brief's rule is that there is no escape hatch, and an escape hatch does not
    have to be spelled ``--tier`` to be one.
    """
    forbidden = (
        "tier", "force", "unsafe", "override", "mechanical", "computational",
        "literature", "kernel", "trust", "skip", "no-verify", "admin",
    )
    parser = math_state._build_parser()
    subparsers = [
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    ]
    assert subparsers, "the sweep found no subcommands, so it proves nothing"

    offenders: list[str] = []
    for group in subparsers:
        for name, child in group.choices.items():
            for action in child._actions:
                for option in action.option_strings:
                    if any(word in option.lower() for word in forbidden):
                        offenders.append(f"{name} {option}")
                for choice in action.choices or ():
                    if str(choice).lower() in {
                        "mechanical", "computational", "literature"
                    }:
                        offenders.append(f"{name} {action.dest}={choice}")
    assert offenders == []

    judge = group.choices["judge"]
    verdicts = next(
        action.choices for action in judge._actions if action.dest == "verdict"
    )
    assert set(verdicts) == {item.value for item in Verdict}


def test_no_environment_variable_can_change_what_a_command_may_write() -> None:
    """An env var is the escape hatch that no ``--help`` output would show."""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    reads = [
        node
        for node in ast.walk(tree)
        if (isinstance(node, ast.Attribute) and node.attr in {"environ", "getenv"})
        or (isinstance(node, ast.Name) and node.id in {"environ", "getenv"})
    ]
    assert reads == []

    # And behaviourally, for the names somebody would reach for first.
    state = MathState()
    for name in ("ARGUS_SKILL_MATH_TIER", "ARGUS_SKILL_MATH_FORCE"):
        os.environ[name] = "mechanical"
    try:
        with pytest.raises(MathStateError):
            math_state._agent_evidence(
                state,
                subject=SubjectRef(SubjectKind.CLAIM, "C1", "a" * 64),
                tier=EvidenceTier.MECHANICAL,
                verdict=Verdict.SUPPORTS,
                produced_by="agent",
            )
    finally:
        for name in ("ARGUS_SKILL_MATH_TIER", "ARGUS_SKILL_MATH_FORCE"):
            del os.environ[name]


def test_a_judgement_cannot_reach_a_kernel_status_however_many_are_recorded(
    tmp_path: Path,
) -> None:
    """The tier gate would be pointless if the writable tier promoted anyway."""
    _run(tmp_path, "context", "--id", "ctx", "--statement", "Fix n : Nat.")
    _run(tmp_path, "claim", "--id", "C1", "--context", "ctx", "--statement", "P",
         "--formal", "theorem p : True := trivial")
    for referee in ("alice", "bob", "carol", "dan", "erin"):
        assert _run(tmp_path, "judge", "--claim", "C1", "--verdict", "supports",
                    "--by", f"reviewer:{referee}")[0] == 0
    _, payload = _run(tmp_path, "show", "--claim", "C1")
    assert payload["claim"]["status"] == ClaimStatus.SUPPORTED.value
    assert len(payload["claim"]["support"]["judgement"]) == 5
    assert "caveats" not in payload["claim"]


def test_repeating_a_judgement_does_not_manufacture_a_second_producer(
    tmp_path: Path,
) -> None:
    """Retrying is how an autonomous loop recovers, and independence is counted.

    Without a derived id, an agent that ran the same command twice would turn
    one referee into two, which is exactly the reading ``support`` invites.
    """
    _run(tmp_path, "context", "--id", "ctx", "--statement", "Fix n : Nat.")
    _run(tmp_path, "claim", "--id", "C1", "--context", "ctx", "--statement", "P")
    first = _run(tmp_path, "judge", "--claim", "C1", "--verdict", "supports",
                 "--by", "reviewer:alice")[1]
    second = _run(tmp_path, "judge", "--claim", "C1", "--verdict", "supports",
                  "--by", "reviewer:alice")[1]
    assert first["changed"] is True
    assert second["changed"] is False
    assert len(load_state(tmp_path).evidence) == 1

    # A different answer from the same referee is a different record.
    _run(tmp_path, "judge", "--claim", "C1", "--verdict", "inconclusive",
         "--by", "reviewer:alice")
    assert len(load_state(tmp_path).evidence) == 2


# -- concurrency ------------------------------------------------------------

def test_simultaneous_writers_do_not_lose_a_record(tmp_path: Path) -> None:
    """Every command is a read-modify-write over one JSON file.

    Real processes rather than threads, because the writers this serializes are
    separate agent invocations and a lock that only holds within one interpreter
    would pass a threaded test and lose writes in production.
    """
    _run(tmp_path, "context", "--id", "ctx", "--statement", "Fix n : Nat.")
    processes = [
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "argus_skill.verticals.math.math_state",
                "claim",
                "--project-root",
                str(tmp_path),
                "--id",
                f"C{index}",
                "--context",
                "ctx",
                "--statement",
                f"claim number {index}",
            ],
            cwd=REPO_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        for index in range(12)
    ]
    for process in processes:
        _, errors = process.communicate(timeout=120)
        assert process.returncode == 0, errors.decode("utf-8", "replace")

    written = {claim.claim_id for claim in load_state(tmp_path).current_claims()}
    assert written == {f"C{index}" for index in range(12)}


def test_a_body_that_raises_inside_the_lock_publishes_nothing(
    tmp_path: Path,
) -> None:
    """A rejected write must not be half a write.

    The lock makes the read-modify-write atomic against other processes; this
    is the other half, and it is asserted against ``locked_state`` rather than
    against a command because no command today mutates and then refuses — they
    all validate first. That ordering is a property of nine functions and could
    change in any of them; this is a property of the one place they all write
    through.
    """
    _run(tmp_path, "context", "--id", "ctx", "--statement", "Fix n : Nat.")
    _run(tmp_path, "claim", "--id", "C1", "--context", "ctx", "--statement", "P")
    before = math_state.state_path(tmp_path).read_bytes()

    with pytest.raises(RuntimeError):
        with math_state.locked_state(tmp_path) as state:
            state.add_claim(
                ClaimVersion(
                    claim_id="C2",
                    version=1,
                    context=state.latest_claim("C1").context,
                    natural_statement="written then abandoned",
                )
            )
            raise RuntimeError("the command decided to refuse")

    assert math_state.state_path(tmp_path).read_bytes() == before
    assert [claim.claim_id for claim in load_state(tmp_path).current_claims()] == ["C1"]

    # And the surface agrees: a refusal reports it and changes nothing.
    code, payload = _run(tmp_path, "route", "--id", "R1", "--goal", "C1",
                         "--obligation", "MISSING")
    assert code == 1
    assert payload["ok"] is False
    assert math_state.state_path(tmp_path).read_bytes() == before


def test_a_hand_edited_ledger_is_repaired_by_the_next_write_not_refused_by_it(
    tmp_path: Path,
) -> None:
    """State arrives by text editor as well as by command, and must stay usable.

    ``revise_claim`` demands a written reason for every carried assumption a new
    version drops, and "carried" walks the whole history — so a revision built
    from the last version's own list would be refused as a silent deletion on
    any claim whose ledger somebody damaged by hand. That turns one bad edit
    into a claim no command can touch again. Building each version from what the
    claim carries re-lists the inherited dependency instead, which is the repair
    the store documents.
    """
    _run(tmp_path, "context", "--id", "ctx", "--statement", "Fix n : Nat.")
    _run(tmp_path, "claim", "--id", "C1", "--context", "ctx", "--statement", "P")
    _run(tmp_path, "assume", "--claim", "C1", "--id", "RH",
         "--statement", "The Riemann Hypothesis", "--source", "Riemann 1859")

    # The hand edit: a third version that quietly stops listing the assumption.
    path = math_state.state_path(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    edited = dict(payload["claims"][-1])
    edited["version"] = 3
    edited["external_assumptions"] = []
    payload["claims"].append(edited)
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert load_state(tmp_path).effective_assumptions("C1")[0].assumption_id == "RH"

    code, revised = _run(tmp_path, "revise-claim", "--id", "C1",
                         "--statement", "P, restated")
    assert code == 0
    assert [
        item["assumption_id"] for item in revised["claim"]["external_assumptions"]
    ] == ["RH"]
    _, shown = _run(tmp_path, "show", "--claim", "C1")
    assert shown["claim"]["undischarged"] == ["RH"]


# -- Lean into the kernel ---------------------------------------------------

def test_a_compiled_proof_records_mechanical_evidence_naming_kernel_and_artifact(
    tmp_path: Path,
) -> None:
    """The only path by which ``closed_kernel`` becomes reachable at all."""
    source = _proved_project(tmp_path)
    recording = record_lean_evidence(tmp_path, claim_id="C1", source=source)

    assert recording.refusals == ()
    record = recording.record
    assert record is not None
    assert record.tier is EvidenceTier.MECHANICAL
    assert record.verdict is Verdict.SUPPORTS
    assert record.produced_by == "lean_evidence/lean 4.34.0-rc1"
    assert record.artifact == "research/lean/lean_check.json"
    assert (tmp_path / record.artifact).is_file()

    _, payload = _run(tmp_path, "show", "--claim", "C1")
    assert payload["claim"]["status"] == ClaimStatus.CLOSED_KERNEL.value


def test_the_producer_names_the_proof_kernel_and_not_the_build_driver(
    tmp_path: Path,
) -> None:
    """One Lean, run bare and again under Lake, is one checker answering twice.

    ``produced_by`` is the independence key, so recording ``lake`` when a
    workspace applied would let a re-run through a different front end look
    like a second confirmation.
    """
    source = _proved_project(tmp_path)
    _result(
        tmp_path,
        tool="lake",
        tools={
            "lean": {
                "available": True,
                "path": "/x/lake env lean",
                "version": "Lean (version 4.34.0-rc1, x86_64-unknown-linux-gnu, Release)",
            },
            "lake": {
                "available": True,
                "path": "/x/lake",
                "version": "Lake version 5.0.0-src+3447a66 (Lean version 4.34.0-rc1)",
            },
        },
    )
    recording = record_lean_evidence(tmp_path, claim_id="C1", source=source)
    assert recording.record is not None
    assert recording.record.produced_by == "lean_evidence/lean 4.34.0-rc1"


def test_a_failed_compile_is_inconclusive_and_never_refutes(
    tmp_path: Path,
) -> None:
    """``mechanical`` is a refuting tier, and Lean failing is not a disproof.

    A timeout, a missing Mathlib, or a proof the author has not finished would
    otherwise mark a true theorem false — and ``refutes`` is terminal in a way
    no amount of later evidence undoes.
    """
    source = _proved_project(tmp_path)
    _result(tmp_path, status="type_error", exit_code=1, stderr="error: unsolved goals")
    recording = record_lean_evidence(tmp_path, claim_id="C1", source=source)

    assert recording.refusals == ()
    assert recording.record is not None
    assert recording.record.tier is EvidenceTier.MECHANICAL
    assert recording.record.verdict is Verdict.INCONCLUSIVE

    _, payload = _run(tmp_path, "show", "--claim", "C1")
    assert payload["claim"]["status"] == ClaimStatus.PROPOSED.value
    assert payload["claim"]["support"] == {}


def test_an_unverified_compile_is_still_inconclusive_rather_than_unrecorded(
    tmp_path: Path,
) -> None:
    """An environment gap is a fact about the run and worth keeping.

    ``inconclusive`` is a first-class answer in this schema: "we tried and the
    host had no Mathlib" is different from silence, and the difference is what
    stops the same attempt being made every round.
    """
    source = _proved_project(tmp_path)
    _result(
        tmp_path,
        status="type_error",
        exit_code=1,
        stderr="error: unknown module prefix 'Mathlib'",
    )
    recording = record_lean_evidence(tmp_path, claim_id="C1", source=source)
    assert "lean_unverified_missing_dependency" in {
        issue.code for issue in validate_lean_evidence(tmp_path).issues
    }
    assert recording.record is not None
    assert recording.record.verdict is Verdict.INCONCLUSIVE


def test_a_forged_success_records_nothing(tmp_path: Path) -> None:
    """The cheapest attack available is a hand-written ``lean_check.json``."""
    source = _proved_project(tmp_path)
    (_lean_dir(tmp_path) / "lean_check.json").write_text(
        json.dumps({"status": "success", "source": str(source)}), encoding="utf-8"
    )
    recording = record_lean_evidence(tmp_path, claim_id="C1", source=source)
    assert recording.record is None
    assert any("not usable as evidence" in text for text in recording.refusals)
    assert load_state(tmp_path).evidence == []


def test_a_result_recorded_against_different_source_text_records_nothing(
    tmp_path: Path,
) -> None:
    """Editing the proof after it compiled must not carry the certificate."""
    source = _proved_project(tmp_path)
    source.write_text(THEOREM + "\ntheorem sneaky : False := by sorry\n", encoding="utf-8")
    recording = record_lean_evidence(tmp_path, claim_id="C1", source=source)
    assert recording.record is None
    assert load_state(tmp_path).evidence == []


def test_a_claim_that_does_not_carry_the_compiled_text_records_nothing(
    tmp_path: Path,
) -> None:
    """Lean's answer is about the file it read, and about nothing else.

    Without this, a proof of one formal statement could certify a claim
    carrying another — and because the formal statement is inside the claim's
    digest, requiring them to agree is also what makes a later retranslation
    cost the certificate.
    """
    source = _proved_project(tmp_path)
    _run(tmp_path, "claim", "--id", "C2", "--context", "ctx",
         "--statement", "something else entirely")
    recording = record_lean_evidence(tmp_path, claim_id="C2", source=source)

    assert recording.record is None
    assert any(
        "records a different formal statement" in text for text in recording.refusals
    )
    assert load_state(tmp_path).evidence == []


def test_an_unknown_claim_records_nothing(tmp_path: Path) -> None:
    """Compiling first and inventing the claim afterwards is not the order."""
    source = _proved_project(tmp_path)
    recording = record_lean_evidence(tmp_path, claim_id="ghost", source=source)
    assert recording.record is None
    assert load_state(tmp_path).evidence == []


# -- statement fidelity, which nothing in this tree verifies ----------------

def test_a_fidelity_note_edited_after_the_compile_records_nothing(
    tmp_path: Path,
) -> None:
    """The gap this PR found in the checker it was told to wire up.

    Every existing fidelity check asks whether *some* substantive note names
    the declaration, so rewriting the note after a successful compile left the
    project passing while a proof of one thing was paired with a reading
    written for another. The compile stays valid; its meaning does not.
    """
    source = _proved_project(tmp_path)
    _fidelity(tmp_path, FIDELITY + "\nActually this is about the integers.\n")

    assert "lean_fidelity_changed" in {
        issue.code for issue in validate_lean_evidence(tmp_path).issues
    }
    recording = record_lean_evidence(tmp_path, claim_id="C1", source=source)
    assert recording.record is None
    assert any("edited since this result" in text for text in recording.refusals)


def test_a_result_carrying_no_fidelity_digest_records_nothing(
    tmp_path: Path,
) -> None:
    """Fail closed on the pre-digest artifact rather than trusting it.

    ``lean_evidence check`` keeps accepting such a result, because a project
    that verified before this change is not retroactively wrong. Minting kernel
    status from one is a different question: nothing pins the reading, so the
    unchecked half of the argument is attached to nothing.
    """
    source = _proved_project(tmp_path)
    payload = json.loads((_lean_dir(tmp_path) / "lean_check.json").read_text())
    del payload["statement_fidelity_sha256"]
    (_lean_dir(tmp_path) / "lean_check.json").write_text(json.dumps(payload))

    assert validate_lean_evidence(tmp_path).issues == ()
    recording = record_lean_evidence(tmp_path, claim_id="C1", source=source)
    assert recording.record is None
    assert any("does not carry the digest" in text for text in recording.refusals)


def test_a_missing_fidelity_note_records_nothing(tmp_path: Path) -> None:
    """A compile with no statement of intent is not evidence about a claim."""
    source = _proved_project(tmp_path)
    (_lean_dir(tmp_path) / "statement_fidelity.md").unlink()
    recording = record_lean_evidence(tmp_path, claim_id="C1", source=source)
    assert recording.record is None
    assert load_state(tmp_path).evidence == []


def test_a_kernel_status_is_reported_with_the_half_nobody_checked(
    tmp_path: Path,
) -> None:
    """The schema has no field for "fidelity was verified", because nothing
    verifies it. What it must not do is let ``closed_kernel`` be read as if it
    did — so the caveat rides along with the status, and the recording names
    the document without claiming anyone checked it."""
    source = _proved_project(tmp_path)
    recording = record_lean_evidence(tmp_path, claim_id="C1", source=source)

    fidelity = recording.as_dict()["statement_fidelity"]
    assert fidelity["document"] == "research/lean/statement_fidelity.md"
    assert fidelity["verified_by"] is None
    assert "nothing has checked" in fidelity["note"]

    _, payload = _run(tmp_path, "show", "--claim", "C1")
    assert payload["claim"]["status"] == ClaimStatus.CLOSED_KERNEL.value
    assert any("nothing has checked" in text for text in payload["claim"]["caveats"])


def test_a_result_from_another_run_is_refused(tmp_path: Path) -> None:
    """The artifact lock is released before the record is written.

    Between ``verify`` returning and the record being made, another process can
    publish a different answer to the same path; pinning the expected result is
    what keeps the record about the run the caller actually performed.
    """
    source = _proved_project(tmp_path)
    stale = dict(json.loads((_lean_dir(tmp_path) / "lean_check.json").read_text()))
    stale["duration_ms"] = 999999
    recording = record_lean_evidence(
        tmp_path, claim_id="C1", source=source, expect_result=stale
    )
    assert recording.record is None
    assert any("changed between the compile" in text for text in recording.refusals)


def test_a_source_outside_the_project_records_nothing(tmp_path: Path) -> None:
    """An artifact path in project state must name something the project has."""
    _proved_project(tmp_path)
    outside = tmp_path.parent / "Elsewhere.lean"
    outside.write_text(THEOREM, encoding="utf-8")
    recording = record_lean_evidence(tmp_path, claim_id="C1", source=outside)
    assert recording.record is None
    assert any("outside the project root" in text for text in recording.refusals)


# -- what a proof costs when the theorem moves ------------------------------

def test_restating_a_claim_costs_the_proof_bound_to_the_previous_statement(
    tmp_path: Path,
) -> None:
    """Evidence goes stale by identity, and the write path must not hide it."""
    source = _proved_project(tmp_path)
    record_lean_evidence(tmp_path, claim_id="C1", source=source)
    _, before = _run(tmp_path, "show", "--claim", "C1")
    assert before["claim"]["status"] == ClaimStatus.CLOSED_KERNEL.value

    code, payload = _run(tmp_path, "revise-claim", "--id", "C1",
                         "--formal", "theorem argus_add_comm : False := by sorry")
    assert code == 0
    assert "no longer binds" in payload["note"]

    _, after = _run(tmp_path, "show", "--claim", "C1")
    assert after["claim"]["status"] == ClaimStatus.PROPOSED.value
    assert after["claim"]["stale_evidence"]


def test_an_assumption_holds_a_proved_claim_at_conditional_kernel(
    tmp_path: Path,
) -> None:
    """And no judgement discharges it, whoever writes it.

    The one place ``conditional_kernel`` and ``closed_kernel`` come apart, run
    through the commands rather than the constructors: recording a dependency
    keeps the proof (assumptions sit outside the digest) and withholds the
    status, and only a written retirement gets it back.
    """
    source = _proved_project(tmp_path)
    record_lean_evidence(tmp_path, claim_id="C1", source=source)

    _run(tmp_path, "assume", "--claim", "C1", "--id", "RH",
         "--statement", "The Riemann Hypothesis", "--source", "Riemann 1859")
    _, payload = _run(tmp_path, "show", "--claim", "C1")
    assert payload["claim"]["status"] == ClaimStatus.CONDITIONAL_KERNEL.value
    assert payload["claim"]["undischarged"] == ["RH"]
    assert payload["claim"]["support"]["mechanical"]

    _run(tmp_path, "judge", "--claim", "C1", "--assumption", "RH",
         "--verdict", "supports", "--by", "reviewer:alice")
    _, judged = _run(tmp_path, "show", "--claim", "C1")
    assert judged["claim"]["status"] == ClaimStatus.CONDITIONAL_KERNEL.value

    code, retired = _run(tmp_path, "revise-claim", "--id", "C1",
                         "--retire", "RH=Lemma 2 gives the bound unconditionally")
    assert code == 0
    _, closed = _run(tmp_path, "show", "--claim", "C1")
    assert closed["claim"]["status"] == ClaimStatus.CLOSED_KERNEL.value


def test_dropping_an_assumption_without_a_reason_is_refused_from_the_cli(
    tmp_path: Path,
) -> None:
    """The store's cheapest route to ``closed_kernel``, closed at the surface too.

    ``revise-claim`` builds each version from what the claim carries rather
    than from what its last version listed, so there is no command that silently
    stops standing on something.
    """
    source = _proved_project(tmp_path)
    record_lean_evidence(tmp_path, claim_id="C1", source=source)
    _run(tmp_path, "assume", "--claim", "C1", "--id", "RH",
         "--statement", "The Riemann Hypothesis", "--source", "Riemann 1859")

    code, payload = _run(tmp_path, "revise-claim", "--id", "C1",
                         "--statement", "addition is commutative, restated")
    assert code == 0
    _, after = _run(tmp_path, "show", "--claim", "C1")
    assert after["claim"]["undischarged"] == ["RH"]

    code, refused = _run(tmp_path, "revise-claim", "--id", "C1", "--retire", "RH=")
    assert code == 1
    assert "needs a reason" in refused["error"]


# -- an unreferenced CLI is the same as no CLI ------------------------------

SKILLS = REPO_ROOT / "argus_skill" / "verticals" / "math" / "skills"


def test_the_engineer_is_told_which_commands_write_the_ledger() -> None:
    """A write path nobody is told to use records nothing on any real run.

    That is the failure this whole PR exists to fix, one layer up: the kernel
    was complete and unreachable because no code called it. A CLI that no skill
    mentions is unreachable for the same reason, by an agent instead of by a
    function.
    """
    text = (SKILLS / "engineer" / "math-research-execution.md").read_text(
        encoding="utf-8"
    )
    parser = math_state._build_parser()
    group = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    missing = [name for name in group.choices if f"$S {name} " not in text]
    assert missing == [], f"commands the Engineer is never told about: {missing}"
    assert "verify Main.lean" in text
    assert "--claim C1" in text


def test_the_reviewer_is_told_what_a_kernel_status_does_not_include() -> None:
    """The caveat is only useful if it reaches the role that can act on it."""
    text = (SKILLS / "reviewer" / "math-research-review.md").read_text(
        encoding="utf-8"
    )
    assert "math_state show" in text
    assert "math_state judge" in text
    assert "inconclusive" in text


def test_no_skill_tells_an_agent_to_select_an_evidence_tier() -> None:
    """Prose is a surface too: an instruction to pass a flag that does not exist
    teaches an agent to look for one, and the answer must be that there is none."""
    offenders: list[str] = []
    for path in sorted(SKILLS.rglob("*.md")):
        text = path.read_text(encoding="utf-8").lower()
        for phrase in ("--tier", "--force", "tier mechanical", "tier=mechanical"):
            if phrase in text:
                offenders.append(f"{path.name}: {phrase}")
    assert offenders == []


# -- end to end, on a host that has Lean ------------------------------------

@requires_lean
def test_a_real_compile_reaches_closed_kernel_through_the_documented_commands(
    tmp_path: Path,
) -> None:
    """No synthesized artifact anywhere: the compiler decides the status.

    This is the claim the PR rests on — that ``closed_kernel`` is reachable
    only by running a proof kernel — and the only way to check it is to run one.
    """
    from argus_skill.verticals.math.lean_evidence import main as lean_main

    source = _source(tmp_path)
    fidelity = _fidelity(tmp_path)
    _run(tmp_path, "context", "--id", "ctx", "--statement", "Natural numbers.")
    _run(tmp_path, "claim", "--id", "C1", "--context", "ctx",
         "--statement", "addition of naturals is commutative",
         "--formal-file", str(source))

    code = lean_main([
        "verify", str(source),
        "--statement-fidelity", str(fidelity),
        "--claim", "C1",
        "--project-root", str(tmp_path),
        "--timeout", "300",
    ])
    assert code == 0

    _, payload = _run(tmp_path, "show", "--claim", "C1")
    assert payload["claim"]["status"] == ClaimStatus.CLOSED_KERNEL.value
    producers = payload["claim"]["support"]["mechanical"]
    assert len(producers) == 1
    assert producers[0].startswith("lean_evidence/lean ")


@requires_lean
def test_a_real_compile_failure_leaves_the_claim_unproved_and_says_so(
    tmp_path: Path,
) -> None:
    """The other half: the exit code and the state agree that nothing was proved."""
    from argus_skill.verticals.math.lean_evidence import main as lean_main

    source = _source(
        tmp_path, "theorem argus_false (n : Nat) : n = n + 1 := by rfl\n"
    )
    fidelity = _fidelity(
        tmp_path,
        "# Statement fidelity\n\n`argus_false` states that every natural number "
        "equals its successor. Objects: naturals. Hypotheses: none. This is "
        "false, and the formalization renders the false claim faithfully.\n",
    )
    _run(tmp_path, "context", "--id", "ctx", "--statement", "Natural numbers.")
    _run(tmp_path, "claim", "--id", "C1", "--context", "ctx",
         "--statement", "every natural equals its successor",
         "--formal-file", str(source))

    assert lean_main([
        "verify", str(source),
        "--statement-fidelity", str(fidelity),
        "--claim", "C1",
        "--project-root", str(tmp_path),
        "--timeout", "300",
    ]) == 1

    _, payload = _run(tmp_path, "show", "--claim", "C1")
    assert payload["claim"]["status"] == ClaimStatus.PROPOSED.value
    assert payload["claim"]["support"] == {}
