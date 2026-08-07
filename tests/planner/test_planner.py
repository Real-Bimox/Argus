from __future__ import annotations

from argus_skill.core.models import RunnerResult
from argus_skill.planner.planner import (
    NO_CONCRETE_TASKS_ERROR,
    OPEN_ENDED_PROJECT_DONE_ERROR,
    PLANNER_SUPERSEDED_ERROR,
    Planner,
    PlannerConfig,
    parse_planner_text,
)
from argus_skill.roles.prompts.planner import _PLANNER_CORE_CONTRACT


def test_parse_key_value_completion_after_freeform_progress() -> None:
    verdict = parse_planner_text(
        "Implemented the source change and ran the focused tests.\n"
        "PROJECT_DONE=true\n"
        "REASON=Updated the parser and verified the regression suite."
    )

    assert verdict.error == ""
    assert verdict.project_done is True
    assert verdict.new_tasks == []
    assert verdict.reason == "Updated the parser and verified the regression suite."


def test_parse_task_workdir_for_nested_target_repository() -> None:
    verdict = parse_planner_text(
        "\n".join([
            "PROJECT_DONE=false",
            "REASON=work in the cloned target repository",
            "TASK_KEY=target",
            "TASK_TITLE=Repair target kernel",
            "TASK_OBJECTIVE=Edit and test the target kernel.",
            "TASK_HYPOTHESIS=The target kernel contains the defect.",
            "TASK_GOAL_CONTRIBUTION=Fix the operator's target repository.",
            "TASK_EXPECTED_REGRESSIONS=The focused test may stay red during repair.",
            "TASK_DECISION_RULE=Replan if the defect is outside this repository.",
            "TASK_WORKDIR=flash-linear-attention",
            "TASK_ACCEPTANCE_CHECK=pytest tests/ops/test_attnres.py -q",
        ])
    )

    assert verdict.error == ""
    assert verdict.new_tasks[0].execution_workdir == "flash-linear-attention"


def test_parse_status_summary_aliases() -> None:
    verdict = parse_planner_text(
        "STATUS=completed\nSUMMARY=Implementation and verification finished."
    )

    assert verdict.project_done is True
    assert verdict.reason == "Implementation and verification finished."


def test_parse_task_blocker_fingerprint() -> None:
    verdict = parse_planner_text(
        "PROJECT_DONE=false\n"
        "REASON=The same external blocker remains.\n"
        "TASK_KEY=retry\n"
        "TASK_TITLE=Retry renamed task\n"
        "TASK_OBJECTIVE=Verify whether the blocker changed.\n"
        "TASK_BLOCKER_FINGERPRINT=dataset-license:benchmark-x"
    )

    assert verdict.error == ""
    assert verdict.new_tasks[0].blocker_fingerprint == "dataset-license:benchmark-x"


def test_incomplete_key_value_result_is_retryable() -> None:
    verdict = parse_planner_text(
        "PROJECT_DONE=false\nREASON=External credential is still required."
    )

    assert verdict.project_done is False
    assert verdict.error == "planner said not done but produced no concrete tasks"


def test_missing_completion_marker_is_retryable() -> None:
    verdict = parse_planner_text("I inspected the repository but did not finish.")

    assert verdict.project_done is False
    assert verdict.error == "planner missing key-value completion marker"


def test_planner_prompt_requires_read_only_delegation_and_plain_key_values() -> None:
    assert "Planner read-only delegation contract" in _PLANNER_CORE_CONTRACT
    assert "Do not edit project files" in _PLANNER_CORE_CONTRACT
    assert "Engineer owns edits" in _PLANNER_CORE_CONTRACT
    assert "PROJECT_DONE=true|false" in _PLANNER_CORE_CONTRACT
    assert "not JSON" in _PLANNER_CORE_CONTRACT


class _Runner:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def run_exec(self, **kwargs):  # noqa: ANN003
        self.calls.append(kwargs)
        return RunnerResult(
            exit_code=0,
            agent_messages=[
                "Changed the implementation.\n"
                "PROJECT_DONE=true\n"
                "REASON=Focused verification passed."
            ],
        )


class _SequenceRunner:
    def __init__(self, messages: list[str]) -> None:
        self.messages = list(messages)
        self.calls: list[dict] = []

    def run_exec(self, **kwargs):  # noqa: ANN003
        self.calls.append(kwargs)
        return RunnerResult(exit_code=0, agent_messages=[self.messages.pop(0)])


def test_plan_next_disables_schema_and_planner_timeouts(monkeypatch) -> None:
    runner = _Runner()
    monkeypatch.setattr(
        Planner,
        "_build_planner_prompt",
        staticmethod(lambda **kwargs: "direct execution prompt"),
    )

    verdict = Planner(runner).plan_next(
        continuous_objective="fix the issue",
        config=PlannerConfig(
            working_dir="/tmp/project",
            add_dirs=["/tmp/project-state"],
            dangerous_yolo=True,
        ),
    )

    assert verdict.project_done is True
    call = runner.calls[0]
    assert call["run_label"] == "planner.cycle0"
    options = call["options"]
    assert not hasattr(options, "output_schema_path")
    assert options.external_interrupt_reason_provider is None
    assert options.watchdog_hard_idle_seconds == 0
    assert options.dangerous_yolo is True
    assert options.full_auto is False
    assert options.sandbox_mode is None
    assert options.add_dirs == ["/tmp/project-state"]


