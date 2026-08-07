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
- Status labels: `unassigned`, `investigating`, `design-review`, `implementing`,
  `experimenting`, `blocked`, `done`.

## Priority map

| ID | Priority | Severity | Urgency | Suggested DRI | Dependencies |
| --- | --- | --- | --- | --- | --- |
| ARGUS-P0-01 | P0 | Critical | Immediate | Runtime/state | none |
| ARGUS-P0-02 | P0 | Critical | Immediate | Mission loop | P0-01 checkpoint invariants |
| ARGUS-P0-03 | P0 | Critical | Immediate | Manager/contract | none |
| ARGUS-P0-04 | P0 | High | Immediate | Planner/goal | P0-03 |
| ARGUS-P1-01 | P1 | High | Next | Mission progress/evaluation | P0-02, P0-03, P0-04 |
| ARGUS-P1-02 | P1 | High | Next | Agent/session integration | none; can run in parallel |
| ARGUS-P1-03 | P1 | Medium | Next | Skill system | partially implemented |
| ARGUS-P1-04 | P1 | Medium | Next | Architecture/verticals | behavior baseline first |
| ARGUS-P2-01 | P2 | Medium | Later spike | Persistence | P0 state semantics stable |
| ARGUS-P2-02 | P2 | Medium | Continuous | Evaluation/observability | supports all items |

---

## ARGUS-P0-01 — Make human approval and resume transactionally consistent

**Problem.** Approving an Argus decision and resuming frequently leaves backlog,
campaign, daemon, decision-card, or lifecycle state at different revisions. The
user then cannot continue the goal.

**Work packages**

- [ ] Reproduce at least three real failure traces: approval during a running
      daemon, approval after Web/API restart, and repeated/idempotent approval.
- [ ] Define one approval identity containing project/session id, campaign
      generation, backlog item id, decision id, and expected state revision.
- [ ] Apply approval with compare-and-swap semantics. Reject stale decisions with a
      clear UI explanation instead of partially mutating state.
- [ ] Commit answer, decision resolution, backlog transition, continuous state, and
      daemon restart intent as one recoverable transaction or one append-only event
      followed by deterministic projections.
- [ ] Make resume idempotent: retries must neither duplicate a mission nor lose the
      approved answer.
- [ ] Add crash-injection tests between every write and restart boundary.
- [ ] Add Web/TUI integration tests for pause → approve → process restart → resume.

**Acceptance criteria**

- A decision can be submitted repeatedly with one resulting mission transition.
- Stale approval never mutates current state.
- After host/Web/daemon restart, the same authoritative event rebuilds identical
  backlog and campaign state.
- The UI reports one of `accepted`, `already applied`, or `stale`; never a generic
  state mismatch.

---

## ARGUS-P0-02 — Replace the hard 24-round interruption with progress-aware continuation

**Problem.** `SupervisedConfig.hard_escalate_rounds=24` currently force-ends a
mission when Reviewer keeps returning `continue`. Long-horizon missions can remain
productive beyond this boundary, and their observable indicators are often
non-monotonic. A stronger proof invariant may temporarily break proved obligations;
a coherent refactor may increase failing tests before interfaces converge; and a
negative experiment may invalidate an intermediate hypothesis while reducing
uncertainty. The fixed boundary fragments one task frontier and can turn a bounded,
productive local regression into an unrelated replacement mission.

**Work packages**

- [ ] Instrument why each round continues: semantic frontier advance, bounded and
      expected local regression, information-gaining exploration, repeated unchanged
      failure, external blocker, or no decision progress.
- [ ] Define a Reviewer-owned `productive_continue`/equivalent semantic signal;
      avoid deriving it from changed-file count, verifier/test pass count, benchmark
      score, open-obligation count, or keywords.
- [ ] Permit productive missions to cross round 24 while budget, operator stop,
      backend-failure, and genuine no-progress guards remain active.
