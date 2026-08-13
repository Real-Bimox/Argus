"""One mission, one claim's neighbourhood, and nothing else in the prompt.

A mathematics project's recorded state is the wrong shape to hand an agent.
It grows without bound, most of it is about claims this task is not working
on, and the part that matters — what is still taken on faith, what evidence
binds to the statement *as it now reads*, which routes are already dead — is
buried in it. Pasting the file in is unreadable; pasting a summary of "the
project so far" is unreadable and still does not say which claim this task is
about.

The projection exists to answer that second question first, and the tests
below are organised around the four properties that make it safe to put its
output into an Engineer's prompt:

* **Targeting.** The claim is found in the mission's own text, most-decisive
  field first. Naming nothing is fine and yields nothing; naming two claims is
  refused rather than guessed at, because a fragment aimed at the wrong
  theorem is internally consistent and therefore invisible.
* **Boundedness.** What appears is a function of the claim, not of the
  project. A project that grew by forty claims renders the same bytes.
* **Determinism.** Same store, same mission, same bytes — no timestamps, no
  host paths, no dict-order dependence — so an unchanged digest really does
  mean nothing moved.
* **Degrading honestly.** No recorded mathematics means no fragment. A store
  that cannot be read means a fragment that *says so*, because silence there
  would tell the Engineer that a project holding a hundred proofs believes
  nothing.

The adversarial cases are cheap to build and would be expensive to notice: a
claim id that is a prefix of another id, a lemma named only in the non-goals,
evidence left over from a previous version of the statement.
"""
from __future__ import annotations

import json
from pathlib import Path

from argus_skill.life.memory import BacklogItem
from argus_skill.research_math import (
    ClaimVersion,
    ContextVersion,
    EvidenceRecord,
    EvidenceTier,
    ExternalAssumption,
    MathState,
    ProofRoute,
    Verdict,
    load_state,
    save_state,
    state_path,
)
from argus_skill.verticals._base import load_vertical_contract
from argus_skill.verticals.math.context_projection import (
    MISSION_TARGET_FIELDS,
    project_mission_context,
    resolve_target,
)

# -- fixtures ---------------------------------------------------------------

SZEMEREDI = ExternalAssumption(
    assumption_id="szemeredi-trotter",
    statement="Point-line incidences in the plane are O((mn)^(2/3) + m + n).",
    source="Szemeredi-Trotter 1983",
)


def _context(state: MathState, context_id: str, statement: str, **definitions: str):
    return state.add_context(
        ContextVersion(
            context_id=context_id,
            version=1,
            statement=statement,
            definitions=dict(definitions),
        )
    )


def _claim(
    state: MathState,
    claim_id: str,
    context: ContextVersion,
    natural: str,
    *,
    formal: str = "",
    assumptions: tuple[ExternalAssumption, ...] = (),
) -> ClaimVersion:
    return state.add_claim(
        ClaimVersion(
            claim_id=claim_id,
            version=1,
            context=context.ref(),
            natural_statement=natural,
            formal_statement=formal,
            external_assumptions=assumptions,
        )
    )


def _lean(
    claim: ClaimVersion,
    evidence_id: str,
    *,
    verdict: Verdict = Verdict.SUPPORTS,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        subject=claim.ref(),
        tier=EvidenceTier.MECHANICAL,
        verdict=verdict,
        produced_by="lean_check 4.9.0",
        artifact="research/lean/lean_check.json",
    )


