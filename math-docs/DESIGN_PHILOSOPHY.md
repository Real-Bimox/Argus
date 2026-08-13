# Argus 核心设计理念

本文记录 Argus 为什么是现在这个形状：每一条架构决策对应哪个失效模式，哪些约束是不可
放宽的，以及在扩展系统时什么算越界。

它不描述 API，也不复述运行流程——那是 `docs/FEATURES.md` 的职责。它回答的是**"为什么"**，
用于在改动前判断一段新逻辑该不该存在、该放在哪一层。

> **权威层级。** 当本文与代码冲突时，以 `argus_skill/` 的实现和 `tests/` 的行为回归为准，
> 并在同一次改动里修正本文。`technical_report/` 是绑定特定版本的正式报告，其经验结论不
> 覆盖当前运行契约。本文引用符号名和模块路径，不依赖会漂移的行号。

---

## 1. 目标任务类：没有可信分数的工作

Argus 不是为"更难的分数"设计的，而是为**分数不存在**的场景设计的。

技术报告把目标任务类定义为 **dense-intelligence task**，需要同时满足三条
(`technical_report/sections/03_problem_formulation.tex`)：

| | 条件 | 含义 |
| --- | --- | --- |
| **T1** | Invention | 答案无法从手册或数据库中检索得到 |
| **T2** | Long horizon | 单次通过不够，进展需要跨小时或数天的多轮依赖迭代 |
| **T3** | Verifiability | 存在任务原生的评价方式，能把真实改进和"有说服力但错误的声明"区分开 |

定义循环是 `proposal → execution → measurement → revised proposal`。

这三条同时排除了两类任务：没有评价者的开放式脑暴（缺 T3），以及耗时但不需要新决策的
固定流程（缺 T1/T2）。**这是判断 Argus 是否适用的 scoping test。**

针对稠密监督信号调优的系统是"只会答考题的学生"——它们在 kernel、leaderboard、单元测试
上有效，而在目标本身、约束集合、正确的度量方式都还在被发现的研究中失效
(`01_introduction.tex`)。所以运行时的职责不是爬分，而是**把一次战役维持得足够久，久到
目标本身变得清晰**。

**推论：进展不是每步单调改善。** 阶段索引和任务原生质量不必每轮上升——实验会失败，评审
会否决分支，后续测量会推翻先前假设。报告的原话是：预期的上升是**多轮之后 accepted
frontier 的推进**，而不是每次转移都单调改善 (`03_problem_formulation.tex`)。假设单调进展的
设计会把每一次回退当成 bug，并压制掉证伪工作——而证伪正是研究的正常产出。

---

## 2. 架构的推导：三个失效模式

整个架构不是从"多智能体"这个形式出发的，而是从三个具体失效模式反推出来的
(`01_introduction.tex`)。想清楚这三条，架构的其余部分几乎是被迫的：

| 失效模式 | 什么时候发生 | 被迫产生的机制 |
| --- | --- | --- |
| **Continuity** | 增长的 transcript 被压缩或丢弃，于是当一次修订被提出时，当初支持它的证据已经不存在了 | **持久化状态**，而不是更长的上下文窗口 |
| **Acceptance** | 执行工作的组件同时宣布工作完成 | **Engineer / Reviewer 分离** |
| **Experience** | 只有最终产物存活，于是被证伪的路线无法在日后被引用为"目标不可达"的证据 | **保留被拒绝的路线** |

> 更大的上下文窗口延长的是 session 连续性；而**认证一次目标变更**额外需要显式的状态、
> 归属和更新规则。

这解释了一个常见误解：Argus 的多角色不是"让多个模型讨论以提高质量"，而是**权限划分**。
Reviewer 存在不是因为两个模型比一个准，而是因为执行者不能同时是验收者。

### 2.1 为什么 pivot 需要被治理

目标修订与失败在外部是**不可区分的**：一个放弃目标的系统，可能是发现目标本身设错了，
也可能是失败了然后合理化。最终产物里没有任何东西能区分二者。

所以 Argus 不禁止 pivot，而是让 pivot 可被认证。一次可采纳的 pivot 需要：
(a) 有证据表明先前路线或目标不可达/设定有误，(b) 经由显式的角色边界准入，(c) 被记录，
使后续 mission 同时继承这次变更和它的理由。

不加治理的修订会导致目标漂移：**目标退化成执行者恰好能完成的那个东西。**

---

## 3. 权威分离

四个角色是**权限的划分**，不是流水线上的四个工位。它们参与同一个连续循环，但调度、
执行、记录三件事保持可分离。

