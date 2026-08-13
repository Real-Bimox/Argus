# Argus Math 计划评审与可行性分析

评审对象：`research-math-principles.md`、`argus-math-goal.md`、`argus-math-plan.md`
评审方式：逐条对照 `argus_skill/` 源码核实计划中关于 Argus 现状的论断
评审日期：2026-08

**总结论：方向判断基本正确，九条冲突里五条诊断准确。但有六处事实前提需要修正，其中两处显著改变成本估计（PR2 变便宜、PR4 变贵），另有两处新发现使首批工作比计划设想的更容易见效。**

---

## 一、三份文档的评价

### 1.1 `research-math-principles.md`

质量最高的一份。两条真正的架构约束是：

- **`10 个相似 LLM judges ≠ 10 个独立 verifier`** —— 推出「verification 必须异构」
- **statement fidelity ⊥ proof validity** —— 推出「formalization agent 不能给自己发保真证书」

这两条不是口号，是能直接机械化的设计约束。

两个问题：

1. 文中 `citeturn14view1` 一类标记是检索工具残留，落进仓库文档应清掉或换成真链接。
2. §「过度 orchestration 伤害 discovery」提出的 **monolithic deep-think lane 在 plan 里没有落点**。PR7 只处理了 portfolio。这与 Argus 的 bounded-mission + 每轮 Reviewer 裁决结构存在真实张力，不是加个 prompt 能解决的（处理方案见 §5.4）。

### 1.2 `argus-math-goal.md`

三层分层（Adapter / Kernel / Policy）和「`research_math/` 不 import 角色」是正确直觉，与 core 现有的 AST 边界测试（`tests/core/test_vertical_contract.py:159`）同构。

**但文末的判据会否决自己的 plan PR7。** 判据原文：「不要为了实现 portfolio reasoning，把 Argus 的一个 Engineer mission 逐渐变成隐藏在内部的第二个完整 orchestrator。」而 PR7 描述的正是「一个 Engineer 启动受监督 portfolio、workers 提交 proposal、主 Engineer 合并」。这个矛盾必须显式裁决（见 §5.3）。

### 1.3 `argus-math-plan.md`

九条冲突里五条诊断准确且理由充分，四条前提有误。四结构分离（Semantic Graph / per-claim AND–OR DAG / backlog DAG / events.jsonl）以及「不新增持久角色、不新增 lifecycle stage」的克制是正确的。

---

## 二、事实核查：六处需要修正

### A. `completion_gate` 的取值是 `none / metric / certified`，不是 `full_paper`

```python
# core/vertical_contract.py
_COMPLETION_GATES = frozenset({"none", "metric", "certified"})
```

计划 §三.7（L462）与 §五.3（L756）两处写成 `full_paper`。

**命名不是重点，重点是冲突 7 的论证方向错了。** 计划说「Argus 把来源按弱到强线性排序，数学放不进这条线」——前提描述对，结论也对，**理由不成立**：

那条 rank 阶梯在生产里从不拒绝任何东西。唯一生产调用点 `life/supervisor/_lifecycle.py:197` 把 source 硬编码成 rank 3（`SOURCE_INDEPENDENT_CERTIFICATION`），且只在 `gate == "certified"` **且** `paper/main.pdf` 存在时进入。反过来，`gate == "none"` 的 math 走的是 `life/supervisor/_planning_cycle_helpers.py:125-165` 的 `_staged_goal_completion_issue`，那里要求一份 fingerprint 绑定的 Reviewer 终局阶段认证。

**结论**：「不要给 math 加 rank 2.5」是对的，但真正理由是**那条 rank 不是当前的完成权威，改它没有任何效果**。数学的 trust contract 该挂在 `stage_completion_issues` + `_staged_goal_completion_issue`。计划 §五.3 的 `vertical_completion_evaluator` 若挂在 rank 层，会做出一个没有生产调用者的钩子。

### B. PR2 的前提不成立 —— per-mission 动态上下文钩子**已经存在**

计划 §五.1 称「没有每个 mission 动态生成 structured context 的接口」。实际上：

```python
# core/vertical_contract.py:55
mission_prelude: Callable[[str, Path, Path], str] | None = None
```

