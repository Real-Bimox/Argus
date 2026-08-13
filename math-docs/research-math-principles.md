## 核心结论

1. 最强数学研究系统应当把数学研究显式建模成一个持续演化的、带证据的 Research State，而不是一段越来越长的 conversation。
Research State 至少应该同时保存：问题及定义的精确版本、literature map、候选 conjectures、proof obligation DAG、并行 approach families、实验结果、counterexamples、已证明/未证明 lemmas、失败路线、引用 provenance、Lean artifacts，以及每个 claim 当前接受过哪些类型的 verification。
2. Verification 必须异构，而不能只是更多 LLM critic。采用至少下面五条相对独立的 evidence channel：LLM referee ensemble → computational falsification/code → Lean kernel → (literature/attribution audit → human/domain-expert audit) optional。
3. self-evolving让系统的外部研究能力不断复利，每次项目都应该留下可复用的 theorem/lemma、proof pattern、failed approach、counterexample pattern、retrieval path、formalization bridge、verification failure、tool recipe 和 cost/success statistics。

## **数学研究系统的核心原则**

| **Principle** | **类型** | **为什么重要** | **代表性证据** |
| --- | --- | --- | --- |
| **Breadth before commitment** | 通用 reasoning | 早期搜索空间应该保持高 entropy；不要因第一条漂亮路线过早塌缩。 | Momus 并行 solvers；OpenAI CDC prompt 明确隐藏 favored route 并维护 approach families；Anthropic 先后搜索数百 ideas。 |
| **Adaptive breadth → depth allocation** | 通用 reasoning | 所有路线同预算浪费严重。应先广搜，再把更多 compute 给经过初步 evidence 的路线，同时保留 long-shot。 | Aletheia inference scaling、AlphaProof Nexus evolutionary selection、Momus staged search。 |
| **Separate generation from criticism** | 通用 reasoning | 让模型重新处于“无义务维护原答案”的 context 中，更容易发现原 reasoning 的漏洞。 | Aletheia Generator/Verifier/Reviser；Rethlas generator/verifier；ProofCouncil author/critic。 |
| **Adversarial search, not polite review** | 通用，但数学中尤其强 | critic 的任务不是帮助原 proof 自洽，而是主动破坏它。 | Momus prove/disprove agents、Anthropic counterexample search、CDC adversarial audit。 |
| **Externalize state** | 通用 reasoning | 长期任务不能靠 LLM context 隐式记忆；需要显式 graph、ledger、files、version control。 | AI co-mathematician workspace、LEAP DAG、MMAT Execution Graph、AutoformBot repository。 |
| **Monotone progress preservation** | 通用 reasoning | 一个后续失败 agent 不应摧毁已经验证的成果。 | LEAP 只提交被 compiler 接受的 dependency update；ProofCouncil 保存 earlier verified answer；Git/version-control based systems保留历史。 |
| **Failure is data** | 通用 reasoning | dead end 不应该从 context 中删除，否则下一轮会重复踩坑。 | AI co-mathematician 明确把失败探索作为 permanent first-class outcomes；MMAT 跨 session 保存 negative constraints。 |
| **Tools are part of cognition, not post-processing** | 通用 reasoning | agent 应在推理过程中主动通过外部环境获得新证据，而非最后才验证。 | Aletheia web search、Anthropic shell/Python、AI co-mathematician PySAT、ProofCouncil CAS。 |
| **Use explicit uncertainty and abstention** | 通用 reasoning | 强行回答会把低置信路径包装成 proof。 | Aletheia verifier 可导致 no-answer；AI co-mathematician 把 uncertainty 作为被管理的系统状态。 |
| **Human steering at high-value breakpoints** | 通用 reasoning | 人类最值得投入的是 problem formulation、deadlock breaking、significance 和审计，而非微观补每一步 algebra。 | AI co-mathematician、MMAT、OpenAI First Proof 均显式采用 steering。 |
| **Decompose proof into explicit obligations** | **Math-specific** | 数学 proof 的 dependency structure 可以显式化成 theorem/lemma obligations，并获得机械意义。 | LEAP AND–OR DAG 是最明确实例。 |
| **Prove and disprove symmetrically** | **Math-specific** | 对真正 open conjecture，系统不能先假定命题为真；counterexample 常比 proof 更容易，同时可以揭露错误 formulation。 | Momus 的 prove/disprove subagents；AlphaProof 工具本身可以返回 disproof。 |
| **Theorem-level literature retrieval** | **Math-specific** | 关键不是找“相关文献”，而是找到准确 theorem statement、assumptions、number、dependencies。 | Rethlas/Matlas、AI co-mathematician exact theorem retrieval、Aletheia citation experiments。 |
| **Statement fidelity before proof validity** | **Math-specific** | Lean 可以正确证明错误 formalization。原问题、formal statement 和证明对象必须单独验证。 | AlphaProof Nexus 在 Erdős experiments 中主动发现并修正 misformalizations，并给 OEIS formalization 增加 test lemmas。 |
| **Informal ↔ formal interleaving** | **Math-specific** | Natural language 适合 strategy / analogy，Lean 适合局部严格性；二者不应互相替代。 | LEAP、Rethlas–Archon、OpenAI Astra 均体现这一 separation。 |
| **Exact / symbolic computation as falsifier** | **Math-specific** | 数值实验不能证明一般 theorem，但对寻找 counterexample、结构、parameter schedule 极强。 | Claude 的大量 numerical checks；AI co-mathematician 的 SAT reduction；AlphaProof Nexus 同时搜索 algorithm parameter 和 proof。 |
| **Correctness ≠ novelty ≠ significance** | **Math-specific research** | 一个真正 research-level system 必须分别回答这三个问题。 | Aletheia Erdős audit、First Proof citation problems、Anthropic 的 prior-art search。 |
| **Native mathematical artifacts** | **Math-specific** | 输出单位应是 definitions、conjectures、lemmas、proofs、counterexamples、Lean files、citation records，而不是 chat messages。 | AI co-mathematician living paper、LEAP proof graph、AutoformBot Atlas。 |

