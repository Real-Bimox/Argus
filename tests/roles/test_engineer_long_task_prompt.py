from __future__ import annotations

import pytest

from argus_skill.roles.prompts.engineer import build_mission_prompt


@pytest.mark.parametrize("include_static", [True, False])
def test_long_task_rule_requires_argus_durable_receipt(include_static: bool) -> None:
    prompt = build_mission_prompt(
        task="Run a long evaluation.",
        skill_text="",
        next_action=None,
        include_static=include_static,
    )

    assert '"${ARGUS_SKILL_PYTHON:-python3}" -m argus_skill.tools.subagent submit' in prompt
    assert "--mode supervised" in prompt
    assert "--timeout <seconds>" in prompt
    assert 'task(mode="background")' in prompt
    assert "session-owned background shell" in prompt
    assert "state=submitted" in prompt
    assert "task_id" in prompt
    assert "run_id" in prompt
    assert "check_with" in prompt


def test_long_task_rule_does_not_use_ambiguous_supervised_subagent_wording() -> None:
    prompt = build_mission_prompt(
        task="Run a long evaluation.",
        skill_text="",
        next_action=None,
    )

    assert "launch a supervised subagent" not in prompt
