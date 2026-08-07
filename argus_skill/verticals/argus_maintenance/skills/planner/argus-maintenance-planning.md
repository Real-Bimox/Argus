---
name: Argus Maintenance Planning
description: Plan concise, reusable, core-decoupled Argus changes from call-path evidence and independently verifiable risks.
---

# Argus maintenance planning

Read `research/MAINTENANCE_SCOPE.md` and the architecture audit before decomposition.

Plan by behavior and ownership, not by file count:

- Keep one cohesive node when one Engineer can audit, change, and verify it safely.
- Split only independent deliverables or failure risks.
- Put generic state/orchestration/recovery interfaces in core; put domain tools, Skills, checklists, stages, and workflow in the owning vertical.
- Prefer an existing narrow contract over a new registry, adapter, facade, or compatibility layer.
- A wrapper/alias/knob/fallback survives only with an observed consumer and explicit owner.
- Treat local regressions as acceptable only when bounded, explained, and outweighed by semantic progress.
- Require a behavioral regression test, affected-suite command, boundary test, and release rebuild when shipped artifacts participate.
- Never schedule a mass deletion from heuristic counts. Every removal needs a real call path or proof of no callers.

The plan must state the expected complexity removed, the invariant retained, and the evidence that decides success.
