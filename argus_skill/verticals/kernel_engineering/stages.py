"""General GPU-kernel engineering vertical.

This vertical is for real repository work: diagnose and improve CUDA/Triton/
TileLang/CUTLASS/PyTorch kernels, preserve the public API, validate numerical
behavior, benchmark on the target accelerator, and prepare an upstream-quality
change.  ``kernelbench`` remains the fixed SOL-ExecBench competition vertical;
this package owns production/library kernel work where environment provenance
and integration quality matter as much as a latency number.
"""

from __future__ import annotations

from ...skills.stage_machine import ChecklistItem
from ..speedrun.stages import _PIPELINE_CHECK

STAGE_ORDER = [
    "scope",
    "discover",
    "environment",
    "baseline",
    "optimize",
    "validate",
    "report",
    "deliver",
]

# Profiling is the first phase inside optimize, not a standalone pipeline stage.
# Older/project-authored state may still use this descriptive phase name.
STAGE_ALIASES = {
    "profiling": "optimize",
    "optimization": "optimize",
}

WORKFLOW_MODE = "staged"
completion_gate = "metric"
MISSION_KIND = "optimize"


def search_altitude_context(project_root) -> str:
    from .campaign import planner_context

    return planner_context(project_root)


def planner_task_issues(stage: str, project_root, task) -> tuple[str, ...]:
    from .campaign import planner_task_issues as check_task

    return check_task(stage, project_root, task)


def stage_completion_issues(stage: str, project_root) -> tuple[str, ...]:
    from .campaign import stage_completion_issues as check_stage

    return check_stage(stage, project_root)


def prepare_mission(stage: str, project_root, state_root) -> str:
    """Prepare baseline isolation or current campaign control."""
    if stage in {"optimize", "validate", "report", "deliver"}:
        return search_altitude_context(project_root)
    if stage != "baseline":
        return ""
    from .baseline_workspace import prepare_baseline_workspace

    try:
        baseline = prepare_baseline_workspace(project_root, state_root)
    except Exception as exc:  # setup failure is actionable mission context
        return f"## Baseline isolation unavailable\n- error: {exc}"
    return baseline.prompt_block() if baseline is not None else ""

_AUDIT = (
    "${ARGUS_SKILL_PYTHON:-python} -m argus_skill.verticals.kernel_engineering.environment_audit"
)
_FRONTIER = (
    "${ARGUS_SKILL_PYTHON:-python} -m argus_skill.verticals.kernel_engineering.frontier_watch"
)
_OUTCOME = (
    "${ARGUS_SKILL_PYTHON:-python} -m argus_skill.verticals.kernel_engineering.attempt_outcome"
)
_LEVERAGE = (
    "${ARGUS_SKILL_PYTHON:-python} -m argus_skill.verticals.kernel_engineering.leverage_gate"
)
_CAMPAIGN = (
    "${ARGUS_SKILL_PYTHON:-python} -m argus_skill.verticals.kernel_engineering.campaign"
)

