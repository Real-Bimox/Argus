from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from argus_skill.core.models import RunnerOptions, RunnerResult
from argus_skill.manager.skill_tidy import propagate_after_mission
from argus_skill.skills.layered import LayeredSkillStore
from argus_skill.skills.missions import EngineerMission


@dataclass
class _PromotingBackend:
    shared_root: Path
    calls: list[dict[str, Any]] = field(default_factory=list)

    def run_exec(
        self,
        *,
        prompt: str,
        options: RunnerOptions,
        run_label: str,
        resume_thread_id: str | None = None,
    ) -> RunnerResult:
        self.calls.append({
            "prompt": prompt,
            "options": options,
            "run_label": run_label,
            "resume_thread_id": resume_thread_id,
        })
        destination = self.shared_root / "engineer" / "verified-debugging.md"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            "---\n"
            "name: verified debugging\n"
            "description: Reuse a verified debugging procedure\n"
            "---\n\n"
            "Verify the reduced reproducer before changing the implementation.\n",
            encoding="utf-8",
        )
        return RunnerResult(exit_code=0, agent_messages=["review complete"])


def test_team_learning_promotes_to_profile_and_new_session_discovers_it(
    tmp_path: Path,
) -> None:
    project = tmp_path / "workspace"
    state = tmp_path / "session-state"
    shared = tmp_path / "profile-skills"
    project.mkdir()
    candidate = state / "skills" / "engineer" / "debugging-candidate.md"
    candidate.parent.mkdir(parents=True)
    candidate.write_text(
        "---\n"
        "name: debugging candidate\n"
        "description: Candidate procedure from this project\n"
        "---\n",
        encoding="utf-8",
    )
    backend = _PromotingBackend(shared)
    events: list[dict[str, Any]] = []

    counts = propagate_after_mission(
        project,
        backend,
        project_state_dir=state,
        shared_root=shared,
        mission_objective="Repair the parser and verify the reduced reproducer",
        on_event=events.append,
    )

    promoted_dir = (shared / "engineer").resolve()
    next_session = LayeredSkillStore(
        project_dir=tmp_path / "next-session-skills",
        global_dir=shared,
    )
    assert counts["to_shared"] == 1
    assert candidate.exists()
    assert promoted_dir in EngineerMission(next_session).libraries().native_paths
    assert backend.calls[0]["run_label"] == "team-learning-review"
    assert backend.calls[0]["options"].working_dir == str(shared.resolve())
    assert "only location you may edit" in backend.calls[0]["prompt"]
    assert "Project-specific or still-unverified learning stays" in backend.calls[0]["prompt"]
    assert [event["type"] for event in events] == [
        "team.learning.review.started",
        "team.learning.review.completed",
    ]


def test_failed_team_mission_prompt_requires_verified_or_repeated_root_cause(
    tmp_path: Path,
) -> None:
    project = tmp_path / "workspace"
    state = tmp_path / "session-state"
    shared = tmp_path / "profile-skills"
    project.mkdir()
    state.mkdir()
    backend = _PromotingBackend(shared)
    events: list[dict[str, Any]] = []

    counts = propagate_after_mission(
        project,
        backend,
        project_state_dir=state,
        shared_root=shared,
        mission_objective="Retry a fixed memory threshold",
        mission_success=False,
        mission_result=(
            "status=blocked; the same unsupported swap-free threshold rejected "
            "three otherwise healthy preflights"
        ),
        on_event=events.append,
    )

    prompt = backend.calls[0]["prompt"]
    assert counts["to_shared"] == 1
    assert "Mission verdict: failure" in prompt
    assert "same mechanism/assumption failing repeatedly" in prompt
    assert "single transient, ambiguous, interrupted, or unresolved failure" in prompt
    assert "Reviewer self-evolution belongs in `reviewer/`" in prompt
    assert "Do not make the main Reviewer edit Skills itself" in prompt
    assert events[0]["mission_success"] is False
    assert events[-1]["mission_success"] is False
