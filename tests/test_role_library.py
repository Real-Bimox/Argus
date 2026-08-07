"""Role Agents receive library paths and perform their own discovery."""
from pathlib import Path

from argus_skill.adapters.memory_backend import MemoryBackend
from argus_skill.skills.layered import LayeredSkillStore
from argus_skill.skills.missions import EngineerMission, ReviewerMission
from argus_skill.skills.role_library import role_skill_libraries
from argus_skill.skills.store import SkillStore


def test_role_receives_path_without_matcher_call_or_content(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    root.mkdir()
    (root / "example.md").write_text(
        "---\nname: Example\ndescription: Example guidance.\n---\n\n"
        "# Example\n\nPRIVATE BODY\n",
        encoding="utf-8",
    )
    backend = MemoryBackend()
    store = SkillStore(root)

    result = role_skill_libraries(store, role="engineer")

    assert str(root.resolve()) in result.block
    assert "PRIVATE BODY" not in result.block
    assert "Leave every non-fitting body unopened" in result.block
    assert backend.history == []


def test_layered_roots_are_exposed_in_order(tmp_path: Path) -> None:
    store = LayeredSkillStore(
        project_dir=tmp_path / "project",
        vertical_dir=tmp_path / "vertical",
        global_dir=tmp_path / "global",
    )
    result = role_skill_libraries(store, role="reviewer")
    positions = [result.block.index(str(path)) for path in store.library_roots()]
    assert positions == sorted(positions)


def test_each_role_searches_same_library_independently(tmp_path: Path) -> None:
    store = SkillStore(tmp_path / "skills")
    (store.skills_dir / "engineer").mkdir()
    (store.skills_dir / "reviewer").mkdir()
    engineer = EngineerMission(store).libraries()
    reviewer = ReviewerMission(store).libraries()
    assert engineer.block != ""
    assert reviewer.block != ""
    assert engineer.library_roots == reviewer.library_roots
    assert "OWN: engineer, root" in engineer.block
    assert "REFERENCE only: reviewer" in engineer.block
    assert "OWN: reviewer" in reviewer.block
    assert "REFERENCE only: engineer" in reviewer.block
    assert engineer.native_paths == [
        store.skills_dir.resolve() / "engineer",
        store.skills_dir.resolve(),
    ]
    assert reviewer.native_paths == [store.skills_dir.resolve() / "reviewer"]


def test_role_library_event_exposes_precedence_without_skill_content(
    tmp_path: Path,
) -> None:
    store = SkillStore(tmp_path / "skills")
    (store.skills_dir / "planner").mkdir()
    events: list[dict] = []

    result = role_skill_libraries(store, role="planner", on_event=events.append)

    assert result.own_paths == [store.skills_dir.resolve() / "planner"]
    assert events[0]["precedence"] == "project,vertical,global"
    assert events[0]["discovery"] == "native-or-path-fallback"
    assert "Skill body" not in str(events[0])
