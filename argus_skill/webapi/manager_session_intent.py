"""Conversation-context helpers for Manager routing.

This module deliberately does not classify operator intent.  The Manager front-door
LLM decides whether a turn is chat, control, configuration, SELF work, or TEAM
work.  The helper below only attaches a small factual transcript excerpt to short
turns so the LLM can resolve pronouns and ellipses itself.
"""
from __future__ import annotations

from typing import Iterable, Mapping

_CJK_CONTEXT_PREFIXES = (
    "那",
    "那么",
    "这个",
    "那个",
    "它",
    "就",
    "继续",
    "按刚才",
    "照刚才",
    "你自己",
    "自己",
)
_EN_CONTEXT_PREFIXES = (
    "then",
    "that",
    "this",
    "it",
    "continue",
    "as above",
    "you choose",
)


def _turn_text(turn: Mapping[str, object]) -> str:
    return " ".join(str(turn.get("text") or "").split()).strip()


def _needs_context(text: str) -> bool:
    lowered = text.casefold()
    if any(lowered.startswith(prefix) for prefix in _CJK_CONTEXT_PREFIXES):
        return True
    return any(
        lowered == prefix or lowered.startswith(prefix + " ")
        for prefix in _EN_CONTEXT_PREFIXES
    )


def contextualize_operator_turn(
    body: str,
    prior_turns: Iterable[Mapping[str, object]],
) -> str:
    """Attach bounded dialogue context to referential short turns."""
    text = " ".join(str(body or "").split()).strip()
    if not text or len(text) > 120 or not _needs_context(text):
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
        "and omitted nouns. Do not infer intent here.]\n"
        + "\n".join(rows)
        + "\n[CURRENT OPERATOR MESSAGE]\n"
        + str(body or "").strip()
    )


__all__ = ["contextualize_operator_turn"]
