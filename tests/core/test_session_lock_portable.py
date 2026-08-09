from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import ContextManager

import pytest

from argus_skill.core.session import session_lifecycle_lock, session_meta_lock


@pytest.mark.parametrize("lock", [session_meta_lock, session_lifecycle_lock])
def test_session_locks_serialize_threads(
    tmp_path: Path,
    lock: Callable[[Path, str], ContextManager[None]],
) -> None:
    owner_entered = threading.Event()
    release_owner = threading.Event()
    contender_entered = threading.Event()

    def owner() -> None:
        with lock(tmp_path, "s-portable"):
            owner_entered.set()
            release_owner.wait(timeout=5)

    def contender() -> None:
        with lock(tmp_path, "s-portable"):
            contender_entered.set()

    owner_thread = threading.Thread(target=owner)
    contender_thread = threading.Thread(target=contender)
    owner_thread.start()
    assert owner_entered.wait(timeout=2)
    contender_thread.start()
    try:
        assert not contender_entered.wait(timeout=0.1)
    finally:
        release_owner.set()
        owner_thread.join(timeout=2)
        contender_thread.join(timeout=2)

    assert contender_entered.is_set()
