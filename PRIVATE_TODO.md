# Private Repository TODO

> Scope: private repository `lbx154/argus-skill` after synchronizing its `main`
> branch to public `lbx154/Argus:main` on 2026-08-06.
>
> Public `main` is the code authority. Private `main` may carry only explicitly
> approved, allowlisted private overlays such as this TODO. Do not merge the old
> private history wholesale.

# Team Product and Architecture Backlog

This backlog consolidates issues observed by Shan, Xuchuan, Jinlang, and current
Argus users. Priorities reflect impact on whether a user can finish a real goal,
not implementation convenience.

## Collaboration rules

- Every item below gets one DRI, one issue, and one topic branch. Keep unrelated
  storage, prompt, session, and vertical refactors separate.
- Start with a reproducible trace from a real project. A source-code smell alone is
  not enough to justify a behavior change.
- Each PR must state baseline behavior, intended behavior, migration/rollback plan,
  focused tests, and the observable metric it should move.
- Do not replace Agent judgment with keyword rules. Encode authority and state
  transitions explicitly, then let the responsible role make the semantic decision.
- Do not require roles to emit strict JSON or conform to a model-facing output
  schema. Capture required semantics through tool calls, runtime-owned state, or
  tolerant extraction from the role's natural response.
- Treat a Planner mission as a working plan, not a fixed contract. User goals and
  safety/authority limits stay fixed; technical choices can change when later
  evidence points to a better route.
- Every gate, assertion, wrapper, fallback, and compatibility path must have a clear
  job. Do not add layers “just in case,” and remove duplicates once one layer owns
  the check. Keep security, authority, data-integrity, and process-isolation
  protections unless an equivalent safeguard is proven.
- Status labels: `unassigned`, `investigating`, `design-review`, `implementing`,
  `experimenting`, `blocked`, `done`.

## Priority map

| ID | Priority | Severity | Urgency | Suggested DRI | Dependencies |
| --- | --- | --- | --- | --- | --- |
| ARGUS-P0-01 | P0 | Critical | Done | Runtime/state | none |
| ARGUS-P0-02 | P0 | Critical | Done | Mission loop | P0-01 checkpoint invariants |
| ARGUS-P0-03 | P0 | Critical | Done | Manager/contract | none |
| ARGUS-P0-04 | P0 | High | Done | Planner/goal | P0-03 |
| ARGUS-P1-01 | P1 | High | Next | Mission progress/evaluation | P0-02, P0-03, P0-04 |
| ARGUS-P1-02 | P1 | High | Controlled experiment done | Agent/session integration | next: real-project canary |
| ARGUS-P1-03 | P1 | Medium | Controlled experiment done; revise | Skill system | legacy migration remains |
| ARGUS-P1-04 | P1 | Medium | Next | Architecture/verticals | behavior baseline first |
| ARGUS-P1-05 | P1 | High | Next | Role prompts/UX | P0-03, P0-04 |
| ARGUS-P1-06 | P1 | High | Next | Runtime/architecture | behavior baseline first |
| ARGUS-P2-01 | P2 | Medium | Later spike | Persistence | P0 state semantics stable |
| ARGUS-P2-02 | P2 | Medium | Continuous | Evaluation/observability | supports all items |

---

## ARGUS-P0-01 — Make human approval and resume transactionally consistent

**Status: completed.** Implemented in `e9bfae30caf7` (release
`0.1.1+ef1ffc08e1f034b6`). The full test suite passed (4,396 collected; existing
skips unchanged).

**Problem.** Approving an Argus decision and resuming could leave backlog, campaign,
daemon, decision-card, or lifecycle state at different revisions. The user could
then be unable to continue the goal.

**Completed work**

- [x] Bound each new decision to project/session id, campaign generation, backlog
      item id, decision id, and expected revision.
- [x] Added compare-and-swap checks before Manager calls or state mutation; stale
      decisions now return `stale` without changing current state.
- [x] Persisted decision resolution, continuation creation, dependency rewiring,
      resolution identity, and restart intent in one atomic backlog update.
- [x] Made retries and concurrent submissions idempotent: the first request returns
      `accepted`, and the same request returns `already_applied` with the original
      continuation.
- [x] Added idempotent continuous-state reconciliation plus durable transcript, UI,
      and audit records for accepted or stopped decisions.
