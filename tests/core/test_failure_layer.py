"""Failure attribution, and the loop it exists to break.

The observed behaviour: a project asked to prove a conjecture spent weeks
proving that one sufficient criterion could never work, then periodically
returned to routes it had already ruled out. Both symptoms come from a review
verdict that says "keep going" without saying what went wrong.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from argus_skill.core.failure_layer import (
    FAILURE_LAYERS,
    LAYER_MEANING,
    RouteLedger,
    abandoned_routes,
    normalize_layer,
    route_key,
)


@pytest.fixture
def ledger(tmp_path: Path) -> RouteLedger:
    return RouteLedger(tmp_path)


# -- vocabulary -------------------------------------------------------------

def test_three_layers_with_distinct_meanings() -> None:
    assert FAILURE_LAYERS == ("proof", "plan", "strategy")
    assert set(LAYER_MEANING) == set(FAILURE_LAYERS)
    assert len(set(LAYER_MEANING.values())) == 3


@pytest.mark.parametrize("layer", FAILURE_LAYERS)
def test_layers_normalize(layer) -> None:
    assert normalize_layer(f"  {layer.upper()}  ") == layer


def test_unknown_layers_are_rejected(ledger: RouteLedger) -> None:
    assert normalize_layer("giving_up") is None
    with pytest.raises(ValueError, match="unknown failure layer"):
        ledger.record_failure("some route", "giving_up")


# -- the same route must be recognised again --------------------------------

def test_route_identity_ignores_spacing_and_case() -> None:
    assert route_key("endpoint Eisenstein at y = -2") == route_key(
        "Endpoint  Eisenstein  at  y=-2"
    )


def test_an_abandoned_route_is_recognised_when_reproposed(ledger: RouteLedger) -> None:
    ledger.record_failure("endpoint Eisenstein at y=-2", "strategy")

    # Reproposed with different whitespace and capitalisation.
    assert ledger.is_abandoned("Endpoint  Eisenstein  at  y = -2") is True


# -- what each layer does ---------------------------------------------------

def test_a_strategy_failure_retires_the_route(ledger: RouteLedger) -> None:
    ledger.record_failure("route C", "strategy", evidence="infeasible except finitely many n")

    assert ledger.is_abandoned("route C") is True
    assert abandoned_routes(ledger.path.parent.parent) == ["route C"]


@pytest.mark.parametrize("layer", ["proof", "plan"])
def test_proof_and_plan_failures_do_not_retire_the_route(ledger: RouteLedger, layer) -> None:
    # A gap in the argument, or a wrong decomposition, does not mean the
    # approach is worthless — that conflation is what causes goal drift.
    ledger.record_failure("route D", layer)

    assert ledger.is_abandoned("route D") is False


def test_repeated_proof_failures_still_do_not_retire_the_route(ledger: RouteLedger) -> None:
    for _ in range(5):
        ledger.record_failure("route D", "proof")

    assert ledger.record_for("route D").proof_failures == 5
    assert ledger.is_abandoned("route D") is False


def test_the_abandon_threshold_is_configurable(tmp_path: Path) -> None:
    strict = RouteLedger(tmp_path, abandon_after=2)
    strict.record_failure("route E", "strategy")

    assert strict.is_abandoned("route E") is False
    strict.record_failure("route E", "strategy")
    assert strict.is_abandoned("route E") is True


# -- refusing to re-run a dead route ---------------------------------------

def test_reproposing_an_abandoned_route_is_refused_with_its_evidence(
    ledger: RouteLedger,
) -> None:
    ledger.record_failure(
        "endpoint Eisenstein", "strategy", evidence="y=-2 infeasible except finitely many n"
    )

    message = ledger.revisit_error("endpoint Eisenstein")

    assert "already abandoned" in message
    # Told what it already knows, not merely refused.
    assert "y=-2 infeasible" in message
    assert "different mechanism" in message


def test_a_live_route_is_not_refused(ledger: RouteLedger) -> None:
    ledger.record_failure("route F", "proof")

    assert ledger.revisit_error("route F") == ""


def test_an_unseen_route_is_not_refused(ledger: RouteLedger) -> None:
    assert ledger.revisit_error("brand new idea") == ""


# -- reopening requires new information ------------------------------------

def test_reopening_needs_a_reason(ledger: RouteLedger) -> None:
    ledger.record_failure("route G", "strategy")

    with pytest.raises(ValueError, match="requires a reason"):
        ledger.reopen("route G", reason="   ")


def test_reopening_with_a_reason_clears_the_abandonment(ledger: RouteLedger) -> None:
    ledger.record_failure("route G", "strategy")

    ledger.reopen("route G", reason="new lemma removes the obstruction")

    assert ledger.is_abandoned("route G") is False
    assert any("reopened" in item for item in ledger.record_for("route G").evidence)


# -- persistence ------------------------------------------------------------

def test_the_ledger_survives_a_restart(tmp_path: Path) -> None:
    RouteLedger(tmp_path).record_failure("route H", "strategy", evidence="checked")

    # A fresh process must still refuse the route.
    assert RouteLedger(tmp_path).is_abandoned("route H") is True


def test_a_corrupt_ledger_is_treated_as_empty(tmp_path: Path) -> None:
    path = tmp_path / "research" / "ROUTE_LEDGER.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")

    assert RouteLedger(tmp_path).is_abandoned("anything") is False


def test_the_ledger_is_readable_json(tmp_path: Path) -> None:
    RouteLedger(tmp_path).record_failure("route I", "strategy", evidence="why")
    payload = json.loads((tmp_path / "research" / "ROUTE_LEDGER.json").read_text())

    assert payload["routes"][route_key("route I")]["abandoned"] is True
