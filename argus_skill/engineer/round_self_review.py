"""Round-loop progress bookkeeping and optional low-risk self-review."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable

from ..core.models import ReviewDecision
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
        if not supervised_config.require_independent_review and successful_work:
            if milestone_done:
                return self._settle_round(
                    review=ReviewDecision(
                        status="done",
                        reason=(
                            "Engineer reached the Host-defined milestone decision "
                            "point; completion was accepted without an independent "
                            "Reviewer call."
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


__all__ = ["RoundSelfReviewMixin"]
