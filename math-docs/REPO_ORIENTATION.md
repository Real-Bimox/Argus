# Argus 仓库导览（session 起手读这一篇）

> **这篇文档存在的理由**：让一个新 session 读完就能动手，不必再为了"这个仓库是怎么组织的"
> 而并发一堆 subagent 去扫代码。它记录的是**结构与定位**——哪个概念住在哪个文件、
> 调用链怎么走、哪些东西看着像活的其实是死的。
>
> 它**不**解释"为什么这样设计"（见 `math-docs/DESIGN_PHILOSOPHY.md`），
> 也**不**给出 math vertical 的改动边界（见 `math-docs/VERTICAL_BOUNDARY.md`）。
>
> **准确性约定**：本文每条结论都来自读源码，并尽量附上可自查的文件:行号。
> 行号会随提交漂移，符号名不会——**以符号名为准，行号只是路标**。
> 凡是我没有亲自验证的，都显式标了「未验证」。

---

## 0. 三十秒速览

Argus 是一个**领域无关的长时程 agent 运行时**。它不是一个"帮你写代码的工具"，
而是一个把「一个模糊的目标」变成「一串被验证过的进展」的调度系统。

- **四个常驻角色**：Manager（控制）→ Planner（方向）→ Engineer（执行）⇄ Reviewer（验证）。
  `RoleName` 枚举严格只有这 4 个成员：`argus_skill/roles/prompts/types.py:10-14`。
- **Vertical = 领域插件**：一个 duck-typed 的 Python 模块 `argus_skill/verticals/<name>/stages.py`。
  Core **永不 import 具体 vertical**，这条由 AST 测试强制：
  `tests/core/test_vertical_contract.py:159` (`test_core_has_no_vertical_package_imports`)。
- **规模**：`argus_skill/` 下 570 个 `.py`，约 16.1 万行；`tests/` 下 455 个 `test_*.py`。
  其中 `verticals/` 一家就占 4.4 万行——**领域逻辑的体量远大于 core**，这是刻意的。
- **两个入口点**（`pyproject.toml:104-106`）：
  - `argus` → `argus_skill/apps/tui_launcher.py:main` → exec 一个 Node/Ink 的 TUI bundle；
    带管理类 flag 时回落到 Python CLI。
  - `argus-skill` → `argus_skill/__main__.py:main`，纯 Python 后端 CLI。

---

## 1. 顶层目录

| 路径 | 是什么 |
|---|---|
| `argus_skill/` | **全部 Python 运行时**。下面 §2 展开。 |
| `tests/` | 455 个测试文件。**这是本仓库最可靠的规格说明**——见 §10。 |
| `frontend/` | `tui/`（Ink 驾驶舱，打包成 `bundle/argus.mjs`）、`web/`、`core/`。 |
| `desktop/` | Electron 壳 + PyInstaller 打包（`argus_backend.spec`）。 |
| `docs/` | **原有文档**，不要跟本目录混。含 `FEATURES.md`（运行流程）、`ROLE_SESSIONS_AND_SKILLS.md`、`RESEARCH_AGENCY_AND_VERIFICATION_TODO.md`、`backend-providers.md`。 |
| `math-docs/` | **本目录**：我为 math 特化写的三篇。 |
| `technical_report/` | LaTeX 技术报告（`main.tex` + `sections/` + 已编译的 pdf）。设计理念的原始叙述来源。 |

---

## 2. `argus_skill/` 子包地图

按行数排序，附一句话职责。**读代码时先定位到子包，再进文件**。

