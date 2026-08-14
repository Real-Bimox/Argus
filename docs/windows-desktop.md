# Windows Desktop

Argus includes an Electron host for Windows x64. The desktop application does
not fork the Argus product or maintain a separate Web UI: it starts the same
Python runtime, serves the checked-in Web cockpit on loopback, and displays that
cockpit in a hardened Electron window.

The desktop package version follows the repository version. Prebuilt installers
and unpacked applications are build artifacts and are intentionally not stored
in Git.

## Scope

The Desktop integration adds:

- an Electron main process, preload bridge, launcher, and first-run settings UI;
- a PyInstaller build of the existing `argus_skill` runtime;
- strict ownership checks between Electron and its local Python backend;
- automatic recovery with a bounded restart circuit;
- supported Agent CLI discovery and explicit binary selection;
- redacted diagnostic export;
- NSIS installer and portable-package definitions.

It does **not** replace Manager, Planner, Engineer, Reviewer, WebAPI, Workbench,
or Vertical behavior. Those remain owned by the main Argus runtime. It also does
not expand the Windows portability claims of the underlying runtime; see the
main README for the currently supported Windows surface.

## End-user installation

Download `Argus-<version>-setup.exe` from the matching GitHub Release and run it.
The installer contains the frozen Argus backend; end users do not install
Python, Node.js, or a virtual environment for the Desktop application.

The first-run screen selects an installed Agent CLI and starts the bundled
backend. Installation is usable only after the backend reaches the ready screen.
If startup fails, use **Export sanitized diagnostics** from the error screen;
the report includes the failed stage and backend log without credentials.

`Argus-<version>-portable.exe` is the no-install alternative. The source
development instructions later in this document are for contributors building
the package, not for end users.

## Architecture

```text
Argus.exe (Electron)
  ├─ local launcher and settings renderer
  ├─ hardened BrowserWindow / WebContentsView
  └─ supervised resources/argus-backend/argus-backend.exe
       └─ existing Argus WebAPI + checked-in Web cockpit
```

In a packaged application, `argus-backend.exe` is a one-folder PyInstaller
bundle. Its entry point also implements the small Python invocation subset used
by Argus-owned tools:

- `argus-backend.exe -m argus_skill...`
- `argus-backend.exe -c "..."`
- `argus-backend.exe path/to/script.py ...`

Non-Argus `-m` modules are rejected. The build gate imports every registered
Vertical and Domain so a package cannot look healthy while dynamic providers
are missing.

## Runtime ownership and safety

The Electron supervisor starts the backend with a random Web token and writes a
per-user ownership record. A backend is accepted only when an authenticated
`/api/meta` response agrees with that record on all relevant fields:

- PID and process start identity;
- executable path;
- release-manifest source digest;
- loopback host and port;
- SHA-256 of the Web token.

The Desktop application never adopts, restarts, or terminates a process whose
ownership cannot be proven. It also:

- binds the managed service to `127.0.0.1` by default;
- uses Electron context isolation and renderer sandboxing;
- disables Node integration in renderers;
- denies renderer permission requests;
- sends non-local links to the system browser;
- redacts tokens, authorization headers, and credential-bearing URLs from logs
  and exported diagnostics;
- bounds automatic restart attempts and surfaces crash-loop failures.

## Requirements

For source development and packaging:

- Windows 10 or 11, x64;
- Python 3.11+;
- Node.js 22.12+;
- PowerShell;
- one supported Agent CLI installed and authenticated if agent work will run.

The first-run UI supports Codex CLI, Claude Code, GitHub Copilot CLI, Pi,
OpenCode, and Grok Build. Auto-detection is only a convenience; the operator can
select the executable explicitly.

## Contributor-only development setup

This section builds the frozen backend and installer and therefore uses an
isolated build environment. End users do not run these commands and do not
create a venv.

From the repository root in PowerShell:

```powershell
uv venv --python 3.12 --seed .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e . pytest ruff "pyinstaller>=6.11,<7"

npm --prefix frontend/web ci
npm --prefix desktop ci
```

`py -3.11 -m venv .venv` is also valid when the Python Launcher is installed.
The `uv` form above works on machines (including this tested setup) where
`py.exe` is absent. Always run Argus through this repository's `.venv`; a bare
global Python can appear to start the WebAPI from the source directory and then
fail to import `argus_skill` after an executor changes into the project
workdir.

For direct CLI use in a legacy CP936/GBK PowerShell, the launcher now switches
its streams to UTF-8. For older builds, set these two variables before launch:

```powershell
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
```

Run the Desktop host against the source runtime:

