# Argus Impressive Results — Candidate List

> 目标：用 Argus 真正做出一批外部可验证、值得展示的结果。
>
> 计划、跑通 demo、内部 checker 变绿，都不能直接算 impressive result。
> 只有结果、复现材料和独立验证都齐了，才能从候选清单进入正式结果清单。

## 什么结果可以收录

至少满足下面这些条件：

- **结果本身有分量：** 明显性能提升、真实榜单名次、上游采用、可用系统，或被独立核验的数学证明/反例。
- **比较公平：** 固定 baseline、硬件、输入、精度、版本和计分方法，不只挑一个最好看的 shape。
- **可以复现：** 有环境、命令、原始结果、补丁/代码、失败记录和已知限制。
- **有独立检查：** Reviewer 复核；重要性能结果做重复测量；数学结果需要独立专家或形式化验证。
- **确实由 Argus 推进：** 保留 session、任务轨迹、关键假设、代码改动和 Reviewer 结论；人工贡献单独写清楚。
- **不夸大：** 外部参考结果不能写成 Argus 的结果，单机单 shape 结果不能写成通用结论。

### 状态

- `candidate`：只有方向，尚未建立可靠 baseline。
- `active`：已有可运行任务和测量协议。
- `certified`：内部重复测量和独立 Reviewer 已通过。
- `externally-verified`：上游、榜单、外部复现或独立专家已确认。
- `shipped`：已经进入可使用的代码、产品或公开成果。
- `retired`：证据表明不值得继续；保留负面结果和原因。

## 候选总览

| ID | 方向 | 当前状态 | 主要平台 | 进入正式结果清单的关键条件 |
| --- | --- | --- | --- | --- |
| ARGUS-IR-01 | Sol-Engine / Sol-Attn 优化 | `candidate` | B200、H100 | 有代表性 workload 上的可复现提升，并形成可用 patch/PR |
| ARGUS-IR-02 | FLA `chunk_kda` 泛化与上游闭环 | `active` | B200、H100 | 补齐 D128 与 H100 数据，完成 combined N>=10，回应上游 review |
| ARGUS-IR-03 | MiniMax Speedrun 刷榜 | `candidate` | B200、H100 | 冻结公开计分协议并取得可复现榜单成绩 |
| ARGUS-IR-04 | Fast MiniMax-H3：从数据中心到桌面 | `candidate` | DGX Spark、RTX 5090 | 基于原始 33B checkpoint 独立复现或超过参考结果 |
| ARGUS-IR-05 | W2A4 GEMM 算子 | `candidate` | B200、H100、RTX 5090 | 在真实模型 shape 上超过强 baseline，并带来端到端收益 |
| ARGUS-IR-06 | Erdős 猜想证明或反例 | `exploration` | CPU/GPU + proof tooling | 明确问题、完整证明或最小反例，并通过独立核验 |

---

## ARGUS-IR-01 — 优化 Sol-Engine / Sol-Attn

**目标**

用 Argus 优化 Sol-Engine 中的 attention 路径，重点看 Sol-Attn、sparse attention、
kernel launch、访存和跨 step 可复用状态，最终形成可复现 patch 或上游 PR。

**先固定**

- 仓库、commit、模型 checkpoint 和 workload。
- B200/H100 的软件栈、精度、batch、序列/分辨率和计时范围。
- 正确性、输出质量、显存和端到端基线；不能只测 isolated kernel。

**待做**

- [ ] 在 B200 和 H100 上复现原始 Sol-Engine / Sol-Attn baseline。
- [ ] 用 profiler 找出 attention 主耗时、launch 开销、HBM round-trip 和稀疏路径浪费。
- [ ] 分别尝试 kernel fusion、稀疏 attention 实现、layout/tiling、cross-step caching 和调度优化。
- [ ] 每个改动同时记录 kernel microbenchmark、端到端延迟、吞吐、显存和质量差异。
- [ ] 对有效改动做消融，说明收益来自哪里，不能只提交一包无法解释的组合优化。
- [ ] 在一组有实际意义的 shape/workload 上重复测量，不用单个 cherry-picked case 做标题。
- [ ] 整理最小 patch、复现脚本和 upstream issue/PR。

**完成标准**

- B200/H100 至少一个平台有稳定、重复可见的端到端提升；
- 正确性、质量和显存没有未解释回退；
- 结果可由另一台机器复现；
- 代码进入上游评审，或形成维护成本清楚的独立实现。

---

## ARGUS-IR-02 — FLA `chunk_kda`：补齐 D128/H100 并推动上游

**已有 Argus 结果**

Argus 已在 FLA `chunk_kda`、B200、`B8_T1024_H8_D64` 上完成：