| 角色 | 拥有的权威 | 明确无权做的事 |
| --- | --- | --- |
| **Manager** | operator 唯一前门；解析任务/lifetime/vertical；维护 GoalContract；**独占 stage 的语义决策** | 不代替 Engineer 实现，不代替 Reviewer 验收 |
| **Planner** | 读取真实项目状态；生成 bounded DAG 或后续任务；`replan_requested` 后替换剩余计划 | **不把 mission 判为完成**，不直接写 stage |
| **Engineer** | 用真实文件、工具、实验、硬件执行任务；更新 `CHECKPOINT.md`；交付可检查证据 | 不跳过 Reviewer，不写 stage，不静默放宽 GoalContract |
| **Reviewer** | 独立检查 artifact、日志与 checklist；返回 `done` / `continue` / `blocked` / `replan_requested` | 不写 stage，不扩大 mission 范围，不替 Planner 建计划 |

角色状态机在一个 stage 内反复执行 `M → P → E ⇄ R → M`。`E ⇄ R` 的振荡（修订循环）与
`M / P` 外层循环是**不同层级**：评审否决不会升级成重新规划。

### 3.1 三个平面

- **控制平面**锚定战役并调度工作；
- **执行平面**针对真实工具和产物执行一个 bounded mission；
- **记录平面**存储发生了什么，**但不决定工作在科学上是否完成**。

typed、append-only 的事件带是权威时间线；所有用户界面都是它的投影。这条防止记录本身变成
一个权威面——**记录了某件事不等于它被接受了**，UI 也不能成为第二个事实源。

### 3.2 完成的来源必须显式

完成永远不来自文件名、token 量或散文关键词。Mission 完成带有显式且被记录的**来源**
(`core/project_api.py`)，来源按强度排序：

```
planner_verdict (1)  <  vertical_completion_certificate (2)  <  independent_certification (3)
```

Vertical 声明自己要求的强度 `completion_gate ∈ {none, metric, certified}`，core 只做机械比较：

```
none (1)   metric (2)   certified (3)
```

三条设计取舍写在模块本身：

1. **排序是机械的**——它说的是哪个来源**压过**哪个，不是哪种工作更有价值。强来源可以满足
   任何不高于自己的要求。
2. **未知的 gate 按最强处理**（`_UNKNOWN_GATE_RANK = 3`）。fail closed：一个声明了本模块
   从未听说过的 gate 的 vertical，提出了一个我们无法核对的主张，而对不可读要求的安全解读
   是最严的那个，不是最松的那个。
3. **harness 不判断工作好不好**。要求的强度读自 vertical 自己的声明，证据来自 Reviewer；
   本模块只贡献一次机械比较和一次原子写入。

### 3.3 执行失败不是想法的证据

这条独立成节，因为它是最常被违反、后果最隐蔽的一条。

> **一个分不清"实验没跑起来"和"这个想法是错的"的 agent，会因为错误的理由杀死好想法。**

一个 TileLang import 错误、一块缺失的 GPU、一个 permission-denied 的 profiler、一次样本量不足的
预实验——它们**都不对假设说任何话**，但都产生一次失败的运行；而失败的运行会被读成负结果，
除非有东西禁止这种读法。`core/evidence_status.py` 就是那个东西。它把三件事拆成三个字段：

| 字段 | 问题 | 取值 |
| --- | --- | --- |
| `execution_status` | 这次尝试真的跑了吗？ | `completed` / `blocked` / `failed` |
| `failure_class` | 如果没跑干净，是什么坏了？ | 环境与工具类失败，与携带真实信息的失败**分开列出** |
| `idea_status` | 我们现在对这个前提相信什么？ | `untested` / `inconclusive` / `supported` / `refuted` |

**核心不变量**：一次从未有效检验过前提的运行，不能告诉我们关于该前提的任何事。因此：

- 环境/依赖/工具链/硬件类失败 → `idea_status` 只能是 `untested` 或 `inconclusive`；
- `execution_status != completed` → 不能 `supported` 或 `refuted`；
- 调度类信号（prior art、descoping）解释的是**下一步做什么**，不是关于前提的观测——
  它们不能让想法变成 supported 或 refuted，只能记为 replan 理由；
- 结论性判断（supported/refuted）之前，domain 要求的 grounding 字段必须齐全——
  **这些字段是让别人能复核该主张的东西**。

领域特化的推论同样重要：**实现不充分不是反证**（`implementation` 不属于 refuting failure
class），**样本量不足的预实验是 inconclusive 而不是负结果**（`statistical_power`）。

