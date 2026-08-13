当前 `math` vertical 已经是一个合适的“薄控制壳”：只有 `scope → solve → review` 三个粗粒度阶段，采用 proportional workflow；文献检索、反例搜索、计算、自然语言证明和 Lean 都被定义为按问题需要选择的方法，而不是固定流水线阶段。这一取舍应当保留。真正缺失的是 vertical 下方的 **Math Research Substrate**：版本化数学状态、proof-obligation DAG、异步证据、失效传播和受控经验蒸馏。

可以把目标架构理解为：

```text
现有 Argus 控制层
Manager → Planner → Backlog Execution DAG → Engineer ↔ Reviewer
                           │
                           ▼
新增 Math Research Substrate
Semantic State │ Proof DAG │ Evidence/Trust │ Async Jobs │ Context Projection
                           │
          ┌────────────────┼─────────────────┐
          ▼                ▼                 ▼
     Literature          Code/CAS           Lean
```

不是：

```text
Argus
  └── 另一个完整的 Math multi-agent framework
```

---

# 一、当前已经很适合直接接入的 principles

## 1. Goal fidelity、human steering 和权限分层

Argus 已经明确区分：

* Manager 管目标、范围和阶段；
* Planner 只读检查现状并选择下一步；
* Engineer 产生工作；
* Reviewer 独立裁决；
* harness 不应该靠关键词或结构化标签自行冒充科学判断。

这与 Research Director、Mathematical Strategist、Solver、Verification Council 的职责分离高度兼容。无需新增一批平级 authority，只需要给现有角色增加数学状态接口。 

当前 Math role skills 也已经强调：

* 不把 partial progress 当成完整证明；
* 失败路线是证据，不是成功；
* 不把 finite computation 称作 universal proof；
* Lean 编译不能补偿 statement mistranslation；
* novelty 未经检索不能过度声称。

这些原则本身不需要修改 Argus core。

## 2. Generation 与 criticism 分离

现有每一轮 Engineer 和 Reviewer 都使用独立 fresh session，Reviewer 是正常路径上的唯一完成裁决者。这个结构已经比许多 multi-agent math systems 更干净，因为不会让 proof author 自己给自己签发最终证书。

因此可以直接映射：

```text
Deep Thinker / proof worker  → Engineer 或受监督 subagent
Critic / referee             → Reviewer
Lean / code verifier         → objective evidence producer
最终任务控制                 → Reviewer 的 done/continue/blocked/replan
```

要增加的是 Reviewer 看到的数学证据结构，不是再引入一个与 Reviewer 争夺 authority 的 “Verification Council controller”。

## 3. Failure as data、append-only provenance 和 replan

Argus 已经有：

* canonical `events.jsonl`；
* terminal backlog items 不可复活；
* 新尝试必须建立新 item；
* plan revision 会显式 supersede 旧计划；
* dependency cycle 检查；
* 失败依赖向下游级联；
* Planner 可以整体替换一个活跃 plan revision。

这非常适合作为研究过程的 execution/provenance 基础。

需要注意：它只能直接承担 **Execution DAG**，不能同时承担数学语义图和 proof DAG。这一点后面会详细讨论。

## 4. Uncertainty、abstention 和多种合法终止结果

现有 `research_contract.py` 已经区分：

* result class；
* correctness；
* novelty；
* significance；
* statement fidelity；
* exploratory / publishable / doctoral target。

这与报告中“不把 correctness、novelty、significance 压成一个 confidence score”的原则一致。

它可以继续作为 **project-level result manifest**。但它粒度太粗，不能替代 claim-level evidence ledger。正确做法是保留它，在其下方增加：

```text
root_claim_ref
supporting_claim_refs
evidence_refs
open_assumption_refs
formalization_status
conditional_or_closed
```

## 5. 异步工具和长任务

Argus 已经有相当合适的 external-work protocol：

* 区分执行存活状态和科学有效性；
* 有 heartbeat、stale、terminal、needs-attention；
* Engineer 可以在外部作业运行期间继续独立工作；
* 只有所有剩余工作都依赖该作业时才进行受控等待；
* 文件增长或进程仍活着不会被当作科学进展。

