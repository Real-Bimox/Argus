"""Engineer prompt operations and structured context requests."""

from __future__ import annotations

import re
from pathlib import Path

from ...core.model_visible_text import sanitize_model_visible_text
from ..task_contract import (
    EFFECTIVE_TASK_CONTRACT,
    native_shell_contract,
    native_shell_summary,
)
from .types import RoleName, RolePromptRequest

MISSION = "mission"
OPERATIONS = frozenset({MISSION})
_MANAGER_GROUNDING_HEADER = "\n\n## Manager project grounding (advisory evidence)\n"

_POSIX_LONG_EXPERIMENT_RULE = (
    "For commands over two minutes, submit through Argus's durable runner: "
    "`\"${ARGUS_SKILL_PYTHON:-python3}\" -m "
    "argus_skill.tools.subagent submit --task-id <id> --mode direct "
    "--timeout <seconds> --command '<command>'`; use `--mode supervised` only for "
    "semantic monitoring. Never use `task(mode=\"background\")` or session-owned "
    "background shells. Require receipt fields `state=submitted`, `task_id`, `run_id`, "
    "`check_with`; persist them only when a later round must observe the run. On "
    "`state=discussing`, use its exact `reply_with`. Yield; do not poll in the foreground."
)
_PERFORMANCE_DIAGNOSTIC_TASK = re.compile(
    r"\b(?:throughput|latency|performance|bottleneck|profil(?:e|ing|er)?|"
    r"resource|cpu|gpu|scal(?:e|ing|ability)|benchmark)\b|"
    r"吞吐|性能|瓶颈|延迟|剖析",
    re.IGNORECASE,
)


def _performance_diagnostic_section(task: str) -> str:
    if not _PERFORMANCE_DIAGNOSTIC_TASK.search(task):
        return ""
    return (
        "## Performance diagnosis\n"
        "An end-to-end threshold miss only shows that this run missed its target. Before "
        "claiming a root cause, dominant/bottleneck stage, or replacement "
        "architecture, inspect the code hot path and live resource/wait state, then "
        "obtain phase timing/profiling or a controlled A/B that explains a material "
        "share of elapsed time. Otherwise say that the cause is still unclear, "
        "continue the diagnosis, and do not promote the hypothesis into a Skill."
    )

_WINDOWS_LONG_EXPERIMENT_RULE = (
    "For commands expected to run over two minutes on native Windows, use "
    "Windows PowerShell 5.1 syntax to submit through Argus's durable runner: "
    "`& '.\\.venv\\Scripts\\python.exe' -m argus_skill.tools.subagent submit "
    "--task-id '<id>' --mode direct --timeout '<seconds>' --command '<command>'`. "
    "Use `--mode supervised` only when an experiment needs semantic monitoring. "
    "Never use the provider's native `task(mode=\"background\")` tool or a "
    "session-owned background shell for durable work. Before handoff, require a "
    "JSON receipt with `state=submitted`, `task_id`, `run_id`, and `check_with`; "
    "record those in CHECKPOINT.md only when another round must observe the run. "
    "For supervised runs, if status returns `state=discussing`, read the concern "
    "and answer through its exact `reply_with` command before relaunching. Then "
    "yield or do independent work; do not poll in the foreground."
)


def _long_experiment_rule() -> str:
    return (
        _WINDOWS_LONG_EXPERIMENT_RULE
        if native_shell_contract()
        else _POSIX_LONG_EXPERIMENT_RULE
    )


def append_live_guidance(prompt: str, guidance: list[str]) -> str:
    if not guidance:
        return sanitize_model_visible_text(prompt)
    return sanitize_model_visible_text(
        prompt
        + "\n\n## LIVE MANAGER / OPERATOR DIRECTIVES — HIGHEST PRIORITY\n"
        + "These directives may stop, narrow, or correct the current mission. "
        + "They do not silently broaden a structured bounded task or cross its "
        + "pipeline stage. If a directive materially replaces the current "
        + "bounded objective, preserve state, update CHECKPOINT.md, and request "
        + "Reviewer/Planner replanning instead of executing the new scope here.\n"
        + "\n".join(f"- {item}" for item in guidance)
    )