provider 侧叫 `prepare_mission(stage, project_root, state_root) -> str`，调用点 `life/supervisor/_mission_execution_runtime.py:100`，返回块被前置到 mission prelude。`verticals/kernel_engineering/stages.py:82` 是现成参考实现，**零 core 改动**。

它缺的只有三样：

1. 只拿到 `stage`，拿不到 `BacklogItem` → 做不到 per-claim target-specific
2. 只到 Engineer 的 mission prelude，不到 Planner / Reviewer
3. 返回 `str` 而非结构化 fragment

**PR2 因此从「跨 6 个文件新增 core seam」缩小为「给一个已有钩子加参数 + 决定是否扩到另外两个角色」。这是本次核查性价比最高的修正。**

附带说明：计划担心的 prefix caching 破坏问题已被现有机制处理——`mission.json` 本就是 per-mission 写的，静态 `role_banner` 不受影响。且 `life/context_packet.py:42` 已把 `content_hash` 从模型可见字段隐藏，说明「哪些进 prompt、哪些只做去重」这条边界已有人想过。

### C. PR5 的 `vertical_payload` 也有前身，且已跑通

`ReviewDecision` 已有 `research_result: dict[str, Any] | None`（`core/models.py:204`），由 `reviewer/_parsing.py:354` 从 Reviewer 输出的 `RESEARCH_RESULT` 命名块解析，经 `core/research_contract.py:normalize_research_result` 归一化，被 `manager/stage_decider.py:313` 与 `core/planner_verdict.py:114` 消费。

即「**Reviewer 输出结构化 payload → harness 归一化 → 顶层 status 仍是唯一控制权威**」这套机制**已存在、有测试、math 已在用**。PR5 要做的是把 hardcoded-to-research-schema 的通道泛化成 per-vertical，不是从零发明。

**坑**：`to_event_payload()` 显式剔除了一批字段，`tests/core/test_review_event_payload.py:32` 与 `tests/test_reviewer_completion_contract.py:36` 都断言 `failure_layer` 等**不在** payload 里。新 math payload 要上事件流须显式处理，否则静默丢失。

### D. PR4 的「复用 external-work」需要改写

`.argus_external_work` 是**只读观测协议**。`argus_skill/` 里没有任何代码写它——`EXTERNAL_WORK_REGISTRY` 的唯一使用是 `scan_external_work` 的读取（`engineer/external_work.py:236`）。记录由 agent 自己手写，Argus 只轮询心跳。

真正的进程 supervisor 在**另一处**：`tools/subagent/_registry.py`，有 `_launch_durable_command`（:96）、PID 跟踪（`_is_pid_alive`:196）、`reconcile_terminal_task`（:209）、`.argus_subagents/` 注册表。

**PR4 的 `submit(job) -> JobRef` 没有现成实现可复用。** 应改写为：「复用 `tools/subagent` 的 launch + reconcile 骨架，复用 `engineer/external_work.py` 的 liveness 状态语义（`running_healthy / needs_attention / stalled / terminal`）」。

**PR4 还漏了一个 core seam**：计划 §五 称「三个 core seam 不可避免」，但 §五.3 末尾自己又提了 `reconcile_vertical_external_work(...)`——那是第四个，且最难，因为要在 Planner cycle / Engineer context assembly / Reviewer invocation **三个不同安全边界**上插入。

### E. SQLite 会是全仓库首例

`argus_skill/` 只有两处外围用 `sqlite3`（`providers/copilot_usage.py`、`agent_cli/_opencode_recovery.py`）。**所有项目状态都是 JSON/JSONL + 文件锁**（`core/file_lock.py:16 exclusive_file_lock`、`core/workspace_lease.py`）。`verticals/research/literature_ledger.py` 是标准范式：JSON 文件 + validator + CLI + 投影渲染器。

既然 PR1 自己要求「event replay 能重建相同 state」，而单项目 claim 规模是百量级——**第一版用 JSONL + 内存投影**更贴合仓库、更易 diff 审计，并直接消除 PR1 自己点出的「crash 时 JSONL 与 SQLite 不可恢复分叉」风险。SQLite 留到能证明查询是瓶颈之后。