这个模型放在 `core` 是因为它不是 kernel 概念。每个 domain 通过 `EvidenceContract` 提供自己的
失败词汇和 grounding 要求，**不变量是共享且相同的**——规则被移动了，但没有被放宽。

配套的还有一条：**前提变了就开一份新的证据记录。** `premise_version` 是刻意版本化的，
重新定义前提会 bump 版本，使得关于旧前提的结论不能被静默地搬到新前提上——那是"一个被证伪的
主张在没有任何新实验的情况下变成被支持"的经典路径。

### 3.4 verification-gated 与 verification-guided 是不同尺度

术语精度在这里是有意的，用于防止"每次更新都经过独立评审"这类过度声称：

- **verification-guided** 指整体控制策略——决定是坚持、停止还是 pivot；
- **verification-gated** 指对**可复用更新**的准入条件，更窄；
- **reviewer-gated** 只用于独立 Reviewer 路径；
- **external grader** 只用于角色循环之外的任务原生评价器。

准入要求的是"该表面上实际存在的任务原生证据 + 其授权 owner 的提交"，**不意味着每一次
低风险更新都需要一个独立 Reviewer**。

---

## 4. Harness 与 Agent 的边界

这是本仓库唯一的 hard 原则，也是最常被违反的一条。

> **Harness 是领域无关的笨管道。它永远不做科研判断。**

| Harness 拥有 | Agent 拥有 |
| --- | --- |
| 管道（load / save / schedule / render / parse / persist） | **所有品味、质量、"够不够好"的裁决** |
| 预算（token 上限、日上限、单 mission 上限） | **所有领域判断**（这个假设新颖吗？这些证据真的支持这个声明吗？） |
| 反造假守卫（claim → evidence 链完整性、bundle provenance、tainted 标记） | 本轮的**最终裁决权**（Reviewer 的判断是 "done" 的唯一事实源） |
| 结构化 I/O（schema、退出码、journal） | |

### 4.1 判定测试

在往 `argus_skill/` 加任何代码前问：

> **这段代码做的判断，一个有科研素养的 Reviewer 是否也需要做？**

- **是** → 它不属于 harness。把判断移到 Reviewer 会读的 prompt / checklist 里，harness 只负责
  把事实暴露出来。
- **否** → 它是管道。大概率没问题。

### 4.2 正例与反例

✅ **属于 harness**

| 代码 | 为什么没问题 |
| --- | --- |
| 检查被引用的文件是否存在 | 反造假："你不能引用一个不存在的路径"。不是质量判断。 |
| 日预算上限阻断 | 管道：`spent >= cap` 是算术，不是判断。 |
| bundle 必须含 provenance 信息 | 可复现性。不是"这个证据好不好"。 |
| `TAINTED — DO NOT CITE` 硬阻断 | bundle 自己标记了污染。尊重该标记是反造假，不是判断。 |

❌ **不属于 harness**

| 代码 | 为什么是错的 |
| --- | --- |
| `min_delta = 0.02` 判断"改进是否有意义" | 0.02 在 benchmark A 上可发表，在 B 上是噪声。**Reviewer 决定，不是 Python。** |
| `min_benchmark_families = 3` 判断"证据是否够广" | 有的领域 2 个强 benchmark 就够，有的需要 5 个。 |
| "写作阶段超过 21 天自动隔离" | "21 天太长"是科研节奏判断。发 advisory 信号，让 planner 决定。 |
| 用关键词启发式判断目标是否在范围内 | 已在上游删除；不要复活。 |

### 4.3 想加判断时怎么改

1. **找出 agent 会用来做这个判断的事实**；
2. **计算并暴露该事实**为结构化 finding，**绝不是 pass/fail 裁决**——
   harness 打印 `baseline=0.62, proposed=0.66, delta=+0.04`，
   **不打印** `FAIL: improvement below 0.02 threshold`；
3. 通过 agent 可调用的工具或持久产物暴露它，让 Reviewer 直接查验；
4. **绝不让该检查的退出码决定科研质量**；硬失败只保留给结构性/反造假违规；
5. **让 Reviewer 裁决。**

```
要加一个新 gate / check / validator？
        │
        ▼
"一个有科研素养的 Reviewer，会不会因项目领域和目标不同
 而对这个检查的结论有不同意见？"
        │
   ┌────┴────┐
   │ 会      │ 不会
   ▼         ▼
ADVISORY    STRUCTURAL
只渲染事实   可以非零退出、
不影响退出码  硬阻断本轮
```

**存疑时默认 advisory。** 过于宽松的 advisory 的代价是浪费一个 Reviewer 轮次；写错的硬编码
阈值的代价是整个系统静默地拒绝掉 agent 本会接受的研究。