STAGE_CHECKS: dict[str, list[tuple[str, str]]] = {
    "scope": [
        _PIPELINE_CHECK,
        ("Kernel mission contract present", "test -s research/KERNEL_SCOPE.md"),
        ("Repository instructions inspected", "test -s research/PROJECT_NATIVE_SETUP.md"),
    ],
    "discover": [
        _PIPELINE_CHECK,
        (
            "Online algorithm frontier validates",
            f"{_FRONTIER} check --project-root . --stage discover",
        ),
        ("Algorithm plan present", "test -s research/ALGORITHM_PLAN.md"),
    ],
    "environment": [
        _PIPELINE_CHECK,
        ("Environment audit present", "test -s research/ENVIRONMENT_AUDIT.json"),
        ("Environment audit passes", f"{_AUDIT} check --project-root ."),
        (
            "Specialized tool shortlist present",
            "test -s research/TOOLCHAIN_CANDIDATES.md",
        ),
        ("Infrastructure reuse plan present", "test -s research/INFRASTRUCTURE_REUSE_PLAN.md"),
    ],
    "baseline": [
        _PIPELINE_CHECK,
        ("Baseline protocol pinned", "test -s research/BASELINE_PROTOCOL.md"),
        ("Correct baseline evidence present", "test -s research/BASELINE_RESULT.json"),
    ],
    "optimize": [
        _PIPELINE_CHECK,
        ("Kernel leverage gate is valid", f"{_LEVERAGE} check --project-root ."),
        (
            "Hypothesis-driven attempt evidence exists",
            "{python} -m argus_skill.verticals.path_evidence --project-root . "
            "--glob 'attempts/*/*' --glob 'attempts/*/*/*' "
            "--glob 'experiments/*/*' --glob 'experiments/*/*/*'",
        ),
        ("Attempt outcome taxonomy is valid", f"{_OUTCOME} check --project-root ."),
        ("A retained winner has real paired speedup", f"{_CAMPAIGN} check --project-root ."),
    ],
    "validate": [
        _PIPELINE_CHECK,
        ("Kernel leverage gate is valid", f"{_LEVERAGE} check --project-root ."),
        ("Attempt outcome taxonomy is valid", f"{_OUTCOME} check --project-root ."),
        ("Validation matrix present", "test -s research/VALIDATION_MATRIX.md"),
        ("Candidate validation evidence present", "test -s research/VALIDATION_RESULT.json"),
    ],
    "report": [
        _PIPELINE_CHECK,
        ("Results report present", "test -s RESULTS.md"),
        ("Environment provenance retained", "test -s research/ENVIRONMENT_AUDIT.json"),
    ],
    "deliver": [
        _PIPELINE_CHECK,
        ("Feature branch is active", "test \"$(git branch --show-current)\" != main"),
        ("Tracked worktree is clean", "git diff --quiet && git diff --cached --quiet"),
    ],
}

for _stage in ("scope", "report"):
    STAGE_CHECKS[_stage].insert(
        1,
        (
            "Online frontier snapshot validates for this stage",
            f"{_FRONTIER} check --project-root . --stage {_stage}",
        ),
    )

_ENGINEER_SKILL = "engineer/kernel-environment-first-engineering.md"
_REVIEWER_SKILL = "reviewer/kernel-engineering-review.md"

