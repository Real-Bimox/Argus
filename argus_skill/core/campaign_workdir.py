"""Persist and validate a campaign's primary execution root.

A session can start in a parent workspace, clone the real target repository, and
then spend the rest of its life operating in that child repository.  Keeping the
parent as the execution/artifact root creates two ``research/`` trees and makes
Manager/Reviewer evidence invisible to one another.  This module lets a
Planner-selected directory become the campaign root without changing the stable
Argus state directory.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

CAMPAIGN_WORKDIR_FILENAME = "campaign-workdir.json"


def campaign_workdir_path(state_root: Path | str) -> Path:
    return Path(state_root) / CAMPAIGN_WORKDIR_FILENAME


def normalize_task_workdir(value: object) -> str:
    """Normalize a Planner-authored execution root."""
    raw = str(value or "").strip()
    if not raw or raw == ".":
        return ""
    return Path(raw).as_posix()


def resolve_task_workdir(base_root: Path | str, value: object) -> Path:
    """Resolve an ordinary task root from *base_root*, without adopting it."""
    base = Path(base_root).expanduser().resolve(strict=True)
    requested = normalize_task_workdir(value)
    try:
        candidate = Path(requested).expanduser()
        target = (
            base
            if not requested
            else (candidate if candidate.is_absolute() else base / candidate).resolve(
                strict=True
            )
        )
    except OSError as exc:
        raise ValueError(f"TASK_WORKDIR is not a directory: {value!r}") from exc
    if not target.is_dir():
        raise ValueError(f"TASK_WORKDIR is not a directory: {value!r}")
    return target


def active_campaign_workdir(
    state_root: Path | str,
    base_root: Path | str,
) -> Path | None:
    """Return a valid persisted campaign root, otherwise ``None``."""
    _ = base_root
    try:
        payload = json.loads(
            campaign_workdir_path(state_root).read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    raw = str(payload.get("workdir") or "").strip()
    if not raw:
        return None
    try:
        target = Path(raw).expanduser().resolve(strict=True)
    except OSError:
        return None
    if not target.is_dir():
        return None
    return target


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _copy_pipeline_state(source_root: Path, target_root: Path) -> None:
    """Move Manager-owned stage authority to the adopted repository.

    The old file is retained as a compatibility snapshot, but all subsequent
    framework reads resolve to the adopted root.  Conflicting live state fails
    closed instead of silently choosing one copy.
    """
    source = source_root / "research" / "PIPELINE_STATE.json"
    target = target_root / "research" / "PIPELINE_STATE.json"
    if not source.is_file():
        return
    source_payload = _load_json(source)
    if source_payload is None:
        raise ValueError(f"cannot adopt workdir with unreadable pipeline state: {source}")
    if target.is_file():
        target_payload = _load_json(target)
        if target_payload is None:
            raise ValueError(f"target pipeline state is unreadable: {target}")
        for key in ("vertical", "current_stage"):
            left = str(source_payload.get(key) or "")
            right = str(target_payload.get(key) or "")
            if left and right and left != right:
                raise ValueError(
                    f"target pipeline state conflicts on {key}: {left!r} != {right!r}"
                )
        merged = {**source_payload, **target_payload}
        if merged != target_payload:
            temporary = target.with_suffix(
                target.suffix + f".adopt.{os.getpid()}.tmp"
            )
            temporary.write_text(
                json.dumps(merged, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, target)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + f".adopt.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(source_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, target)


def adopt_campaign_workdir(
    *,
    state_root: Path | str,
    base_root: Path | str,
    current_root: Path | str,
    requested: object,
) -> Path:
    """Validate and persist a Planner-selected directory as campaign root."""
    base = Path(base_root).expanduser().resolve(strict=True)
    current = Path(current_root).expanduser().resolve(strict=True)
    relative = normalize_task_workdir(requested)
    # Relative DAG paths remain anchored to the original session root even
    # after an earlier sibling has adopted another campaign directory.
    target = current if not relative else resolve_task_workdir(base, relative)
    if target == current:
        return current

    _copy_pipeline_state(current, target)
    payload = {
        "schema_version": 1,
        "base_workdir": str(base),
        "workdir": str(target),
    }
    path = campaign_workdir_path(state_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)
    return target


__all__ = [
    "CAMPAIGN_WORKDIR_FILENAME",
    "active_campaign_workdir",
    "adopt_campaign_workdir",
    "campaign_workdir_path",
    "normalize_task_workdir",
    "resolve_task_workdir",
]
