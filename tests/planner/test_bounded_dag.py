from __future__ import annotations

from argus_skill.core.models import RunnerResult
from argus_skill.planner.bounded_dag import plan_bounded_dag


class _Runner:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls = []

    def run_exec(self, **kwargs):
        self.calls.append(kwargs)
        lines = [f"PLAN_REASON={self.payload['reason']}"]
        for task in self.payload["tasks"]:
            lines.extend([
                f"TASK_KEY={task['key']}",
                f"TASK_DEPS={','.join(task['deps'])}",
                f"TASK_TITLE={task['title']}",
                f"TASK_OBJECTIVE={task['objective']}",
                f"TASK_HYPOTHESIS={task.get('hypothesis', 'This task tests its stated mechanism.')}",
                f"TASK_GOAL_CONTRIBUTION={task.get('goal_contribution', 'This task advances the requested deliverable.')}",
                f"TASK_EXPECTED_REGRESSIONS={task.get('expected_regressions', 'None expected beyond local work in progress.')}",
                f"TASK_DECISION_RULE={task.get('decision_rule', 'Replan if the mechanism cannot satisfy the user goal.')}",
                f"TASK_SCOPE={task.get('scope', 'bounded')}",
                f"TASK_STAGE_CLOSING={task.get('stage_closing', 'false')}",
                "TASK_REQUIRE_INDEPENDENT_REVIEW="
                f"{task.get('require_independent_review', 'false')}",
                "TASK_SKIP_STAGE_TRANSITION="
                f"{task.get('skip_stage_transition', 'false')}",
                "TASK_OPERATOR_APPROVAL_REQUIRED="
                f"{task.get('operator_approval_required', 'false')}",
                "TASK_ALLOW_SKILL_CHANGES="
                f"{task.get('allow_skill_changes', 'false')}",
            ])
            for key in (
                "acceptance_check",
                "non_goals",
                "context_refs",
            ):
                if key in task:
                    field = f"TASK_{key.upper()}"
                    lines.append(f"{field}={task[key]}")
        return RunnerResult(
            exit_code=0,
            agent_messages=["\n".join(lines)],
            input_tokens=100,
            output_tokens=20,
        )


class _RawRunner:
    def __init__(self, text: str) -> None:
        self.text = text

    def run_exec(self, **_kwargs):
        return RunnerResult(exit_code=0, agent_messages=[self.text])


class _SequenceRunner:
    def __init__(self, *responses: str) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []

    def run_exec(self, **kwargs):
        self.calls.append(kwargs)
        return RunnerResult(
            exit_code=0,
            agent_messages=[self.responses.pop(0)],
            input_tokens=10,
            output_tokens=2,
        )


def test_bounded_planner_parses_real_fanout_fanin_dag(tmp_path) -> None:
    runner = _Runner(
        {
            "reason": "separate implementation from independent verification",
            "tasks": [
                {
                    "key": "a",
                    "deps": [],
                    "title": "Implement parser",
                    "objective": "write src/parser.py; run pytest tests/test_parser.py",
                },
                {
                    "key": "b",
                    "deps": [],
                    "title": "Build fixtures",
                    "objective": "write tests/fixtures.json; validate JSON parsing",
                },
                {
                    "key": "c",
                    "deps": ["a", "b"],
                    "title": "Integrate CLI",
                    "objective": "read src/parser.py and tests/fixtures.json; write src/cli.py; run pytest -q",
                    "acceptance_check": "pytest -q exits zero",
                    "non_goals": "do not publish|do not edit pipeline state",
                    "context_refs": (
                        "artifact::research/chem_playground/x/QUESTION.md::question|"
                        "artifact::research/chem_playground/x/RESULT.md::result"
                    ),
                    "scope": "bounded",
                    "stage_closing": "false",
                    "require_independent_review": "true",
                    "skip_stage_transition": "true",
                },
            ],
        }
    )

    plan = plan_bounded_dag(runner, "build the tool", workdir=tmp_path)

    assert not plan.error
    assert [task.key for task in plan.tasks] == ["a", "b", "c"]
    assert plan.tasks[2].deps == ("a", "b")
    assert plan.tasks[2].acceptance_check == "pytest -q exits zero"
    assert plan.tasks[2].non_goals == ("do not publish", "do not edit pipeline state")
    assert [ref["ref"] for ref in plan.tasks[2].context_refs] == [
        "research/chem_playground/x/QUESTION.md",
        "research/chem_playground/x/RESULT.md",
    ]
    assert plan.tasks[2].stage_closing is False
    assert plan.tasks[2].require_independent_review is True
    assert plan.tasks[2].skip_stage_transition is True
    call = runner.calls[0]
    assert call["run_label"] == "planner.bounded_dag"
    assert call["options"].working_dir == str(tmp_path.resolve())
    assert not hasattr(call["options"], "output_schema_path")
    assert "one fresh Engineer session" in call["prompt"]
    assert "Do not initialize Git" in call["prompt"]
    assert "Never create standalone inspect/audit/planning" in call["prompt"]
    assert "The Engineer decides" in call["prompt"]
    assert "framework-required gates may still force review" in call["prompt"]
    assert "Return plain key-value text, not JSON" in call["prompt"]
    assert "TASK_CONTEXT_REFS" in call["prompt"]
    assert "TASK_STAGE_CLOSING" in call["prompt"]
    assert "TASK_REQUIRE_INDEPENDENT_REVIEW" in call["prompt"]
    assert "low-risk direct repair" in call["prompt"]
    assert "security, authentication, data loss, concurrency" in call["prompt"]
    assert "TASK_SKIP_STAGE_TRANSITION" in call["prompt"]
    assert "Every node pays for a full Engineer + Reviewer cycle" not in call["prompt"]


