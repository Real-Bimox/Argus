"""Durable, idempotent background messages shown in the operator conversation."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..life.event_log import JsonlEventSink
from .transcript import append_turn


def render_operator_update(
    *,
    title: str,
    status: str,
    reason: str = "",
    next_action: str = "",
    user_action_required: bool = False,
) -> str:
    """Render structured runtime state as a short, plain operator update."""
    subject = str(title or "the current task").strip()
    state = str(status or "").strip().lower()
    why = str(reason or "").strip()
    action = str(next_action or "").strip()
    if state in {"done", "completed", "success"}:
        first = f"Completed: {subject}."
    elif state in {"continue", "running", "in_progress"}:
        first = f"Still working on {subject}."
    elif state in {"blocked", "infra_blocked", "paused_operator"}:
        first = f"Cannot continue yet: {subject}."
    elif state in {"replan_requested", "revise"}:
        first = f"The current route for {subject} needs to change."
    else:
        first = f"Could not complete {subject}."
    lines = [first]
    if why:
        lines.append(f"Reason: {why}")
    if action:
        prefix = "Your decision: " if user_action_required else "Next: "
        lines.append(prefix + action)
    elif state not in {"done", "completed", "success"}:
        lines.append(
            "Your decision is needed before work can continue."
            if user_action_required
            else "Next: Argus will diagnose the failure and choose a safe next step."
        )
    return "\n".join(lines)


def publish_operator_message(
    life_dir: Path | str,
    *,
    text: str,
    message_id: str,
    event_fields: dict[str, Any] | None = None,
) -> bool:
    """Append one Argus transcript turn and matching live event exactly once."""
    if not append_turn(life_dir, "argus", text, message_id=message_id):
        return False
    event = {
        "type": "ui.argus",
        "agent_layer": "manager",
        "message_id": message_id,
        "text": text,
    }
    event.update(event_fields or {})
    JsonlEventSink(None, life_dir=Path(life_dir)).append(event)
    return True


__all__ = ["publish_operator_message", "render_operator_update"]

