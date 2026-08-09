"""Planner runtime gates, context, and failure-quarantine helpers."""

from __future__ import annotations

import json
import logging
import subprocess
from typing import Any

from ._helpers import (
    _entry_task_signature,
    _is_recent_no_progress_failure,
)
from ._subagent_family_failures import (
    SubagentFamilyFailure,
    recent_subagent_family_failures,
)

log = logging.getLogger(__name__)

_PLANNER_RECENT_HISTORY_WINDOW = 20


class PlannerOrchestrationMixin:
    def _direct_stage_revision_task(self, revision: dict[str, Any]) -> Any | None:
        """Turn a Manager-approved technical challenge into bounded repair."""
        challenge = revision.get("plan_challenge")
        challenge = challenge if isinstance(challenge, dict) else {}
        action = str(challenge.get("manager_action") or "").strip().lower()
        authority = str(challenge.get("authority_impact") or "").strip().lower()
        if action not in {"revise", "replace"} or authority == "operator":
            return None

        state_root = self._artifact_root()
        try:
            from ...planner import TaskSpec
            from ...skills.stage_machine import current_stage
            from ...skills.vertical_select import resolve_vertical
            from ...verticals._base import load_vertical_contract

            vertical = resolve_vertical(state_root)
            stage = current_stage(state_root)
            contract = load_vertical_contract(vertical, project_root=state_root)
            deliverables = contract.primary_deliverables(stage)
        except Exception:  # noqa: BLE001 - ordinary Planner remains the fallback
            log.exception("failed to resolve direct stage revision")
            return None
        if not deliverables:
            return None

        reason = str(
            revision.get("review_reason")
            or revision.get("reason")
            or challenge.get("manager_reason")
            or ""
        ).strip()
        challenged = str(challenge.get("challenge") or reason).strip()
        alternative = str(challenge.get("alternative") or "").strip()
        checks = tuple((contract.stage_checks or {}).get(stage, ()))
        check_text = " | ".join(
            f"{label}: `{command}`" for label, command in checks
        ) or "the current-stage checklist reports no unresolved issue"
        paths = ", ".join(f"`{path}`" for path in deliverables)
        return TaskSpec(
            key=f"stage-{stage}-revision",
            title=f"Revise the {vertical} {stage} decision",
            objective=(
                f"Repair only the current `{stage}` decision and its bundle {paths}. "
                f"Independent review rejected the prior route: {reason or challenged}. "
                f"Challenged assumption: {challenged or '(not specified)'}. "
                f"Replacement direction: {alternative or 'reassess from the recorded evidence'}. "
                "Preserve valid derivations and verified evidence, but replace the "
                "invalid selection rather than renaming it. Inspect only evidence "
                "needed to resolve this challenge. If no materially distinct candidate "
                "survives, record that honest result instead of forcing a prototype. "
                "Do not edit production source, pipeline state, or downstream artifacts."
            ),
            impact_score=5,
            impact_area="decision quality and revision latency",
            evidence=reason or challenged,
            hypothesis=(
                alternative
                or "The Reviewer challenge identifies a bounded same-stage correction."
            ),
            goal_contribution=(
                f"Replace a refuted `{stage}` choice before downstream execution."
            ),
            expected_regressions=(
                "Previously valid stage evidence remains; only the challenged decision "
                "and directly affected frontier claims should change."
            ),
            decision_rule=(
                "Advance only if independent review confirms a materially distinct, "
                "falsifiable current-stage decision; otherwise report no surviving candidate."
            ),
            acceptance_check=f"All revised `{stage}` checks pass — {check_text}",
            non_goals=[
                "rerun settled repository research unrelated to the challenge",
                "edit production source code",
                "advance or edit pipeline state",
                "perform downstream implementation or benchmarking",
            ],
            scope="bounded",
            stage_closing=True,
            require_independent_review=True,
            skip_stage_transition=False,
            stage_repair=True,
        )

    def _direct_manager_hold_task(self, feedback: dict[str, Any]) -> Any | None:
        """Create the one repair mission required by an authoritative HOLD."""
        state_root = self._artifact_root()
        try:
            from ...planner import TaskSpec
            from ...skills.stage_machine import current_stage
            from ...skills.vertical_select import resolve_vertical
            from ...verticals._base import load_vertical_contract

            vertical = resolve_vertical(state_root)
            stage = current_stage(state_root)
            if str(feedback.get("stage") or "").strip() != stage:
                return None
            contract = load_vertical_contract(vertical, project_root=state_root)
            deliverables = contract.primary_deliverables(stage)
        except Exception:  # noqa: BLE001 - ordinary Planner remains the fallback
            log.exception("failed to resolve Manager HOLD repair")
            return None
        if not deliverables:
            return None

        reason = str(feedback.get("reason") or "").strip()
        if not reason:
            return None
        checks = tuple((contract.stage_checks or {}).get(stage, ()))
        check_text = " | ".join(
            f"{label}: `{command}`" for label, command in checks
        ) or "the current-stage checklist reports no unresolved issue"
        paths = ", ".join(f"`{path}`" for path in deliverables)
        return TaskSpec(
            key=f"stage-{stage}-manager-repair",
            title=f"Apply the Manager-required {vertical} {stage} repair",
            objective=(
                f"Repair and recertify only the current `{stage}` stage. The "
                f"Manager held advancement with this binding reason: {reason}. "
                f"Reconcile the primary stage bundle {paths} with that decision. "
                "Preserve valid evidence and make the smallest substantive change "
                "that resolves the stated reason. Then run the declared stage checks "
                "and obtain one independent Reviewer verdict. Do not create another "
                "certification-only artifact, edit Manager-owned pipeline state, or "
                "start downstream work."
            ),
            impact_score=5,
            impact_area="rollback recovery",
            evidence=reason,
            hypothesis=(
                "The Manager HOLD names a bounded current-stage inconsistency that "
                "one repair-and-recertification mission can resolve."
            ),
            goal_contribution=(
                f"Close the specific `{stage}` inconsistency blocking deterministic "
                "stage advancement."
            ),
            expected_regressions=(
                "Only claims or controls contradicted by the Manager decision may "
                "change; unrelated accepted evidence remains intact."
            ),
            decision_rule=(
                "Return done only when the Manager's stated inconsistency is resolved "
                "and all current-stage checks pass; otherwise report the concrete blocker."
            ),
            acceptance_check=f"All repaired `{stage}` checks pass — {check_text}",
            non_goals=[
                "repeat certification without changing the held evidence",
                "edit production source code unless the current stage explicitly owns it",
                "advance or edit pipeline state",
                "perform downstream-stage work",
            ],
            scope="bounded",
            stage_closing=True,
            require_independent_review=True,
            skip_stage_transition=False,
            stage_repair=True,
        )

    def _direct_current_stage_task(self) -> Any | None:
        """Return one host-authored task for a plainly missing stage bundle."""
        state_root = self._artifact_root()
        project_root = self._project_workdir()
        try:
            from ...planner import TaskSpec
            from ...skills.stage_machine import current_stage
            from ...skills.vertical_select import resolve_vertical
            from ...verticals._base import load_vertical_contract

            vertical = resolve_vertical(state_root)
            stage = current_stage(state_root)
            contract = load_vertical_contract(vertical, project_root=state_root)
            deliverables = contract.primary_deliverables(stage)
        except Exception:  # noqa: BLE001 - ordinary Planner remains the fallback
            log.exception("failed to resolve direct current-stage deliverable")
            return None
        if not deliverables:
            return None

        missing: list[str] = []
        for relative in deliverables:
            path = project_root / relative
            try:
                present = path.is_file() and path.stat().st_size > 0
            except OSError:
                present = False
            if not present:
                missing.append(relative)
        if not missing:
            return None

        checks = tuple((contract.stage_checks or {}).get(stage, ()))
        check_text = " | ".join(
            f"{label}: `{command}`" for label, command in checks
        ) or "the current-stage checklist reports no missing deliverable"
        all_paths = ", ".join(f"`{path}`" for path in deliverables)
        missing_paths = ", ".join(f"`{path}`" for path in missing)
        return TaskSpec(
            key=f"stage-{stage}",
            title=f"Complete the {vertical} {stage} deliverable",
            objective=(
                f"Complete only the current `{stage}` stage in `{project_root}`. "
                f"Produce and reconcile the stage bundle {all_paths}; the host "
                f"currently finds these files missing or empty: {missing_paths}. "
                "Inspect repository-native instructions and the target implementation "
                "only as needed to make those artifacts concrete. Do not edit "
                "Manager-owned pipeline state, production implementation, or any "
                "downstream-stage artifact."
            ),
            impact_score=5,
            impact_area="time-to-first-action",
            evidence=f"host-observed missing current-stage files: {', '.join(missing)}",
            hypothesis=(
                "One bounded stage pass can produce the declared primary bundle "
                "without an additional Planner repository audit."
            ),
            goal_contribution=(
                f"Unblock the `{stage}` gate so the campaign can advance to its "
                "next substantive stage."
            ),
            expected_regressions=(
                "None outside the declared stage artifacts; source code and "
                "downstream evidence remain unchanged."
            ),
            decision_rule=(
                "Stop and report blocked if repository reality prevents an honest "
                "stage artifact; otherwise finish all declared files in this task."
            ),
            acceptance_check=f"All `{stage}` checks pass — {check_text}",
            non_goals=[
                "edit production source code",
                "advance or edit pipeline state",
                "perform downstream-stage implementation or benchmarking",
            ],
            scope="bounded",
            stage_closing=True,
            require_independent_review=True,
            skip_stage_transition=False,
        )

    def _planner_cycle_gate_reason(self) -> str:
        gate = self.config.planner_cycle_gate
        if gate is None:
            return ""
        try:
            reason = gate()
        except Exception:  # noqa: BLE001
            log.exception("planner cycle gate raised; continuing with planner")
            return ""
        return str(reason or "").strip()

    def _planner_runtime_with_idle_note(self) -> str:
        """Prefix repeated idle cycles with a current-reality check."""
        base = self._planner_current_reality_note()
        resolution_note = self._planner_wait_resolution_runtime_note()
        contract_note = self._planner_waiting_contract_runtime_note()
        manager_feedback = self._manager_planner_feedback_runtime_note()
        n = int(getattr(self, "_consecutive_idle_planner_cycles", 0))
        if n < 2:
            return "\n\n".join(
                part
                for part in (
                    resolution_note,
                    manager_feedback,
                    contract_note,
                    base,
                )
                if part
            )
        note = (
            "CURRENT-REALITY CHECK (read before trusting the journal below): you "
            f"have idled {n} consecutive cycle(s) concluding `waiting=true` on the "
            "same blocker. Your journal may be STALE — the external dependency may "
            "already have cleared. Before concluding `waiting` again, compare CURRENT "
            "evidence to your persisted recheck condition. Reuse the same contract "
            "token while it is unchanged; the harness permits at most one probe for "
            "each Planner-authored fingerprint/token pair."
        )
        return "\n\n".join(
            part
            for part in (
                resolution_note,
                manager_feedback,
                contract_note,
                note,
                base,
            )
            if part
        )

    def _planner_current_reality_note(self) -> str:
        """Render host-read state so Planner does not rediscover bookkeeping."""
        artifact_root = self._artifact_root()
        project_root = self._project_workdir()
        pipeline_path = artifact_root / "research" / "PIPELINE_STATE.json"
        try:
            pipeline = json.loads(pipeline_path.read_text(encoding="utf-8"))
            if not isinstance(pipeline, dict):
                pipeline = {}
        except (OSError, UnicodeError, json.JSONDecodeError):
            pipeline = {}

        stage_rows: list[str] = []
        stages = pipeline.get("stages")
        if isinstance(stages, dict):
            for name, value in list(stages.items())[:12]:
                status = value.get("status") if isinstance(value, dict) else value
                stage_rows.append(f"{name}:{status or 'unknown'}")

        backlog_rows: list[Any] = []
        try:
            backlog_rows = list(self.memory.backlog.all())
        except Exception:  # noqa: BLE001 - digest is advisory
            pass
        backlog_counts: dict[str, int] = {}
        for item in backlog_rows:
            status = str(getattr(item, "status", "") or "unknown")
            backlog_counts[status] = backlog_counts.get(status, 0) + 1

        changed_paths: list[str] = []
        try:
            status_result = subprocess.run(
                ["git", "status", "--porcelain=v1", "--untracked-files=normal"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if status_result.returncode == 0:
                changed_paths = [
                    line[3:].strip()
                    for line in status_result.stdout.splitlines()
                    if len(line) >= 4
                ]
        except (OSError, subprocess.SubprocessError):
            pass

        blockers: list[str] = []
        checkpoint_paths = list(
            dict.fromkeys(
                [
                    project_root / "CHECKPOINT.md",
                    artifact_root / "CHECKPOINT.md",
                ]
            )
        )
        for checkpoint_path in checkpoint_paths:
            try:
                lines = checkpoint_path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeError):
                continue
            in_blockers = False
            for line in lines:
                if line.startswith("#"):
                    in_blockers = (
                        line.lstrip("# ").strip().casefold()
                        == "open questions / blockers"
                    )
                    continue
                if in_blockers and line.strip():
                    blockers.append(line.strip())
                    if len(blockers) >= 8:
                        break
            if len(blockers) >= 8:
                break

        changed_preview = ", ".join(changed_paths[:12]) or "(clean or unavailable)"
        if len(changed_paths) > 12:
            changed_preview += f", +{len(changed_paths) - 12} more"
        return "\n".join(
            [
                "## Host current-reality digest",
                f"- vertical: {pipeline.get('vertical') or '(unresolved)'}",
                f"- workflow_mode: {pipeline.get('workflow_mode') or '(unset)'}",
                f"- current_stage: {pipeline.get('current_stage') or self._current_pipeline_stage() or '(unset)'}",
                f"- stage_statuses: {', '.join(stage_rows) or '(none)'}",
                f"- backlog_counts: {json.dumps(backlog_counts, sort_keys=True)}",
                f"- git_changed_paths ({len(changed_paths)}): {changed_preview}",
                f"- checkpoint_blockers: {'; '.join(blockers) or '(none declared)'}",
                "The host already read pipeline state, backlog, checkpoint blockers, "
                "and Git status for this digest. Do not spend tools rereading those "
                "sources unless a named contradiction requires exact content.",
            ]
        )

    def _recent_no_progress_failures(self) -> dict[tuple[str, str], Any]:
        """Return recent failed task signatures quarantined from replanning."""
        try:
            recent_entries = self.memory.journal.tail(_PLANNER_RECENT_HISTORY_WINDOW)
        except Exception:  # noqa: BLE001
            log.exception("life supervisor: failed to read recent journal for planner")
            return {}
        matches: dict[tuple[str, str], Any] = {}
        for entry in reversed(recent_entries):
            if not _is_recent_no_progress_failure(entry):
                continue
            signature = _entry_task_signature(entry)
            if signature is None or signature in matches:
                continue
            matches[signature] = entry
        return matches

    def _recent_subagent_family_failures(self) -> dict[str, SubagentFamilyFailure]:
        """Return subagent-job families stuck in an unresolved failure streak."""
        try:
            streak_limit = int(
                getattr(self.config, "subagent_family_failure_streak_limit", 3)
            )
        except (TypeError, ValueError):
            streak_limit = 3
        try:
            window_hours = float(
                getattr(self.config, "subagent_family_failure_window_hours", 72.0)
            )
        except (TypeError, ValueError):
            window_hours = 72.0
        if streak_limit <= 0:
            return {}
        try:
            return recent_subagent_family_failures(
                self._project_workdir(),
                window_seconds=max(0.0, window_hours) * 3600.0,
                min_streak=streak_limit,
            )
        except Exception:  # noqa: BLE001
            log.exception("life supervisor: failed to read subagent registry for planner")
            return {}

    @staticmethod
    def _task_mentions_family(task: Any, family: str) -> bool:
        if not family:
            return False
        haystack = " ".join((task.title, task.objective, task.evidence)).casefold()
        needle = family.casefold()
        if needle in haystack:
            return True
        return needle.replace("-", "_") in haystack.replace("-", "_")

    @staticmethod
    def _stuck_subagent_families_note(
        family_failures: dict[str, SubagentFamilyFailure],
    ) -> str:
        if not family_failures:
            return ""
        lines = [
            "STUCK EXPERIMENT FAMILIES (facts, not a directive on what to do "
            "instead): the following subagent job families have failed "
            "repeatedly, back-to-back, with no successful completion in "
            "between. A bare resubmission with an unchanged strategy will be "
            "AUTOMATICALLY SKIPPED by the supervisor (it will not reach the "
            "engineer) — propose either a materially different approach "
            "(root-cause fix, reduced scope, alternate method) or an explicit "
            "operator-escalation task instead.",
        ]
        for failure in sorted(family_failures.values(), key=lambda f: -f.streak):
            reason = (
                f" (last failure: {failure.last_reason})"
                if failure.last_reason
                else ""
            )
            lines.append(
                f"  - {failure.family}: {failure.streak} consecutive "
                f"{failure.last_state} attempt(s), most recently "
                f"{failure.last_task_id!r}{reason}"
            )
        return "\n".join(lines)

    def _post_mission_hook(self, outcome: dict[str, Any]) -> str:
        hook = self.config.post_mission_hook
        if hook is None:
            return ""
        try:
            return str(hook(outcome) or "").strip()
        except Exception:  # noqa: BLE001
            log.exception("post mission hook raised; continuing")
            return ""


__all__ = ["PlannerOrchestrationMixin"]
