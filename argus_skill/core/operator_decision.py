"""Small, human-readable operator decision cards.

Cards live on the blocked backlog item, so the question, options, and resolution
share the backlog's existing lock and persistence. IDs are readable item-based
labels; revisions are plain integers.
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Mapping


def _human_reason(reason: str, *, language_hint: str) -> str:
    from .operator_messages import humanize_runtime_reason

    return humanize_runtime_reason(reason, language_hint=language_hint)


def build_operator_decision(
    *,
    item_id: str,
    title: str,
    reason: str,
    question: str,
    recommendation: str = "",
    evidence: Iterable[Mapping[str, Any]] = (),
    project_id: str = "",
) -> dict[str, Any]:
    operator_language_is_chinese = bool(
        re.search(r"[\u3400-\u9fff]", f"{title}\n{question}")
    )
    options: list[dict[str, Any]] = []
    if recommendation.strip():
        options.append({
            "id": "recommended",
            "label": (
                "按建议继续"
                if operator_language_is_chinese
                else "Use the recommended next step"
            ),
            "description": recommendation.strip(),
            "requires_note": False,
        })
    options.extend([
        {
            "id": "custom",
            "label": "给出其他指示" if operator_language_is_chinese else "Give different guidance",
            "description": question.strip(),
            "requires_note": True,
        },
        {
            "id": "stop",
            "label": "保留当前结果并停止" if operator_language_is_chinese else "Stop this campaign",
            "description": (
                "保留当前工作，停止自动继续。"
                if operator_language_is_chinese
                else "Keep the current work and stop automatic continuation."
            ),
            "requires_note": False,
        },
    ])
    card: dict[str, Any] = {
        "id": f"decision-{item_id}",
        "item_id": item_id,
        "revision": 1,
        "status": "pending",
        "title": title.strip() or "Operator decision required",
        "reason": _human_reason(
            reason,
            language_hint=f"{title}\n{question}",
        ),
        "question": question.strip(),
        "evidence": [
            {
                "label": str(row.get("label") or row.get("why") or "Evidence"),
                "path": str(row.get("path") or row.get("ref") or ""),
                "summary": str(row.get("summary") or row.get("why") or ""),
            }
            for row in evidence
            if isinstance(row, Mapping)
        ],
        "options": options,
        "selected_option": "",
        "note": "",
    }
    if project_id.strip():
        card["project_id"] = project_id.strip()
    return card


def selected_decision_text(card: Mapping[str, Any], option_id: str, note: str) -> str:
    option = next(
        (
            row
            for row in card.get("options", [])
            if isinstance(row, Mapping) and str(row.get("id")) == option_id
        ),
        None,
    )
    if option is None:
        raise ValueError("unknown decision option")
    note = note.strip()
    if bool(option.get("requires_note")) and not note:
        raise ValueError("this option requires guidance")
    if option_id == "custom":
        return note
    description = str(option.get("description") or "").strip()
    return f"{description}\n\nOperator note: {note}" if note else description


__all__ = ["build_operator_decision", "selected_decision_text"]
