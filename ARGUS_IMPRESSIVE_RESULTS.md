# Argus Impressive Results — Candidate Campaigns

> Goal: use Argus to produce substantial results that a third party can understand,
> reproduce, and verify.
>
> This is a campaign list, not a list of completed Argus achievements. A plan, a demo,
> or a green internal checker is not yet an impressive result.

**Public-source audit:** 2026-08-07. Each claim below is labelled as background,
an external result, existing Argus evidence, or future Argus work. If those categories
are not interchangeable, neither are their numbers.

## How to read this document

- **Background** explains the technology in plain language.
- **External reference** means somebody else reported the result. It is context or a
  baseline candidate, never an Argus result.
- **Existing Argus evidence** means an Argus run produced evidence, but the claim is
  only as broad as the listed hardware, shape, repeat count, and review status.
- **Argus goal / Work** describes work that has not yet been completed.

### Important evidence corrections

1. The previously listed **3.92× DGX Spark** and **4.52× RTX 5090** MiniMax-H3
   claims could not be traced to a primary public source. They have been removed.
2. Public sources verify that **Enze Xie is a co-author of Sol-Engine and Sol-Attn**;
   they do not assign the MiniMax-H3 implementation or a desktop benchmark to him
   individually. The official H3 result is therefore attributed to the **NVLabs
   Sol-Engine team**, not to one person.
