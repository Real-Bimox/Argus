"""Math objective mode and the proof-gap graph.

Two projects run through this vertical with opposite completion rules — prove
this conjecture, versus find what is true near here — and the observed failure
was measuring one against the other's bar.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from argus_skill.verticals.math.objective_mode import (
    MATH_OBJECTIVE_MODES,
    normalize_mode,
    resolve_objective,
    set_objective,
)
from argus_skill.verticals.math.proof_graph import (
    ProofGraph,
    graph_required_for,
    load_graph,
    template,
)

# -- the operator picks; nothing is assumed ---------------------------------

def test_an_unset_mode_is_reported_not_guessed(tmp_path: Path) -> None:
    objective = resolve_objective(tmp_path)

    # Targeted and exploratory have opposite completion bars; picking either
    # silently is wrong in one direction.
    assert objective.mode is None
    assert objective.resolved is False
    assert "different completion bars" in objective.note


@pytest.mark.parametrize("mode", MATH_OBJECTIVE_MODES)
def test_modes_normalize(mode) -> None:
    assert normalize_mode(f" {mode.upper()} ") == mode


def test_unknown_modes_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown math objective mode"):
        set_objective(tmp_path, mode="whatever")


def test_targeted_mode_requires_the_goal(tmp_path: Path) -> None:
    # Without a goal there is nothing to measure the gap against, and the
    # project drifts into whichever subproblem is most tractable.
    with pytest.raises(ValueError, match="requires the goal"):
        set_objective(tmp_path, mode="targeted")


def test_targeted_mode_round_trips(tmp_path: Path) -> None:
    objective = set_objective(tmp_path, mode="targeted", goal="N_n is irreducible")

    assert objective.is_targeted
    assert objective.goal == "N_n is irreducible"
    assert objective.resolved is True
    assert "shrink the gap" in objective.completion_rule


def test_exploratory_mode_needs_no_goal(tmp_path: Path) -> None:
    objective = set_objective(tmp_path, mode="exploratory")

    assert objective.resolved is True
    assert "no single named goal has to close" in objective.completion_rule


def test_a_targeted_project_missing_its_goal_is_unresolved(tmp_path: Path) -> None:
    path = tmp_path / "research" / "PIPELINE_STATE.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"math_objective_mode": "targeted"}), encoding="utf-8")

    assert resolve_objective(tmp_path).resolved is False


def test_setting_the_mode_preserves_other_state(tmp_path: Path) -> None:
    path = tmp_path / "research" / "PIPELINE_STATE.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"research_target_level": "publishable"}), encoding="utf-8")

    set_objective(tmp_path, mode="exploratory")

    assert json.loads(path.read_text())["research_target_level"] == "publishable"


# -- when the graph is required --------------------------------------------

def test_exploration_does_not_require_a_goal_rooted_dag() -> None:
    # Decomposing before the route is settled fills in lemmas for a structure
    # that gets thrown away.
    assert graph_required_for("explore", "targeted") is False


def test_development_and_certification_require_it() -> None:
    assert graph_required_for("develop", "targeted") is True
    assert graph_required_for("certify", "targeted") is True


def test_exploratory_projects_are_never_required_to_close_a_goal() -> None:
    # There is no single G, so a goal-rooted DAG would be a fiction.
    assert graph_required_for("certify", "exploratory") is False


# -- the question the graph answers ----------------------------------------

def _graph(**nodes) -> ProofGraph:
    return ProofGraph({"goal": "G", "routes": [], "nodes": nodes})


def test_gap_reports_what_the_goal_still_rests_on() -> None:
    graph = _graph(
        G={"status": "open", "is_goal": True, "depends_on": ["A", "B"]},
        A={"status": "proved", "reviewer_confirmed": True, "depends_on": []},
        B={"status": "open", "depends_on": []},
    )

    report = graph.gap()

    assert report.gap_size == 1
    assert report.blocking_nodes == ["B"]
    assert report.proved_nodes == ["A"]


def test_a_fully_proved_graph_has_no_gap() -> None:
    graph = _graph(
        G={"status": "proved", "reviewer_confirmed": True, "is_goal": True, "depends_on": ["A"]},
        A={"status": "proved", "reviewer_confirmed": True, "depends_on": []},
    )

    assert graph.gap().gap_size == 0


def test_the_frontier_is_the_deepest_unproved_node() -> None:
    # If B rests on B1, the actionable gap is B1, not B.
    graph = _graph(
        G={"status": "open", "is_goal": True, "depends_on": ["B"]},
        B={"status": "open", "depends_on": ["B1"]},
        B1={"status": "open", "depends_on": []},
    )

    assert graph.gap().blocking_nodes == ["B1"]


# -- checks that keep the graph honest -------------------------------------

def test_a_proved_node_needs_reviewer_confirmation() -> None:
    graph = _graph(
        G={"status": "proved", "is_goal": True, "depends_on": []},
    )

    issues = graph.validate()

    # An unconfirmed node makes the remaining gap look smaller than it is.
    assert any("without reviewer confirmation" in issue for issue in issues)


def test_a_ruled_out_route_needs_evidence() -> None:
    graph = ProofGraph(
        {"goal": "G", "routes": [{"name": "C", "status": "ruled_out"}], "nodes": {}}
    )

    assert any("ruled_out without evidence" in issue for issue in graph.validate())


def test_a_dependency_cycle_is_reported() -> None:
    graph = _graph(
        G={"status": "open", "is_goal": True, "depends_on": ["A"]},
        A={"status": "open", "depends_on": ["B"]},
        B={"status": "open", "depends_on": ["A"]},
    )

    assert any("dependency cycle" in issue for issue in graph.validate())


def test_an_unknown_dependency_is_reported() -> None:
    graph = _graph(G={"status": "open", "is_goal": True, "depends_on": ["ghost"]})

    assert any("unknown node 'ghost'" in issue for issue in graph.validate())


def test_an_empty_goal_is_reported() -> None:
    assert any("goal is empty" in issue for issue in ProofGraph({}).validate())


def test_bad_statuses_are_reported() -> None:
    graph = ProofGraph(
        {
            "goal": "G",
            "routes": [{"name": "C", "status": "maybe"}],
            "nodes": {"G": {"status": "probably", "is_goal": True}},
        }
    )
    issues = graph.validate()

    assert any("routes[0] status" in issue for issue in issues)
    assert any("node 'G' status" in issue for issue in issues)


# -- routes -----------------------------------------------------------------

def test_routes_are_readable() -> None:
    graph = ProofGraph(
        {
            "goal": "G",
            "routes": [
                {"name": "C", "status": "ruled_out", "evidence": "E1"},
                {"name": "D", "status": "current"},
            ],
            "nodes": {},
        }
    )

    assert graph.ruled_out_routes() == ["C"]
    assert graph.current_route() == "D"


# -- io ---------------------------------------------------------------------

def test_a_missing_graph_reads_as_none(tmp_path: Path) -> None:
    assert load_graph(tmp_path) is None


def test_a_written_graph_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "research" / "PROOF_GRAPH.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(template("N_n is irreducible")), encoding="utf-8")

    graph = load_graph(tmp_path)

    assert graph is not None
    assert graph.goal == "N_n is irreducible"
    assert graph.gap().gap_size == 1


def test_a_corrupt_graph_reads_as_none(tmp_path: Path) -> None:
    path = tmp_path / "research" / "PROOF_GRAPH.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")

    assert load_graph(tmp_path) is None


# -- the CLI ----------------------------------------------------------------

def _write_graph(root: Path, payload: dict) -> None:
    path = root / "research" / "PROOF_GRAPH.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_check_passes_on_a_sound_graph(tmp_path: Path, capsys) -> None:
    from argus_skill.verticals.math import proof_graph_check as cli

    _write_graph(tmp_path, {
        "goal": "G",
        "routes": [{"name": "D", "status": "current"}],
        "nodes": {
            "G": {"status": "open", "is_goal": True, "depends_on": ["A"]},
            "A": {"status": "proved", "reviewer_confirmed": True, "depends_on": []},
        },
    })

    assert cli.main(["check", "--project-root", str(tmp_path)]) == 0
    assert "valid" in capsys.readouterr().out


def test_check_fails_on_an_unconfirmed_proof(tmp_path: Path, capsys) -> None:
    from argus_skill.verticals.math import proof_graph_check as cli

    _write_graph(tmp_path, {
        "goal": "G",
        "routes": [],
        "nodes": {"G": {"status": "proved", "is_goal": True, "depends_on": []}},
    })

    assert cli.main(["check", "--project-root", str(tmp_path)]) == 2
    assert "reviewer confirmation" in capsys.readouterr().err


def test_gap_prints_what_the_goal_rests_on(tmp_path: Path, capsys) -> None:
    from argus_skill.verticals.math import proof_graph_check as cli

    _write_graph(tmp_path, {
        "goal": "G",
        "routes": [],
        "nodes": {
            "G": {"status": "open", "is_goal": True, "depends_on": ["B"]},
            "B": {"status": "open", "statement": "bridging lemma", "depends_on": []},
        },
    })

    assert cli.main(["gap", "--project-root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "gap: 1" in out
    assert "bridging lemma" in out


def test_a_missing_graph_is_reported(tmp_path: Path, capsys) -> None:
    from argus_skill.verticals.math import proof_graph_check as cli

    assert cli.main(["check", "--project-root", str(tmp_path)]) == 2
    assert "no proof graph" in capsys.readouterr().err


def test_template_emits_a_usable_starting_graph(capsys) -> None:
    from argus_skill.verticals.math import proof_graph_check as cli

    assert cli.main(["template", "--goal", "N_n is irreducible"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["goal"] == "N_n is irreducible"
    assert payload["nodes"]["N_n is irreducible"]["is_goal"] is True


# -- the prompts actually carry the rules ----------------------------------

SKILLS = Path(__file__).resolve().parents[1] / "argus_skill" / "verticals" / "math" / "skills"


def _flat(path: Path) -> str:
    """Prompt text with line wrapping collapsed, so assertions survive rewrapping."""
    return " ".join(path.read_text(encoding="utf-8").split())


def test_planner_states_that_ruling_out_a_criterion_is_not_solving() -> None:
    text = _flat(SKILLS / "planner" / "math-research-planning.md")

    assert "ruling out a sufficient criterion is not solving it" in text
    assert "ROUTE_LEDGER.json" in text
    # The old blanket ban on graphs is gone.
    assert "no particular ledger or graph file is required" not in text


def test_reviewer_names_the_three_failure_layers() -> None:
    text = _flat(SKILLS / "reviewer" / "math-research-review.md")

    for layer in ("`proof`", "`plan`", "`strategy`"):
        assert layer in text
    assert "Local progress is not gap reduction" in text


def test_engineer_permits_the_graph_once_the_route_is_settled() -> None:
    text = _flat(SKILLS / "engineer" / "math-research-execution.md")

    # The blanket "do not create graph files" used to forbid the one structure
    # that measures progress.
    assert "planning, ledger, graph, audit" not in text
    assert "PROOF_GRAPH.json" in text
    assert "Under `explore` neither is required" in text
