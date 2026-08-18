from __future__ import annotations

import json
import time
from pathlib import Path

from argus_skill.core.vertical_contract import VerticalLibraryContext
from argus_skill.team import pool, task_board
from argus_skill.verticals.research.idea_portfolio import (
    ensure_idea_portfolio,
    idea_portfolio_completion_issues,
    idea_portfolio_selection,
)
from argus_skill.verticals.research.library_preparation import prepare_skill_libraries
from argus_skill.verticals.research.stages import stage_completion_issues


def _pipeline(root: Path, *, direction: str = "broad") -> None:
    path = root / "research" / "PIPELINE_STATE.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "vertical": "research",
                "current_stage": "research",
                "research_target_level": "publishable",
                "research_direction_mode": direction,
            }
        ),
        encoding="utf-8",
    )


def _route_text(task: dict) -> str:
    headings = (
        "## Mechanism",
        "## Primary sources\nhttps://example.com/paper",
        "## Closest work",
        "## Kill argument",
        "## Faithful probe",
    )
    return f"# {task['task_id']}\n\n" + "\n\nEvidence.\n".join(headings) + "\n"


def _review_payload(task: dict, *, verdict: str) -> dict:
    payload = {
        "schema_version": 1,
        "route_id": task["target"],
        "verdict": verdict,
        "summary": f"{task['target']} independent review",
        "technical_depth": "high",
        "originality": "high",
        "theoretical_grounding": "high",
        "field_significance": "high",
        "local_feasibility": "executable",
        "fatal_concerns": [] if verdict == "qualified" else ["prior art collision"],
        "probe": {},
    }
    if verdict == "qualified":
        payload["probe"] = {
            "premise": "The route's binding mechanism produces a measurable effect.",
            "evaluator_identity": "public benchmark evaluator revision 1",
            "comparison_identity": "strong public baseline revision 1",
            "minimum_signal": "held-out effect with uncertainty excluding the null",
            "stop_rules": "advance on support; reject on faithful contradiction",
        }
    return payload


def _probe_payload(task: dict, *, decision: str) -> dict:
    if decision == "advance":
        execution, failure, status = "completed", "none", "supported"
    elif decision == "reject":
        execution, failure, status = "completed", "empirical", "refuted"
    elif decision == "inconclusive":
        execution, failure, status = "completed", "statistical_power", "inconclusive"
    else:
        execution, failure, status = "blocked", "scope_change", "untested"
    return {
        "schema_version": 1,
        "idea_id": task["target"],
        "premise_version": 1,
        "premise": "The route's binding mechanism produces a measurable effect.",
        "execution_status": execution,
        "failure_class": failure,
        "idea_status": status,
        "evaluator_identity": "public benchmark evaluator revision 1",
        "comparison_identity": "strong public baseline revision 1",
        "summary": f"{decision} result",
        "evidence": "raw/results.jsonl and REPORT.md",
        "decision": decision,
    }


