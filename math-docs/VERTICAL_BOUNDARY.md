# Vertical 扩展边界：改 math 之前先看这份

**这份文档回答一个问题**：给 math vertical 加东西时，哪些面是我自己的，哪些是 core 的，
哪些看起来能用但其实是死的。

本文所有结论都是**在 main 上逐条验证过的**（读源码 + 运行时求值），不是从设计文档推断的。
每条都给出可自查的符号名与调用点。`math-docs/DESIGN_PHILOSOPHY.md` 讲**为什么**是这些边界，
本文讲**边界具体在哪一行**。

**权威顺序**：代码与测试 > 本文 > 设计叙述。本文若与 main 冲突，以 main 为准，并请修正本文。

---

## 0. 一页速查

| 分类 | 含义 | 改动成本 |
|---|---|---|
| 🟢 `vertical-owned-free` | 完全在 `verticals/math/` 内，改了不影响别人 | 随便改 |
| 🔵 `core-hook-no-core-edit` | core 已经开好的插槽，vertical 填实现即可 | 只改 vertical |
| 🟡 `requires-core-edit` | 必须动 `verticals/math/` 之外的文件 | 需评估爆炸半径 |
| 🔴 `core-invariant-do-not-touch` | 动了就破坏系统的诚实性保证 | 绕开设计，不要改 |
| ⚫ `dead-do-not-rely` | 声明了、被校验、但运行时**没有任何消费者** | 写了等于没写 |

**最重要的三条**（下面各有详述）：

1. ⚫ **`STAGE_CHECKS` 在运行时从不执行。** 想加 Lean 机器验证却写进 `STAGE_CHECKS`，
   等于什么都没做。唯一活着的确定性 gate 是 `stage_completion_issues`。
2. 🔵 **`stage_completion_issues` 是 math 唯一的强制执行钩子，且 fail-closed。**
   几乎所有你想要的机器化验证都应该挂在这里，**零 core 改动**。
3. 🟡 **`completion_gate` 不是严格度旋钮，是形态选择器。** 把 math 从 `"none"` 改成
   `"certified"` 会让它变成**论文投稿型 vertical**，而不是"更严格的 math"。见 §4。

---

## 1. 契约的全貌：core 到底开了哪些插槽

`argus_skill/core/vertical_contract.py` 的 `VerticalContract` 有 **21 个字段、1 个派生属性
（`assurance_level`）、7 个包装方法**。core 用 `getattr` 从 provider 上鸭子类型地取，
`vertical_contract()` 一次性校验。

下表逐字段追查消费者（`name` 除外，它只是身份）。"活"= 在 `argus_skill/` 里
（非测试、非 vertical 自身）有真实读取点。注意有些字段的读取发生在包装方法里
（`contract.completion_issues()` 而不是 `contract.stage_completion_validator`），
所以直接 grep 字段名会漏。