### F. PR8 的前提「靠 quarantine 纠错」不成立

quarantine 是**项目级**的（`life/project_lifecycle.py:43 QUARANTINED`，budget-fraction 规则 :156-172），不是 skill 级。skill 准入实际走 `manager/skill_review.py:classify_skill_placement`——一个 LLM 放置分类器，无 shadow / canary / promotion 状态机。

两面结论：PR8 比设想更 green-field（无现成生命周期可挂），但它要解决的问题也更真实（现在确实没有任何机制阻止一次偶然成功写进 active pool）。

---

## 三、两处新发现（对首批工作有利）

### 新发现 1：statement fidelity 的机械强制**已经在 harness 里**

`tools/lean_check.py`（753 行）远比计划设想的完整：

```python
def prepare_canonical_lean_artifacts(source, artifact_dir, statement_fidelity) -> tuple[Path, Path]:
    ...
    if source_path == fidelity_source:
        raise ValueError("Lean source and statement fidelity must be distinct")
```

它**要求**一份独立的 statement fidelity 文档，并显式拒绝它与 Lean 源同文件。此外还有 `find_proof_holes`（:293，检测 `sorry`/`admit` 类洞）、`_AXIOM_AUDIT_MARKER` + `lean_axiom_audit.lean` 的公理审计、`audit_lean_tools` 的工具链探测、`_atomic_artifact_write` + `_artifact_directory_lock` 的并发安全写。

**principles 文档最核心的约束（statement fidelity ⊥ proof validity）已经实现了。`verticals/math/` 对 `lean_check` 零引用。**

### 新发现 2：math 的机械门只有一条 file-existence 测试

```python
_PIPELINE_CHECK = ("Pipeline state present", "test -f research/PIPELINE_STATE.json")
STAGE_CHECKS = {stage: [_PIPELINE_CHECK] for stage in STAGE_ORDER}
```

三个 stage 共用同一条检查。加上 `completion_gate = "none"`，math vertical 当前的全部机械保证就是「有没有那个 JSON 文件」。`stage_completion_issues` 里的 proof-graph 检查只在 `develop/certify` profile 且 targeted 模式下触发。

**这两条合起来意味着：接线 `lean_check` 不是「加一个 Lean 检查器」，而是「把一个已建好的、强制 statement fidelity 的验证器，连到一个机械门几乎为空的 vertical 上」。首批工作的杠杆比计划估计的大。**

---

## 四、判断正确、应当保留的

- **冲突 2（不能复用 backlog DAG 做 proof DAG）** —— 理由比计划写的更硬。`life/memory.py:725-729` 明确：一个 item 只有在**每个** dep 都到达终态 `done` 后才可认领。纯 AND 语义，**OR 路线在这个结构里字面上无法表达**，不是「语义不合适」而是「表达不出来」。
- **冲突 3（LifeSupervisor 同步）** —— `tick()` docstring 原文即 "Process at most one backlog item"（`life/supervisor/_core.py:907`）。
- **冲突 5（MathState 是 harness-owned runtime state，不是 Engineer 的文档 deliverable）** —— 全篇最重要的判断，且与现有测试一致：`test_math_engineer_uses_one_checkpoint_without_process_artifacts`、`test_math_checklist_is_small_and_judges_results_not_files`（后者专门断言 `solve.gap-reduced` 必须由「哪个命题改变了状态」满足，而非由文件存在满足）。
- **冲突 8（append-only 与可撤销性分离）** —— 对照表正确。
- **冲突 9（live search 不覆盖 math）** —— 属实，且比描述更窄，见下。

### 冲突 9 的精确形态

```python
# engineer/round_config.py:96
live_search_stages: frozenset[str] = frozenset({"research"})
```

`_engineer_live_search`（:99）用 `current_stage(workdir)` 匹配，fail-closed 到 False。该字段**全仓库无任何覆盖点**——只有定义处与 `runner.py:318` 的读取。math 的 stage 是 `scope/solve/review`，所以 **math Engineer 永远拿不到 live search**，不是「很可能不会」。