def _seed(tmp_path: Path) -> MathState:
    """Two unrelated claims, each with its own context, routes and evidence.

    Two is the minimum that can show a leak: every anti-leak test below asserts
    something about `erdos-sum` while projecting `udist-main`, and would pass
    vacuously against a store holding one claim.
    """
    state = MathState()

    plane = _context(
        state,
        "ctx-plane",
        "Bound the number of unit distances among n points in the plane.",
        **{
            "unit distance": "a pair of points at Euclidean distance exactly 1",
            "incidence": "a point lying on a line",
        },
    )
    main = _claim(
        state,
        "udist-main",
        plane,
        "The number of unit distances among n planar points is O(n^(4/3)).",
        formal="theorem unit_distance_bound (n : Nat) : ...",
        assumptions=(SZEMEREDI,),
    )
    lemma = _claim(
        state,
        "lemma-crossing",
        plane,
        "A graph with e >= 4v edges has crossing number at least e^3 / (64 v^2).",
    )
    deep = _claim(
        state,
        "lemma-euler",
        plane,
        "A simple planar graph on v >= 3 vertices has at most 3v - 6 edges.",
    )
    state.add_evidence(_lean(main, "ev-lean-main"))
    state.add_route(
        ProofRoute(
            route_id="via-crossing",
            goal=main.ref(),
            obligations=(lemma.ref(),),
            retired_because="",
        )
    )
    state.add_route(
        ProofRoute(
            route_id="via-incidence",
            goal=main.ref(),
            obligations=(lemma.ref(),),
            retired_because="the incidence bound it needs is the theorem itself",
        )
    )
    # The second hop. If the projection ever follows dependencies transitively,
    # `lemma-euler` shows up in a mission about `udist-main`.
    state.add_route(
        ProofRoute(
            route_id="crossing-via-euler",
            goal=lemma.ref(),
            obligations=(deep.ref(),),
            retired_because="",
        )
    )

    sums = _context(
        state,
        "ctx-sums",
        "Distinct sums of a finite set of reals.",
        **{"sumset": "the set of pairwise sums of a set with itself"},
    )
    other = _claim(
        state,
        "erdos-sum",
        sums,
        "A set of n reals has at least n^(2-o(1)) distinct sums or products.",
    )
    state.add_evidence(_lean(other, "ev-lean-sum"))
    state.add_route(
        ProofRoute(
            route_id="sum-via-elekes",
            goal=other.ref(),
            obligations=(),
            retired_because="",
        )
    )

    save_state(tmp_path, state)
    return state


def _mission(**fields: object) -> BacklogItem:
    """A backlog item shaped the way the Planner actually delivers one."""
    return BacklogItem.new(
        title=str(fields.pop("title", "Advance the current bound")),
        objective=str(fields.pop("objective", "Make progress on the open case")),
        **fields,  # type: ignore[arg-type]
    )


def _project(tmp_path: Path, **fields: object) -> str:
    return project_mission_context(project_root=tmp_path, mission=_mission(**fields))


# -- targeting --------------------------------------------------------------

def test_two_missions_about_different_claims_get_different_context(
    tmp_path: Path,
) -> None:
    """The point of the hook: per mission, not per stage.

    Before this existed, every task in a stage received the same block, which
    is the same as writing it once in the role banner. If these two fragments
    were ever equal the whole mechanism would be decoration.
    """
    _seed(tmp_path)

    unit = _project(tmp_path, acceptance_check="udist-main is proved or refuted.")
    sums = _project(tmp_path, acceptance_check="erdos-sum is proved or refuted.")

    assert unit and sums
    assert unit != sums
    assert "udist-main" in unit and "erdos-sum" not in unit
    assert "erdos-sum" in sums and "udist-main" not in sums


def test_the_acceptance_check_decides_the_target_before_the_title(
    tmp_path: Path,
) -> None:
    """One field has to win, and it should be the one that says what is owed.

    A title is a label an agent wrote to be readable; the acceptance check is
    the field whose declared job is to state what this round must make true.
    When they disagree, believing the title would aim the fragment at whatever
    the task was filed under rather than at what it has to move.
    """
    _seed(tmp_path)

    fragment = _project(
        tmp_path,
        title="Follow-up work on erdos-sum",
        acceptance_check="A recorded verdict for udist-main.",
    )

    assert "claim `udist-main`" in fragment
    assert "erdos-sum" not in fragment
    assert MISSION_TARGET_FIELDS[0] == "acceptance_check"


def test_a_claim_named_only_in_the_non_goals_is_not_the_target(
    tmp_path: Path,
) -> None:
    """Naming a claim to exclude it must not select it.

    ``non_goals`` is the Planner's field for "not this round". Scanning it for
    ids would invert its meaning and aim the entire fragment at the one
    statement the mission was told to leave alone -- and the Engineer, reading
    a coherent block about a real claim, has no way to notice.
    """
    _seed(tmp_path)

    fragment = _project(
        tmp_path,
        acceptance_check="A recorded verdict for udist-main.",
        non_goals=["Do not touch erdos-sum this round."],
    )

    assert "claim `udist-main`" in fragment
    assert "erdos-sum" not in fragment
    assert "non_goals" not in MISSION_TARGET_FIELDS