这几乎就是异步 Lean、长时间 CAS、文献下载或大规模反例搜索所需的底层机制。

真正缺失的是数学语义层：

```text
这个 Lean job 正在验证哪个 claim version？
绑定了哪些 definition/context versions？
结果回来时目标是否已经变化？
成功是 closed proof 还是 conditional proof？
失败是 proof attempt 失败，还是 statement 被反例推翻？
需要使哪些下游路线 stale？
```

因此异步进程基础设施不必重写，只需增加数学 job manifest、结果 reconciliation 和 dependency invalidation。

## 6. 粗粒度、非固定的 research workflow

当前 Math vertical 明确反对把 retrieval、computation、Lean 等变成 mandatory stages，这是正确的。继续保留：

```text
scope
solve
review
```

所有这些活动都应发生在 `solve` 内部，并由数学状态和 Scheduler 决定下一动作。Formalization 发现 statement 错误时，可以产生 `replan_requested`，回到新的 scope/solve plan，而不是新加十几个 lifecycle stages。

---

# 二、与 Argus 兼容，但需要新增 substantive subsystem 的 principles

这些不是 core 冲突，单靠修改 prompt 却实现不了。

## 1. Versioned Research Semantic Graph

Argus 当前有 backlog DAG、event history、CHECKPOINT 和 wiki，但没有一等公民的：

* context version；
* definition version；
* claim version；
* mechanism；
* equivalence/generalization/contradiction；
* evidence-to-claim relation；
* claim supersession；
* reverse mathematical dependency。

需要新增独立的数据模型，而不是继续往 `BacklogItem.notes` 或 `CHECKPOINT.md` 里塞自然语言。

## 2. Per-claim AND–OR proof DAG

现有 backlog DAG 只表示：

> 某个 mission 在另一个 mission 完成之后才能执行。

它不表示：

> Claim (T) 有两条 alternative routes；route A 同时需要 (L_1,L_2)，route B 同时需要 (L_3,L_4)。

现有 DAG 已经有无环校验和拓扑调度，可复用其算法思想，但不能复用同一组节点和 `deps` 字段。Planner 的 bounded DAG 本质上也是 execution plan，而且默认要求尽量把相关工作合并成一个 cohesive node，不是 proof search graph。

建议表示为：

```text
ClaimVersion                    # OR node
  ├── ProofRoute A              # AND node
  │     ├── requires Claim L1
  │     └── requires Claim L2
  └── ProofRoute B
        ├── requires Claim L3
        └── requires Claim L4
```

这样不必显式创建抽象 OR node：一个 claim 自然就是其所有 proof routes 的 OR。

## 3. Mechanism 作为一等对象

当前 Math prompts 能让 agent 在自然语言中讨论 mechanism，但没有结构化保存和复用机制。

MVP 中不用把它做得很重，可以先定义：

```python
MechanismVersion:
    id
    version
    title
    requirements: list[SubjectRef]
    provides: list[SubjectRef]
    gaps: list[ClaimRef]
    applicability
    failure_boundary
    supporting_evidence
    provenance
```

Mechanism 不是 verified theorem，也不是 execution task。它是连接若干 facts 与目标 consequence 的可复用研究资产。

## 4. Claim-level evidence vector 和 trust lattice

现有 project-level research result 是一个好的粗粒度输出，但无法回答：

* 哪个 lemma 只有 LLM support？
* 哪个有 exhaustive computation？
* 哪个 Lean proof 依赖外部 axiom？
* 哪个 citation 已经核对 theorem number？
* 哪个自然语言 statement 与 Lean statement 尚未对齐？

需要给每个 `ClaimVersion` 建立独立维度：

```text
truth_status
informal_proof_status
formal_status
statement_fidelity_status
citation_status
novelty_status
uncertainty
open_assumptions
```

而不是单个 `verified=true`。

## 5. Target-specific context distillation

现有 `context_refs` 是非常合适的接入点。Mission packet 已经携带：

