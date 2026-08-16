"""Regression test: a correct COMPLETE must not be lost to a wording slip.

``parse_stage_decision`` used to accept ``complete`` only when ``target_stage``
was empty or exactly the current stage; anything else became a HOLD carrying
the diagnostic ``illegal_complete_target``. The policy bullet in the Manager
prompt does say to "COMPLETE at the current stage", but that reads as guidance
about *when* to complete — the format contract at the end of the prompt pinned
TARGET_STAGE for HOLD alone.

So a Manager that reasoned correctly still filled the field wrong. Testbed runs
11 (``s-b1a3757f``) and 12 (``s-44cb57c7``) each emitted::

    ACTION=complete
    TARGET_STAGE=review
    REASON=Reviewer-certified final submission satisfies the scoped problem...

against ``current_stage=scope``, and each was recorded as::

    {"action": "hold", "target_stage": "scope",
     "diagnostic": "illegal_complete_target"}

Nothing feeds that diagnostic back to the model, so the Manager had no way to
converge — it made the same call, and lost it, on every cycle. Both campaigns
completed and delivered all three phases anyway through the Goal Gate and the
final-submission path, so the stage machine sat at ``scope`` for both full runs
and nothing surfaced it as a failure.

Two changes, one prompt and one parser, because a prompt-only fix leaves a hard
gate keyed on a probabilistic output:

* the format contract now pins the field for COMPLETE as well as HOLD;
* a COMPLETE naming a *later* stage is normalized to the current one rather
  than rejected. The target is discarded before completion is actually decided
  — ``final_stage_completion_decision`` rules on review certification, mission
  scope, research target and the external gate regardless — so the syntactic
  check was buying nothing the real contract does not already enforce.

An *earlier* or unknown target stays fail-closed: that is a model confusing
completion with a rollback, not a wording slip.
"""

from __future__ import annotations

import pytest

from argus_skill.manager.stage_decider import parse_stage_decision

STAGES = ["scope", "solve", "review", "report"]


def _verdict(action: str, target: str, *, current: str = "scope"):
    return parse_stage_decision(
        f"ACTION={action}\nTARGET_STAGE={target}\nREASON=because",
        current_stage=current,
        stage_order=STAGES,
    )


def test_complete_at_the_current_stage_is_unchanged() -> None:
    decision = _verdict("complete", "scope")

    assert decision.action == "complete"
    assert decision.diagnostic == "valid_complete"


def test_complete_with_no_target_is_unchanged() -> None:
    decision = parse_stage_decision(
        "ACTION=complete\nREASON=because",
        current_stage="scope",
        stage_order=STAGES,
    )

    assert decision.action == "complete"
    assert decision.diagnostic == "valid_complete"


@pytest.mark.parametrize("target", ["solve", "review", "report"])
def test_a_later_target_is_normalized_not_dropped(target: str) -> None:
    """Runs 11 and 12's exact verdict. ``review`` is the one they emitted."""
    decision = _verdict("complete", target)

    assert decision.action == "complete"
    assert decision.target_stage == "scope"
    assert decision.diagnostic == "complete_target_normalized"


def test_the_deviation_is_still_named_in_the_trace() -> None:
    """Normalizing must not make the slip invisible to an operator."""
    assert _verdict("complete", "review").diagnostic != _verdict(
        "complete", "scope"
    ).diagnostic


def test_an_earlier_target_stays_fail_closed() -> None:
    decision = _verdict("complete", "solve", current="review")

    assert decision.action == "hold"
    assert decision.diagnostic == "illegal_complete_target"


def test_an_unknown_target_stays_fail_closed() -> None:
    decision = _verdict("complete", "publication")

    assert decision.action == "hold"
    assert decision.diagnostic == "illegal_complete_target"


@pytest.mark.parametrize("action", ["HOLD", "COMPLETE"])
def test_the_prompt_pins_target_stage_for_both_actions(action: str) -> None:
    """The format contract must name both actions where the field is defined.

    The parser is forgiving now, but a verdict that needs normalizing is still
    a verdict the operator has to read past.
    """
    from argus_skill.roles.prompts import manager as manager_prompts

    with open(manager_prompts.__file__, encoding="utf-8") as handle:
        text = handle.read()

    marker = "set TARGET_STAGE to the current stage"
    assert marker in text
    line = next(ln for ln in text.splitlines() if marker in ln)
    assert action in line.upper(), (
        f"the TARGET_STAGE format rule does not mention {action}; a Manager "
        "filling the field for that action has nothing to go on"
    )
