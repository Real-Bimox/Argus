from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

from argus_skill.core.operator_decision import build_operator_decision
from argus_skill.daemon.state import read_continuous_state, write_continuous_config
from argus_skill.life.memory import BacklogItem, MemoryBundle
from argus_skill.manager import front_door
from argus_skill.webapi import manager_pending_question


def _blocked_project(tmp_path, sid: str = "s-decision"):
    workspace = tmp_path / "workspace"
    workspace.mkdir(exist_ok=True)
    mem = MemoryBundle.for_cwd(workspace, global_root=tmp_path, fingerprint=sid)
    mem.init()
    item = mem.backlog.add(BacklogItem.new(title="Blocked", objective="Do work", item_id="item"))
    card = build_operator_decision(
        item_id=item.id,
        title=item.title,
        reason="Provider access is missing.",
        question="Use the fallback?",
        recommendation="Use the local fallback.",
    )
    mem.backlog.update(
        item.id,
        status="paused_operator",
        pending_question="Use the fallback?",
        operator_decision=card,
    )
    return mem, card


def _bound_blocked_project(tmp_path, sid: str = "s-decision"):
    workspace = tmp_path / "workspace"
    workspace.mkdir(exist_ok=True)
    mem = MemoryBundle.for_cwd(workspace, global_root=tmp_path, fingerprint=sid)
    mem.init()
    write_continuous_config(mem.project_root, enabled=True, objective="standing work")
    campaign = read_continuous_state(mem.project_root)
    item = mem.backlog.add(
        BacklogItem.new(title="Blocked", objective="Do work", item_id="item")
    )
    card = build_operator_decision(
        item_id=item.id,
        title=item.title,
        reason="Provider access is missing.",
        question="Use the fallback?",
        recommendation="Use the local fallback.",
        project_id=sid,
        campaign_generation=campaign.generation,
    )
    mem.backlog.update(
        item.id,
        status="paused_operator",
        pending_question="Use the fallback?",
        operator_decision=card,
    )
    return mem, card


def _manager_accepts_fallback(*_args, **_kwargs) -> str:
    return json.dumps({
        "is_answer": True,
        "resolved": True,
        "decision": "Use the local fallback and retain the acceptance check.",
        "reply": "I delivered the fallback decision to the team.",
    })


def test_stop_option_resolves_item_and_disables_campaign(tmp_path) -> None:
    mem, card = _blocked_project(tmp_path)
    write_continuous_config(mem.project_root, enabled=True, objective="standing work")

    result = manager_pending_question.manager_resolve_operator_decision(
        "s-decision",
        card["id"],
        "stop",
        global_root=tmp_path,
    )

    assert result is not None and result["stopped"] is True
    item = next(row for row in mem.backlog.all() if row.id == "item")
    assert item.status == "aborted"
    assert item.operator_decision["selected_option"] == "stop"
    assert item.operator_decision["resume_requested"] is False
    assert read_continuous_state(mem.project_root).enabled is False
    events = [
        json.loads(line)
        for line in (mem.project_root / "events.jsonl").read_text().splitlines()
    ]
    stopped = [
        event
        for event in events
        if event.get("type") == "life.operator_question.answered"
    ]
    assert stopped and stopped[-1]["stopped"] is True
    assert "event_validation" not in stopped[-1]


def test_recommended_option_routes_text_through_manager(tmp_path, monkeypatch) -> None:
    _mem, card = _blocked_project(tmp_path)
    seen: dict[str, object] = {}

    def answer(sid, item_id, text, **kwargs):
        seen.update(sid=sid, item_id=item_id, text=text, kwargs=kwargs)
        return {"resolved": True, "reply": "continued"}

    monkeypatch.setattr(manager_pending_question, "manager_answer_pending_question", answer)
    result = manager_pending_question.manager_resolve_operator_decision(
        "s-decision",
        card["id"],
        "recommended",
        expected_revision=1,
        global_root=tmp_path,
    )

    assert result == {
        "resolved": True,
        "reply": "continued",
        "decision_id": card["id"],
    }
    assert seen["text"] == "Use the local fallback."
    assert seen["kwargs"]["decision_option"] == "recommended"


