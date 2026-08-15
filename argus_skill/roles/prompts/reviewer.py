"""Reviewer prompt operations, structured context, and complete prompt body."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Mapping

from ...core.model_visible_text import (
    MODEL_INTEGRITY_BOUNDARY,
    sanitize_model_visible_text,
)
from ..task_contract import (
    EFFECTIVE_TASK_CONTRACT,
    format_native_shell_command,
    native_shell_summary,
)
from .types import ChecklistMode, RoleName, RolePromptRequest

EVALUATE = "evaluate"

OPERATIONS = frozenset({EVALUATE})

_REEVALUATE_HEADER = (
    "## NEW ROUND — RE-EVALUATE INDEPENDENTLY (resumed reviewer)\n"
    "You are resuming your OWN thread ONLY to avoid re-sending the static rubric "
    "— NOT to defer to your previous verdict. The role, rubric, and decision "
    "rules from earlier in this thread still bind, but THIS round's artifacts "
    "below are the ONLY evidence: re-verify against them from scratch. Your prior "
    "verdict is not a prior and must never be rubber-stamped; judge this round on "
    "its own artifacts, summary, and log audit.\n\n"
)

_MAX_SHARED_CTX_CHARS = 100_000_000


def evaluate_request(
    project_root: Path | str,
    *,
    scope: str = "",
    stage: str | None = None,
    vertical: str | None = None,
    checklist_mode: ChecklistMode = ChecklistMode.AUTO,
) -> RolePromptRequest:
    return RolePromptRequest(
        role=RoleName.REVIEWER,
        operation=EVALUATE,
        project_root=project_root,
        vertical=vertical,
        stage=stage,
        scope=scope,
        checklist_mode=checklist_mode,
        include_search_altitude=True,
    )


def _project_has_wiki(
    working_dir: str | Path | None = None,
) -> bool:
    project_root = Path(working_dir).expanduser() if working_dir else Path.cwd()
    autors = project_root / ".autors"
    if not autors.exists():
        return False
    from ...wiki.bootstrap import is_initialized_wiki

    return any(is_initialized_wiki(p / "wiki") for p in autors.iterdir() if p.is_dir())


def _load_wiki_curator_skill_if_present(
    working_dir: str | Path | None = None,
) -> str | None:
    """Compatibility helper returning the compact wiki-curator contract."""
    if not _project_has_wiki(working_dir):
        return None
    return (
        "knowledge curator: directly edit durable concepts, principles, facts, "
        "hypotheses, relationships, and conflicts grounded in real evidence; "
        "do not return page operations in the verdict."
    )


def _direct_memory_edit_block(
    skill_store: Any,
    working_dir: str | Path | None,
) -> str:
    from ...skills.role_memory import role_skill_maintenance_block

    skill_block = role_skill_maintenance_block(
        skill_store,
        "reviewer",
        enabled=True,
    )
    project_root = (
        Path(working_dir).expanduser().resolve()
        if working_dir
        else Path.cwd().resolve()
    )
    try:
        from ...wiki.auto_hooks import discover_wikis

        has_wiki = bool(discover_wikis(project_root))
    except Exception:  # noqa: BLE001
        has_wiki = False
    if not has_wiki:
        return skill_block
    from ...wiki.context import render_knowledge_wiki_block

    return skill_block + render_knowledge_wiki_block(
        project_root,
        role="Reviewer",
    )


def _format_academic_paper_review_skill_block(*, include: bool) -> str:
    if not include:
        return ""
    return (
        "## Near-complete paper review\n"
        "Be a skeptical program-committee reviewer: require a clear contribution, "
        "credible comparisons, sufficient evidence/statistics, accurate citations, "
        "readable writing, and clean figures/layout. `done` requires the applicable "
        "final checklist with no critical blocker; do not reward polish without "
        "substantive evidence. Rebuild the manuscript and inspect the generated "
        "artifact: reject undefined citations, bibliography warnings, significant "
        "overfull boxes or clipped pages, and missing PDF title/author metadata. "
        "Render the relevant pages when layout matters.\n\n"
    )


def _verification_directive() -> str:
    """Compact trust-first verification stance."""
    return (
        "Trust consistent shown results. Re-open only for missing, stale, contradictory, "
        "or implausible facts; otherwise judge work and next step. Empty git diff proves "
        "nothing for untracked/outside-repo artifacts: inspect content/output. A resource "
        "violation requires a mutation command attributable to this mission. Identity "
        "drift alone means external change or unknown provenance; do not fail independent "
        "verification.\n\n"
    )


def _prompt_block_stats(blocks: Mapping[str, str]) -> dict[str, dict[str, int]]:
    stats: dict[str, dict[str, int]] = {}
    for name, text in blocks.items():
        rendered = str(text or "")
        byte_count = len(rendered.encode("utf-8"))
        stats[str(name)] = {
            "chars": len(rendered),
            "bytes": byte_count,
            "estimated_tokens": (byte_count + 3) // 4,
        }
    return stats


def _engineer_log_audit_block(
    engineer_log_path: str,
    *,
    engineer_call_id: str = "",
    round_index: int,
    measured: bool,  # noqa: ARG001 — kept for call-site symmetry
    compact: bool = False,
) -> str:
    """Reviewer prompt section for auditing the engineer's execution log."""
    path = (engineer_log_path or "").strip()
    if not path:
        return ""
    call_id = (engineer_call_id or "").strip()
    if compact:
        scope = f"current engineer call id `{call_id}`" if call_id else "the current engineer round"
        return (
            "## Engineer execution log (on-demand)\n"
            f"Log: `{path}`; scope: {scope}. Do not read or grep it routinely. "
            "Previously certified process evidence remains valid. Inspect this log "
            "only for a concrete contradiction, implausible result, missing material "
            "provenance, or suspected shortcut; otherwise spend the review judging "
            "the result and next research decision.\n\n"
        )
    if call_id:
        current_call_rows = format_native_shell_command(
            [
                sys.executable,
                "-I",
                "-m",
                "argus_skill.tools.event_log_query",
                "--log",
                path,
                "--call-id",
                call_id,
            ]
        )
        query_block = (
            f"Current engineer call id: `{call_id}`. Scope every audit command "
            "to this id so prior rounds and this Reviewer's own prompt cannot "
            "pollute the evidence. The query parses top-level JSON fields and "
            "reads rolled logs in chronological order:\n"
            f"    {current_call_rows}\n"
        )
        log_row_description = (
            "The call-scoped raw `agent.io.*` rows record the commands, tool "
            "results, and assistant messages produced by this invocation."
        )
    else:
        query_block = (
            "No exact call id is available. Do not scan the whole project history "
            "unless a concrete concern cannot be resolved from current artifacts.\n"
        )
        log_row_description = (
            "Each `engineer.progress` event's `text` field is what the engineer "
            "actually DID this round — a shell command it ran, a tool call, or a "
            "reasoning beat."
        )
    if measured:
        when_clause = (
            "MEASURED-BENCHMARK mode is active, so this is a RED-FLAG-ONLY check: "
            "you already TRUST the frozen scorer's pasted RESULT line and must NOT "
            "burn the round re-deriving an honest number. Inspect the log ONLY when "
            "the engineer pasted NO RESULT line, the number is implausible / "
            "self-contradictory, or the score jumped suspiciously. Otherwise "
            "skip this section.\n"
        )
    else:
        when_clause = (
            "Decide WHEN to dig: you do not need to read the log every round, but "
            "you SHOULD when the artifact is suspicious, the result is "
            "surprisingly good, a checklist item cannot be independently verified "
            "from the produced files, or the summary is thin on HOW the work was "
            "done. When the engineer's own summary already shows the verification "
            "output and it is internally consistent, a quick log skim is enough.\n"
        )
    return (
        "## Engineer execution-log audit (process correctness — SUPPLEMENTARY)\n"
        "This round's engineer EXECUTION LOG is on disk at:\n"
        f"  {path}\n"
        "It is the per-project event log (NOT in the git work-tree). "
        f"{log_row_description}\n"
        f"{query_block}\n"
        "Result-traceability (does the final artifact match the checklist?) tells "
        "you the OUTCOME is real. This log tells you the PROCESS was honest — the "
        "two are different, and an artifact can match the checklist while the "
        "process may still contradict the claim.\n\n"
        f"{when_clause}\n"
        "Choose any further inspection yourself from the concrete concern and the "
        "actual event fields; do not classify the process by a preset keyword list. "
        "If the process matches the claim, judge the result as usual. This audit "
        "supplements result traceability and never changes frozen measurements.\n\n"
    )