### 4.4 推论：harness 不规定 agent 怎么说话

同一条边界的另一个方向。角色**不被强制输出 JSON**：

> 一个被要求"只回一个 JSON 对象、别的什么都不要"的模型，会把它的回答花在满足序列化器上
> 而不是思考上，失去解释自己的能力，并且在多写了一句上下文时让整个决策失败。
> **harness 不比 agent 聪明**，规定 wire format 是 harness 在决定 agent 可以怎么说话。

所以角色自然地写，把决策写在具名行上（`KEY=value` 或 `KEY: value`），由
`core/role_reply.py` 一个宽容的读取器解析：忽略前导 bullet 和 `ARGUS_` 前缀、剥掉反引号和代码
围栏、大小写不敏感、无法识别的行直接跳过（所以上下文散文不花代价）、**最后一次出现获胜**
（一个在结尾重述结论的角色会被按人类的读法读）。JSON 在调用方选择时仍被接受，但从不被要求。

相邻的一条：**不透明的机器标识符不进入模型可见的判断**（`core/model_visible_text.py`）。
校验和与内容摘要用于缓存键、原子性身份、损坏检测和去重。比较两个不透明字符串**无法**建立
正确性、新鲜度、provenance 或任务完成——但一个被展示了"哈希匹配"的模型会把它当成正是这些
东西的证据。

### 4.5 只为"只有人能决定的事"打断人

自治边界同样刻意保持窄小 (`core/autonomy.py`)：**凭证、金钱、不可逆/对外的动作、以及对
operator 拥有的验收契约的变更**需要 operator；技术路线选择和可逆的诊断留给 Argus。

边界正则匹配的是**权威边界，不是一份通用的"听起来吓人的技术词"清单**。保持它窄，是为了不让
一次普通的超时、失败的测试或不可用的后端变成一次人工中断——**那是一个自治系统退化成传呼机的
方式。**

### 4.6 参考事故

历史上的 anti-mediocrity gate 把 `DEFAULT_MIN_DELTA = 0.02` 和 `DEFAULT_MIN_FAMILIES = 3`
写进 Python 并计入 stage_check 退出码，在评审中被否决。重写后的版本
(`skills/anti_mediocrity.py`) 是纯事实抽取器：不与任何阈值比较、不发裁决、不影响退出码。
`tests/skills/test_anti_mediocrity.py` 和 `tests/life/test_project_lifecycle.py` 用
"这些符号必须保持被删除"的形式把该决定锁住了。

---

## 5. 什么算 verified progress

一次完整的更新循环有四步 (`04_argus_method.tex`)：

1. 一次执行轨迹产生一个候选（memory / skill / procedure / 验证规则 / 路由决策 / 任务定义）；
2. 负责的角色对照产物与任务原生证据检查该候选；
3. **被授权的 owner** 提交、修订或拒绝它；
4. 后续某个 mission 把保留下来的状态取回，作为起始上下文或执行策略的一部分。

> **没有走完这条 commit-and-reuse 路径的活动，不计为 self-evolution。**

第 4 步是最容易被忽略的：一个从未被取回的更新同样不算数。这条排除了把活动量、token 数或
未经评审的总结当作进展。

### 5.1 状态归属刻意不统一

`H_t = {Memory, Skills, Tools, Verifiers, Routing}`，各自的归属不同：

| 表面 | 谁产生 | 谁提交 |
| --- | --- | --- |
| Memory | Engineer 轨迹 | Reviewer |
| Skills | Engineer / Scientist | Reviewer |
| Tools / procedures | 系统配置 | 双侧 |
| Verification（stage checklist） | Planner | Planner（Reviewer 提供反馈，不是第二道提交门） |
| Routing | 运行时策略 | Manager |
| Tasks / evaluations | Planner 撰写 | Scheduler |

**归属模型是刻意不统一的。** Memory 和 Skills 采用"工作 vs 认证"分离，因为它们携带可复用的
**主张**；配置类表面不需要评审门。统一加门会同时导致配置被过度阻塞和主张被检查不足。

### 5.2 演化发生在状态里，不在权重里

`H_{t+1} = U(H_t, τ_t, E_t, K_{t+1})`，其中 **`θ_{t+1} = θ_t`**。

θ 不变是一个**范围条件**：在线演化不要求梯度更新。更新 `U` 是部分的——很多 mission 只改
memory，有些 mission 什么可复用组件都不改。

这条把 self-evolution 的声明限定成可证伪的，并把所有改进定位在**可检查、可 diff、可回滚的
状态**里，而不是模型权重或对先前对话的无约束总结。

### 5.3 复利是一个反事实，不是修辞

