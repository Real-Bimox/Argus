# 明确不做的部分，以及重新开工的信号

这份文件记录**决定不建造什么**。它不是 backlog——backlog 是「还没轮到」，这里是「判断过，现在不做」。

每一条都写三件事：它是什么、为什么不做、什么现象出现时应当重新打开。第三件最重要。一个没有触发条件的延期等于遗忘，几个月后没人分得清「当初想清楚了不做」和「当初漏了」。

---

## MechanismVersion（PR1 中被砍掉的第四个实体）

**是什么**：把可复用的解题机制（而不是具体结论）作为一等实体存进状态内核，带版本。

**为什么不做**：它是全部候选实体里最缺运行数据支撑的一个。goal 文档自己在「哪些经验很可能可以复用」一节里就承认，agent 是否真的稳定地产生 mechanisms，要跑过真实问题才知道。在没有数据的情况下先把 schema 固化下来，是把一个未经验证的假设写成不可逆的结构。

内核最终收敛到三个实体（context / claim / assumption）加 `ProofRoute`，每一个都对应一个已经存在的失败模式。

**重新打开的信号**：跑过若干个真实数学项目后，回头看 `CHECKPOINT.md` 和退休路线的理由，发现同一个机制被不同项目分别重新描述了三次以上，且描述之间足够相似到可以合并。那时才有数据决定它的字段。

---

## PR4 完整版（统一 verifier 接口 + 多后端 + daemon）

**是什么**：一个通用的异步验证器接口，Lean、Python、任意命令都是后端，由常驻进程调度与回收。

**为什么做缩减版**：真正付出等待代价的只有 Lean——带 Mathlib 的编译是分钟级，而 Python 层的反例检查按用户的判断直接交给 Reviewer 同步做就行，它不需要异步机械。为一个后端建三个后端的抽象，抽象会长成后端的形状，之后加真正的第二个后端时还得重写。

daemon 被砍掉的理由更硬：常驻进程要处理崩溃、重启、孤儿回收、状态漂移，而这里进程死亡的全部代价是**重编译一次**。用一个新的长期故障源去换一次重编译，不划算。

已确认不需要新的 core seam：`argus_skill/engineer/round_prompt.py`、`argus_skill/engineer/round_reviewer.py`、`argus_skill/life/supervisor/_planning_cycle.py` 三处「安全边界」本来就都在消费外部工作。

**重新打开的信号**：出现第二个真正需要异步的验证后端——即单次运行稳定超过分钟级、且不能交给 Reviewer 同步完成的那种。届时统一接口有两个真实实例可以对照，抽象才有形状。

---

## PR7 原形态（受监督的 portfolio orchestrator）

**是什么**：一个 Engineer 启动受监督的 portfolio，workers 提交 proposal，主 Engineer 合并。

**为什么否决**：被 goal 文档自己的判据否掉的。判据原文是「不要为了实现 portfolio reasoning，把 Argus 的一个 Engineer mission 逐渐变成隐藏在内部的第二个完整 orchestrator」，而 PR7 描述的正是这个。

改成的形态见 PLAN_REVIEW §5.4：只读 explorer。worker 以 external verifier 身份存在，隔离 workspace、只读 canonical state、只提交 candidate，主 Engineer 下一轮消费。这样它是 evidence producer 而不是 orchestrator，符合「specialists 产生 artifacts，四角色保留控制权」。

**重新打开的信号**：真正的并行 approach portfolio 属于「转移到专用 Research Math OS」那一侧，不在本仓库的边界内。

---

## PR8（typed distillation / 跨项目知识提取）

**是什么**：把一次 mission 学到的东西结构化地提取出来，供后续项目复用。

**为什么不做**：Argus **已经有自进化**。mission 结束后会跑一次 TEAM learning review（`argus_skill/life/supervisor/_evolution.py:46` 的 `_evolve_runtime_skills_after_mission`，落到 `argus_skill/manager/skill_tidy.py:174` 的 `propagate_after_mission`），把自然语言 Skill 写进跨项目共享的角色目录。而 Skill 层是**纯路径**的——`argus_skill/skills/layered.py` 的模块 docstring 写得很直白：「the runtime does not parse, match, rank, copy, or rewrite Skill documents」。

所以 PR8 是给一个**已经存在的能力**做类型化版本。而要蒸馏的东西一分为二，两半都已经有归属：

- **方法论**——「这类问题先试这个变换」——属于散文 Skill，现有机制已经在做。
- **数学事实**——「这个定理成立」——属于 ledger。ledger 已经有版本、有引用、有 `check`，是比新 schema 更强的载体。

剩下一个**没有答案的阻塞问题**：项目 A 里 `confirmed` 的一条引用，在项目 B 里还算 `confirmed` 吗？这不是工程问题。引用核查是「某人在某个 locator 读到了某段文字」，那段文字的内容跨项目不变；但**该定理的假设在新语境下是否成立**是一个全新的数学判断，而这正是引用核查三层里最要命的第 3 层（适用性）。把 A 的 `confirmed` 直接搬到 B，等于把第 2 层的答案冒充成第 3 层的答案。在想清楚这一点之前建 schema，会把这个混淆固化进去。

**重新打开的信号**：出现一个具体实例——某个 mission 重新核查了先前 mission 已经核查过的同一条引用，且两次的语境确实相同。有了这个实例，跨项目继承的边界就有了讨论的对象，而不是凭空设计。

---

## C-full（第四个 research 阶段）

**是什么**：给 math vertical 加一个真正的第四阶段，带自己的 checklist 和独立的 Reviewer 门。

**为什么做 C-lite**：因为**光有阶段等于零**。一条已确认、已归档的引用，对注入 mission 的开场白造成的改变是 0 字节——坏掉的是传播通道，不是时机。先加阶段而不修通道，得到的是一个按时完成、没人读到结果的阶段。

C-lite 把前置检索做成 `scope` 的一条**验收标准**（`scope.known-status-recorded`），配 PR-A 打通的传播通道。两者严格互补：C-lite 决定什么被记录，PR-A 决定下游有没有人看得见。任何一个单独上都产生不了效果。

**重新打开的信号**：`scope` 的验收标准在真实项目里被系统性地敷衍过去——即多个项目的 `scope` 都以「搜索了，没找到相关的」通过，而 `solve` 阶段随后仍然在重复检索。那说明一条验收标准的约束力不够，需要一个有独立 Reviewer 的阶段。

---

## deep-think lane（PLAN_REVIEW §5.5 提出，尚无落点）

**是什么**：给需要长时间连续思考的问题一条不被切成 bounded mission 的通道。

**为什么还没做**：Argus 现有结构里最接近的实现不需要新机制——一个 `bounded=False`、`iterate=True`、`iteration_max_cycles` 拉高、Reviewer 只在 checkpoint 介入的长 mission 就是它。缺的不是机制，是**在 math policy 里显式声明什么问题走这条 lane**。

这一条与上面几条不同：它不是「判断过不做」，而是「知道该做、还没决定判据」。写在这里是因为它有真实的丢失风险——如果不声明，所有数学工作都会被默认切成 bounded mission，恰好丢掉 unit-distance 那一类结果的产生条件。

**重新打开的信号**：这一条不等信号，它等的是判据。下一次有人问「这个问题该不该切成小 mission」的时候，答案就该写进 math policy。
