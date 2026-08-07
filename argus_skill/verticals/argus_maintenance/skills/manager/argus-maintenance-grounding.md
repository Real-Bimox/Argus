---
name: Argus Maintenance Grounding
description: Ground a change to the Argus framework in its real call path, architecture boundary, tests, and release obligations before implementation.
---

# Argus maintenance grounding

Use only when Argus is changing or repairing its own repository/runtime. Ordinary application work belongs to `software`; domain projects belong to their own vertical.

Before handoff, inspect the repository and return a compact brief:

1. Requested observable behavior and exact acceptance check.
2. Current entry point → owner → persistence/external-effect call path.
3. Closest unchanged reusable analogue.
4. Public API, state, event, CLI/Web/TUI, plugin, and release surfaces affected.
5. Correct ownership: generic orchestration contract in core, concrete policy/tool/workflow in a vertical.
6. Protected boundaries: authentication, authorization, sandbox, secrets, idempotency, crash recovery, concurrency, and data integrity.
7. Exact narrow and affected-suite verification commands.
8. Explicit non-goals; never turn a bounded repair into repository-wide aesthetic cleanup.

Do not infer that an `assert`, digest, broad exception, or wrapper is wrong from syntax alone. Name the observed caller and failure mode, or leave it for audit.