- [x] Added tests for stale revisions and campaign generations, concurrent and
      repeated submissions, reopened state, injected write failure, and stop replay.
- [x] Rebuilt Web/TUI release artifacts and ran the complete test suite.

**Acceptance criteria**

- A decision can be submitted repeatedly with one resulting mission transition.
- Stale approval never mutates current state.
- Reopening the project reproduces the same resolved card, continuation, and campaign
  intent from durable state.
- The API reports `accepted`, `already_applied`, or `stale`; never a generic state
  mismatch.

---

## ARGUS-P0-02 — Replace the hard 24-round interruption with progress-aware continuation

**Status: completed.** Implemented and tested in `e9bfae30caf7`.

**Problem.** `SupervisedConfig.hard_escalate_rounds=24` previously force-ended a
mission when Reviewer kept returning `continue`. Long-horizon missions can remain
productive beyond this boundary, and their observable indicators are often
non-monotonic. A stronger proof invariant may temporarily break proved obligations;
a coherent refactor may increase failing tests before interfaces converge; and a
negative experiment may invalidate an intermediate hypothesis while reducing
uncertainty. The fixed boundary fragmented one task frontier and could turn a
bounded, productive local regression into an unrelated replacement mission.

**Completed work**

- [x] Reused the Reviewer-owned `planner_report.forward_progress` judgment instead of
      inferring progress from file count, pass count, benchmark score, or keywords.
- [x] Added `forward_progress` and `plan_signal` to durable round-review events.
- [x] Allowed missions with an explicit progress judgment to cross round 24,
      including a bounded local regression that has not reached the stall threshold.
- [x] Kept operator stop, budget, backend-failure, decision-timeout, semantic-stall,
      no-output, and final `max_rounds` protections active.
- [x] Kept `CHECKPOINT.md` as the mission baton so continuation does not replace the
      objective merely because a round counter was reached.
- [x] Updated Reviewer guidance to separate productive internal work from a genuine
      external blocker and to state the progress judgment explicitly.
- [x] Added a real 26-round regression test: round 24 temporarily regresses, the
      mission recovers, and Reviewer accepts it at round 26.

**Acceptance criteria**

- A productive long-horizon mission can run beyond 24 rounds without replacement
  even when one or more local indicators temporarily regress.
- A truly stagnant loop still terminates under budget/no-progress policy.
- Continuation preserves the objective and durable checkpoint while exposing why the
  boundary was crossed.

---

## ARGUS-P0-03 — Keep Planner missions revisable

**Status: completed.** Implemented in `ec32c0c0ee28` (release
`0.1.1+52dd12145f5c7077`).

**Problem.** A Planner direction could become an unintended hard constraint after it
was written into a mission, allowing an early, lower-information choice to override
later counterexamples or better alternatives.

**Completed work**

- [x] Kept user goals, safety, authority, trust, permission, and resource boundaries
      separate from Planner-authored technical strategy.
- [x] Persisted each mission’s working hypothesis, goal contribution, expected local
      regressions, decision rule, and provenance in backlog and mission context.
- [x] Let Reviewer report a challenged assumption, a better alternative, and the
      affected authority layer without using a strict JSON schema.
- [x] Made `done` or `continue` plus `PLAN_SIGNAL=reconsider` stop the old mission
      instead of silently dispatching stale downstream work.
- [x] Routed every challenge through a Manager-owned `keep`, `revise`, `replace`, or
      `ask_operator` decision before Planner acts.
- [x] Routed operator-owned changes into the durable decision-card path; technical
      alternatives do not become unnecessary operator blockers.
- [x] Recorded challenge, adjudication, commit time, and revision latency in durable
      events.
- [x] Added the `0d-3` replay: the `no-gap` route replaces `skip-zero`, and the old
      plan nodes are atomically superseded before more stale work runs.

**Acceptance criteria**

- A Planner strategy remains a revisable working plan after mission serialization.
- Later evidence receives a recorded Manager decision before disputed work continues.
- The `0d-3` replay selects the alternative against the user goal and does not rerun
  the stale `skip-zero` path.
- User-owned boundaries remain enforced, and revision latency is measurable.

---

## ARGUS-P0-04 — Improve Planner mission quality and measure goal completion

