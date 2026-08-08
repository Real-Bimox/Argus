from __future__ import annotations

import json

import pytest

from argus_skill.core.models import ReviewDecision
from argus_skill.manager.stage_decider import (
    build_stage_decision_prompt,
    fallback_empty_stage_decision,
    final_stage_completion_decision,
    parse_stage_decision,
)

ORDER = ("research", "plan", "benchmark", "run", "analysis", "draft", "review", "submission")


def _review(status: str = "done") -> ReviewDecision:
    return ReviewDecision(
        status=status,
        reason="Reviewer inspected the evidence and made this judgment.",
        next_action="" if status == "done" else "Continue the work.",
    )


def test_prompt_uses_minimal_reviewer_verdict() -> None:
    prompt = build_stage_decision_prompt(
        current_stage="research",
        next_stage="plan",
        earlier_stages=(),
        checklist_md="Read the actual evidence.",
        review=_review(),
    )

    assert "status: done" in prompt
    assert "Reviewer inspected the evidence" in prompt
    for removed in (
        "scientific_decision",
        "planner_report",
        "Harness arbitration",
        "Reviewer per-item checklist",
    ):
        assert removed not in prompt


def test_parse_advance_immediate_ok() -> None:
    decision = parse_stage_decision(
        '{"action":"advance","target_stage":"plan","reason":"ok"}',
        current_stage="research",
        stage_order=ORDER,
    )
    assert decision.action == "advance"
    assert decision.target_stage == "plan"


def test_parse_advance_cannot_skip_stage() -> None:
    decision = parse_stage_decision(
        '{"action":"advance","target_stage":"benchmark","reason":"skip"}',
        current_stage="research",
        stage_order=ORDER,
    )
    assert decision.action == "hold"
    assert decision.diagnostic == "illegal_advance_target"


def test_parse_rollback_requires_earlier_stage() -> None:
    valid = parse_stage_decision(
        '{"action":"rollback","target_stage":"plan","reason":"repair"}',
        current_stage="run",
        stage_order=ORDER,
    )
    invalid = parse_stage_decision(
        '{"action":"rollback","target_stage":"draft","reason":"bad"}',
        current_stage="run",
        stage_order=ORDER,
    )
    assert valid.action == "rollback"
    assert invalid.action == "hold"


@pytest.mark.parametrize("target", ["`plan`", "plan stage"])
def test_target_formatting_is_normalized(target: str) -> None:
    decision = parse_stage_decision(
        json.dumps({"action": "advance", "target_stage": target, "reason": "ok"}),
        current_stage="research",
        stage_order=ORDER,
    )
    assert decision.action == "advance"
    assert decision.target_stage == "plan"


def test_invalid_manager_output_holds() -> None:
    decision = parse_stage_decision(
        '{"action":"unknown"}',
        current_stage="research",
        stage_order=ORDER,
    )
    assert decision.action == "hold"


def test_empty_manager_output_always_holds() -> None:
    decision = fallback_empty_stage_decision(
        _review(),
        current_stage="research",
        stage_order=ORDER,
    )
    assert decision.action == "hold"
    assert decision.diagnostic == "empty_output_no_manager_judgment"


def test_final_submission_done_can_complete_final_stage() -> None:
    decision = final_stage_completion_decision(
        _review(),
        current_stage="submission",
        stage_order=ORDER,
        mission_scope="final_submission",
    )
    assert decision is not None
    assert decision.action == "complete"


def test_bounded_done_does_not_auto_complete_final_stage() -> None:
    decision = final_stage_completion_decision(
        _review(),
        current_stage="submission",
        stage_order=ORDER,
        mission_scope="bounded",
    )
    assert decision is None


def test_no_second_machine_value_guard_overrides_manager() -> None:
    """The Manager's parsed decision is what reaches disk.

    This used to be pinned by calling ``enforce_scientific_stage_guard`` and
    asserting it returned its input — but that function had been reduced to
    ``_ = review, current_stage; return decision``, an identity function whose
    name still promised a guard. It was deleted; two live call sites went with
    it. The property it stood for is now pinned structurally instead: the write
    path does not receive the reviewer verdict at all, so there is nowhere for a
    second machine gate to reappear without that being visible in the signature.
    """
    import inspect

    from argus_skill.manager import stage_decider
    from argus_skill.manager._stage_ops import _StageDecisionMixin

    assert not hasattr(stage_decider, "enforce_scientific_stage_guard")

    params = set(inspect.signature(_StageDecisionMixin._apply_stage_decision_to_disk).parameters)
    assert params == {"self", "decision", "cur", "root"}

    manager = parse_stage_decision(
        '{"action":"advance","target_stage":"plan","reason":"review accepted"}',
        current_stage="research",
        stage_order=ORDER,
    )
    assert manager.action == "advance"
    assert manager.target_stage == "plan"


