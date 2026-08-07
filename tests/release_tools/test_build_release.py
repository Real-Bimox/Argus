from __future__ import annotations

import os
from pathlib import Path

from argus_skill.release_tools import build_release


def test_release_subprocesses_use_current_python_bin(monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr(build_release.sys, "executable", "/opt/argus-venv/bin/python")
    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        captured.update(kwargs)
        shim_dir = kwargs["env"]["PATH"].split(os.pathsep)[0]
        shim = Path(shim_dir) / ("python.cmd" if os.name == "nt" else "python")
        captured["python_target"] = (
            shim.read_text(encoding="utf-8")
            if os.name == "nt"
            else str(shim.resolve())
        )

    monkeypatch.setattr(build_release.subprocess, "run", fake_run)

    build_release.run("npm", "run", "build")

    assert captured["argv"] == ("npm", "run", "build")
    assert captured["check"] is True
    assert "/opt/argus-venv/bin/python" in captured["python_target"]
    assert captured["env"]["PYTHONPATH"].split(os.pathsep)[0] == str(build_release.ROOT)