def test_bounded_planner_rejects_future_operator_gated_nodes(tmp_path) -> None:
    runner = _Runner(
        {
            "reason": "stop before the operator approval boundary",
            "tasks": [
                {
                    "key": "statement-lock",
                    "deps": [],
                    "title": "Lock statement",
                    "objective": "Lock the statement after the operator approves it.",
                    "operator_approval_required": "true",
                },
            ],
        }
    )

    plan = plan_bounded_dag(runner, "prepare work up to operator approval", workdir=tmp_path)

    assert plan.tasks == ()
    assert "operator approval" in plan.error


def test_bounded_planner_rejects_cycle(tmp_path) -> None:
    runner = _Runner(
        {
            "reason": "bad graph",
            "tasks": [
                {"key": "a", "deps": ["b"], "title": "A", "objective": "do A"},
                {"key": "b", "deps": ["a"], "title": "B", "objective": "do B"},
            ],
        }
    )

    plan = plan_bounded_dag(runner, "x", workdir=tmp_path)

    assert "cycle" in plan.error


def test_bounded_planner_rejects_omitted_review_control_fields(tmp_path) -> None:
    plan = plan_bounded_dag(
        _RawRunner(
            "PLAN_REASON=truncated footer\n"
            "TASK_KEY=a\n"
            "TASK_DEPS=\n"
            "TASK_TITLE=A\n"
            "TASK_OBJECTIVE=do A"
        ),
        "x",
        workdir=tmp_path,
    )

    assert "missing required control fields" in plan.error


def test_bounded_planner_rejects_any_malformed_context_ref(tmp_path) -> None:
    runner = _Runner(
        {
            "reason": "malformed metadata",
            "tasks": [{
                "key": "a",
                "deps": [],
                "title": "A",
                "objective": "do A",
                "context_refs": (
                    "artifact::research/valid.md::valid|malformed-entry"
                ),
            }],
        }
    )

    plan = plan_bounded_dag(runner, "x", workdir=tmp_path)

    assert "TASK_CONTEXT_REFS entries must use" in plan.error


def test_bounded_planner_repairs_invalid_absolute_context_ref_once(tmp_path) -> None:
    invalid = (
        "PLAN_REASON=repair one test\n"
        "TASK_KEY=fix\n"
        "TASK_DEPS=\n"
        "TASK_TITLE=Fix one test\n"
        "TASK_OBJECTIVE=locate and repair the failing test\n"
        "TASK_HYPOTHESIS=The named test exposes the remaining defect.\n"
        "TASK_GOAL_CONTRIBUTION=Restore the requested behavior.\n"
        "TASK_EXPECTED_REGRESSIONS=The focused test may remain red during repair.\n"
        "TASK_DECISION_RULE=Replan if the failure is outside this path.\n"
        f"TASK_CONTEXT_REFS=workspace::{tmp_path}::current workspace\n"
        "TASK_SCOPE=bounded\n"
        "TASK_STAGE_CLOSING=false\n"
        "TASK_REQUIRE_INDEPENDENT_REVIEW=false\n"
        "TASK_SKIP_STAGE_TRANSITION=false\n"
        "TASK_OPERATOR_APPROVAL_REQUIRED=false\n"
        "TASK_ALLOW_SKILL_CHANGES=false\n"
    )
    corrected = invalid.replace(str(tmp_path), "./")
    runner = _SequenceRunner(invalid, corrected)

    plan = plan_bounded_dag(runner, "fix one test", workdir=tmp_path)

    assert not plan.error
    assert len(plan.tasks) == 1
    assert plan.tasks[0].context_refs[0]["ref"] == "./"
    assert [call["run_label"] for call in runner.calls] == [
        "planner.bounded_dag",
        "planner.bounded_dag.repair",
    ]
    assert "project-relative file paths" in runner.calls[1]["prompt"]


