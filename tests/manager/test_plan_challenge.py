from __future__ import annotations

from argus_skill.manager.plan_challenge import adjudicate_plan_challenge


def test_no_gap_alternative_replaces_skip_zero_working_plan() -> None:
    decision = adjudicate_plan_challenge(
        {
            "plan_signal": "reconsider",
            "challenge": "The preselected skip-zero candidate is not required.",
            "alternative": "Use the no-gap validator alternative.",
            "authority_impact": "technical",
        },
        reviewer_status="done",
        review_reason="The local candidate is complete but no longer preferred.",
    )

    assert decision.action == "replace"
    assert decision.authority_impact == "technical"
    assert "no-gap" in decision.alternative


def test_operator_owned_change_routes_back_to_operator() -> None:
    decision = adjudicate_plan_challenge(
        {
            "plan_signal": "reconsider",
            "challenge": "The requested trust boundary would need to expand.",
            "authority_impact": "operator",
        },
        reviewer_status="replan_requested",
        operator_question="May the trusted boundary be expanded?",
    )

    assert decision.action == "ask_operator"


def test_unchallenged_plan_is_kept() -> None:
    decision = adjudicate_plan_challenge(
        {"plan_signal": "continue", "forward_progress": True},
        reviewer_status="continue",
    )

    assert decision.action == "keep"