| 子包 | 行数 | 职责 |
|---|---:|---|
| `verticals/` | 44290 | 全部领域插件。23 个内置 vertical + `_base.py`（加载器）+ `_registry.py`（out-of-tree 插件）+ `_data_domain.py`（Manager 运行时撰写的 JSON domain）。 |
| `life/` | 19139 | **长时程调度**。`supervisor/` 是心脏；还有 memory、event log、project lifecycle、chat 前门、IM bot。 |
| `core/` | 16951 | 领域无关的基础设施：契约、路径、成本、事件、session、证据、验证策略。**63 个文件，全是"框架自己拥有"的东西**。 |
| `webapi/` | 11057 | HTTP/WS API，给 web 与 desktop 用。 |
| `tools/` | 10307 | agent 可调用的工具：`lean_check.py`、`gpu_lease.py`、`pdf_chat.py`、`subagent/`、`team.py`、`capability_vault.py`。 |
| `manager/` | 9673 | Manager 角色的全部实现：前门、路由、stage 操作、vertical 选择、domain 撰写、plan 模式、自维护。 |
| `skills/` | 9108 | Skill 库 + stage machine + checklist store + 反平庸 / 证据链 / provenance 等横切件。 |
| `apps/` | 8997 | CLI 应用层与 `_runtime*.py`（真正构造 `SkillLoop` 的地方）。 |
| `daemon/` | 7275 | 后台常驻进程：life worker、握手、健康检查、进程管理。 |
| `agent_cli/` | 4322 | 与外部 agent CLI 交互的封装。 |
| `adapters/` | 3763 | `agent_cli_backend/`——真正 spawn agent 子进程的地方；`memory_backend.py`；`stream_progress.py`。 |
| `roles/` | 3378 | **角色 prompt 的唯一权威**：`prompts/{manager,planner,engineer,reviewer}.py` + `registry.py` + `types.py`；`task_contract.py`。 |
| `engineer/` | 3565 | Engineer 的 round loop：执行、自审、settlement、stop signal、background subagent。 |
| `team/` | 1806 | 多 agent 协作。 |
| `domains/` | 1551 | **domain overlay**，与 vertical 正交（目前只有 `chemistry`）。叠加在 workflow vertical 之上。 |
| `cli/` | 793 | `cli/_core.py:main` —— Python 侧的 argparse 入口。 |
| `planner/` | 1057 | Planner 执行侧（prompt 在 `roles/prompts/planner.py`）。 |
| `reviewer/` | 852 | Reviewer 执行侧：`_core.py`（`Reviewer.evaluate`）+ `_parsing.py`。 |
| `builtin_skills/` | 1095 | 随包发布的通用 Skill 文档。 |
| `providers/` | 835 | Copilot 配额/守卫。 |
| `wiki/` | 507 | 项目 wiki 记忆。 |
| `release_tools/` | 341 | 发布身份与校验。 |

顶层还有四个模块：`loop.py`（`SkillLoop`）、`release.py`（`release_identity`）、
`__main__.py`、`__init__.py`。

---

## 3. 运行时调用链（从进程启动到 agent 干活）

这是**最值得记住的一张图**。遇到"这个行为是谁决定的"，沿这条链找。

```
argus (TUI)  ──exec──>  Node Ink bundle  ──spawn──>  argus-skill (Python)
                                                          │
argus-skill --daemon ──> daemon/life_worker.py ───────────┤
                             │  _life_worker_boot.py:554  构造 supervisor
                             │  _life_worker_runtime_context.py:171  组装
                             │      LifeSupervisorConfig + runner namespace
                             ▼
                      life/supervisor/_core.py:LifeSupervisor
                             │  .run()   :532   —— 循环直到 backlog 空 / 预算跳闸 / stop_event
                             │  .tick()  :907   —— 处理一个 backlog item
                             │
                             ├─ 规划周期  _planning_cycle*.py   （Planner 出方向、出裁决）
                             └─ 任务执行  _mission_execution*.py
                                     │  runner namespace = apps/_runtime.py:_SkillLoopRunner
                                     ▼
                             apps/_runtime_execute.py:708  构造 SkillLoop
                                     │
                                     ▼
                             loop.py:164  SkillLoop
                                     │   task → Skill 库路径 → round loop
                                     ▼
                          engineer/runner.py:65  SupervisedEngineer.run()  :92
                                     │  ⇄  reviewer/_core.py:80  Reviewer.evaluate()  :102
                                     ▼
                          adapters/agent_cli_backend/_exec_spawn.py
                                     │
                                     ▼
                              真正的 agent CLI 子进程
```