* objective；
* acceptance check；
* non-goals；
* plan identity；
* dependencies；
* versioned references。

Planner task 去重还会使用 reference 的 `content_hash`，因此上游 artifact 变化后，同一任务可以合法重新运行。

需要新增 `MathContextProjector`，为每个 mission 生成：

```text
target claim/version
exact assumptions and definitions
immediate proof dependencies
currently open obligations
relevant mechanisms
evidence delta
known failed routes
open external assumptions
artifact references
allowed state transitions
```

这个动态 ContextBundle 不应进入静态 `role_banner`，否则会破坏 prompt prefix caching，也会把整个项目状态塞给每个 agent。应在每个 mission/round 中作为动态 delta 注入。

## 6. Experience distillation

Argus 已经有 Scientist、skill adaptation、skill version history 和使用结果记录，因此接口层很接近目标。

但现有 SkillStore 的安全语义不够严格：结构合法的新 skill 可以很快进入 active pool，主要依赖后续成功/失败统计和 quarantine 来纠错。对数学研究经验而言，这容易把一次偶然成功或 verifier bias 写成长期策略。

因此 Math vertical 需要先有一个独立的：

```text
MathStrategyCandidateStore
```

状态为：

```text
proposed
quarantined
shadow_tested
canary
promoted
rejected
superseded
```

只有 promoted candidate 才编译成普通 Argus Skill。

---

# 三、与 Argus 本体存在的主要冲突，以及建议取舍

## 冲突 1：report 中的 specialist swarm 与 Argus 的四角色 authority

报告中有 Deep Thinker、Contrarian、Literature Cartographer、Computational Lab、Formalization Team、Experience Distiller 等多个组件。

不建议把它们都变成 Argus 的新 persistent roles。Argus 当前清晰的 Manager–Planner–Engineer–Reviewer authority graph 是优势，不应破坏。

建议映射：

| Report component        | Argus 中的实现                              |
| ----------------------- | --------------------------------------- |
| Research Director       | Manager + Planner                       |
| Mathematical Strategist | Planner 的 math skill                    |
| Deep Thinker            | Engineer 的一种 execution capability       |
| Approach Portfolio      | 受监督、隔离的 subagent portfolio              |
| Contrarian              | portfolio policy / 专门任务                 |
| Literature Cartographer | retrieval worker + citation certificate |
| Computational Lab       | external verifier adapter               |
| Formalization Team      | Lean external workers                   |
| Verification Council    | Reviewer + heterogeneous evidence       |
| Experience Distiller    | Scientist + candidate store             |

核心原则是：

> **specialists 产生 artifacts 和 evidence；现有四角色继续拥有控制权。**

## 冲突 2：把整个 research state 都当作一个 DAG

Argus 已经有 backlog DAG，很容易诱导实现者把 claim、proof、task 和 provenance 全部塞进去。这应明确禁止。

建议维持四种结构：

```text
Math Semantic Graph
    typed/versioned，允许环

Per-Claim Proof DAG
    AND–OR，无环

Argus Backlog DAG
    execution dependencies，无环

events.jsonl
    append-only provenance
```

`BacklogItem.deps` 只能表示执行依赖，不表示逻辑蕴含，也不表示一个 theorem 依赖另一个 theorem。

## 冲突 3：真正的 breadth portfolio 与同步 LifeSupervisor

Argus 的 LifeSupervisor 是一次 claim 一个 mission、执行一个 mission 后再进行下一步的同步 scheduler；bounded Planner prompt 也明确要求不要随意 spawn subagents。

因此不能仅修改 Math prompt 就声称已经实现并行 approach portfolio。

建议分阶段取舍：

* **MVP 保持主 Supervisor 同步**；
* Lean、code、retrieval 等作为 async external work；
* 真正的多路线 reasoning 先由一个 Engineer 启动受监督、只读或隔离 workspace 的 portfolio；
* portfolio workers 不直接写 canonical MathState；
* 结果作为 proposal 返回，由主 Engineer/Reviewer 合并；
* 后期增加显式任务字段：

```text
execution_mode = direct | portfolio | external
capabilities = [deep_think, contrarian, literature, lean, code]
```