| 契约面 | provider 属性 | 状态 | 真实消费点 |
|---|---|---|---|
| `stage_completion_validator` | `stage_completion_issues(stage, root)` | 🔵 **活，且是主力** | `skills/stage_machine.py:154` |
| `planner_task_validator` | `planner_task_issues(stage, root, task)` | 🔵 活 | `life/supervisor/_planning_cycle_enqueue.py:334` |
| `role_guidance` | `role_banner(role)` | 🔵 活 | `roles/prompts/registry.py:75` |
| `search_altitude` | `search_altitude_context(root)` | 🔵 活 | `roles/prompts/registry.py:132` |
| `mission_prelude` | `prepare_mission(stage, root, state_root)` | 🔵 活 | `life/supervisor/_mission_execution_runtime.py:100` |
| `library_preparer` | `LIBRARY_PREPARER(ctx)` | 🔵 活 | `skills/loop_skill_library.py:39` |
| `stage_order` / `checklist_items` | `CHECKLIST_STAGE_ORDER` / `CHECKLIST_ITEMS` | 🟢 活 | 到处 |
| `completion_gate` | `completion_gate` | 🟡 活，语义见 §4 | 9 处 |
| `workflow_mode` | `WORKFLOW_MODE` | 🟢 活 | 16 处 |
| `mission_kind` | `MISSION_KIND` | 🟢 活 | 3 处 |
| `requires_independent_review` | `REQUIRE_INDEPENDENT_REVIEW` | 🟢 活 | `apps/_runtime_supervisor.py:80` 等 |
| `completion_contract_version` | `COMPLETION_CONTRACT_VERSION` | 🟢 活，见 §4.2 | `stage_machine.py:574` 等 |
| `research_target_levels` | `RESEARCH_TARGET_LEVELS` | 🟢 活 | `skills/vertical_select.py:555` |
| `ground_before_handoff` | `GROUND_BEFORE_HANDOFF` | 🟢 活 | `manager/_vertical_ops.py:353` |
| `checklist_optional_stages` | `CHECKLIST_OPTIONAL_STAGES` | 🟢 活 | 契约校验 + `assurance_level` |
| `stage_aliases` | `STAGE_ALIASES` | 🟢 活 | `stage_machine.py` 归一化 |
| **`stage_checks`** | **`STAGE_CHECKS`** | ⚫ **死** | 见 §2 |
| **`stage_primary_deliverables`** | **`STAGE_PRIMARY_DELIVERABLES`** | ⚫ **死** | `_base.py` 有 accessor，**无人调用** |
| **`evidence_schema`** | **`EVIDENCE_SCHEMA`** | ⚫ **死** | 全仓零读取点 |
| **`assurance_level`**（属性） | — | ⚫ **死** | 只有 `tests/core/test_vertical_contract.py` |

另外：**`REVIEWER_CHECKLISTS` 根本不在契约里**。`vertical_contract()` 从不读它，
`argus_skill/` 里（vertical 自身之外）零消费者。math 的 `stages.py:69-89` 写了一份，
它只是给人看的文档。

> 教训：这份表本身就是 §5 反模式的证据。已经有四个面走完了"声明 → 校验 → 从没被消费"
> 的全程。**加新契约槽之前，先确认调用点会被写出来。**

---

## 2. ⚫ `STAGE_CHECKS` 是死的 —— 这条最容易踩

`STAGE_CHECKS` 是 `{stage: [(描述, shell 命令)]}`，看起来完全像"每个 stage 的机器门禁"。
28 个 vertical 里有十几个认真填了它。**运行时没有任何东西执行这些命令。**

验证方式：在 `argus_skill/` 中搜索 `stage_checks` / `STAGE_CHECKS`，
排除 `verticals/` 之后只剩 `core/vertical_contract.py` 自己——它校验形状
（:232-263：必须是 dict、stage 必须已知、每项必须是非空 label-command 二元组），
存进 dataclass，然后**唯一的读取者是 `assurance_level`（:64），而 `assurance_level`
自己也没有生产消费者**。

那些 `tests/test_fiction_writing_*.py`、`test_prose_runtime.py` 之类名字里带 "RUN TIME" 的
测试，是**测试自己**用 subprocess 跑那些命令。那是测试期保证，不是运行期保证。

**对 math 的含义**：`math/stages.py:29` 声明了三个 stage 各一条
`test -f research/PIPELINE_STATE.json`。这条从来没跑过。把 Lean 编译放进 `STAGE_CHECKS`
不会有任何效果。

同理，`STAGE_PRIMARY_DELIVERABLES`、`EVIDENCE_SCHEMA` 也不要指望。

---

## 3. 🔵 `stage_completion_issues`：math 唯一活着的强制点

这是**你应该把机器化验证放进去的地方**，而且完全不需要动 core。

**调用链**（全部已存在）：

```
manager/_stage_ops.py:396-450   ← 唯一的生产调用者，Manager-only
  └─ skills/stage_machine.py:458  advance_stage()
  └─ skills/stage_machine.py:567  complete_final_stage()
       └─ _ensure_stage_completion()            stage_machine.py:154
            └─ vertical_stage_completion_issues()  verticals/_base.py:171
                 └─ contract.completion_issues()   core/vertical_contract.py:89
                      └─ math.stages.stage_completion_issues()   ← 你的代码
  返回非空 issues → raise StageCompletionError
       → _stage_ops.py:412/432 捕获 → hold，source=stage_completion_gate_hold
```

