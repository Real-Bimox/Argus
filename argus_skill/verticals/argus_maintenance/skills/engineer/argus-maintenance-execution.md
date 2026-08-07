---
name: Argus Maintenance Execution
description: Audit and implement Argus self-maintenance changes with concise code, reusable contracts, vertical isolation, and behavior-based verification.
---

# Argus maintenance execution

## Audit first

Run:

```bash
python -m argus_skill.verticals.argus_maintenance.architecture_audit collect
```

In `research/MAINTENANCE_DECISIONS.md`, classify only findings relevant to the task:

- **keep** — necessary boundary, with caller/invariant;
- **simplify** — same owner and behavior with less machinery;
- **move** — valid policy in the wrong layer;
- **remove** — no behavior, caller, or supported compatibility obligation.

A heuristic finding is never enough evidence by itself.

## Implementation rules

1. One source of truth; no shadow state or synchronized aliases.
2. Reuse the closest implementation; do not add a framework for one call site.
3. Runtime validation uses explicit errors, not `assert` that disappears under `python -O`.
4. Catch the narrow exception you can handle. If a boundary intentionally isolates all callback/UI/telemetry failures, make that ownership visible and observable where useful.
5. Fixed hashes are acceptable for integrity or content-bound migration only with an owner and retirement condition.
6. Do not preserve speculative compatibility. Demonstrate a consumer or remove the path.
7. Core never imports a concrete vertical. Extend the core-owned contract; keep domain code under the vertical.
8. Preserve authorization, sandbox, credentials, atomicity, locks, idempotency, recovery, and data integrity.
9. Test externally visible behavior and failure paths; do not copy the patch's implementation into expected values.
10. Rebuild release artifacts only after final source changes.

Keep the diff narrow and delete obsolete comments/tests/config together with the code they described.