- component stack 的 **N>=10 +17.66%**；
- combined 单次冻结验证 **+29.93%**；
- correctness PASS，memory-neutral；
- 已提交 [`fla-org/flash-linear-attention#1054`](https://github.com/fla-org/flash-linear-attention/pull/1054)，尚未合并。

完整证据在：
[`technical_report/evidence/fla_kernel_optimization/README.md`](technical_report/evidence/fla_kernel_optimization/README.md)。

**当前缺口**

上游 maintainer 已明确指出：D64 实际代表性有限，还需要 D128（例如 H32/H64）和 H100
数据。现有结果只能说明一个 B200 D64 shape，不能写成 KDA 的通用加速。

**待做**

- [ ] 把现有 patch rebase 到 FLA 当前可评审基线。
- [ ] 在 B200 上补 `D=128`、H32/H64 等实际 shape。
- [ ] 在 H100 上跑相同 correctness、latency、memory 协议。
- [ ] 对 combined stack 做完整 N>=10 paired certification 和 cleared-cache repeat。
- [ ] 分别报告 forward、backward、forward+backward，避免 geomean 掩盖退化。
- [ ] 检查 D128 register pressure、occupancy 和 fusion 收益是否按机制预期缩小。
- [ ] 更新 PR 数据和机制解释，直接回应 maintainer review。

**完成标准**

- D128 与 H100 数据完整、可复现；
- combined 结果通过 N>=10、correctness 和 memory bar；
- 结论按 shape/hardware 如实限定；
- 上游完成实质 review。进入 `externally-verified` 需要 merge 或独立外部复现。

---

## ARGUS-IR-03 — 在 B200/H100 上做 MiniMax Speedrun

**目标**

建立一个固定、公开、可重复的 MiniMax speedrun 赛道，让 Argus 在 B200 和 H100 上持续
优化并冲击榜单，而不是只做一次内部演示。

**先固定**

- 使用哪个 MiniMax 模型/checkpoint、任务和输出质量要求。
- 输入尺寸、输出长度、batch/concurrency、精度、warmup、计时边界和硬件功耗模式。
- 榜单规则、允许/禁止的优化，以及提交所需日志。
- B200 与 H100 分开排名，不把不同平台数字混成一个结论。

**待做**

- [ ] 选定并归档公开计分脚本和 baseline commit。
- [ ] 在 B200/H100 各跑一份可复现 baseline，记录吞吐、首 token/首帧、端到端延迟和显存。
- [ ] 建立 Argus 自动实验账本：每次只写清假设、改动、结果、噪声和保留/回退决定。
- [ ] 分层优化 model graph、attention、GEMM、quantization、cache、kernel 和调度。
- [ ] 对进入冠军栈的改动做单项与组合复测，防止把噪声当收益。
- [ ] 完成榜单提交或由独立机器按相同脚本复现。

**完成标准**

- 有公开或可审计的排名，而不只是“跑得更快”；
- 相比冻结 baseline 的提升在重复运行中成立；
- 输出质量符合赛道要求；
- 所有冠军改动可从干净环境重建。

---

## ARGUS-IR-04 — Fast MiniMax-H3：从数据中心走到桌面

**外部参考，不是 Argus 当前成果**

参考谢恩泽的 Fast MiniMax 工作：在 Sol-Engine 完成 B200 Day-1 支持后，H3 被部署并加速到
DGX Spark 和 RTX 5090：

- **DGX Spark：** 480p、5 秒、24 FPS，端到端 **3.92x**；
- **RTX 5090：** 720p、5 秒、24 FPS，端到端 **4.52x**；
- 使用 kernel optimization、Sol-Attn / sparse attention、cross-step caching；
- 直接使用原始 **33B checkpoint**，不做蒸馏、微调或 LoRA。

这些数字只能作为待复现的参考线，不能直接列为 Argus result。

**Argus 目标**

在同等输入、checkpoint、质量和计时口径下，独立复现或超过参考结果，并给出一套普通用户
可以部署的 Fast MiniMax-H3 路径。

**待做**

- [ ] 拿到或重建可审计 baseline，确认参考数字的计时边界和质量口径。
- [ ] 固定原始 33B checkpoint，禁止用蒸馏、微调或 LoRA 偷换任务。
- [ ] 分别在 DGX Spark、RTX 5090 上建立未优化 baseline。
- [ ] 逐项实现并消融 kernel optimization、Sol-Attn/sparse attention、cross-step caching。
- [ ] 记录端到端 latency、FPS、显存、峰值功耗、启动/编译时间和输出质量。
- [ ] 做可重复安装、模型准备和一键 demo；不能依赖开发机上的隐式缓存。
- [ ] 与参考结果按同一规格比较，低分辨率/短视频不能冒充更高规格胜出。

**完成标准**

- 至少一个桌面平台在同规格下达到或超过参考 speedup；
- 原始 33B checkpoint 的输出质量没有未解释损失；
- 干净机器可按文档完成部署和复现；
- 技术收益有消融，能说明 kernel、attention 和 cache 各自贡献。

---

## ARGUS-IR-05 — 用 Argus 做 W2A4 GEMM 算子

**目标**

让 Argus 设计、实现并优化一个可用于真实模型的 W2A4 GEMM，而不是只在理想 shape 上跑通
一个玩具 kernel。优先服务 MiniMax-H3 / Fast MiniMax 路线，同时保留独立 benchmark。

**待做**

- [ ] 固定 W2A4 数据布局、group size、scale/zero-point 语义、accumulation precision 和误差范围。
- [ ] 从目标模型收集真实 M/N/K、batch 和并发分布，建立代表性 shape suite。
- [ ] 选定强 baseline（现有框架/CUTLASS/Triton 实现，按实际可用项冻结版本）。
- [ ] 实现 reference path 和逐元素/矩阵级 correctness 测试。
- [ ] 尝试 dequant+GEMM fusion、packing、tile、pipeline、Tensor Core 和 epilogue 优化。
- [ ] 在 B200、H100、RTX 5090 的适用平台分别测 kernel latency、吞吐、显存和端到端收益。
- [ ] 把 packing/dequant、编译和数据搬运成本计入，不能只报理想 steady-state kernel 时间。
- [ ] 集成到至少一个真实模型路径并验证输出质量。
- [ ] 提交可复现源码、benchmark、结果表和上游/集成 PR。

**完成标准**

- 多个真实 shape 上稳定超过强 baseline；
- correctness 和模型质量过关；
- 集成后有端到端收益，而不是 kernel 单点数字；
- 另一台同类硬件能复现。

---

## ARGUS-IR-06 — Erdős 猜想：证明或反例

**目标**

从 [Unsolved Math](https://www.unsolvedmath.com/) 和原始文献中选择一个明确的 Erdős
问题，让 Argus 进行长程证明搜索。成功结果可以是完整证明，也可以是一个真正推翻命题的
可核验反例。

**先做问题锁定**

- [ ] 选择一个具体命题，记录准确表述、量词、参数范围、已知部分结果和原始引用。
- [ ] 让数学专家确认 statement 没有抄错；网站只是索引，原始论文/权威资料才是依据。
- [ ] 在开始大规模搜索前冻结 statement version，避免发现困难后悄悄换题。

**证明/反例路线**

- [ ] 建立已知结果、等价形式、关键障碍和可计算小规模实例的资料包。
- [ ] 并行维护 proof 路线和 counterexample 路线；每次失败都记录排除了什么。
- [ ] 计算搜索使用精确算术、可重放代码和完整范围，不把浮点迹象当证明。
- [ ] 找到反例时给出最小对象、独立 verifier 和第二套实现复核。
- [ ] 找到证明时逐 lemma 检查依赖、边界情况和量词，不接受只有思路的 proof sketch。
- [ ] 适合形式化的部分进入 Lean/Isabelle/Coq 或等价 proof tooling；不适合形式化的部分交给
      至少两位独立数学审阅者。
- [ ] 与最新文献核对新颖性，确认不是已知结果或错误命题版本。

**完成标准**

满足以下任一项：

1. 完整证明通过独立专家审阅，并形成可公开手稿；或
2. 具体反例由两套独立程序/证明复现，且命题范围与原始 statement 完全一致。

有限范围验证、数值证据、搜索未发现反例、或者“模型认为证明成立”，都不能进入正式结果清单。

---

## 推荐执行顺序

1. **先收口 FLA KDA：** 已有代码和上游反馈，最快形成 externally-verified result。
2. **并行开 Sol-Attn 与 W2A4：** 两条 kernel 路线都能为 Fast MiniMax 提供组件。
3. **做 Fast MiniMax-H3 桌面复现：** 先对齐参考规格，再组合经过认证的优化。
4. **建立 MiniMax Speedrun：** benchmark 冻结后持续刷榜，避免边做边改规则。
5. **Erdős 长程路线独立运行：** 先锁 statement 和验证工具，不占用 GPU 工程主线。

## 每个正式结果的记录模板

进入正式 impressive result list 时，至少写清：

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

正式展示页只放通过标准的结果；失败路线、负面结果和被否决的 claim 留在各 campaign 的证据目录里。
