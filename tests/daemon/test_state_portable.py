from __future__ import annotations

import json
from pathlib import Path

from argus_skill.daemon.state import read_continuous_state, write_continuous_config


def test_continuous_config_round_trips_unicode_as_utf8(tmp_path: Path) -> None:
    objective = "自动科研平台 🔬 → α"

    write_continuous_config(tmp_path, enabled=True, objective=objective)

    raw = (tmp_path / "continuous.json").read_bytes()
    assert json.loads(raw.decode("utf-8"))["objective"] == objective
    state = read_continuous_state(tmp_path)
    assert state.enabled is True
    assert state.objective == objective
    assert state.generation == 1
