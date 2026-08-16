from __future__ import annotations

import json

from argus_skill.life.event_log import JsonlEventSink
from argus_skill.life.memory import LifeMemory
from argus_skill.life.supervisor import LifeSupervisor, LifeSupervisorConfig


class _Runner:
    pass


def test_completion_message_carries_one_structured_delivery_receipt(tmp_path) -> None:
    memory = LifeMemory.open(tmp_path)
    supervisor = LifeSupervisor(
        memory=memory,
        runner=_Runner(),
        sink=JsonlEventSink(None, life_dir=memory.root, verbosity="full"),
        config=LifeSupervisorConfig(continuous=False, open_ended=False),
    )
    delivery = {
        "schema_version": 1,
        "delivery_id": "delivery:task-1:task_completed",
        "kind": "task_completed",
        "item_id": "task-1",
        "title": "Create final report",
        "summary": "Wrote and reviewed the final report.",
        "status": "done",
        "review_status": "done",
        "delivered_at": 1.0,
        "primary_target": {
            "path": "results/final.md",
            "label": "final.md",
            "source": "reviewer_evidence",
            "why": "Reviewed evidence.",
        },
        "targets": [{
            "path": "results/final.md",
            "label": "final.md",
            "source": "reviewer_evidence",
            "why": "Reviewed evidence.",
        }],
    }

    assert supervisor._emit({
        "type": "life.mission.completed",
        "item_id": "task-1",
        "title": "Create final report",
        "success": True,
        "status": "done",
        "summary": "Wrote and reviewed the final report.",
        "outcome": {"review_status": "done"},
        "delivery": delivery,
        "delivery_id": delivery["delivery_id"],
    })

    transcript = [
        json.loads(line)
        for line in (tmp_path / "transcript.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert transcript[-1]["delivery"] == delivery
    assert transcript[-1]["delivery_id"] == delivery["delivery_id"]
    ui_events = [
        json.loads(line)
        for line in (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if '"type":"ui.argus"' in line
    ]
    assert len(ui_events) == 1
    assert ui_events[0]["delivery"] == delivery