REVIEWER_CHECKLISTS: dict[str, tuple[str, str, list[str]]] = {
    "scope": (
        _ENGINEER_SKILL,
        "Evaluate the kernel scope before any implementation work. The target op, "
        "public API, editable/frozen files, target hardware, correctness oracle, "
        "benchmark command, supported shapes/dtypes, and intended upstream change "
        "must be explicit. The project-native install and benchmark instructions "
        "must have been read. Pass only when the task is narrow enough to measure.",
        ["research/KERNEL_SCOPE.md", "research/PROJECT_NATIVE_SETUP.md"],
    ),
    "discover": (
        _REVIEWER_SKILL,
        "Review algorithm discovery before any GPU implementation. Require at least "
        "three materially different mathematical or dataflow reformulations. Each must "
        "name the work, storage, synchronization, launch, or communication it removes; "
        "state complexity and an exactness/error argument; estimate the end-to-end "
        "ceiling; and distinguish itself from current primary prior art. Ordinary "
        "tiling, warp/stage tuning, split-count changes, wrapper cleanup, or autotune "
        "expansion do not satisfy this stage. Advance only when one selected prototype "
        "plausibly offers at least 10% end-to-end gain, meaningful memory/communication "
        "reduction, or an asymptotic/coverage improvement. No production kernel edits "
        "are allowed in discover.",
        ["research/ALGORITHM_PLAN.md", "research/frontier/discover.json"],
    ),
    "environment": (
        _ENGINEER_SKILL,
        "Treat this as a hard gate. Independently inspect ENVIRONMENT_AUDIT.json, "
        "TOOLCHAIN_CANDIDATES.md, and INFRASTRUCTURE_REUSE_PLAN.md. The registry "
        "must have been queried for the relevant platform and bottleneck categories. "
        "The selected implementation path must name its "
        "required capability (for example tilelang, triton, cuda_cpp, cutlass_cute, "
        "profiling, or sanitizer), and every required capability must be ready in the "
        "same environment that will run tests and benchmarks. Project extras/lockfiles "
        "and mature upstream libraries must be preferred over hand-rolled substitutes. "
        "A missing compiler/package/profiler is an environment failure, not evidence "
        "that the kernel idea is bad. Do not advance while the audit is mismatched, "
        "not refreshed after environment changes, or red.",
        [
            "research/ENVIRONMENT_AUDIT.json",
            "research/ENVIRONMENT_AUDIT.md",
            "research/TOOLCHAIN_CANDIDATES.md",
            "research/INFRASTRUCTURE_REUSE_PLAN.md",
        ],
    ),
    "baseline": (
        _ENGINEER_SKILL,
        "Verify a clean unmodified baseline in the audited environment. Correctness "
        "must pass before timing; warmup/autotune/JIT policy, synchronization, input "
        "matrix, hardware/software versions, and isolation policy must be pinned. A "
        "baseline that differs from project/official reference expectations must be "
        "diagnosed before optimization starts.",
        ["research/BASELINE_PROTOCOL.md", "research/BASELINE_RESULT.json"],
    ),
    "optimize": (
        _ENGINEER_SKILL,
        "Evaluate the latest attempt as an engineering experiment: measured bottleneck, "
        "Amdahl/leverage gate, mechanistic hypothesis, minimal implementation, correctness result, timing, "
        "and verdict. Reject blind parameter sweeps and reinvention of an available "
        "project/vendor primitive. Compile/runtime failures must be attributed to code "
        "versus environment before abandoning the mechanism. Every attempt must have "
        "OUTCOME.json with separate execution_status, failure_class, and idea_status; "
        "environment/toolchain/infrastructure failures cannot refute an idea or consume "
        "a candidate Try. A correct but slower/noisy candidate keeps the direction open "
        "when profile evidence supports a materially distinct next Try. Optimize closes only with a "
        "retained winner; final evidence-backed exhaustion requests replanning instead "
        "of advancing a failed candidate to validate/report.",
        ["attempts/", "attempts/*/LEVERAGE.json", "research/ENVIRONMENT_AUDIT.json", "research/BASELINE_RESULT.json"],
    ),
    "validate": (
        _REVIEWER_SKILL,
        "Audit the retained candidate against the full supported contract: forward and "
        "backward/reference parity, dtypes, aligned and ragged shapes, optional/varlen "
        "paths, determinism where relevant, fallback behavior, memory, and repeated "
        "isolated benchmarks. Require environment provenance and no benchmark/scorer "
        "weakening. Hardware-specific dispatch is acceptable when unsupported devices "
        "fall back safely.",
        ["research/VALIDATION_MATRIX.md", "research/VALIDATION_RESULT.json", "attempts/"],
    ),
    "report": (
        _REVIEWER_SKILL,
        "Require an upstream-ready report with exact commands, measured speedup, "
        "regressions, limits, and a narrow diff. Then move to delivery; do not reopen optimization.",
        ["RESULTS.md", "research/ENVIRONMENT_AUDIT.json", "research/VALIDATION_RESULT.json"],
    ),
    "deliver": (
        _REVIEWER_SKILL,
        "Confirm the validated winner is isolated on a clean feature branch. Commit only "
        "with operator authorization and never push without approval.",
        ["RESULTS.md", "research/PERFORMANCE_RESULT.json"],
    ),
}

for _stage in ("scope", "report"):
    _skill, _instructions, _artifacts = REVIEWER_CHECKLISTS[_stage]
    _frontier_artifact = f"research/frontier/{_stage}.json"
    REVIEWER_CHECKLISTS[_stage] = (
        _skill,
        (
            "FRONTIER FRESHNESS GATE: independently inspect the current stage's "
            f"`{_frontier_artifact}`. It must prove a real online search for the current "
            "stage across the target repository, official toolchains, and recent "
            "papers/author implementations. Re-check cited sources when material. "
            "`no_material_update=true` is acceptable only with real queries/sources "
            "and a decision-impact explanation. Offline, wrong-stage, superseded, or "
            "template evidence fails "
            "the stage.\n\n" + _instructions
        ),
        [_frontier_artifact, *_artifacts],
    )

CHECKLIST_STAGE_ORDER: tuple[str, ...] = tuple(STAGE_ORDER)

