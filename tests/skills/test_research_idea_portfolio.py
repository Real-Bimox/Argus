from __future__ import annotations

import json
import time
from pathlib import Path

from argus_skill.core.vertical_contract import VerticalLibraryContext
from argus_skill.team import pool, task_board
from argus_skill.verticals.research.idea_portfolio import (
    ensure_idea_portfolio,
    idea_portfolio_completion_issues,
    portfolio_tasks,
)
from argus_skill.verticals.research.library_preparation import prepare_skill_libraries
from argus_skill.verticals.research.stages import stage_completion_issues


def _pipeline(root: Path, *, direction: str = "broad") -> None:
    path = root / "research" / "PIPELINE_STATE.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({
            "vertical": "research",
            "current_stage": "research",
            "research_target_level": "publishable",
            "research_direction_mode": direction,
        }),
        encoding="utf-8",
    )


def _artifact_text(task: dict) -> str:
    headings = {
        "idea-route": (
            "## Mechanism",
            "## Primary sources\nhttps://example.com/paper",
            "## Closest work",
            "## Kill argument",
            "## Faithful probe",
        ),
        "selection-proponent": (
            "## Technical depth",
            "## Originality",
            "## Grounding",
            "## Significance",
            "## Falsifier",
            "## Feasibility",
        ),
        "selection-assassin": (
            "## Prior-art reduction",
            "## Technical shallowness",
            "## Confounds",
            "## Fatal probes",
        ),
        "selection-meta-review": (
            "## Originality verdict",
            "## Killed ideas",
            "## Surviving thesis",
            "## Unresolved risks",
            "## First faithful probe",
        ),
    }[task["role"]]
    return f"# {task['task_id']}\n\n" + "\n\nEvidence.\n".join(headings) + "\n"


def _complete_portfolio(project_root: Path, root: Path) -> None:
    for index in range(len(portfolio_tasks())):
        owner = f"worker-{index + 1:02d}"
        task = task_board.claim_top(root, owner, now=time.time())
        assert task is not None
        output = project_root / task["owns_paths"][0]
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(_artifact_text(task), encoding="utf-8")
        shard = root / "shards" / f"{owner}.jsonl"
        shard.parent.mkdir(parents=True, exist_ok=True)
        shard.write_text(
            json.dumps({
                "member_id": owner,
                "task_id": task["task_id"],
                "success": True,
            }) + "\n",
            encoding="utf-8",
        )
        task_board.complete(root, task["task_id"], shard=str(shard))


def test_broad_publishable_research_forms_and_validates_real_team(
    tmp_path: Path,
) -> None:
    _pipeline(tmp_path)

    root = ensure_idea_portfolio(tmp_path, direction="agent reliability")

    assert len(task_board.snapshot(root)) == 15
    assert "incomplete routes" in " ".join(
        idea_portfolio_completion_issues(tmp_path)
    )

    _complete_portfolio(tmp_path, root)
    signal = tmp_path / "research" / "SIGNAL_DERISK.json"
    signal.write_text("{}\n", encoding="utf-8")

    assert idea_portfolio_completion_issues(tmp_path) == ()
    assert stage_completion_issues("research", tmp_path) == ()
    route = next(
        task
        for task in task_board.snapshot(root)
        if task["role"] == "idea-route"
    )
    route_path = tmp_path / route["owns_paths"][0]
    route_text = route_path.read_text(encoding="utf-8")
    route_path.write_text("Evidence.\n", encoding="utf-8")
    assert "lacks route or debate artifacts" in " ".join(
        idea_portfolio_completion_issues(tmp_path)
    )
    route_path.write_text(route_text, encoding="utf-8")
    pool.update(root, state="dissolved")
    ensure_idea_portfolio(tmp_path, direction="agent reliability")
    assert pool.read(root)["state"] == "dissolved"

    meta_path = next((root / "tasks").glob("*-selection-meta-review.json"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    original_claim = meta["claim_seq"]
    meta["claim_seq"] = 0
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    assert "completion order is invalid" in " ".join(
        idea_portfolio_completion_issues(tmp_path)
    )

    meta["claim_seq"] = original_claim
    meta["role"] = "selection-proponent"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    assert "not canonical" in " ".join(
        idea_portfolio_completion_issues(tmp_path)
    )


def test_locked_hypothesis_does_not_require_portfolio(tmp_path: Path) -> None:
    _pipeline(tmp_path, direction="locked")

    assert idea_portfolio_completion_issues(tmp_path) == ()


def test_new_direction_gets_a_new_portfolio(tmp_path: Path) -> None:
    _pipeline(tmp_path)
    first = ensure_idea_portfolio(tmp_path, direction="agent reliability")
    _complete_portfolio(tmp_path, first)

    second = ensure_idea_portfolio(tmp_path, direction="agent memory")

    assert second != first
    assert first.is_dir()
    assert "incomplete routes" in " ".join(
        idea_portfolio_completion_issues(tmp_path)
    )


def test_research_library_hook_forms_team_and_requires_both_skills(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _pipeline(tmp_path)
    monkeypatch.setenv("ARGUS_SKILL_VENUE_RESEARCH", "0")
    monkeypatch.setenv("ARGUS_SKILL_IDEA_SEARCH", "0")
    events: list[dict] = []
    required: list[str] = []

    prepare_skill_libraries(VerticalLibraryContext(
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
    ))

    assert required == [
        "engineer/idea-discovery.md",
        "engineer/agent-team-lead.md",
    ]
    assert events[0]["type"] == "idea.portfolio.formed"
    assert len(task_board.snapshot(Path(events[0]["team_root"]))) == 15
