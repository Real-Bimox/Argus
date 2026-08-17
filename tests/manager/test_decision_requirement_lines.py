"""The contract's constraint sections were structurally unreachable.

``VerticalDecision`` has carried ``precise_constraints`` and ``ambiguities``
since the contract was introduced, and ``front_door`` reads all three of
constraints/exclusions/ambiguities off the decision to build
``goal_contract.json``. ``render_contract`` gives each its own heading in every
prompt that shows the contract.

None of it could ever fire:

* ``_DECISION_KEYS`` — the complete list of lines ``_decision_fields`` reads —
  named neither ``PRECISE_CONSTRAINTS`` nor ``AMBIGUITIES``, so
  ``_stated_requirements`` looked up keys the parser could not produce;
* the prompt never asked the Manager for them, so even a tolerant reader had
  nothing to read;
* ``exclusions`` had no field on ``VerticalDecision`` at all —
  ``front_door.py`` reached it through ``getattr(decision, "exclusions", ())``,
  which is a spelling of ``()``.

Testbed runs 15 (``s-f0dbba19``) and 16 (``s-ed5b69fc``) both wrote
``{"precise_constraints": null, "exclusions": null, "ambiguities": null}``.
Every downstream role was shown a contract with the operator's stated
requirements silently missing.

The three are read as one ``;``-separated line each, the same convention
``STAGES`` and ``LIVE_VIEW_PATHS`` already use.
"""

from __future__ import annotations

import pytest

from argus_skill.manager.domain_author import (
    _DECISION_KEYS,
    _decision_fields,
    _stated_requirements,
    parse_vertical_decision,
)
from argus_skill.roles.prompts.manager import build_vertical_decision_prompt

KNOWN = ("math", "research", "software")

RUN_16_SHAPED = """I read testbed.md and inspected the repository.

CHOICE=existing
VERTICAL=math
WORKFLOW_MODE=staged
EXECUTION_TASK=Prove or refute the stated conjecture.
RATIONALE=A pure mathematics conjecture with a Lean obligation.
RESEARCH_TARGET_LEVEL=exploratory
PRECISE_CONSTRAINTS=must compile under Lean 4; no sorry; no new axioms
EXCLUSIONS=do not modify mathlib; no numerical experiments
AMBIGUITIES=which universe cardinality bound the operator means
"""


def _decide(text: str):
    return parse_vertical_decision(text, known_verticals=KNOWN)


@pytest.mark.parametrize(
    "key", ["PRECISE_CONSTRAINTS", "EXCLUSIONS", "AMBIGUITIES"]
)
def test_the_parser_reads_the_key_the_prompt_asks_for(key: str) -> None:
    """Prompt and reader must name the same lines, or neither works."""
    assert key in _DECISION_KEYS
    assert key in build_vertical_decision_prompt(
        "prove something", verticals_with_purpose={"math": "mathematics"}
    )


def test_run_16s_decision_now_carries_its_requirements() -> None:
    decision = _decide(RUN_16_SHAPED)

    assert decision.precise_constraints == (
        "must compile under Lean 4",
        "no sorry",
        "no new axioms",
    )
    assert decision.exclusions == ("do not modify mathlib", "no numerical experiments")
    assert decision.ambiguities == ("which universe cardinality bound the operator means",)


def test_exclusions_is_a_real_field_not_a_getattr_default() -> None:
    """``front_door`` reads it through ``getattr``; that must find something."""
    decision = _decide(RUN_16_SHAPED)

    assert "exclusions" in type(decision).__dataclass_fields__
    assert getattr(decision, "exclusions", ()) == decision.exclusions


def test_a_new_domain_decision_carries_them_too() -> None:
    """Both decision shapes reach the same contract writer."""
    decision = _decide(
        "CHOICE=new\n"
        "VERTICAL=knot_theory\n"
        "STAGES=survey; construct; verify\n"
        "WORKFLOW_MODE=staged\n"
        "EXECUTION_TASK=Classify the invariants.\n"
        "RATIONALE=No existing vertical covers knot invariants.\n"
        "CONFIDENCE=0.8\n"
        "PRECISE_CONSTRAINTS=finish within 40 rounds\n"
        "EXCLUSIONS=no machine-learning surrogates\n"
        "AMBIGUITIES=which knot table to use\n"
    )

    assert decision.precise_constraints == ("finish within 40 rounds",)
    assert decision.exclusions == ("no machine-learning surrogates",)
    assert decision.ambiguities == ("which knot table to use",)


def test_none_is_an_answer_and_reads_as_empty() -> None:
    decision = _decide(
        RUN_16_SHAPED.replace("EXCLUSIONS=do not modify mathlib; no numerical experiments", "EXCLUSIONS=none")
    )

    assert decision.exclusions == ()


def test_an_unanswered_line_is_absent_rather_than_empty() -> None:
    """The contract writer distinguishes "not asked" from "answered none".

    ``revise_contract`` keeps a standing clause when the field is absent and
    clears it when the field is explicitly empty, so collapsing the two would
    let a silent Manager erase a constraint the operator set earlier.
    """
    fields = _decision_fields(
        "CHOICE=existing\nVERTICAL=math\nEXECUTION_TASK=go\nWORKFLOW_MODE=staged\n"
    )

    assert "exclusions" not in fields
    assert "precise_constraints" not in fields


def test_a_semicolon_separates_but_a_comma_does_not() -> None:
    """A constraint contains commas far more often than semicolons.

    ``read_list`` splits on ``;`` and ``|`` only; this pins that a constraint
    written with commas arrives in one piece rather than cut in half.
    """
    decision = _decide(
        RUN_16_SHAPED.replace(
            "PRECISE_CONSTRAINTS=must compile under Lean 4; no sorry; no new axioms",
            "PRECISE_CONSTRAINTS=at least 1.5x faster, measured on B200, over PyTorch",
        )
    )

    assert decision.precise_constraints == (
        "at least 1.5x faster, measured on B200, over PyTorch",
    )


def test_the_operators_wording_is_not_reworded() -> None:
    """A paraphrased constraint is already a revision of what was agreed."""
    verbatim = "the bound must be strictly less than 2^aleph_0, not <="
    decision = _decide(
        RUN_16_SHAPED.replace(
            "PRECISE_CONSTRAINTS=must compile under Lean 4; no sorry; no new axioms",
            f"PRECISE_CONSTRAINTS={verbatim}",
        )
    )

    assert decision.precise_constraints == (verbatim,)


def test_a_volunteered_json_object_still_works() -> None:
    """The legacy door fed these three long before the named lines existed."""
    stated, exclusions, ambiguities = _stated_requirements(
        {
            "precise_constraints": ["a", "a", "b"],
            "exclusions": ["c"],
            "ambiguities": ["d"],
        }
    )

    assert (stated, exclusions, ambiguities) == (("a", "b"), ("c",), ("d",))


def test_the_prompt_forbids_inventing_a_constraint() -> None:
    """A constraint nobody asked for becomes a goal nobody agreed to."""
    prompt = build_vertical_decision_prompt(
        "prove something", verticals_with_purpose={"math": "mathematics"}
    )

    assert "invent" in prompt.lower()
