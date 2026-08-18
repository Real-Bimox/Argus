from __future__ import annotations

from pathlib import Path

from argus_skill.verticals.research.stages import STAGE_CHECKLISTS

_SKILLS = Path(__file__).parents[2] / "argus_skill" / "builtin_skills"
_AMBITION_SKILLS = (
    "engineer/research-ideation.md",
    "engineer/idea-discovery.md",
    "engineer/idea-creator.md",
    "engineer/novelty-check.md",
    "engineer/auto-research-pipeline.md",
    "engineer/research-brief-to-experiment-plan.md",
    "engineer/idea-feasibility-derisk.md",
    "engineer/final-paper-review.md",
    "reviewer/experiment-plan-review.md",
    "reviewer/experiment-results-review.md",
    "reviewer/academic-paper-peer-review-benchmark.md",
)


def _skill(relative: str) -> str:
    return (_SKILLS / relative).read_text(encoding="utf-8")


def test_paper_drafting_skills_stay_compact() -> None:
    paths = (
        "engineer/emnlp-paper-drafting.md",
        "engineer/aaai-paper-drafting.md",
        "engineer/research-brief-to-experiment-plan.md",
    )

    sizes = {path: len(_skill(path)) for path in paths}
    assert all(size < 9_000 for size in sizes.values()), sizes
    assert sum(sizes.values()) < 22_000


def test_protocol_does_not_auto_publish_negative_results() -> None:
    results_review = _skill("reviewer/experiment-results-review.md")
    result_to_claim = _skill("engineer/result-to-claim.md")
    analysis = _skill("engineer/research-results-analysis-and-figures.md")
    runner = _skill("engineer/research-experiment-runner.md")
    pipeline = _skill("engineer/auto-research-pipeline.md")

    assert "at most ONE" not in results_review
    assert "write the paper on the current results" not in results_review
    assert "There is no fixed number of optimization passes" in results_review
    assert "does not automatically advance to drafting" in runner
    assert "not automatic write-up" in pipeline
    assert "post-selection repair loop" in result_to_claim
    assert "chronological experiment report" in analysis
    assert "change labels, discard seeds" in pipeline


def test_paper_is_claim_driven_without_hiding_contrary_evidence() -> None:
    result_to_claim = _skill("engineer/result-to-claim.md")
    final_review = _skill("engineer/final-paper-review.md")
    analysis = {item.id: item.statement for item in STAGE_CHECKLISTS["analysis"]}
    draft = {item.id: item.statement for item in STAGE_CHECKLISTS["draft"]}

    assert "claim-driven" in result_to_claim
    assert "claim-critical contrary evidence" in result_to_claim
    assert "strongest valid evidence for its thesis" in final_review
    assert "strongest valid evidence for the thesis" in analysis["analysis.thesis"]
    assert "not a chronological experiment report" in draft["draft.tex"]


def test_live_checklist_requires_thesis_and_implementation_adequacy() -> None:
    run = {item.id: item.statement for item in STAGE_CHECKLISTS["run"]}
    analysis = {item.id: item.statement for item in STAGE_CHECKLISTS["analysis"]}
    draft = {item.id: item.statement for item in STAGE_CHECKLISTS["draft"]}
    review = {item.id: item.statement for item in STAGE_CHECKLISTS["review"]}

    assert "under-engineered" in run["run.method_diagnosis_recall"]
    assert "selective argument" in analysis["analysis.thesis"]
    assert "same thesis" in draft["draft.tex"]
    assert "weak result cannot be rescued" in review["review.publication_value"]


def test_open_ended_paper_ideation_reuses_twelve_route_team() -> None:
    discovery = _skill("engineer/idea-discovery.md")
    research = {item.id: item.statement for item in STAGE_CHECKLISTS["research"]}

    assert "pool-set --root <team_root> --width 12 --state running" in discovery
    assert "A single model call" in discovery
    assert "written cross-examination" in discovery
    assert "12-route portfolio" in research["research.thesis"]
    assert "adversarial meta-review" in research["research.thesis"]


def test_research_idea_selection_requires_ambition_without_decorative_math() -> None:
    discovery = _skill("engineer/idea-discovery.md")
    creator = _skill("engineer/idea-creator.md")
    peer_review = _skill("reviewer/academic-paper-peer-review-benchmark.md")
    research = {item.id: item.statement for item in STAGE_CHECKLISTS["research"]}

    assert "Hard technical core" in discovery
    assert "Frontier significance" in discovery
    assert "decorative equations" in discovery
    assert "technical_depth" in creator
    assert "theoretical_foundation" in creator
    thesis = research["research.thesis"]
    assert "nontrivial technical core" in thesis
    assert "formal/causal predictions" in thesis
    assert "decorative math" in thesis
    assert "feasibility rescue" in thesis
    assert "shallow prompt/schema/wrapper/scale" in peer_review


def test_research_selection_and_review_skills_share_the_ambition_standard() -> None:
    for path in _AMBITION_SKILLS:
        text = " ".join(_skill(path).split())
        assert "nontrivial technical core" in text, path
        assert "verified originality" in text, path
        assert "formal/causal grounding" in text, path
        assert "field-level consequence" in text, path


def test_manager_and_planner_prompts_preserve_the_ambition_standard() -> None:
    root = Path(__file__).parents[2] / "argus_skill" / "roles" / "prompts"
    manager = (root / "manager.py").read_text(encoding="utf-8")
    planner = (root / "planner.py").read_text(encoding="utf-8")

    for prompt in (manager, planner):
        assert "nontrivial " in prompt and "technical core" in prompt
        assert "verified originality" in prompt
        assert "formal/causal" in prompt
        assert "field-level significance" in prompt
