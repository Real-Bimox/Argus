"""Shared, concurrently-claimable task list for an agent team.

All mutating ops take an exclusive flock on ``.tasks.lock`` and persist
each task as ``tasks/<task_id>.json`` via atomic write. Claiming is a
compare-and-set (state must be ``pending`` and every dep ``done``) so two
teammates can never own the same task.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..core.portable_filename import (
    legacy_hashed_filename_components,
    normalized_logical_identifier,
    portable_filename_component,
)
from . import _store


def _tasks_dir(root: Path) -> Path:
    return Path(root) / "tasks"


def _lock(root: Path) -> Path:
    return Path(root) / ".tasks.lock"


def _task_filename(task_id: str) -> str:
    if not isinstance(task_id, str):
        raise TypeError("task_id must be a string")
    invalid = not task_id or task_id in {".", ".."} or any(c in task_id for c in "/\\\0")
    if invalid:
        raise ValueError(f"invalid task_id for task board path: {task_id!r}")
    component = portable_filename_component(task_id, windows=os.name == "nt")
    return f"{component}.json"


def _path(root: Path, task_id: str) -> Path:
    return _tasks_dir(root) / _task_filename(task_id)


def _legacy_paths(root: Path, task_id: str) -> tuple[Path, ...]:
    directory = _tasks_dir(root)
    return tuple(
        directory / f"{component}.json"
        for component in legacy_hashed_filename_components(task_id)
    )


def _read_task(root: Path, task_id: str) -> dict[str, Any] | None:
    records: list[tuple[int, bool, dict[str, Any]]] = []
    canonical = _path(root, task_id)
    for path in (_path(root, task_id), *_legacy_paths(root, task_id)):
        task = _store.read_json(path, default=None)
        if isinstance(task, dict) and str(task.get("task_id") or "") == task_id:
            try:
                modified = path.stat().st_mtime_ns
            except OSError:
                modified = 0
            records.append((modified, path == canonical, task))
    if not records:
        return None
    return max(records, key=lambda item: item[:2])[2]


def _write_task(root: Path, task_id: str, task: dict[str, Any]) -> None:
    path = _path(root, task_id)
    _store.atomic_write_json(path, task)
    for legacy in _legacy_paths(root, task_id):
        legacy_task = _store.read_json(legacy, default=None)
        if (
            legacy != path
            and isinstance(legacy_task, dict)
            and str(legacy_task.get("task_id") or "") == task_id
        ):
            legacy.unlink(missing_ok=True)


def _load_all(root: Path) -> list[dict[str, Any]]:
    d = _tasks_dir(root)
    if not d.exists():
        return []
    # Atomic writes use hidden ``.tmp-*.json`` siblings. If a process dies
    # between temp creation and replace, the leftover file must not become a
    # second claimable copy of the same logical task.
    tasks: dict[str, tuple[int, bool, dict[str, Any]]] = {}
    for path in sorted(d.glob("*.json")):
        if path.name.startswith("."):
            continue
        task = _store.read_json(path, default=None)
        if not isinstance(task, dict):
            continue
        task_id = str(task.get("task_id") or "")
        if not task_id:
            continue
        canonical = path == _path(root, task_id)
        try:
            modified = path.stat().st_mtime_ns
        except OSError:
            modified = 0
        candidate = (modified, canonical, task)
        if task_id not in tasks or candidate[:2] > tasks[task_id][:2]:
            tasks[task_id] = candidate
    return [task for _modified, _canonical, task in tasks.values()]


# Liveness/ownership fields that belong to a teammate working or waiting on a task.
# A re-form of an already-running campaign (operator re-runs ``team form`` while
# the Curator has teammates in flight) must NOT reset these to the pending
# defaults: doing so silently de-owns the task, drops ``count_in_flight`` to 0,
# and lets the pool double-spawn a second teammate into the SAME workdir on the
# next reap. The static spec fields are always refreshed from the new spec.
_LIVE_OWNERSHIP_FIELDS = (
    "state",
    "owner",
    "claim_ts",
    "heartbeat_ts",
    "attempts",
    "reason",
    "pending_question",
    "operator_options",
    "operator_answer",
    "last_thread_id",
)

_MATERIAL_SPEC_FIELDS = (
    "title",
    "objective",
    "target",
    "lower_is_better",
    "owns_paths",
    "cwd",
    "deps",
    "result_shard",
    "operator_answer",
    "priority",
)


def _material_task_spec(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": str(task.get("title", "") or ""),
        "objective": str(task.get("objective", "") or ""),
        "target": str(task.get("target", "") or ""),
        "lower_is_better": task.get("lower_is_better"),
        "owns_paths": list(task.get("owns_paths", [])),
        "cwd": str(task.get("cwd", "") or ""),
        "deps": list(task.get("deps", [])),
        "result_shard": str(task.get("result_shard", "") or ""),
        "operator_answer": str(task.get("operator_answer", "") or ""),
        "priority": int(task.get("priority", 100)),
    }


def _has_complete_material_spec(task: dict[str, Any]) -> bool:
    return all(field in task for field in _MATERIAL_SPEC_FIELDS)


def form(root: Path, tasks: list[dict[str, Any]]) -> None:
    """Create (or refresh) the task records for a team from partial specs.

    Idempotent over an ACTIVE campaign: when a task record already exists and a
    teammate is mid-flight or waiting on it (``claimed``/``running``/``blocked``), its
    ownership/liveness fields are PRESERVED and only the static spec fields
    (title/objective/acceptance_check/target/priority/...) are refreshed.
    Re-running ``form`` on a live fleet therefore never de-owns a task a Curator
    teammate is working — which would otherwise defeat the pool's double-spawn
    guard. Takes the board lock so the read-merge can't race a concurrent
    claim/heartbeat/reassign.

    The record is rebuilt field by field rather than copied from the spec, and
    what that buys is lifecycle integrity: ``state``, ``owner``, ``claim_ts``,
    ``heartbeat_ts`` and ``attempts`` belong to the board and to the Curator, so
    a spec that sets them is ignored rather than trusted. It is not a schema
    guard on the descriptive half of the record — the fields above are simply the
    ones the lead had a way to say. Widening that half is admissible; widening it
    to anything the board itself acts on is not.
    """
    with _store.locked(_lock(root)):
        existing = _load_all(root)
        seen_identities: dict[str, str] = {}
        for task in existing:
            task_id = str(task.get("task_id") or "")
            identity = normalized_logical_identifier(task_id)
            if identity:
                prior_identity = seen_identities.get(identity)
                if prior_identity is not None and prior_identity != task_id:
                    raise ValueError(
                        "existing task board contains conflicting normalized task ids: "
                        f"{prior_identity!r} vs {task_id!r}"
                    )
                seen_identities.setdefault(identity, task_id)
        for spec in tasks:
            tid = spec["task_id"]
            identity = normalized_logical_identifier(tid)
            if not identity:
                raise ValueError(f"invalid task_id for task board path: {tid!r}")
            prior_identity = seen_identities.get(identity)
            if prior_identity is not None and prior_identity != tid:
                raise ValueError(
                    "task_id conflicts with an existing task under normalized identity: "
                    f"{tid!r} vs {prior_identity!r}"
                )
            if identity in seen_identities and seen_identities[identity] == tid:
                pass
            elif identity in seen_identities:
                raise ValueError("duplicate task_id under normalized identity")
            else:
                seen_identities[identity] = tid
            task = {
                "task_id": tid,
                "title": spec.get("title", ""),
                "objective": spec.get("objective", ""),
                # This task's done condition, carried verbatim and never read
                # here. Every other mission in this runtime has one — the
                # Planner writes it, the Manager's DAG carries it, the
                # supervisor puts it in front of the Reviewer — and a board task
                # was the single mission shape with no way to state one. It is
                # the field a per-mission hook consults first
                # (``verticals._base.vertical_mission_prelude`` is handed this
                # record as the mission), so with no slot for it, a dispatched
                # teammate could only be briefed off prose meant for a human.
                # The board neither parses nor matches on the string: what a
                # well-formed one says is the vertical's business, and stays
                # there.
                "acceptance_check": str(spec.get("acceptance_check", "") or ""),
                # The target this task contributes to. Several tasks (breadth + depth
                # re-forms) can share one target, so the leaderboard aggregates by
                # target, not task_id. Defaults to task_id.
                "target": spec.get("target") or tid,
                # Optimization direction for this target's metric, for the leaderboard:
                # True = lower is better (latency / error-count / loss), False = higher
                # (a speedup / score). None (default) → the leaderboard's global default.
                "lower_is_better": spec.get("lower_is_better"),
                "owns_paths": list(spec.get("owns_paths", [])),
                # Per-task working directory. When set, the Curator spawns this task's
                # teammate in its OWN dir, so N tasks can be independent project
                # workdirs (e.g. one per kernel) instead of all sharing the campaign
                # cwd. Empty → fall back to the campaign cwd (legacy behaviour).
                "cwd": str(spec.get("cwd", "") or ""),
                "deps": list(spec.get("deps", [])),
                "state": "pending",
                "owner": "",
                "result_shard": spec.get("result_shard", ""),
                "reason": "",
                "pending_question": "",
                "operator_options": [],
                "operator_answer": str(spec.get("operator_answer", "") or ""),
                "last_thread_id": "",
                "claim_ts": 0.0,
                "heartbeat_ts": 0.0,
                "attempts": 0,
                "priority": int(spec.get("priority", 100)),
            }
            prior = _read_task(root, tid)
            if prior is None and len(str(tid).encode("utf-8")) > 120:
                raise ValueError("task_id exceeds 120 UTF-8 bytes")
            if isinstance(prior, dict) and prior.get("state") in (
                "claimed",
                "running",
                "blocked",
            ):
                if (
                    _has_complete_material_spec(prior)
                    and _material_task_spec(prior) != _material_task_spec(task)
                ):
                    raise ValueError(
                        "cannot reuse live task identity with a materially changed spec: "
                        f"{tid!r}"
                    )
                # A teammate is mid-flight on this task — keep its ownership and
                # only refresh the static spec fields rebuilt above.
                for field in _LIVE_OWNERSHIP_FIELDS:
                    if field in prior:
                        task[field] = prior[field]
            elif (
                isinstance(prior, dict)
                and prior.get("state") == "pending"
                and prior.get("operator_answer")
            ):
                task["operator_answer"] = prior["operator_answer"]
            _write_task(root, tid, task)


def _done_ids(tasks: list[dict[str, Any]]) -> set[str]:
    return {t["task_id"] for t in tasks if t["state"] == "done"}


def claim_top(root: Path, member_id: str, *, now: float) -> dict[str, Any] | None:
    """Atomically claim the highest-priority pending task whose deps are all done.

    Lower ``priority`` values run first, tie-broken by ``task_id``. The resident
    Curator is the sole caller that allocates work from the lead's backlog.
    """
    with _store.locked(_lock(root)):
        tasks = _load_all(root)
        done = _done_ids(tasks)
        eligible = [
            t for t in tasks
            if t["state"] == "pending" and all(dep in done for dep in t["deps"])
        ]
        if not eligible:
            return None
        eligible.sort(key=lambda t: (int(t.get("priority", 100)), t["task_id"]))
        task = eligible[0]
        task["state"] = "claimed"
        task["owner"] = member_id
        task["claim_ts"] = now
        task["heartbeat_ts"] = now
        _write_task(root, task["task_id"], task)
        return task


def count_in_flight(root: Path) -> int:
    """Number of tasks currently claimed or running (occupying a pool slot)."""
    return sum(1 for t in _load_all(root) if t["state"] in ("claimed", "running"))


def heartbeat(root: Path, task_id: str, *, now: float) -> None:
    """Refresh liveness; first heartbeat promotes ``claimed`` -> ``running``."""
    with _store.locked(_lock(root)):
        task = _read_task(root, task_id)
        if not isinstance(task, dict):
            return
        task["heartbeat_ts"] = now
        if task["state"] == "claimed":
            task["state"] = "running"
        _write_task(root, task_id, task)


def _mutate(root: Path, task_id: str, **changes: Any) -> None:
    with _store.locked(_lock(root)):
        task = _read_task(root, task_id)
        if not isinstance(task, dict):
            return
        task.update(changes)
        _write_task(root, task_id, task)


def complete(root: Path, task_id: str, *, shard: str = "") -> None:
    _mutate(root, task_id, state="done", result_shard=shard)


def fail(root: Path, task_id: str, *, reason: str = "") -> None:
    _mutate(root, task_id, state="failed", reason=reason)


def block_for_operator(
    root: Path,
    task_id: str,
    *,
    question: str,
    options: list[dict[str, Any]] | None = None,
    reason: str = "",
    last_thread_id: str = "",
) -> None:
    """Park a task without making it claimable until an explicit answer resumes it."""

    _mutate(
        root,
        task_id,
        state="blocked",
        reason=reason,
        pending_question=question,
        operator_options=list(options or []),
        last_thread_id=last_thread_id,
    )


def resume(root: Path, task_id: str, *, answer: str) -> None:
    """Apply an operator answer and return one blocked task to the Curator queue."""

    answer = answer.strip()
    if not answer:
        raise ValueError("operator answer must not be empty")
    with _store.locked(_lock(root)):
        task = _store.read_json(_path(root, task_id), default=None)
        if not isinstance(task, dict):
            raise KeyError(task_id)
        if task.get("state") != "blocked" or not task.get("pending_question"):
            raise ValueError(f"task is not waiting for an operator answer: {task_id}")
        task.update(
            state="pending",
            owner="",
            reason="",
            pending_question="",
            operator_options=[],
            operator_answer=answer,
        )
        _store.atomic_write_json(_path(root, task_id), task)


def reassign_stale(
    root: Path,
    *,
    ttl: float,
    now: float,
    live_owners: set[str] | None = None,
) -> list[str]:
    """Return stale claimed/running tasks to pending.

    ``live_owners`` lets the resident Curator distinguish a stale heartbeat
    from a still-running teammate process whose heartbeat thread is delayed. A
    task with a live owner must not be reset to pending, or the same logical task
    can be claimed again while the old teammate is still running.
    """
    live_owners = live_owners or set()
    reassigned: list[str] = []
    with _store.locked(_lock(root)):
        for task in _load_all(root):
            if task["state"] in ("claimed", "running") and now - task["heartbeat_ts"] > ttl:
                if task.get("owner") in live_owners:
                    continue
                task["state"] = "pending"
                task["owner"] = ""
                task["attempts"] = int(task.get("attempts", 0)) + 1
                _write_task(root, task["task_id"], task)
                reassigned.append(task["task_id"])
    return reassigned


def snapshot(root: Path) -> list[dict[str, Any]]:
    return _load_all(root)
