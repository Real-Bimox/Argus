---
name: "Idea Creator"
description: "Given IDEA_CANDIDATES.md from idea-discovery, rank candidates and run the cheapest faithful falsification or characterization probe within the operator's budget. Positive, negative, diagnostic, and boundary findings may all justify an experiment plan when they have research value."
---

# Idea Creator — rank, pilot, commit

> Adapted from ARIS `idea-creator` skill (MIT, © 2026 wanshuiyin).

`idea-discovery` produces candidates; `idea-creator` first decides which ideas
are reasonable enough to deserve real budget, then probes only those selected
survivors. The probe budget is set by the operator and project, not a universal
wall-clock threshold.

For publishable/doctoral selection, the ambition standard is a nontrivial
technical core, verified originality, claim-relevant formal/causal grounding,
and field-level consequence. Feasibility is a separate gate, not compensation
for weakness in one of these four.

## When to invoke

- `research/IDEA_CANDIDATES.md` exists
- Project hasn't yet committed to an experiment plan
- Budget allows a faithful bounded probe (operator-set, not harness-set)

## Workflow

### Step 1 — rank candidates

Reviewer agent (gpt-5.5 via `author` route) reads
`IDEA_CANDIDATES.md` and ranks by joint **novelty × technical_depth ×
theoretical_foundation × stake × tractability × local_feasibility** — read each
candidate's ambition-gate and `Local Feasibility` blocks:

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

Complete this selection from literature, formal/causal analysis, closest-method
reduction attempts, and feasibility evidence before designing or executing any
probe. Probe outcomes must not be used to retroactively make an otherwise
unreasonable idea selectable. A `queue` or `drop` candidate receives no model,
API, or GPU calls; revise its method case or reject it first. A `run`
recommendation locks that candidate's method-reasonableness case for probing; it
does not yet choose the single final paper thesis.

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

Run probes via `research-experiment-runner`. For paper selection, launch all
independent `run`-recommended probes concurrently when resources allow. If a
shared scarce resource requires waves, record that constraint and keep the lead
doing source verification or analysis while the probes run; do not select an
idea from whichever serial probe happened to finish first.

### Step 4 — record verdicts

Each pilot writes:
- `experiments/pilot-{{id}}/RESULTS.md` — measurement summary
- `experiments/pilot-{{id}}/VERDICT.md` — reviewer-written
  engineering-validity and hypothesis-evidence verdict
- the existing `research/ideas/<id>/EVIDENCE.json` four-state record, keeping
  execution validity separate from `untested` / `inconclusive` / `supported` /
  `refuted`

### Step 5 — commit to one candidate

The Planner reads all pilot verdicts and chooses which already-selected
candidate has the strongest empirical case for a full experiment plan. This
does not reopen the Step 1 method-reasonableness decision. If implementation
changed the method or the probe exposed a broken premise in that selection
case, return the candidate upstream for revision instead of asking the
experiment reviewer to re-select it. This is where one final thesis is chosen
from the probe-eligible candidates. The chosen candidate goes into
`research/EXPERIMENT_PLAN.md` (input to the `plan` stage).

## Anti-patterns

- ❌ Pilot all candidates fully instead of using the cheapest faithful probe
- ❌ Mark "ambiguous" as commit — ambiguous pilots usually become
  ambiguous full experiments
- ❌ Skip the pivot step when pilot kills — commit-bias is the
  number-one cause of dead-end papers
- ❌ Re-pilot a killed candidate to "make sure" — the kill verdict
  was made on evidence; treat it as final unless the candidate is
  re-specified

## Output contract

Writes `research/IDEA_RANKING.json`,
`experiments/pilot-*/{RESULTS,VERDICT}.md`, and updates
`research/IDEA_CANDIDATES.md` with `pilot_status` plus
`research/ideas/<id>/EVIDENCE.json` per probed candidate. The final commit is
recorded in `research/EXPERIMENT_PLAN.md`.
