from __future__ import annotations

import json

from argus_skill.core.operator_messages import (
    publish_operator_message,
    render_operator_update,
)
from argus_skill.core.transcript import read_turns


def test_publish_operator_message_is_idempotent_across_transcript_and_event(tmp_path) -> None:
    assert publish_operator_message(
        tmp_path,
        text="Team completed.",
        message_id="team-summary-1",
    )
    assert not publish_operator_message(
        tmp_path,
        text="Team completed.",
        message_id="team-summary-1",
    )

    assert [turn["text"] for turn in read_turns(tmp_path)] == ["Team completed."]
    events = [
        json.loads(line)
        for line in (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [event["message_id"] for event in events if event["type"] == "ui.argus"] == [
        "team-summary-1",
    ]


def test_operator_update_explains_blocker_and_next_action() -> None:
    text = render_operator_update(
        title="run the H100 benchmark",
        status="blocked",
        reason="The H100 runner is unavailable.",
        next_action="Choose whether to wait or use a named H200-only track.",
        user_action_required=True,
    )

    assert text.splitlines()[0] == "Cannot continue yet: run the H100 benchmark."
    assert "Reason: The H100 runner is unavailable." in text
    assert "Your decision:" in text
    assert text.strip() not in {"BLOCKED", "NO-GO", "REVISE"}


def test_operator_update_leads_with_result() -> None:
    assert render_operator_update(
        title="repair the parser",
        status="done",
        reason="18 focused tests passed.",
    ).splitlines() == [
        "Completed: repair the parser.",
        "Reason: 18 focused tests passed.",
    ]
