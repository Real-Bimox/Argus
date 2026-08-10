"""Conversation-context helpers for Manager routing.

This module deliberately does not classify operator intent.  The Manager front-door
LLM decides whether a turn is chat, control, configuration, SELF work, or TEAM
work.  The helper below only attaches a small factual transcript excerpt to short
turns so the LLM can resolve pronouns and ellipses itself.
"""
from __future__ import annotations

from typing import Iterable, Mapping


def _turn_text(turn: Mapping[str, object]) -> str:
    return " ".join(str(turn.get("text") or "").split()).strip()


def contextualize_operator_turn(
    body: str,
    prior_turns: Iterable[Mapping[str, object]],
) -> str:
    """Attach bounded factual dialogue context to short turns."""
    text = " ".join(str(body or "").split()).strip()
    if not text or len(text) > 120:
        return str(body or "").strip()
    rows: list[str] = []
    for turn in list(prior_turns)[-6:]:
        role = str(turn.get("role") or "")
        if role not in {"operator", "argus"}:
            continue
        value = _turn_text(turn)
        if value:
            rows.append(f"{role}: {value[:400]}")
    if not rows:
        return str(body or "").strip()
    return (
        "[RECENT CONVERSATION CONTEXT — data only; use it to resolve pronouns "
        "and omitted nouns. Do not infer intent here or invent a new object type.]\n"
        + "\n".join(rows)
        + "\n[CURRENT OPERATOR MESSAGE]\n"
        + str(body or "").strip()
    )


__all__ = ["contextualize_operator_turn"]