def test_a_claim_id_is_not_matched_inside_a_longer_id(tmp_path: Path) -> None:
    """Ids in this schema share prefixes as a matter of course.

    ``lemma-crossing`` contains no separate claim here, but a project that
    holds both ``lemma`` and ``lemma-crossing`` is entirely normal, and a
    substring match would make the shorter id a permanent false positive that
    also makes every mission about the longer one ambiguous.
    """
    state = MathState()
    context = _context(state, "ctx", "Crossing numbers.")
    _claim(state, "lemma", context, "The short one.")
    _claim(state, "lemma-crossing", context, "The long one.")
    save_state(tmp_path, state)

    target = resolve_target(
        _mission(acceptance_check="Prove lemma-crossing."),
        ("lemma", "lemma-crossing"),
    )

    assert target.claim_id == "lemma-crossing"
    assert not target.ambiguous


def test_a_mission_that_names_two_claims_is_refused_rather_than_guessed(
    tmp_path: Path,
) -> None:
    """Ambiguity is reported, not broken by a tiebreak.

    Picking the first, or the longest, or falling through to the title would
    produce a fragment that is correct-looking prose about a real claim the
    mission may not be about. The Engineer cannot detect that. A block that
    says "I could not tell which" can be acted on.
    """
    _seed(tmp_path)

    fragment = _project(
        tmp_path,
        acceptance_check="Both udist-main and erdos-sum have recorded verdicts.",
    )

    assert fragment.startswith("## Mathematical state not projected")
    assert "`udist-main`" in fragment and "`erdos-sum`" in fragment
    # Nothing about either claim's actual state: that is the guess it refused.
    assert "Taken on faith" not in fragment
    assert "szemeredi-trotter" not in fragment


def test_a_mission_that_names_no_recorded_claim_contributes_nothing(
    tmp_path: Path,
) -> None:
    """Most math tasks name no claim id, and must pay nothing for the feature.

    The fallback is silence rather than "here is the whole project", because
    the only thing worse than no context is a page of context about claims
    chosen by proximity.
    """
    _seed(tmp_path)

    assert _project(
        tmp_path,
        title="Read the literature on distance problems",
        objective="Find out what is known about incidence bounds.",
    ) == ""


# -- what the fragment says -------------------------------------------------

def test_the_fragment_states_the_claim_its_faith_its_evidence_and_its_next_steps(
    tmp_path: Path,
) -> None:
    """The five things a mission cannot reconstruct by reading the repository.

    Each of these is a decision already made and recorded: the exact statement
    and version in force, what it is still standing on, what has actually
    checked it, what the live plan owes, and which branch is already dead.
    An Engineer without them re-derives the state from the files and gets it
    wrong in the expensive direction -- by retrying a retired route or by
    treating an assumption as proved.
    """
    _seed(tmp_path)

    fragment = _project(tmp_path, acceptance_check="Record a verdict for udist-main.")

    assert "claim `udist-main` v1" in fragment
    assert "unit distances" in fragment          # the statement itself
    assert "`unit distance`" in fragment         # the definition it names
    assert "szemeredi-trotter" in fragment       # still taken on faith
    assert "`ev-lean-main`" in fragment          # what checked this statement
    assert "`via-crossing`" in fragment          # the live route
    assert "`lemma-crossing`" in fragment        # what that route owes
    assert "`via-incidence`" in fragment         # already retired
    assert "the incidence bound it needs is the theorem itself" in fragment
    assert "closed_kernel" in fragment           # what would move it


def test_only_the_first_hop_of_the_proof_tree_is_shown(tmp_path: Path) -> None:
    """Depth 1, because depth 2 is the whole tree.

    ``lemma-euler`` is what ``lemma-crossing`` needs, not what this claim
    needs. Following dependencies transitively in a project with a real proof
    tree reproduces the state file, which is the thing this module exists not
    to send -- and none of those statements is something this round could move
    anyway.
    """
    _seed(tmp_path)

    fragment = _project(tmp_path, acceptance_check="Record a verdict for udist-main.")

    assert "`lemma-crossing`" in fragment
    assert "lemma-euler" not in fragment
    assert "crossing-via-euler" not in fragment


