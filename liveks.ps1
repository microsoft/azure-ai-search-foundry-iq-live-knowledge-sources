$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $Root ".liveks\venv\Scripts\python.exe"
$CommandName = if ($args.Count -gt 0) { $args[0] } else { "help" }
$Remaining = if ($args.Count -gt 1) { $args[1..($args.Count - 1)] } else { @() }

function Find-LiveKsPython {
    foreach ($candidate in @("python3", "python")) {
        if (Get-Command $candidate -ErrorAction SilentlyContinue) {
            & $candidate -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" 2>$null
            if ($LASTEXITCODE -eq 0) { return @($candidate) }
        }
    }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($version in @("3.14", "3.13", "3.12", "3.11")) {
            & py "-$version" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" 2>$null
            if ($LASTEXITCODE -eq 0) { return @("py", "-$version") }
        }
    }
    throw "Python 3.11 or newer is required."
}

function Invoke-LiveKsPython {
    param([string[]]$Python, [string[]]$Arguments)
    if ($Python.Count -gt 1) {
        & $Python[0] $Python[1] @Arguments
    } else {
        & $Python[0] @Arguments
    }
}

if ($CommandName -eq "try" -and -not (Test-Path $VenvPython)) {
    $Python = Find-LiveKsPython
    $InvokeArgs = @((Join-Path $Root "tools\try_offline.py")) + @($Remaining)
    Invoke-LiveKsPython $Python $InvokeArgs
    exit $LASTEXITCODE
}

if ($CommandName -eq "bootstrap") {
    $Python = Find-LiveKsPython
    New-Item -ItemType Directory -Force (Join-Path $Root ".liveks") | Out-Null
    Invoke-LiveKsPython $Python @("-m", "venv", (Join-Path $Root ".liveks\venv"))
    & $VenvPython -m pip install --disable-pip-version-check --no-input -r (Join-Path $Root "requirements-liveks.txt") @Remaining
    Write-Host "LiveKS CLI environment ready: $(Split-Path -Parent $VenvPython)"
    exit 0
}

if (-not (Test-Path $VenvPython)) {
    Write-Error "LiveKS CLI dependencies are not installed. Run: .\liveks.ps1 bootstrap"
    exit 3
}

$env:PYTHONPATH = "$(Join-Path $Root 'src');$env:PYTHONPATH"
& $VenvPython -m liveks.cli @args
exit $LASTEXITCODE
