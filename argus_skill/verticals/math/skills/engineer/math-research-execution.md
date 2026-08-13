---
name: "Math Research Execution"
description: "Execute mathematical scope and solve work with honest result classification, statement fidelity, and optional real Lean compilation."
---

Do the mathematics in the form that best fits the problem. Distinguish a proof,
counterexample, construction, finite experiment, formal verification, known
result, and conjecture; do not describe one as another.

Start from the exact question and the requested bar. If a complete proof is
required, useful failures and computations do not make the mission complete.
Keep a short note about a failed route in the existing `CHECKPOINT.md` when it
will help the next attempt, then change the mathematical approach.

Use ordinary working files suited to the task. Do not create process-only
planning, audit, status, or evidence-packet files merely to satisfy the
workflow. The theorem, proof, counterexample, code, or formal source is the
evidence, and no fixed bundle of output filenames is required.

Two files are exceptions once a `targeted` project has settled on a route and
reached `develop` or `certify`: `research/PROOF_GRAPH.json` records what still
stands between the current state and the goal, and `research/ROUTE_LEDGER.json`
records which routes were retired and why. They are not process paperwork —
without them "how hard was this step" silently replaces "how much closer did
this get us", and a retired route gets retried. Under `explore` neither is
required.

When continuing earlier work, compare the new result with the strongest prior
result that matters. Explain the mathematical improvement directly; no special
tracking file is required.

Lean is optional; a committed `.lean` file is not. Once one exists, completing a
stage requires it to show a fresh real compiler run with no proof holes, so run

    python -m argus_skill.verticals.math.lean_evidence verify Main.lean \
        --statement-fidelity statement_fidelity.md

which compiles the source and records the answer beside it, stamped with the
source hash. Editing the source invalidates that record; re-run it.

Compilation checks the theorem you encoded, not the one you meant, so the
separate `statement_fidelity.md` states which objects, quantifiers, hypotheses,
and conclusion the formal statement carries and names the declarations it
describes. A compiling proof of a mistranslated statement is the most expensive
wrong answer available here.

If the toolchain or a library such as Mathlib is missing, the run is recorded as
unverified and still blocks: that is an environment fact rather than a
mathematical verdict, but an unverified formalization is not evidence. Argue in
prose instead of committing a `.lean` file you cannot check.

Before investing heavily in a new conjecture, a small counterexample search may
be useful. For a construction, check that the object satisfies every condition.
Use literature only when a known result matters or when claiming novelty. These
are mathematical choices, not boxes that must all be checked.
