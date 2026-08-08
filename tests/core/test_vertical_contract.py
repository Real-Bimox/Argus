from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from argus_skill.core.vertical_contract import (
    VerticalContractError,
    vertical_contract,
)
from argus_skill.skills.stage_machine import ChecklistItem


def _item(item_id: str) -> ChecklistItem:
    return ChecklistItem(item_id, f"Verify {item_id}", f"evidence for {item_id}")


def test_minimal_non_research_vertical_implements_only_documented_contract() -> None:
    provider = SimpleNamespace(
        CHECKLIST_STAGE_ORDER=("build", "verify"),
        CHECKLIST_ITEMS={"build": (_item("build.output"),), "verify": (_item("verify.output"),)},
        completion_gate="none",
    )

    contract = vertical_contract("minimal_delivery", provider)

    assert contract.name == "minimal_delivery"
    assert contract.stage_order == ("build", "verify")
    assert contract.completion_gate == "none"
    assert contract.mission_kind == "custom"
    assert contract.ground_before_handoff is False
    assert contract.banner("engineer") == ""
    assert contract.evidence_schema is None
    assert contract.assurance_level == "reviewer"


def test_provider_declares_routing_metadata_without_manager_name_tables() -> None:
    provider = SimpleNamespace(
        CHECKLIST_STAGE_ORDER=("work",),
        CHECKLIST_ITEMS={"work": (_item("work.output"),)},
        completion_gate="none",
        MISSION_KIND="software",
        GROUND_BEFORE_HANDOFF=True,
    )

    contract = vertical_contract("maintainer", provider)

    assert contract.mission_kind == "software"
    assert contract.ground_before_handoff is True


def test_provider_completion_validator_is_typed_and_normalized(tmp_path: Path) -> None:
    provider = SimpleNamespace(
        CHECKLIST_STAGE_ORDER=("verify",),
        CHECKLIST_ITEMS={"verify": (_item("verify.output"),)},
        completion_gate="none",
        stage_completion_issues=lambda stage, root: [f"{stage}:{root.name}", ""],
    )

    contract = vertical_contract("validated", provider)

    assert contract.completion_issues("verify", tmp_path) == (
        f"verify:{tmp_path.name}",
    )
    assert contract.assurance_level == "hybrid"


def test_non_callable_completion_validator_fails_visibly() -> None:
    with pytest.raises(VerticalContractError, match="non-callable"):
        vertical_contract(
            "broken",
            SimpleNamespace(
                CHECKLIST_STAGE_ORDER=("verify",),
                CHECKLIST_ITEMS={"verify": (_item("verify.output"),)},
                completion_gate="none",
                stage_completion_issues=[],
            ),
        )


def test_empty_required_checklist_fails_but_runtime_authored_is_explicit() -> None:
    with pytest.raises(VerticalContractError, match="empty required"):
        vertical_contract(
            "empty",
            SimpleNamespace(
                CHECKLIST_STAGE_ORDER=("work",),
                CHECKLIST_ITEMS={"work": ()},
                completion_gate="none",
            ),
        )

    contract = vertical_contract(
        "authored_later",
        SimpleNamespace(
            CHECKLIST_STAGE_ORDER=("work",),
            CHECKLIST_OPTIONAL_STAGES=("work",),
            CHECKLIST_ITEMS={},
            completion_gate="none",
        ),
    )
    assert contract.assurance_level == "runtime-authored"


def test_primary_stage_deliverables_are_exposed_by_contract() -> None:
    provider = SimpleNamespace(
        CHECKLIST_STAGE_ORDER=("scope", "work"),
        CHECKLIST_ITEMS={
            "scope": (_item("scope.output"),),
            "work": (_item("work.output"),),
        },
        STAGE_PRIMARY_DELIVERABLES={
            "scope": ("research/SCOPE.md", "research/setup.md"),
        },
        completion_gate="none",
    )

    contract = vertical_contract("scoped", provider)

    assert contract.primary_deliverables("scope") == (
        "research/SCOPE.md",
        "research/setup.md",
    )
    assert contract.primary_deliverables("work") == ()


def test_stage_checks_are_validated_and_mark_contract_hybrid() -> None:
    provider = SimpleNamespace(
        CHECKLIST_STAGE_ORDER=("work",),
        CHECKLIST_ITEMS={"work": (_item("work.output"),)},
        STAGE_CHECKS={"work": [("Artifact exists", "test -s RESULT.md")]},
        completion_gate="none",
    )

    contract = vertical_contract("checked", provider)

    assert contract.assurance_level == "hybrid"
    assert contract.stage_checks == {
        "work": (("Artifact exists", "test -s RESULT.md"),)
    }

    provider.STAGE_CHECKS = {"ghost": [("No", "false")]}
    with pytest.raises(VerticalContractError, match="unknown stages"):
        vertical_contract("checked", provider)


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