- [ ] When a clean boundary is necessary, continue the same mission contract and
      task frontier from `CHECKPOINT.md`; do not ask Planner to invent a replacement
      target merely because a counter reached 24.
- [ ] Separate an external unresolved blocker from an internal repair or exploration
      frontier. Only the former should be escalated to `blocked` solely for lack of
      local work.
- [ ] Add cross-domain regression fixtures: for example, Verus invariant
      strengthening that temporarily reduces passing obligations, a refactor that
      temporarily increases failing tests, and an experiment that retires a weak
      hypothesis before the next approach succeeds. Include a productive trajectory
      that requires more than 24 rounds.
- [ ] Compare fixed-24, disabled-cap, and progress-aware policies on cost, completion,
      repeated exploration, and task-frontier continuity and quality.

**Acceptance criteria**

- A productive long-horizon mission can run beyond 24 rounds without replacement
  even when one or more local indicators temporarily regress.
- A truly stagnant loop still terminates under budget/no-progress policy.
- Continuation preserves the objective, assumptions, artifacts, evidence,
  resolved/open obligations, observed regressions, recovery or exit conditions, and
  next action across process/session boundaries.

---

## ARGUS-P0-03 — Keep Planner missions revisable

**Problem.** Planner has to choose a direction before most of the work has been
done. That direction is useful, but today it can become too rigid once it is written
into a mission. Engineer works toward it; Reviewer may later find a counterexample or
a better route, but can usually only escalate instead of changing the mission. A
decision made with less information then overrides a better-informed one.

This is sometimes called endogenous harnessing, or self-harnessing: an internal plan
starts acting like an external constraint. Planning is not the problem. The user’s
goal, safety rules, and authority or trust limits are real constraints. A candidate,
method, decomposition, or validator usually is not. The workflow should let later
evidence change those technical choices.

This showed up in `0d-3`:

1. Planner asked for a `skip-zero` candidate.
2. Engineer worked inside that target.
3. Reviewer found a `no-gap` validator alternative.
4. Reviewer could escalate, but could not change the mission.
5. Work continued under the earlier plan even though a better option was available.

**Work packages**

- [ ] Distinguish user constraints, Manager decisions, and Planner’s working plan in
      prompts and saved state. Keep track of where each constraint came from.
- [ ] Writing a plan into a mission must not make it harder to change.
- [ ] Keep hard constraints to the user’s goal, safety rules, authority boundaries,
      and explicit trust, permission, or resource limits. Treat technical choices as
      revisable unless the user has explicitly fixed them.
- [ ] Give Engineer and Reviewer a direct way to challenge the current plan, attach
      the evidence, and suggest a replacement.
- [ ] Let Manager decide whether to keep, revise, or replace the plan. Ask the user
      only when the change affects a user-owned constraint.
- [ ] Once a plan is challenged, do not make Engineer finish it or Reviewer approve
      it just because it is still written in the mission.
- [ ] Record when the conflicting evidence first appeared, when the challenge was
      raised, and how much work happened before the mission changed.
- [ ] Replay `0d-3`: compare the `no-gap` alternative with the original `skip-zero`
      plan before requiring more work on `skip-zero`.
- [ ] Add tests for underspecified goals, where Argus should ask the user rather than
      silently making a product or scope decision.

**Acceptance criteria**

- A Planner strategy remains a working plan after it is written into a mission.
- A challenge from Engineer or Reviewer gets an explicit keep, revise, or replace
  decision before work quietly continues on the disputed plan.
- In the `0d-3` replay, the `no-gap` alternative is considered against the user’s
  actual goal before more `skip-zero` work is required.
- User-owned goals and safety, authority, and trust boundaries remain enforced.
- Time and work lost between new evidence and a mission change are measured.

---

## ARGUS-P0-04 — Improve Planner mission quality and measure goal completion