不要用普通 tags 隐式改变并发语义。

## 冲突 4：严格 stage gate 与 event-driven research

Argus 强调只能做当前 stage 工作。对细粒度数学研究而言，formalization、retrieval、counterexample 和 reformulation 会频繁交错。

取舍是保留粗 stages，但不要增加：

```text
literature_stage
conjecture_stage
proof_stage
formalization_stage
verification_stage
```

`solve` 应被视为一个 event-driven research loop。Reviewer 发现 statement mismatch 时返回 `replan_requested`，Manager/Planner 创建新的 plan revision，而不是让 lifecycle state machine倒退十个阶段。

## 冲突 5：externalized state 与当前 Math skill 的 “不要做 process paperwork”

现有 Math prompts 明确反对为了流程而创建 graph、ledger、audit 文档。这是正确的，因为让 agents 手动维护 Markdown DAG 会迅速变成形式主义。

取舍应是：

> **MathState 是 harness-owned runtime state，不是 Engineer 的文档 deliverable。**

Agent 只能通过结构化 command 提交 delta：

```text
propose_claim
revise_claim
propose_mechanism
propose_proof_route
attach_evidence
request_verification
```

状态服务执行：

* schema validation；
* expected-version check；
* cycle detection；
* transaction；
* event emission；
* projection update。

CHECKPOINT 和 wiki 只展示人类可读投影，不作为 canonical state。

## 冲突 6：最小 Reviewer verdict 与 evidence vector

当前 Reviewer 控制输出刻意保持很小，正常 verdict 核心是：

```text
done
continue
blocked
replan_requested
```

而且代码明确规定 harness 不应根据结构化结果标签推翻 Reviewer 的科学裁决。

不应把 Reviewer 改成输出一个复杂 JSON，然后让 harness 自己根据分数决定 done。

正确取舍是扩展：

```python
ReviewDecision:
    status
    reason
    next_action
    operator_question
    vertical_payload: dict   # optional
```

其中 `MathReviewPayload` 只保存：

```text
reviewed_claim_refs
accepted/rejected evidence refs
fidelity status
formal status
open assumptions
citation status
requested invalidations
```

顶层控制 authority 仍然是 Reviewer 的 `status`。

## 冲突 7：线性 completion rank 与数学 trust lattice

Argus 当前 completion API 把来源按弱到强做线性排序：

```text
planner verdict
vertical certificate
reviewer full-paper gate
```

vertical gate 也是 `none / metric / full_paper`。

数学结果不能被放进同一条线性 rank：

* exact counterexample 与 closed Lean proof 不存在普遍强弱关系；
* conditional Lean proof 可能很可靠，但有外部 assumption；
* novelty 与 correctness 是正交维度；
* publishability 不能由 kernel certificate 自动推出。

因此不要增加：

```text
math_result rank = 2.5
```

而应增加 generic optional hook：

```python
vertical_completion_evaluator(...)
```

Math evaluator 根据目标类型和 trust contract 决定：

```text
proof problem:
    fidelity verified
    correctness verified
    requested theorem proved
    open assumptions allowed only if objective permits conditional result

counterexample problem:
    witness satisfies exact hypotheses
    violation independently checked

publishable target:
    correctness + fidelity + novelty protocol + significance review
```

在该 hook 完成之前，先保留当前 `completion_gate="none"`，避免半实现状态改变已有行为。

## 冲突 8：append-only progress 与数学判断的可撤销性

Argus 的 terminal task 不可复活是正确的；数学 claim 却必须可被推翻。

取舍是：

```text
append-only:
    events
    evidence
    artifacts
    old claim versions
    completed missions

non-monotone:
    current claim status
    current favored formulation
    current route priority
    novelty assessment
    dependency validity
```

例如 `Claim C@v1` 被证明后，definition 更新产生 `C@v2`：

* `C@v1` 的 proof 不删除；
* 它继续是旧 context 下的有效 artifact；
* `C@v2` 状态为 unverified；
* 所有把旧 proof 当作新 claim 证据的 route 被标 stale；
* 创建新的 revalidation backlog item；
* 不把原来的 terminal mission 改回 pending。