几个必须知道的细节：

- **`LifeSupervisor` 是 8 个 mixin 拼起来的**（`_core.py:169-177`）：
  `EvolutionMixin`、`IdleCycleMixin`、`MissionExecutionMixin`、`LifecycleMixin`、
  `PlanningContextMixin`、`PlanningCycleMixin`、`PlannerOrchestrationMixin`、
  `PlannerRenderingMixin`。找方法找不到时，去对应的 `_*.py` 里搜。
- **`run()` 的退出条件**都在 `_core.py:532-620` 那段：manager 配置待定、
  `_maybe_stop()`（预算/暂停）、idle timeout、以及"最终认证门已过且日志里有认证"的 early auto-stop。
- **`tick()` 是单步版本**，测试与 `life next` 用它。写测试时优先打 `tick()`。
- **round loop 的语义**：Engineer 对 bounded 任务可以显式自验并豁免 Reviewer；
  否则一直被 Reviewer 监督到满意为止。见 `loop.py` 的模块 docstring（写得很清楚，值得原文读一遍）。

---

## 4. 四个角色：prompt 从哪来

**所有角色 prompt 的权威在 `argus_skill/roles/prompts/`**，不在各自的执行包里。
`life/router.py` 只是从 `roles/prompts/manager.py` 再导出，保持源码兼容。

- `roles/prompts/types.py`：`RoleName`（4 个）、`ChecklistMode`（`none`/`stage`/`full_pipeline`/`auto`）、
  `RolePromptRequest`。
- `roles/prompts/registry.py:174` `resolve_role_prompt(request) -> ResolvedRolePrompt`——唯一的解析入口。
- `RolePromptRequest.banner_role`（`types.py:41`）是给 "Skill Scientist" 用的：
  它让 Engineer 拥有的 Scientist 能力去取自己的 vertical overlay，
  **而不必假装 Scientist 是第五个常驻角色**。这条注释就写在字段旁边，是设计意图的直接证据。

角色的**领域特化**有两条完全不同的投递路径，别混：

| 路径 | 机制 | 能触达谁 |
|---|---|---|
| **role banner** | vertical 的 `role_banner(role)` → `VerticalContract.banner()` | 只有 4 个常驻角色（生产代码里没有任何地方传 `banner_role=`）。 |
| **skill store 播种** | vertical 的 `skills/<role>/*.md` 被写进 Skill 库 | 全部 6 个目录（含 `scientist/`），但**只在操作员显式跑 `--export-builtin-skills` 时**。 |

后果：math 的两个 `skills/scientist/*.md` **不会被自动加载**。
（`role_banner("scientist")` / `("scientist_create")` 走的是第一条路径，是活的；
`.md` 文件走第二条，是手动的。）

---

## 5. Vertical 机制

### 5.1 加载

`argus_skill/verticals/_base.py:39` `load_vertical(name, project_root=None)`：

1. 归一化名字（`_normalize_vertical_name`，会剥掉尾部的 `-needed` 哨兵）。
2. 查别名表 `_VERTICAL_IMPORT_ALIASES`（目前只有一条：
   `digital_circuit_benchmark` → `digital_circuit.benchmark`）。
3. import `argus_skill.verticals.<import_name>.stages`。
4. 也支持 **out-of-tree 插件**（`_registry.py`，entry-point group `argus_skill.verticals`，
   `VERTICAL_API_VERSION = 1`）与 **project-local data domain**（`_data_domain.py`）。

`_base.py` 提供一层 `vertical_*()` 访问器（`vertical_completion_gate`、`vertical_role_banner`、
`vertical_stage_completion_issues` ……）。**core 与 skills 层通过这些函数取值，不直接 getattr**。

### 5.2 契约

`argus_skill/core/vertical_contract.py`：**21 个 dataclass 字段 + 1 个派生 property + 7 个包装方法**。

