"""Durable streaming idea pipelines for broad paper research."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from pathlib import Path
from typing import Any

from ...core.research_contract import (
    resolve_research_direction_mode,
    resolve_research_target_level,
)
from ...team import formation, pool, task_board

TEAM_ID = "research-idea-pipeline-v2"
TEAM_WIDTH = 12
TEAM_ROOT = Path(".argus") / "teams"
_STATE_PATH = Path("research") / "IDEA_PORTFOLIO.json"
_SELECTION_PATH = Path("research") / "IDEA_SELECTION.json"
_REVIEW_VERDICTS = frozenset({"qualified", "rejected"})
_PROBE_DECISIONS = frozenset({"advance", "reject", "inconclusive", "skipped"})
_ROUTE_THEMES = (
    ("mechanism", "method mechanisms and algorithmic interventions"),
    ("systems", "systems architecture, runtime, and deployment failures"),
    ("learning-theory", "probability and learning-theoretic limits"),
    ("information-theory", "information-theoretic bounds and measurements"),
    ("control", "control and dynamical-systems mechanisms"),
    ("causal", "causal identification and intervention design"),
    ("game-theory", "game-theoretic incentives and multi-agent effects"),
    ("formal-methods", "formal methods, contracts, and verification limits"),
    ("evaluation", "evaluation and benchmark blind spots"),
    ("data", "data, measurement, and trace-grounded opportunities"),
    ("negative", "impossibility, negative, and boundary results"),
    ("incidents", "cross-domain incidents and unmet practitioner needs"),
)


def portfolio_required(project_root: Path) -> bool:
    target = resolve_research_target_level(project_root)
    direction = resolve_research_direction_mode(project_root)
    return target in {"publishable", "doctoral"} and direction != "locked"


def _route_task(
    team_id: str,
    artifact_root: str,
    route_id: str,
    theme: str,
) -> dict[str, Any]:
    task_id = f"{team_id}-{route_id}"
    output = f"{artifact_root}/routes/{route_id}.md"
    return {
        "task_id": task_id,
        "title": f"Investigate ideation route {route_id}",
        "objective": (
            f"Independently investigate {theme} for the Manager's current paper "
            f"direction. Write `{output}` with a distinct mechanism, primary-source "
            "trail, closest work, non-obvious gap, strongest kill argument, and a "
            "faithful public-benchmark or real-trace probe. Use headings `## Mechanism`, "
            "`## Primary sources`, `## Closest work`, `## Kill argument`, and "
            "`## Faithful probe`; include primary URLs. Preserve a negative result."
        ),
        "acceptance_check": (
            f"`{output}` exists and contains the mechanism, sources, closest work, "
            "kill argument, and faithful probe."
        ),
        "role": "idea-route",
        "owns_paths": [output],
        "target": route_id,
        "priority": 10,
    }


def _review_task(
    route_task: dict[str, Any],
    artifact_root: str,
) -> dict[str, Any]:
    route_id = str(route_task["target"])
    route_output = str(route_task["owns_paths"][0])
    output = f"{artifact_root}/reviews/{route_id}.json"
    return {
        "task_id": f"{route_task['task_id']}-review",
        "title": f"Independently review candidate {route_id}",
        "objective": (
            f"Act as a fresh, hostile research reviewer for `{route_output}`. "
            "Verify its primary sources and nearest prior art with live evidence. "
            "Judge the nontrivial technical core, originality, formal or causal "
            "grounding, field-level significance, falsifiability, and local "
            "feasibility. Do not compare against unfinished routes and do not wait "
            "for the rest of the portfolio. Write exactly one JSON object to "
            f"`{output}` with schema_version=1, route_id, verdict (`qualified` or "
            "`rejected`), summary, technical_depth, originality, "
            "theoretical_grounding, field_significance, local_feasibility, "
            "fatal_concerns (array), and probe (object). A "
            "qualified review's probe object must contain premise, evaluator_identity, "
            "comparison_identity, minimum_signal, and stop_rules. Qualify only when "
            "the route is strong enough to justify an immediate cheap faithful probe."
        ),
        "acceptance_check": (
            f"`{output}` is valid review JSON with a decisive qualified/rejected "
            "verdict and a complete probe contract when qualified."
        ),
        "role": "idea-review",
        "owns_paths": [output],
        "deps": [str(route_task["task_id"])],
        "target": route_id,
        "priority": 5,
    }


def _probe_task(
    route_task: dict[str, Any],
    review_task: dict[str, Any],
    artifact_root: str,
) -> dict[str, Any]:
    route_id = str(route_task["target"])
    review_output = str(review_task["owns_paths"][0])
    probe_root = f"{artifact_root}/probes/{route_id}"
    evidence_path = f"{probe_root}/EVIDENCE.json"
    return {
        "task_id": f"{route_task['task_id']}-probe",
        "title": f"Run the first faithful probe for {route_id}",
        "objective": (
            f"Read `{review_output}`. Own only `{probe_root}/`. If the review verdict "
            "is rejected, do not spend experiment budget: write a skipped evidence "
            f"record to `{evidence_path}`. If qualified, immediately execute the "
            "review's cheapest faithful public-evidence probe without waiting for any "
            "other route. Preserve code, commands, raw outputs, and uncertainty under "
            f"`{probe_root}/`. Write `{evidence_path}` as schema_version=1 research "
            "idea evidence with idea_id, premise_version, premise, execution_status, "
            "failure_class, idea_status, evaluator_identity, comparison_identity, "
            "summary, evidence, and decision (`advance`, `reject`, `inconclusive`, "
            "or `skipped`). Encode `advance` as completed/none/supported; encode "
            "`reject` only as completed/empirical/refuted; encode under-powered or "
            "execution-limited results as inconclusive; encode a rejected-review "
            "short-circuit as blocked/scope_change/untested/skipped. Use advance only "
            "for an independently reviewable result strong enough to enter planning."
        ),
        "acceptance_check": (
            f"`{evidence_path}` is valid research evidence with a machine-readable "
            "decision and links to every probe artifact, or a justified skipped record."
        ),
        "role": "idea-probe",
        "owns_paths": [probe_root],
        "deps": [str(review_task["task_id"])],
        "target": route_id,
        "priority": 0,
    }


def portfolio_tasks(
    team_id: str = TEAM_ID,
    artifact_root: str = "research/ideation",
) -> list[dict[str, Any]]:
    routes = [
        _route_task(
            team_id,
            artifact_root,
            f"route-{index:02d}-{slug}",
            theme,
        )
        for index, (slug, theme) in enumerate(_ROUTE_THEMES, 1)
    ]
    reviews = [_review_task(route, artifact_root) for route in routes]
    probes = [_probe_task(route, review, artifact_root) for route, review in zip(routes, reviews)]
    return [*routes, *reviews, *probes]


def _portfolio_identity(direction: str) -> tuple[str, str, str]:
    normalized = " ".join(str(direction or "").split())
    if not normalized:
        raise ValueError("broad research portfolio requires a direction")
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    key = digest[:12]
    return (
        f"{TEAM_ID}-{key}",
        f"research/ideation/portfolios/{key}",
        digest,
    )


def _write_state(project_root: Path, payload: dict[str, Any]) -> None:
    path = project_root / _STATE_PATH
    previous_digest = ""
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(previous, dict):
            previous_digest = str(previous.get("direction_sha256") or "")
    except (OSError, json.JSONDecodeError):
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(
        f"{path.name}.tmp.{os.getpid()}.{threading.get_ident():x}.{uuid.uuid4().hex[:8]}"
    )
    try:
        tmp.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
    if previous_digest != str(payload.get("direction_sha256") or ""):
        (project_root / _SELECTION_PATH).unlink(missing_ok=True)


def _active_portfolio(
    project_root: Path,
) -> tuple[Path, str, str, str] | None:
    try:
        payload = json.loads((project_root / _STATE_PATH).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    team_id = str(payload.get("team_id") or "")
    artifact_root = str(payload.get("artifact_root") or "")
    digest = str(payload.get("direction_sha256") or "")
    key = digest[:12]
    if (
        team_id != f"{TEAM_ID}-{key}"
        or len(digest) != 64
        or artifact_root != f"research/ideation/portfolios/{key}"
    ):
        return None
    root = (project_root / TEAM_ROOT / team_id).resolve()
    try:
        root.relative_to((project_root / TEAM_ROOT).resolve())
    except ValueError:
        return None
    return root, team_id, artifact_root, digest


def ensure_idea_portfolio(project_root: Path, *, direction: str) -> Path:
    project_root = Path(project_root).expanduser().resolve()
    team_id, artifact_root, direction_digest = _portfolio_identity(direction)
    root = project_root / TEAM_ROOT / team_id
    tasks = portfolio_tasks(team_id, artifact_root)
    existing = task_board.snapshot(root)
    receipt = formation.load_receipt(root)
    canonical = (
        existing
        and str(receipt.get("team_id") or "") == team_id
        and task_board.material_specs_match(root, tasks)
    )
    if canonical:
        _write_state(
            project_root,
            {
                "artifact_root": artifact_root,
                "direction_sha256": direction_digest,
                "team_id": team_id,
            },
        )
        selection = idea_portfolio_selection(project_root)
        if selection is not None:
            _materialize_selection(project_root, root, selection)
            return root
        pool_state = pool.read(root)
        if (
            str(pool_state.get("state") or "") == "running"
            and int(pool_state.get("width", 0) or 0) != TEAM_WIDTH
        ):
            pool.update(root, width=TEAM_WIDTH, state="running")
        return root
    formation.form_team(
        project_root=project_root,
        root=root,
        team_id=team_id,
        mission=(
            "Stream independent idea discovery through review and faithful probes for "
            f"{direction_digest}."
        ),
        lead="engineer",
        cwd=project_root,
        tasks=tasks,
    )
    pool.update(root, width=TEAM_WIDTH, state="running")
    _write_state(
        project_root,
        {
            "artifact_root": artifact_root,
            "direction_sha256": direction_digest,
            "team_id": team_id,
        },
    )
    return root


def _valid_shard(root: Path, task: dict[str, Any]) -> bool:
    raw_path = str(task.get("result_shard") or "").strip()
    if not raw_path:
        return False
    path = Path(raw_path).expanduser().resolve()
    try:
        path.relative_to(root.resolve())
        row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    except (ValueError, OSError, IndexError, json.JSONDecodeError):
        return False
    return bool(
        isinstance(row, dict)
        and row.get("success") is True
        and str(row.get("task_id") or "") == str(task.get("task_id") or "")
        and str(row.get("member_id") or "") == str(task.get("owner") or "")
    )


def _task_output_path(project_root: Path, task: dict[str, Any]) -> Path | None:
    owned = list(task.get("owns_paths") or [])
    if len(owned) != 1:
        return None
    path = project_root / str(owned[0])
    if str(task.get("role") or "") == "idea-probe":
        path /= "EVIDENCE.json"
    return path


def _json_object(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _review_payload(project_root: Path, task: dict[str, Any]) -> dict[str, Any] | None:
    payload = _json_object(_task_output_path(project_root, task))
    target = str(task.get("target") or "")
    if (
        payload is None
        or payload.get("schema_version") != 1
        or str(payload.get("route_id") or "") != target
        or str(payload.get("verdict") or "") not in _REVIEW_VERDICTS
        or not str(payload.get("summary") or "").strip()
        or any(
            not str(payload.get(key) or "").strip()
            for key in (
                "technical_depth",
                "originality",
                "theoretical_grounding",
                "field_significance",
                "local_feasibility",
            )
        )
        or not isinstance(payload.get("fatal_concerns"), list)
    ):
        return None
    if payload["verdict"] == "qualified":
        probe = payload.get("probe")
        required = (
            "premise",
            "evaluator_identity",
            "comparison_identity",
            "minimum_signal",
            "stop_rules",
        )
        if not isinstance(probe, dict) or any(
            not str(probe.get(key) or "").strip() for key in required
        ):
            return None
    return payload


def _probe_payload(project_root: Path, task: dict[str, Any]) -> dict[str, Any] | None:
    payload = _json_object(_task_output_path(project_root, task))
    target = str(task.get("target") or "")
    decision = str((payload or {}).get("decision") or "")
    if (
        payload is None
        or str(payload.get("idea_id") or "") != target
        or decision not in _PROBE_DECISIONS
    ):
        return None
    from .idea_evidence import validate_idea_evidence

    if validate_idea_evidence(payload):
        return None
    execution = str(payload.get("execution_status") or "")
    status = str(payload.get("idea_status") or "")
    if decision == "advance" and not (execution == "completed" and status == "supported"):
        return None
    if decision == "reject" and not (execution == "completed" and status == "refuted"):
        return None
    if decision == "inconclusive" and status not in {"untested", "inconclusive"}:
        return None
    if decision == "skipped" and status != "untested":
        return None
    return payload


def _output_present(project_root: Path, task: dict[str, Any]) -> bool:
    path = _task_output_path(project_root, task)
    if path is None:
        return False
    role = str(task.get("role") or "")
    if role == "idea-review":
        return _review_payload(project_root, task) is not None
    if role == "idea-probe":
        return _probe_payload(project_root, task) is not None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    required = (
        "## Mechanism",
        "## Primary sources",
        "## Closest work",
        "## Kill argument",
        "## Faithful probe",
    )
    if not path.is_file() or any(heading not in text for heading in required):
        return False
    return "https://" in text or "http://" in text


def _selection_from_tasks(
    project_root: Path,
    root: Path,
    team_id: str,
    artifact_root: str,
    direction_digest: str,
    actual: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    candidates: list[tuple[int, float, str, dict[str, Any]]] = []
    for route_spec in portfolio_tasks(team_id, artifact_root):
        if str(route_spec.get("role") or "") != "idea-route":
            continue
        route_id = str(route_spec["task_id"])
        review_id = f"{route_id}-review"
        probe_id = f"{route_id}-probe"
        route = actual.get(route_id, {})
        review = actual.get(review_id, {})
        probe = actual.get(probe_id, {})
        if any(task.get("state") != "done" for task in (route, review, probe)):
            continue
        if any(not _valid_shard(root, task) for task in (route, review, probe)):
            continue
        if any(not _output_present(project_root, task) for task in (route, review, probe)):
            continue
        review_payload = _review_payload(project_root, review)
        probe_payload = _probe_payload(project_root, probe)
        if (
            review_payload is None
            or review_payload.get("verdict") != "qualified"
            or probe_payload is None
            or probe_payload.get("decision") != "advance"
        ):
            continue
        owners = {str(task.get("owner") or "") for task in (route, review, probe)}
        route_seq = int(route.get("finish_seq") or 0)
        review_seq = int(review.get("finish_seq") or 0)
        probe_seq = int(probe.get("finish_seq") or 0)
        if "" in owners or len(owners) != 3 or not (0 < route_seq < review_seq < probe_seq):
            continue
        paths = {
            "route_artifact": _task_output_path(project_root, route),
            "review_artifact": _task_output_path(project_root, review),
            "evidence_artifact": _task_output_path(project_root, probe),
        }
        selection = {
            "schema_version": 1,
            "policy": "greedy_first_qualified",
            "team_id": team_id,
            "direction_sha256": direction_digest,
            "route_id": str(route.get("target") or ""),
            "route_task_id": route_id,
            "review_task_id": review_id,
            "probe_task_id": probe_id,
            "probe_finish_seq": probe_seq,
            "selected_at": float(probe.get("finished_ts") or 0),
            **{
                key: str(path.relative_to(project_root))
                for key, path in paths.items()
                if path is not None
            },
        }
        candidates.append(
            (
                probe_seq,
                float(probe.get("finished_ts") or 0),
                route_id,
                selection,
            )
        )
    return min(candidates, default=None, key=lambda item: item[:3])[3] if candidates else None


def idea_portfolio_selection(project_root: Path) -> dict[str, Any] | None:
    project_root = Path(project_root).expanduser().resolve()
    active = _active_portfolio(project_root)
    if active is None:
        return None
    root, team_id, artifact_root, direction_digest = active
    tasks = portfolio_tasks(team_id, artifact_root)
    if not task_board.material_specs_match(root, tasks):
        return None
    actual = {str(task.get("task_id") or ""): task for task in task_board.snapshot(root)}
    return _selection_from_tasks(
        project_root,
        root,
        team_id,
        artifact_root,
        direction_digest,
        actual,
    )


def _materialize_selection(
    project_root: Path,
    root: Path,
    selection: dict[str, Any],
) -> None:
    path = project_root / _SELECTION_PATH
    current = _json_object(path)
    if current != selection:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(
            f"{path.name}.tmp.{os.getpid()}.{threading.get_ident():x}.{uuid.uuid4().hex[:8]}"
        )
        try:
            tmp.write_text(
                json.dumps(selection, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)
    if str(pool.read(root).get("state") or "") not in {"draining", "dissolved"}:
        pool.update(root, state="draining")


def idea_portfolio_completion_issues(project_root: Path) -> tuple[str, ...]:
    project_root = Path(project_root).expanduser().resolve()
    if not portfolio_required(project_root):
        return ()
    active = _active_portfolio(project_root)
    if active is None:
        return ("research idea portfolio state is missing or invalid",)
    root, team_id, artifact_root, direction_digest = active
    tasks = portfolio_tasks(team_id, artifact_root)
    expected = {task["task_id"]: task for task in tasks}
    actual = {str(task.get("task_id") or ""): task for task in task_board.snapshot(root)}
    issues: list[str] = []
    if set(actual) != set(expected) or not task_board.material_specs_match(root, tasks):
        return ("research idea portfolio task board is missing or not canonical",)
    if int(pool.read(root).get("width", 0) or 0) != TEAM_WIDTH:
        issues.append("research idea portfolio did not preserve width 12")

    selection = _selection_from_tasks(
        project_root,
        root,
        team_id,
        artifact_root,
        direction_digest,
        actual,
    )
    if selection is not None:
        _materialize_selection(project_root, root, selection)
        return tuple(issues)

    advanced = any(
        str(task.get("role") or "") == "idea-probe"
        and (_probe_payload(project_root, task) or {}).get("decision") == "advance"
        for task in actual.values()
    )
    if advanced:
        issues.append("research greedy selection lacks valid route/review/probe provenance")
        return tuple(issues)

    probes = [task for task in actual.values() if str(task.get("role") or "") == "idea-probe"]
    terminal = {"done", "failed", "blocked"}
    if probes and all(str(task.get("state") or "") in terminal for task in probes):
        issues.append(
            "research idea pipeline exhausted without a reviewed probe qualified to advance"
        )
    else:
        issues.append(
            "research idea pipeline has no independently reviewed probe qualified to advance yet"
        )
    return tuple(issues)


__all__ = [
    "TEAM_ID",
    "TEAM_ROOT",
    "TEAM_WIDTH",
    "ensure_idea_portfolio",
    "idea_portfolio_completion_issues",
    "idea_portfolio_selection",
    "portfolio_required",
    "portfolio_tasks",
]