## 冲突 9：当前 deep research 实际没有完全接通

这里有一个具体实现问题。

Engineer 的 live search 默认只在名为 `research` 的 stage 启用；而 Math vertical 的 stages 是 `scope/solve/review`，因此 Math Engineer 默认很可能不会获得 native live search。Planner 的 `RunnerOptions` 当前也没有设置 `live_search=True`。Reviewer 虽然打开了 search，但 Reviewer 不应承担主要文献研究工作。

这应作为较早的修复：

* Planner 在 Math vertical 下允许 live search；
* Engineer 在 `scope` 和需要文献检索的 `solve` task 下允许 live search；
* 最终最好从 stage-based 改为 task capability-based：

```text
TASK_CAPABILITIES=literature_search,lean,code
```

---

# 四、推荐的数据模型

不建议第一版上 Neo4j。Argus 是本地、单项目、事务性较强的系统，SQLite 更合适：

```text
events.jsonl
    canonical append-only history

math_state.sqlite
    rebuildable/queryable projection

artifact store
    Lean files, code, paper snapshots, reports
```

建议新增包，而不是把逻辑都堆进 `verticals/math/stages.py`：

```text
argus_skill/research_math/
    models.py
    commands.py
    store.py
    events.py
    projection.py
    obligations.py
    mechanisms.py
    context.py
    invalidation.py
    review.py
    completion.py
    distillation.py
    verifiers/
        base.py
        lean.py
        code.py
        literature.py
```

`verticals/math/` 继续只负责：

* stage declaration；
* role skills；
* checklists；
* hook registration；
* Math vertical policy。

`math_synth` 应继续保持为独立 vertical，不与 research-math runtime 合并；两者的目标和完成语义不同。

## 核心实体

```python
ContextVersion:
    context_id
    version
    parent_version
    definitions
    assumptions
    notation
    content_hash

ClaimVersion:
    claim_id
    version
    context_ref
    natural_statement
    formal_statement_ref
    logical_shape
    truth_status
    formal_status
    fidelity_status
    citation_status
    novelty_status

MechanismVersion:
    mechanism_id
    version
    requirements
    provides
    gaps
    applicability
    failure_boundary

ProofRoute:
    route_id
    parent_claim_ref
    required_claim_refs
    mechanism_refs
    status

EvidenceRecord:
    evidence_id
    subject_ref
    evidence_type
    verdict
    conditions
    artifact_refs
    producer
    tool_versions
    created_at

ExternalAssumption:
    assumption_id
    exact_statement
    source_ref
    theorem_number
    fidelity_status
    citation_status
    formalization_status

VerificationJob:
    job_id
    verifier_kind
    subject_ref
    context_hash
    input_artifact_hashes
    toolchain_versions
    state
    result_ref
```

## 建议的状态分离

```text
truth_status:
    proposed | supported | refuted | superseded | unknown

formal_status:
    none
    statement_checked
    skeleton_verified
    partial
    conditional_kernel
    closed_kernel
    stale

fidelity_status:
    unreviewed | verified | failed

citation_status:
    none | discovered | certified | failed

novelty_status:
    unchecked
    no_match_under_protocol
    known
    uncertain
```

这里最重要的是：

> `conditional_kernel` 和 `closed_kernel` 必须是两个状态。

Mathlib 缺少的文献定理进入 `ExternalAssumption`。下游 Lean proof 即使通过，也只能是 conditional，直到该 assumption 被 Mathlib theorem、local formalization 或其他可信 certificate 消除。

---

# 五、需要给 Argus core 增加的最小通用扩展点

大部分 Math 代码可以放在 `research_math/`，但有三个 core seam 是不可避免的。

## 1. Dynamic vertical context hook

当前 vertical hook 主要提供 role banner、stage checklist、completion gate、workflow mode 和 search altitude；没有每个 mission 动态生成 structured context 的接口。

建议增加：