```
G_L(ΔH_t) = Σ_{j=1..L} γ^{j-1} [ R_{q_{t+j}}(H_t) − R_{q_{t+j}}(H_t ⊕ ΔH_t) ]
```

`G_L > 0` 意味着这次被接受的 memory / skill / verifier / 路由规则 / 认证死分支，在预先设定的
任务分布上降低了未来损失。`G_L < 0` 表示**负迁移**。

这把"复利式智能"从单调修辞变成了一个反事实主张：**复用必须在匹配的未来任务上胜过冻结
状态。** 它同时承认负迁移是一个真实可能的结果——积累不能自我论证。

---

## 6. 失败是信息

### 6.1 过程数据严格支配最终产物

设 `D_process = {(s_k, a_k, e_k, r_k, ΔH_k)}`，`D_final = {y*}`。若 `Y = g(P)`，则对每个下游
决策问题 `q` 有 `R_q(P) ≤ R_q(Y)`；当两条过程记录产生相同产物却蕴含不同最优下一步时严格成立
(`03_problem_formulation.tex`, Proposition 1)。

证明是平凡的：任何使用 `Y` 的策略都能通过先施加 `g` 从 `P` 复现；反向模拟未必存在。

这使"保留失败分支"成为**信息论事实**而非偏好。注意 Argus 保留的是 typed、保护隐私的观测和
裁决，**不是**私有的思维链 transcript。

### 6.2 但支配是信息意义上的，不是计算意义上的

原始轨迹可能太大、太陈旧或自相矛盾，无法被高效使用。给定上下文预算 `b`，真正相关的对象是
一个 typed compression：

```
ψ*_b = argmin_{ψ: size ≤ b}  E_q[ R_q(ψ(P)) + λ_c · C_read(ψ(P)) ]
```

> **失败分支属于这个压缩，当且仅当它改变了下一步的最优动作——而不是仅仅因为它发生过。**

这正是为什么要保留**两个**表面：append-only 事件带保存信息量更大的实验记录；有界的、被评审
过的 CHECKPOINT 近似有限上下文预算下的决策有用压缩。它同时给出了什么该进 checkpoint 的
保留判据。

### 6.3 被拒绝的分支如何参与演化

被拒绝的分支在**被保留为 verified exclusion** 时参与演化：后续 mission 可以避免重复该分支，
并在提出 pivot 时引用它失败的证据。

关键工程含义：**一条被退休的路线必须带着退休它的证据。** 没有理由的退休会被重新尝试——
循环会用一个新名字重新发现同一条死路。

一个负结果即使没有扩大有效能力集合，也能通过排除一条失败分支产生价值。

---

## 7. 价值导向 vs 诚实导向

**诚信是准入条件，不是成果。**

两者都不作假。区别在于：诚实导向把"没做出来"当成一个可接受的终态，价值导向把它当成下一步的
输入。

| | 诚实导向 | 价值导向 |
| --- | --- | --- |
| 成功的定义 | 我如实报告了发生的事 | 我做出了别人能用的东西 |
| 遇到阻碍 | 记录阻碍，收工 | 换一条路，再试 |
| 对自己的 idea | 试一次，不行就丢 | 珍惜它，把工程做扎实 |
| 负结果 | 终点 | 诊断输入 |
| 典型句式 | "已诚实记录该方向不可行" | "该方向不可行，因此改为 X，结果是 Y" |

### 7.1 诚实导向的失败形态

一个真实事故：某项目把同一个 mission 重排了 **100 次，跨 75 小时**。每一轮 Reviewer 都给出
正确判断，每一条都是真的，没有任何造假。**而三天的净产出是零。**

根因是 harness 层的死锁（Planner 的"无任务"回答无法改变任何状态），已修。但形态值得记住：
**诚实的报告可以稳定地掩盖零产出。**

### 7.2 危险信号

在 Reviewer 裁决和 CHECKPOINT 里可见：

- 完成理由只引用 checklist 项被勾上，不引用**结果本身**；
- "已达到最低要求"作为完成依据出现；
- idea 只被实现了一个最省事的版本，没有任何一次迭代改进；
- 遇到第一个障碍就转向"诚实记录该路不通"。

> **checklist 是准入门槛，不是目标函数。** 把它当目标函数，就会得到一个精确满足门槛、
> 且仅仅满足门槛的产物。

### 7.3 好奇与诚实的边界

诚实约束的是**声明**，不是**探索**。

