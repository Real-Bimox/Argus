---
name: "Math Research Planning"
description: "Plan dynamic mathematical research inside scope, solve, and review without creating Math-specific role or lifecycle machinery."
---

Plan from the mathematical structure, not a fixed workflow. Pick the step most
likely to settle a real uncertainty: derive a lemma, seek a counterexample,
compute examples, read a source, try a different proof idea, or formalize a
delicate step.

Objective mode in `research/PIPELINE_STATE.json`: `targeted` (one goal — ruling
out a sufficient criterion is not solving it) or `exploratory` (partial results).
If unset, ask. Prefer gap reduction over tractability; a finite check at a larger
bound reduces nothing. Check `research/ROUTE_LEDGER.json` — a strategy-retired
route needs a different mechanism. Targeted at `develop`/`certify`: maintain
`research/PROOF_GRAPH.json`.

A failed attempt is information, not success; use what it revealed to choose a
genuinely different move. When strengthening a result, compare against the
strongest one available.

Use Lean only when it reduces uncertainty; check novelty only when the result is
presented as new. Cheap falsification often precedes a long proof; a construction
must satisfy every condition; a formal statement must match the original. These
are options, not mandatory phases.
