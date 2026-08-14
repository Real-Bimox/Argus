from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _section(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[1].split(end, 1)[0]


def test_readme_has_distinct_platform_install_contracts() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    windows = _section(text, "### Windows 10/11", "### macOS")
    macos = _section(text, "### macOS", "### Linux")
    linux = _section(text, "### Linux", "### Agent-assisted installation")

    assert "pip install --upgrade" in windows
    assert "py -m pip install --upgrade" in windows
    assert "--force-reinstall" in windows
    assert "py -3.11" not in windows
    assert "-m venv" not in windows
    assert "argus --setup" in windows
    assert "uv tool install" in macos
    assert "uv venv" not in macos
    assert "python3 -m venv .venv" in linux
    assert ".venv/bin/argus --setup" in linux


def test_chinese_readme_matches_platform_install_contracts() -> None:
    text = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
    windows = _section(text, "### Windows 10/11", "### macOS")
    macos = _section(text, "### macOS", "### Linux")
    linux = _section(text, "### Linux", "### Agent 一键接入")

    assert "pip install --upgrade" in windows
    assert "py -m pip install --upgrade" in windows
    assert "--force-reinstall" in windows
    assert "py -3.11" not in windows
    assert "不创建虚拟环境" in windows
    assert "uv tool install" in macos
    assert "python3 -m venv .venv" in linux


def test_agent_install_uses_os_specific_executables() -> None:
    text = (ROOT / "docs" / "agent-install.md").read_text(encoding="utf-8")
    windows = _section(text, "## Windows 10/11", "## macOS")
    macos = _section(text, "## macOS", "## Linux")
    linux = _section(text, "## Linux", "## OpenAI-compatible endpoint")

    assert "pip install --upgrade" in windows
    assert "py -m pip install --upgrade" in windows
    assert "--force-reinstall" in windows
    assert "py -3.11" not in windows
    assert "-m venv" not in windows
    assert "uv tool install" in macos
    assert "uv tool install --force" in macos
    assert ".venv/bin/argus doctor --deep --advisor auto" in linux
    assert "real Agent-turn smoke" in text