| 允许 | 不允许 |
| --- | --- |
| 试一个可能失败的方向 | 把失败说成成功 |
| 报告一个 N=1 的初步数字 | 把 N=1 的数字当成认证结果 |
| 提出没有证据的假设 | 提出没有证据的**结论** |
| 用不完美的代理指标探索 | 拿代理指标冒充目标指标 |

判据是**标注**：任何数字，只要标清了它的强度（N、硬件、shape、是否认证），就可以拿出来。
诚实要求的是不误导，不是不尝试。

反过来，"因为不确定所以不做"不是诚实，是把诚实当成了不作为的借口。**保守不是安全**——
一个平庸但稳妥的结果，和一次诚实的失败，对 operator 的价值同样接近于零；而激进尝试至少产生
可用的负结果。

### 7.4 两条轴必须分开

- **探索姿态（ExplorationPosture）**：愿意花多少预算探索非显然、高风险、高收益的路线；
- **验证强度（VerificationProfile）**：当前 artifact/claim 需要什么证据才能完成当前 mission。

不能用"更严格的 Reviewer"代替研究方向选择，也不能用"更有好奇心"降低真实性底线。
**一个更大胆的姿态绝不意味着更松的结论，一个更轻的 profile 绝不意味着更弱的事实。**

可调整的是"完成什么"，不是"事实是否真实"。任何 profile 下都必须阻断：伪造/重标/不可追溯的
证据；stub evaluator、常量 scorer、未执行却声称执行；通过放宽测试、容差或 scorer 制造成功；
把环境/权限/工具失败解释成科学反证；把 N=1 结果冒充普适结论。

**降低完成门槛是 operator 决定。** 提高标准立即生效；降低标准在没有 operator 确认时抛出
`PolicyConfirmationRequired`——Engineer 或 Reviewer 不能让自己的完成变得更容易
(`core/verification_policy.py`)。

---

## 8. 已知的设计缺陷

这些是报告自己点名的、尚未修复的问题。写在这里是因为**扩展系统时最容易踩的就是它们**。

### 8.1 Endogenous harnessing（内生性自缚）

Planner 在规划时点的信息下提出一个策略。从第一轮开始，Engineer 把它当作任务，Reviewer 把它
当作评判工作的标准。

> 一个 agent 的假设，变成了对之后每一个 agent 的外部约束——**包括那些现在知道得更多的
> agent。**

在被记录的轨迹中，Reviewer 识别出了更好的 validator 方案，但它的权限被限定在当前轮次，无法
重定义 mission。**更早、信息更少的决策靠权威而非证据取胜。**

报告的结论是：这个系统类别的约束瓶颈是**方法论的，不是认知的**——修复方式是改变权威路由，
而不是换更强的模型。

### 8.2 计划是硬约束还是可证伪假设

> 一个计划可以是 **contract**——有约束力、修改代价高；也可以是**可证伪的假设**——
> 一旦证据反转就应当被丢弃。

正确的划分是：

- **硬约束**：冻结的权威、禁止授予新信任、不可逆性限制。这些应当抵抗修订。
- **技术性下注**：路线、validator、表示方式的选择。这些应当可以被**任何产生反证的角色**推翻。

当前 Argus 把两者记录在同一个地方，于是一个技术策略继承了本该只属于安全边界的不可移动性。
GoalContract 已经编码了这条区分的一半（semantic vs precise 子句），缺的是：mission 的技术策略
被归到了不可移动的一侧，而**最可能持有反证的角色（Reviewer）没有移动它的通道**。

### 8.3 验证的可靠性以其证据边界为上限

一个可执行测试、形式化检查器、benchmark 或模型 Reviewer 都可能编码了**错误的性质**。

> 运行时可以记录并修订一个 verifier，但这并不使该 verifier 正确。

这是整个 verification-gated 设计最深的限制。推论：**决定性评价器在外部时（静态时序引擎、
独立化学 validator、形式化证明检查器），gate 无法被叙事满足**——这正是那些 vertical 构成更强
证据的原因。

### 8.4 派生的质量元数据必须与权威 stage 状态对账

在六篇论文的案例研究中，一个项目在其规范流水线和最终 PDF 都完成之后，仍保留着一个陈旧的
`blocked` assurance 快照。

> 产物完成和过程认证是**两个不同的事实**；一个滞后于权威状态的派生快照是一张假证书。

---

## 9. 不可破坏的系统不变量

以下已对照 `main` 核对。改动触碰任何一条前，先确认你在修的是不变量本身还是它的实现。

- 常驻角色是 **Manager、Planner、Engineer、Reviewer**；Curator 只属于可选团队模式
  (`team/curator.py`)。