```python
class VerticalRuntimeHooks(Protocol):
    def build_mission_context(
        self,
        *,
        role: RoleName,
        mission: MissionContext,
        context_refs: list[ContextRef],
    ) -> DynamicContextFragment | None: ...
```

该 fragment 作为 prompt delta 注入，而不是并入静态 role banner。

## 2. Optional reviewer extension payload

```python
@dataclass
class ReviewDecision:
    ...
    vertical_payload: dict[str, Any] = field(default_factory=dict)
```

Parser 对 Math payload fail-soft：

* payload malformed：保留合法的顶层 verdict，但忽略 payload；
* 若任务 completion 明确要求 Math certificate，则缺失 payload 导致不能完成；
* harness 不根据 payload 中的 score 自己推翻 Reviewer status。

## 3. Pluggable completion evaluator

```python
def vertical_completion_evaluator(
    project_root,
    source,
    evidence_refs,
) -> CompletionOutcome | None:
    ...
```

返回 `None` 时走现有 `none/metric/full_paper` 逻辑；Math vertical 返回 claim-aware completion result。

此外还建议有一个通用安全边界 hook：

```python
def reconcile_vertical_external_work(...):
    ...
```

在 Planner cycle、Engineer context assembly 和 Reviewer invocation 之前导入已完成的异步 evidence。

---

# 六、异步 Lean 的具体执行协议

建议直接复用 `.argus_external_work`，但给 Lean job 增加一个 immutable manifest：

```json
{
  "job_id": "lean-...",
  "claim_ref": "claim:C17@v3",
  "context_ref": "context:K4@v8",
  "context_hash": "...",
  "natural_statement_hash": "...",
  "lean_statement_hash": "...",
  "source_commit": "...",
  "lean_version": "...",
  "mathlib_commit": "...",
  "lake_manifest_hash": "...",
  "external_assumption_refs": ["assumption:A2"],
  "requested_check": "closed_or_conditional"
}
```

完成后的 reconciler 执行：

1. 检查 job subject 是否仍是当前 claim/context version；
2. 若 hash 不匹配，结果记为 `stale`，不能晋升当前 claim；
3. 若 Lean 编译失败，只生成 `proof_attempt_failed` evidence；
4. 若 Lean 成功且存在未关闭 assumption，标记 `conditional_kernel`；
5. 若 Lean 成功、无 `sorry`、无未授权 axiom、所有 dependencies closed，标记 `closed_kernel`；
6. 若 code/Lean 发现真正 counterexample 或 formal inconsistency，更新 claim truth/fidelity；
7. 计算 reverse dependency closure；
8. 将依赖路线标为 stale/invalid；
9. 创建新的 recovery/revalidation backlog items；
10. Reviewer 在下一次安全边界看到这些 delta。

Lean job 不应阻塞其他 reasoning。只有当所有剩余高价值工作都依赖该结果时，Engineer 才使用现有 external-work wait。

---

# 七、按 PR 划分的实现计划

## PR 0：固定 architecture invariants 和 characterization tests

先写一份小型 ADR，并用测试锁住以下边界：

* 四角色 authority 不变；
* `scope/solve/review` 不扩张成固定数学流水线；
* backlog DAG 只表示 execution；
* events 是 canonical history；
* CHECKPOINT/wiki 不是 canonical MathState；
* Reviewer 顶层 status 仍是控制 authority；
* agents 不直接写 canonical SQLite；
* 所有 proof/evidence 必须绑定版本。

这一 PR 不增加功能，只防止后续实现逐渐形成第二套架构。

## PR 1：Math state kernel

新增 `argus_skill/research_math/`：

* dataclasses/schema；
* SQLite projection；
* command validation；
* context/claim/mechanism/evidence versioning；
* expected-version optimistic concurrency；
* idempotency key；
* reverse dependency query；
* typed `research.math.*` events。

建议每次数学状态 transaction 以一个原子事件表达：

```text
research.math.transaction.committed
```

事件包含规范化 mutations 或其 artifact hash。SQLite 可以从事件重建，避免 JSONL 与 SQLite 在 crash 时产生无法恢复的分叉。

验收：

