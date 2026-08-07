# Argus Impressive Results — Candidate List

> Goal: use Argus to produce results that are genuinely impressive and externally verifiable.
>
> A plan, a working demo, or a green internal checker is not yet an impressive result.
> A candidate enters the official result list only after the result, reproduction package,
> and independent verification are complete.

## Admission bar

Every listed result should meet these conditions:

- **The result matters:** a material performance gain, real leaderboard rank, upstream adoption,
  useful system, or independently checked mathematical proof/counterexample.
- **The comparison is fair:** frozen baseline, hardware, inputs, precision, versions, and scoring;
  no headline built from one cherry-picked shape.
- **It is reproducible:** environment, commands, raw results, code/patch, failed attempts, and
  limitations are available.
- **It was checked independently:** Reviewer audit; repeated measurements for performance;
  independent experts or formal verification for mathematics.
- **Argus did identifiable work:** preserve the session, task trace, hypotheses, code changes,
  and Reviewer decisions; disclose human contributions separately.
- **The claim stays narrow:** an external reference is not an Argus result, and a one-GPU,
  one-shape result is not a universal result.

### Status

- `candidate`: direction only; no reliable baseline yet.
- `active`: executable campaign and measurement protocol exist.
- `certified`: repeated internal measurements and independent Reviewer passed.
- `externally-verified`: confirmed by upstream, leaderboard, external reproduction, or experts.
- `shipped`: available in usable code, a product, or a public result.
- `retired`: evidence says to stop; retain the negative result and reason.

## Candidate board

| ID | Track | Status | Main platforms | Requirement for the official result list |
| --- | --- | --- | --- | --- |
| ARGUS-IR-01 | Sol-Engine / Sol-Attn optimization | `candidate` | B200, H100 | Reproducible gain on representative workloads plus a usable patch/PR |
| ARGUS-IR-02 | Generalize and upstream FLA `chunk_kda` | `active` | B200, H100 | D128 and H100 data, combined N>=10, and response to upstream review |
| ARGUS-IR-03 | MiniMax Speedrun leaderboard | `candidate` | B200, H100 | Frozen public scoring protocol and reproducible leaderboard result |
| ARGUS-IR-04 | Fast MiniMax-H3 from datacenter to desktop | `candidate` | DGX Spark, RTX 5090 | Independently reproduce or beat the reference with the raw 33B checkpoint |
| ARGUS-IR-05 | W2A4 GEMM kernel | `candidate` | B200, H100, RTX 5090 | Beat strong baselines on real model shapes and improve end-to-end performance |
| ARGUS-IR-06 | Prove or refute an Erdős conjecture | `exploration` | CPU/GPU + proof tooling | Exact statement and proof/counterexample with independent verification |

---

## ARGUS-IR-01 — Optimize Sol-Engine / Sol-Attn

**Goal**

Use Argus to optimize the attention path in Sol-Engine, focusing on Sol-Attn,
sparse attention, kernel launches, memory traffic, and state reusable across steps.
The output should be a reproducible patch or upstream PR.

**Freeze first**

- Repository, commit, model checkpoint, and workload.
- B200/H100 software stack, precision, batch, sequence/resolution, and timing boundary.
- Correctness, output quality, memory, and end-to-end baseline—not just an isolated kernel.

**Work**

- [ ] Reproduce the original Sol-Engine / Sol-Attn baseline on B200 and H100.
- [ ] Profile attention time, launch overhead, HBM round-trips, and waste in sparse paths.
- [ ] Test kernel fusion, sparse-attention implementations, layout/tiling,
      cross-step caching, and scheduling separately.
- [ ] Record kernel microbenchmarks, end-to-end latency, throughput, memory, and quality
      for every retained change.
- [ ] Ablate successful changes so the mechanism is known rather than shipping an opaque bundle.
- [ ] Repeat across a useful workload/shape set; do not headline one cherry-picked case.
- [ ] Produce a minimal patch, reproduction script, and upstream issue/PR.

**Done when**

- At least one of B200/H100 has a stable, repeated end-to-end gain;
- correctness, quality, and memory have no unexplained regression;
- another machine can reproduce the result; and
- the code is under upstream review or maintained as a clearly scoped implementation.

---

## ARGUS-IR-02 — FLA `chunk_kda`: D128/H100 coverage and upstream closure

**Existing Argus result**

Argus has already optimized FLA `chunk_kda` on B200 at `B8_T1024_H8_D64`:

- **N>=10 +17.66%** for the certified component stack;
- **+29.93%** on one frozen combined verification run;
- correctness PASS and memory-neutral; and
- submitted as [`fla-org/flash-linear-attention#1054`](https://github.com/fla-org/flash-linear-attention/pull/1054), not merged.

Evidence:
[`technical_report/evidence/fla_kernel_optimization/README.md`](technical_report/evidence/fla_kernel_optimization/README.md).

**Open gap**

The upstream maintainer correctly noted that D64 has limited practical coverage. The PR still
needs D128 (for example H32/H64) and H100 results. The current claim is one B200 D64 shape,
not a general KDA acceleration.

**Work**

- [ ] Rebase the patch onto the current reviewable FLA baseline.
- [ ] Add practical `D=128`, H32/H64 shapes on B200.
- [ ] Run the same correctness, latency, and memory protocol on H100.
- [ ] Certify the combined stack with N>=10 paired repeats and a cleared-cache repeat.
- [ ] Report forward, backward, and forward+backward separately so geomean cannot hide a loss.
- [ ] Inspect D128 register pressure, occupancy, and whether fusion gains shrink as predicted.
- [ ] Update the PR with data and a direct response to maintainer feedback.

**Done when**

- D128 and H100 evidence is complete and reproducible;
- the combined result clears N>=10, correctness, and memory bars;
- the claim is scoped by shape and hardware; and
- upstream performs substantive review. `externally-verified` requires merge or external reproduction.

---

## ARGUS-IR-03 — MiniMax Speedrun on B200/H100

**Goal**

Create a fixed, public, repeatable MiniMax speedrun track and let Argus optimize against it
continuously. This should produce a real rank, not a one-off internal demo.

**Freeze first**

- MiniMax model/checkpoint, task, and output-quality requirement.
- Input dimensions, output length, batch/concurrency, precision, warmup, timing boundary,
  and hardware power mode.
- Leaderboard rules, allowed/forbidden optimizations, and required logs.
- Separate B200 and H100 rankings.

**Work**

- [ ] Archive the public scorer and baseline commit.
- [ ] Produce reproducible B200/H100 baselines with throughput, first-token/first-frame,
      end-to-end latency, and memory.
- [ ] Maintain an Argus experiment ledger: hypothesis, change, result, noise, and keep/revert decision.
- [ ] Optimize graph, attention, GEMM, quantization, cache, kernels, and scheduling in layers.
- [ ] Re-test individual and combined champion changes; do not bank noise.
- [ ] Submit to the leaderboard or reproduce on an independent machine with the same script.

**Done when**

- There is a public or auditable rank, not merely a “faster” claim;
- the gain over the frozen baseline survives repeated runs;
- quality satisfies the track; and
- the champion stack rebuilds from a clean environment.

---

## ARGUS-IR-04 — Fast MiniMax-H3: datacenter to desktop

**External reference, not an Argus result**

Use Xie Enze's Fast MiniMax work as the reference. After Sol-Engine B200 Day-1 support,
H3 was deployed and accelerated on DGX Spark and RTX 5090:

- **DGX Spark:** 480p, 5 seconds, 24 FPS, **3.92x** end-to-end;
- **RTX 5090:** 720p, 5 seconds, 24 FPS, **4.52x** end-to-end;
- kernel optimization, Sol-Attn / sparse attention, and cross-step caching; and
- the original **33B checkpoint**, without distillation, fine-tuning, or LoRA.

These numbers are a reference to reproduce, not numbers that Argus may claim today.

**Argus goal**

Independently reproduce or beat the reference under the same input, checkpoint, quality,
and timing rules, then package a Fast MiniMax-H3 path that a normal user can deploy.

**Work**

- [ ] Obtain or reconstruct an auditable baseline and confirm the reference timing/quality rules.
- [ ] Freeze the original 33B checkpoint; no distillation, fine-tuning, or LoRA substitution.
- [ ] Establish unoptimized baselines on DGX Spark and RTX 5090.
- [ ] Implement and ablate kernel optimization, Sol-Attn/sparse attention, and cross-step caching.
- [ ] Record end-to-end latency, FPS, memory, peak power, startup/compile time, and quality.
- [ ] Build repeatable installation, model preparation, and one-command demo steps without hidden caches.
- [ ] Compare at the same specification; lower resolution or shorter video cannot masquerade as a win.

**Done when**

- At least one desktop platform matches or beats the reference speedup at the same specification;
- the raw 33B checkpoint has no unexplained quality loss;
- a clean machine can deploy and reproduce it; and
- ablations identify the contribution of kernels, attention, and cache.

---

## ARGUS-IR-05 — Build a W2A4 GEMM kernel with Argus

**Goal**

Design, implement, and optimize a W2A4 GEMM that serves a real model—not a toy kernel that
works only on convenient shapes. Prioritize the MiniMax-H3 / Fast MiniMax path while retaining
an independent benchmark.

**Work**

- [ ] Freeze W2A4 layout, group size, scale/zero-point semantics, accumulation precision,
      and error tolerance.
- [ ] Collect real M/N/K, batch, and concurrency distributions from the target model.
- [ ] Freeze strong available baselines (framework/CUTLASS/Triton as applicable).
- [ ] Implement a reference path and element/matrix correctness tests.
- [ ] Test dequant+GEMM fusion, packing, tiling, pipelines, Tensor Cores, and epilogues.
- [ ] Measure kernel latency, throughput, memory, and end-to-end gain on applicable
      B200/H100/RTX 5090 platforms.
- [ ] Include packing, dequantization, compilation, and transfer costs—not only ideal steady state.
- [ ] Integrate into at least one real model path and verify output quality.
- [ ] Publish source, benchmark, result table, and upstream/integration PR.

**Done when**

- It beats a strong baseline on multiple real shapes;
- correctness and model quality pass;
- integration produces an end-to-end gain; and
- a second machine can reproduce it.

---

## ARGUS-IR-06 — Prove or refute an Erdős conjecture

**Goal**

Select one precise Erdős problem from [Unsolved Math](https://www.unsolvedmath.com/) and
primary literature for a long-horizon Argus proof search. Success can be a complete proof
or a verifiable counterexample that genuinely refutes the stated conjecture.

**Lock the problem first**

- [ ] Select one statement and record exact quantifiers, parameter range, known partial results,
      and primary references.
- [ ] Have a mathematician confirm the statement; the website is an index, not the authority.
- [ ] Freeze the statement version before large search so difficulty cannot cause silent task drift.

**Proof/counterexample tracks**

- [ ] Build a packet of known results, equivalent forms, key obstacles, and computable small cases.
- [ ] Maintain proof and counterexample tracks in parallel; record what every failure rules out.
- [ ] Use exact arithmetic, replayable code, and complete ranges for computation; floating-point
      evidence is not a proof.
- [ ] For a counterexample, provide the minimal object, an independent verifier, and a second implementation.
- [ ] For a proof, check every lemma, dependency, boundary case, and quantifier; a proof sketch is insufficient.
- [ ] Formalize suitable parts in Lean/Isabelle/Coq or equivalent tooling; send non-formalizable parts
      to at least two independent mathematical reviewers.
- [ ] Check current literature for novelty and the exact statement version.

**Done when either**

1. A complete proof passes independent expert review and becomes a public manuscript; or
2. A concrete counterexample is reproduced by two independent programs/proofs and matches the
   original statement exactly.

Finite checks, numerical evidence, failure to find a counterexample, or “the model believes the proof”
do not enter the official result list.

---

## Recommended order

1. **Close FLA KDA first:** existing code and upstream feedback make it the shortest path to an
   externally verified result.
2. **Start Sol-Attn and W2A4 in parallel:** both can become components of Fast MiniMax.
3. **Reproduce Fast MiniMax-H3 on desktop:** align the reference specification before stacking wins.
4. **Establish the MiniMax Speedrun:** freeze the benchmark before optimizing it.
5. **Run the Erdős track independently:** lock the statement and verification tools without blocking
   the GPU engineering tracks.

## Record template for an official result

```text
RESULT_ID=
TITLE=
ONE_LINE_RESULT=
STATUS=certified|externally-verified|shipped
BASELINE_REPO_AND_COMMIT=
ARGUS_REPO_AND_COMMIT=
HARDWARE_AND_SOFTWARE=
WORKLOAD_AND_QUALITY_BAR=
MEASURED_RESULT=
REPEAT_COUNT_AND_VARIANCE=
REPRODUCE_COMMAND=
CODE_OR_PR=
ARGUS_SESSION_AND_TRACE=
HUMAN_CONTRIBUTIONS=
INDEPENDENT_VERIFICATION=
KNOWN_LIMITATIONS=
```

The public result page should contain only qualified results. Failed routes, negative results,
and rejected claims stay in each campaign's evidence directory.