**parallelism、critic、memory、tools、adaptive compute 本身都不是数学特有的**；真正 math-specific 的，是这些机制操作的对象具有非常特殊的结构——definitions、quantifiers、proof dependencies、counterexamples、formal kernels、theorem libraries 和 mathematical novelty。

也因此，普通 general-purpose research agent 的“事实核查”不能直接替代 mathematics verification。例如，一个 web research agent 可以确认“某篇论文说过 X”；数学 agent 还必须确认“X 的 hypotheses 是否与当前 lemma 完全吻合”“使用 X 是否产生 circularity”“formalization 是否保留了原定义”“引用的 theorem 是否足够强但又没有把待证命题偷偷装进 assumption”。Aletheia 和 First Proof 的 citation failure，以及 AlphaProof Nexus 的 misformalization experience，都说明这些不是边缘工程问题，而是核心 reasoning problem。

## **当前系统暴露出的关键缺口**

### **LLM-verifier 会形成伪共识**

最危险的 misconception 是认为“再加三个 reviewer agents 就可靠了”。AI co-mathematician 直接报告了一种 **reviewer-pleasing bias / false consensus**：prover 不一定真正修复了 argument，而可能持续改写到 reviewer 再也检测不到原漏洞。也就是说，prover 和 verifier 如果共享同一模型家族、相似 training data、相似 context 和同一种 proof representation，其 errors 并不独立。citeturn14view1

因此：

$$\text{10 个相似 LLM judges} \neq \text{10 个独立 verifier}.$$

真正需要的是 **epistemically heterogeneous verification**：语言模型找概念性漏洞，code 找 finite counterexample，SMT/SAT/CAS 检查可计算子命题，Lean 检查形式逻辑，literature agent 检查先验知识和 novelty，人类专家评估 statement fidelity 与 significance。

### **Formal proof 也不能独立解决 research correctness**

Lean 的巨大价值不可替代，但也必须准确理解它验证的是什么：**kernel 验证的是 formal theorem statement 下的 formal proof。** AlphaProof Nexus 的作者发现 formalized Erdős statements 中存在“density”解释等问题，并在修正 formalization 后重新运行证明；在 OEIS autoformalization 中，他们特意要求先证明前几个 sequence terms 的 test lemmas，作为 specification sanity check。citeturn16view0

因此需要两个不同的 gate：

$$\text{Statement Fidelity}
\quad\text{和}\quad
\text{Proof Validity}.$$

Formalization agent 本身不能给自己颁发 Statement Fidelity 证书。

### **Literature search 仍是 research bottleneck**

