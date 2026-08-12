param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$repo = Split-Path -Parent $root

if (-not $SkipInstall) {
    python -m pip install "pyinstaller>=6.11,<7"
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

python -m PyInstaller `
    --noconfirm `
    --clean `
    "$root\argus_backend.spec" `
    --distpath "$root\build" `
    --workpath "$root\build\.work"

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$backend = Join-Path $root "build\argus-backend\argus-backend.exe"
if (-not (Test-Path -LiteralPath $backend)) {
    Write-Error "PyInstaller did not produce $backend"
    exit 1
}

function Assert-BackendCommand {
    param(
        [string]$Label,
        [string[]]$CommandArgs
    )
    Write-Host "verifying $Label"
    & $backend @CommandArgs
    if ($LASTEXITCODE -ne 0) {
        $verifyExitCode = $LASTEXITCODE
        Write-Error "$Label failed with exit code $verifyExitCode"
        exit $verifyExitCode
    }
}

Assert-BackendCommand `
    -Label "frozen vertical/domain providers: $backend" `
    -CommandArgs @("--verify-frozen-runtime")
Assert-BackendCommand `
    -Label "frozen isolated internal module dispatch" `
    -CommandArgs @("-I", "-m", "argus_skill.tools.manager_live_view", "--help")
Assert-BackendCommand `
    -Label "frozen Python-compatible -c dispatch" `
    -CommandArgs @("-c", "import argus_skill; print(argus_skill.__version__)")

$scriptProbe = Join-Path $env:TEMP "argus-frozen-script-probe-$PID.py"
try {
    Set-Content `
        -LiteralPath $scriptProbe `
        -Value "import argus_skill; print('script-ok', argus_skill.__version__)" `
        -Encoding UTF8
    Assert-BackendCommand `
        -Label "frozen Python-compatible script dispatch" `
        -CommandArgs @($scriptProbe)
}
finally {
    Remove-Item -LiteralPath $scriptProbe -Force -ErrorAction SilentlyContinue
}

Write-Host "backend ready: $backend"
