from __future__ import annotations

import json
from pathlib import Path

import pytest

from argus_skill.daemon import state as daemon_state
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


def test_failed_replace_preserves_existing_continuous_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_continuous_config(tmp_path, enabled=True, objective="existing")
    original = (tmp_path / "continuous.json").read_text(encoding="utf-8")
    real_replace = daemon_state.os.replace

    def _boom(src: str, dst: str) -> None:
        if dst.endswith("continuous.json"):
            raise OSError("disk full")
        real_replace(src, dst)

    monkeypatch.setattr(daemon_state.os, "replace", _boom)

    daemon_state.write_continuous_config(tmp_path, enabled=False, objective="new")

    assert (tmp_path / "continuous.json").read_text(encoding="utf-8") == original
    assert list(tmp_path.glob("continuous.json.*.tmp")) == []


def test_windows_continuous_lock_retries_until_acquired(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts: list[int] = []
    sleeps: list[float] = []

    class _FakeMsvcrt:
        LK_NBLCK = 1
        LK_UNLCK = 2

        @staticmethod
        def locking(_fd: int, mode: int, _size: int) -> None:
            if mode == _FakeMsvcrt.LK_UNLCK:
                return
            attempts.append(mode)
            if len(attempts) < 3:
                raise OSError("busy")

    monkeypatch.setattr(daemon_state.os, "name", "nt")
    monkeypatch.setattr(daemon_state, "msvcrt", _FakeMsvcrt)
    monkeypatch.setattr(daemon_state.time, "sleep", sleeps.append)

    with daemon_state._continuous_config_lock(tmp_path):
        pass

    assert len(attempts) == 3
    assert sleeps == [
        daemon_state._WINDOWS_LOCK_POLL_SECONDS,
        daemon_state._WINDOWS_LOCK_POLL_SECONDS,
    ]