**Planner 侧要小心**：`planner/planner.py:226` 的 `RunnerOptions` 是 `sandbox_mode="read-only"` + `dangerous_yolo=False` + `full_auto=False`，注释明确说这是 role-owned boundary，防止上游 yolo 设置给 Planner 授予 shell/网络/写权限。**给 Planner 开 search 不得顺手放宽这条边界。** Reviewer 已开（`reviewer/_core.py:205`）。

---

## 五、可行性分析与调整建议

### 5.1 按 PR 的成本与风险

| PR | core 改动 | 成本 | 风险 | 备注 |
|---|---|---|---|---|
| PR0 不变量测试 | 无 | 低 | **中** | 须先修正 A/B/C/D，否则把错误认知锁进测试 |
| PR1 state kernel | 无 | 中 | 中 | 纯新增包；风险在 schema 过设计 |
| PR2 ContextBundle | **1 处**（原估 6） | **低**（因 B 下调） | 低 | 扩 `mission_prelude` 签名 |
| PR-A live search | 1 处 | **极低** | 低 | ~10 行 + 测试，**独立提前** |
| PR-B lean 接线 | **0 处** | **低** | 低 | **新增，首个异质证据通道** |
| PR3 proof obligations | 无 | 中高 | 中 | 纯 `research_math/` 内部 |
| PR4 async verification | **4 处**（原估 1） | **高**（因 D 上调） | **高** | 全计划最大风险点 |
| PR5 Reviewer payload | 1–2 处 | **中**（因 C 下调） | 中 | completion hook 须挂对地方（见 A） |
| PR6 literature + citation | 无 | 中 | 低 | 有 `literature_ledger.py` 可抄结构 |
| PR7 portfolio | 未知 | 高 | **高** | 与 goal 判据冲突，需先裁决 |
| PR8 distillation | 无 | 中 | 低 | 比设想更 green-field（见 F） |

**PR4 为何是最大风险**，三因叠加：(i) 无现成 submit，须在 `tools/subagent` 上新建；(ii) Lean 工具链环境依赖是真实运维成本；(iii) reconcile 横跨三个安全边界，是第四个未列入的 core seam。

### 5.2 建议顺序：先放两个当天能看到行为变化的修复

```
PR0'  修正后的 invariant 测试
PR-A  live search 修复                    ← 新增，~10 行，立刻可验
PR-B  把 tools/lean_check.py 接进 math    ← 新增，零 core，首条异质证据通道
PR1   砍瘦的 state kernel
PR2'  扩 mission_prelude 签名
PR3 → PR5' → PR6 → PR4 → (PR7/PR8 待裁决)
```

理由：把两个当天可完成、当天可见行为变化的修复放最前，避免「先建三层抽象再看到第一个真实效果」。PR-B 尤其关键——它是整个计划里成本最低、离「异质 verification」核心原则最近的一步，且不需要 state kernel、不需要 async、不动 core。

### 5.3 PR1 的 schema 砍到三个实体

计划列了 8 个实体 + 5 组状态枚举。第一版只做 `ContextVersion` / `ClaimVersion` / `EvidenceRecord` + `ProofRoute`。

**`MechanismVersion` 先不做** —— 它是全部实体里最缺运行数据支撑的一个，而 goal 文档自己在「哪些经验很可能可以复用」里就承认「agent 是否真的稳定地产生 mechanisms」要跑过真实问题才知道。先做它就是在无数据的情况下固化 schema。

**不可砍的一条**：`conditional_kernel` 与 `closed_kernel` 必须是两个状态。这条与 `ExternalAssumption` 是 statement-fidelity 约束的直接机械化，是真正 math-specific 的部分。

### 5.4 裁决 PR7 与 goal 判据的冲突

**建议按 goal 文档自己的判据否决 PR7 当前形态。** 改成「只读 explorer」：portfolio worker 以 external verifier 身份存在，隔离 workspace、只读 canonical state、只提交 candidate，由主 Engineer 在下一轮消费。这样它是 evidence producer 而非 orchestrator，符合「specialists 产生 artifacts，四角色保留控制权」这条已写对的原则。

真正的并行 approach portfolio 应明确划到「转移到专用 Research Math OS」那一侧。

### 5.5 给 deep-think lane 留位置

