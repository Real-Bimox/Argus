## Argus Math vertical

Argus 版本只实现那些能直接提高数学研究能力、并且可以独立做消融实验的机制：

1. 数学任务的动态策略
prove/disprove 双线；
counterexample-first 的条件化策略；
proof、computation、retrieval、Lean 之间的动态切换；
Reviewer 发现问题后触发 replan。

2. 异步多源 verification

LLM Reviewer；
Python/Sage/SMT；
Lean；
文献检查。

重点是 evidence-triggered，而不是要求所有结果都走完整固定流程。

3. 轻量 claim/obligation ledger

当前目标；
open lemmas；
failed approaches；
evidence；
open assumptions；
Lean jobs。

4. 版本绑定的异步 Lean
Lean job 绑定 statement hash；
reasoning 不等待 Lean；
旧版本的 Lean 结果返回后不得认证新版本；
failure 能触发局部回溯和 replan。

5. 数学专属 skill / experience
记录具体 failure mechanism；
避免重复相同路线；
对新问题复用经过验证的策略；
先保守写入，不做激进自动演化。

这已经足以支撑一个有内容的研究问题，例如：

在通用 long-horizon harness 上，显式 mathematical obligations、evidence-triggered verification 和异步 formal feedback，能否显著提高开放式数学问题的正确性、效率与恢复能力？

我建议从一开始把 Argus Math vertical 分成三层。

Layer A: Argus Adapter
    把 Manager / Planner / Engineer / Reviewer / external-work
    接到数学系统

Layer B: Reusable Math Kernel
    claim、obligation、evidence、verification job、
    invalidation、context projection

Layer C: Argus Math Policy
    prompts、stage checklist、routing heuristic、
    completion policy

具体目录可以类似：

argus_skill/
    research_math/
        models.py
        store.py
        obligations.py
        evidence.py
        context.py
        invalidation.py
        verifiers/
            base.py
            lean.py
            code.py
            literature.py

    verticals/math/
        stages.py
        policy.py
        skills/
        argus_adapter.py

其中：

research_math/ 尽量不 import Manager、Planner、Reviewer；
verifier interface 不依赖 Argus backlog；
claim ID、evidence ID、job manifest 使用独立稳定 schema；
Argus events 只是一个 adapter；
SQLite/event store 的读写不散落到 prompts 和 role code 中。

这样未来创建独立 repo 时，可以直接迁移：

research_math/models.py
research_math/obligations.py
research_math/evidence.py
research_math/verifiers/*
research_math/invalidation.py

真正需要重写的主要是 orchestration 和 UI。

## 哪些经验很可能可以复用

即使最终代码没有全部迁移，Argus 阶段仍然会产出非常有价值的设计经验。

1. 什么信息真的值得结构化

报告里可以定义几十种 node 和 edge，但运行真实问题后才知道：

agent 是否真的稳定地产生 mechanisms；
proof obligation 粒度应多大；
failed route 需要记录到什么程度；
statement version 多频繁变化；
Reviewer 最需要看到哪些 evidence；
context bundle 多大才不丢失关键全局信息。

这些很难纯靠架构设计推出。

2. 异步 verification 的控制规律

你会实际观察：

Lean 多久提交一次最合适；
哪类 claim 值得先 formalize statement；
哪些 Lean failures 是语法/库问题，哪些是真数学问题；
formal feedback 何时应中断当前路线；
如何避免旧 job 返回后污染新 statement；
code 和 Lean 的优先级应怎样分配。

这些数据会直接决定专用 OS 的 scheduler。

3. General harness 与 math-specific state 的真实边界

Argus 实现会帮助识别：

哪些功能确实应属于通用 harness；
哪些必须进入 Math kernel；
哪些只需是 prompt policy；
哪些必须机械验证，不能依赖角色自觉；
哪些状态适合 event log，哪些适合数据库 projection。

这是未来拆 repo 时最重要的经验之一。

4. Self-evolution 的有效单位

实际运行后可能发现可迁移经验的单位不是完整 skill，而是：

proof pattern；
mechanism template；
falsification policy；
formalization repair；
Mathlib retrieval adapter；
failure constraint；
scheduler rule。

这会决定未来 Research OS 的 memory schema，而不是预先假定“都蒸馏成 Markdown skill”。

## 需要明确设置一个停止改造 Argus 的边界

我建议用下面的判据判断某项功能是否继续留在 Argus。

留在 Argus，若它满足：

能通过 vertical hook 或独立 library 接入；
不改变四角色 authority；
不要求 Supervisor 变成通用并行图执行引擎；
不要求 backlog 同时承担数学语义；
对其他 scientific vertical 也可能有价值；
能较快形成可评测实验。

转移到专用 Research Math OS，若它要求：

多个长期并行 reasoning branches；
branch-level transaction 和 merge；
复杂 semantic graph 查询；
AND–OR proof search 成为核心 scheduler；
claim/evidence 更新驱动系统持续事件循环；
多 verifier council 有独立 arbitration；
跨项目数学 memory 与 causal policy evolution；
面向大型 graph 的专用研究 UI。

尤其是：不要为了实现 portfolio reasoning，把 Argus 的一个 Engineer mission 逐渐变成隐藏在内部的第二个完整 orchestrator。 一旦出现这种趋势，就应当把该功能放到独立系统。