**Status: completed.** Implemented in `ec32c0c0ee28`; the full Python suite passed
(4,451 collected, existing skips unchanged), together with Web 134/134 and TUI
224/224 tests.

**Problem.** Planner missions could optimize a convenient local checker without
stating how the work advances the user’s actual goal, what may regress, or what
evidence should change direction.

**Completed work**

- [x] Required Planner missions to state a revisable hypothesis, goal-frontier
      contribution, expected temporary regressions, decision rule, and decisive
      acceptance check.
- [x] Added one bounded repair pass when Planner omits mission-quality context instead
      of accepting a weak local-checker task.
- [x] Applied the same quality contract to continuous and bounded-DAG planning.
- [x] Persisted the quality context in backlog rows, mission packets, Mission View,
      and the Web task inspector.
- [x] Told Planner that a green checker verifies an artifact but does not alone prove
      progress toward the operator goal.
- [x] Fed Reviewer challenges, negative evidence, and replacement rationale into the
      next planning cycle while preserving existing duplicate-work protection.
- [x] Added goal-level metrics for mission acceptance, forward progress, replans,
      duplicate work, time to first useful progress, terminal completion, and
      unfinished-goal age.
- [x] Added fixed replays and regression tests for weak mission repair, plan
      replacement, persistence, metrics, prompt budgets, and user-visible rendering.

**Acceptance criteria**

- A mission cannot enter the new Planner path without saying how it advances the
  goal and what evidence changes the plan.
- Checker success alone is not treated as a goal-level outcome.
- Goal progress and wasted/replanned work are visible in durable metrics.
- The fixed `0d-3` replay exits the stale path and commits a coherent replacement.

---

## ARGUS-P1-01 — Model non-monotonic progress in long-horizon tasks

**Problem.** Long-horizon progress is multidimensional and often non-monotonic.
During one coherent trajectory, selected proxies may temporarily worsen even while
the global task state improves: proof strengthening can create repair obligations, a
software migration can break intermediate tests while removing structural risk, and
a research or optimization run can lower a headline metric while eliminating a bad
hypothesis. Requiring a small set of counters to rise every round—or every
intermediate state to be locally green—misclassifies bounded, explained regression
as failure. Conversely, “non-monotonic” must not become an excuse for churn:
temporary regressions need an attributable cause, explicit scope, and recovery or
exit conditions.

**Work packages**

- [ ] Audit representative missions and Reviewer verdicts across software/refactor,
      research/optimization, and proof workflows, with Verus retained as one
      concrete case rather than the governing abstraction.
- [ ] Define a generic persisted task frontier containing the objective and
      invariants, current hypothesis/strategy, artifacts and evidence, resolved/new/
      regressed obligations, remaining work clusters, relevant proxy measurements,
      uncertainty, and the next decision point.
- [ ] Define progress over semantic frontier transitions rather than a scalar score.
      Progress may be an improved artifact, discharged risk, reduced uncertainty, or
      a justified transformation that introduces bounded repair debt; no individual
      field is required to improve monotonically.
- [ ] Require a regression envelope when local state worsens: what changed, why the
      regression is expected, its permitted scope/budget, how recovery will be
      recognized, and what evidence triggers replan or abandonment.
- [ ] Plan coherent frontier transitions such as “change the shared abstraction and
      repair its affected cluster,” not “make the next convenient checker green.”
- [ ] Teach Reviewer to distinguish bounded expected regression, unsupported or
      expanding regression, information-gaining failure, genuine recovery, and
      repeated unchanged failure.
- [ ] Preserve exact diagnostics, causal hypotheses, accepted repair debt, and
      frontier state across fresh sessions and process restarts.
- [ ] Add end-to-end fixtures spanning invariant strengthening, multi-module
      refactoring, and research/optimization search, each with temporary regression,
      multi-round recovery or justified abandonment, and a goal-level outcome.

**Acceptance criteria**

- Planner and Reviewer neither reject a valid route solely because a selected proxy
  temporarily worsens nor accept a route solely because one proxy improves.
- Every tolerated regression is attributable, bounded, visible in durable state, and
  paired with recovery and exit conditions.
- Repeated unchanged failures or expanding unexplained regressions still trigger
  diagnosis, replan, escalation, or termination.