3. FLA PR
   [`#1054`](https://github.com/fla-org/flash-linear-attention/pull/1054) is now
   **closed, not merged**. Representative D128 follow-up showed that the large D64
   gain did not carry over to training. The useful SM100 correctness fix was extracted
   into focused PR
   [`#1109`](https://github.com/fla-org/flash-linear-attention/pull/1109), which is
   open and maintainer-approved as of the audit date.

## Small glossary

| Term | Plain-language meaning |
| --- | --- |
| **checkpoint** | The published model weights and configuration. Changing to a smaller or differently trained model changes the task. |
| **baseline** | The frozen version to beat. It must use the same hardware, input, quality bar, and timing boundary. |
| **kernel** | A low-level GPU program for one operation. A faster kernel does not automatically make the whole application faster. |
| **GEMM** | General matrix multiplication, the operation behind most neural-network linear layers. |
| **attention** | The operation that lets tokens exchange information. Full attention compares every query with every key and becomes expensive for long video sequences. |
| **sparse attention** | Compute only selected attention interactions. It can be faster, but selection overhead and approximation error must be measured. |
| **cache across steps** | Reuse work from nearby diffusion denoising steps. It can save substantial compute, but is usually approximate. |
| **end-to-end** | The user-visible path, not just one kernel. The exact included/excluded stages must still be stated. |
| **hot path** | The repeatedly expensive part of a run. It may exclude model load, prompt encoding, compilation, or output packaging. |
| **1.5× speedup** | New time is old time divided by 1.5. It does not mean “150% less time.” |
| **N>=10** | At least ten paired measurements, used here to reduce the chance that noise is mistaken for a speedup. |
| **B/T/H/D** | Batch size / sequence length / attention-head count / dimension per head. For example, `B8_T1024_H8_D64`. |

H100 is a Hopper-generation datacenter GPU; B200 is a newer Blackwell datacenter
GPU. DGX Spark is a compact GB10 system with unified memory; RTX 5090 is a desktop
GPU. Results are not portable between them without remeasurement.

## Admission bar

Every official result must satisfy all of the following:

- **The result matters:** a material performance gain, real leaderboard rank, upstream
  adoption, useful system, or independently checked mathematical proof/counterexample.
- **The comparison is fair:** frozen baseline, hardware, inputs, precision, versions,
  quality bar, and scoring; no headline built from one convenient shape.
- **It is reproducible:** environment, commands, raw results, code/patch, failed routes,
  and limitations are available.
- **It was checked independently:** Reviewer audit; repeated measurements for performance;
  independent experts or formal verification for mathematics.
- **Argus did identifiable work:** preserve the session, task trace, hypotheses, code
  changes, and Reviewer decisions; disclose human contributions separately.
- **The claim stays narrow:** an external reference is not an Argus result, and a one-GPU,
  one-shape result is not universal.

### Status vocabulary

- `exploration`: even the exact problem or feasibility gate is not locked.
- `candidate`: direction exists, but no reliable baseline and protocol yet.
- `active`: executable campaign and measurement protocol exist.
- `certified`: repeated internal measurements and independent Reviewer passed.
- `externally-verified`: confirmed by upstream, a leaderboard, an external reproduction,
  or independent experts.
- `shipped`: available as usable code, a product, or a public result.
- `retired`: evidence says to stop that route; retain the negative result and reason.

## Candidate board

| ID | Track | Status | Main platforms | Requirement for the official result list |
| --- | --- | --- | --- | --- |
| ARGUS-IR-01 | Sol-Engine / Sol-Attn optimization | `candidate` | B200, H100 | Representative repeated end-to-end gain plus a usable patch/PR |
| ARGUS-IR-02 | FLA `chunk_kda`: close the SM100 fix and preserve the D128 lesson | `active` | B200, Hopper CI | PR #1109 merged/external reproduction; no broad performance claim from D64 |
| ARGUS-IR-03 | MiniMax-H3 Speedrun | `candidate` | B200, H100 | Frozen public protocol and a reproducible, quality-qualified result |
| ARGUS-IR-04 | MiniMax-H3 from datacenter to desktop | `candidate` | DGX Spark, RTX 5090 | Reproducible same-device gain with an explicitly declared fidelity/quantization tier |
| ARGUS-IR-05 | W2A4 GEMM | `exploration` | B200, H100, RTX 5090 | Quality feasibility first; then real-shape kernel and end-to-end gains |
| ARGUS-IR-06 | Prove or refute one Erdős problem | `exploration` | CPU/GPU + proof tools | Frozen exact statement and independently verified proof/counterexample |

---

## ARGUS-IR-01 — Optimize Sol-Engine / Sol-Attn

### Background: what is Sol-Engine?

[Sol-Engine](https://github.com/NVlabs/Sana/tree/sol-engine) is not a model and not a
GPU. It is NVLabs' inference-engineering codebase for making high-resolution video
**diffusion models** run faster, built on SGLang's `multimodal_gen` runtime. A diffusion
video model starts with noise and repeatedly runs a large transformer to denoise it;
doing this for many frames and many steps is expensive.

Sol-Engine combines five kinds of acceleration:

1. **cache** — reuse similar work across denoising steps;
2. **quantization** — use fewer bits where quality permits;
3. **kernel fusion** — combine several small GPU operations to avoid launches and
   memory round-trips;
4. **sparse attention** — compute only selected token interactions; and
5. **token pruning** — temporarily remove low-value tokens.

It calls the workflow **agent-native** because coding agents can prepare environments,
try techniques, and compose candidate stacks while a human validates output quality.
That does not mean every result is autonomous or automatically correct.
The [Sol-Engine paper](https://arxiv.org/abs/2606.23743) reports more than 2×
end-to-end acceleration on its original three model case studies with near-lossless
VBench quality.

### Background: what is Sol-Attn?

Long videos produce many tokens. Full attention compares all query/key pairs, so its
work grows roughly with the square of sequence length. Sol-Attn is a training-free,
dynamic sparse-attention method. During the online-softmax pass it routes important key
blocks, computes those blocks exactly, and uses a lightweight approximation for omitted
blocks instead of simply dropping them. It is one technique inside Sol-Engine, not the
whole engine. The [Sol-Attn paper](https://arxiv.org/abs/2607.24027) reports 2.1× and
2.3× end-to-end speedups on its video generation/editing evaluations while preserving
reported visual quality; those are external paper results, not Argus measurements.

### External reference: the official MiniMax-H3 stack

The current Sol-Engine H3 documentation reports this frozen **team result**:

- model/workload: MiniMax-H3, 1344×768, 124 frames, 50 steps;
- hardware: 8×GB200 in the same NVL72 rack, Ulysses context parallelism;
- timing: hot path (denoising plus video decode), excluding about 2.1 seconds of fixed
  text/audio encoding, packing, scheduling, and output assembly;
- baseline: 27.21 s;
- kernel line: 19.51 s;
- plus Sol-Attn: 17.74 s;
- plus FirstBlockCache: 6.88 s, or **3.97× cumulative**; and
- peak memory: 144,474 MiB down to 120,763 MiB.

Source: the official
[`models/minimax_h3/README.md`](https://github.com/NVlabs/Sana/blob/sol-engine/models/minimax_h3/README.md).
The kernel line is described as lossless; Sol-Attn and FirstBlockCache are
approximations and therefore require both audio and video quality checks. The 3.97×
number is an 8×GB200 hot-path benchmark. It is not a DGX Spark or RTX 5090 result.

### What exactly did Enze Xie do?

Publicly verifiable facts are:

- [Enze Xie's public page](https://xieenze.github.io/) identifies him as a Staff
  Research Scientist at NVIDIA Research and a visiting researcher at MIT HAN Lab.
- He is co-first author of
  [SANA](https://arxiv.org/abs/2410.10629), co-author of
  [Sol-Engine](https://arxiv.org/abs/2606.23743), and co-author of
  [Sol-Attn](https://arxiv.org/abs/2607.24027).
- At the level supported by the co-authored paper, the SANA work introduced a 32× deep
  compression autoencoder, a linear-attention Diffusion Transformer, a decoder-only
  text encoder, and a faster sampling/training recipe for high-resolution image
  generation. The paper does not split those items into per-author implementation credits.
- His public page says his SANA research contributes to NVIDIA generative-AI projects.

What the public record does **not** establish is that he personally wrote each H3
optimization, produced a DGX Spark/RTX 5090 result, or owns the official 3.97× number
alone. The H3 model page documents a team implementation without a per-person
contribution ledger. We therefore describe his documented research/co-authorship and
attribute the implementation benchmark to the Sol-Engine team. A stronger personal
attribution requires a primary post, commit, or author statement.

### Argus goal

Find and upstream a new, reproducible improvement beyond the frozen Sol-Engine baseline.
Prioritize attention time, GPU launch overhead, HBM traffic, and reusable state, but
judge changes by end-to-end latency and audio/video quality rather than kernel latency
alone.

### Freeze first

- Repository commit, model checkpoint, prompt/seed, and output dimensions/steps.
- B200/H100 software stack, precision, GPU topology, batch/concurrency, power mode,
  warm-up, and timing boundary.
- Dense/reference output, audio and video quality checks, peak memory, and end-to-end
  baseline.
- Which official optimizations are already enabled; do not “rediscover” an existing
  Sol-Engine feature and call it new.

### Work

- [ ] Reproduce an official Sol-Engine candidate on B200 and/or H100.
- [ ] Profile attention, launch overhead, HBM round-trips, collectives, and sparse-path waste.
- [ ] Test fusion, sparse kernels, layouts/tiling, cross-step reuse, and scheduling separately.
- [ ] Keep a per-change ledger with kernel and end-to-end latency, memory, audio/video
      quality, and keep/revert decision.
- [ ] Ablate retained changes so the mechanism is known.
- [ ] Repeat on a representative workload set; do not headline one cherry-picked case.
- [ ] Produce a minimal patch, clean reproduction script, and upstream issue/PR.

### Done when

- At least one B200/H100 configuration has a stable repeated end-to-end gain;
- correctness, audio/video quality, and memory have no unexplained regression;
- another machine reproduces the result; and
- the code receives substantive upstream review or is maintained as a clearly scoped fork.

---

## ARGUS-IR-02 — FLA `chunk_kda`: close the useful fix, retire the weak route

### Background: KDA and FLA in plain language

Conventional transformer attention stores keys and values for every previous token, so
its KV cache grows with context length. **Kimi Delta Attention (KDA)** is a linear-attention
module that updates a fixed-size recurrent state instead. It extends Gated DeltaNet with
finer-grained gates that decide how memory is erased and written. Kimi Linear combines
KDA with global MLA layers; KDA is the mechanism, not the entire model.

The [Kimi Linear paper](https://arxiv.org/abs/2510.26692) reports up to 75% less KV-cache
usage and up to 6× decoding throughput at a one-million-token context. Those are
architecture/model results under the paper's setup—not the effect of this Argus kernel
patch.

[Flash Linear Attention (FLA)](https://github.com/fla-org/flash-linear-attention) is an
open-source library of efficient kernels and training-ready layers for KDA and other
modern sequence mechanisms. `chunk_kda` divides a sequence into chunks so GPUs can
parallelize KDA while preserving its recurrent mathematics. Training needs both forward
and backward kernels, so a forward-only win may be irrelevant to users. This campaign
is about a language/sequence-model KDA operator; it is separate from MiniMax-H3's video
attention and does not make Sol-Attn faster by itself.

The old test shape `B8_T1024_H8_D64` means batch 8, 1,024 tokens, 8 heads, and 64 values
per head. Upstream users care more about D128/H32/H64 shapes; doubling D increases useful
arithmetic, so removing a fixed launch may matter much less.

### Existing Argus evidence: the narrow D64 result

Against frozen FLA commit `ccb0ff94`, Argus measured on one B200 at
`B8_T1024_H8_D64`, BF16:

- **+17.66%** for the N>=10-certified cumulative component stack;
- **+29.93%** for one combined paired run;
- correctness PASS and no peak-memory increase.

The mechanisms fused q/k normalization, an inter-solve epilogue, and a chunk-local
cumulative-gate producer to remove launches/HBM round-trips. Evidence:
[`technical_report/evidence/fla_kernel_optimization/README.md`](technical_report/evidence/fla_kernel_optimization/README.md).
This remains valid evidence for one old commit, one B200, and one D64 shape only.

### Follow-up result: why the performance PR was closed

The maintainer of PR
[`#1054`](https://github.com/fla-org/flash-linear-attention/pull/1054) asked for
representative D128 and Hopper evidence. Follow-up against current code found:

- on the available H200 runner, four D128 shapes had only 1.055–1.061× forward geomean
  and 1.001–1.002× forward+backward geomean;
- `B4_T4096_H64_D128` slightly regressed in forward and was essentially unchanged in
  forward+backward; and
- isolated B200 D128 q/k fusion and cumsum fusion were approximately 1.00× for training.

That result matches the mechanism: fixed launch/HBM savings were important at D64 but
were amortized by the larger D128 computation. The 432-line performance stack was not
worth maintaining, and #1054 was closed without merge. This is a useful negative result:
Argus followed the evidence rather than preserving a large headline.

H200 is Hopper-family hardware but is not an H100 measurement. No broad H100 performance
claim is made.

### Active useful output: SM100 correctness PR #1109

The investigation independently reproduced an illegal memory access while B200/SM100
autotuning explored unsafe backward-kernel configurations. Argus extracted a two-line,
SM100-scoped filter into
[`#1109`](https://github.com/fla-org/flash-linear-attention/pull/1109):

- full B200 KDA test file: **76 passed, 7 skipped** after the fix;
- Hopper and SM120 search spaces remain unchanged; and
- an upstream maintainer approved the focused PR on 2026-08-07; merge is still pending.

This correctness fix, not the discarded broad performance stack, is now the shortest
path to externally verified upstream value.

### Work

- [ ] Address the two non-blocking review nits and keep #1109 rebased/green.
- [ ] Obtain successful upstream CI and merge or independent external reproduction.
- [ ] Update the evidence package with the D128 negative result and final PR state.
- [ ] Archive #1054's performance route as `retired`; do not reopen the same fusion stack.
- [ ] Start a new performance route only if profiling reveals a mechanism that matters to
      representative D128 forward+backward workloads.

### Done when

- **Correctness outcome:** #1109 is merged or reproduced and adopted independently.
- **Any future performance outcome:** multiple practical D128 shapes on named hardware
  pass correctness, memory, and N>=10 paired forward+backward measurements.

The D64 number may remain a scoped case study; it must not be advertised as general KDA
acceleration.

---

## ARGUS-IR-03 — Create a MiniMax-H3 Speedrun on B200/H100

### Background

A “speedrun” here is a proposed engineering benchmark: everyone runs the same model,
input, hardware class, quality gates, and timer, then tries to reduce time. It is useful
because GPU results are otherwise easy to manipulate by changing resolution, frame
count, denoising steps, precision, warm-up, or what the timer excludes.

No independently verified public MiniMax-H3 speedrun leaderboard has been identified.
Therefore the first deliverable is the protocol and scorer—not a rank. The campaign
should explicitly choose one of MiniMax-H3's task-specific checkpoints (FL2VA or Ref2VA)
and should benchmark local **H3-Base** separately from the complete hosted 2K workflow.

[MiniMax's official model card](https://huggingface.co/MiniMaxAI/MiniMax-H3) describes
H3 as an omni-modal system that packs text, visual, and audio representations into one
sequence. Its 33B dense H3-Omni-Transformer jointly predicts video and stereo-audio
latents. Official output supports 4–15 seconds, 24 FPS, and up to 2K through a three-part
system; H3-Context-IR and H3-Regenerate-2K are hosted/not fully open, while the local
released H3-Base produces the 768p stage. A fair open benchmark must say exactly which
part it measures.

The released H3 checkpoints are BF16 and **CFG-distilled** according to the model card.
“Official checkpoint” means using those published weights; it must not be described as
an undistilled model.

### Relationship to the other campaigns

- IR-01 builds reusable Sol-Engine/Sol-Attn improvements.
- IR-03 supplies a fixed datacenter benchmark and auditable rank.
- IR-04 turns a selected stack into a desktop deployment.
- IR-05 may contribute a low-precision GEMM only after quality feasibility passes.

### Freeze first

- Checkpoint commit and task (for example FL2VA text-to-audio-video).
- Prompt, seed, resolution, frames/duration, FPS, denoising steps, and output container.
- B200 and H100 as separate tracks; GPU count/topology and power mode.
- Precision and permitted approximations; all submissions disclose quantization/cache.
- Cold-start, first-run compile, warm end-to-end, and hot-path timers as separate fields.
- Video and audio validity/quality gates, memory, and failure policy.
- Public scorer, raw-log schema, allowed/forbidden optimization rules, and anti-cheating checks.

### Work

- [ ] Publish protocol v1 before optimization begins.
- [ ] Pin authoritative model and baseline commits and archive the scorer.
- [ ] Produce reproducible B200/H100 baselines with latency, throughput, memory, load,
      compile, and quality data.
- [ ] Keep an Argus experiment ledger: hypothesis, patch, noise, quality, and keep/revert.
- [ ] Optimize graph, attention, GEMM, cache, quantization, kernels, collectives, and scheduling.
- [ ] Re-test individual and combined champion changes; do not bank noise.
- [ ] Submit to a public board or have an independent machine run the same scorer.

### Done when

- The protocol was frozen before the claimed run;
- the quality-qualified gain survives repeated measurements;
- the champion stack rebuilds from a clean environment; and
- there is a public or independently auditable rank, not merely a “faster” statement.

---

## ARGUS-IR-04 — MiniMax-H3 from datacenter to desktop

### Background: why this is a different problem

The official Sol-Engine 3.97× H3 result uses eight GB200 GPUs with rack-scale NVLink.
A DGX Spark has one GB10 with 128-GB-class unified memory; an RTX 5090 has far less memory
and a different instruction/memory balance. Porting H3 is therefore not “rerun the same
script.” It may require quantization, CPU/offload choices, architecture-specific kernels,
smaller concurrency, and careful accounting for compile/startup time.

H3's “33B” names its dense Omni-Transformer, not the size of the whole downloadable
pipeline. The public checkpoint also includes processor/tokenizer, Qwen3-VL-32B text
encoder, visual VAE, and audio VAE. A desktop claim must specify what stays resident,
what is precomputed/freed, and what is offloaded.

### External references, not Argus results

1. **NVLabs official:** 27.21 s to 6.88 s (**3.97×**) for the specified 8×GB200 hot
   path. This is a technical roadmap, not a desktop baseline.
2. **Third-party DGX Spark feasibility:**
   [`joeynyc/MiniMax-H3-DGX-Spark`](https://github.com/joeynyc/MiniMax-H3-DGX-Spark)
   reports one-Spark FL2VA runs with online dynamic FP8. For its 768×448, 2-second,
   20-step fixed request, it reports 152.911 s warmed baseline, 111.373 s for its final
   no-cache full-compute profile, and 80.579 s for an approximate Cache-DiT profile,
   each based on two warm runs. This is useful third-party evidence, but it changes
   precision, uses a small workload, and is neither an NVIDIA benchmark nor an Enze Xie
   result.
3. **RTX 5090:** no primary, reproducible MiniMax-H3 end-to-end result matching the old
   4.52× claim was found in this audit.

### Two honest result tiers

- **Fidelity tier:** official released BF16 checkpoint semantics and no approximate cache
  or weight quantization; exact/lossless engineering changes only.
- **Practical tier:** declared FP8/FP4/W2A4, cache, or offload is allowed, but the result
  must be compared with a same-device baseline and pass explicit audio/video quality
  gates. It cannot be described as lossless or equivalent by default.

A run may qualify in either tier. Mixing the two into one speedup is forbidden.

### Argus goal

Create a clean, one-command MiniMax-H3 deployment on at least one desktop platform and
produce a stable same-device improvement with transparent quality, memory, power,
startup, and compile costs. RTX 5090 feasibility should be gated before promising an
end-to-end target.

### Work

- [ ] Pin the official checkpoint, task, license requirements, and reproducible input.
- [ ] Run a memory/feature preflight for one DGX Spark and one RTX 5090; record infeasible
      tiers instead of silently changing the model.
- [ ] Establish each device's own unoptimized baseline.
- [ ] Port/ablate architecture-compatible kernels, Sol-Attn, cache, quantization, compile,
      and offload independently.
- [ ] Record load time, first run, warm end-to-end latency, FPS, peak device/host memory,
      swap, power, compile cache, and full audio/video decode.
- [ ] Compare audio and video quality across a prompt/seed suite, not one attractive clip.
- [ ] Build container/environment locks, model preparation, one-command run, and verifier.
- [ ] Seek reproduction on a second machine.

### Done when

- At least one platform has a repeated, same-specification gain over its own frozen baseline;
- the fidelity or practical tier is stated without ambiguity;
- quality and resource trade-offs are visible, including approximation/quantization loss;
- a clean machine reproduces deployment and output validation; and
- each major optimization's contribution is shown by ablation.

---

## ARGUS-IR-05 — Build a real W2A4 GEMM

### Background: what does W2A4 mean?

**W2A4** means two-bit weights and four-bit activations. Before multiplication, a model's
large weight matrices are packed into 2-bit values and the current activations into
4-bit values; accumulation normally uses a wider type. In ideal arithmetic storage,
2-bit weights are one eighth the size of BF16 weights and 4-bit activations are one
quarter, but scales, zero points, padding, packing, and temporary buffers reduce the
real saving.

This is not the same as NVIDIA **NVFP4/W4A4**, where both operands use 4-bit formats.
A GPU may have a fast symmetric 4-bit instruction but no direct asymmetric 2-bit ×
4-bit instruction. Software then has to unpack/upcast, split values into bit planes,
use lookup tables, or reconstruct partial products. The winning method can change with
matrix shape: in autoregressive LLMs, large-`M` prefill is compute-heavy while small-`M`
decode is often limited by loading weights. MiniMax-H3 is a diffusion transformer, not
an autoregressive LLM, so it has a different repeated-GEMM shape distribution and LLM
kernel results cannot be transferred without measurement.

Quantization has two separate questions:

1. **Model question:** do W2A4 values preserve acceptable output quality?
2. **Kernel question:** given those exact values/scales, can the GPU multiply them faster?

A fast kernel is useless if the quantized model fails quality, and a good quantizer does
not guarantee a fast kernel.

### External landscape and evidence boundary

The OSDI 2026 paper
[ADAngel](https://www.usenix.org/conference/osdi26/presentation/liu-yao) explains three
mapping families—padding, bit decomposition, and workload-adaptive selection—and uses
a W2A4 bit-disaggregation diagram. Its reported end-to-end evaluation, however, focuses
on combinations including W2A8/W3A8/W4A8/W5A8 on Jetson Orin and A100. It is useful
design background, not a ready B200/H100/RTX 5090 W2A4 baseline.

As of the audit date, no official mature W2A4 implementation was found in the public
CUTLASS or BitBLAS sources searched for this document. That absence is not proof that
none exists; it means baseline discovery is a required first milestone. W4A4/NVFP4
numbers must never be relabelled W2A4.

MiniMax-H3 currently publishes BF16 checkpoints, and Sol-Engine's documented low-precision
path uses NVFP4 in other models. W2A4 must not be assumed to preserve H3 quality. H3
integration proceeds only after a calibrated checkpoint and audio/video quality gate
exist; otherwise this remains an independent GEMM campaign or is retired.

### Feasibility gate

- [ ] Select a target model/layer set and define the exact W2A4 quantization recipe.
- [ ] Measure model quality against BF16 before serious kernel engineering.
- [ ] Inventory current framework, CUTLASS, Triton, BitBLAS, and relevant research baselines
      at pinned commits; document unsupported combinations.
- [ ] Collect real `(M,N,K)`, batch, and concurrency distributions.
- [ ] Stop or pivot if quality fails or the target hardware cannot plausibly beat the
      strongest honest mapping after conversion costs.

### Kernel work

- [ ] Freeze layout, signedness, group size, scale/zero-point semantics, accumulator,
      rounding/saturation, and error tolerance.
- [ ] Implement a slow reference and bit-exact element/matrix tests, including tails.
- [ ] Compare upcast/padding, split/partial-product, bit-plane, and other justified mappings.
- [ ] Optimize packing, dequantization fusion, tiles, pipelines, Tensor Core use, and epilogues.
- [ ] Autotune/dispatch by real shape where one static strategy is not best.
- [ ] Measure latency, throughput, memory, pack/dequant/compile/transfer costs, and power on
      applicable B200/H100/RTX 5090 platforms.
- [ ] Integrate into at least one real model path and measure end-to-end benefit and quality.
- [ ] Publish source, shape suite, raw results, reproduction command, and integration PR.

### Done when

- W2A4 model quality passes a declared application bar;
- the kernel beats strong pinned baselines on multiple representative shapes;
- integration produces a repeated end-to-end gain after all conversion costs; and
- a second machine reproduces correctness and performance.

---

## ARGUS-IR-06 — Prove or refute one Erdős problem

### Background

There is no single “the Erdős conjecture.” Paul Erdős posed or popularized thousands of
problems across number theory, combinatorics, graph theory, and geometry. Each has its own
quantifiers, parameter range, known partial results, and current status.

[UnsolvedMath](https://www.unsolvedmath.com/) is a useful discovery index, but an index
label may lag the literature. The selected statement must be checked against primary
papers and a specialist source such as the
[Erdős Problems database](https://www.erdosproblems.com/). This is not bureaucracy:
a changed inequality, missing condition, or already-resolved version can invalidate
months of work.

For a universal claim—“every object satisfying A also satisfies B”—a **proof** must cover
all allowed objects, while a **counterexample** needs one explicit object satisfying A
and violating B. Testing a billion cases is evidence, not a proof of the universal claim.
Failure to find a counterexample proves nothing by itself.

### Problem-selection gate

Prefer a problem with:

- a short, unambiguous statement and accessible primary references;
- meaningful known partial results but no current resolution;
- exact finite cases or lemmas that software can verify;
- a plausible proof assistant boundary; and
- independent experts willing to review it.

Avoid choosing solely by prize, fame, or a website difficulty badge.

### Lock the problem first

- [ ] Record database ID, exact statement in LaTeX, all quantifiers, parameter domain,
      equivalent forms, prize/status, and source versions.
- [ ] Perform a current literature search and contact the database editor or a domain expert.
- [ ] Have a mathematician sign off that the frozen statement is open and copied correctly.
- [ ] Publish a statement hash/version before large search; difficulty may not cause silent drift.

### Proof and counterexample tracks

- [ ] Build a source packet of known theorems, failed approaches, equivalent formulations,
      and computable small cases.
- [ ] Maintain proof and counterexample tracks in parallel; record what each failure rules out.
- [ ] Use exact arithmetic, replayable code, deterministic seeds, and complete stated ranges.
- [ ] For a counterexample, provide the object, a minimality claim only if proved, an
      independent verifier, and a second implementation/proof.
- [ ] For a proof, check every lemma, dependency, boundary case, and quantifier; a sketch is
      not a completed result.
- [ ] Formalize suitable parts in Lean/Isabelle/Coq; clearly mark any remaining trusted axioms
      or informal steps.
- [ ] Send the complete artifact to at least two independent domain reviewers and check novelty.

### Done when either

1. a complete proof passes independent expert review and becomes a public manuscript,
   with formal verification where feasible; or
2. an exact counterexample is reproduced by two independent verifiers and violates the
   frozen original statement exactly.

Finite checks, numerical evidence, “the model believes it,” or an argument for a nearby
variant do not enter the official result list.

---

## Recommended order

1. **Land FLA #1109 and archive #1054 honestly:** this is closest to upstream verification;
   do not spend more time on the disproven D64-to-D128 fusion assumption.
2. **Freeze and reproduce one Sol-Engine baseline:** only then profile a new Sol-Attn/kernel
   contribution.
3. **Publish MiniMax-H3 Speedrun protocol v1:** rules must precede optimization.
4. **Build the DGX Spark desktop tier first:** use it to establish packaging and quality
   methodology before promising RTX 5090 feasibility.
5. **Gate W2A4 on model quality and baseline discovery:** kernel work follows evidence.
6. **Run the Erdős track independently:** lock the statement and reviewers without blocking
   the GPU campaigns.

## Record template for an official result

```text
RESULT_ID=
TITLE=
ONE_LINE_RESULT=
STATUS=certified|externally-verified|shipped
CLAIM_SCOPE=
BASELINE_REPO_AND_COMMIT=
ARGUS_REPO_AND_COMMIT=
HARDWARE_AND_SOFTWARE=
WORKLOAD_TIMING_BOUNDARY_AND_QUALITY_BAR=
MEASURED_RESULT=
REPEAT_COUNT_AND_VARIANCE=
REPRODUCE_COMMAND=
CODE_OR_PR=
RAW_EVIDENCE=
ARGUS_SESSION_AND_TRACE=
HUMAN_CONTRIBUTIONS=
INDEPENDENT_VERIFICATION=
KNOWN_LIMITATIONS=
```

The public result page should contain only qualified results. Failed routes, negative
results, and rejected claims remain visible in each campaign's evidence directory.

## Primary sources used for this background audit

- [NVLabs Sol-Engine branch](https://github.com/NVlabs/Sana/tree/sol-engine) and
  [paper](https://arxiv.org/abs/2606.23743)
- [Official Sol-Engine MiniMax-H3 case study](https://github.com/NVlabs/Sana/blob/sol-engine/models/minimax_h3/README.md)
- [Sol-Attn paper](https://arxiv.org/abs/2607.24027)
- [MiniMax-H3 official model card](https://huggingface.co/MiniMaxAI/MiniMax-H3)
- [Enze Xie public profile](https://xieenze.github.io/) and
  [SANA paper](https://arxiv.org/abs/2410.10629)
- [Kimi Linear paper](https://arxiv.org/abs/2510.26692) and
  [FLA repository](https://github.com/fla-org/flash-linear-attention)
- [FLA PR #1054](https://github.com/fla-org/flash-linear-attention/pull/1054) and
  [focused PR #1109](https://github.com/fla-org/flash-linear-attention/pull/1109)
- [ADAngel, OSDI 2026](https://www.usenix.org/conference/osdi26/presentation/liu-yao)
- [UnsolvedMath](https://www.unsolvedmath.com/) and
  [Erdős Problems](https://www.erdosproblems.com/)
