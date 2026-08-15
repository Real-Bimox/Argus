"""The clean-launcher boundary must relay why a daemon refused to start.

Bug #40: the helper ran with ``quiet=True``, so every admission refusal in
``spawn_detached_process`` took its ``if not quiet`` branch to nowhere and
exited non-zero having written nothing. The caller found empty stderr and
raised the bare fallback, "clean daemon launcher exited with code 3". A
testbed re-run in a directory whose previous daemon was still alive therefore
started no executor at all, and the mission sat queued with no stated reason.
"""
from __future__ import annotations

import inspect
import io
import subprocess
from types import SimpleNamespace

import argus_skill.daemon._life_worker_admission as admission
import argus_skill.daemon.spawn_helper as spawn_helper

# What ``_busy_message`` actually produces when a live daemon holds the lease:
# an owner line, indented context, then the ways out. Only the first line names
# the pid, so a last-line-only summary throws away the entire diagnosis.
BUSY = (
    "argus-skill: workdir /home/u/proj is already leased by pid 3870690\n"
    "  session: s-7d03352c\n"
    "  project: /home/u/.argus-skill/projects/s-7d03352c\n"
    "  a workdir runs one daemon at a time. Either:\n"
    "    - watch the one already there:  argus --status   (or --follow)\n"
    "    - stop it:                      kill 3870690\n"
    "    - or start this objective in a different directory\n"
)


def _run_clean_launcher(monkeypatch, *, stderr: str, returncode: int) -> str:
    """Drive the real launcher against a canned helper result; return the error."""
    monkeypatch.setattr(
        admission.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(
            returncode=returncode, stderr=stderr, stdout=""
        ),
    )
    config = SimpleNamespace(life_dir=None, project_workdir=None)
    monkeypatch.setattr(admission, "_config_payload", lambda _c: {})
    try:
        admission.spawn_detached_daemon_clean(config, quiet=True)
    except RuntimeError as exc:
        return str(exc)
    raise AssertionError("launcher did not raise")


def test_the_helper_is_not_muted(monkeypatch) -> None:
    """``quiet`` means "no operator is reading this stream". The helper's
    stream is captured and relayed by its caller, so it is exactly the stream
    the operator reads."""
    seen: dict = {}
    monkeypatch.setattr(
        spawn_helper, "config_from_payload", lambda _payload: "config"
    )
    monkeypatch.setattr(
        spawn_helper,
        "spawn_detached_daemon",
        lambda config, *, quiet: seen.update(config=config, quiet=quiet) or 0,
    )
    monkeypatch.setattr(spawn_helper.sys, "stdin", io.StringIO("{}"))

    assert spawn_helper.main() == 0
    assert seen == {"config": "config", "quiet": False}


def test_a_busy_workdir_still_names_the_process_holding_it(monkeypatch) -> None:
    message = _run_clean_launcher(monkeypatch, stderr=BUSY, returncode=3)

    assert "pid 3870690" in message
    assert "s-7d03352c" in message
    assert "kill 3870690" in message
    assert "exited with code" not in message


def test_an_unformatted_crash_still_collapses_to_its_last_line(
    monkeypatch,
) -> None:
    """The last-line rule is right for a traceback and stays for that case."""
    traceback = (
        "Traceback (most recent call last):\n"
        '  File "x.py", line 1, in <module>\n'
        "    boom()\n"
        "ValueError: no backend configured\n"
    )

    message = _run_clean_launcher(monkeypatch, stderr=traceback, returncode=1)

    assert message == "ValueError: no backend configured"


def test_silence_still_reports_the_exit_code(monkeypatch) -> None:
    message = _run_clean_launcher(monkeypatch, stderr="", returncode=3)

    assert message == "clean daemon launcher exited with code 3"


def test_chatter_before_the_refusal_is_dropped(monkeypatch) -> None:
    """Anchor on the LAST framework message, so unrelated preamble on the same
    stream cannot bury the refusal that actually stopped the spawn."""
    message = _run_clean_launcher(
        monkeypatch,
        stderr="warning: unrelated preamble\n" + BUSY,
        returncode=3,
    )

    assert message.startswith("argus-skill: workdir")
    assert "unrelated preamble" not in message


def test_the_helper_result_is_captured_rather_than_inherited() -> None:
    """If the caller ever stopped capturing, unmuting the helper would spray
    the parent's own stderr instead of being relayed."""
    source = inspect.getsource(admission.spawn_detached_daemon_clean)

    assert "capture_output=True" in source


def test_subprocess_is_the_real_module() -> None:
    assert admission.subprocess is subprocess
