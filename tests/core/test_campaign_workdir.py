from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from argus_skill.core.campaign_workdir import (
    active_campaign_workdir,
    adopt_campaign_workdir,
    normalize_task_workdir,
    resolve_task_workdir,
)


def _git_init(path: Path) -> None:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)


def _pipeline(root: Path, *, stage: str = "baseline") -> None:
    path = root / "research" / "PIPELINE_STATE.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"vertical": "kernel_engineering", "current_stage": stage}),
        encoding="utf-8",
    )


def test_normalize_task_workdir_rejects_escape_and_absolute(tmp_path: Path) -> None:
    assert normalize_task_workdir(".") == ""
    assert normalize_task_workdir("repo/") == "repo"
    with pytest.raises(ValueError, match="project-relative"):
        normalize_task_workdir("../repo")
    with pytest.raises(ValueError, match="project-relative"):
        normalize_task_workdir(str(tmp_path / "repo"))


def test_resolve_task_workdir_stays_inside_workspace(tmp_path: Path) -> None:
    child = tmp_path / "repo"
    child.mkdir()

    assert resolve_task_workdir(tmp_path, "repo") == child.resolve()
    with pytest.raises(ValueError, match="not a directory"):
        resolve_task_workdir(tmp_path, "missing")


def test_adopt_nested_git_root_and_copy_pipeline_state(tmp_path: Path) -> None:
    base = tmp_path / "workspace"
    base.mkdir()
    child = base / "target"
    _git_init(child)
    state = tmp_path / "life"
    _pipeline(base)

    adopted = adopt_campaign_workdir(
        state_root=state,
        base_root=base,
        current_root=base,
        requested="target",
    )

    assert adopted == child.resolve()
    assert active_campaign_workdir(state, base) == child.resolve()
    copied = json.loads(
        (child / "research" / "PIPELINE_STATE.json").read_text(encoding="utf-8")
    )
    assert copied["vertical"] == "kernel_engineering"
    assert copied["current_stage"] == "baseline"


def test_repeated_preplanned_child_path_is_idempotent_after_adoption(
    tmp_path: Path,
) -> None:
    base = tmp_path / "workspace"
    base.mkdir()
    child = base / "target"
    _git_init(child)
    state = tmp_path / "life"

    first = adopt_campaign_workdir(
        state_root=state,
        base_root=base,
        current_root=base,
        requested="target",
    )
    second = adopt_campaign_workdir(
        state_root=state,
        base_root=base,
        current_root=first,
        requested="target",
    )

    assert second == child.resolve()


def test_adoption_requires_nested_git_toplevel(tmp_path: Path) -> None:
    base = tmp_path / "workspace"
    plain = base / "plain"
    plain.mkdir(parents=True)

    with pytest.raises(ValueError, match="nested Git repository"):
        adopt_campaign_workdir(
            state_root=tmp_path / "life",
            base_root=base,
            current_root=base,
            requested="plain",
        )


def test_conflicting_target_pipeline_state_fails_closed(tmp_path: Path) -> None:
    base = tmp_path / "workspace"
    base.mkdir()
    child = base / "target"
    _git_init(child)
    _pipeline(base, stage="baseline")
    _pipeline(child, stage="optimize")

    with pytest.raises(ValueError, match="conflicts on current_stage"):
        adopt_campaign_workdir(
            state_root=tmp_path / "life",
            base_root=base,
            current_root=base,
            requested="target",
        )


def test_web_session_exposes_the_effective_campaign_root(tmp_path: Path) -> None:
    from argus_skill.webapi.project_state import apply_campaign_workdir

    base = tmp_path / "workspace"
    base.mkdir()
    child = base / "target"
    _git_init(child)
    state = tmp_path / "life"
    adopt_campaign_workdir(
        state_root=state,
        base_root=base,
        current_root=base,
        requested="target",
    )

    session = apply_campaign_workdir(
        {"id": "s-one", "workdir": str(base), "cwd": str(state)}, state
    )

    assert session["session_workdir"] == str(base)
    assert session["campaign_workdir"] == str(child.resolve())
    assert session["workdir"] == str(child.resolve())


def test_invalid_persisted_root_is_ignored(tmp_path: Path) -> None:
    base = tmp_path / "workspace"
    base.mkdir()
    state = tmp_path / "life"
    state.mkdir()
    (state / "campaign-workdir.json").write_text(
        json.dumps({"workdir": str(tmp_path / "missing")}),
        encoding="utf-8",
    )

    assert active_campaign_workdir(state, base) is None
