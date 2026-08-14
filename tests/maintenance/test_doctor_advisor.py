from __future__ import annotations

from types import SimpleNamespace

from argus_skill.maintenance import advisor
from argus_skill.maintenance.models import DoctorFinding, DoctorReport


def _report(detail: str = "codex was not found") -> DoctorReport:
    return DoctorReport(
        schema_version=1,
        target_fingerprint="target",
        generated_at="2026-08-14T00:00:00Z",
        findings=(
            DoctorFinding(
                code="ARGUS-BACKEND-001",
                scope="backend",
                severity="error",
                ok=False,
                status="not_ready",
                detail=detail,
                recommendation="install or authenticate the selected Agent CLI",
            ),
        ),
    )


def test_doctor_advisor_uses_installed_configured_agent(monkeypatch) -> None:
    monkeypatch.setattr(
        advisor,
        "_resolve_advisor",
        lambda _requested: ("claude", "/usr/bin/claude"),
    )
    monkeypatch.setattr(
        "argus_skill.core.knobs.resolve_role_model",
        lambda *_args, **_kwargs: "",
    )
    captured: dict[str, object] = {}

    def probe(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(ok=True, output="Install Claude, then rerun setup.", error="")

    monkeypatch.setattr(
        "argus_skill.core.agent_probe.run_read_only_agent_prompt",
        probe,
    )

    result = advisor.run_doctor_advisor(_report(), requested="auto")

    assert result["status"] == "completed"
    assert result["backend"] == "claude"
    assert captured["model"] == ""
    assert captured["run_label"] == "doctor-advisor"
    assert captured["disable_tools"] is True
    assert "ARGUS-BACKEND-001" in str(captured["prompt"])


def test_doctor_advisor_uses_configured_manager_executable(monkeypatch) -> None:
    monkeypatch.setattr(
        "argus_skill.core.knobs.resolve_role_backend",
        lambda _role: "claude",
    )
    monkeypatch.setattr(
        "argus_skill.core.knobs.resolve_runner_bin_setting",
        lambda _role: "/opt/agents/claude-custom",
    )
    calls: list[tuple[str, str | None]] = []

    def resolve(backend: str, requested: str | None = None):
        calls.append((backend, requested))
        return requested

    monkeypatch.setattr(
        "argus_skill.agent_cli.runner_backend.resolve_runner_bin",
        resolve,
    )

    assert advisor._resolve_advisor("auto") == (
        "claude",
        "/opt/agents/claude-custom",
    )
    assert calls == [("claude", "/opt/agents/claude-custom")]


def test_doctor_advisor_skips_codex_for_automatic_tool_free_analysis(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "argus_skill.core.knobs.resolve_role_backend",
        lambda _role: "codex",
    )
    monkeypatch.setattr(
        "argus_skill.core.knobs.resolve_runner_bin_setting",
        lambda _role: "",
    )
    monkeypatch.setattr(
        "argus_skill.agent_cli.runner_backend.resolve_runner_bin",
        lambda backend, _configured=None: (
            "/usr/bin/pi"
            if backend == "pi"
            else "/usr/bin/codex"
            if backend == "codex"
            else None
        ),
    )

    assert advisor._resolve_advisor("auto") == ("pi", "/usr/bin/pi")


def test_doctor_advisor_redacts_known_secrets(monkeypatch) -> None:
    secret = "sk-example-secret-value-123456"
    monkeypatch.setenv("OPENAI_API_KEY", secret)

    prompt = advisor._advisor_prompt(_report(f"backend rejected {secret}"))

    assert secret not in prompt
    assert "<REDACTED:" in prompt


def test_doctor_advisor_redacts_configured_argus_home(monkeypatch, tmp_path) -> None:
    argus_home = tmp_path / "operator-state"
    monkeypatch.setenv("ARGUS_SKILL_HOME", str(argus_home))

    prompt = advisor._advisor_prompt(_report(f"missing {argus_home / 'repairs/path-memory.json'}"))

    assert str(argus_home) not in prompt
    assert "<ARGUS_SKILL_HOME>/repairs/path-memory.json" in prompt


def test_doctor_advisor_reports_missing_agent(monkeypatch) -> None:
    monkeypatch.setattr(advisor, "_resolve_advisor", lambda _requested: None)

    result = advisor.run_doctor_advisor(_report(), requested="auto")

    assert result["status"] == "unavailable"
    assert "no supported Agent CLI" in result["error"]