def assemble_round_prompt(
    prompt: str,
    *,
    checkpoint_block: str = "",
    background_advisory: str = "",
    external_work_advisory: str = "",
) -> str:
    """Append all dynamic Engineer round fragments in one stable order."""
    tail = [
        block
        for block in (
            checkpoint_block,
            background_advisory,
            external_work_advisory,
        )
        if block
    ]
    if not tail:
        return sanitize_model_visible_text(prompt)
    return sanitize_model_visible_text(prompt + "\n\n" + "\n\n".join(tail))


def _deduplicated_original_request(original_request: str, task: str) -> str:
    original = original_request.strip()
    current = task.strip()
    if not original or original == current:
        return ""
    if (
        _MANAGER_GROUNDING_HEADER in original
        and _MANAGER_GROUNDING_HEADER in current
    ):
        original_base, original_grounding = original.split(
            _MANAGER_GROUNDING_HEADER,
            1,
        )
        _current_base, current_grounding = current.split(
            _MANAGER_GROUNDING_HEADER,
            1,
        )
        if original_grounding.strip() == current_grounding.strip():
            original = original_base.strip()
    return "" if original == current else original


def _post_task_learning_section(
    *,
    require_post_task_learning: bool,
    project_skill_dir: Path | str | None,
) -> str:
    """Render the Engineer's own durable-learning contract.

    The Engineer ends the task with the full execution context, making it the
    right place to retain a reusable procedure. Roles edit the project Skill
    layer directly, so the contract names the destination explicitly.
    """
    if not require_post_task_learning or project_skill_dir is None:
        return ""
    from ...skills.role_memory import role_skill_edit_rules

    rules = role_skill_edit_rules("engineer", project_skill_dir)
    return (
        "## Durable learning\n"
        "You have file and shell tools. After verification, if this task "
        "produced durable procedures that would change how future tasks are "
        "done, create or update the applicable Engineer Skills directly in the "
        "project skill directory before you hand off.\n"
        + rules
        + "\nDo not turn task-specific hypotheses, causal attributions, failed "
        "attempts, or replacement recommendations into Skills unless phase "
        "attribution/profiling or a controlled comparison verified the causal rule. "
        "Keep inconclusive findings out of Skills.\n"
        "If there is no durable reusable procedure, make no Skill edit."
    )


