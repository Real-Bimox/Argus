from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from argus_skill.core.vertical_contract import (
    VerticalContractError,
    vertical_contract,
)


def test_minimal_non_research_vertical_implements_only_documented_contract() -> None:
    provider = SimpleNamespace(
        CHECKLIST_STAGE_ORDER=("build", "verify"),
        CHECKLIST_ITEMS={"build": (), "verify": ()},
        completion_gate="none",
    )

    contract = vertical_contract("minimal_delivery", provider)

    assert contract.name == "minimal_delivery"
    assert contract.stage_order == ("build", "verify")
    assert contract.completion_gate == "none"
    assert contract.banner("engineer") == ""
    assert contract.evidence_schema is None


def test_incomplete_vertical_fails_visibly() -> None:
    with pytest.raises(VerticalContractError, match="no checklist"):
        vertical_contract(
            "broken",
            SimpleNamespace(
                CHECKLIST_STAGE_ORDER=("work",),
                completion_gate="none",
            ),
        )


def test_core_has_no_vertical_package_imports() -> None:
    core = Path(__file__).parents[2] / "argus_skill" / "core"
    offenders: list[str] = []
    for path in core.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and "verticals" in str(node.module or ""):
                offenders.append(f"{path.name}:{node.lineno}")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if ".verticals" in alias.name:
                        offenders.append(f"{path.name}:{node.lineno}")
    assert offenders == []
