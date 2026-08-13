<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/brand/svg/argus-logo-horizontal-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="docs/assets/brand/svg/argus-logo-horizontal.svg">
  <img src="docs/assets/brand/svg/argus-logo-horizontal.svg" width="420" alt="Argus">
</picture>

### 面向科研与工程的持久、可审查自主运行时

让长期 Agent 能够规划、执行、验证、暂停，并在一次模型调用之后继续推进。

**当前为 Preview v0.1.1 · 正式开源版正在路上。**

[![GitHub Stars](https://img.shields.io/github/stars/lbx154/Argus?style=flat-square)](https://github.com/lbx154/Argus/stargazers)
[![License](https://img.shields.io/github/license/lbx154/Argus?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![arXiv](https://img.shields.io/badge/arXiv-2608.05144-b31b1b?style=flat-square&logo=arxiv&logoColor=white)](https://arxiv.org/abs/2608.05144)

[官方网站](https://argusbot.cn) · [视频演示](https://www.youtube.com/watch?v=i8Qy9HCboQE) · [技术报告 · arXiv:2608.05144](https://arxiv.org/pdf/2608.05144) · [微信群](#微信群) · [English](README.md) / **简体中文**

`Manager` → `Planner` → `Engineer` ⇄ `Reviewer`

</div>

---

## Argus 是什么？

大多数 Agent 面向一次对话或一次编码回合设计。Argus 面向真正需要持续推进的工作：保存状态、分离执行与判断，并从已经验证的进展继续，而不是每次重新开始。

| 核心能力 | 含义 |
|---|---|
| **持久状态** | 任务、检查点、决策、Skill 与证据可跨 Session 和运行时升级保存。 |
| **独立审查** | 执行与验证相互分离；正常回合由 Reviewer 给出独立判断。 |
| **四角色运行时** | Manager、Planner、Engineer 和 Reviewer 分别拥有明确的权威与职责。 |
| **真实工具调用** | Agent 直接使用文件、终端、实验、API 和可检查的产物。 |
| **领域扩展** | Vertical 可以定义专属阶段、工具、证据要求与完成标准。 |
| **多种 Backend** | 支持 GitHub Copilot CLI、Pi、Codex CLI、Claude Code、OpenCode 与 Grok Build。 |

## 运行模型

| | 权威 | 职责 |
|---:|---|---|
| `01` | **Manager · 控制** | 理解 operator 意图、选择工作流，并独占阶段迁移权。 |
| `02` | **Planner · 方向** | 选择下一项高价值任务，并定义它必须产出的证据。 |
| `03` | **Engineer · 执行** | 实现代码、开展调研、运行实验，并生成可检查的产物。 |
| `04` | **Reviewer · 验证** | 独立检查正确性、证据、局限和完成状态。 |

项目可以停止、恢复、跨运行时替换，并从最近一次已验证位置继续推进。

**原生 Backend：** `GitHub Copilot CLI` · `Pi` · `OpenAI Codex CLI` · `Claude Code` · `OpenCode` · `Grok Build`

**Harbor 评测：** Harbor Framework 可以把完整的有界 Argus
Manager/Planner/Engineer/Reviewer 运行时作为自定义 Agent 直接调用。配置和边界见
**[Harbor 接入说明](docs/harbor.md)**。

## 快速安装

请只使用当前操作系统对应的一组命令，不要混用。

所有平台都需要：

- 已按官方方式安装的 Agent CLI；
- 该 CLI 已完成官方登录鉴权；
- Node.js 22+（终端 cockpit 需要）。

正式 PyPI 首发前，公共 Preview 直接从 GitHub archive 安装。

### Windows 10/11：直接 pip 安装，不创建虚拟环境

从 [python.org](https://www.python.org/downloads/windows/) 安装 Python 3.11+
并勾选 **Add Python to PATH**。重新打开 PowerShell 后执行：

```powershell
py -m pip install --upgrade pip
py -m pip install --upgrade "argus-skill @ https://github.com/lbx154/Argus/archive/refs/heads/main.zip"
$Scripts = py -c "import sysconfig; print(sysconfig.get_path('scripts'))"
$env:Path = "$Scripts;$env:Path"
argus --setup
argus doctor --deep --advisor auto
argus
```

`argus --setup` 不会只检查到 CLI 就宣称完成：它会检查 backend/鉴权，并实际执行
一次禁止工具调用的 Agent turn。上面的 `$Scripts` 命令会让当前 PowerShell 立即找到
`argus`；如果新窗口仍找不到，再确认 Python 安装器的 Scripts 目录已加入 PATH。

`argus doctor` 是主动修复命令：默认会在真实 Argus 目录中启动用户电脑上已安装的
Agent CLI，开放工具让 Agent 直接检查并修复机器，然后重新运行确定性检查验收。
只有需要“纯诊断、不启动 Agent 修复”时才使用 `argus doctor --advisor none`。

正式 PyPI 版本发布前，用下面的命令刷新持续更新的 GitHub Preview：

```powershell
py -m pip install --upgrade --force-reinstall "argus-skill @ https://github.com/lbx154/Argus/archive/refs/heads/main.zip"
```

Windows 当前支持安装、Manager 对话、配对、Web/TUI 和终端作用域 daemon 控制。
detached subagent 仍属于 POSIX/WSL2 能力；native Windows 会明确失败，不会伪报任务
已启动。图形安装见 **[Windows Desktop](docs/windows-desktop.md)**。

### macOS：uv tool 管理安装，不手工创建虚拟环境

安装 [uv](https://docs.astral.sh/uv/getting-started/installation/) 后执行：

```bash
uv tool install --python 3.12 \
  "argus-skill @ https://github.com/lbx154/Argus/archive/refs/heads/main.zip"
argus --setup
argus doctor --deep --advisor auto
argus
```

以后更新：

```bash
uv tool install --force --python 3.12 \
  "argus-skill @ https://github.com/lbx154/Argus/archive/refs/heads/main.zip"
```

### Linux：保留隔离源码 venv

Linux 服务器继续显式使用 venv，保证 Python、CUDA 工具链和长任务进程环境可复现：

```bash
git clone https://github.com/lbx154/Argus.git
cd Argus
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
.venv/bin/argus --setup
.venv/bin/argus doctor --deep --advisor auto
.venv/bin/argus
```

私有 Preview 协作者在 Linux clone 命令中改用
`https://github.com/lbx154/argus-skill.git`。Windows/macOS 应安装私有 wheel
或经过认证的私有 archive，不要把 GitHub token 写进 shell history。

### Agent 一键接入

把下面整段发送给已安装的 Code Agent：

```text
请阅读 https://github.com/lbx154/Argus/blob/main/docs/agent-install.md，
使用当前操作系统对应的方式安装 Argus。优先复用当前 Agent CLI 作为 backend。
Windows 和 macOS 不创建手工 venv；Linux 保留文档中的 venv。必须让 setup 完成真实
Agent turn 验收，再运行 argus doctor --deep --advisor auto。需要登录、sudo 或修改
全局配置时先说明原因并等待确认。不要要求我在对话中粘贴密码、token 或 API Key。
```

Agent 将遵循 **[安装执行规范](docs/agent-install.md)**。

### Backend 说明

`--backend` 可使用 `copilot`、`pi`、`codex`、`claude`、`opencode`、`grok`
或 `qoder`。
未显式配置 model 时，Argus 使用所选 CLI 的原生默认模型，不会把 OpenAI 模型 id
传给 Claude Code、Pi、OpenCode 或 Grok。
如果已有 OpenAI-compatible URL，setup 会在需要时自动安装 Pi 并完成配置：

```bash
ARGUS_SETUP_API_KEY=... argus --setup --non-interactive \
  --api-url https://api.example.com/v1 \
  --api-model model-id
```

使用 Grok Build 时，请先安装并登录 xAI 官方 CLI：

```bash
curl -fsSL https://x.ai/cli/install.sh | bash
grok login
argus --setup --non-interactive --backend grok
```

无界面环境也可以使用 `XAI_API_KEY`。Argus 通过 Grok 原生 headless JSON
流运行、按 Session ID 续接，并避免把角色 prompt 放进进程参数。
PowerShell 多行续行符为反引号，不是 `\`。

#### 为多 provider 的 CLI 指定 provider

Pi 与 OpenCode 是与 provider 无关的前端：具体走哪个账户，取决于你给它认证了什么
（原生 DeepSeek key、Anthropic、Azure、本地 vLLM、Copilot 代理）。Argus 会把你配置
的 model id 原样透传，因此 `deepseek-chat` 这样的裸 id 由 CLI 自己解析。

只有在裸 id 有歧义、或 CLI 本身要求限定时才需要指定 provider：

```bash
# Pi —— 仅当两个已认证目录里存在同名 model 时才需要
export ARGUS_SKILL_PI_PROVIDER=deepseek

# OpenCode —— 必需：`opencode run --model` 只接受 provider/id
export ARGUS_SKILL_OPENCODE_PROVIDER=deepseek
```

两者也可以在座舱 `/config` 里设置，在那里设置后会持久化、重启依然生效。

`argus --doctor` 会读取 CLI 的已认证目录：配置的 provider 你并没有 key，或选定的
model 不在目录中时，会直接告诉你。

完整说明（含对依赖旧的隐式 `github-copilot` 前缀的 Pi 部署的不兼容变更）：
**[后端 provider 说明](docs/backend-providers.md)**。

### 启动

```bash
argus
```

```bash
argus --doctor   # 检查安装与后端
argus --status   # 查看当前运行状态
```

## 交互界面

### Windows Desktop

Windows x64 源码包含一个 Electron 桌面宿主：它监管由同一套 Argus 运行时冻结得到的
本地后端，并直接打开现有 Web Cockpit；Manager、Workbench 与 WebAPI 不存在单独的
Desktop 分叉。源码运行、安全边界、验收和打包命令见
**[Windows Desktop 文档](docs/windows-desktop.md)**。

### Terminal Cockpit

```bash
argus
```

通过终端 Cockpit 与 Manager 对话、跟踪实时工作、检查状态并恢复项目。
未显式指定 `--port` 时，Argus 会复用兼容后端；若默认端口被其他程序或旧后端占用，
则从 `8799` 开始选择首个可用端口。在 Windows 上，普通 `argus` 启动会同时打开
Web UI；使用 `argus --no-open` 可只保留终端 Cockpit。

### Web UI

启动 Argus，并在默认浏览器中打开 Web UI：

```bash
argus --web
```

首选地址：[http://127.0.0.1:8799](http://127.0.0.1:8799)；被占用时会自动顺延。

```bash
argus --web --web-port 8800  # 使用其他端口
```

#### 通过 SSH 使用远程服务器

在服务器上：

```bash
argus --web
```

在自己的电脑上：

```bash
ssh -L 8799:127.0.0.1:8799 user@server
```

然后在本机打开 [http://127.0.0.1:8799](http://127.0.0.1:8799)。

<details>
<summary><strong>直接通过局域网访问</strong></summary>

非本机监听始终受 Bearer Token 保护：设置了 `ARGUS_SKILL_WEB_TOKEN` 就用它，没设置则为本次运行自动生成一个。

```bash
argus --web --web-host 0.0.0.0 --web-port 8799
```

命令会打印其他设备可达的地址、Token，以及一个二维码。想让 Token 在重启后保持不变，自己设置即可：

```bash
export ARGUS_SKILL_WEB_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
```

如果确实要在没有 Token 的情况下提供服务（仅在你自己有鉴权代理的前提下），设置 `ARGUS_SKILL_WEB_ALLOW_INSECURE=1`。

</details>

### 在手机上使用

Telegram、飞书 / Lark 和网页版都可以在手机上使用。两个聊天机器人都是**向外拨号**的长连接，所以位于 NAT 后面的守护进程不需要内网穿透，也不需要公网地址：

```bash
# 飞书 / Lark —— WebSocket 长连接，无需配置请求地址
pip install 'argus-skill[feishu]'
export ARGUS_SKILL_ENABLE_FEISHU=1
export ARGUS_SKILL_FEISHU_APP_ID=cli_xxx ARGUS_SKILL_FEISHU_APP_SECRET=xxx

# Telegram
export ARGUS_SKILL_ENABLE_TELEGRAM=1
export ARGUS_SKILL_TELEGRAM_BOT_TOKEN=... ARGUS_SKILL_TELEGRAM_CHAT_ID=...
```

两个机器人提供完全相同的命令（`/add`、`/status`、`/nudge`、`/backlog` 等）。网页版可以添加到手机主屏幕，扫描 `argus --web --web-host 0.0.0.0` 打印的二维码即可完成配对。

完整配置见 **[docs/mobile.md](docs/mobile.md)**。

## 高级使用

Argus 的设计目标不是“只能配置”，而是“可以被你改变”。

### 自主程度

默认 `pragmatic` 模式会自行处理超时、失败测试、benchmark 规模和技术路线等可恢复问题；只有凭证、预算增加、不可逆操作、对外发布或改变你定义的验收边界时才会询问。

```bash
# 谨慎：每个明确问题都询问
export ARGUS_SKILL_AUTONOMY_MODE=cautious

# 务实（默认）：技术问题自动恢复，权威边界询问
export ARGUS_SKILL_AUTONOMY_MODE=pragmatic

# 主动：最大化可逆技术执行，仍保留凭证/金钱/不可逆边界
export ARGUS_SKILL_AUTONOMY_MODE=autonomous
```

也可以从 Web 配置页或 `/config` 修改该选项。

### 改造整个运行时

如果你是 Agent 的狂热爱好者，我们推荐你在本地部署 Argus，让完整闭环真正适合自己的工作方式。你可以调整角色 Prompt、工作流边界、审查策略、工具与运行约定，对接已有基础设施，并用测试固定自己重视的行为。

### 创建自己的 Vertical

Vertical 可以为你的领域提供专属阶段、Skill、数据集、工具、证据要求、评测方法与完成标准。规划与审查将遵循该领域真正重要的规范，而不是一套通用流程。

### 让其他 Agent 成为外层入口

你可以通过 GitHub Copilot、Pi、Codex、Claude Code、OpenCode、Grok Build、OpenClaw 或 Hermes 调用 Argus、检查状态、操作本地 CLI 或 Web/API，并继续迭代自己的部署。

- **Argus 原生 Backend：** GitHub Copilot CLI、Pi、Codex CLI、Claude Code、OpenCode、Grok Build
- **外层 Agent：** OpenClaw、Hermes，或任何能够使用 Shell / HTTP API 的 Agent

如需运行持久任务，可安装或适配可移植的
[`argus-runtime-orchestration` Agent Skill](integrations/agent-skills/argus-runtime-orchestration/SKILL.md)。
该 Skill 明确定义了双方操作模型、主动检查 `Needs you` 的干预闭环、
各宿主适配器、证据边界与收尾检查。

常用入口：

```bash
argus doctor
argus --status
argus --web
```

最强大的 Argus 往往是一套被你认真改造成更适合自己伟大领域与工作方式的 Argus。

## 更新

Windows：

```powershell
pip install --upgrade "argus-skill @ https://github.com/lbx154/Argus/archive/refs/heads/main.zip"
```

macOS：

```bash
uv tool upgrade argus-skill
```

Linux 源码 checkout：

```bash
argus update
```

Linux 源码更新会拒绝 dirty/detached checkout，只做 fast-forward 并刷新 editable
安装。更新后 Argus 会识别过期的本地 WebAPI 与 daemon，并在受控任务边界完成替换。

## 微信群

扫码加入 Argus 交流群。二维码有效期以图片中的提示为准；如果已经过期，请在 Issue 中联系维护者更新。

<p align="center">
  <img src="docs/assets/argus-wechat-group.jpg" width="360" alt="Argus 微信交流群二维码">
</p>