CHECKLIST_ITEMS: dict[str, tuple[ChecklistItem, ...]] = {
    "scope": (
        ChecklistItem(
            id="scope.kernel_contract",
            statement=(
                "The target kernel/op, public API, allowed edits, target accelerator, "
                "correctness oracle, benchmark entry point, and supported shape/dtype "
                "surface are pinned before implementation."
            ),
            evidence_hint="research/KERNEL_SCOPE.md",
        ),
        ChecklistItem(
            id="scope.project_native_setup",
            statement=(
                "Repository-native installation, extras, lockfiles, CI, benchmark tools, "
                "and existing backend abstractions were inspected and recorded."
            ),
            evidence_hint="research/PROJECT_NATIVE_SETUP.md",
        ),
    ),
    "discover": (
        ChecklistItem(
            id="discover.algorithm_reformulations",
            statement=(
                "At least three materially different algorithm or dataflow "
                "reformulations are derived before implementation, each identifying "
                "the computation, storage, synchronization, launch, or communication "
                "it removes and why the result remains exact or has a bounded error."
            ),
            evidence_hint="research/ALGORITHM_PLAN.md",
        ),
        ChecklistItem(
            id="discover.novelty_and_value",
            statement=(
                "The selected prototype is distinguished from current primary prior "
                "art and has a credible path to at least 10% end-to-end gain, meaningful "
                "memory/communication reduction, or an asymptotic/coverage improvement."
            ),
            evidence_hint="research/ALGORITHM_PLAN.md and research/frontier/discover.json",
        ),
    ),
    "environment": (
        ChecklistItem(
            id="environment.capability_audit",
            statement=(
                "A fresh machine-readable audit proves that every capability selected "
                "for this implementation path is available in the actual test/benchmark "
                "environment. Missing professional tooling is resolved or explicitly "
                "blocks the stage; it is never papered over with a homemade substitute."
            ),
            evidence_hint=(
                "research/ENVIRONMENT_AUDIT.json generated by "
                "`python -m argus_skill.verticals.kernel_engineering.environment_audit collect`"
            ),
        ),
        ChecklistItem(
            id="environment.specialized_catalog",
            statement=(
                "The professional tool registry was queried by relevant platform and "
                "bottleneck category; the shortlist records maintained specialist "
                "packages considered, legacy/archived options rejected, and why the "
                "selected stack is preferable to custom infrastructure."
            ),
            evidence_hint="research/TOOLCHAIN_CANDIDATES.md",
        ),
        ChecklistItem(
            id="environment.infrastructure_reuse",
            statement=(
                "The reuse plan identifies project-native and mature upstream libraries, "
                "profilers, build tools, and reference implementations considered; it "
                "justifies any custom infrastructure that remains necessary."
            ),
            evidence_hint="research/INFRASTRUCTURE_REUSE_PLAN.md",
        ),
    ),
    "baseline": (
        ChecklistItem(
            id="baseline.correct_reproducible",
            statement=(
                "The unmodified baseline passes the real correctness oracle and has a "
                "reproducible isolated timing record with exact commands, versions, "
                "warmup/autotune policy, shapes, and synchronization."
            ),
            evidence_hint="research/BASELINE_PROTOCOL.md and research/BASELINE_RESULT.json",
        ),
    ),
    "optimize": (
        ChecklistItem(
            id="optimize.mechanistic_attempt",
            statement=(
                "Each attempt starts from a measured bottleneck, states a physical or "
                "compiler-level hypothesis, changes the smallest relevant surface, and "
                "records correctness, timing, and a two-axis OUTCOME.json. Environment, "
                "dependency, toolchain, permission, or benchmark-infrastructure failures "
                "leave the idea untested or inconclusive; only a valid executed result "
                "may support or refute that exact candidate. Round count is not Try count: "
                "environment and orchestration repair rounds do not consume a Try. A correct "
                "but slower/noisy candidate may lead to a materially distinct implementation "
                "when profile evidence shows plausible headroom. The stage passes only for a retained "
                "candidate; an evidence-exhausted direction replans instead of advancing a failed "
                "through validate/report."
            ),
            evidence_hint=(
                "attempts/<id>/OUTCOME.json, CHANGES.md, and raw test/benchmark artifacts; "
                "validate with `python -m argus_skill.verticals.kernel_engineering."
                "attempt_outcome check --project-root .`"
            ),
        ),
    ),
    "validate": (
        ChecklistItem(
            id="validate.full_contract",
            statement=(
                "The retained candidate is validated across the supported numerical, "
                "shape, dtype, gradient, determinism, fallback, memory, and performance "
                "matrix without weakening the harness."
            ),
            evidence_hint="research/VALIDATION_MATRIX.md and research/VALIDATION_RESULT.json",
        ),
    ),
    "report": (
        ChecklistItem(
            id="report.evidence_bounded_claim",
            statement=(
                "RESULTS.md reports exact environment and commands, raw correctness and "
                "performance evidence, uncertainty, regressions, dispatch boundaries, "
                "limitations, and only the speedup claim actually demonstrated."
            ),
            evidence_hint="RESULTS.md",
        ),
    ),
    "deliver": (
        ChecklistItem(
            id="deliver.clean_change",
            statement="The validated winner is on a clean feature branch, ready for review.",
            evidence_hint="git status, branch, commit, RESULTS.md",
        ),
    ),
}