def build_mission_prompt(
    *,
    task: str,
    skill_text: str,
    next_action: str | None,
    original_request: str = "",
    include_static: bool = True,
    role_banner: str = "",
    require_post_task_learning: bool = False,
    project_root: Path | str | None = None,
    project_skill_dir: Path | str | None = None,
) -> str:
    """Build the complete per-round Engineer mission prompt."""
    sections: list[str] = [EFFECTIVE_TASK_CONTRACT]
    shell_contract = native_shell_contract()
    shell_summary = native_shell_summary()
    if shell_summary:
        sections.append(shell_summary)
    delta_sections: list[str] = []
    if role_banner.strip():
        sections.append("## Active vertical role\n" + role_banner.strip())
    if skill_text:
        sections.append(skill_text)
    unique_original_request = _deduplicated_original_request(
        original_request,
        task,
    )
    if unique_original_request:
        sections.append(
            "## Original operator request\n"
            "Higher-priority live operator instructions may update this; "
            "lower-authority guidance may not silently change it.\n\n"
            + unique_original_request
        )
    sections.append("## Current mission task\n" + task)
    diagnostic_block = _performance_diagnostic_section(task)
    if diagnostic_block:
        sections.append(diagnostic_block)
    # The Engineer is the role that can most easily satisfy a task while
    # missing the requirement the task exists to serve — the mission text
    # describes this increment, not what the operator agreed "done" means.
    from ...core.project_contract import contract_briefing, load_contract_for_cwd

    contract_block = contract_briefing(
        load_contract_for_cwd(),
        authoritative_objective=original_request,
    )
    if contract_block:
        sections.append(contract_block)
    if project_root is not None:
        from ...wiki.context import render_knowledge_wiki_block

        knowledge_block = render_knowledge_wiki_block(
            project_root,
            role="Engineer",
        )
        if knowledge_block:
            sections.append(knowledge_block)
    if next_action:
        delta_sections.append(
            "## Reviewer guidance from prior round\n"
            "The previous round was judged incomplete. Address the\n"
            "following before declaring done:\n\n" + next_action
        )
    sections.append(
        "## This turn\n"
        "Own the milestone end to end. Choose and revise intermediate steps without "
        "returning to Planner for each probe or candidate; reach its decision point "
        "or stop on a real blocker. Update CHECKPOINT.md only for another "
        "round's blocker/next action; pure "
        "reading without an artifact or measurement is not progress. Work in the "
        "current directory; unless required, do not write planning/spec/brief "
        "documents, initialize Git, branch/worktree, commit, spawn subagents, or "
        "invoke meta-workflows.\n"
        "Never repeat unchanged checks/reads; batch tools and cap results at 200 "
        "lines. At 18 tool calls, synthesize or checkpoint/yield; never exceed 24.\n"
        "Wiki is context, not a boundary: independently inspect papers, upstream "
        "source, issues, and hardware/API docs when useful. When related attempts "
        "repeatedly fail, prioritize fresh investigation of primary papers, official "
        "implementations, issues, hardware/API behavior, and the performance model "
        "before deciding the next implementation. Record durable findings in the Wiki.\n"
        + _long_experiment_rule()
    )
    learning_block = _post_task_learning_section(
        require_post_task_learning=require_post_task_learning,
        project_skill_dir=project_skill_dir,
    )
    if learning_block:
        sections.append(learning_block)
    sections.append(
        "## Handoff\n"
        "CHECKPOINT.md is the only role-maintained cross-round handoff file; do not create "
        "handoff or evidence packets. Host invokes Reviewer only when required; do not "
        "spawn a Reviewer subagent. End with "
        "`MILESTONE_STATUS=done|continue`, `NEXT_OWNER=reviewer|engineer|operator`, "
        "`OPERATOR_QUESTION=<operator-only question|none>`, "
        "`OPERATOR_OPTIONS=<id :: label :: description; ...|none>`. "
        "Standard review: owner=reviewer, question=none. A real operator decision: "
        "owner=operator; its question parks the task. Give at most five choices."
    )
    static_text = "\n\n".join(sections)
    delta_text = "\n\n".join(delta_sections)
    if include_static:
        return sanitize_model_visible_text(
            static_text + ("\n\n" + delta_text if delta_text else "")
        )
    compact = (
        "## Continuation turn\n"
        "Read the shared CHECKPOINT.md first. Execute its current Next Action "
        "and the Reviewer guidance below. Do not repeat an unchanged failing "
        "command; reduce it to the cheapest decisive diagnostic. The original "
        "task, active vertical, and repository instructions remain binding.\n"
        + _long_experiment_rule()
        + "\n\n"
        "## Handoff\n"
        "Use only CHECKPOINT.md across rounds. End with summary, check, "
        "`MILESTONE_STATUS=done|continue` and `NEXT_OWNER=reviewer|engineer|operator`. End with "
        "`OPERATOR_QUESTION=<operator-only question|none>` and "
        "`OPERATOR_OPTIONS=<id :: label :: description; ...|none>`. Standard review uses "
        "owner=reviewer and question=none; only a real operator decision parks the task. "
        "Give brief updates only at meaningful transitions."
    )
    if diagnostic_block:
        compact = diagnostic_block + "\n\n" + compact
    if shell_contract:
        compact = shell_contract + "\n\n" + compact
    if learning_block:
        compact += "\n\n" + learning_block
    return sanitize_model_visible_text(
        compact + ("\n\n" + delta_text if delta_text else "")
    )


def mission_request(
    project_root: Path | str,
    *,
    vertical: str | None = None,
) -> RolePromptRequest:
    return RolePromptRequest(
        role=RoleName.ENGINEER,
        operation=MISSION,
        project_root=project_root,
        vertical=vertical,
    )


__all__ = [
    "MISSION",
    "OPERATIONS",
    "append_live_guidance",
    "assemble_round_prompt",
    "build_mission_prompt",
    "mission_request",
]