- **Manager 是 pipeline stage 的唯一语义决策者。** Supervisor 只有一个机械补偿例外：
  bounded DAG 尚有同计划未完成节点时，`_apply_dynamic_plan_stage_guard`
  (`life/supervisor/_mission_execution_settlement.py`) 可把被提前推进的 stage 恢复到本 mission
  的起始 stage；它不能选择新的科研阶段。
- **Planner 负责 forward planning 和 DAG 替换，不负责 mission 验收。**
- `current_stage` 的写入口只有四个，全部在 `skills/stage_machine.py`，且都经由同一个原语
  `_set_stage`：`advance_stage`（严格向后）、`rollback_stage`（严格向前，并把下游降级为
  pending）、`reset_stage_for_replacement_intent`（Manager 确认的替换目标，可停在当前 stage）、
  `complete_final_stage`（不移动 stage，只把当前 stage 标记 done）。
- **`complete_final_stage` fail closed**：completion contract 版本或指纹取不到时抛
  `ValueError("completion contract unavailable")`，不放行。
- Reviewer 的有效状态是 `done`、`continue`、`blocked`、`replan_requested`
  (`reviewer/_parsing.py`)。`replan_requested` 直接请求 Planner 替换剩余计划。
- 当前 mission round 固定走 `Engineer → Reviewer`；不存在活跃的 `review=skip` 自审旁路。
  历史事件里的 `engineer_self_review` 是兼容字段，不是当前生产路径。
- `events.jsonl` 是项目历史事实源；`EventJournal` (`life/memory.py`) 是它的投影，不是第二份日志。
- 项目工作目录与 Argus project state root 是两个不同目录，恢复 session 不得偷偷重绑工作目录。
- `goal_contract.json` (`core/project_contract.py`) 保存 operator 目标、precise/semantic 子句、
  排除项与歧义。**precise 约束不能被 Manager 静默放宽。**
  - `semantic` 子句、排除项与歧义可以自由移动——澄清 operator 的意思是 Manager 的日常工作；
    要求人类批准每一次措辞修改会让契约在实践中变成只读。
  - 改动 `precise` 子句或目标本身，需要一份**绑定的**确认：它点名它覆盖的确切子句 id，
    带 nonce 和 TTL，并绑定到签发时的契约 revision。
  - **同意是绑定的，不是空白支票**——一个"Manager 可以编辑约束"的总开关会连下一次变更一起
    授权，而那正是要防的事。子句 id 由**内容派生**（sha256 截断），所以一份点名某子句的确认
    不能通过重排列表被重定向到另一个子句上；revision 绑定则阻止一份攥在手里的确认在契约
    move on 之后被重放。
- **Manager 可以自由提议，但不能静默决定。** Manager 被期望对 operator 从未提到的指标、阈值、
  baseline 和范围限制运用自己的判断——但任何**提议**（而非复述）的东西进入 `questions`，
  绝不进入被重写的 brief。**operator 绝不应该发现一个他们没有同意过的要求。**
- **Harness 保证存在一个合法的下一步，但从不替 Manager 选这一步。** 任何转移之后，落点 stage
  被强制回到可执行状态，所以永远存在合法的下一步；但去哪里仍由 Manager 决定。该保证从不覆盖
  一个仍然可执行的状态，并刻意排除 `complete`。
  （事故背景：回滚到一个已经 `done` 的 stage 会死锁——Planner 无法为一个 done 的 stage 派发
  工作，而只有 Manager 能推进，于是循环永远空转发 `planner_waiting`。修复不能变成 harness
  替人选阶段。）
- **Stage 认证是一张收据，不是一次裁决**（`core/stage_certificate.py`）。stage-closing 评审在
  host 侧被记录为携带 checklist 指纹和被评审项证据指纹的证书，原子写入。一次已完成的认证尝试
  会阻止重复尝试，**直到一次非 stage-closing 的修复真的改变了 stage 证据**——否则 Planner 每个
  周期重新提议同一个 gate，循环在完全相同的裁决上空转（线上观测到：5 次相同裁决、4 次跳过、
  无法退出）。
- **Argus 可以读一个外部完成门，但永远不能撰写一个**（`core/external_completion_gate.py`）。
  可选的项目本地 completion gate 让外部控制方拥有权威结果，Argus 拥有达成它所需的工作。
  本模块**不提供写入器**；路径为绝对路径或逃逸出项目根时被拒绝。
  **一个能给自己签发完成证书的系统，没有证书。**
- **唯一的货币预算是 host-global daily USD cap** (`core/cost_control.py`)。预算在集中的
  model-call 与 external-job 边界检查，任何角色不能扩大自己的额度。