**Fail-closed**：`stage_machine.py:172-178` 把 validator 抛出的**任何**异常包成
`StageCompletionError("completion validator unavailable: ...")`。校验器崩了不等于放行。

**必须知道的三个约束**：

1. **没有超时保护。** `_ensure_stage_completion` 自己不设超时。如果在这里调 Lean 编译，
   **必须自己传 `timeout_seconds`**，否则一个挂死的编译器会卡住 Manager tick。
2. **传进来的是执行 workdir，不是 state root。** `stage_machine.py:166-169` 用的是
   `Path(evidence_root or project_root)`。解析 Lean 源码路径要相对这个参数。
3. **只在 advance / complete 上触发，不在 rollback 上触发。**
   `rollback_stage` (:474) 和 `reset_stage_for_replacement_intent` (:520) **不**调用它——
   这是对的（回滚不该被它要修的门禁挡住），但意味着你的 gate **无法主动"撤销"任何推进**。
   它只能拒绝前进。

**math 现在已经在用它**（`stages.py:34`）：校验 objective 身份 + PROOF_GRAPH。
加一个 Lean oracle 就是在这个函数里多几行 + `from ...tools.lean_check import run_lean_check`。

### 3.1 `argus_skill/tools/lean_check.py` 已经存在，而且没被 math 用

一个完整的、fail-closed 的 Lean 检查器已经在仓库里（`tools/lean_check.py`，24KB），
状态是 `success | proof_hole | syntax_error | type_error | timeout | unavailable`，
**`unavailable`（PATH 上没有 lean/lake）不算 success**——这正是把它当 oracle 用所需要的语义。

**`verticals/math/` 从来没有 import 过它。** 唯一的引用是
`tests/skills/test_math_vertical.py:239`，而且是在断言 `"lean_check.json"` 这个字符串
**不出现**在 checklist 文案里。

调用它是 🟢 自由的——vertical import `argus_skill.tools.*` 是既有模式
（`verticals/research/figure_tool.py:31` 等）。**修改**它是 🟡（共享 `tools/` 包），
`tests/tools/test_lean_check.py` 钉死了状态集、产物名（`Main.lean`、`compile.log`、
`lean_check.json`、`statement_fidelity.md`）、原子写与拒绝符号链接的行为。

---

## 4. 🟡 `completion_gate`：不是严格度旋钮

这是本文档最容易被误读的一点，务必读完。

朴素读法是：`core/project_api.py` 有一个 rank 阶梯，`none`=1 < `metric`=2 < `certified`=3，
所以 math 的 `completion_gate = "none"` 意味着"最弱，一个 Planner 裁决就能完成"，
把它改成 `"certified"` 就"更严格"。

**这个读法是错的，两头都错。**

### 4.1 rank 阶梯在生产中从不拒绝任何东西

`evaluate_completion` / `complete_project` 在 `argus_skill/` 里**只有一个生产调用者**：
`life/supervisor/_lifecycle.py:190-204`，而它**硬编码传 `SOURCE_INDEPENDENT_CERTIFICATION`（rank 3）**。
rank 3 满足任何 gate。所以那个阶梯今天不会挡下任何东西。

更关键：那个分支的进入条件是
`_effective_final_certification_gate(...)`（`_planning_context.py:342-375`），
它**当且仅当 `completion_gate == "certified"` 时返回 True**。

> **所以对 math（gate=`"none"`）而言，`complete_project` 这条路径根本不会被走到。**
> 项目级 `ProjectState.DONE` 对 math 目前不可达——同一分支还要求
> `status.has_submission_artifact`，而它的定义是 `paper/main.pdf` 存在
> （`life/project_lifecycle.py:449`）。

### 4.2 `"none"` 实际上要求一份 Reviewer 签发、指纹绑定的 stage 证书