def test_bounded_planner_parses_nested_execution_workdir(tmp_path) -> None:
    payload = (
        "PLAN_REASON=work in cloned repository\n"
        "TASK_KEY=fix\n"
        "TASK_DEPS=\n"
        "TASK_TITLE=Fix target repository\n"
        "TASK_OBJECTIVE=repair the target code\n"
        "TASK_HYPOTHESIS=The defect is in the nested repository.\n"
        "TASK_GOAL_CONTRIBUTION=Fix the operator's requested project.\n"
        "TASK_EXPECTED_REGRESSIONS=The focused test may remain red.\n"
        "TASK_DECISION_RULE=Replan if the defect is outside the nested repo.\n"
        "TASK_WORKDIR=target-repo\n"
        "TASK_SCOPE=bounded\n"
        "TASK_STAGE_CLOSING=false\n"
        "TASK_REQUIRE_INDEPENDENT_REVIEW=false\n"
        "TASK_SKIP_STAGE_TRANSITION=false\n"
        "TASK_OPERATOR_APPROVAL_REQUIRED=false\n"
        "TASK_ALLOW_SKILL_CHANGES=false\n"
    )
    runner = _SequenceRunner(payload)

    plan = plan_bounded_dag(runner, "fix target", workdir=tmp_path)

    assert not plan.error
    assert plan.tasks[0].execution_workdir == "target-repo"


def test_bounded_planner_repairs_invalid_stage_skip_contract_once(tmp_path) -> None:
    invalid = (
        "PLAN_REASON=draft a paper\n"
        "TASK_KEY=outline\n"
        "TASK_DEPS=\n"
        "TASK_TITLE=Draft outline\n"
        "TASK_OBJECTIVE=write paper/outline.md\n"
        "TASK_HYPOTHESIS=A grounded outline is the next useful paper increment.\n"
        "TASK_GOAL_CONTRIBUTION=Create the structure needed for the requested paper.\n"
        "TASK_EXPECTED_REGRESSIONS=Section order may change during drafting.\n"
        "TASK_DECISION_RULE=Replan if evidence requires a different paper structure.\n"
        "TASK_SCOPE=bounded\n"
        "TASK_STAGE_CLOSING=false\n"
        "TASK_REQUIRE_INDEPENDENT_REVIEW=false\n"
        "TASK_SKIP_STAGE_TRANSITION=true\n"
        "TASK_OPERATOR_APPROVAL_REQUIRED=false\n"
        "TASK_ALLOW_SKILL_CHANGES=false\n"
    )
    corrected = invalid.replace(
        "TASK_SKIP_STAGE_TRANSITION=true",
        "TASK_SKIP_STAGE_TRANSITION=false",
    )
    runner = _SequenceRunner(invalid, corrected)

    plan = plan_bounded_dag(
        runner,
        "帮我写一篇AI方面的论文，我要投到ICLR上面",
        workdir=tmp_path,
    )

    assert not plan.error
    assert len(plan.tasks) == 1
    assert plan.tasks[0].skip_stage_transition is False
    assert plan.input_tokens == 20
    assert plan.output_tokens == 4
    assert [call["run_label"] for call in runner.calls] == [
        "planner.bounded_dag",
        "planner.bounded_dag.repair",
    ]
    assert "VALIDATION_ERROR=ValueError: skip_stage_transition requires" in (
        runner.calls[1]["prompt"]
    )
    assert "Return the COMPLETE corrected plan" in runner.calls[1]["prompt"]


def test_bounded_planner_rejects_stage_skip_without_review_only_contract(
    tmp_path,
) -> None:
    runner = _Runner(
        {
            "reason": "unsafe metadata",
            "tasks": [{
                "key": "a",
                "deps": [],
                "title": "A",
                "objective": "do A",
                "skip_stage_transition": "true",
            }],
        }
    )

    plan = plan_bounded_dag(runner, "x", workdir=tmp_path)

    assert "requires independent review" in plan.error


def test_bounded_planner_does_not_cap_node_count(tmp_path) -> None:
    runner = _Runner(
        {
            "reason": "too many overlapping stages",
            "tasks": [
                {"key": str(index), "deps": [], "title": f"Task {index}", "objective": "work"}
                for index in range(12)
            ],
        }
    )

    plan = plan_bounded_dag(runner, "one cohesive change", workdir=tmp_path)

    assert not plan.error
    assert len(plan.tasks) == 12