def _write_artifact(
    project_root: Path,
    task: dict,
    *,
    review_verdict: str = "qualified",
    probe_decision: str = "advance",
) -> None:
    output = project_root / task["owns_paths"][0]
    role = task["role"]
    if role == "idea-route":
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(_route_text(task), encoding="utf-8")
        return
    if role == "idea-review":
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(
                _review_payload(task, verdict=review_verdict),
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return
    assert role == "idea-probe"
    output.mkdir(parents=True, exist_ok=True)
    (output / "EVIDENCE.json").write_text(
        json.dumps(
            _probe_payload(task, decision=probe_decision),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _claim_complete(
    project_root: Path,
    root: Path,
    owner: str,
    *,
    expected_role: str,
    review_verdict: str = "qualified",
    probe_decision: str = "advance",
) -> dict:
    task = task_board.claim_top(root, owner, now=time.time())
    assert task is not None
    assert task["role"] == expected_role
    _write_artifact(
        project_root,
        task,
        review_verdict=review_verdict,
        probe_decision=probe_decision,
    )
    shard = root / "shards" / f"{owner}.jsonl"
    shard.parent.mkdir(parents=True, exist_ok=True)
    shard.write_text(
        json.dumps(
            {
                "member_id": owner,
                "task_id": task["task_id"],
                "success": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    task_board.complete(root, task["task_id"], shard=str(shard))
    return task


def _complete_candidate(
    project_root: Path,
    root: Path,
    *,
    prefix: str,
    review_verdict: str = "qualified",
    probe_decision: str = "advance",
) -> tuple[dict, dict, dict]:
    route = _claim_complete(
        project_root,
        root,
        f"{prefix}-route",
        expected_role="idea-route",
    )
    review = _claim_complete(
        project_root,
        root,
        f"{prefix}-review",
        expected_role="idea-review",
        review_verdict=review_verdict,
    )
    probe = _claim_complete(
        project_root,
        root,
        f"{prefix}-probe",
        expected_role="idea-probe",
        probe_decision=probe_decision,
    )
    return route, review, probe


def test_first_qualified_probe_advances_without_all_routes(
    tmp_path: Path,
) -> None:
    _pipeline(tmp_path)
    root = ensure_idea_portfolio(tmp_path, direction="agent reliability")

    assert len(task_board.snapshot(root)) == 36
    assert "no independently reviewed probe" in " ".join(idea_portfolio_completion_issues(tmp_path))

    route, _review, _probe = _complete_candidate(
        tmp_path,
        root,
        prefix="first",
    )

    assert idea_portfolio_completion_issues(tmp_path) == ()
    assert stage_completion_issues("research", tmp_path) == ()
    selection = idea_portfolio_selection(tmp_path)
    assert selection is not None
    assert selection["route_task_id"] == route["task_id"]
    assert (
        json.loads((tmp_path / "research" / "IDEA_SELECTION.json").read_text(encoding="utf-8"))[
            "route_task_id"
        ]
        == route["task_id"]
    )
    assert pool.read(root)["state"] == "draining"
    unfinished_routes = [
        task
        for task in task_board.snapshot(root)
        if task["role"] == "idea-route" and task["state"] != "done"
    ]
    assert len(unfinished_routes) == 11
    ensure_idea_portfolio(tmp_path, direction="agent reliability")
    assert pool.read(root)["state"] == "draining"


def test_rejected_route_does_not_block_next_candidate(tmp_path: Path) -> None:
    _pipeline(tmp_path)
    root = ensure_idea_portfolio(tmp_path, direction="agent reliability")

    _complete_candidate(
        tmp_path,
        root,
        prefix="rejected",
        review_verdict="rejected",
        probe_decision="skipped",
    )
    assert idea_portfolio_selection(tmp_path) is None

    route, _review, _probe = _complete_candidate(
        tmp_path,
        root,
        prefix="winner",
    )

    selection = idea_portfolio_selection(tmp_path)
    assert selection is not None
    assert selection["route_task_id"] == route["task_id"]
    assert idea_portfolio_completion_issues(tmp_path) == ()


def test_greedy_selection_keeps_earliest_advancing_probe(tmp_path: Path) -> None:
    _pipeline(tmp_path)
    root = ensure_idea_portfolio(tmp_path, direction="agent reliability")

    first, _review, _probe = _complete_candidate(
        tmp_path,
        root,
        prefix="first",
    )
    _complete_candidate(
        tmp_path,
        root,
        prefix="later",
    )

    selection = idea_portfolio_selection(tmp_path)
    assert selection is not None
    assert selection["route_task_id"] == first["task_id"]


def test_invalid_selected_artifact_blocks_greedy_provenance(
    tmp_path: Path,
) -> None:
    _pipeline(tmp_path)
    root = ensure_idea_portfolio(tmp_path, direction="agent reliability")
    route, _review, _probe = _complete_candidate(
        tmp_path,
        root,
        prefix="candidate",
    )
    route_path = tmp_path / route["owns_paths"][0]
    route_path.write_text("Evidence.\n", encoding="utf-8")

    assert "greedy selection lacks valid" in " ".join(idea_portfolio_completion_issues(tmp_path))


def test_locked_hypothesis_does_not_require_portfolio(tmp_path: Path) -> None:
    _pipeline(tmp_path, direction="locked")

    assert idea_portfolio_completion_issues(tmp_path) == ()


def test_new_direction_gets_a_new_pipeline_and_clears_selection(
    tmp_path: Path,
) -> None:
    _pipeline(tmp_path)
    first = ensure_idea_portfolio(tmp_path, direction="agent reliability")
    _complete_candidate(tmp_path, first, prefix="first")
    assert idea_portfolio_completion_issues(tmp_path) == ()
    assert (tmp_path / "research" / "IDEA_SELECTION.json").is_file()

    second = ensure_idea_portfolio(tmp_path, direction="agent memory")

    assert second != first
    assert first.is_dir()
    assert not (tmp_path / "research" / "IDEA_SELECTION.json").exists()
    assert "no independently reviewed probe" in " ".join(idea_portfolio_completion_issues(tmp_path))


def test_research_library_hook_forms_streaming_pipeline(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _pipeline(tmp_path)
    monkeypatch.setenv("ARGUS_SKILL_VENUE_RESEARCH", "0")
    monkeypatch.setenv("ARGUS_SKILL_IDEA_SEARCH", "0")
    events: list[dict] = []
    required: list[str] = []

    prepare_skill_libraries(
        VerticalLibraryContext(
            workdir=tmp_path,
            stage="research",
            objective="discover a thesis",
            direction="agent reliability",
            workflow_mode="staged",
            paper_mission=True,
            runner=None,
            model=None,
            emit=events.append,
            required_skill_paths=required,
        )
    )

    assert required == [
        "engineer/idea-discovery.md",
        "engineer/idea-creator.md",
        "engineer/agent-team-lead.md",
    ]
    assert events[0]["type"] == "idea.portfolio.formed"
    assert events[0]["policy"] == "greedy_first_qualified"
    assert events[0]["task_count"] == 36
    assert len(task_board.snapshot(Path(events[0]["team_root"]))) == 36