反直觉的部分在 `life/supervisor/_planning_cycle_helpers.py:125-165`：

```python
if vertical_completion_gate(module) != "none":
    return ""                      # ← certified 的 vertical 从这里直接走掉
...
if ... vertical_has_current_completion_certificate(project_root, vertical):
    return ""
return f"{vertical} final-stage Goal Gate is not Reviewer-certified (...contract=v1:<sha>)"
```

也就是说：**`"none"` 这条路要求最终 stage 有一份当前有效的 Reviewer 认证**，
并且因为 math 声明了 `COMPLETION_CONTRACT_VERSION = 1`，这份认证被
`completion_contract_fingerprint` 绑定到 checklist 内容上——**改了 checklist，旧认证自动失效，
必须重新认证一次**（`skills/vertical_select.py:705-740`）。

这比"Planner 说一声"强得多。

### 4.3 结论

| 你想要的 | 该怎么做 |
|---|---|
| 让 math 的完成更难 | **不要动 `completion_gate`。** 加强 `stage_completion_issues` + `CHECKLIST_ITEMS`，并 bump `COMPLETION_CONTRACT_VERSION` |
| 让 math 变成投稿型 | 改成 `"certified"`——但这同时打开论文任务类型判定（`_runtime_supervisor.py:60`）、full-submission checklist 标题（`stage_machine.py:985`）、venue 指引等整条论文流水线 |
| 表达"由证明图证明达成" | 现有三个 gate 名表达不了。加第四个值需要改 `core/vertical_contract.py:14` 的 `_COMPLETION_GATES` **和** `core/project_api.py:58` 的 `_GATE_REQUIRED_RANK` —— 🟡，且影响全部 28 个 vertical |

**一处需要澄清的细节**：把 gate 改成 `"certified"` 会让
`skills/checklist_store.py:227` 并入 `_SHARED_PROTECTED_ITEM_IDS`（`submission.anonymous` 之类
论文反造假条目）。但 `_with_protected_floor` (:249) 把这个集合**与 vertical 自己的 seed 求交**
（`seed_items_for(project_root, stage)`），所以 math 不会凭空长出论文条目。
真正的影响是上面那张表里的其它 8 个调用点，不是幻影 checklist 项。

---

## 5. 🟡 `STAGE_PROFILES`：math 现在是靠意外工作的

`core/verification_policy.py:74-95` 的 `STAGE_PROFILES` **只有 `research` 和
`kernel_engineering` 两张表**。运行时实测：

```
profile_for_stage('scope',  'math') -> 'explore'    # 从 kernel_engineering 表泄漏过来
profile_for_stage('solve',  'math') -> None         # 两张表都没有
profile_for_stage('review', 'math') -> 'certify'    # 从 research 表泄漏过来
```

`profile_for_stage` (:126-134) 在 vertical 无表时会**遍历所有其它 vertical 的表**去猜。
`solve` 猜不到 → `resolve_policy` 落到第 4 步 unresolved 分支（:234-243），
返回 `profile="develop", resolved=False`。

而 `math/proof_graph.py:53` 的 `_PROFILES_REQUIRING_GRAPH = {"develop", "certify"}`。
**所以 `solve` 阶段要求证明图，纯粹是 unresolved 兜底默认值恰好等于 `develop` 的结果。**

`resolved=False` 这个事实除了 `policy_line` 里加一个 `" (unresolved)"` 后缀之外，
没有任何地方消费。

**要改**：给 `STAGE_PROFILES` 加 `"math"` 键是 🟡（core 文件），但是**纯增量**，
不改变 `research`/`kernel_engineering` 的解析。**注意**：一旦加了表，
`scope` 和 `review` 会走你的表而不是泄漏值——如果你的表和现在的泄漏值不一致，
math 在这两个 stage 的行为会变。

---

## 6. 🔴 不要碰的不变量

### 6.1 core 永不 import 具体 vertical（AST 强制）