* 不能原地覆盖 claim；
* 旧版本永久可追溯；
* 并发提交有 expected-version conflict；
* event replay 能重建相同 SQLite state。

## PR 2：ContextBundle 和 live-search 接入

增加 generic dynamic-context hook，并让 Math vertical 生成 target-specific bundle。

修改方向：

* `verticals/_base.py`
* `roles/prompts/types.py`
* `roles/prompts/registry.py`
* `life/context_packet.py`
* `skills/loop_prompt.py`
* `engineer/round_prompt.py`

同时修复 deep research：

* Math Planner 可 live search；
* `scope` 阶段 Engineer 可 search；
* `solve` 中由 task capability 决定是否 search；
* search result 默认是 exploratory evidence，不自动成为 certified citation。

验收：

* 两个不同 claim mission 收到不同 ContextBundle；
* bundle 有稳定 hash；
* upstream state 变化后任务 dedup signature 变化；
* agent 不需要读取整个 event history 或 SQLite；
* prompt 中不泄漏无关 branches。

## PR 3：Proof obligations 与 mechanisms

实现：

* Claim 作为 OR node；
* ProofRoute 作为 AND node；
* obligation cycle detection；
* shared lemma reuse；
* route solved/invalid propagation；
* mechanism requirements/provides/gaps；
* prove/disprove 对称任务类型。

给 Math Planner/Engineer 增加结构化操作：

```text
decompose_claim
propose_route
prove_obligation
search_counterexample
compare_mechanisms
revise_formulation
```

验收：

* 两条 alternative routes 正确表示 OR；
* 一条 route 的多个 obligations 正确表示 AND；
* 公共 lemma 只需解决一次；
* 循环 decomposition 被拒绝；
* route failure 不自动 refute parent claim；
* exact counterexample 可以 refute claim。

## PR 4：异步 verification plane

先实现统一 verifier interface：

```python
submit(job) -> JobRef
inspect(job_ref) -> JobStatus
reconcile(job_ref) -> EvidenceDelta
```

第一批 backend：

* Lean；
* Python/code counterexample；
* generic command verifier。

复用现有 external-work liveness，不重写 process supervisor。

验收：

* Lean 运行时独立 reasoning mission 仍可执行；
* statement v1 的 Lean success 不能 certify v2；
* Lean compile failure 不把 theorem 标 false；
* counterexample 会触发正确的 reverse invalidation；
* daemon restart 后能够继续 reconcile terminal job；
* toolchain、Mathlib commit 和 artifact hash 全部可追溯。

## PR 5：Math Reviewer payload、trust gate 和 completion

扩展 `ReviewDecision.vertical_payload`，定义：

```python
MathReviewPayload:
    subject_refs
    accepted_evidence_refs
    rejected_evidence_refs
    fidelity_status
    formal_status
    citation_status
    open_assumption_refs
    invalidated_refs
    confidence_notes
```

增加 `MathResultManifest`，并映射到现有 `research_contract.py` 的粗粒度字段。

实现 custom completion evaluator：

```text
hard gates:
    goal fidelity
    correctness
    required evidence integrity

then:
    novelty
    significance
    exposition
```

验收：

* 高 novelty 不能补偿低 correctness；
* closed Lean proof 不能补偿 statement mismatch；
* conditional proof 不能标为 closed；
* malformed Math payload 不会伪造 Reviewer verdict；
* project completion 必须引用 root claim 和 decisive evidence。

到这里已经形成第一个可用 vertical slice。

## PR 6：Literature theorem 与 external-assumption boundary

实现：

* source snapshot；
* theorem-level record；
* theorem number；
* exact hypotheses/conclusion；
* definition mapping；
* citation certificate；
* discovered → certified promotion；
* `ExternalAssumption`；
* formalization backlog。

验收：

* 仅搜索到论文不能作为 certified theorem；
* assumption mismatch 会使 citation certificate 失败；
* 引用未形式化 theorem 的 Lean proof只能是 conditional；
* 后续 formalization 完成后可自动把所有下游 conditional proofs 重新排队检查。

## PR 7：Portfolio reasoning