def test_plan_next_defaults_to_full_tool_access(monkeypatch) -> None:
    runner = _Runner()
    monkeypatch.setattr(
        Planner,
        "_build_planner_prompt",
        staticmethod(lambda **kwargs: "direct execution prompt"),
    )

    Planner(runner).plan_next(
        continuous_objective="inspect safely",
        config=PlannerConfig(working_dir="/tmp/project"),
    )

    options = runner.calls[0]["options"]
    assert options.dangerous_yolo is True
    assert options.full_auto is False
    assert options.sandbox_mode is None


def test_plan_next_repairs_not_done_empty_task_response(monkeypatch) -> None:
    runner = _SequenceRunner([
        "PROJECT_DONE=false\nREASON=implementation still needs a concrete follow-up",
        "\n".join(
            [
                "PROJECT_DONE=false",
                "REASON=queue the concrete verifier repair",
                "TASK_KEY=verifier",
                "TASK_TITLE=Repair verifier path",
                (
                    "TASK_OBJECTIVE=Update src/verifier.py and run pytest "
                    "tests/test_verifier.py."
                ),
                "TASK_HYPOTHESIS=The verifier path is the remaining defect.",
                "TASK_GOAL_CONTRIBUTION=Restore trustworthy verification for the objective.",
                "TASK_EXPECTED_REGRESSIONS=The focused verifier may stay red during repair.",
                "TASK_DECISION_RULE=Replan if the failing evidence points outside this path.",
                "TASK_ACCEPTANCE_CHECK=pytest tests/test_verifier.py",
            ]
        ),
    ])
    monkeypatch.setattr(
        Planner,
        "_build_planner_prompt",
        staticmethod(lambda **kwargs: "original planner prompt"),
    )

    verdict = Planner(runner).plan_next(
        continuous_objective="fix the verifier",
        planning_cycle=7,
        config=PlannerConfig(working_dir="/tmp/project"),
    )

    assert verdict.error == ""
    assert verdict.project_done is False
    assert [task.title for task in verdict.new_tasks] == ["Repair verifier path"]
    assert verdict.new_tasks[0].hypothesis == "The verifier path is the remaining defect."
    assert verdict.new_tasks[0].goal_contribution.startswith("Restore trustworthy")
    assert runner.calls[0]["run_label"] == "planner.cycle7"
    assert runner.calls[1]["run_label"] == "planner.cycle7.repair1"
    assert NO_CONCRETE_TASKS_ERROR in runner.calls[1]["prompt"]
    assert (
        "Never return `PROJECT_DONE=false` without either `WAITING=true`"
        in runner.calls[1]["prompt"]
    )
    assert "TASK_HYPOTHESIS=..." in runner.calls[1]["prompt"]
    assert "TASK_GOAL_CONTRIBUTION=..." in runner.calls[1]["prompt"]
    assert runner.calls[1]["options"].working_dir == "/tmp/project"


def test_plan_next_repairs_missing_mission_quality_context(monkeypatch) -> None:
    runner = _SequenceRunner([
        "\n".join([
            "PROJECT_DONE=false",
            "REASON=try the next checker",
            "TASK_KEY=weak",
            "TASK_TITLE=Make checker green",
            "TASK_OBJECTIVE=Change code until the local checker passes.",
            "TASK_ACCEPTANCE_CHECK=pytest tests/test_checker.py",
        ]),
        "\n".join([
            "PROJECT_DONE=false",
            "REASON=ground the checker repair in the user goal",
            "TASK_KEY=grounded",
            "TASK_TITLE=Repair the user-visible parser behavior",
            "TASK_OBJECTIVE=Fix the parser defect and verify the user-visible case.",
            "TASK_HYPOTHESIS=The parser branch drops the required user-visible value.",
            "TASK_GOAL_CONTRIBUTION=Restore the behavior requested by the user.",
            "TASK_EXPECTED_REGRESSIONS=The local checker may remain red during repair.",
            "TASK_DECISION_RULE=Replan if the parser branch is not causal.",
            "TASK_ACCEPTANCE_CHECK=Reproduce the user case, then run pytest tests/test_checker.py.",
        ]),
    ])
    monkeypatch.setattr(
        Planner,
        "_build_planner_prompt",
        staticmethod(lambda **kwargs: "original planner prompt"),
    )

    verdict = Planner(runner).plan_next(
        continuous_objective="restore parser behavior",
        config=PlannerConfig(working_dir="/tmp/project"),
    )

    assert verdict.error == ""
    assert verdict.new_tasks[0].title == "Repair the user-visible parser behavior"
    assert len(runner.calls) == 2
    assert "missing mission-quality fields" in runner.calls[1]["prompt"]