- A long trajectory remains one coherent, inspectable task frontier across rounds,
  including its local setbacks and recovered state.

---

## ARGUS-P1-02 — Design a bounded role-session lifecycle

**Status: controlled live experiment complete; real-project canary remains.**
`60060c38` implements `fresh`, `mission`, and `rolling`; production still defaults
to `fresh`. Twenty real provider runs are reported in
`docs/evaluations/ARGUS_P1_02_P1_03_LIVE_EXPERIMENT_2026-08-07.md`: mission achieved
4/4 joint success on controlled matched tasks, fresh 2/4, and the current two-turn
rolling policy 1/4. Advance mission to a larger canary, stop this rolling
configuration, and leave the production default unchanged for now.

**Problem.** Manager reuses a session, while Planner, Engineer, and Reviewer normally
start fresh sessions. Fresh sessions repeat repository exploration and spend time and
Tokens; indefinitely long sessions accumulate stale context and reduce output quality.

**Work packages**

- [x] Measure prompt size, provider Tokens, wall time, repeated repository reads,
      Reviewer verdict, and held-out correctness by role across two controlled
      repository tasks with two replicates each. Raw traces remain local; the repo
      stores disclosure-safe aggregates. Real user trajectories remain the next canary.
- [x] Complete the fresh/mission/rolling live comparison and decide: versus fresh,
      mission reduced wall time 14.6%, explicit prompt estimate 33.5%, and repeated
      repository reads 41.9%, with joint success 4/4 versus 2/4. Current rolling
      achieved only 1/4 joint success, so stop that configuration.
- [x] Implement a small role-isolated capsule containing only objective revision,
      repository map, inspected paths, latest decisive output, open items,
      checkpoint pointer, and session counters—not the transcript.
- [ ] Complete every rotation trigger. Turn/Token limits, objective/branch/model/
      backend changes, resume failure, backend failure, and path-map refresh are
      implemented. Repeated contradiction, Reviewer-detected confusion, and model
      quality degradation still need explicit role signals rather than keyword rules.
- [x] Isolate Planner, Engineer, and Reviewer capsules/threads. Reviewer does not
      inherit Engineer private reasoning, and role sessions do not write
      Manager-owned pipeline state.
- [x] Drop only the affected thread after resume/backend failure and restart from
      the durable capsule, mission packet, and checkpoint; the same design supports
      resumable and fresh-only providers.

**Acceptance criteria**

- [x] Mission reduces repeated exploration, wall time, and explicit prompt on
      controlled live matched tasks. Provider input Tokens rose 43.8% and cost 4.7%,
      so total Token/cost reduction is not claimed.
- [x] In the controlled pairing, mission held-out correctness plus Reviewer acceptance
      was 4/4 versus fresh at 2/4; a real-project canary still must test external validity.
- [x] Context rotation is explicit, observable, and recoverable across process restart.
- [x] The design works with resumable and fresh-only coding-agent backends.

---

## ARGUS-P1-03 — Finish coding-agent-native, on-demand Skill use

**Status: controlled live experiment complete; cost acceptance failed and legacy
migration remains.** `43a76917` and `60060c38` provide the implementation. The live
A/B in `docs/evaluations/ARGUS_P1_02_P1_03_LIVE_EXPERIMENT_2026-08-07.md` ran four
relevant and four control conditions: the relevant body was opened 4/4 and passed
held-out checks 4/4 versus control at 0/4; a wrong Skill was opened in 1/4 treatment
runs. Quality improved strongly, but wall time rose 27.8% and provider cost 18.8%, so
this item needs optimization rather than a completed label.

**Work packages**

- [x] Audit Manager, Planner, Engineer, and Reviewer prompts and backend adapters;
      remove direct Manager role-Skill and software-grounding Skill-body injection,
      plus duplicate path wrappers.
- [x] Define the minimal contract: project → active vertical/domain → global; OWN
      guidance precedes cross-role REFERENCE guidance within a layer; read a body
      only after a clearly high-fit description, with no harness matcher/scorer.
- [x] Cover Codex, Claude, Copilot, OpenCode, and Pi adapters. Pi uses explicit
      `--skill` with ambient discovery disabled; the other backends use the same
      role-path fallback. Parameterized contract tests cover the matrix.
