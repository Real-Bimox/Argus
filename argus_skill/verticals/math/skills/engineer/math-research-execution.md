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
        --statement-fidelity statement_fidelity.md --claim C1

which compiles the source, records the answer beside it stamped with the source
hash, and — because of `--claim` — writes the outcome into the claim ledger as
mechanical evidence. Editing the source invalidates that record; re-run it. If
the host has Mathlib installed it is used automatically, so `import Mathlib`
needs no extra flag. `--claim` is the only way mechanical evidence is ever
written: there is no flag that lets you record a compiler verdict you did not
get, and asking for one is a bug report rather than a request. Formalizing
several claims in one directory is fine and needs no filename scheme of your
own: each run archives its own certificate under `research/lean/certificates/`
and the claim cites that, so reusing the names above does not cost the previous
claim its evidence.

Compilation checks the theorem you encoded, not the one you meant, so the
separate `statement_fidelity.md` states which objects, quantifiers, hypotheses,
and conclusion the formal statement carries and names the declarations it
describes. A compiling proof of a mistranslated statement is the most expensive
wrong answer available here. The document is hashed into the compiler result, so
rewriting it afterwards invalidates the run rather than quietly re-labelling it.
Nothing checks that the document is *true* — that half of the argument is yours,
and it is why a proved claim still reports what nobody verified.

If the toolchain or a library such as Mathlib is missing, the run is recorded as
unverified and still blocks: that is an environment fact rather than a
mathematical verdict, but an unverified formalization is not evidence. Argue in
prose instead of committing a `.lean` file you cannot check.

## Recording what the project believes

`research/MATH_STATE.json` is the ledger of claims and what supports each one.
Status is derived, never written: `closed_kernel` is what a compiler earned, and
there is no argument you can type that produces it. Keep it current with

    S="python -m argus_skill.verticals.math.math_state"

    # the problem statement every claim is stated against, once per project
    $S context --id ctx --statement "..." --define "term=meaning"

    # one mathematical assertion; --formal-file points at the Lean source
    $S claim --id C1 --context ctx --statement "..." --formal-file research/lean/Main.lean

    # a result taken from elsewhere: holds C1 at conditional_kernel until retired
    $S assume --claim C1 --id RH --statement "..." --source "Riemann 1859, Thm 1.1"

    # one decomposition of a goal into obligations; records a plan, confers nothing
    $S route --id R1 --goal C1 --obligation L1 --obligation L2

    # your own or a reviewer's opinion, recorded as an opinion
    $S judge --claim C1 --verdict supports --by "reviewer:alice"

    # the next version, when the definitions or the theorem change
    $S revise-context --id ctx --define "term=corrected meaning"
    $S revise-claim --id C1 --formal-file research/lean/Main.lean
    $S revise-claim --id C1 --retire "RH=Lemma 2 gives the bound unconditionally"

    # after revising a context: every claim stated against it, one at a time
    $S revise-claim --id C1 --use-current-context

    # what it all adds up to, and structural defects
    $S show --claim C1
    $S check --project-root .

Record a context and a claim before formalizing, so `verify --claim` has
something to attach to. Record an assumption the moment the proof starts leaning
on an unproved result — an undischarged assumption is the difference between
`conditional_kernel` and `closed_kernel`, and it is invisible unless written
down. Record a route when a goal splits into steps, so a retired decomposition
is not retried. Record a judgement when you or a reviewer have read a proof that
no checker can check.

Revising a context supersedes it for every claim stated against it, and `check`
reports each one as `claim_context_outdated` until you say what happened to it.
That is the point: a corrected definition can turn a proved theorem into a
statement about something else, so the claims do not follow the context along
silently. Re-state each one with `revise-claim --id ID --use-current-context`
once you have read it against the new definitions and it still says what you
mean — and if it no longer does, restate the theorem instead.

Two things this ledger deliberately will not let you do. Restating a claim mints
a new version and the evidence bound to the previous statement stops counting —
that is the cost of retranslating, not a bug to work around. And you cannot stop
standing on an assumption without writing why: `revise-claim --retire ID=reason`
takes the reason because deleting a dependency asserts the proof does not need
it, which is itself a mathematical claim.
Before investing heavily in a new conjecture, a small counterexample search may
be useful. For a construction, check that the object satisfies every condition.
Use literature only when a known result matters or when claiming novelty. These
are mathematical choices, not boxes that must all be checked.
