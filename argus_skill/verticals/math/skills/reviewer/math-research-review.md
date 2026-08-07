---
name: "Math Research Review"
description: "Independently review mathematical correctness, novelty, significance, statement fidelity, and real Lean evidence against the requested research target."
---

Review the mathematics, not the paperwork. Missing scope documents, ledgers,
graphs, audit reports, or evidence bundles are not defects by themselves, and
their presence is not evidence of correctness.

Read the original question and the actual result. Check the important steps,
assumptions, quantifiers, dependencies, and conclusion. A finite computation is
not a proof of a universal claim. A counterexample or construction must satisfy
the original conditions.

If a complete proof was requested, return `done` only for a complete proof; an
honest failed attempt remains useful but incomplete. If the task asks for
continued strengthening, compare the new result directly with the strongest
prior one. A bounded subproblem can be done without claiming that the whole
research goal is complete.

## Say which layer failed

When the round is incomplete, name where it failed. The verdict says whether
to continue; this says what to change, and without it every failure gets
patched locally.

- `proof` — the plan holds and this argument has a gap. Fix the argument.
- `plan` — the subgoal decomposition or its dependencies are wrong. Re-derive
  the subgoals; the approach may still be sound.
- `strategy` — the approach itself is not worth continuing. Say so plainly and
  record the evidence that retires it, so the route is not proposed again
  under a new name.

A `targeted` project that has drifted into proving some method can never work
is a `strategy` failure, however rigorous that work is. Ruling out a
sufficient criterion does not settle the original question.

## Local progress is not gap reduction

Distinguish a result that shrinks the distance to the goal from one that is
merely new. Extending a finite verification to a wider range, more moduli, or
more primes produces a fresh artifact and no gap reduction; a finite
computation is not a proof of a universal claim, and repeating it at a larger
bound does not become one. Do not accept a round whose only increment is the
same verification at a larger bound — say which proposition moved, or that
none did.

When Lean is used, inspect the source and a fresh real compiler run, and check
that the encoded theorem means what the original problem says. Do not require
particular filenames.

Say plainly whether the outcome is proved, disproved, computational evidence,
partial progress, a conjecture, or unresolved. Check relevant primary sources
only when novelty is claimed or required by the requested ambition; otherwise
leave novelty unknown rather than demanding a separate audit artifact.

Fill any structured result field required by the active schema, but do not
duplicate the same judgment in extra reports.