Aletheia 的结果非常说明问题：加入 search 后，完全虚构 paper title/author 的低级 hallucination 显著减少，但错误变成了更隐蔽的类型——**论文确实存在，可所声称的 theorem 并不在里面，或者 theorem 的 assumptions 被错误引用。** First Proof Second Batch 同样发现 citation/attribution failure 即使在带 literature harness 的系统中仍然常见。citeturn17search0turn2view0

所以 deep research module 不能只做 conventional RAG。数学 retrieval 的最小数据单元最好是：

> `Theorem / Lemma / Definition + exact assumptions + exact conclusion + source + theorem number + dependency context + proof technique + citation provenance`
> 

而不是 generic 1,000-token text chunks。

### **过度 orchestration 也可能伤害 discovery**

OpenAI 的 unit-distance result 是很好的警告。该结果据 OpenAI 和随后的人类 companion paper 所述，来自 general-purpose reasoning model 的一次 autonomous mathematical effort，而不是一个专门针对该问题构造的复杂 multi-agent harness；它将 algebraic-number-theoretic ideas 带入了一个看似 elementary 的 discrete-geometry 问题。citeturn19search5turn20search1

所以最强系统不应该只有“拆任务 → subagents → 汇总”的模式。某些真正深的 insight 恰恰需要一个 agent 长时间保持完整 global representation。

我会因此保留两类互补 reasoning lane：

**Monolithic Deep Think lane**：允许一个最强模型持续、自由地研究整个问题。

**Structured Research Swarm lane**：进行分工、breadth search、proof/disproof、literature、code、formalization 和 audit。

二者互相交换 artifacts，但不强制共享完整 chain/context。

### **当前“self-evolving”仍远未完成**

当前系统已经出现了几个局部组件：AlphaProof Nexus 的 evolutionary proof population、AI co-mathematician 的失败历史、MMAT 的 continual negative memory、AutoformBot 的可累积 formal repository。citeturn16view0turn15view0turn21view2turn18search2

但距离真正的“研究经验复利”还有差距。现在多数 agent 在开始一个新数学问题时，仍然没有一个成熟机制自动回答：

> “过去五万个 research trajectories 中，和这个 problem fingerprint 相似的问题，哪些 approach families 成功率最高？哪些 theorem retrieval paths 最有效？哪些 verifier 曾经漏掉过同类漏洞？这个新 lemma 是否已经在过去项目中形式化？哪种 decomposition 曾经导致 theorem-strength subgoal 循环？”
> 

这正是下一阶段最值得做的 architecture。

---

参考：

## **代表性系统与关键创新**

下面先把用户指定的工作，以及我认为必须同时纳入的 2026 年补充工作，放在同一张系统图谱中。这里所谓“最重要创新”，指的不是单纯 benchmark 数字，而是对下一代 research system architecture 最可迁移的贡献。