def test_evidence_for_an_earlier_version_is_shown_as_not_evidence(
    tmp_path: Path,
) -> None:
    """A restated claim keeps its history and loses its certificate.

    This is the single most dangerous thing an agent can get wrong here:
    ``ev-lean-main`` is a real mechanical pass, it is still in the file, and it
    is about a sentence the project no longer asserts. Dropping it silently
    would hide that the proof exists for something; listing it as evidence
    would launder it into support for the new statement. It is named, under a
    heading that says it is not evidence for this version.
    """
    state = _seed(tmp_path)
    state.revise_claim(
        "udist-main",
        natural_statement="The number of unit distances is O(n^(1+eps)).",
    )
    save_state(tmp_path, state)

    fragment = _project(tmp_path, acceptance_check="Record a verdict for udist-main.")

    assert "claim `udist-main` v2" in fragment
    assert "not evidence for it" in fragment
    assert "`ev-lean-main`" in fragment
    assert "none. Nothing has checked this statement as it now stands." in fragment


# -- boundedness ------------------------------------------------------------

def test_the_fragment_does_not_grow_with_the_project(tmp_path: Path) -> None:
    """Size is a property of the claim, not of how long the project has run.

    This is the property that decides whether the hook is usable in month six.
    Anything that scales with the store -- a project summary, an index of open
    claims, a "recent activity" list -- eventually costs more context than the
    mission itself and gets skimmed, at which point the parts that matter are
    skimmed too.
    """
    state = _seed(tmp_path)
    before = _project(tmp_path, acceptance_check="Record a verdict for udist-main.")

    context = state.latest_context("ctx-sums")
    assert context is not None
    for index in range(40):
        filler = _claim(
            state,
            f"filler-{index:03d}",
            context,
            f"Auxiliary estimate number {index}.",
        )
        state.add_evidence(_lean(filler, f"ev-filler-{index:03d}"))
        state.add_route(
            ProofRoute(
                route_id=f"route-filler-{index:03d}",
                goal=filler.ref(),
                obligations=(),
                retired_because="",
            )
        )
    save_state(tmp_path, state)

    after = _project(tmp_path, acceptance_check="Record a verdict for udist-main.")

    assert after == before
    assert "filler-" not in after


def test_work_on_an_unrelated_claim_leaves_this_mission_byte_identical(
    tmp_path: Path,
) -> None:
    """Anti-leak, stated as a diff rather than as an absence.

    Asserting only that ``erdos-sum`` does not appear would still pass if some
    aggregate over the whole store -- a count, a status tally, a digest of
    everything -- crept into the text. Byte equality across a real change
    elsewhere in the file is the stronger claim, and it is the one that makes
    the fragment's own digest mean "nothing about this claim moved".
    """
    state = _seed(tmp_path)
    before = _project(tmp_path, acceptance_check="Record a verdict for udist-main.")

    other = state.revise_claim(
        "erdos-sum",
        natural_statement="A set of n reals has at least n^(2-o(1)) distinct sums.",
        external_assumptions=(SZEMEREDI,),
    )
    state.add_evidence(_lean(other, "ev-sum-second", verdict=Verdict.REFUTES))
    save_state(tmp_path, state)

    assert _project(tmp_path, acceptance_check="Record a verdict for udist-main.") == before


def test_a_change_to_the_target_claim_changes_what_the_mission_sees(
    tmp_path: Path,
) -> None:
    """The other side of the byte-identity claim.

    A fragment that were stable under changes to its *own* claim would be
    stable for the wrong reason -- and the digest it carries would say "nothing
    moved" while the claim moved. Discharging the assumption is the change with
    the largest consequence in the kernel: it takes the claim from conditional
    to closed.
    """
    state = _seed(tmp_path)
    before = _project(tmp_path, acceptance_check="Record a verdict for udist-main.")
    assert "szemeredi-trotter" in before

    state.add_evidence(
        EvidenceRecord(
            evidence_id="ev-szt",
            subject=SZEMEREDI.ref(),
            tier=EvidenceTier.MECHANICAL,
            verdict=Verdict.SUPPORTS,
            produced_by="lean_check 4.9.0",
            artifact="research/lean/szemeredi_trotter.json",
        )
    )
    save_state(tmp_path, state)

    after = _project(tmp_path, acceptance_check="Record a verdict for udist-main.")

    assert after != before
    assert "(closed_kernel)" in after
    # Still named, because a discharged assumption is a covered dependency
    # rather than an absent one, and a reader who cannot see it has no way to
    # ask whether the discharge is any good.
    assert "szemeredi-trotter" in after


