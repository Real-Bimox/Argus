"""Planner must delegate implementation and keep standing campaigns moving."""

from __future__ import annotations

import json
import time
from pathlib import Path

from argus_skill.core.models import RunnerResult
from argus_skill.daemon.state import write_continuous_config
from argus_skill.life.event_log import JsonlEventSink
from argus_skill.life.memory import BacklogItem, LifeMemory
from argus_skill.life.supervisor import LifeBudget, LifeSupervisor, LifeSupervisorConfig
from argus_skill.planner import PlannerConfig
from argus_skill.skills.vertical_select import persist_vertical


class _MissionRunner:
    pass


class _PlannerBackend:
    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.calls: list[dict] = []

    def run_exec(self, **kwargs):  # noqa: ANN003
        self.calls.append(kwargs)
        return RunnerResult(exit_code=0, agent_messages=[self.replies.pop(0)])


def _supervisor(project: Path, life: Path, planner: _PlannerBackend) -> LifeSupervisor:
    memory = LifeMemory.open(life)
    supervisor = LifeSupervisor(
        memory=memory,
        runner=_MissionRunner(),
        sink=JsonlEventSink(None, life_dir=memory.root, verbosity="full"),
        config=LifeSupervisorConfig(
            budget=LifeBudget(),
            continuous=True,
            continuous_objective="keep optimizing Argus",
            open_ended=True,
            project_worktree=project,
            artifact_root=project,
        ),
        planner_runner=planner,
    )
    persist_vertical(project, "software", workflow_mode="direct")
    supervisor._vertical_resolved = True
    # Isolate this flow test from host continuous.json state. The Planner class
    # still receives and forwards this provider in production.
    supervisor._planner_config = lambda: PlannerConfig(  # type: ignore[method-assign]
        working_dir=str(project),
        open_ended=True,
    )
    return supervisor


