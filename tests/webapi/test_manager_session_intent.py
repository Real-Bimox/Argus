from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from argus_skill.core.session import SessionMeta, write_session_meta
from argus_skill.core.transcript import append_turn
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


def test_directory_question_reaches_llm_front_door_classifier(
    tmp_path: Path,
    monkeypatch,
) -> None:
    sid = "s-path-info"
    life, _workspace = _session(tmp_path, sid)
    seen: list[str] = []

    def classify(_mem, text, chat_state, **_kwargs):
        seen.append(text)
        chat_state["_frontdoor_self_mode"] = "reply"
        chat_state["_frontdoor_fast_reply"] = "LLM path answer"
        return None, "no_dispatch", "simple"

    monkeypatch.setattr(config_intent, "_front_door_classify", classify)
    monkeypatch.setattr(front_door, "manager_triage", lambda *_a, **_k: None)

    result = manager_bridge.manager_message(
        sid,
        "那么你的项目目录呢？",
        global_root=tmp_path,
    )

    assert result["kind"] == "chat"
    assert result["reply"] == "LLM path answer"
    assert seen == ["那么你的项目目录呢？"]
    assert LifeMemory.open(life).backlog.all() == []


def test_short_turn_is_supplied_to_classification_and_dispatch(
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

    def dispatch(
        _mem,
        body,
        _state,
        _root_task_id,
        _cancelled,
        _emitter,
        **_kwargs,
    ):
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


def test_contextualization_is_bounded_by_turn_length() -> None:
    prior = [
        {"role": "operator", "text": "old task"},
        {"role": "argus", "text": "old reply"},
    ]

    enriched = contextualize_operator_turn("那就列出修改", prior)
    assert "old task" in enriched
    assert "[CURRENT OPERATOR MESSAGE]\n那就列出修改" in enriched

    assert contextualize_operator_turn("itemize the changes", prior) == "itemize the changes"
    long_text = "那" + ("x" * 120)
    assert contextualize_operator_turn(long_text, prior) == long_text