`tests/core/test_vertical_contract.py:159-171` 用 `ast` 解析 `argus_skill/core/` 下每个
`*.py`，断言没有任何 `from ...verticals...` 或 `import ....verticals...`。它会走完整 AST，
**函数内的延迟 import 也抓得到**。

精确范围：只管 `argus_skill/core/`；用的是 `core.glob("*.py")`，**不递归**
（`core/mission_view/` 下的 10 个文件不在其内）；不限制 `skills/`、`life/`、`manager/`。

**后果**：oracle 永远不能写成 core 里的 `if vertical == "math": run_lean_check(...)`。
需要跨领域的东西放 `verticals/_base.py` 或 `skills/stage_machine.py`——那是合法的桥接层。

### 6.2 降低验证标准需要 operator 确认

`core/verification_policy.py:265-321`：提高标准立即生效，**降低标准**
（`PROFILE_ORDER: explore < develop < certify`）抛 `PolicyConfirmationRequired`，
除非 `confirmed=True`。`final_submission` scope 强制 `certify` 且无法覆盖（:219-220）。

**设计时避开**：不要让 agent 能通过写 `verification_profile` 关掉 oracle；
不要让 agent 自己写的文件（比如证明图内容）去选择 profile。
注意 `resolve_policy` 第 2 步——一个 operator 设定的 `explore` 会**整个关掉**
math 的证明图要求。这是有意的 operator 权威，但你的新设计要清楚这条旁路存在。

平行的不变量在 vertical 侧：`math/objective_mode.py:113-124`，
targeted 模式必须有显式 goal，未设定的 mode 是**被报告**而不是被猜测。

### 6.3 stage 证书由 host 写，vertical 只能读

`core/stage_certificate.py` 的 `stage-certificates.json` **只由** host supervisor 在独立
Reviewer 返回 `done` 之后写入（`life/supervisor/_mission_execution_settlement.py:205-227`），
写到 `state_root = self.memory.root`——一个**在 agent 可写的执行 workdir 之外**的目录，
并内嵌 `completion_contract_fingerprint`。

这正是"agent 伪造不了的裁决"原语。**设计成消费它，永远不要试图产生它。**

同理 `core/external_completion_gate.py`：docstring 写明
"Argus may read the aggregate gate, but must never manufacture or edit it"，
且模块**不提供写入器**。

### 6.4 stage 状态只有 Manager 能改

`advance_stage` / `rollback_stage` / `reset_stage_for_replacement_intent` /
`complete_final_stage` 四个 mutator，唯一生产调用者是 `manager/_stage_ops.py`。
Reviewer / Planner 只能建议，Engineer 从不编辑 stage 状态。

---

## 7. 🟢 完全自由的面

这些改起来没有任何外部影响：

- **`proof_graph.py` 全部**：节点状态词表、AND/OR 策略层、`GapReport`、frontier 计算、
  `validate()` 规则。core 对证明图一无所知。
- **`proof_graph_check.py` CLI**。
- **`objective_mode.py`**：targeted/exploratory 的判定与 `PIPELINE_STATE.json` 里的
  `math_objective_mode` / `math_goal` 字段。core 不校验 `PIPELINE_STATE.json` 的未知键。
- **`CHECKLIST_ITEMS` 的措辞与结构**、**`PROTECTED_ITEM_IDS`**
  （`checklist_store.py:224` 原样读取 vertical 声明的 id）。
- **六个 `skills/*.md` 的内容**。
- **`STAGE_ORDER`** 的增删改（只要 `CHECKLIST_ITEMS` 跟着覆盖，见 `vertical_contract.py:167-185`）。
- **🟢 采用四态证据模型**：`core/evidence_status.py` 的 `EvidenceContract` 是一个
  **core 提供、vertical 实例化**的库。`kernel_engineering/attempt_outcome.py:51` 和
  `research/idea_evidence.py:76` 各建一份自己的词表；`materials/stages.py:53` 把自己的
  `validate_evidence` 接进 `stage_completion_issues`。**math 可以照做，零 core 改动**——
  这是把"环境失败 ≠ 想法被否证"引入 math 的现成路径。

