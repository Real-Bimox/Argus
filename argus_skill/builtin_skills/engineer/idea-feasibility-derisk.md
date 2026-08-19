---
name: "Research Reality Probe"
description: "Run the cheapest faithful observation that informs a research idea, preserve the raw result, and leave its interpretation and next move to the Planner."
---

# Research Reality Probe

## Purpose

After an idea has passed method-reasonableness selection, and before committing
substantial compute, obtain one real observation about its binding premise on
available models, data, or systems. This is a source of information, not a
routing gate and not a substitute for idea selection.

For publishable/doctoral work, a successful probe does not waive the ambition
standard: nontrivial technical core, verified originality, claim-relevant
formal/causal grounding, and field-level consequence. Wiring success or easy
feasibility cannot promote a shallow idea.

## How to work

1. Read the research brief and the completed selection reasoning. If technical
   validity, prior-art reduction, originality, significance, falsifiability, or
   resource feasibility is still unresolved, stop before model/API/GPU execution
   and finish selection first. Otherwise identify the selected idea's uncertain
   empirical premise whose answer would most change the plan.
2. Choose the cheapest faithful probe that can inform it. Use real public data or
   the actual system when the claim depends on them; do not replace the premise
   with an easy toy proxy. For a comparative claim, require discriminative
   headroom: the task slice must exercise the proposed mechanism, the baseline
   must not already saturate at the metric ceiling or floor, and the planned
   cases/repeats must be able to resolve the predeclared contrast.
3. Record the setup before running: model/system identity, data slice, comparator
   or control, metric/observation, and the limitations of the probe.
4. Before any paid or model-backed call, inspect the prediction boundary:
   - candidate and baseline code may receive only information available at their
     claimed decision time, never gold labels, expected outcomes, scorer verdicts,
     or fields derived from them;
   - remove or permute hidden labels and confirm candidate predictions do not
     change;
   - execute baselines with the same information and intervention timing. A
     historical trace that already executed an action or a post-hoc verifier is a
     diagnostic, not an online prevention baseline.
5. Run it for real and preserve the command, raw output, and analysis under a
   sensible project path. Reuse existing run conventions instead of creating a
   special de-risk packet.
6. Write a short factual note in `research/RESEARCH_BRIEF.md` or the existing
   experiment log:
   - what was observed;
   - what remains uncertain;
   - plausible explanations, including implementation weakness;
   - paths to the raw material.

Do not emit PASS/FAIL, force a pivot, or automatically schedule another direction.
The Planner reads the stored observation with the rest of the project and decides
what it changes. A wiring smoke test is not evidence for the scientific thesis.
A tie from an easy, ceilinged/floored, or underpowered probe is inconclusive:
redesign the probe rather than treating it as evidence that the method failed.

## Integrity

Never type expected numbers as results, hide failed calls, or relabel synthetic
examples as public evidence. If the probe is not faithful enough to inform the
premise, say so plainly. A result produced by candidate code reading the gold
label is a failed probe, not weak supporting evidence.

## Handoff

Report the observation and its limits in ordinary prose, with paths to the raw
run. Avoid verdict packets and workflow language.
