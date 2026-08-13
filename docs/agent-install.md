# Argus installation instructions for coding agents

You are responsible for completing the installation, not merely describing
commands. Keep changes scoped to Argus and follow these rules:

- Argus does not require a separate Argus account. The selected backend must
  be installed and authenticated through its official login flow.
- Inspect before changing the machine.
- Prefer the Agent CLI that is already running and authenticated.
- Ask before using `sudo`, installing system packages, changing shell startup
  files, or changing global Git or backend configuration.
- Never request secrets in chat, print secrets, or write credentials into the
  Argus repository. Use the backend's official interactive login flow.
- Do not overwrite an existing Argus checkout or discard local modifications.
- Stop and explain the exact blocker if a required action cannot be completed.

### 1. Inspect the environment

Determine the operating system and check:

```bash
git --version
python3 --version
node --version
```

Requirements:

- Python 3.11 or newer
- Node.js 22 or newer
- Git
- One supported Agent CLI

Do not assume `python3` satisfies the requirement, especially on macOS where
`/usr/bin/python3` may be 3.9. Validate it before creating a venv:

```bash
python3 -c 'import sys; assert sys.version_info >= (3, 11), sys.version'
```

If it fails and the user approves installing a user-scoped prerequisite, prefer
uv's official installation path, then run `uv python install 3.12` and
`uv venv --python 3.12 --seed .venv`. Keep using `.venv/bin/python` explicitly
for the remaining install and verification commands.

Check which supported backends are available:

```bash
command -v copilot || true
command -v codex || true
command -v claude || true
command -v pi || true
command -v opencode || true
command -v grok || true
```

Select the CLI hosting the current conversation when possible. Otherwise,
prefer an already installed and authenticated backend. Supported Argus backend
values are:

| Agent CLI | Argus backend |
|---|---|
| GitHub Copilot CLI | `copilot` |
| OpenAI Codex CLI | `codex` |
| Claude Code | `claude` |
| Pi | `pi` |
| OpenCode | `opencode` |
| xAI Grok Build | `grok` |

If prerequisites are missing, explain the proposed installation command and
obtain approval before using a system package manager, `sudo`, or making a
global installation. Follow the prerequisite project's official installation
instructions rather than inventing an unofficial download source.

### 2. Confirm backend authentication

Use a read-only status or version check first. If the selected CLI is not
authenticated, start its official interactive login flow and let the user
complete browser/device authorization directly. Do not ask the user to send
credentials through chat.

If the current Agent CLI is clearly working through its normal authenticated
session, do not force an unnecessary re-login.

### 3. Install Argus

Choose a persistent installation directory with the user. If they have no
preference, use `$HOME/Argus`.

For a new installation:

macOS / Linux:

```bash
git clone https://github.com/lbx154/Argus.git "$HOME/Argus"
cd "$HOME/Argus"
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
```

Windows PowerShell (portable preview):

```powershell
git clone https://github.com/lbx154/Argus.git "$HOME\Argus"
Set-Location "$HOME\Argus"
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
```

Windows installation, Manager chat, pairing, and the terminal-scoped daemon are
covered by the portable surface. POSIX-only subagent detachment and file-locking
paths are not yet full-parity features; do not claim full Windows support when a
requested workflow depends on them.

For an authorized private-preview installation, use
`https://github.com/lbx154/argus-skill.git` and a matching directory instead.
Do not silently substitute one repository for the other.

If `$HOME/Argus` already exists:

1. Verify that it is the Argus repository.
2. Inspect `git status`.
3. Never remove or overwrite local changes.
4. If it is clean, update it with `git pull --ff-only`.
5. Re-run `.venv/bin/python -m pip install -e .`.

On Windows, keep using `.\.venv\Scripts\python.exe` explicitly; activation is
optional and the POSIX `.venv/bin/...` commands do not apply.

### 4. Configure the selected backend

From the Argus checkout, run:

```bash
.venv/bin/argus --setup --non-interactive \
  --backend <copilot|codex|claude|pi|opencode|grok>
```

Windows PowerShell:

```powershell
.\.venv\Scripts\argus.exe --setup --non-interactive `
  --backend <copilot|codex|claude|pi|opencode>
```

For an OpenAI-compatible endpoint, no backend flag is needed. Setup installs Pi
when it is missing:

```bash
ARGUS_SETUP_API_KEY=... .venv/bin/argus --setup --non-interactive \
  --api-url https://api.example.com/v1 --api-model model-id
```

```powershell
$env:ARGUS_SETUP_API_KEY = "..."
.\.venv\Scripts\argus.exe --setup --non-interactive `
  --api-url https://api.example.com/v1 --api-model model-id
```

Use the backend selected in steps 1-2. Do not silently switch to another
provider after a failed readiness check. Diagnose the reported failure first,
then either fix it or ask the user to choose another installed backend.

### 5. Verify the installation

Run:

```bash
.venv/bin/argus --doctor
.venv/bin/argus --status
```

Windows PowerShell:

```powershell
.\.venv\Scripts\argus.exe --doctor
.\.venv\Scripts\argus.exe --status
```

The task is complete only when `argus --doctor` reports that the installation
and selected backend are ready. Do not claim success based only on a successful
package installation.

If the user wants `argus` available outside the checkout, offer a safe PATH or
launcher option appropriate for their operating system. Do not edit shell
startup files without approval.

### 6. Report the result

Tell the user:

- the Argus installation directory;
- the selected backend;
- whether `argus --doctor` passed;
- the exact command to start Argus;
- any remaining manual action.

Typical launch commands:

```bash
cd "$HOME/Argus"
.venv/bin/argus
```

Web UI:

```bash
cd "$HOME/Argus"
.venv/bin/argus --web
```

Windows PowerShell uses `.\.venv\Scripts\argus.exe --web`.