# -- determinism ------------------------------------------------------------

def test_the_same_mission_on_an_unchanged_store_renders_the_same_bytes(
    tmp_path: Path,
) -> None:
    """Byte-identical, or the digest it prints is worth nothing.

    Two runs of the same mission that differ by a timestamp, an iteration
    order, or a host path would make every comparison between fragments read
    as "something changed", which trains the reader to ignore the one time it
    did. The reload in the middle is deliberate: it re-parses the JSON, so a
    dependence on in-memory insertion order would show up here.
    """
    _seed(tmp_path)
    check = "Record a verdict for udist-main."

    first = _project(tmp_path, acceptance_check=check)
    reloaded = load_state(tmp_path)
    save_state(tmp_path, reloaded)
    second = _project(tmp_path, acceptance_check=check)

    assert first == second
    assert first.count("fragment digest") == 1
    # A host path would differ between machines and between worktrees, and
    # would put the operator's directory layout into a model's prompt.
    assert str(tmp_path) not in first


# -- degrading honestly -----------------------------------------------------

def test_a_project_with_no_recorded_mathematics_contributes_nothing(
    tmp_path: Path,
) -> None:
    """Almost every math project is this one, and it must pay nothing.

    Both the never-written case and the written-but-empty case return the same
    thing, because both mean the same thing: this project records no claims.
    Neither may raise -- the hook runs inside mission setup, where an exception
    is a failed mission.
    """
    assert _project(tmp_path, acceptance_check="Prove udist-main.") == ""

    save_state(tmp_path, MathState())

    assert _project(tmp_path, acceptance_check="Prove udist-main.") == ""


def test_an_unreadable_state_says_so_instead_of_looking_empty(
    tmp_path: Path,
) -> None:
    """A broken file and an absent one mean opposite things.

    Returning ``""`` for a corrupt store would tell a project with a hundred
    recorded proofs that it believes nothing -- and the Engineer's rational
    next move is to start recording claims into the file that is already
    holding them, over the top of proofs it cannot read. The block names the
    file and refuses to characterise the state.
    """
    _seed(tmp_path)
    state_path(tmp_path).write_text("{not json", encoding="utf-8")

    fragment = _project(tmp_path, acceptance_check="Record a verdict for udist-main.")

    assert fragment.startswith("## Mathematical state unavailable")
    assert "research/MATH_STATE.json" in fragment
    assert "not as empty" in fragment
    assert str(tmp_path) not in fragment


def test_a_state_file_with_the_wrong_shape_is_unreadable_not_empty(
    tmp_path: Path,
) -> None:
    """Valid JSON is not a valid state, and the difference is not visible.

    A hand-edit or a half-finished write leaves a file that parses. The kernel
    rejects it; this asserts the rejection reaches the prompt as a stated
    failure rather than as silence, which is the same argument as the corrupt
    case but a much likelier accident.
    """
    _seed(tmp_path)
    state_path(tmp_path).write_text(json.dumps(["claims"]), encoding="utf-8")

    fragment = _project(tmp_path, acceptance_check="Record a verdict for udist-main.")

    assert fragment.startswith("## Mathematical state unavailable")
    assert str(tmp_path) not in fragment


# -- wiring -----------------------------------------------------------------

def test_the_math_vertical_serves_this_projection_as_its_mission_prelude(
    tmp_path: Path,
) -> None:
    """The module is only worth anything if the contract actually calls it.

    Everything above tests the projector directly and would keep passing if
    ``stages.prepare_mission`` were deleted or never wired up. This is the one
    test that fails when the hook is disconnected -- it goes through the same
    contract object the supervisor builds, with the same keyword arguments.
    """
    _seed(tmp_path)
    item = _mission(acceptance_check="Record a verdict for udist-main.")
    contract = load_vertical_contract("math", project_root=tmp_path)

    block = contract.prepare_mission(
        stage="solve",
        project_root=tmp_path,
        state_root=tmp_path / "runtime",
        mission=item,
    )

    assert block == project_mission_context(project_root=tmp_path, mission=item)
    assert "claim `udist-main`" in block