在状态和 evidence 基础稳定后再加入：

```text
execution_mode:
    direct
    portfolio
    external
```

Portfolio workers：

* fresh session；
* 隔离 workspace；
* 可以使用 information firewall；
* 不直接改 canonical MathState；
* 只提交 candidate claims/mechanisms/routes；
* 主 Engineer 或 Reviewer 合并。

Scheduler 第一版不用学习算法，使用显式启发式即可：

[
\text{priority} =
f(
\text{critical-path value},
\text{expected information gain},
\text{downstream fanout},
\text{decisiveness},
\text{diversity contribution},
\text{estimated cost}
).
]

同时保留：

* minimum exploration floor；
* contrarian quota；
* long-shot budget；
* 不读取 strategy memory 的 cold-start branch。

## PR 8：受控 experience distillation

新增 `MathStrategyCandidate`：

```text
trigger
preconditions
procedure
expected signals
known failure modes
scope
supporting trajectory refs
counterevidence
model/tool versions
```

流程：

```text
trajectory
→ candidate extraction
→ quarantine
→ replay / shadow comparison
→ canary
→ promotion
→ ordinary Argus Skill
```

第一版可以要求人工 promotion；之后再做 held-out problem families 和自动 canary。不要让一次成功 trajectory 直接更新 production routing。

---

# 八、建议优先完成的 MVP

第一版不需要：

* graph UI；
* Neo4j；
* 并行主 missions；
* learned scheduler；
* 自动 skill promotion；
* 完整 theorem search engine；
* 所有 accepted results 都 F3 Lean；
* 十几个专门 agent roles。

第一版应只实现这五件事：

1. versioned claim/context/evidence；
2. per-claim AND–OR proof DAG；
3. target-specific ContextBundle；
4. async Lean + stale detection + invalidation；
5. Math Reviewer payload + conditional/closed trust + custom completion。

一个合格的端到端测试应当是：

```text
1. 建立 root claim C@v1
2. Planner/Engineer 提出两个 proof routes
3. Route A 分解出 L1、L2
4. Route B 启动 counterexample search
5. L1 启动异步 Lean job
6. 系统继续研究 L2
7. 中途 statement 修订为 C@v2
8. L1 的旧 Lean job 返回成功
9. reconciler 发现版本不匹配，将结果标 stale
10. counterexample worker 找到 C@v2 的精确反例
11. 系统 refute C@v2，失效相关 routes
12. Reviewer 以 exact counterexample 结束任务
```

另一个必须通过的测试是：

```text
1. 下游 theorem 依赖 Mathlib 中不存在的文献定理 E
2. E 被登记为 ExternalAssumption，带精确 citation
3. 下游 Lean proof 编译成功
4. 状态只能是 conditional_kernel
5. E 后续被正式形式化
6. 系统重新验证下游 proof
7. 成功后晋升为 closed_kernel
```

# 最终取舍

基于当前 repo，我认为最正确的边界是：

[
\boxed{
\text{Argus Backlog DAG = 执行}
}
]

[
\boxed{
\text{Math Semantic Graph = 数学语义}
}
]

[
\boxed{
\text{Per-Claim Proof DAG = 逻辑依赖}
}
]

[
\boxed{
\text{events.jsonl = 历史与 provenance}
}
]

同时：

* 保留 Manager–Planner–Engineer–Reviewer 四个 authority；
* specialists 只作为 capability/subagent/verifier；
* 保留 `scope/solve/review` 三阶段；
* MathState 由 harness 管理，不让 agent 手写图和 ledger；
* Reviewer verdict 保持简单，证据向量作为扩展 payload；
* completion 使用 trust contract，不使用单一 rank；
* self-evolution 先进入 candidate lifecycle，不直接写 active skills。

因此，最先值得落地的不是更多 Math prompts，而是 **PR 1 的 versioned MathState kernel 和 PR 2 的 dynamic ContextBundle seam**。没有这两层，Lean、portfolio、mechanism 和 distillation 最终都会退化成散落在 CHECKPOINT、Reviewer prose 和 Markdown skills 中的不可计算状态。
