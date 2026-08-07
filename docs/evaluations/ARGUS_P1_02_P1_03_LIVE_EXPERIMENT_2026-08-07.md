# ARGUS-P1-02 / P1-03 controlled live experiment

Date: 2026-08-07  
Source baseline: `bc553f04`  
Backend/model: Pi 0.84.1 via GitHub Copilot, `gpt-5-mini`, low reasoning  
Runs: 20 real provider-backed runs, all sequential and isolated

## Method

Two small Python repositories were generated from identical frozen baselines per run:

- strict scalar/iterable normalization;
- ordered case-insensitive header merging.

The session experiment used a required three-round protocol so every policy had the
same intended work: repository map, first bounded repair, final repair. Each policy
ran both tasks twice (`n=4` per policy). Success required both Reviewer `done` and an
external held-out evaluator, not only visible tests.

The Skill experiment used one-turn tasks with incomplete visible tests. The relevant
condition exposed one high-fit Engineer Skill plus one unrelated SQL Skill. The
control exposed only the unrelated Skill. Each condition ran both tasks twice
(`n=4`). Raw provider/tool traces were used to count actual Skill reads and repeated
repository reads.

## P1-02 results

| Policy | Runs | Reviewer done | Held-out pass | Joint success | Mean wall time | Mean explicit prompt estimate | Mean repeated repo reads | Mean Engineer repeated reads | Mean provider cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fresh | 4 | 3/4 | 3/4 | 2/4 | 185.9 s | 13,434 tok | 7.75 | 4.75 | $0.02860 |
| mission | 4 | 4/4 | 4/4 | 4/4 | 158.8 s | 8,934 tok | 4.50 | 0.50 | $0.02993 |
| rolling (rotate after 2 turns) | 4 | 2/4 | 2/4 | 1/4 | 161.3 s | 10,173 tok | 4.25 | 2.00 | $0.02558 |

Compared with `fresh`, mission-scoped sessions produced:

- 14.6% lower wall time;
- 33.5% lower explicit prompt estimate;
- 41.9% fewer repeated repository reads;
- 89.5% fewer repeated Engineer reads;
- higher joint success in this sample (4/4 versus 2/4).

The trade-off was 43.8% more provider-reported input tokens and 4.7% higher cost,
mostly from the retained/cached conversation context. Prompt reduction therefore did
not translate into lower total provider input. The two-turn rolling boundary was not
safe: rotation caused stale-stage confusion in observed runs and joint success fell
to 1/4.

**Decision:** keep production default unchanged for now; advance `mission` to a
larger real-project canary. Stop the current rolling policy (`max_turns=2`) rather
than ship it. A revised rolling policy needs a rotation handoff that explicitly
carries the current gate/stage before another trial.

## P1-03 results

| Condition | Runs | Reviewer done | Held-out pass | Useful Skill opened | Wrong Skill opened | Mean wall time | Mean explicit prompt estimate | Mean provider cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| unrelated-only control | 4 | 4/4 | 0/4 | 0/4 | 0/4 | 63.6 s | 4,767 tok | $0.01034 |
| relevant + unrelated | 4 | 4/4 | 4/4 | 4/4 | 1/4 | 81.3 s | 4,859 tok | $0.01228 |

The relevant Skill body was actually read in every treatment run; this was not a
prompt-only exposure. The four treatment runs read 3,794 useful Skill bytes in total.
One run also opened the 294-byte unrelated SQL Skill, so false reuse was non-zero
(1/4). Control agents did not open the unrelated Skill, yet every control Reviewer
returned `done`; all four then failed held-out checks. This demonstrates both a real
quality gain from on-demand Skill use and a gap in Reviewer acceptance when visible
tests are incomplete.

Treatment overhead versus control was:

- 27.8% higher wall time;
- 1.9% higher explicit prompt estimate;
- 18.8% higher provider cost;
- 62.6% higher provider-reported input tokens, almost entirely cached context
  (uncached input increased only 2.5%).

**Decision:** retain agent-native on-demand Skill loading—the quality signal is
strong in this controlled sample—but do not claim cost reduction. Next work is to
reduce discovery/tool overhead, investigate the one false reuse, and add held-out
acceptance probes to Reviewer evaluations.

## Limitations

- One backend/model and two controlled repositories; these are real coding-agent
  calls, not production user trajectories.
- Four runs per condition are enough to expose large failures, not to estimate a
  stable population effect.
- Skill tasks explicitly asked the Agent to inspect clearly relevant guidance; a
  natural-incidence study is still required.
- Wall time includes provider variance. Runs were sequential, not simultaneous.
- Raw traces remain local because they contain machine paths and provider session
  material; only aggregate, disclosure-safe results belong in the repository.

## Next experiment

1. Replay `fresh` and `mission` on disclosure-safe slices of two real projects.
2. Revise rolling rotation to carry an explicit current-stage handoff, then rerun.
3. Repeat Skill A/B on at least ten naturally occurring tasks without an explicit
   “inspect Skills” instruction.
4. Measure bytes opened and false reuse by role, and gate Reviewer acceptance with
   held-out or independently generated edge cases where available.