- [x] Complete a controlled live measurement of files actually opened, bytes read,
      Tokens, cost, wall time, useful/false reuse, Reviewer verdicts, visible tests,
      and held-out tests. Relevant bodies were read 4/4 and moved held-out success
      from 0/4 to 4/4; false reuse occurred in 1/4. A natural-incidence study without
      an explicit Skill-inspection instruction remains.
- [x] Make Agent-authored role Skills immediately discoverable from stable library
      roots; prompts retain paths rather than a body snapshot, so no daemon restart
      or giant-prompt rebuild is required.
- [ ] Keep legacy compatibility fields until migration replays with old event/session
      fixtures prove that existing runs remain readable; no fields were removed yet.

**Acceptance criteria**

- [x] No ordinary mission prompt contains full non-role Skill bodies by default.
- [x] Agents can load relevant Skills on demand through Pi's native loader or the
      portable file-tool paths.
- [ ] **Not met.** Completion quality rose from 0/4 to 4/4, but explicit prompt grew
      1.9%, wall time 27.8%, and provider cost 18.8%. Keep on-demand loading and next
      reduce discovery/tool overhead.

---

## ARGUS-P1-04 — Decouple vertical semantics from core

**Problem.** Core still contains vertical-specific concepts and names, including
paper/research target and full-paper completion surfaces. This reverses the intended
dependency direction and makes a new vertical inherit assumptions from another.

**Work packages**

- [ ] Produce an import/symbol inventory of vertical-specific names under
      `argus_skill/core`, `life/supervisor`, shared prompts, and event payloads.
- [ ] Classify each occurrence as generic contract, compatibility adapter, or true
      vertical leakage. Do not mechanically rename generic research concepts.
- [ ] Define dependency direction: core owns generic lifecycle/authority/event
      protocols; each vertical declares stages, completion strength, role guidance,
      evidence schema, and optional extensions through a narrow interface.
- [ ] Move paper/venue/full-paper policy out of core into the research vertical or a
      registered capability. Keep only generic completion-source ranking in core if
      multiple verticals genuinely share it.
- [ ] Replace direct vertical imports with registration/protocol calls and fail
      visibly for missing/incompatible plugins.
- [ ] First land behavior-preserving moves with contract tests; remove compatibility
      adapters only in later PRs.
- [ ] Add a minimal non-research test vertical proving core can run without paper,
      venue, or research-target symbols.

**Acceptance criteria**

- Core imports no concrete vertical package.
- Adding a vertical requires implementing one documented interface, not editing
  central conditionals.
- Existing vertical behavior and persisted state remain compatible.

---

## ARGUS-P1-05 — Make user-facing output clear and natural

**Problem.** Some Argus messages read like generated process notes: they repeat the
request, pile up headings, use abstract language, and bury the result. Users should
not have to decode the output to learn what happened or what Argus needs from them.
A bare verdict such as `NO-GO` is a common example: it may be useful internally, but
it tells the user neither what failed nor what happens next.

Argus should write like a good teammate. Lead with the result, explain the important
tradeoff in plain language, point to concrete evidence, and say when the answer is
uncertain or has changed. The reasoning visible to users should be easy to follow:
what changed, which options mattered, and why one was chosen. This is not about
adding a human persona or exposing a raw thought transcript.

**Work packages**

- [ ] Collect real CLI, Web, notification, and decision-card examples that users find
      hard to read or obviously machine-written. Pair each with a short human rewrite.
- [ ] Keep internal role traffic out of user-facing messages unless it helps the user
      make a decision or understand a failure.
- [ ] Do not show bare internal verdicts such as `GO`, `NO-GO`, `REVISE`, or
      `BLOCKED`. If a status is useful, follow it with a plain-language reason and the
      next action. For example: “Cannot continue yet: the validator still fails on X.
      Argus will try Y next; no user action is needed.”
- [ ] Put the answer or current status first. Follow with the reason, evidence, and
      next action only when they add value.
- [ ] Replace generic claims with concrete facts: the file changed, test that failed,
      decision waiting, result found, or uncertainty that remains.
- [ ] Cut repeated summaries, stock transitions, excessive headings, inflated praise,
      and fake certainty. Do not implement this as a keyword blacklist.