```powershell
$env:ARGUS_DESKTOP_DEV = "1"
$env:ARGUS_DESKTOP_REPO_ROOT = (Get-Location).Path
$env:ARGUS_SKILL_BIN = "$PWD\.venv\Scripts\python.exe"
npm --prefix desktop run dev
```

The development host reads the repository release manifest and starts
`python -m argus_skill --web` from the selected repository root.

Only one managed Argus API should own a host/port. Stop a manually started
`argus --web` on port 8799 before starting Desktop, otherwise Desktop will
correctly refuse to take over an unowned process. Also keep separate checkouts
in separate virtual environments: the public and private repositories share a
default state root and port but can carry different release identities.

### What exits when the terminal closes

`argus`, the local WebAPI on `127.0.0.1:8799`, and each session's background
executor are separate processes. The default interactive exit policy is
`detach`: Ctrl-D (or Ctrl-C twice in the live view) closes only the terminal UI,
so Web and an in-progress executor remain available. A later plain `argus` in
the same folder now detects that live session and reattaches instead of trying
to create a competing executor for the leased workspace.

Choose cleanup explicitly when that is what you want:

```powershell
argus --exit-policy stop-api  # stop only an API spawned and still owned by this invocation
argus --exit-policy stop-all  # gracefully stop the current executor, then that owned API
$env:ARGUS_TUI_EXIT_POLICY = "stop-all"  # optional persistent shell policy
```

`stop-api` is fail-closed: it checks the loopback endpoint, ownership record,
runtime PID/start identity, and both Windows launcher/listener PIDs before
signalling anything. It never stops a pre-existing, remote, unowned, or
PID-reused service. `stop-all` uses the daemon's graceful stop endpoint; it does
not recommend or issue `Stop-Process` against a raw PID. Workspace lease errors
name the safe session command, for example
`argus --daemon-stop --resume s-12345678`.

## Troubleshooting startup

- **Local backend startup timed out**: inspect the Desktop log and authenticated
  `/api/meta`. Older source builds confused the `.venv` launcher PID with the
  actual Python listener PID on Windows; current ownership records both.
- **Connecting to Argus** after the project list appears: the API handshake and
  project index already succeeded; the selected snapshot is still pending.
  Current builds bound that read and no longer let Manager prewarm hold it.
- **`snapshot refresh failed · fetch failed`**: this is a new REST request that
  could not reach or finish against the shared local WebAPI, not evidence that
  CLI and Web maintain separate state. Current TUI output includes the socket
  cause and retries bounded requests.
- **`background executor failed to start (rc=...)`**: inspect the diagnostic
  appended to the UI and the newest `daemons/boot-*.log`. Current builds retain
  helper stderr, validate the workdir/interpreter, and preserve the Windows
  child exit code instead of reducing every failure to a bare integer.

## Verification

Run the fast source checks:

```powershell
.\.venv\Scripts\python.exe -m ruff check desktop tests/desktop
.\.venv\Scripts\python.exe -m pytest -q tests/desktop/test_frozen_runtime.py
npm --prefix desktop run typecheck
npm --prefix desktop run test:identity
npm --prefix desktop run build
npm --prefix desktop audit
```

Build and verify the frozen backend:

```powershell
.\desktop\scripts\build-backend.ps1 -SkipInstall
```

The script verifies provider collection and the frozen `-m`, `-c`, and script
entry points before reporting success.

For an unsigned CI-style package-layout check:

```powershell
Set-Location desktop
npx electron-builder --win --dir --publish never -c.win.signAndEditExecutable=false
```

This validates the Electron application and bundled backend without changing or
signing Windows executable resources.

## Building distributable packages

Activate the intended Python environment, then run:

```powershell
npm --prefix desktop run dist
```

This command:

1. validates and builds the existing Web cockpit;
2. builds and verifies the frozen Python backend;
3. builds Electron main, preload, and launcher bundles;
4. produces NSIS and portable artifacts under `desktop/release/`.

`desktop/build/`, `desktop/out/`, and `desktop/release/` are reproducible local
outputs and are ignored by Git.

The repository does not contain signing credentials. Release owners should
provide the normal electron-builder signing configuration in the release
environment. On Windows machines where electron-builder cannot unpack its code
signing helper, enable Windows Developer Mode or run the release build in an
environment allowed to create symbolic links.

## Local data and diagnostics

Desktop settings, ownership metadata, and Desktop logs live under Electron's
per-user `userData` directory. Argus project state continues to use
`ARGUS_SKILL_HOME`, defaulting to the normal `~/.argus-skill` location.

The application menu and settings screen can:

- restart the owned backend;
- open logs and local data;
- select the Agent CLI and executable;
- change the loopback port and appearance;
- export a redacted diagnostic ZIP.

Diagnostic export is intended for troubleshooting, but operators should still
review any archive before sharing it.