principles 文档提出了它，plan 无落点。Argus 现有结构里最接近的实现是**一个 `bounded=False`、`iterate=True`、`iteration_max_cycles` 拉高、Reviewer 只在 checkpoint 介入的长 mission**。不需要新机制，但需要在 math policy 里显式声明什么问题走这条 lane。否则所有数学工作都会被切成 bounded mission，恰好丢掉 unit-distance 那类结果的产生条件。

---

## 六、三点补充的处理

### 6.1 Citation verification 作为单独一类 —— 同意，但要挂对地方

citation 检查有三个**不同**的失败模式，必须分开：

| 层 | 检查什么 | 成本 | 现状 |
|---|---|---|---|
| 1 存在性 | 文献/DOI 是否存在 | 低（机械） | `integrity_check.check_citations`（:39）已做 tex↔bib 一半 |
| 2 归属性 | 被引文献是否**真的**含所声称的命题 | 中（需检索+阅读） | **无** |
| 3 适用性 | 被引定理的**假设**在本语境是否成立 | 高（需数学判断） | **无** |

第 3 类最要命，且**在结构上就是 statement fidelity 问题**：一个引用正确、但假设未经核实就套用的定理，正是一个隐藏的 `ExternalAssumption`。

**设计建议：citation verifier 不应是 Lean/code/literature 之外的第四个兄弟，它应该产出 `ExternalAssumption` 记录。** 被引定理在其假设被 discharge 之前即为一条 external assumption，claim 停留在 `conditional_kernel`。这样它与 conditional/closed kernel 主线统一，而不是并列加机制。

三层应分别落为 `verifiers/citation.py` 的三个独立 check，各自产出独立 `EvidenceRecord`，因为它们的**可信度等级完全不同**：第 1 层是机械事实，第 3 层是 LLM 判断，混在一个 verdict 里就退化成 principles 文档警告的「相似 judges 的假共识」。

### 6.2 anydoc —— 建议分流，不要全量替换

**现状核实**：Argus **没有** PDF→结构化文本的转换层。`literature_ledger.py` 只管 JSON ledger + TSV matrix + URL 有效性（`_valid_http_url`:147），不管原文获取。所以「Argus 内置机制够不够好」的答案是：**这一层根本不存在**。

**但对数学有个具体反对意见**：PDF→markdown 会**损坏 LaTeX 保真度**，而数学的 statement fidelity 恰恰依赖公式的精确性。一个被转换器吃掉下标的不等式，正是第 6.1 节第 2/3 层检查最需要精确的地方。

**建议分流**：

- arXiv / 有 LaTeX 源的 → **直接取 e-print 源码**，严格优于任何 PDF 转换器
- 仅有 PDF 的（老论文、期刊版、书籍章节）→ 才走 anydoc 一类转换器

anydoc 是 Firecrawl 的外部服务依赖，应做成 `verifiers/literature.py` 后面的**可选 adapter，默认关闭，不进 core**，并在 `EvidenceRecord` 里记录来源是 `tex_source` 还是 `pdf_conversion`——因为后者的保真度天然更低，下游判断应当知道这件事。

### 6.3 Eval 与污染问题 —— 建议放弃「造干净题库」，改用三层

guard-search 是必要的，但它是**最弱的杠杆**：只堵检索通道，堵不住参数记忆。research-math 级别的题目只要发表过，大概率已在权重里。

#### 第一层（最重要）：把主实验设计成配对消融，而非绝对能力测试

goal 文档自己的研究问题是「显式 obligations + evidence-triggered verification + 异步 formal feedback **能否显著提高**正确性/效率/恢复能力」——这是个 **delta** 问题。**污染对 A/B 两臂是同等的。**

所以主实验用同一批题、同一 backbone、只切换 math kernel 开关。污染抬高两臂绝对分，delta 依然有意义。

**这一条最重要，因为它意味着 eval 的可信度不依赖题库的干净程度。**

#### 第二层：过程指标 —— 污染伪造不了，且同时是污染探针

即使模型记得答案，它伪造不了：