**Problem.** Current users often fail to finish one goal after weeks or a month.
Planner mission quality strongly affects completion. Some missions optimize for a
verifier/check script becoming green instead of moving the actual goal frontier;
local one-shot objectives can be invalid for long-horizon work with temporary,
bounded regressions or information-gaining failures.

**Work packages**

- [ ] Build a disclosure-safe trace set from Shan, Xuchuan, and existing long-running
      projects: original goal, missions, revisions, stalls, questions, and terminal
      state.
- [ ] Define a mission-quality rubric: goal alignment, authority correctness,
      dependency readiness, coherent scope, expected failure/regression model,
      revision freedom, decisive evidence, and contribution to project frontier.
- [ ] Label failure modes: verifier chasing, early-plan lock-in, duplicate mission,
      premature polish, missing prerequisite, local-green/global-no-progress,
      overlarge mission, and fragmented continuation.
- [ ] Change Planner guidance so acceptance checks measure a meaningful frontier
      increment, not only the easiest script/checker result.
- [ ] Require missions to state what may temporarily regress and what evidence would
      trigger revise, continue, split, or abandon decisions.
- [ ] Feed Reviewer outcomes and negative results into later planning without
      converting every failure into another similarly worded repair mission.
- [ ] Add goal-level metrics: time to first useful artifact, mission acceptance rate,
      duplicate-work rate, replan rate, operator-question latency, terminal goal
      completion, and unfinished-goal age.
- [ ] Run blinded human review of sampled missions before/after the Planner change.

**Acceptance criteria**

- The three reference user traces have a clear next/terminal path rather than an
  indefinitely growing backlog.
- Sampled missions improve on the rubric without increasing silent scope changes.
- Goal-level completion improves in a fixed replay/paired evaluation; verifier pass
  count alone is not accepted as the outcome.

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

**Problem.** Manager reuses a session, while Planner, Engineer, and Reviewer normally
start fresh sessions. Fresh sessions repeat repository exploration and spend time and
Tokens; indefinitely long sessions accumulate stale context and reduce output quality.

**Work packages**

- [ ] Measure current repeated-exploration cost by role: duplicate file reads,
      repeated repository mapping, prompt Tokens, wall time, and correction rate.
- [ ] Evaluate at least three policies on matched tasks:
      fresh every turn; persistent per mission+role; rolling session with explicit
      compaction/rotation.
- [ ] Prototype a small role session capsule containing objective revision,
      repository map, inspected paths, decisive outputs, open hypotheses, and
      checkpoint pointer—without copying the full transcript.
- [ ] Define rotation triggers: context utilization, objective/branch change,
      repeated contradiction, stale path map, Reviewer-detected confusion, or model
      quality degradation.
- [ ] Ensure role isolation: Reviewer never inherits Engineer private reasoning;
      Planner/Engineer sessions cannot silently change Manager-owned state.
- [ ] Preserve restart behavior and provider portability when a backend cannot
      resume sessions.

**Acceptance criteria**

- A selected policy reduces repeated exploration/time/Tokens on matched tasks.
- Correctness and Reviewer acceptance do not regress.
- Context rotation is explicit, observable, and recoverable from durable state.
- The design works with both resumable and fresh-only coding-agent backends.

---

## ARGUS-P1-03 — Finish coding-agent-native, on-demand Skill use

**Status: partially implemented.** Current public baseline passes Skill library paths
to roles and states that no Skill is parsed, matched, adapted, or injected by the
runtime. Coding agents are expected to discover/read Markdown on demand. We still
need to verify that all roles and backends follow this contract and that no large
legacy body remains duplicated in prompts.

**Work packages**

- [ ] Audit all four role prompts and backend adapters for remaining direct Skill
      body injection or duplicate fixed-role content.
- [ ] Define a minimal coding-agent Skill discovery contract: roots, role ownership,
      precedence, and when to read; avoid a harness-side matcher/scorer.
