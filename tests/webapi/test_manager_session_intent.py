from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from argus_skill.core.session import SessionMeta, read_session_meta, write_session_meta
from argus_skill.core.transcript import append_turn, read_turns
from argus_skill.life.memory import LifeMemory
from argus_skill.manager import config_intent, front_door
from argus_skill.webapi import manager_bridge, manager_state
from argus_skill.webapi.manager_session_intent import contextualize_operator_turn


def _session(tmp_path: Path, sid: str) -> tuple[Path, Path]:
    life = tmp_path / "projects" / sid
    life.mkdir(parents=True)
    (life / "backlog.jsonl").write_text("", encoding="utf-8")
    workspace = tmp_path / "workspaces" / sid
    workspace.mkdir(parents=True)
    write_session_meta(
        tmp_path,
        SessionMeta(
            id=sid,
            display_name="test",
            cwd=str(life),
            workdir=str(workspace),
            launch_cwd=str(tmp_path),
        ),
    )
    manager_state._STATES.clear()
    return life, workspace


def _forbid_models(monkeypatch) -> None:
    monkeypatch.setattr(
        config_intent,
        "_front_door_classify",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("session fast path must not call the classifier")
        ),
    )
    monkeypatch.setattr(
        front_door,
        "manager_triage",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("session fast path must not call Manager")
        ),
    )


def test_directory_question_reads_session_metadata_without_models(
    tmp_path: Path,
    monkeypatch,
) -> None:
    sid = "s-path-info"
    life, workspace = _session(tmp_path, sid)
    _forbid_models(monkeypatch)

    result = manager_bridge.manager_message(
        sid,
        "那么你的项目目录呢？",
        global_root=tmp_path,
    )

    assert result["kind"] == "chat"
    assert result["fast_path"] == "session_paths"
    assert f"实际执行工作区：`{workspace}`" in result["reply"]
    assert f"内部状态目录：`{life}`" in result["reply"]
    assert "尚未选择独立项目仓库" in result["reply"]
    assert LifeMemory.open(life).backlog.all() == []
    assert [turn["role"] for turn in read_turns(life)] == ["operator", "argus"]


def test_hypothetical_workspace_request_stays_conversational(
    tmp_path: Path,
    monkeypatch,
) -> None:
    sid = "s-workdir-offer"
    life, _workspace = _session(tmp_path, sid)
    parent = tmp_path / "root"
    parent.mkdir()
    _forbid_models(monkeypatch)

    result = manager_bridge.manager_message(
        sid,
        f"如果我要求你在 {parent} 下创建一个文件夹在里面工作呢？",
        global_root=tmp_path,
    )

    assert result["kind"] == "chat"
    assert result["fast_path"] == "workdir_offer"
    assert str(parent) in result["reply"]
    assert list(parent.iterdir()) == []
    assert LifeMemory.open(life).backlog.all() == []


def test_root_without_leading_slash_is_understood_in_hypothetical(
    tmp_path: Path,
    monkeypatch,
) -> None:
    sid = "s-root-spelling"
    life, _workspace = _session(tmp_path, sid)
    _forbid_models(monkeypatch)

    result = manager_bridge.manager_message(
        sid,
        "如果我要求你在root/下面创建一个文件夹在里面工作呢？",
        global_root=tmp_path,
    )

    assert result["kind"] == "chat"
    assert result["parent"] == "/root"
    assert "`/root`" in result["reply"]
    assert LifeMemory.open(life).backlog.all() == []


def test_delegated_followup_creates_folder_and_switches_workdir(
    tmp_path: Path,
    monkeypatch,
) -> None:
    sid = "s-delegated-folder"
    life, old_workspace = _session(tmp_path, sid)
    parent = tmp_path / "root"
    parent.mkdir()
    append_turn(
        life,
        "operator",
        f"如果我要求你在 {parent} 下创建一个文件夹在里面工作呢？",
    )
    append_turn(life, "argus", "可以，请提供文件夹名称。")
    _forbid_models(monkeypatch)

    result = manager_bridge.manager_message(
        sid,
        "你自己创建一个",
        global_root=tmp_path,
    )

    expected = parent / "argus-work-delegated-folder"
    assert result == {
        "reply": (
            "已创建并切换到新的执行工作区：\n\n"
            f"`{expected}`\n\n"
            "后续 Manager、Planner、Engineer 和 Reviewer 都会在这里工作；"
            "Argus 内部状态目录保持不变。"
        ),
        "kind": "control",
        "control": "workdir",
        "changed": True,
        "workdir": str(expected),
        "created": True,
    }
    assert expected.is_dir()
    assert old_workspace.is_dir()
    meta = read_session_meta(tmp_path, sid)
    assert meta is not None and meta.workdir == str(expected)
    assert LifeMemory.open(life).backlog.all() == []


