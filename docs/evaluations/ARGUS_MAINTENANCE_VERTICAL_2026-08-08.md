# Argus Maintenance Vertical — 2026-08-08

## Result

Argus now has a built-in `argus_maintenance` vertical for changes to Argus itself. It owns its audit tool, Skills, checklist, stages, workflow, and review policy. Generic core exposes only contract metadata and does not import the concrete vertical.

Automatic daemon repairs carry an explicit, persisted `argus_maintenance` route into their isolated worktree. Ordinary software projects remain on `software`.

## Requirements

The vertical enforces the operator's three requirements:

1. Code stays concise; behavior-free wrappers, duplicate state, stale knobs, speculative compatibility, and silent fallback chains require evidence or removal.
2. Shared behavior has one reusable owner rather than copied special cases.
3. Core owns generic self-evolution, context orchestration, durable long-running execution, review/recovery, and the narrow vertical contract. Domain tools, Skills, checklist items, stages, and workflow stay in vertical providers.

Additional requirements:

4. A heuristic match is evidence to inspect, not an automatic defect.
5. Simplification must preserve authentication, authorization, sandboxing, secrets, idempotency, crash recovery, concurrency safety, and data integrity.
6. Runtime invariants use explicit errors; tests use assertions. Production correctness must not change under `python -O`.
7. Compatibility code needs an observed consumer, owner, and retirement rule.
8. Tests must falsify public behavior and decisive failure paths independently of the implementation.
9. Claims are bounded by exact commands and results; lower static-warning counts alone do not prove quality.
10. Release identity and generated frontends are rebuilt only after final source changes.

## Workflow

```text
scope → audit → change → verify → report
```

Evidence:

- `research/MAINTENANCE_SCOPE.md`
- `research/ARCHITECTURE_AUDIT.json`
- `research/ARCHITECTURE_AUDIT.md`
- `research/MAINTENANCE_DECISIONS.md`
- `research/MAINTENANCE_PLAN.md`
- `research/VERIFICATION.md`
- `MAINTENANCE_REPORT.md`

The audit is generated with:

```bash
python -m argus_skill.verticals.argus_maintenance.architecture_audit collect
```

## Repository baseline

A full maintained-source scan covered 1,531 files. After the initial cleanup it reported 608 review candidates:

| Category | Candidates | Interpretation |
|---|---:|---|
| Silent broad exception | 244 | Review boundary ownership; many UI/telemetry/callback isolators may be justified. |
| Fallback chain | 195 | Inspect provenance and error visibility; ordinary value defaults are not automatically wrong. |
| Oversized function | 131 | Decomposition candidates, not line-count failures. |
| Thin wrapper | 21 | Keep only for a real API/dependency boundary. |
| Fixed digest | 16 | Mostly release, provenance, or content-bound migration pins; retain only with owner/lifecycle. |
| Concrete vertical branch | 0 | Research-only Skill preparation now runs through a provider-owned hook. |
| Concrete vertical import | 1 | The learning CLI still imports its implementation directly and remains architecture debt. |
| Runtime assert | 0 | Reduced from 14; runtime invariants now remain active under `python -O`. |
| Generic-layer hardware literal | 0 | Reduced from 7; project/harness evidence now owns hardware facts. |
| Machine-specific path | 0 | No maintained-source personal path detected. |

The complete report is intentionally regenerated rather than checked in: it is source-derived evidence, not another stale baseline or gate.

## Initial changes made through the policy

- Removed Manager's hardcoded `_OPTIMIZE_VERTICALS` table. Verticals now declare `MISSION_KIND` through the core-owned `VerticalContract`.
- Replaced software-name grounding branches with provider-declared `GROUND_BEFORE_HANDOFF` metadata.
- Removed concrete research imports from generic checklist fallback/rendering.
- Added explicit vertical and stage routing for isolated maintenance worktrees.
- Seeded the active vertical's package-managed Skills into its shared runtime scope.
- Fixed `BacklogItem.manager_decision` deserialization, which previously erased a persisted route after reload.
- Replaced all 14 production `assert` statements with explicit invariants or simpler non-optional control flow.
- Deleted the behavior-free `--skill-cleanse`, `--skill-stats`, and `--skill-stats-json` legacy no-ops plus two unused compatibility aliases instead of preserving wrappers around retired behavior.
- Removed A100/B200/H100/H200 facts from generic prompts and infrastructure guidance; benchmark constraints now come from the active frozen harness.
- Retired machine-specific NanoChat playbooks separately; exact old copies are removed safely while operator-edited copies are archived.

## Deliberately retained boundaries

Fixed digests are not blindly deleted. Release identity, artifact provenance, immutable evidence, and safe retirement of known old Skill bodies are legitimate integrity uses. Likewise, broad exception isolation may be correct at UI, callback, telemetry, shutdown, or recovery boundaries. The Reviewer must verify the caller, failure visibility, and ownership before changing either class.

## Verification

- Full Python suite: 4,770 passed / 13 skipped (4,783 collected).
- Web: 150 passed; TypeScript and production build passed.
- TUI: 224 passed; TypeScript and bundled production build passed.
- Ruff on every changed Python file: passed.
- Release artifact consistency: `0.1.1+0c75a0ea6d24a714` passed.
- Architecture audit report validation: passed.

## Known follow-up debt

- Remove the remaining direct `learning` vertical import from the generic CLI only when a reusable command-extension boundary is justified; do not add a framework for one handler.
- Review the 244 silent broad handlers by subsystem, prioritizing durable state, routing, and settlement before UI-only sinks.
- Decompose oversized functions only when a behavioral change gives an independent boundary; do not split functions to satisfy a count.