- [ ] Test native loaders for each supported coding agent and provide a portable
      path/index fallback where native Skill APIs differ.
- [ ] Measure on-demand behavior: skills opened, bytes/Tokens read, useful reuse,
      false reuse, task success, and latency.
- [ ] Ensure Agent-created role Skills are immediately discoverable without
      rebuilding a giant prompt or restarting the daemon.
- [ ] Remove legacy compatibility fields only after event/session migration tests
      confirm old runs remain readable.

**Acceptance criteria**

- No ordinary mission prompt contains full non-role Skill bodies by default.
- Agents can find and load relevant Skills with tools only when needed.
- On-demand use lowers prompt cost without reducing completion quality.

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

1. **Immediately:** P0-01 approval/resume consistency and trace collection for P0-04.
2. **In parallel:** design P0-03 authority/mission contracts; benchmark P1-02 session
   policies without changing production defaults.
3. **Then:** P0-02 progress-aware continuation and the P1-01 cross-domain
   non-monotonic progress model on the clarified contract.
4. **After lifecycle stability:** P1-03 Skill audit and P1-04 vertical/core cleanup.
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

## P1 — Classify the former private-only tree

The `202686` backup differs from synchronized `main` in 535 paths:

- 532 paths exist only in the former private tree;
- 2 paths are modified (`README.md`, `README.zh-CN.md`);
- 1 path exists only in public (`docs/assets/argus-wechat-group.jpg`).

Do not restore these paths in bulk. Produce a manifest assigning every path one of:

1. `archive-private` — retain only on `202686` or external private storage;
2. `private-overlay` — restore on a reviewed private topic branch;
3. `candidate-public` — propose upstream to the public repository via PR;
4. `obsolete` — intentionally retire.

### Review groups

- [ ] **Technical report sources and evidence (215 paths):** decide whether LaTeX,
      editable figures, evidence bundles, and PPT sources should be public,
      private-overlay, or immutable release artifacts. The public PDF remains the
      authority until that policy is decided.
- [ ] **GitHub/Impeccable automation (105 `.github` paths plus `.agents` and
      `.impeccable`):** audit third-party hooks, generated assets, permissions, and
      maintenance burden before restoring anything.
- [ ] **Frontend/demo material (66 paths):** separate source from generated `dist/`,
      remove duplicated math-vertical demo bundles, and restore only reproducible
      artifacts required by a private deployment.
- [ ] **Private documentation (61 paths):** reconcile architecture/design/runtime
      docs against public current behavior. Do not restore stale documents merely
      because they existed in the old repository.
- [ ] **Release and experiment scripts (35 paths):** review binary/npm release
      tooling, MLE-Bench campaign scripts, and verification helpers for secrets,
      obsolete interfaces, and reproducibility before selecting any overlay.
- [ ] **Tests (16 paths):** restore tests only with the production surface they
      validate; avoid private tests for code no longer present on public `main`.
- [ ] **Packaging/deployment:** review `packaging/`, the systemd unit, binary build
      definitions, and npm launchers as one coherent private deployment feature.
- [ ] **Large/private assets:** keep presentations, DOCX/PDF working files, research
      state, and internal evidence off synchronized `main` unless publication and
      licensing are explicit.

## P1 — Verify that no functionality was silently lost

- [ ] Compare public smoke behavior with the former private release on `202686` for
      CLI startup, Manager routing, bounded DAG dispatch, four-role execution,
      Web/TUI startup, and persistent session recovery.
- [ ] For every behavioral difference, create a small reproducible issue before
      proposing code restoration. A file diff alone is not evidence of regression.
- [ ] Prefer public implementations when both trees provide the same capability;
      restore only private behavior that has a current owner and a testable need.

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
- Every former private-only path has an explicit disposition.
- Any restored private overlay is minimal, tested, documented, and stays on a topic
  branch unless explicitly approved for private `main` and added to the overlay
  allowlist, or deliberately upstreamed to public.
