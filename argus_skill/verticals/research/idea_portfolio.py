"""Durable team formation and completion checks for broad paper ideation."""
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

TEAM_ID = "research-idea-portfolio-v1"
TEAM_WIDTH = 12
TEAM_ROOT = Path(".argus") / "teams"
_STATE_PATH = Path("research") / "IDEA_PORTFOLIO.json"
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
_DEBATE_TASKS = (
    "selection-proponent",
    "selection-assassin",
    "selection-meta-review",
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
    route_ids = [task["task_id"] for task in routes]
    proponent_path = f"{artifact_root}/debates/proponent.md"
    assassin_path = f"{artifact_root}/debates/assassin.md"
    meta_path = f"{artifact_root}/debates/meta-review.md"
    debates = [
        {
            "task_id": f"{team_id}-selection-proponent",
            "title": "Build the strongest portfolio selection case",
            "objective": (
                "Read all 12 independent route reports, select the strongest serious "
                f"candidates, and write `{proponent_path}`. Steelman technical depth, "
                "originality, grounding, significance, falsifier, and feasibility "
                "under matching `##` headings."
            ),
            "acceptance_check": f"`{proponent_path}` compares all viable routes.",
            "role": "selection-proponent",
            "owns_paths": [proponent_path],
            "deps": route_ids,
            "target": "selection",
            "priority": 20,
        },
        {
            "task_id": f"{team_id}-selection-assassin",
            "title": "Attack the portfolio independently",
            "objective": (
                "Read all 12 independent route reports as a prior-art and ambition "
                f"assassin. Write `{assassin_path}` with the strongest reduction to "
                "existing work, technical shallowness, confounds, and fatal probes "
                "under matching `##` headings."
            ),
            "acceptance_check": f"`{assassin_path}` attacks each serious finalist.",
            "role": "selection-assassin",
            "owns_paths": [assassin_path],
            "deps": route_ids,
            "target": "selection",
            "priority": 20,
        },
        {
            "task_id": f"{team_id}-selection-meta-review",
            "title": "Adjudicate the adversarial idea debate",
            "objective": (
                "Act as a fresh meta-reviewer. Read the route reports and both debate "
                f"sides, then write `{meta_path}` with an originality verdict, killed "
                "ideas, surviving thesis, unresolved risks, and the first faithful "
                "probe under matching `##` headings."
            ),
            "acceptance_check": (
                f"`{meta_path}` adjudicates proponent and assassin evidence without "
                "collapsing them into one author's simulation."
            ),
            "role": "selection-meta-review",
            "owns_paths": [meta_path],
            "deps": [
                f"{team_id}-selection-proponent",
                f"{team_id}-selection-assassin",
            ],
            "target": "selection",
            "priority": 30,
        },
    ]
    return [*routes, *debates]


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


def _active_portfolio(
    project_root: Path,
) -> tuple[Path, str, str, str] | None:
    try:
        payload = json.loads(
            (project_root / _STATE_PATH).read_text(encoding="utf-8")
        )
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
    if (
        existing
        and all(task.get("state") == "done" for task in existing)
        and str(receipt.get("team_id") or "") == team_id
        and task_board.material_specs_match(root, tasks)
    ):
        _write_state(project_root, {
            "artifact_root": artifact_root,
            "direction_sha256": direction_digest,
            "team_id": team_id,
        })
        return root
    formation.form_team(
        project_root=project_root,
        root=root,
        team_id=team_id,
        mission=(
            "Discover and adversarially select publishable direction "
            f"{direction_digest}."
        ),
        lead="engineer",
        cwd=project_root,
        tasks=tasks,
    )
    pool.update(root, width=TEAM_WIDTH, state="running")
    _write_state(project_root, {
        "artifact_root": artifact_root,
        "direction_sha256": direction_digest,
        "team_id": team_id,
    })
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


def _output_present(project_root: Path, task: dict[str, Any]) -> bool:
    owned = list(task.get("owns_paths") or [])
    if len(owned) != 1:
        return False
    path = project_root / str(owned[0])
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    required = {
        "idea-route": (
            "## Mechanism",
            "## Primary sources",
            "## Closest work",
            "## Kill argument",
            "## Faithful probe",
        ),
        "selection-proponent": (
            "## Technical depth",
            "## Originality",
            "## Grounding",
            "## Significance",
            "## Falsifier",
            "## Feasibility",
        ),
        "selection-assassin": (
            "## Prior-art reduction",
            "## Technical shallowness",
            "## Confounds",
            "## Fatal probes",
        ),
        "selection-meta-review": (
            "## Originality verdict",
            "## Killed ideas",
            "## Surviving thesis",
            "## Unresolved risks",
            "## First faithful probe",
        ),
    }.get(str(task.get("role") or ""), ())
    if not path.is_file() or any(heading not in text for heading in required):
        return False
    return (
        str(task.get("role") or "") != "idea-route"
        or "https://" in text
        or "http://" in text
    )


def idea_portfolio_completion_issues(project_root: Path) -> tuple[str, ...]:
    project_root = Path(project_root).expanduser().resolve()
    if not portfolio_required(project_root):
        return ()
    active = _active_portfolio(project_root)
    if active is None:
        return ("research idea portfolio state is missing or invalid",)
    root, team_id, artifact_root, _direction_digest = active
    tasks = portfolio_tasks(team_id, artifact_root)
    expected = {task["task_id"]: task for task in tasks}
    actual = {
        str(task.get("task_id") or ""): task
        for task in task_board.snapshot(root)
    }
    issues: list[str] = []
    if (
        set(actual) != set(expected)
        or not task_board.material_specs_match(root, tasks)
    ):
        return ("research idea portfolio task board is missing or not canonical",)
    if int(pool.read(root).get("width", 0) or 0) != TEAM_WIDTH:
        issues.append("research idea portfolio did not preserve width 12")

    route_tasks = [
        actual[task_id]
        for task_id in expected
        if task_id not in {f"{team_id}-{name}" for name in _DEBATE_TASKS}
    ]
    debate_tasks = [actual[f"{team_id}-{name}"] for name in _DEBATE_TASKS]
    if any(task.get("state") != "done" for task in route_tasks):
        issues.append("research idea portfolio has incomplete routes")
    if any(task.get("state") != "done" for task in debate_tasks):
        issues.append("research adversarial selection is incomplete")
    route_owners = {str(task.get("owner") or "") for task in route_tasks}
    if "" in route_owners or len(route_owners) != TEAM_WIDTH:
        issues.append("research idea routes lack 12 distinct worker owners")
    debate_owners = {str(task.get("owner") or "") for task in debate_tasks}
    if (
        "" in debate_owners
        or len(debate_owners) != len(debate_tasks)
        or debate_owners & route_owners
    ):
        issues.append("research selection roles lack fresh independent workers")
    if any(not _valid_shard(root, task) for task in actual.values()):
        issues.append("research idea portfolio lacks valid worker result shards")
    if any(not _output_present(project_root, task) for task in actual.values()):
        issues.append("research idea portfolio lacks route or debate artifacts")

    route_finished = [int(task.get("finish_seq") or 0) for task in route_tasks]
    debate_by_role = {
        str(task.get("role") or ""): task for task in debate_tasks
    }
    proponent = debate_by_role.get("selection-proponent", {})
    assassin = debate_by_role.get("selection-assassin", {})
    meta = debate_by_role.get("selection-meta-review", {})
    route_boundary = max(route_finished, default=0.0)
    debate_finished = [
        int(proponent.get("finish_seq") or 0),
        int(assassin.get("finish_seq") or 0),
    ]
    if (
        not route_boundary
        or any(
            not finished
            or not int(task.get("claim_seq") or 0)
            or finished <= int(task.get("claim_seq") or 0)
            for task, finished in zip(route_tasks, route_finished)
        )
        or any(
            not finished
            or int(task.get("claim_seq") or 0) <= route_boundary
            or finished <= int(task.get("claim_seq") or 0)
            for task, finished in zip((proponent, assassin), debate_finished)
        )
        or int(meta.get("claim_seq") or 0) <= max(debate_finished, default=0)
        or int(meta.get("finish_seq") or 0)
        <= int(meta.get("claim_seq") or 0)
    ):
        issues.append("research idea portfolio completion order is invalid")
    meta_finished_ns = int(float(meta.get("finished_ts") or 0) * 1_000_000_000)
    probes = [project_root / "research/SIGNAL_DERISK.json"]
    probes.extend((project_root / "research/ideas").glob("*/EVIDENCE.json"))
    if meta_finished_ns:
        try:
            probe_predates_selection = any(
                probe.is_file() and probe.stat().st_mtime_ns < meta_finished_ns
                for probe in probes
            )
        except OSError:
            probe_predates_selection = True
        if probe_predates_selection:
            issues.append("research signal probe predates adversarial idea selection")
    return tuple(issues)


__all__ = [
    "TEAM_ID",
    "TEAM_ROOT",
    "TEAM_WIDTH",
    "ensure_idea_portfolio",
    "idea_portfolio_completion_issues",
    "portfolio_required",
    "portfolio_tasks",
]