系统 / 工作	最重要的系统创新	Verification / Memory 特征
First Proof Second Batch — ProofCouncil / IMProofBench	First Proof 第二批实验中三个公开 academic harness 之一。ProofCouncil 将 research workflow 写成可组合 workflow，核心是长程 Author ↔ Critic 迭代，同时可以调用不同 frontier models；还有专门 Compute Worker，集成 SageMath、GAP、Singular、PARI/GP，并在继续探索退化时保留此前最好的 verified/compiling answer。
LLM critic + CAS/code；显式 budget/round/deadline；“best-so-far 不回退”是非常值得保留的 monotone state 原则。
First Proof Second Batch — UCLA Moonshot Harness	把 research workflow 分成 Deep Literature Search → Advisor–Solver → Verifier–Refiner，尤其值得注意的是 literature research 不再只是工具调用，而成为 proof search 前的一等阶段。
Literature grounding + solver/advisor role separation + verification/refinement。
First Proof Second Batch — Princeton Momus	目前最值得研究的 academic harness 之一：parallel solvers、BSDetector、grader、共享 research notebook；若整体卡住，则自动提取 load-bearing conjectures，再派生专门 subagents 做 prove / disprove；支持 arXiv search、paper triage 和 PDF distillation；candidate solution 还会经多个 graders 与 aggregator 再验。
强调 independent breadth、反证、persistent notebook 和 ensemble verification，而不只是 self-refinement。
Aletheia	Google DeepMind 将 research math agent 明确拆成 Generator → Verifier → Reviser，三者循环直至 verifier 接受或预算耗尽；核心还包括 Deep Think inference scaling，以及 intensive Google Search/web tool use。它是自然语言 research agent，而不是先形式化问题。
verifier 与 generator 分离；允许 abstain；搜索 literature。Aletheia 在 FirstProof best-of-2 中按团队组织的专家评审得到 6/10 majority-correct，其中 P8 有分歧。
AI co-mathematician	我认为它在“research UX / OS architecture”上最先进：不是一次 autonomous run，而是一个 asynchronous, stateful mathematical workspace。Project Coordinator 管理多个并行 workstreams；living working paper 保存研究状态；用户可以随时 steer；失败 hypotheses、uncertainty、claim provenance 都长期存在。
reviewer loops、numerical simulations、citation checking、version history、failed-exploration memory；FrontierMath Tier 4 的 blind evaluation 为 23/48，即 48%。
LEAP	形式数学中非常关键的一步：把 proof planning 表示为 AND–OR DAG。先 direct formalization；失败后生成 informal blueprint，再生成带 auxiliary lemmas 的 Lean sketch；只有 Lean 接受 dependency structure 后才写入 graph，然后递归证明 children。
Lean compiler + LLM planning reviewer；lemma memoization、DAG acyclicity、compiler-feedback revision。Lean-IMO-Bench 上将 general-purpose LLM 的 formal solve rate 从不足 10% 推到 70%，并形式化全部 2025 Putnam 题。
AlphaProof Nexus	把 Lean proof search 与 evolutionary population search 真正结合。Basic agent 本质上是 LLM ↔ Lean 的 Ralph loop；full system 加入 AlphaProof tool、population DB、pairwise rater、Elo、P-UCB sampling，使 proof sketches 在 population 中不断繁衍和改进。
Lean 是硬 verifier；AlphaProof 可返回 proof / disproof / failure；最终 validator 检查 statement 未被危险修改。full agent 在 353 个形式化 Erdős 问题中证明 9 个，在 492 个 OEIS conjectures 中证明 44 个。
Rethlas + Archon	FrenzyMath 的重要贡献是把研究 agent 划分为 informal discovery 和 formal verification 两个世界。Rethlas 利用数学 reasoning primitives 和 theorem-retrieval engine Matlas 寻找 proof；Archon 再借助 LeanSearch 将其变成完整 Lean 4 project，并可自行补上 informal proof 中非平凡的 gap。
Rethlas 自身又有 generator/verifier loop；Archon 提供独立 Lean verification。论文报告端到端解决并 formalize 一个 commutative algebra open problem。
AutoformBot / Atlas	formalization 从“一个 theorem”扩展到“一个数学 corpus”。AutoformBot 同时调度大量 LLM agents，用 dependency-aware scheduling + version control + isolated work + formal verification 协作，把 26 本公开教材转成 Atlas。
>45,000 Lean declarations、约 500k LOC；核心启示是 mathematical agents 也需要成熟的软件工程基础设施，而不是靠共享 chat context。
OpenAI First Proof	OpenAI 的第一批 First Proof run 不是纯 autonomous benchmark：模型可长时间思考，人会把此前 fruitful strategy 重新交给模型，也会根据专家反馈要求展开 proof，并让另一个 ChatGPT 实例参与 verification / formatting。OpenAI 后来也明确撤回了最初对 Problem 2 的乐观判断。
很有价值的 lesson 是 human-mediated trajectory memory + model-model review；但由于人工选择与反馈较多，它更像真实协作 workflow，而非严格 autonomous evaluation。
OpenAI Astra / Ten Advances	2026 年 8 月公开的结果是当前最强烈的“frontier discovery → manuscript → formal certificate”信号之一：OpenAI 称十项数学/TCS结果均由内部下一代模型 Astra 获得；之后人类和同一模型整理成 manuscripts，最后模型再把每个 argument formalize 为 Lean certificate。
自然语言发现和形式化认证分阶段，而不是要求搜索全过程都在 Lean 中完成。官方称发现这十项结果的 token 量按 Sol API 价格折算约 $2,000。
OpenAI Unit Distance result	一个很重要的反例：并非所有突破都来自复杂 harness。OpenAI 报告 unit-distance conjecture 的反例来自一个 general-purpose reasoning model，而非 math-specific model，也没有针对该题搭建 strategy-search scaffold；随后 Alon、Bloom、Gowers 等数学家给出了 condensed human-verified exposition。
说明系统设计中应该保留一条 unconstrained long-context “deep thinker” lane，不能把所有思维都强制碎片化成 agents。
OpenAI Cycle Double Cover prompt	这是一个非常有信息量的系统 prompt：允许最多 64 concurrent agents，要求真正不同的 approach portfolio；早期不要告诉多数 agents 当前 favored approach；显式维护 approach-family registry；卡在 theorem-strength lemma 时冻结路线；保留多个 incompatible routes；root agent 持续 synthesize / challenge / redirect / relaunch。
prompt 还强制 adversarial audit、具体 lemma/construction/counterexample 输出，以及至少 8 小时持续搜索。与此同时它明确要求“假设 affirmative proof 存在”，这对通用 open-problem research 并不是一个安全的默认假设。
Anthropic Claude — Riemann zeta	截至本次检索时间，这是特别值得关注的最新案例。Anthropic 报告 unreleased Claude 在尝试 Riemann Hypothesis 时没有证明 RH，却意外把已知的“在 critical line 上的 zeros 最低比例”从 41.6% 提高到 67.2%。真正重要的系统信息是其搜索过程：约 31M output tokens、约 60 个 subagents、2,400 shell commands、数百 Python scripts、数千 numerical checks。
subagents 互相 referee、主动寻找 counterexamples、下载 54 篇 arXiv papers 做 novelty checking、从头独立重证，之后又产生 Lean formalization，并由 Anthropic 数学家和外部专家检查。
MMAT / MechMath Agent Team	2026 年 7 月非常值得纳入：把 harness 分成 Control / Execution / Augmentation 三个 plane。Control 用 Execution DAG + Task Ledger；Execution 用 isolated workspaces + file-based handoff；Augmentation 支持 human co-reasoning 和 stratified continual memory。
特别关键的是 continual memory：重复出现的 reasoning errors 被蒸馏成跨 session 的 negative constraints，dense domain facts 则进入 Knowledge Base。这是目前最接近“research agent self-evolving architecture”的公开设计之一。