def _format_engineer_shared_context(
    *,
    skill_used: str | None,
    prev_review_summary: str,
) -> str:
    """Render the read-only shared context block injected into reviewer prompts."""
    skill = (skill_used or "").strip()
    prev = (prev_review_summary or "").strip()
    if not skill and not prev:
        return ""
    parts = ["Shared read-only context (do NOT modify; advisory only):"]
    if skill:
        parts.append(f"- skill_used: {skill}")
    if prev:
        if len(prev) > _MAX_SHARED_CTX_CHARS:
            prev = prev[:_MAX_SHARED_CTX_CHARS].rstrip() + "..."
        indented = "\n".join("    " + line for line in prev.splitlines())
        parts.append("- previous_review_summary:\n" + indented)
    return "\n".join(parts) + "\n\n"


def render_reviewer_prompt(
    owner: Any,
    *,
    resumed: bool = False,
    objective: str,
    original_objective: str = "",
    operator_messages: list[str],
    planner_review_instruction: str,
    round_index: int,
    session_id: str | None,
    main_summary: str,
    main_error: str | None,
    round_max: int = 0,
    active_skill_id: str | None = None,
    prev_review_summary: str = "",
    raw_evidence: str = "",
    scope: str = "",
    prior_checkpoint: dict[str, Any] | None = None,
    checkpoint_path: str = "",
    background_context: str = "",
    escalate_hint: str = "",
    engineer_log_path: str = "",
    engineer_call_id: str = "",
    preselected_skill_block: str | None = None,
    working_dir: str | Path | None = None,
    vertical_state_root: str | Path | None = None,
    vertical: str = "",
) -> tuple[str, str]:
    """Render the complete Reviewer prompt as ``(static_preamble, round_delta)``."""
    from ...core.project import resolve_project_root
    from ...core.research_contract import resolve_research_target_level
    from ...skills.vertical_select import _persisted_vertical
    from .registry import resolve_role_prompt

    error_text = main_error or "none"
    # Reviewer receives Skill-library paths and searches independently; no
    # Skill body is selected or injected by the runtime.
    _proot = resolve_project_root(vertical_state_root or working_dir)
    scope_normalized = (scope or "").strip().lower().replace("-", "_")
    _persisted = _persisted_vertical(_proot)
    explicit_vertical = str(vertical or "").strip()
    routed_vertical = explicit_vertical or _persisted
    prompt_context = resolve_role_prompt(
        evaluate_request(
            _proot,
            scope=scope_normalized,
            vertical=routed_vertical,
            # Suppressed only when this project has no pipeline state to read a
            # stage from — not merely because the caller named the vertical.
            #
            # The two used to be the same condition, on the reasoning that a
            # caller passing ``vertical`` explicitly is one running outside a
            # project (``argus_maintenance`` in a bare directory), where asking
            # for a stage checklist is actively harmful: ``current_stage``
            # returns the vertical's first stage as a FALLBACK rather than
            # reporting that it found nothing, and an unresolved stage renders
            # as "Configuration error: this required checklist is not loaded.
            # Do not mark the stage complete" — a blocker manufactured out of a
            # missing file.
            #
            # But the daemon passes ``vertical_override`` for a real campaign
            # that does have pipeline state, so the proxy misfires there and the
            # Reviewer silently loses its stage checklist: for a math project in
            # ``solve`` that is ~2k characters of the acceptance criteria it is
            # supposed to be judging against, while the Engineer's own prompt
            # still carries them. ``_persisted`` is non-None exactly when
            # ``research/PIPELINE_STATE.json`` records a vertical, which is the
            # condition actually being asked about.
            checklist_mode=(
                ChecklistMode.NONE
                if explicit_vertical and not _persisted
                else ChecklistMode.AUTO
            ),
        )
    )
    persisted_prompt_context = (
        resolve_role_prompt(
            evaluate_request(
                _proot,
                vertical=routed_vertical,
                checklist_mode=ChecklistMode.NONE,
            )
        )
        if routed_vertical is not None
        else None
    )
    _requires_engineering_audit = bool(
        persisted_prompt_context is not None
        and persisted_prompt_context.requires_independent_review
    )
    matched_review_skill_block = ""
    if preselected_skill_block is not None:
        if preselected_skill_block.strip():
            matched_review_skill_block = preselected_skill_block.strip() + "\n\n"
    elif owner.skill_store is not None:
        review_libraries = owner.mission.libraries()
        if review_libraries.block:
            matched_review_skill_block = review_libraries.block + "\n\n"
    stage = prompt_context.stage
    _measured = not _requires_engineering_audit and os.environ.get(
        "ARGUS_SKILL_MEASURED_MODE", ""
    ).strip().lower() in ("1", "true", "yes", "on")
    # Vertical-native prompt framing: resolve the active vertical and let it
    # supply the top-of-prompt role banner. The rollback / final-submission
    # framing below applies ONLY to a paper vertical (completion_gate ==
    # final certification; for any other vertical (e.g. speedrun) those blocks are
    # suppressed and the vertical's banner is prepended so the reviewer judges
    # only that vertical's metric instead of paper-pipeline artifacts.
    _final_certification = prompt_context.requires_final_certification
    optimize_banner = prompt_context.role_banner
    if prompt_context.requires_independent_review and not _requires_engineering_audit:
        optimize_banner = ""
    research_target_instruction = ""
    _research_target_level = resolve_research_target_level(_proot)
    if _research_target_level is not None:
        # Two separate things, previously one sentence: `research_target_level`
        # says what finishing the PROJECT means, and the verification profile
        # says what THIS round has to show. Conflating them made every early
        # probe get judged against publication readiness.
        from ...core.verification_policy import policy_line, resolve_policy
        from ...skills.stage_machine import current_stage

        try:
            _stage = current_stage(_proot)
        except Exception:  # noqa: BLE001 - stage is advisory here
            _stage = ""
        _policy = resolve_policy(
            _proot, stage=_stage, vertical=_persisted_vertical(_proot),
            target_level=_research_target_level,
        )
        research_target_instruction = (
            f"Project target `{_research_target_level}` defines project completion, "
            f"not this round's bar. This round: {policy_line(_policy)}. The integrity "
            "floor is identical at every profile. Judge directly and explain in "
            "`reason`. If the direction cannot reach the target, return "
            "`replan_requested`. End with `RESEARCH_RESULT=<JSON>` using the "
            "project research-result contract and only evidence you inspected. "
            "Fields: `result_class`, `correctness_status`, `novelty_status`, "
            "`significance_status`, `statement_fidelity_status`, `evidence`, and "
            "`limitations`. Use `result_class=literature_review` for a bounded "
            "review or survey; literature reviews may use `novelty_status=not_applicable`. "
            "`evidence` and `limitations` are JSON string arrays.\n\n"
        )
    # Live search-altitude facts (NO verdict) so the reviewer can SEE the
    # floor history when judging forward_progress — i.e. distinguish "this
    # round advanced a declared structural line" from "Nth single-knob
    # nibble at a floor that has not moved in N attempts". Empty for
    # verticals that do not surface it.
    search_altitude_block = prompt_context.search_altitude
    # Structured scope only. The planner threads scope=final_submission as
    # a backlog tag all the way here; we no longer sniff the objective
    # prose for "scope: final_submission" markers. Normalize the same way
    # the planner does (lower + hyphen→underscore) so callers that pass
    # "final-submission" still match.
    is_final_submission = scope_normalized == "final_submission"
    if _measured:
        stage_checklist = (
            "## MEASURED-BENCHMARK MODE — TRUST the scorer, judge the IDEA\n"
            "Trusted, FROZEN scorer; the engineer has NO reward signal and does "
            "not control it, so its pasted RESULT (correct + cand_ms/score) is "
            "the honest norm. Your verdict turns on ONE thing: did this round's "
            "MEASURED score beat the engineer's previous best?\n"
            "Do NOT re-run the scorer yourself to re-confirm an honest, "
            "self-consistent number — the engineer self-supervises correctness "
            "by running it every round, so re-measuring burns the round for zero "
            "value. Spend a check ONLY if NO RESULT was pasted or it is "
            "self-contradictory. Otherwise: JUDGMENT + DIRECTION, not "
            "re-measurement.\n"
            "- `continue` if the score improved (lock it in, explore the NEXT "
            "mechanism) OR a clearly-different mechanism is still untried. First "
            "judge: was this mechanism genuinely novel or a re-tweak of a "
            "direction that already lost? `next_action` MUST name a CONCRETE new "
            "direction (a different SOTA/library approach, a hardware technique, "
            "the profiled bottleneck) — push mechanism diversity; never ask to "
            "re-tweak a losing direction or re-paste a shown result.\n"
            "- `blocked` ONLY on a real plateau (several rounds, no improvement, "
            "distinct mechanisms exhausted) or an operator-only blocker. When "
            "only the OPERATOR can unblock (route, budget, which task, GPU, a "
            "yes/no), ALSO set `operator_question`: ONE plain-language question "
            "in the operator's language (Chinese here), answerable in a sentence "
            "— no jargon/JSON/template names.\n"
            "- `done` is rare here — only at/above the known ceiling.\n"
            "Ignore GROUND_TRUTH/gate/marker/status/provenance files (the harness "
            "ignores them) and artifact hygiene — the scorer's number is the only "
            "evidence. A round that MEASURED a real number, even a worse one, made "
            "progress by ruling out a mechanism. This OVERRIDES the generic "
            "demand-evidence / re-run rules below."
        )
    else:
        stage_checklist = prompt_context.stage_checklist

    # Academic peer-review benchmark skill: advisory rubric for reviewing
    # a near-complete manuscript. Gate it on the structured stage/scope
    # signal — final_submission, or the paper-writing stages (review /
    # submission) — instead of keyword-sniffing the objective/evidence
    # for tokens like "main.pdf". `draft` is excluded so mid-production
    # drafting isn't held to final peer-review standards prematurely.
    paper_review_skill_block = _format_academic_paper_review_skill_block(
        include=(
            is_final_submission
            or (_final_certification and stage in {"review", "submission"})
        ),
    )
    wiki_curator_skill_block = ""
    direct_memory_edit_block = ""

    venv_skill_block = (
        "## Dependency rule\n"
        "A missing project package is repairable: tell the Engineer to install "
        "it with `./.venv/bin/pip`; never modify the Argus framework venv."
    )

    # Upstream-evidence defect REPORT. When the reviewer notices that an
    # upstream stage's evidence is missing or unreliable while working a
    # later stage, the correct move is to REPORT it so the Manager can roll
    # the stage back — the reviewer does NOT edit the pipeline state machine
    # itself (stage authority is the Manager's). The instruction lives here
    # (not in the individual checklist items) so it applies uniformly.
    stage_order = prompt_context.stage_order
    stage_idx = stage_order.index(stage) if stage in stage_order else 0
    earlier_stages = ", ".join(stage_order[:stage_idx]) or "(none)"
    rollback_block = (
        "## Upstream defects\n"
        f"Current stage: `{stage}`. Earlier stages: {earlier_stages}.\n"
        "If earlier-stage evidence is broken and this mission cannot repair it "
        "within its own scope, return `replan_requested` (never `continue`) and "
        "name the earliest broken stage and concrete evidence in `reason`; the "
        "Manager owns rollback. "
        "Never edit `research/PIPELINE_STATE.json`."
    )
    operator_text = (
        "\n".join(f"- {line}" for line in operator_messages) if operator_messages else "- none"
    )
    original_text = (original_objective or objective).strip()
    current_text = objective.strip()
    if original_text == current_text:
        objective_block = f"Task objective:\n{current_text}\n\n"
    else:
        objective_block = (
            f"Original operator request:\n{original_text}\n\n"
            f"Current mission objective:\n{current_text}\n\n"
        )
    # The Reviewer is the one role whose verdict closes work, so it is the role
    # that most needs the operator's stated bar in front of it. Without this it
    # judges the mission text, which describes the increment rather than what
    # the operator agreed counts as done.
    from ...core.project_contract import contract_briefing, load_contract_for_cwd

    _contract_block = contract_briefing(
        load_contract_for_cwd(_proot),
        authoritative_objective=original_objective,
    )
    if _contract_block:
        objective_block += _contract_block + "\n\n"
    shared_context_block = _format_engineer_shared_context(
        skill_used=active_skill_id,
        prev_review_summary=prev_review_summary,
    )
    incremental_review_block = ""
    if round_index > 1 and prev_review_summary.strip():
        incremental_review_block = (
            "## Incremental re-review boundary\n"
            "The previous Reviewer verdict below is settled context for this "
            "mission. Inspect the prior `next_action`, the current Engineer "
            "summary, the artifacts changed to satisfy that action, and the "
            "implicated acceptance checks. Do not restart repository research, "
            "reopen accepted findings, or repeat unchanged online/source checks. "
            "Repeat a broader check only when the current delta changed its input, "
            "the previous verdict explicitly left it unresolved, or a named "
            "contradiction/security/authority issue requires it. If the requested "
            "delta now passes and no such contradiction exists, return `done`; do "
            "not invent a new unrelated repair round.\n\n"
        )
    # Prefer direct runtime and verifier evidence over the Engineer's summary
    # when callers provide it. Omit the block when no such evidence exists.
    evidence_block = (
        f"\nRaw verification evidence:\n{raw_evidence.rstrip()}\n" if raw_evidence.strip() else ""
    )
    # Background-subagent context (rendered by the engineer/runner from the
    # live ``.argus_subagents`` registry). Present only when this mission has
    # in-flight subagents. A SUPERVISED subagent advancing on its own is NOT
    # by itself the engineer's forward progress, so we steer next_action away
    # from "poll again" toward independent work (or an explicit cadence
    # yield) without forcing a forward_progress value.
    background_block = ""
    if background_context.strip():
        background_block = (
            f"\n{background_context.strip()}\n\n"
            "Reviewer note on the above: these are SUPERVISED subagents with "
            "their own independent supervisor, so their autonomous progress is "
            "NOT by itself the engineer's forward progress. If the engineer only "
            "re-polled a healthy self-watched subagent this round, steer "
            "`next_action` to advance independent work that does not depend on "
            "it. If nothing else can proceed, return `continue` and state what "
            "evidence the next round should wait for.\n"
        )
    # The shared Markdown checkpoint is the live handoff. ``prior_checkpoint``
    # remains accepted for callers that have not migrated to the file path.
    _ = prior_checkpoint
    _ = checkpoint_path
    checkpoint_block = ""
    # Anti-livelock escalation directive (supplied by the round loop once a
    # mission passes the soft round limit): tell the reviewer to escalate an
    # unresolvable EXTERNAL blocker to `blocked` instead of looping `continue`.
    escalate_block = ""
    if escalate_hint:
        escalate_block = (
            f"## Escalation directive (operator harness — IMPORTANT)\n{escalate_hint}\n\n"
        )
    # Engineer execution-log audit (process correctness). The reviewer runs
    # in the project work-tree and only receives the engineer's final
    # summary, so it cannot otherwise SEE how a result was produced. When the
    # supervisor threads the absolute path to this mission's execution log
    # (``<life_dir>/events.jsonl``), give the reviewer grep recipes to audit
    # PROCESS correctness — not just whether the artifact matches the
    # checklist, but whether the engineer reached it honestly. Empty path
    # (memory backend / tests / unresolvable life_dir) → block omitted, prompt
    # byte-for-byte unchanged (back-compat).
    engineer_log_audit_block = _engineer_log_audit_block(
        engineer_log_path,
        engineer_call_id=engineer_call_id,
        round_index=round_index,
        measured=_measured,
        compact=not bool((main_error or "").strip()),
    )
    # Final-submission missions ask the Reviewer to judge the whole project,
    # rather than treating a manuscript-shaped artifact as completion.
    final_submission_block = ""
    if is_final_submission:
        final_submission_block = (
            "## Final paper review\n"
            "Read the current manuscript, rendered PDF, and claim-critical sources "
            "as an independent venue reviewer. Use `done` only when the research "
            "objective and selected venue bar are genuinely met; otherwise return "
            "`continue` with the few highest-leverage scientific or writing changes. "
            "Do not require or manufacture an assurance memo, reviewer-question "
            "bundle, or other certification packet.\n\n"
        )
    if not _final_certification:
        # non-paper vertical: no paper stages to roll back to, and no
        # final-submission certification — judge only the vertical's metric.
        rollback_block = ""
        final_submission_block = ""
    # Byte-stable static policy; every fresh Reviewer receives it in full.
    shell_contract = native_shell_summary()
    static = (
        optimize_banner
        + research_target_instruction
        + EFFECTIVE_TASK_CONTRACT
        + "\n\n"
        + (shell_contract + "\n\n" if shell_contract else "")
        + MODEL_INTEGRITY_BOUNDARY
        + "\n\n## Reviewer role\n"
        "Judge the objective against real evidence. Bounded work may finish before "
        "the project. Use `done` for verified completion, `continue` for agent-fixable "
        "gaps, and `blocked` only for external dependencies. You are strictly read-only. "
        "Use tools only in proportion to unresolved uncertainty and stop when the "
        "verdict is determined; do not reread equivalent records or repeat verified "
        "checks without a contradiction. Externally derived work needs primary-source "
        "grounding and its project implication. Community implementations alone are "
        "insufficient for claim-critical semantics. Return `replan_requested` when missing "
        "grounding may change the mechanism; do not demand new research for local-only work "
        "or already-grounded work.\n\n"
        + ("" if _requires_engineering_audit else _verification_directive())
        + "## Output protocol\n"
        "Reason and use tools normally, and write your review however is "
        "clearest. End the final message with these lines; only they are read, "
        "and REASON/NEXT_ACTION may run over several lines:\n"
        "STATUS=done|continue|blocked|replan_requested\n"
        "REASON=<the verdict rationale>\n"
        "NEXT_ACTION=<the Engineer instruction; empty for done>\n"
        "OPERATOR_QUESTION=<operator-only blocker, or none>\n"
        "OPERATOR_OPTIONS=<id :: label :: description; ...|none>\n"
        + (
            "RESEARCH_RESULT=<JSON research-result contract>\n"
            if _research_target_level is not None
            else ""
        )
        +
        "FORWARD_PROGRESS=true|false\n"
        "PLAN_SIGNAL=continue|reconsider\n"
        "PLAN_CHALLENGE=<invalidated plan assumption, or none>\n"
        "PLAN_ALTERNATIVE=<better technical route, or none>\n"
        "AUTHORITY_IMPACT=technical|manager_contract|operator\n"
        "FRONTIER_CHANGE=artifact_improved|risk_reduced|uncertainty_reduced|information_gain|bounded_regression|recovered|unchanged_failure|expanding_regression\n"
        "FRONTIER_SUMMARY=<semantic change, not a score>\n"
        "FRONTIER_OBLIGATIONS=resolved::<a; b>|new::<c>|regressed::<d>|remaining::<e>\n"
        "FRONTIER_EVIDENCE=hypothesis::<h>|artifacts::<a>|evidence::<e>|proxies::<p>|uncertainty::<u>\n"
        "NEXT_DECISION_POINT=<next evidence-based decision>\n"
        "REGRESSION_ENVELOPE=none, or cause::<c>|scope::<s>|budget::<b>|recovery::<r>|exit::<e>\n"
        "SESSION_SIGNAL=none, or kind::<repeated_contradiction|reviewer_confusion|quality_degradation>|target::<planner|engineer|reviewer>|detail::<evidence>\n"
        "Judge FORWARD_PROGRESS against the operator objective, separately from "
        "whether this bounded implementation is correctly done.\n"
        "Do not inspect or edit checkpoint/context-packet/handoff bookkeeping; it is "
        "not review evidence. Put the next Engineer instruction only in NEXT_ACTION.\n\n"
        + paper_review_skill_block
        + wiki_curator_skill_block
        + direct_memory_edit_block
        + matched_review_skill_block
        + stage_checklist
        + "\n\n"
        + final_submission_block
        + rollback_block
        + "\n\n"
        + venv_skill_block
        + "\n\n## Handoff policy\n"
        "Decision rules:\n"
        "- `done` requires concrete evidence and exact adherence to material operator constraints.\n"
        "- Default to `continue` whenever the agent's claims are not backed by shown evidence.\n"
        "- Preserve useful negative evidence, but integrity is a hard constraint, not scientific value by itself. "
        "Do not automatically turn an honest result into completion. An agent-designed weak proxy is not evidence for the claimed system; otherwise return `replan_requested`.\n"
        "REASON states the strongest supported finding; NEXT_ACTION names only "
        "missing evidence or the next decision. State surprises once in REASON; do not "
        "write them into project or checkpoint files. "
        "Keep factual outcome, claim boundary, and retry condition distinct: timeout, "
        "incomplete coverage, or one failed mechanism is not impossibility.\n"
        "Use done only for checkable evidence satisfying the current scope; use continue "
        "for an agent-fixable in-scope gap; use replan_requested for a new mission, "
        "replacement route, or boundary change; use blocked only for operator/external "
        "dependencies. A timeout, failed test, oversized benchmark, unavailable optional "
        "backend, or choice among reversible diagnostics is technical: provide a concrete "
        "NEXT_ACTION with AUTHORITY_IMPACT=technical and do NOT ask the operator. Local "
        "work may be done while PLAN_SIGNAL=reconsider.\n"
        "FORWARD_PROGRESS tracks artifact/risk/uncertainty change, not activity or one "
        "proxy. Bounded regressions need all envelope parts. SESSION_SIGNAL needs "
        "explicit cross-turn evidence. For operator authority, write the question and up "
        "to five complete options in the operator's language; stop explicitly stops. "
        "No generic choices. Final-submission "
        "done certifies the project; bounded done "
        "certifies only the mission.\n\n"
        + objective_block
        + "Operator messages:\n"
        f"{operator_text}\n\n"
        "Planner guidance:\n"
        f"{planner_review_instruction or 'none'}\n\n"
    )
    # Per-round DELTA — everything that changes round to round. Fresh
    # Reviewers receive this after the full static rubric every time.
    delta = (
        (_REEVALUATE_HEADER if resumed else "")
        + search_altitude_block
        + f"{checkpoint_block}"
        + f"{escalate_block}"
        + f"{engineer_log_audit_block}"
        + (f"Round: {round_index}/{round_max}\n" if round_max > 0 else f"Round: {round_index}\n")
        + f"Session ID: {session_id or 'none'}\n"
        + f"{shared_context_block}"
        + f"{incremental_review_block}"
        + f"{background_block}"
        + f"Main agent fatal error: {error_text}\n\n"
        + "Main agent last summary:\n"
        + f"{main_summary}\n\n"
        + f"{evidence_block}"
    )
    objective_context = f"{objective_block}{operator_text}\n{planner_review_instruction or 'none'}"
    static = sanitize_model_visible_text(static)
    delta = sanitize_model_visible_text(delta)
    owner._last_prompt_block_stats = _prompt_block_stats(
        {
            "static_total": static,
            "delta_total": delta,
            "stage_checklist": stage_checklist,
            "matched_skill": matched_review_skill_block,
            "direct_memory": direct_memory_edit_block,
            "wiki_curator": wiki_curator_skill_block,
            "paper_review": paper_review_skill_block,
            "research_target": research_target_instruction,
            "final_submission": final_submission_block,
            "objective_context": objective_context,
            "checkpoint": checkpoint_block,
            "execution_log_audit": engineer_log_audit_block,
            "background": background_block,
            "shared_context": shared_context_block + incremental_review_block,
            "main_summary": main_summary,
            "raw_evidence": evidence_block,
        }
    )
    return static, delta


def assemble_reviewer_prompt(static: str, delta: str) -> str:
    """Form the exact prompt sent to a fresh Reviewer session."""
    return sanitize_model_visible_text(static + delta)


__all__ = [
    "EVALUATE",
    "OPERATIONS",
    "assemble_reviewer_prompt",
    "evaluate_request",
    "render_reviewer_prompt",
]