def test_delegated_followup_does_not_reuse_stale_operator_request(
    tmp_path: Path,
    monkeypatch,
) -> None:
    sid = "s-stale-folder-context"
    life, _workspace = _session(tmp_path, sid)
    parent = tmp_path / "root"
    parent.mkdir()
    append_turn(
        life,
        "operator",
        f"如果我要求你在 {parent} 下创建一个文件夹在里面工作呢？",
    )
    append_turn(life, "argus", "可以，请提供文件夹名称。")
    append_turn(life, "operator", "先不用，给我看看状态。")
    append_turn(life, "argus", "当前没有运行任务。")
    seen: list[str] = []

    def classify(_mem, text, chat_state, **_kwargs):
        seen.append(text)
        chat_state["_frontdoor_self_mode"] = "reply"
        chat_state["_frontdoor_fast_reply"] = "请说明要创建什么。"
        return None, "no_dispatch", "simple"

    monkeypatch.setattr(config_intent, "_front_door_classify", classify)
    monkeypatch.setattr(front_door, "manager_triage", lambda *_a, **_k: None)

    result = manager_bridge.manager_message(
        sid,
        "你自己创建一个",
        global_root=tmp_path,
    )

    assert result["kind"] == "chat"
    assert seen
    assert list(parent.iterdir()) == []


def test_direct_workspace_request_is_one_control_operation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    sid = "s-direct-folder"
    life, _workspace = _session(tmp_path, sid)
    parent = tmp_path / "root"
    parent.mkdir()
    _forbid_models(monkeypatch)

    result = manager_bridge.manager_message(
        sid,
        f"请在 {parent} 下创建一个文件夹并在里面工作，你自己命名",
        global_root=tmp_path,
    )

    assert result["kind"] == "control"
    assert result["control"] == "workdir"
    assert Path(result["workdir"]).parent == parent
    assert LifeMemory.open(life).backlog.all() == []


def test_idle_bounded_daemon_is_stopped_before_workdir_switch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    sid = "s-idle-daemon-folder"
    life, _workspace = _session(tmp_path, sid)
    parent = tmp_path / "root"
    parent.mkdir()
    _forbid_models(monkeypatch)
    state = {"alive": True, "stops": 0}

    monkeypatch.setattr(
        "argus_skill.daemon.life_worker.read_daemon_status",
        lambda _life: SimpleNamespace(alive=state["alive"]),
    )

    def stop(_life, **_kwargs):
        state["stops"] += 1
        state["alive"] = False
        return 0

    monkeypatch.setattr("argus_skill.daemon.state.stop_daemon", stop)

    result = manager_bridge.manager_message(
        sid,
        f"请在 {parent} 下创建一个文件夹并在里面工作",
        global_root=tmp_path,
    )

    assert result["control"] == "workdir"
    assert result["changed"] is True
    assert state["stops"] == 1
    assert LifeMemory.open(life).backlog.all() == []


def test_workspace_fast_path_failure_never_falls_through_to_team(
    tmp_path: Path,
    monkeypatch,
) -> None:
    sid = "s-folder-error"
    life, _workspace = _session(tmp_path, sid)
    missing = tmp_path / "missing-parent"
    _forbid_models(monkeypatch)

    result = manager_bridge.manager_message(
        sid,
        f"请在 {missing} 下创建一个文件夹并在里面工作",
        global_root=tmp_path,
    )

    assert result["kind"] == "error"
    assert result["control"] == "workdir"
    assert "没有派发软件任务" in result["reply"]
    assert LifeMemory.open(life).backlog.all() == []


def test_contextual_turn_is_supplied_to_classification_and_dispatch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    sid = "s-contextual-task"
    life, _workspace = _session(tmp_path, sid)
    append_turn(life, "operator", "请修复解析器的转义错误。")
    append_turn(life, "argus", "我会保留现有 API，并补充回归测试。")
    seen: dict[str, str] = {}

    def classify(_mem, text, chat_state, **_kwargs):
        seen["classify"] = text
        chat_state["_frontdoor_lifetime"] = "bounded"
        return None, None, "complex"

    def dispatch(_mem, body, _state, _root_task_id, _cancelled, _emitter):
        seen["dispatch"] = body
        return SimpleNamespace(id="task-1", title="repair parser", status="pending"), False, None

    monkeypatch.setattr(config_intent, "_front_door_classify", classify)
    monkeypatch.setattr(front_door, "manager_triage", lambda *_a, **_k: None)
    monkeypatch.setattr(manager_bridge, "_dispatch_team_mission", dispatch)

    result = manager_bridge.manager_message(
        sid,
        "那就按刚才说的做",
        global_root=tmp_path,
    )

    assert result["kind"] == "task"
    assert "请修复解析器的转义错误" in seen["classify"]
    assert "[CURRENT OPERATOR MESSAGE]\n那就按刚才说的做" in seen["classify"]
    assert seen["dispatch"] == seen["classify"]


def test_nonreferential_turn_is_not_enriched() -> None:
    prior = [
        {"role": "operator", "text": "old task"},
        {"role": "argus", "text": "old reply"},
    ]

    assert contextualize_operator_turn("创建一个新网站", prior) == "创建一个新网站"
    assert contextualize_operator_turn("itemize the changes", prior) == "itemize the changes"