```python
VERTICAL_CONTRACT_VERSION = 1
_COMPLETION_GATES = frozenset({"none", "metric", "certified"})
_WORKFLOW_MODES  = frozenset({"staged", "direct", "proportional"})
_MISSION_KINDS   = frozenset({"custom", "optimize", "research", "software"})
```

必填 4 个：`name`、`stage_order`、`checklist_items`、`completion_gate`。其余有默认值。

> ⚠️ **注意**：有些字段是通过包装方法被读的（`banner()`、`altitude()`、`prepare_libraries()`、
> `primary_deliverables()`、`completion_issues()`、`planner_task_issues()`）。
> **只 grep 字段名会漏掉真正的消费者**——要连方法名一起搜。

### 5.3 哪些字段是活的、哪些是死的

这是我在这个仓库里花时间最多、也最反直觉的一块。详细论证在 `VERTICAL_BOUNDARY.md`，
这里只给结论：

| 符号 | 状态 |
|---|---|
| `stage_completion_issues` | **活**。math 唯一真正生效的钩子。 |
| `CHECKLIST_ITEMS` / `role_banner` / `STAGE_ORDER` / `WORKFLOW_MODE` | **活**。 |
| `STAGE_CHECKS` | **死**。被 `vertical_contract()` 校验，但运行时从不执行。 |
| `STAGE_PRIMARY_DELIVERABLES` | **死**。 |
| `EVIDENCE_SCHEMA` | **死**。 |
| `assurance_level`（property） | **死**。是 `stage_checks` 在 `argus_skill` 内唯一的读者，而它自己没有生产消费者。 |
| `REVIEWER_CHECKLISTS` | **根本不在契约里**（math 定义了，但契约不读它）。 |

### 5.4 23 个内置 vertical

`argus_skill/skills/vertical_select.py:62` 的 `VERTICALS` 元组（23 个），
配套 `VERTICAL_PURPOSES`（一行用途，喂给 Manager 的选型 prompt，键必须与 `VERTICALS` 同步）。

按 Python 行数看规模差距极大——这本身就是"vertical 该多重"的经验数据：

```
research 12954 │ quant 8022 │ physics 4356 │ fiction_writing 3604
kernel_engineering 2846 │ chip_design 1741 │ digital_circuit 1059
classical_poetry 889 │ nanochat 775 │ math 772 │ literary_editor 564
prose 549 │ modern_poetry 537 │ materials 506 │ speedrun 484
math_synth 470 │ learning 443 │ kernelbench 441 │ argus_maintenance 313
nanogpt_speedrun 291 │ ale_last_exam 212 │ software 108
```

**`software` 只有 108 行**——这是"契约的最小实现"的参考样本。
**`research` 有 1.3 万行**——是 math 特化时最值得对照的重量级样本
（论文流水线、venue、literature grounding 全在里面）。

---

## 6. Stage machine：阶段怎么推进

`argus_skill/skills/stage_machine.py`。

**四个变更器**，全部只由 Manager 调用（`manager/_stage_ops.py:397-403` 一次性 import 三个）：

| 函数 | 行 | 是否过完成校验 |
|---|---:|---|
| `advance_stage` | 427 | ✅ 调 `_ensure_stage_completion` |
| `complete_final_stage` | 546 | ✅ 调 `_ensure_stage_completion` |
| `rollback_stage` | 474 | ❌ 不调 |
| `reset_stage_for_replacement_intent` | 520 | ❌ 不调 |

后两个不校验是**对的**：回退和换 vertical 不应该被"当前阶段没做完"卡住。

`_ensure_stage_completion`（:154-179）**fail closed**：

```python
except Exception as exc:  # noqa: BLE001 — completion authority fails closed
    raise StageCompletionError(stage, (f"completion validator unavailable: {exc}",)) from exc
```

即：vertical 的校验器**抛异常**会被当作"不通过"，而不是"放行"。写钩子时要意识到这点。

其他值得记的：
- `completion_contract_fingerprint`（:54）——把契约版本绑进认证，防止改了契约还复用旧认证。
- `resolve_stage_checklist_contract`（:784）+ `ChecklistLoadState`——checklist 的
  "种子 + 覆盖"合并语义（空的 stages 条目**不会**压掉 vertical 种子，见
  `tests/skills/test_math_vertical.py:302`）。