First Proof Second Batch 本身也值得作为“system evaluation paper”单独看。它不是仅看 final answer，而是由 First Proof 组织者运行公开 harness，对结果进行接近期刊的 double-blind expert review，每题由多位独立 referee 检查。四个 configuration 中包括上面的三个 academic harness，以及一套 OpenAI ChatGPT 5.5 Pro one-shot configuration；10 道研究题中有 7 道至少有一个系统得到 passing assessment。但论文同时指出：模型更容易在已有 literature 提供结构时成功，对真正最困难的一步反而可能写得过于简略，而且 **citation / attribution failure 在加入 research harness 后仍然频繁存在**。citeturn2view0turn4view0

这一点与 Aletheia 的 700 Erdős problems 实验非常一致。Aletheia 的 informal verifier 从 700 个问题中筛出 212 个看似有希望的回答；后续数学家审查发现，许多回答虽然在某种 literal interpretation 下“数学上正确”，却没有回答 Erdős 真正意图的问题。最终只有少部分属于 meaningful resolution、independent rediscovery 或正确 literature identification。换言之，**proof correctness、problem interpretation、novelty detection 三者绝不能由同一个 verifier score 混成一个指标。** citeturn17search0

形式化方向则正在发生第二个相变：从 theorem-scale 走向 project-scale。除 AutoformBot 外，2026 年的 M2F 采用“statement compilation → proof repair”两阶段方法，在整个项目内先建立可编译的 declaration/dependency skeleton，再逐个消除 proof holes；论文报告约三周把 479 页 analysis/convex-analysis 材料转换为超过 153k 行 Lean。这与 AutoformBot 的结果共同说明，未来 research agent 可以逐渐拥有一个不断增长的、自己可检索的 formal mathematical world，而不必每个项目都从 Mathlib 的原始状态重新开始。citeturn18academia19turn18search2

另外两个 2026 年 7 月后的系统值得作为下一波方向看。OpenProver 使用 Planner–Worker–Verifier，并明确区分 compact whiteboard 与可无限增长的 repository；MECA 则不把目标限制为“证明已有 conjecture”，而是用 Explorer + Critic 围绕 mathematical mechanism 生成和修正新的 conjectures，再用独立 prove/refute attempts 检查其价值。这二者分别补上了 **长期 memory architecture** 与 **problem/conjecture formulation** 两个当前大多数 solver agent 缺失的环节。citeturn12academia1turn20academia39