def test_planner_delegates_to_engineer_and_continues_after_one_increment(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    planner = _PlannerBackend([
        "\n".join([
            "PROJECT_DONE=false",
            "REASON=delegate the first bounded optimization",
            "TASK_KEY=first",
            "TASK_TITLE=Remove redundant snapshot prewarm",
            "TASK_OBJECTIVE=Change the prewarm scheduling and add a regression test.",
            "TASK_HYPOTHESIS=Duplicate prewarm work is the measured bottleneck.",
            "TASK_GOAL_CONTRIBUTION=Remove wasted startup work from the user path.",
            "TASK_EXPECTED_REGRESSIONS=Startup ordering may change during the repair.",
            "TASK_DECISION_RULE=Revise if profiling shows prewarm is not on the critical path.",
            "TASK_ACCEPTANCE_CHECK=pytest tests/webapi/test_index_cache.py",
        ]),
        "PROJECT_DONE=true\nREASON=finished one optimization",
        "\n".join([
            "PROJECT_DONE=false",
            "REASON=continue the standing campaign with a distinct issue",
            "TASK_KEY=second",
            "TASK_TITLE=Deduplicate Manager reply rows",
            "TASK_OBJECTIVE=Use one message identity for live and persisted replies.",
            "TASK_HYPOTHESIS=Identity drift causes duplicate Manager reply rows.",
            "TASK_GOAL_CONTRIBUTION=Make the user conversation readable and stable.",
            "TASK_EXPECTED_REGRESSIONS=Replay ordering may shift while identities converge.",
            "TASK_DECISION_RULE=Replace this route if duplicates persist with stable ids.",
            "TASK_ACCEPTANCE_CHECK=npm test -- stream.test.ts",
        ]),
    ])
    supervisor = _supervisor(project, tmp_path / "life", planner)

    assert supervisor._plan_next_work() is True
    first = supervisor.memory.backlog.pending()
    assert [item.title for item in first] == ["Remove redundant snapshot prewarm"]
    supervisor.memory.backlog.update(first[0].id, status="done")

    assert supervisor._plan_next_work() is True
    pending = supervisor.memory.backlog.pending()
    assert [item.title for item in pending] == ["Deduplicate Manager reply rows"]

    assert len(planner.calls) == 3
    assert all(call["options"].sandbox_mode == "read-only" for call in planner.calls)
    assert all(call["options"].dangerous_yolo is False for call in planner.calls)
    assert not list(project.glob("**/*.py")), "Planner must not create implementation files"


def _kernel_supervisor(
    project: Path,
    life: Path,
    planner: _PlannerBackend,
) -> LifeSupervisor:
    memory = LifeMemory.open(life)
    supervisor = LifeSupervisor(
        memory=memory,
        runner=_MissionRunner(),
        sink=JsonlEventSink(None, life_dir=memory.root, verbosity="full"),
        config=LifeSupervisorConfig(
            budget=LifeBudget(),
            continuous=True,
            continuous_objective="run the kernel algorithm campaign",
            open_ended=True,
            project_worktree=project,
            artifact_root=life,
        ),
        planner_runner=planner,
    )
    persist_vertical(life, "kernel_engineering", workflow_mode="staged")
    supervisor._vertical_resolved = True
    supervisor._planner_config = lambda: PlannerConfig(  # type: ignore[method-assign]
        working_dir=str(project),
        add_dirs=[str(life)],
        open_ended=True,
    )
    return supervisor


def test_missing_kernel_scope_bundle_is_delegated_without_planner_call(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    life = tmp_path / "life"
    planner = _PlannerBackend([])
    supervisor = _kernel_supervisor(project, life, planner)
    from argus_skill.manager.directive import set_active_manager_directive

    set_active_manager_directive(
        life,
        "Keep the existing PR and reference worktree read-only.",
    )

    assert supervisor._plan_next_work() is True

    assert planner.calls == []
    pending = supervisor.memory.backlog.pending()
    assert [item.title for item in pending] == [
        "Complete the kernel_engineering scope deliverable"
    ]
    item = pending[0]
    assert "stage:scope" in item.tags
    assert "stage_closing" in item.tags
    assert "review:required" in item.tags
    assert "research/KERNEL_SCOPE.md" in item.objective
    assert "research/PROJECT_NATIVE_SETUP.md" in item.objective
    assert "research/frontier/scope.json" in item.objective
    assert "Online frontier snapshot validates" in item.acceptance_check


def test_task_policy_uses_isolated_stage_and_execution_evidence_root(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    research = project / "research"
    (research / "frontier").mkdir(parents=True)
    (research / "KERNEL_SCOPE.md").write_text("# scope\n", encoding="utf-8")
    (research / "PROJECT_NATIVE_SETUP.md").write_text("# setup\n", encoding="utf-8")
    (research / "frontier" / "scope.json").write_text("{}\n", encoding="utf-8")
    # Deliberately stale workspace state must not override Manager-owned state.
    (research / "PIPELINE_STATE.json").write_text(
        json.dumps({"vertical": "kernel_engineering", "current_stage": "optimize"}),
        encoding="utf-8",
    )
    attempt = project / "attempts" / "winner"
    attempt.mkdir(parents=True)
    (attempt / "OUTCOME.json").write_text(
        json.dumps({
            "attempt_id": "winner",
            "execution_status": "completed",
            "failure_class": "none",
            "idea_status": "supported",
        }),
        encoding="utf-8",
    )
    (research / "PERFORMANCE_RESULT.json").write_text(
        json.dumps({"passed": True}),
        encoding="utf-8",
    )
    planner = _PlannerBackend([
        "\n".join([
            "PROJECT_DONE=false",
            "REASON=finish the authoritative scope stage",
            "TASK_KEY=scope-repair",
            "TASK_TITLE=Reconcile the scope contract",
            "TASK_OBJECTIVE=Repair the current scope evidence only.",
            "TASK_HYPOTHESIS=The scope contract has one remaining inconsistency.",
            "TASK_GOAL_CONTRIBUTION=Make the campaign ready for discovery.",
            "TASK_EXPECTED_REGRESSIONS=None; implementation is unchanged.",
            "TASK_DECISION_RULE=Stop if the scope is already internally consistent.",
            "TASK_ACCEPTANCE_CHECK=scope artifacts agree",
        ])
    ])
    supervisor = _kernel_supervisor(project, tmp_path / "life", planner)

    assert supervisor._plan_next_work() is True

    assert len(planner.calls) == 1
    assert [item.title for item in supervisor.memory.backlog.pending()] == [
        "Reconcile the scope contract"
    ]


def test_planner_receives_host_current_reality_without_rediscovery(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    planner = _PlannerBackend([])
    supervisor = _supervisor(project, tmp_path / "life", planner)
    checkpoint = project / "CHECKPOINT.md"
    checkpoint.write_text(
        "# Open Questions / Blockers\n\n- verify the production artifact\n",
        encoding="utf-8",
    )
    supervisor.memory.backlog.add(BacklogItem.new(
        title="pending repair",
        objective="repair the active path",
    ))

    note = supervisor._planner_current_reality_note()

    assert note.count("## Host current-reality digest") == 1
    assert "- vertical: software" in note
    assert "- current_stage:" in note
    assert '"pending": 1' in note
    assert "git_changed_paths" in note
    assert "verify the production artifact" in note
    assert "Do not spend tools rereading those sources" in note


def test_0d3_later_no_gap_evidence_replaces_skip_zero_plan(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    planner = _PlannerBackend([
        "\n".join([
            "PROJECT_DONE=false",
            "REASON=replace the refuted candidate with the better validator route",
            "TASK_KEY=no-gap",
            "TASK_TITLE=Adopt the no-gap validator",
            "TASK_OBJECTIVE=Implement and verify the no-gap validator alternative.",
            "TASK_HYPOTHESIS=The no-gap validator meets the user goal without skip-zero.",
            "TASK_GOAL_CONTRIBUTION=Remove an unnecessary candidate constraint.",
            "TASK_EXPECTED_REGRESSIONS=The old skip-zero checker may become obsolete.",
            "TASK_DECISION_RULE=Abandon if no-gap fails the original user-level property.",
            "TASK_ACCEPTANCE_CHECK=Verify the original user property with no-gap enabled.",
        ])
    ])
    supervisor = _supervisor(project, tmp_path / "life", planner)
    trigger = supervisor.memory.backlog.add(BacklogItem.new(
        title="Generate skip-zero candidate",
        objective="Generate and validate the preselected skip-zero candidate.",
        item_id="skip-zero",
        plan_id="plan-old",
        plan_version=1,
        node_key="skip-zero",
    ))
    supervisor.memory.backlog.add(BacklogItem.new(
        title="Continue skip-zero rollout",
        objective="Roll out the skip-zero candidate.",
        item_id="skip-zero-rollout",
        plan_id="plan-old",
        plan_version=1,
        node_key="rollout",
        deps=[trigger.id],
    ))
    outcome = {
        "item_id": trigger.id,
        "status": "replan_requested",
        "review_status": "done",
        "review_reason": "The no-gap validator dominates the preselected candidate.",
        "expected_plan_id": "plan-old",
        "expected_plan_version": 1,
        "planner_report": {
            "plan_signal": "reconsider",
            "challenge": "The preselected skip-zero candidate is unnecessary.",
            "alternative": "Use the no-gap validator alternative.",
            "authority_impact": "technical",
        },
        "plan_challenge": {
            "manager_action": "replace",
            "manager_reason": "Later evidence supports a concrete alternative.",
            "challenge": "The preselected skip-zero candidate is unnecessary.",
            "alternative": "Use the no-gap validator alternative.",
            "authority_impact": "technical",
            "source": "manager_authority_policy",
            "raised_at": time.time() - 2,
        },
    }

    assert supervisor._adjudicate_mission_challenge(outcome) == "replace"
    assert supervisor._plan_next_work(revision_request=outcome) is True

    rows = {item.id: item for item in supervisor.memory.backlog.all()}
    assert rows["skip-zero"].status == "superseded"
    assert rows["skip-zero-rollout"].status == "superseded"
    replacement = next(item for item in rows.values() if item.status == "pending")
    assert replacement.title == "Adopt the no-gap validator"
    assert replacement.plan_hypothesis.startswith("The no-gap validator")
    prompt = planner.calls[0]["prompt"]
    assert "challenged_assumption: The preselected skip-zero candidate" in prompt
    assert "proposed_alternative: Use the no-gap validator" in prompt
    events = [
        json.loads(line)
        for line in (supervisor.memory.root / "events.jsonl").read_text().splitlines()
    ]
    decided = [
        event for event in events
        if event.get("type") == "life.manager.plan_challenge.decided"
    ]
    committed = [
        event for event in events
        if event.get("type") == "life.plan.revision.committed"
    ]
    assert decided and decided[-1]["manager_action"] == "replace"
    assert decided[-1]["revision_latency_seconds"] >= 1
    assert committed and committed[-1]["alternative"].startswith("Use the no-gap")


def test_new_continuous_generation_interrupts_obsolete_planner(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    life = tmp_path / "life"
    memory = LifeMemory.open(life)
    write_continuous_config(life, enabled=True, objective="old objective")
    supervisor = LifeSupervisor(
        memory=memory,
        runner=_MissionRunner(),
        sink=JsonlEventSink(None, life_dir=memory.root, verbosity="full"),
        config=LifeSupervisorConfig(
            continuous=True,
            continuous_objective="old objective",
            open_ended=True,
            project_worktree=project,
            artifact_root=project,
        ),
        planner_runner=object(),
    )

    config = supervisor._planner_config()
    provider = config.external_interrupt_reason_provider
    assert provider() is None
    assert config.add_dirs == [str(life)]

    write_continuous_config(life, enabled=True, objective="new operator objective")

    assert provider() == "planner superseded by newer continuous generation"