- **obligation discovery rate** —— 是否主动发现真实证明缺口（对照人工标注 gap 清单）
- **false-certification rate** —— 是否认证了后来被 Lean 或反例推翻的 claim
- **external assumption 记录率** —— 有多少外部依赖被显式登记为带真实出处的 `ExternalAssumption`

  > **订正（PR1 实现期）**：此处原写的是「conditional_kernel → closed_kernel 转化率」，该指标出生即死，应弃用。因为 discharge 只接受 mechanical 证据（放宽会重演 §6.1 警告的假共识），关闭一个内核需要形式化**每一条**被引定理，这个比率在真实研究项目上会常年读 0——消融两臂都是 0，不具区分度。记录率则由 `open_assumptions()` 直接可答，且正是「背答案」的 run 伪造不了的量：它的特征签名恰恰是零 obligation、零 conditional_kernel、直接给出最终 statement。
- **recovery latency** —— 从 Lean failure 到 replan 到新路线的轮数
- **citation attribution accuracy** —— 见 6.1

一个「背出答案」的 run 在这些指标上有非常特征化的签名：**零 obligation、零 conditional_kernel、直接给出最终 statement**。所以这些指标既是能力度量，**也是污染探针**。

#### 第三层：题目构造，按性价比排序

- **(a) 扰动变体（最高性价比）**：拿已发表定理，改一个常数 / 维数 / 去掉一条假设。记忆的证明不再适用，但技术适用。且污染变成**机器可检测**——agent 若输出原定理的常数，一眼看出是背书失败。
- **(b) 引理挖空**：拿真实证明删掉一个引理。有 ground truth，且直接测量最想测的量：系统**是否先注意到缺口**再去补。
- **(c) 时间切片**：用训练截止之后发表的结果。唯一能真正排除记忆的方法，但供给有限。可机械强制：给 literature verifier 一个 `max_publication_date`，**拒绝**任何晚于题目日期的证据。这在 harness 里可强制执行，而「模型别用记忆」不可执行。

#### 关于 guard-search 本身：建议做成 flag 而非 block

正确形态不是黑名单，而是 **evidence provenance gate**：每条检索结果作为 `EvidenceRecord` 落盘（URL/DOI + 抓取时间 + 与 target statement 的相似度）。若某结果包含目标命题本身或其证明，标记 `solution_leak`，**flag 而不 block**。

flag 优于 block 的三个理由：

1. block 本身泄露信息（「这题被保护了」= 这是道有名的题）
2. block 不可审计，flag 事后可复查
3. flag 直接复用 PR6 要建的 ledger 机械，不是新机制

---

## 七、最大风险

**MVP 五件事里有四件是状态基础设施，只有 async Lean 直接产出数学证据。** 若按计划顺序先建完 kernel 再接 verifier，中间会有很长一段时间无法用「数学问题解得更好了吗」做消融——而 goal 文档自己提出的研究问题恰恰需要这个消融。

**缓解**：每个 PR 绑定一个可跑的数学问题回归，哪怕很小。PR-A 与 PR-B 之所以该提前，正是因为它们能在第一周就给出这条基线。

---

## 附：本评审的核实方法

所有关于 Argus 现状的论断均来自直接 grep / 读源码，未使用 subagent 转述。关键引用点：

- `core/vertical_contract.py` — `_COMPLETION_GATES`、`mission_prelude`
- `core/project_api.py:47-65` — source rank 与 gate rank 表
- `core/models.py:173-204` — `ReviewDecision.research_result`
- `engineer/round_config.py:96` — `live_search_stages`
- `engineer/external_work.py:17-56, 227-258` — 只读观测协议
- `tools/subagent/_registry.py:96, 130, 196, 209` — 真正的 process supervisor
- `tools/lean_check.py:518-580, 741-753` — statement fidelity 强制与 API 面
- `life/memory.py:676-767` — `BacklogItem.deps` 的 AND 语义
- `life/supervisor/_core.py:907-912` — `tick()` 单 item 语义
- `life/supervisor/_mission_execution_runtime.py:75-112` — `prepare_mission` 调用点
- `verticals/math/stages.py:13-60` — `STAGE_CHECKS` 与 `completion_gate`
- `verticals/research/literature_ledger.py`、`integrity_check.py:39` — 现有 literature/citation 机制

论断随代码演进会失效；引用行号以评审日期的 `main` 为准。