for _stage in ("scope", "discover", "report"):
    CHECKLIST_ITEMS[_stage] = (
        ChecklistItem(
            id=f"{_stage}.frontier_current",
            statement=(
                "A current-stage online frontier search covers target-repository work, "
                "official toolchain/package changes, and recent papers or author "
                "implementations. Findings changed the plan, or the artifact explicitly "
                "records that no material update was found."
            ),
            evidence_hint=(
                f"research/frontier/{_stage}.json; "
                f"validate with `python -m argus_skill.verticals.kernel_engineering."
                f"frontier_watch check --stage {_stage}` (the command verifies the "
                "append-only ledger binding without loading the JSONL into context)"
            ),
        ),
        *CHECKLIST_ITEMS[_stage],
    )


def role_banner(role: str) -> str:
    common = (
        "MISSION — production GPU kernel engineering. Improve a real repository's "
        "kernel while preserving its API and correctness. ENVIRONMENT IS PART OF THE "
        "ALGORITHM: before writing code, inspect project-native setup and prove the "
        "chosen professional toolchain is installed and compatible. Do not recreate "
        "Triton/TileLang/CUTLASS/CuTe/vendor libraries, benchmark harnesses, profilers, "
        "or training/RL infrastructure that the project already depends on. A missing "
        "package/compiler/configuration is an execution blocker, never a failed kernel "
        "idea: keep execution_status/failure_class separate from idea_status. Correctness "
        "precedes timing; only isolated real-hardware measurements "
        "support a speed claim. CONTINUOUS FRONTIER WATCH is event-driven: search when "
        "selecting scope, after relevant upstream/toolchain changes or repeated failures, "
        "on mechanism pivots, and before a PR/report. Reuse current evidence across "
        "unchanged intermediate stages. This is not a paper pipeline and not "
        "SOL-ExecBench.\n"
    )
    if role == "planner":
        return common + (
            "After scope, complete the discover stage before environment or code work: "
            "derive and compare genuinely different algorithms, reject ordinary tuning "
            "as novelty, and select a prototype only when its expected value clears the "
            "discover bar. Then install only the project-documented toolchain in an "
            "isolated environment and rerun the audit. During optimize, stop at the first correctness-passing "
            "candidate whose paired end-to-end benchmark clears both aggregate and worst-row "
            "thresholds. Validate, report, and deliver it before starting another cycle.\n"
        )
    if role == "reviewer":
        return common + (
            "At discover, reject implementation work, routine kernel tuning, weak prior-art "
            "search, or proposals with no explicit work-removal and value argument. "
            "Fail closed on mismatched/red environment audits, audits not refreshed after "
            "environment changes, missing project extras, "
            "unexplained fallbacks, mixed benchmark environments, or compile failures "
            "misreported as algorithm failures. Also fail wrong-stage, superseded, "
            "offline, or template frontier snapshots and claims that ignore current "
            "upstream/paper evidence. Repeated identical gate failures must trigger "
            "reconsider/replan, not another full rerun.\n"
        )
    if role == "engineer":
        return common + (
            "During discover, derive the equations/dataflow, compare at least three "
            "reformulations against primary prior art, write ALGORITHM_PLAN.md, and do not "
            "edit production GPU code. After Reviewer selection, run the environment audit. "
            "If a tool is missing, use the repository's "
            "documented lockfile/extras in a local environment and rerun the audit. Profile, "
            "make one focused change, and use `kernel_engineering.campaign compare` for the "
            "paired result. Once it passes, stop tuning and deliver.\n"
        )
    return common


__all__ = [
    "CHECKLIST_ITEMS",
    "CHECKLIST_STAGE_ORDER",
    "REVIEWER_CHECKLISTS",
    "STAGE_CHECKS",
    "STAGE_ORDER",
    "WORKFLOW_MODE",
    "completion_gate",
    "planner_task_issues",
    "prepare_mission",
    "role_banner",
    "search_altitude_context",
    "stage_completion_issues",
]