def test_reviewer_certified_intermediate_stage_skips_manager_model(
    tmp_path,
) -> None:
    from argus_skill.manager import Manager
    from argus_skill.skills.vertical_select import persist_vertical

    state_root = tmp_path / "state"
    workdir = tmp_path / "worktree"
    workdir.mkdir()
    persist_vertical(state_root, "kernel_engineering", workflow_mode="staged")

    decision = Manager(
        project_root=state_root,
        execution_workdir=workdir,
        runner=None,
    ).decide_stage_transition(
        review=_review(),
        project_root=state_root,
        mission_scope="bounded",
        open_ended=True,
        run_exec=lambda _prompt: (_ for _ in ()).throw(
            AssertionError("ordinary reviewed advance must not call Manager model")
        ),
    )

    state = json.loads(
        (state_root / "research" / "PIPELINE_STATE.json").read_text()
    )
    assert decision.action == "advance"
    assert decision.target_stage == "discover"
    assert decision.source == "reviewer_certified_policy"
    assert state["current_stage"] == "discover"
    assert state["stages"]["scope"]["status"] == "done"


def test_reviewer_certified_advance_still_obeys_completion_hook(
    tmp_path,
) -> None:
    from argus_skill.manager import Manager
    from argus_skill.skills.vertical_select import persist_vertical

    state_root = tmp_path / "state"
    workdir = tmp_path / "worktree"
    workdir.mkdir()
    persist_vertical(state_root, "kernel_engineering", workflow_mode="staged")
    state_path = state_root / "research" / "PIPELINE_STATE.json"
    state = json.loads(state_path.read_text())
    state["current_stage"] = "optimize"
    state["stages"] = {"optimize": {"status": "in_progress"}}
    state_path.write_text(json.dumps(state), encoding="utf-8")

    decision = Manager(
        project_root=state_root,
        execution_workdir=workdir,
        runner=None,
    ).decide_stage_transition(
        review=_review(),
        project_root=state_root,
        mission_scope="bounded",
        open_ended=True,
        run_exec=lambda _prompt: (_ for _ in ()).throw(
            AssertionError("deterministic completion failure must not call Manager")
        ),
    )

    assert decision.action == "hold"
    assert decision.source == "stage_completion_gate_hold"
    assert "no supported kernel winner" in decision.reason
    assert json.loads(state_path.read_text())["current_stage"] == "optimize"


def test_reviewer_certified_final_stage_skips_manager_model(
    tmp_path,
) -> None:
    from argus_skill.manager import Manager
    from argus_skill.skills.stage_machine import completion_contract_fingerprint
    from argus_skill.skills.vertical_select import persist_vertical
    from argus_skill.verticals._base import (
        load_vertical,
        vertical_completion_contract_version,
    )

    persist_vertical(tmp_path, "software", workflow_mode="staged")
    state_path = tmp_path / "research" / "PIPELINE_STATE.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["current_stage"] = "delivery"
    state["stages"] = {"delivery": {"status": "in_progress"}}
    state_path.write_text(json.dumps(state), encoding="utf-8")
    version = vertical_completion_contract_version(
        load_vertical("software", project_root=tmp_path)
    )
    state["stages"]["delivery"].update({
        "completion_contract_version": version,
        "completion_contract_sha256": completion_contract_fingerprint(
            tmp_path,
            "delivery",
            version=version,
        ),
    })
    state_path.write_text(json.dumps(state), encoding="utf-8")

    decision = Manager(project_root=tmp_path, runner=None).decide_stage_transition(
        review=_review(),
        project_root=tmp_path,
        mission_scope="bounded",
        run_exec=lambda _prompt: (_ for _ in ()).throw(
            AssertionError("deterministic final completion must not call Manager")
        ),
    )

    assert decision.action == "complete"
    assert decision.source == "reviewer_certified_policy"