### 7.1 但有一个例外：新增文件会挂掉一个测试

`tests/skills/test_math_vertical.py:105-130` 对 `verticals/math/` 做 `rglob` 并断言
**文件集合完全相等**（11 个文件，硬编码）。新加 `verticals/math/lean_oracle.py`
会让这个测试红——测试文件在 `tests/skills/`，所以严格说这不是"纯 vertical 内改动"。

这个断言不是偶然的。它上面的注释把现有三个辅助模块称为"narrow exception"，
理由是"they measure; they do not add stages, roles, or required paperwork"。
**新模块要么符合这个理由，要么就该说服人修改这条断言。**

同一文件里 `test_math_checklist_is_small_and_judges_results_not_files` 还断言
`"Main.lean"` / `"compile.log"` / `"lean_check.json"` / `"statement_fidelity.md"`
**不出现**在任何 checklist 文案里——checklist 判结果，不判文件是否存在。

---

## 8. 🟡 要改 core 才能做到的事（按代价排序）

如果你的设计需要下面任何一条，**先讨论再动手**。

| 想做的事 | 必须改的文件 | 爆炸半径 |
|---|---|---|
| 给 `STAGE_PROFILES` 加 math 表 | `core/verification_policy.py` | **小**，纯增量。但会改变 math 在 `scope`/`review` 的现有泄漏行为 |
| 让 Reviewer 能声明"每个节点的证明裁决" | `reviewer/_parsing.py:290-308` 的 `_VERDICT_KEYS`（18 个键的固定元组） | **大**。25+ 个测试。**没有任何 vertical 钩子能扩展它**——math skill 里写 `PROOF_NODE_VERDICT=...` 会被静默丢弃 |
| 把 Reviewer 裁决写回 `PROOF_GRAPH.json` | 需要新的 core writer（`life/context_packet.py`）或新的通用 review sink 钩子 | **大**。今天只有 core 代码持久化 `ReviewDecision`，且没有 per-round 的 vertical 钩子 |
| 扩展 `research_result` 词表 | `core/research_contract.py:11-30` 的 `RESULT_CLASSES` | **大**。驱动所有 research 型 vertical 的完成判定。注意：`lean_local_verification` **已经**是一个 class（:22），但没有任何东西把它和真实的编译结果对账 |
| 让 oracle 否决 Reviewer 的条目级判定 | `manager/stage_decider.py` `_review_certifies_completion` | **大**，且当前无钩子——:298 是 `_ = (vertical, mission_scope, checklist_contract)`，即 vertical 名和 checklist 契约**被接收后直接丢弃**。28 个 vertical 共用。**强烈建议不要**：`complete_final_stage` 已经会调 `_ensure_stage_completion` |
| 加新的契约槽（如 `ORACLE_*`） | `core/vertical_contract.py` dataclass + probe + `_base.py` accessor + 调用点 | **大**，且 §1 已证明这类槽有很高概率变成第五个死面。**强烈建议不要** |
| 加第五个常驻角色 | `roles/prompts/types.py:10` 的 `RoleName`（4 个成员） | **大**。见 `DESIGN_PHILOSOPHY.md` §「不要为了承载一个能力而发明一个角色」 |

### 8.1 关于 role skill 的一个精确事实

math 的六个 `.md` 通过**两条不同的路**到达角色，不要混淆：

1. **`role_banner()` → 逐字注入 prompt。** `math/stages.py:204-223` 的 dict 里，
   只有 `manager` / `planner` / `engineer` / `reviewer` 四个会被走到，因为
   `banner_role` 默认取 `request.role.value`（`registry.py:52`），而
   **`argus_skill/` 里没有任何代码传 `banner_role=`**。
   四个常驻角色都确实拿到了 banner（Reviewer 经
   `roles/prompts/reviewer.py:313` 的 `evaluate_request`）。
2. **skill store 播种。** `skills/builtins.py:92` 的 `iter_vertical_skill_texts` 会遍历
   `verticals/math/skills/**`，六个都在内。但它唯一的生产入口是
   `apps/cli/_core.py:1222`，挂在 **operator CLI flag `--export-builtin-skills`** 上，
   不是 daemon 自动步骤。

