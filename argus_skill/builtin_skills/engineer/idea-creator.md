---
name: "Idea Creator"
description: "Given IDEA_CANDIDATES.md from idea-discovery, rank candidates and run the cheapest faithful falsification or characterization probe within the operator's budget. Positive, negative, diagnostic, and boundary findings may all justify an experiment plan when they have research value."
---

# Idea Creator — rank, pilot, commit

> Adapted from ARIS `idea-creator` skill (MIT, © 2026 wanshuiyin).

`idea-discovery` streams independent routes; `idea-creator` reviews each route
as soon as it lands, then probes only candidates that are reasonable enough to
deserve real budget. The probe budget is set by the operator and project, not a
universal wall-clock threshold.

For publishable/doctoral selection, the ambition standard is a nontrivial
technical core, verified originality, claim-relevant formal/causal grounding,
and field-level consequence. Feasibility is a separate gate, not compensation
for weakness in one of these four.

## When to invoke

- `research/IDEA_CANDIDATES.md` exists
- Project hasn't yet committed to an experiment plan
- Budget allows a faithful bounded probe (operator-set, not harness-set)

## Workflow

### Step 1 — independently review each completed candidate

A fresh reviewer reads one completed route without waiting for the rest of the
portfolio and judges **novelty × technical_depth × theoretical_foundation ×
stake × tractability × local_feasibility**. The same schema may be used to
summarize the route:

```json
{
  "ranking": [
    {"id": "I-1", "novelty": "high", "technical_depth": "high",
     "theoretical_foundation": "high", "tractability": "med", "stake": "high",
     "local_feasibility": "executable", "rank_score": 0.81,
     "pilot_recommendation": "run"},
    {"id": "I-2", "novelty": "med", "technical_depth": "low",
     "theoretical_foundation": "low", "tractability": "high", "stake": "med",
     "local_feasibility": "conditional", "rank_score": 0.0,
     "pilot_recommendation": "queue"},
    {"id": "I-3", "novelty": "high", "technical_depth": "high",
     "theoretical_foundation": "high", "tractability": "high", "stake": "high",
     "local_feasibility": "unfeasible", "rank_score": 0.0,
     "pilot_recommendation": "drop"}
  ]
}
```

`local_feasibility` ∈ {`executable`, `conditional`, `unfeasible`, `unknown`}
comes straight from the candidate's `Local Feasibility` block (does the core
signal MOVE on a model this box can actually run?). **An `unfeasible` candidate
must NOT be recommended `run`** no matter how novel — a signal that cannot move
locally is a dead pilot (e.g. a safety idea on a frontier API that refuses every
harmful prompt). The reviewer rules on scores; the harness does not impose a
threshold, but piloting an `unfeasible` idea is forbidden — it would only be
killed at the signal-de-risk gate after wasting the pilot.

Likewise, a candidate that is incremental, technically shallow, lacks a genuine
formal/causal foundation, or has no field-level consequence must not be
recommended `run` merely because it is cheap. Reject decorative mathematics:
the foundation score concerns real derivations or mechanism-specific
predictions, not notation density.

Complete this route-local selection from literature, formal/causal analysis,
closest-method reduction attempts, and feasibility evidence before designing or
executing its probe. Do not wait for unfinished routes. Probe outcomes must not
retroactively make an otherwise unreasonable idea selectable. A `queue` or
`drop` candidate receives no model, API, or GPU calls; revise its method case or
reject it first. A `run` recommendation locks that route's
method-reasonableness case for probing; it does not yet choose the final thesis.

### Step 2 — design probes for the top candidates

Only after Step 1 has selected a candidate as `run`, write its
**resource-adaptive probe spec**.
The probe should cheaply test the binding premise or characterize the proposed
phenomenon against a strong reference. Do not force a fixed duration or require
an improvement when a clean null/boundary result would answer the question.
Instantiate the Planner-authored evidence contract: Engineer may choose
implementation details such as batching, caching, file layout, and safe
scheduling, but must not silently change the frozen premise, strongest
comparison, primary observation, interpretation rule, or budget.

```markdown
## Pilot P-{{id}}: <one-line goal>

**Falsifiable hypothesis**: <claim from IDEA_CANDIDATES.md>

**Minimum signal**: <smallest measurement that would already
distinguish hypothesis from null>

**Setup**:
- Models: <subset>
- Prompts: <N samples, source>
- Trial count: <minimum-N for the signal to be visible>
- Token budget: <estimate>

**Stop rules**:
- Signal clearly present → commit to full experiment plan
- Signal clearly absent → record a supported negative or kill the hypothesis,
  depending on whether the result has research value
- Signal ambiguous → enlarge once if justified, then classify honestly
```

### Step 3 — execute pilots in parallel

Run each qualified route's probe via `research-experiment-runner` immediately
after its independent review, while slower discovery routes continue. Use
parallel resources when available and waves when a scarce resource requires
them. The default selection policy is intentionally greedy: the first
independently reviewed probe with an `advance` verdict wins. Do not wait for
every candidate merely to compare finished pilots.

### Step 4 — record verdicts

Each pilot writes:
- `experiments/pilot-{{id}}/RESULTS.md` — measurement summary
- `experiments/pilot-{{id}}/VERDICT.md` — reviewer-written
  engineering-validity and hypothesis-evidence verdict
- the existing `research/ideas/<id>/EVIDENCE.json` four-state record, keeping
  execution validity separate from `untested` / `inconclusive` / `supported` /
  `refuted`

### Step 5 — commit the greedy winner

Materialize the first `advance` verdict as `research/IDEA_SELECTION.json` and
build the full experiment plan around it without waiting for all pilot verdicts.
This does not reopen the Step 1 method-reasonableness decision. If
implementation changed the method or the probe exposed a broken premise in that
selection case, return the candidate upstream for revision instead of asking the
experiment reviewer to re-select it. Later route or probe results remain audit
evidence but do not block or silently replace the selected thesis.

## Anti-patterns

- ❌ Pilot all candidates fully instead of using the cheapest faithful probe
- ❌ Wait for every route or pilot after one independently reviewed probe advances
- ❌ Mark "ambiguous" as commit — ambiguous pilots usually become
  ambiguous full experiments
- ❌ Skip the pivot step when pilot kills — commit-bias is the
  number-one cause of dead-end papers
- ❌ Re-pilot a killed candidate to "make sure" — the kill verdict
  was made on evidence; treat it as final unless the candidate is
  re-specified

## Output contract

Writes per-route review/probe artifacts, a four-state `EVIDENCE.json` for each
probed candidate, `research/IDEA_SELECTION.json`, and the selected candidate's
`research/EXPERIMENT_PLAN.md`.