def test_plan_next_repairs_malformed_context_ref_metadata(monkeypatch) -> None:
    runner = _SequenceRunner([
        "\n".join(
            [
                "PROJECT_DONE=false",
                "REASON=summarize the supplied paper",
                "TASK_KEY=paper-summary",
                "TASK_TITLE=Summarize paper",
                "TASK_OBJECTIVE=Read the supplied paper and summarize it.",
                (
                    "TASK_CONTEXT_REFS=research/PIPELINE_STATE.json; "
                    "/tmp/runtime/events.jsonl"
                ),
            ]
        ),
        "\n".join(
            [
                "PROJECT_DONE=false",
                "REASON=summarize the supplied paper",
                "TASK_KEY=paper-summary",
                "TASK_TITLE=Summarize paper",
                "TASK_OBJECTIVE=Read the supplied paper and summarize it.",
                "TASK_HYPOTHESIS=The supplied paper can be summarized from current sources.",
                "TASK_GOAL_CONTRIBUTION=Produce the requested grounded paper summary.",
                "TASK_EXPECTED_REGRESSIONS=None expected; this is read-only synthesis.",
                "TASK_DECISION_RULE=Stop and ask for sources if the referenced paper is absent.",
                (
                    "TASK_CONTEXT_REFS=artifact::research/PIPELINE_STATE.json::"
                    "current stage"
                ),
            ]
        ),
    ])
    monkeypatch.setattr(
        Planner,
        "_build_planner_prompt",
        staticmethod(lambda **kwargs: "original planner prompt"),
    )

    verdict = Planner(runner).plan_next(
        continuous_objective="summarize the paper",
        config=PlannerConfig(working_dir="/tmp/project"),
    )

    assert verdict.error == ""
    assert verdict.new_tasks[0].context_refs == [
        {
            "kind": "artifact",
            "ref": "research/PIPELINE_STATE.json",
            "why": "current stage",
            "content_hash": "",
        }
    ]
    assert runner.calls[1]["run_label"] == "planner.cycle0.repair1"
    assert "TASK_CONTEXT_REFS=kind::project/relative/path::why|..." in runner.calls[1]["prompt"]
    assert "Never put URLs, absolute paths" in runner.calls[1]["prompt"]


def test_plan_next_reports_bounded_failure_after_empty_task_repair_exhaustion(
    monkeypatch,
) -> None:
    runner = _SequenceRunner([
        "PROJECT_DONE=false\nREASON=still not complete",
        "PROJECT_DONE=false\nREASON=still no concrete task",
    ])
    monkeypatch.setattr(
        Planner,
        "_build_planner_prompt",
        staticmethod(lambda **kwargs: "original planner prompt"),
    )

    verdict = Planner(runner).plan_next(
        continuous_objective="fix the verifier",
        config=PlannerConfig(working_dir="/tmp/project"),
    )

    assert verdict.project_done is False
    assert verdict.new_tasks == []
    assert verdict.error.startswith(NO_CONCRETE_TASKS_ERROR)
    assert "repair exhausted after 1 attempt" in verdict.error
    assert len(runner.calls) == 2


def test_open_ended_planner_must_delegate_after_one_increment() -> None:
    runner = _SequenceRunner([
        "PROJECT_DONE=true\nREASON=finished one cache optimization",
        "\n".join([
            "PROJECT_DONE=false",
            "REASON=continue the standing optimization campaign",
            "TASK_KEY=next",
            "TASK_TITLE=Remove duplicate Manager reply rows",
            "TASK_OBJECTIVE=Unify live and persisted Manager message identity.",
            "TASK_HYPOTHESIS=Identity drift creates duplicate conversation rows.",
            "TASK_GOAL_CONTRIBUTION=Keep the standing user conversation coherent.",
            "TASK_EXPECTED_REGRESSIONS=Replay ordering may move while identity is unified.",
            "TASK_DECISION_RULE=Replan if duplicate rows survive stable message ids.",
            "TASK_ACCEPTANCE_CHECK=run the focused TUI stream tests",
        ]),
    ])

    verdict = Planner(runner).plan_next(
        continuous_objective="keep optimizing Argus",
        config=PlannerConfig(working_dir="/tmp/project", open_ended=True),
    )

    assert verdict.project_done is False
    assert [task.title for task in verdict.new_tasks] == [
        "Remove duplicate Manager reply rows"
    ]
    assert OPEN_ENDED_PROJECT_DONE_ERROR in runner.calls[1]["prompt"]


def test_planner_reports_newer_operator_generation_as_superseded() -> None:
    class Runner:
        def run_exec(self, **_kwargs):
            return RunnerResult(
                exit_code=1,
                fatal_error=f"External interrupt: {PLANNER_SUPERSEDED_ERROR}",
            )

    verdict = Planner(Runner()).plan_next(
        continuous_objective="keep optimizing Argus",
        config=PlannerConfig(working_dir="/tmp/project", open_ended=True),
    )

    assert verdict.project_done is False
    assert verdict.error == PLANNER_SUPERSEDED_ERROR