- `_ensure_stage_completion` 传的是 `project_root=Path(evidence_root or project_root)`（:166-169）——
  证据根可以与项目根不同。

---

## 7. 完成判定：三个不同的东西，别混

这是本仓库**最容易误读**的部分。三个概念常被当成一个：

### (a) `completion_gate`（vertical 声明）
取值 `none` / `metric` / `certified`。
**它是形状选择器，不是严格度旋钮。** 反直觉但确凿：

- `gate == "none"` 时，`life/supervisor/_planning_cycle_helpers.py:125-165`
  的 `_staged_goal_completion_issue` **要求一份 fingerprint 绑定的 Reviewer 终局阶段认证**。
- `gate == "certified"` 才会进入 `_lifecycle.py:179-204` 那条路径，
  而那条路径**额外**要求 `status.has_submission_artifact`（= `paper/main.pdf` 存在）。

所以把 math 从 `none` 改成 `certified` **不会让它更严**，只会让它开始要一篇论文 PDF。

### (b) completion source ranks（`core/project_api.py`）
`planner_verdict`(1) < `vertical_completion_certificate`(2) < `independent_certification`(3)；
gate rank：`none`(1) < `metric`(2) < `certified`(3)；`_UNKNOWN_GATE_RANK = 3`（fail closed）。

**这套 rank 阶梯在生产里从不拒绝任何东西**——唯一的生产调用点
（`_lifecycle.py:179-204`）把 source 硬编码成了 rank 3。它是给未来/外部调用者的防线。

### (c) `stage_completion_issues`（vertical 实现的钩子）
**这才是唯一能真正加严的地方**，而且改它**不需要动 core**。

> 要让 math 更严：加强 `stage_completion_issues` + `CHECKLIST_ITEMS`，并 bump
> `COMPLETION_CONTRACT_VERSION`。**不要碰 `completion_gate`。**

---

## 8. 验证策略：三个正交轴

`argus_skill/core/verification_policy.py`：

| 轴 | 取值 | 含义 |
|---|---|---|
| `ExplorationPosture` | `conservative` / `balanced` / `frontier` | 敢冒多大险 |
| `VerificationProfile` | `explore` / `develop` / `certify` | 验证到什么程度 |
| `research_target_level` | `exploratory` / `publishable` / `doctoral` | 结果要达到什么档次 |

关键函数：`normalize_posture`(:110)、`normalize_profile`(:115)、`profile_for_stage`(:120)、
`lowers_the_bar`(:137)、`resolve_policy`(:193)、`set_policy`(:265)、`policy_line`(:246)。

**已知的坑**：`STAGE_PROFILES`（:74-95）**只有 `research` 和 `kernel_engineering` 两张表**。
`profile_for_stage` 找不到时会去扫别的 vertical 的表作为回落；
`resolve_policy` 第 4 步最终返回 `profile="develop", source="unresolved", resolved=False`。

所以 **math 的 `solve` 阶段是"碰巧"工作的**：没有 `STAGE_PROFILES["math"]` →
`None` → unresolved 回落 → `develop` → 而 `develop` 恰好落在
`verticals/math/proof_graph.py:53` 的 `_PROFILES_REQUIRING_GRAPH = {"develop", "certify"}` 里。
这不是设计，是巧合——两个互不知情的默认值对上了。改 math 时应该显式补一张 `STAGE_PROFILES["math"]`。

`research_target_level` 的判定在 `core/research_contract.py`：
`normalize_research_result`、`research_completion_issue`、`resolve_research_target_level`。
`manager/stage_decider.py:final_stage_completion_decision` 是终局阶段的裁决器。

---

## 9. 证据模型与磁盘状态

### 9.1 四态证据

