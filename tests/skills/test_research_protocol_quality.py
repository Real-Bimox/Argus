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


def test_broad_paper_ideation_streams_review_and_probes() -> None:
    discovery = _skill("engineer/idea-discovery.md")
    creator = _skill("engineer/idea-creator.md")
    pipeline = _skill("engineer/auto-research-pipeline.md")
    normalized_discovery = " ".join(discovery.split())
    normalized_creator = " ".join(creator.split())
    normalized_pipeline = " ".join(pipeline.split())
    research = {item.id: item.statement for item in STAGE_CHECKLISTS["research"]}

    assert "pool-set --root <team_root> --width 12 --state running" in discovery
    assert "spawn only the missing routes" in discovery
    assert "Never restart a second" in discovery
    assert "A single model call" in discovery
    assert "fresh independent reviewer" in discovery
    assert "starts its probe immediately" in discovery
    assert "first route whose independent probe records `advance`" in discovery
    assert "at least four routes" in discovery
    assert "network/statistical physics" in normalized_discovery
    assert "canonical 12-route team pipeline" in research["research.idea_portfolio"].lower()
    assert "without waiting" in research["research.idea_portfolio"]
    assert "earliest independently reviewed candidate" in (
        research["research.adversarial_selection"]
    )
    assert "does not wait for every route or probe" in (
        research["research.adversarial_selection"]
    )
    assert "first independently reviewed probe with an `advance` verdict wins" in (
        normalized_creator
    )
    assert "Do not wait for every candidate" in normalized_creator
    assert "unfinished routes are not a stage blocker" in normalized_pipeline


def test_research_idea_selection_requires_ambition_without_decorative_math() -> None:
    discovery = _skill("engineer/idea-discovery.md")
    creator = _skill("engineer/idea-creator.md")
    peer_review = _skill("reviewer/academic-paper-peer-review-benchmark.md")
    research = {item.id: item.statement for item in STAGE_CHECKLISTS["research"]}

    assert "Hard technical core" in discovery
    assert "Frontier significance" in discovery
    assert "decorative equations" in discovery
    assert "scaling law" in discovery
    assert "measurable quantities" in discovery
    assert "technical_depth" in creator
    assert "theoretical_foundation" in creator
    thesis = research["research.thesis"]
    assert "nontrivial technical core" in thesis
    assert "formal or causal predictions" in thesis
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


def test_research_smokes_reject_label_leakage_before_model_calls() -> None:
    probe = _skill("engineer/idea-feasibility-derisk.md")
    pipeline = _skill("engineer/auto-research-pipeline.md")
    plan_review = _skill("reviewer/experiment-plan-review.md")
    benchmark = {
        item.id: item.statement for item in STAGE_CHECKLISTS["benchmark"]
    }

    for text in (probe, pipeline, plan_review):
        assert "gold labels" in text
    assert "remove or permute hidden labels" in probe
    assert "same information and intervention timing" in probe
    assert "one decision-sized milestone" in pipeline
    assert "removing or permuting hidden labels" in (
        benchmark["benchmark.evaluator_authentic"]
    )


def test_research_smokes_require_discriminative_power_before_rejection() -> None:
    probe = _skill("engineer/idea-feasibility-derisk.md")
    pipeline = _skill("engineer/auto-research-pipeline.md")
    runner = _skill("engineer/research-experiment-runner.md")
    plan_review = _skill("reviewer/experiment-plan-review.md")
    results_review = _skill("reviewer/experiment-results-review.md")
    research = {item.id: item.statement for item in STAGE_CHECKLISTS["research"]}

    for text in (probe, pipeline, runner, plan_review, results_review):
        assert "headroom" in text
        assert "inconclusive" in text
    assert "baseline ceiling/floor saturation" in research["research.signal_derisk"]
    assert "predeclared power and headroom" in research["research.signal_derisk"]


def test_route_review_precedes_probe_without_global_barrier() -> None:
    creator = _skill("engineer/idea-creator.md")
    probe = _skill("engineer/idea-feasibility-derisk.md")
    pipeline = _skill("engineer/auto-research-pipeline.md")
    brief = _skill("engineer/research-brief-to-experiment-plan.md")
    research = {item.id: item.statement for item in STAGE_CHECKLISTS["research"]}
    planner = (
        Path(__file__).parents[2]
        / "argus_skill"
        / "roles"
        / "prompts"
        / "planner.py"
    ).read_text(encoding="utf-8")

    assert "Complete this route-local selection" in creator
    assert "Only after Step 1 has selected" in creator
    assert "After an idea has passed method-reasonableness selection" in probe
    assert "selection-before-probe" in pipeline
    assert "earlier dependency" in brief
    assert "Before any probe is designed or executed" in research["research.thesis"]
    assert "final single thesis" in research["research.thesis"]
    assert "Only after research.thesis" in research["research.signal_derisk"]
    normalized_planner = " ".join(planner.split())
    assert "selection must precede probe design and execution" in normalized_planner
    assert "Author the frozen evidence question" in normalized_planner
    assert "does not yet choose the final thesis" in creator
    assert "must not silently change the frozen premise" in creator
    assert "first independently reviewed probe with an `advance` verdict wins" in (
        " ".join(creator.split())
    )
    assert "unfinished routes are not a stage blocker" in " ".join(pipeline.split())


def test_experiment_review_does_not_repeat_idea_selection() -> None:
    plan_review = _skill("reviewer/experiment-plan-review.md")
    results_review = _skill("reviewer/experiment-results-review.md")

    assert "Do not re-rank its novelty" in plan_review
    assert "not repeating upstream idea selection" in results_review
    assert "Do not re-rank or re-litigate" in results_review
    assert "engineering and protocol validity" in results_review
    assert "decide publication value" in results_review
    assert "`pass` means the experiment is engineering-valid" in " ".join(
        results_review.split()
    )
    assert '"idea_status": "untested|inconclusive|supported|refuted"' in results_review
    assert "research/ideas/<id>/EVIDENCE.json" in _skill(
        "engineer/idea-creator.md"
    )


def test_research_protocol_rejects_unsupported_magic_thresholds() -> None:
    brief = _skill("engineer/research-brief-to-experiment-plan.md")
    pipeline = _skill("engineer/auto-research-pipeline.md")
    plan_review = _skill("reviewer/experiment-plan-review.md")
    results_review = _skill("reviewer/experiment-results-review.md")
    plan = {item.id: item.statement for item in STAGE_CHECKLISTS["plan"]}

    for text in (brief, pipeline, plan_review, results_review):
        assert "round-number" in text
        assert "utility" in text
    assert "unsupported round-number gains" in plan["plan.experiment"]
    assert "continuous evidence" in brief
    assert "cost-quality frontier" in results_review