- [ ] When Argus makes or revises a choice, explain the deciding tradeoff and what new
      evidence would change the decision.
- [ ] Make questions specific: ask for one decision, explain why it belongs to the
      user, and state what happens for each option.
- [ ] Tune length and detail for each surface instead of using one response template
      everywhere.
- [ ] Run blind human review on matched outputs and check comprehension, preference,
      factual accuracy, and time to find the next action.

**Acceptance criteria**

- Users can identify the result, supporting evidence, and next action without reading
  internal logs.
- Blind reviewers prefer the revised output and answer comprehension questions more
  accurately, with no drop in factual correctness.
- Uncertainty and changes of mind are stated plainly rather than hidden behind a
  confident summary.
- No user-facing message stops at a label such as `NO-GO`; it says what is blocked,
  why, and what Argus or the user should do next.
- Questions are understandable without knowing Argus’s internal role vocabulary.

---

## ARGUS-P1-06 — Reduce accidental complexity in the runtime

**Problem.** Argus has accumulated duplicate checks, old compatibility branches,
pass-through wrappers, gates, assertions, and fallback paths. Some protect real
boundaries. Others repeat work, hide the main path, turn recoverable conditions into
crashes, or make a small change pass through several layers. Code kept only “just in
case” is hard to understand and rarely has a useful test.

**Work packages**

- [ ] Start with a few important paths—mission dispatch, review, resume, and Web/API
      commands—and list their gates, assertions, wrappers, fallbacks, and compatibility
      branches.
- [ ] For each one, record the failure or boundary it protects and the test that proves
      it. Mark entries with no current caller, producer, or failure case for removal.
- [ ] Put each check at the layer that owns it. Stop rechecking the same condition in
      every caller unless the boundary can actually be crossed there.
- [ ] Use assertions for impossible internal states, not bad user input, missing tools,
      stale state, or other conditions the runtime can report and handle.
- [ ] Remove wrappers that only rename arguments or forward calls. Keep a wrapper when
      it owns policy, translation, lifecycle, or a real compatibility boundary.
- [ ] Review broad catches, retries, and fallback ladders that hide the first failure.
      Prefer one clear path and a useful error over a plausible but wrong fallback.
- [ ] Simplify gate chains. A remaining gate should have one owner, one reason to
      exist, and a focused test.
- [ ] Delete obsolete compatibility code in small PRs after checking saved-state and
      supported-version requirements.
- [ ] Track branch count, call depth, deleted code, and regression results for each
      cleaned path; do not use line count alone as proof of improvement.

**Acceptance criteria**

- Every remaining gate, wrapper, fallback, and compatibility branch on the reviewed
  paths has a named purpose and a test or known boundary behind it.
- The reviewed paths have fewer duplicate checks and less call indirection without
  changing their expected behavior.
- Recoverable problems return useful errors instead of assertion failures or silent
  fallback behavior.
- Cleanup does not weaken authentication, sandboxing, secret handling, authority
  checks, data integrity, idempotency, or crash recovery.
- A maintainer can trace the normal path without stepping through obsolete branches
  or wrappers that add no behavior.

---

## ARGUS-P2-01 — Evaluate hybrid persistence instead of assuming “all files” or “all DB”

**Problem.** `~/.argus-skill` has complex file organization and many sidecar locks.
A database could simplify transactions/locking, but opaque storage harms direct
human inspection, debugging, Git-style recovery, and Agent tool access.

**Work packages**

- [ ] Inventory every state file, writer, reader, lock, write frequency, size,
      transaction relationship, and human/Agent inspection requirement.
- [ ] Collect real contention, corruption, partial-write, and recovery incidents;
      do not redesign storage based only on lock-file count.
- [ ] Compare three prototypes: hardened append-only files; SQLite/WAL; hybrid DB
      index/coordination plus human-readable canonical exports/artifacts.
- [ ] Define canonical truth per data class. Avoid dual writable sources.
- [ ] Prototype migration, rollback, backup, export, and disaster recovery.
- [ ] Benchmark concurrent daemons, crash injection, query latency, and operator
      inspection workflows.
- [ ] Decide with an ADR after P0 lifecycle transaction semantics are stable.

**Acceptance criteria**

