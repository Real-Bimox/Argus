from __future__ import annotations

import pytest

from argus_skill.roles.prompts import engineer


@pytest.mark.parametrize("include_static", [True, False])
def test_long_task_rule_requires_argus_durable_receipt(include_static: bool) -> None:
    prompt = engineer.build_mission_prompt(
        task="Run a long evaluation.",
        skill_text="",
        next_action=None,
        include_static=include_static,
    )

    assert '"${ARGUS_SKILL_PYTHON:-python3}" -m argus_skill.tools.subagent submit' in prompt
    assert "--mode direct" in prompt
    assert "--mode supervised" in prompt
    assert 'task(mode="background")' in prompt
    assert all(field in prompt for field in ("state=submitted", "task_id", "run_id", "check_with"))
    assert "launch a supervised subagent" not in prompt


def test_native_windows_rule_does_not_offer_unsupported_detach(monkeypatch) -> None:
    monkeypatch.setattr(engineer, "native_shell_contract", lambda: "native Windows")

    prompt = engineer.build_mission_prompt(
        task="Run a long evaluation.",
        skill_text="",
        next_action=None,
    )

    assert "Native Windows preview cannot detach Argus subagents" in prompt
    assert '"${ARGUS_SKILL_PYTHON:-python3}"' not in prompt
    assert "Never claim a detached run was submitted" in prompt