- **不要为了承载一个能力而发明一个角色。** Argus 恰好有四个常驻角色。Engineer 拥有的 Skill
  Scientist 通过 `banner_role` 参数请求它已有的 vertical overlay，而**不假装 Scientist 是第五个
  常驻角色**——每一个新角色都是一条新的权威边界、一份新的 prompt 预算、以及一个决策可能被做
  两次的新地方。**在已有角色上加一个参数，比加一个角色便宜。**
- **fail-open 是一个必须在原地被论证的决定。** fail-open 和 fail-hard 都在用，但每一处都在调用点
  的注释或 docstring 里说明它是哪一种、以及为什么。一个未加标注的 `except Exception` 与 bug
  无法区分；点明方向和理由使该安全性质可被评审，并让后来的读者看出一个守卫的假设何时不再成立。
- 一个 daemon 的实际行为由它加载的 source root 和 release identity 决定；包版本号相同不代表
  代码相同。
- **Core 永不 import 具体 vertical。** 由 `tests/core/test_vertical_contract.py` 的 AST 测试机械
  强制。

> **已过时的历史表述：** 旧文档提到论文型 vertical 的 completion gate 名为 `full_paper` /
> `full_paper_gate`。当前 `main` 上不存在该名字；gate 取值是 `none` / `metric` / `certified`
> (`core/project_api.py`)。

---

## 10. 扩展系统时的方法

### 10.1 顺序

1. **对照哲学** — 读本文第 4 节，问自己"我要加的这段代码是科研判断还是笨管道？"
   是判断 → 不写代码，写 checklist 给 Reviewer。是管道 → 继续。
2. **读当前设计 + 相关历史** — 当前契约从 `argus_skill/` 和 `tests/` 读；某个机制**为什么**
   被加入、删除或重写，用 `git log -S'<symbol>' --oneline --all` 从历史读。
3. **找现有钩子，不要重构** — 90% 的"集成"问题是找对接入点。
4. **测试驱动** — 至少一个端到端测试证明集成路径走通。

### 10.2 集成强度梯度（按改动量）

1. **新增一个模块 + CLI 入口**（最小）：`python -m argus_skill.<area>.<module>`，
   改动 = 新增 1 文件、0 修改。
2. **挂到已有的 vertical 契约钩子**：实现 `stage_completion_issues` / `planner_task_issues` /
   `LIBRARY_PREPARER` 等，core 已经在调用，改动 = 只动 vertical 自己的目录。
3. **加顶层 CLI flag**：`apps/cli.py` 的 `build_parser()` + `action_flags` + dispatch + handler，
   四处同步。
4. **改 schema / 持久化格式**（最大，仅当真的需要）：字段 + 序列化 + migration + 测试 + 文档。

### 10.3 反模式

- ❌ 新建一套并行的 supervisor / daemon / prompt 组装链——先看现有的能不能在 tick 里加一步。
- ❌ 用自动命令的退出码覆盖 Reviewer 裁决——暴露事实和工具，让 Reviewer 自己核验。
- ❌ 从 objective 散文用关键词猜 vertical、scope 或 completion——用 Manager/Planner 的结构化字段。
- ❌ 看到旧配置名就恢复旧机制——先用 `git log -S` 确认它为何被删除。
- ❌ 把长篇设计文档整段复制进四角色 prompt。优先级是：短的结构化 effective-policy block →
  vertical-owned checklist metadata → agent 按需读取的 Skill/reference → 行为测试与可观测指标。

### 10.4 本文与 prompt 的关系

**不要**把本文写成 prompt 里的又一段长文案。它是给维护者、Reviewer 和 operator 判断用的参照，
不是给 Engineer 的第二份行为守则——那会既涨 token 又和现有角色契约重复。

---

## 附：相关文档

| 主题 | 文档 | 代码事实源 |
| --- | --- | --- |
| 运行流程与角色转移 | `docs/FEATURES.md` | `manager/`、`life/supervisor/`、`engineer/`、`reviewer/` |
| 角色 session 与按需 Skill | `docs/ROLE_SESSIONS_AND_SKILLS.md` | `skills/store.py`、`skills/role_library.py` |
| 研究主动性与分级验证的改进计划 | `docs/RESEARCH_AGENCY_AND_VERIFICATION_TODO.md` | `core/verification_policy.py` |
| Vertical 扩展边界 | `math-docs/VERTICAL_BOUNDARY.md` | `core/vertical_contract.py`、`verticals/_base.py` |
| 后端提供方 | `docs/backend-providers.md` | `adapters/agent_cli_backend/` |
| 形式化的问题定义与经验结果 | `technical_report/` | 绑定报告标注的版本，不覆盖当前运行契约 |
