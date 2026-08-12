"""Read-only Reviewer checkpoint guidance and minimal verdict parsing."""

from __future__ import annotations

from argus_skill.reviewer import Reviewer, parse_decision_text


def _prompt(checkpoint_path: str = "/tmp/project/CHECKPOINT.md") -> str:
    r = Reviewer(runner=None, skill_store=None)
    return r._build_prompt(
        objective="minimize val_bpb",
        operator_messages=[],
        planner_review_instruction="",
        round_index=1,
        session_id=None,
        main_summary="(handoff)",
        main_error=None,
        checkpoint_path=checkpoint_path,
    )


def test_reviewer_is_not_given_checkpoint_bookkeeping():
    p = _prompt()
    assert "/tmp/project/CHECKPOINT.md" not in p
    assert "CHECKPOINT_RECOMMENDED" not in p
    assert "Do not inspect or edit checkpoint/context-packet/handoff bookkeeping" in p


def test_reviewer_never_acts_as_checkpoint_editor():
    p = _prompt()
    assert "strictly read-only" in p
    assert "Put the next Engineer instruction only in NEXT_ACTION" in p
    assert "only in proportion to unresolved uncertainty" in p
    assert "six total read/search tool calls" not in p


def test_checkpoint_state_is_not_copied_into_the_prompt():
    p = _prompt()
    assert "CURATED WORKING MEMORY" not in p
    assert "tried_and_failed" not in p


def test_reviewer_final_handoff_requires_explicit_progress_fields():
    p = _prompt()

    for field in (
        "FORWARD_PROGRESS=true|false",
        "PLAN_SIGNAL=continue|reconsider",
        "PLAN_CHALLENGE=<invalidated plan assumption, or none>",
        "PLAN_ALTERNATIVE=<better technical route, or none>",
        "AUTHORITY_IMPACT=technical|manager_contract|operator",
        "OPERATOR_OPTIONS=<id :: true|false :: label :: description; ...|none>",
    ):
        assert field in p
    assert "Return only STATUS, REASON, NEXT_ACTION and OPERATOR_QUESTION" not in p


def test_reviewer_output_without_confidence_parses_into_verdict():
    # The reviewer no longer self-reports a confidence. A structured output that
    # omits ``confidence`` entirely must still parse into a full verdict — the
    # parser must not depend on a confidence field to render a decision.
    raw = (
        '{"status": "done", "reason": "objective met with verified evidence", '
        '"next_action": "No further action needed.", '
        '"operator_question": null}'
    )
    decision = parse_decision_text(raw)
    assert decision is not None
    assert decision.status == "done"
    assert decision.reason == "objective met with verified evidence"
    # The parsed verdict carries no confidence attribute at all.
    assert not hasattr(decision, "confidence")