`argus_skill/core/evidence_status.py:92` `EvidenceContract`——**core 提供的库，
vertical 用自己的词汇去实例化**（不是 core 规定的枚举）。
维度：execution / idea / failure。核心规则在 :163-181：
执行没完成就不能有结论性的 idea 状态；`failure == "none"` 且执行未完成是非法组合；
`idea == "refuted"` 只能配 `contract.refuting_failures` 里的失败类型。

已有的采用样本：`verticals/research/idea_evidence.py`、`verticals/materials/stages.py`。
**math 采用它是零 core 改动的。**

### 9.2 全局根：`~/.argus-skill/`（可用 `ARGUS_SKILL_HOME` 覆盖）

`core/paths.py:61-135`：

```
~/.argus-skill/
├── identity.md          identity_path()
├── config.json          config_path()
├── skills/              shared_skills_root()      └─ _archive/
├── tools/               tools_root()
├── capabilities/        capabilities_root()
├── special_prompts/     special_prompts_root()
├── logs/                logs_root()
├── run/                 run_root()
├── projects/            session_states_root()     ← 每个 session 一个 fingerprint 目录
└── projects_trash/      session_trash_root()
```

`session_state_root(session_id)` 用 `_safe_component` 做路径注入防护
（拒绝空串、`.` 开头、含 `/` `\` `\0`）。

### 9.3 项目根：执行目录

`core/project.py:41` `resolve_project_root()`：显式参数 → `ARGUS_SKILL_PROJECT_ROOT` → `cwd`。
`project_fingerprint()`(:71) 产出 `ProjectIdentity`（12 字符 sha1 前缀，
来源标为 `git-remote` 或 `cwd-path`）——这就是 `projects/` 下的目录名。

**项目内的状态几乎都在 `<project_root>/research/`**：

| 文件 | 用途 |
|---|---|
| `research/PIPELINE_STATE.json` | 当前 vertical、stage、verification profile、research target。**最常读的一个**。 |
| `research/CHECKLISTS.json` | checklist store 的持久化（`{revision, vertical, stages:{...}}`）。 |
| `research/DOMAINS/` | Manager 运行时撰写的 data domain。 |
| `research/PROOF_GRAPH.json` | **math 专用**，证明图。 |
| `research/GROUND_TRUTH.md` | 被引用最多的证据文件（8 处）。 |
| `research/ROUTE_LEDGER.json` | ⚠️ **陷阱**，见 §11。 |

---

## 10. 想查某件事，从哪读起

| 问题 | 入口 |
|---|---|
| 「这个行为的规格是什么」 | **先读 `tests/`**。455 个测试文件是本仓库最可靠的规格。测试名往往就是一句完整的断言。 |
| 「一次任务怎么跑完」 | `life/supervisor/_core.py` 的 `run()` 与 `tick()`，再顺 §3 的链。 |
| 「角色说了什么」 | `roles/prompts/<role>.py`，不是 `<role>/`。 |
| 「vertical 能声明什么」 | `core/vertical_contract.py` 的 dataclass 字段 + `verticals/_base.py` 的访问器。 |
| 「阶段怎么变」 | `skills/stage_machine.py` 的四个变更器 + `manager/_stage_ops.py`。 |
| 「什么算完成」 | 分清 §7 的 (a)(b)(c) 三层。 |
| 「Manager 怎么选 vertical」 | `skills/vertical_select.py` + `manager/_vertical_ops.py` + `manager/domain_author.py`。 |
| 「一个最小 vertical 长什么样」 | `verticals/software/`（108 行）。 |
| 「一个重量级 vertical 长什么样」 | `verticals/research/`（12954 行）。 |
| 「Lean 怎么检查」 | `tools/lean_check.py`（完整、fail-closed）+ `tools/lean_axiom_audit.lean`。 |
| 「成本/预算」 | `core/cost_control.py`、`core/cost_events.py`、`core/pricing.py`、`life/supervisor/_cost.py`。 |
| 「事件流」 | `core/event_catalog.py`（`EventType`）+ `core/event_payload_schemas.json` + `life/event_log.py`。 |

---

## 11. 已知陷阱清单（踩过的坑，别再踩）

1. **`STAGE_CHECKS` 是死的。** 被校验但不执行。名字带 "RUN TIME" 的测试是**测试自己**在跑那些命令。
2. **`completion_gate` 不是严格度旋钮。** 见 §7。这是最贵的一个误解。
3. **rank 阶梯在生产里从不拒绝。** 唯一调用点硬编码 rank 3。
4. **`research/ROUTE_LEDGER.json` 是幻影。** math 的两个 skill `.md`
   （`skills/planner/math-research-planning.md:14`、`skills/engineer/math-research-execution.md:22`）
   指示角色去读它，但**整个仓库没有任何 Python 代码读或写这个路径**
   （`grep -rn ROUTE_LEDGER --include=*.py` 只命中 `tests/test_math_objective_and_graph.py:333`，
   而那一行断言的是 **prompt 文本里出现了这个字符串**，不是文件被使用）。
   同期的 `failure_layer` 字段已被移除，`tests/test_reviewer_completion_contract.py:36`
   与 `tests/core/test_review_event_payload.py:32` 都断言它**不在** review payload 里。
   **prompt 指令与运行时现实脱节的活标本，也是"测试断言的是 prompt 说了什么、
   而不是系统做了什么"的活标本。**
5. **`scientist/*.md` 不会自动加载。** 见 §4 的两条投递路径。
6. **math 的 `solve` 阶段靠回落巧合工作。** 见 §8。
7. **只 grep 契约字段名会漏消费者。** 有 7 个包装方法。
8. **`tests/skills/test_math_vertical.py:105-130` 断言了 math 目录下的精确 11 文件集合。**
   往 `verticals/math/` 加任何文件都会红。这是刻意的护栏（"math 保持轻"），
   加文件时必须同步改这个断言，并在 commit 里说明理由。
9. **`_with_protected_floor` 会与 vertical 自己的种子求交**（`skills/checklist_store.py:206-265`）。
   所以换 gate 不会让 math 长出幽灵 paper 条目——反过来说，也别指望共享底线会自动帮你加严。

---

## 12. 与另外两篇的分工

| 文档 | 回答什么 | 什么时候读 |
|---|---|---|
| `math-docs/REPO_ORIENTATION.md`（本篇） | **在哪、怎么走** | session 开头 |
| `math-docs/DESIGN_PHILOSOPHY.md` | **为什么这么设计**、不可破坏的不变量、已知设计缺陷（endogenous harnessing） | 要动结构、要加判断逻辑之前 |
| `math-docs/VERTICAL_BOUNDARY.md` | **math 能改什么、不能改什么**（五分类：vertical 自由 / 有 core 钩子 / 要改 core / core 不变量 / 死代码） | 开始写 math 改动之前 |

`docs/` 下的原有文档保持独立：`FEATURES.md`（运行流程）、`ROLE_SESSIONS_AND_SKILLS.md`、
`RESEARCH_AGENCY_AND_VERIFICATION_TODO.md`、`backend-providers.md`、`technical_report/`。

---

## 附：本文的验证方式与保鲜

- 目录/行数：`find argus_skill -name '*.py' | wc -l`、逐子包 `cat | wc -l`（2026-08 快照）。
- 调用链：对 `LifeSupervisor`、`SkillLoop`、`SupervisedEngineer`、`Reviewer`
  逐个 grep 实例化点确认，非推测。
- 死代码判定：对每个符号在 `argus_skill/` 内 grep 消费者，排除定义文件本身
  （**这一步我曾漏掉，导致误判 `evaluate_request` 无调用者——它由 `roles/prompts/reviewer.py:313` 调用**）。
- 字段数：对 `VerticalContract` 做 dataclass 内省，不是数源码行。

**保鲜建议**：改动 `core/vertical_contract.py`、`skills/stage_machine.py`、
`core/verification_policy.py`、`life/supervisor/_planning_cycle_helpers.py`、
`life/supervisor/_lifecycle.py` 这五个文件之一时，回来核对本文 §5–§8。
其余部分对重构相对稳健。
