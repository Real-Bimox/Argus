---
name: Argus Maintenance Review
description: Independently review Argus self-maintenance for real simplification, reusable boundaries, vertical decoupling, and preserved safety and recovery behavior.
---

# Argus maintenance review

Review the complete diff and actual callers, not only the Engineer summary.

## Required challenges

- Does the patch change the requested behavior, or only rename/move code?
- Is new abstraction reused now, or speculative?
- Did a wrapper, alias, knob, fallback, digest, or compatibility path survive without an observed consumer and owner?
- Does generic core import or branch on a concrete vertical?
- Did domain tooling/policy leak into core, Manager, Life, or generic prompts?
- Could `python -O`, restart, concurrency, partial writes, missing credentials, or callback failure change correctness?
- Were authentication, authorization, sandboxing, secret protection, idempotency, recovery, and data integrity preserved?
- Do tests falsify public behavior and decisive failure paths independently of the implementation?
- Do build/type checks and affected suites actually run nonzero tests?
- If release identity participates, do generated artifacts match final source?

Do not reward fewer audit findings by itself. Return `done` only when the behavior is correct, the ownership boundary is cleaner, and verification is real. Record justified retained findings and unresolved debt honestly.
