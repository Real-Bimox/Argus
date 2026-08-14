"""Round-loop progress bookkeeping and optional low-risk self-review."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable

from ..core.models import ReviewDecision
from ..core.operator_decision import parse_agent_operator_options
from .round_state import (
    EngineerTurnOutcome,
    RoundControl,
    RoundLoopState,
    control_continue_loop,
    control_proceed,
)
from .round_stop_signals import _runner_result_has_successful_work_signal

if TYPE_CHECKING:
    from .runner import SupervisedConfig


def _engineer_operator_question(message: str) -> str:
    question = ""
    for line in str(message or "").splitlines():
        key, separator, value = line.partition("=")
        if not separator or key.strip().casefold() != "operator_question":
            continue
        candidate = value.strip()
        if candidate.casefold().rstrip(".") in {"", "none", "n/a", "na", "null"}:
            question = ""
        else:
            question = candidate[:500]
    return question


class RoundSelfReviewMixin:
    """Update progress state and settle low-risk work without another model."""

    def _handle_progress_and_self_review(
        self,
        *,
        round_index: int,
        supervised_config: "SupervisedConfig",
        workdir: Path,
        outcome: EngineerTurnOutcome,
        state: RoundLoopState,
        review_completed_hook,
        continue_adaptor,
        on_event: Callable[[dict], None] | None,
    ) -> RoundControl:
        state.backend_failure_streak = 0
        successful_work = _runner_result_has_successful_work_signal(
            outcome.engineer_result,
            engineer_message=outcome.engineer_message,
        )
        if successful_work:
            state.no_progress_streak = 0
        else:
            state.no_progress_streak += 1
        milestone_done = any(
            line.strip().casefold() == "milestone_status=done"
            for line in outcome.engineer_message.splitlines()
        )
        operator_question = _engineer_operator_question(outcome.engineer_message)
        if operator_question:
            operator_options = parse_agent_operator_options(outcome.engineer_message)
            return self._settle_round(
                review=ReviewDecision(
                    status="blocked",
                    reason="Engineer requires an operator-owned decision before continuing.",
                    next_action="Resume after the operator answers the pending question.",
                    operator_question=operator_question,
                    operator_options=operator_options,
                    review_source="engineer_operator_question",
                    planner_report={
                        "plan_signal": "continue",
                        "challenge": operator_question,
                        "authority_impact": "operator",
                    },
                ),
                round_index=round_index,
                supervised_config=supervised_config,
                workdir=workdir,
                outcome=outcome,
                state=state,
                review_completed_hook=review_completed_hook,
                continue_adaptor=continue_adaptor,
                on_event=on_event,
            )
        if not supervised_config.require_independent_review and successful_work:
            if milestone_done:
                return self._settle_round(
                    review=ReviewDecision(
                        status="done",
                        reason=(
                            "Engineer reported the requested milestone complete; "
                            "independent review was not required for this mission."
                        ),
                        next_action="",
                        review_source="engineer_self_review",
                    ),
                    round_index=round_index,
                    supervised_config=supervised_config,
                    workdir=workdir,
                    outcome=outcome,
                    state=state,
                    review_completed_hook=review_completed_hook,
                    continue_adaptor=continue_adaptor,
                    on_event=on_event,
                )
            return control_continue_loop()
        return control_proceed()


__all__ = ["RoundSelfReviewMixin", "_engineer_operator_question"]
