"""Where a failure happened, kept separate from what to do next.

A review verdict says whether to keep going. It does not say *what* went
wrong, and without that the same word covers two very different situations:
a proof with a fixable gap, and a route that should have been abandoned three
rounds ago. Both come back as ``continue``, so both get patched locally. The
system spends weeks perfecting its understanding of a method that cannot work,
and periodically rediscovers a route it already ruled out.

Three layers, following the distinction QED draws:

``proof``
    The plan is still sound; this argument has a gap. Fix the argument.

``plan``
    The decomposition is wrong — subgoals do not compose, or a dependency was
    mis-stated. Re-derive the subgoals; the overall approach may still hold.

``strategy``
    The approach itself is not worth continuing. Ruling out one sufficient
    criterion is not progress toward the original goal, and continuing to
    perfect that refutation is how goal drift happens.

Deliberately *not* a fourth verdict. Argus already has
``done | continue | blocked | replan_requested``; adding a parallel state
machine would put two authorities on the same decision. This is an orthogonal
attribution field, the same shape as ``failure_class`` beside ``idea_status``
in :mod:`argus_skill.core.evidence_status`: the verdict controls flow, the
layer explains it, and the layer is what makes route history checkable.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "FAILURE_LAYERS",
    "LAYER_MEANING",
    "RouteRecord",
    "RouteLedger",
    "abandoned_routes",
    "normalize_layer",
    "route_key",
]

FAILURE_LAYERS = ("proof", "plan", "strategy")

LAYER_MEANING = {
    "proof": "the plan holds; this argument has a gap",
    "plan": "the subgoal decomposition or its dependencies are wrong",
    "strategy": "the approach itself is not worth continuing",
}

_LEDGER_RELPATH = ("research", "ROUTE_LEDGER.json")


def normalize_layer(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    return text if text in FAILURE_LAYERS else None


def route_key(route: Any) -> str:
    """Stable identity for a route, so the same idea is recognised again.

    Normalised rather than compared verbatim: "endpoint Eisenstein at y=-2"
    and "Endpoint  Eisenstein  at  y = -2" are the same route, and a ledger
    that misses that is a ledger that never fires.
    """
    text = " ".join(str(route or "").strip().lower().split())
    return text.replace(" = ", "=").replace(" , ", ",")


@dataclass
class RouteRecord:
    """What has happened to one route."""

    route: str
    strategy_failures: int = 0
    plan_failures: int = 0
    proof_failures: int = 0
    abandoned: bool = False
    evidence: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "route": self.route,
            "strategy_failures": self.strategy_failures,
            "plan_failures": self.plan_failures,
            "proof_failures": self.proof_failures,
            "abandoned": self.abandoned,
            "evidence": list(self.evidence),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RouteRecord":
        return cls(
            route=str(payload.get("route") or ""),
            strategy_failures=int(payload.get("strategy_failures") or 0),
            plan_failures=int(payload.get("plan_failures") or 0),
            proof_failures=int(payload.get("proof_failures") or 0),
            abandoned=bool(payload.get("abandoned")),
            evidence=[str(item) for item in (payload.get("evidence") or [])],
        )


class RouteLedger:
    """Per-route failure history, so an abandoned route stays abandoned.

    ``abandon_after`` strategy-layer failures mark a route abandoned. One is
    enough by default: a strategy-layer verdict already means "this approach
    is not worth continuing", and needing to say it twice is how the loop
    survives.
    """

    def __init__(self, project_root: object, *, abandon_after: int = 1) -> None:
        self.path = Path(str(project_root)).joinpath(*_LEDGER_RELPATH)
        self.abandon_after = max(1, int(abandon_after))
        self._routes: dict[str, RouteRecord] | None = None

    # -- storage -----------------------------------------------------------

    def _load(self) -> dict[str, RouteRecord]:
        if self._routes is not None:
            return self._routes
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        routes: dict[str, RouteRecord] = {}
        if isinstance(payload, dict):
            for key, item in (payload.get("routes") or {}).items():
                if isinstance(item, dict):
                    routes[str(key)] = RouteRecord.from_dict(item)
        self._routes = routes
        return routes

    def _save(self) -> None:
        routes = self._load()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {"routes": {key: record.as_dict() for key, record in routes.items()}},
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    # -- reading -----------------------------------------------------------

    def record_for(self, route: str) -> RouteRecord:
        return self._load().get(route_key(route), RouteRecord(route=str(route)))

    def is_abandoned(self, route: str) -> bool:
        return self.record_for(route).abandoned

    def abandoned(self) -> list[RouteRecord]:
        return sorted(
            (record for record in self._load().values() if record.abandoned),
            key=lambda record: record.route,
        )

    def revisit_error(self, route: str) -> str:
        """Why proposing *route* again is wrong, or ``""`` when it is fine.

        The message carries the evidence that retired it, so the planner is
        told what it already knows rather than merely being refused.
        """
        record = self.record_for(route)
        if not record.abandoned:
            return ""
        why = f"; ruled out by: {record.evidence[-1]}" if record.evidence else ""
        return (
            f"route {record.route!r} was already abandoned at the strategy layer "
            f"after {record.strategy_failures} verdict(s){why}. Choose a route "
            "with a different mechanism, or state what new information reopens "
            "this one"
        )

    # -- writing -----------------------------------------------------------

    def record_failure(
        self, route: str, layer: str, *, evidence: str = ""
    ) -> RouteRecord:
        """Attribute one failure to *route* at *layer* and persist it."""
        normalized = normalize_layer(layer)
        if normalized is None:
            raise ValueError(
                f"unknown failure layer {layer!r}; expected one of "
                f"{', '.join(FAILURE_LAYERS)}"
            )
        routes = self._load()
        key = route_key(route)
        record = routes.get(key) or RouteRecord(route=str(route).strip())
        setattr(
            record,
            f"{normalized}_failures",
            getattr(record, f"{normalized}_failures") + 1,
        )
        if evidence.strip():
            record.evidence.append(evidence.strip())
        if record.strategy_failures >= self.abandon_after:
            record.abandoned = True
        routes[key] = record
        self._routes = routes
        self._save()
        return record

    def reopen(self, route: str, *, reason: str) -> RouteRecord:
        """Un-abandon a route because genuinely new information arrived.

        Requires a reason: reopening on a hunch is exactly the loop this
        ledger exists to break.
        """
        if not reason.strip():
            raise ValueError("reopening an abandoned route requires a reason")
        routes = self._load()
        key = route_key(route)
        record = routes.get(key) or RouteRecord(route=str(route).strip())
        record.abandoned = False
        record.strategy_failures = 0
        record.evidence.append(f"reopened: {reason.strip()}")
        routes[key] = record
        self._routes = routes
        self._save()
        return record


def abandoned_routes(project_root: object) -> list[str]:
    """Route names the project has already retired at the strategy layer."""
    return [record.route for record in RouteLedger(project_root).abandoned()]