- The selected design gives atomic multi-object updates where required.
- Humans and coding agents retain a documented inspection/export path.
- Migration is reversible and old project state remains recoverable.
- The number of locks is not used as the sole success metric.

---

## ARGUS-P2-02 — Build the shared evaluation and observability matrix

- [ ] Create a versioned corpus of disclosure-safe failure traces covering
      approval/resume, non-monotonic proof, software-refactor, and research/
      optimization trajectories, ambiguous goals, early-plan lock-in (including
      `0d-3`), stale Planner targets, repeated exploration, and Skill loading.
- [ ] Define common metrics and event fields once; avoid one bespoke dashboard per
      issue.
- [ ] Run component A/B tests and end-to-end goal replays separately. Component
      improvements do not count as product success without goal-level evidence.
- [ ] Publish a weekly table with item owner, experiment status, regression status,
      and the decision to ship/revise/stop.
- [ ] Keep negative results and abandoned designs so the team does not repeat them.

---

## Recommended execution order

1. **Completed:** P0-01 through P0-04 — approval/resume consistency,
   progress-aware continuation, revisable plans, and goal-level mission quality.
2. **Next:** build the P1-01 cross-domain non-monotonic progress model and canary
   P1-02 mission sessions on real projects. Stop the current rolling configuration
   until its rotation handoff is repaired.
3. **In parallel:** reduce P1-03 Skill discovery/tool overhead, add old-session
   migration tests, and continue P1-05 communication improvements.
4. **After lifecycle stability:** P1-04 vertical/core cleanup and P1-06 runtime
   simplification.
5. **Only after state semantics settle:** P2-01 storage decision and migration.

## P0 — Keep the synchronized baseline operational

- [ ] Controlled-restart the long-running private Web service currently bound to
      `127.0.0.1:8799`; it was started before the repository synchronization and
      still holds the previous Python code in memory.
- [ ] Validate a clean private installation from synchronized `main`: create a new
      venv, install the package using the public instructions, run the public smoke
      tests, and verify CLI/Web startup.
- [ ] Validate the preserved local untracked `config/` against the synchronized
      public configuration schema. Keep credentials and machine-local settings out
      of Git.
- [ ] Record the synchronized public code baseline in operations documentation:
      `public main = 7db07ce1259d51391e0df2b79f00a1706ea255d8`; private
      `main` adds only the approved `PRIVATE_TODO.md` overlay.

## P0 — Protect history and future synchronization

- [ ] Treat private branch `202686` as an immutable backup of the former private
      `main` at `f3439e8c2afdaa5e0f0ce6155edfdb47a6f3d300`.
- [ ] Protect `202686` from force-push/deletion in GitHub branch rules.
- [ ] Require private changes to use topic branches and PRs; private `main` may
      differ from public only by an explicit private-overlay allowlist.
- [ ] Automate public-to-private synchronization with four steps: fetch public,
      back up the observed private head, update the private code baseline using
      `--force-with-lease`, then reapply/verify the allowlisted private overlays.
      Compare code trees after excluding `PRIVATE_TODO.md`.

## P2 — Repository hygiene

- [ ] Remove stale local build/cache directories from operational checkouts without
      touching `config/` or the `202686` backup.
- [ ] Keep generated frontend bundles and release manifests reproducible from source;
      do not hand-edit generated outputs.
- [ ] Periodically verify:

  ```bash
  PUBLIC=$(git ls-remote https://github.com/lbx154/Argus refs/heads/main | cut -f1)
  PRIVATE=$(git ls-remote https://github.com/lbx154/argus-skill refs/heads/main | cut -f1)
  git merge-base --is-ancestor "$PUBLIC" "$PRIVATE"
  git diff --name-only "$PUBLIC..$PRIVATE"
  ```

  The private head must descend from the declared public baseline, and the diff must
  contain only allowlisted private overlays (currently `PRIVATE_TODO.md`).

## Done criteria

- Private `main` descends directly from public `main`; after excluding the approved
  overlay allowlist, their code trees are identical.
- `202686` is remotely protected and recoverable.
- The private service runs from the synchronized source.
- Any restored private overlay is minimal, tested, documented, and stays on a topic
  branch unless explicitly approved for private `main` and added to the overlay
  allowlist, or deliberately upstreamed to public.