**所以 `scientist/math-research-distillation.md` 和 `scientist/math-research-adaptation.md`
在默认运行路径上不会被加载。** 它们不是死文件（路径 2 可达），但也不是自动生效的。

---

## 9. math 现状的已知不一致

改之前应该先修或先决定忽略的：

1. **`STAGE_CHECKS` 是装饰。** 三条 `test -f research/PIPELINE_STATE.json` 从不执行（§2）。
2. **`solve` 的验证 profile 未解析。** 靠兜底默认值恰好为 `develop` 才让证明图生效（§5）。
3. **prompt 引用了不存在的文件。** `math/skills/engineer/math-research-execution.md:22` 与
   `planner/math-research-planning.md:14` 让角色去读 `research/ROUTE_LEDGER.json`——
   **没有任何 Python 代码读或写这个文件**（`grep -rn ROUTE_LEDGER --include=*.py` 全仓库
   只命中 `tests/test_math_objective_and_graph.py:333`，而那行断言的是 prompt 文本里
   出现了这个字符串，不是文件被使用）。同期的 `failure_layer` 字段也已消失：
   `core/failure_layer.py` 在 main 上**不存在**，且 `tests/test_reviewer_completion_contract.py:30-44`
   与 `tests/core/test_review_event_payload.py:32` 明确断言 `failure_layer` 已从
   `ReviewDecision.to_event_payload()` 中**移除**。
4. **Lean oracle 存在但未接线。** `tools/lean_check.py` 完整可用，math 从不 import（§3.1）。
5. **`REVIEWER_CHECKLISTS` 不在契约内。** `stages.py:69-89` 那份只是给人看的。
6. **technical report 的 Erdős–Gyárfás 证据早于 proof graph。**
   `proof_graph.py` 落在 `39104b4e`（2026-08-07），report 的 erdos_trace 证据冻结在
   `5aeb94a0`（2026-08-06）。**论文里的 math 证据并没有展示当前这套进度度量机制。**

---

## 10. 推荐的改动顺序

按"先零 core 改动，再评估 core"排：

1. **接线现有能力**：把 `tools/lean_check.py` 接进 `stage_completion_issues`
   （记得传 timeout，记得用 `evidence_root`）。修 §9.3 的死引用。—— 全部 🟢/🔵
2. **引入证据模型**：照 `research/idea_evidence.py` 建一份 math 的 `EvidenceContract`。—— 🟢
3. **收紧完成条件**：改 `CHECKLIST_ITEMS` + bump `COMPLETION_CONTRACT_VERSION`
   （强制重新认证）。**不要动 `completion_gate`。**—— 🟢
4. **补 `STAGE_PROFILES["math"]`**：让 `solve` 的严格度是被决定的而不是被兜底的。
   —— 🟡 小
5. **只有在 1-4 都不够时**，才讨论 `_VERDICT_KEYS` / review sink 钩子这类改动。—— 🟡 大

> 每一步做完先问：**这个判断该由 harness 做，还是该由 agent 做？**
> 如果你正要往 Python 里写一个阈值，答案通常是后者。见 `DESIGN_PHILOSOPHY.md` §4。

---

## 附：本文的验证方法

结论来自：读 `core/vertical_contract.py` 全文；对 20 个契约字段逐个 grep 消费者；
运行时求值 `load_vertical_contract("math")` 与 `profile_for_stage`；
读完 `stage_machine.py` 的四个 mutator 与 `_ensure_stage_completion`；
追 `evaluate_completion` / `complete_project` 的**唯一**生产调用者；
读 `_effective_final_certification_gate` 与 `_staged_goal_completion_issue` 的分支条件；
以及逐条核对 `tests/core/test_vertical_contract.py`、`tests/skills/test_math_vertical.py`、
`tests/skills/test_checklist_store.py` 的断言。

重新核对时，用符号名搜索而不是行号——行号会漂。