def test_repeated_decision_is_idempotent_across_reopened_memory(
    tmp_path,
    monkeypatch,
) -> None:
    mem, card = _bound_blocked_project(tmp_path)
    calls = 0

    def manager_reply(*args, **kwargs):
        nonlocal calls
        calls += 1
        return _manager_accepts_fallback(*args, **kwargs)

    monkeypatch.setattr(front_door, "manager_triage", manager_reply)
    first = manager_pending_question.manager_resolve_operator_decision(
        "s-decision",
        card["id"],
        "recommended",
        expected_revision=1,
        global_root=tmp_path,
    )
    second = manager_pending_question.manager_resolve_operator_decision(
        "s-decision",
        card["id"],
        "recommended",
        expected_revision=1,
        global_root=tmp_path,
    )

    assert first is not None and first["application_status"] == "accepted"
    assert second is not None and second["application_status"] == "already_applied"
    assert first["item"]["id"] == second["item"]["id"]
    assert first["resolution_id"] == second["resolution_id"]
    assert first["resume_requested"] is True
    assert calls == 1
    assert len(mem.backlog.all()) == 2

    stale = manager_pending_question.manager_resolve_operator_decision(
        "s-decision",
        card["id"],
        "custom",
        "Try a different route.",
        expected_revision=1,
        global_root=tmp_path,
    )
    assert stale is not None and stale["application_status"] == "stale"


def test_campaign_generation_change_rejects_stale_decision_before_manager_call(
    tmp_path,
    monkeypatch,
) -> None:
    mem, card = _bound_blocked_project(tmp_path)
    write_continuous_config(
        mem.project_root,
        enabled=True,
        objective="a newer standing objective",
    )
    monkeypatch.setattr(
        front_door,
        "manager_triage",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("stale decision must not call Manager")
        ),
    )

    result = manager_pending_question.manager_resolve_operator_decision(
        "s-decision",
        card["id"],
        "recommended",
        expected_revision=1,
        global_root=tmp_path,
    )

    assert result is not None and result["application_status"] == "stale"
    assert "campaign changed" in result["error"]
    item = next(row for row in mem.backlog.all() if row.id == "item")
    assert item.pending_question == "Use the fallback?"
    assert item.operator_decision["status"] == "pending"


def test_concurrent_same_decision_returns_accepted_and_already_applied(
    tmp_path,
    monkeypatch,
) -> None:
    mem, card = _bound_blocked_project(tmp_path)
    calls = 0

    def manager_reply(*args, **kwargs):
        nonlocal calls
        calls += 1
        return _manager_accepts_fallback(*args, **kwargs)

    monkeypatch.setattr(front_door, "manager_triage", manager_reply)

    def resolve():
        return manager_pending_question.manager_resolve_operator_decision(
            "s-decision",
            card["id"],
            "recommended",
            expected_revision=1,
            global_root=tmp_path,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _index: resolve(), range(2)))

    assert {result["application_status"] for result in results if result} == {
        "accepted",
        "already_applied",
    }
    assert calls == 1
    assert len(mem.backlog.all()) == 2


def test_stop_decision_replay_does_not_advance_campaign_twice(tmp_path) -> None:
    mem, card = _bound_blocked_project(tmp_path)

    first = manager_pending_question.manager_resolve_operator_decision(
        "s-decision",
        card["id"],
        "stop",
        expected_revision=1,
        global_root=tmp_path,
    )
    generation_after_first = read_continuous_state(mem.project_root).generation
    second = manager_pending_question.manager_resolve_operator_decision(
        "s-decision",
        card["id"],
        "stop",
        expected_revision=1,
        global_root=tmp_path,
    )

    assert first is not None and first["application_status"] == "accepted"
    assert second is not None and second["application_status"] == "already_applied"
    assert read_continuous_state(mem.project_root).generation == generation_after_first
