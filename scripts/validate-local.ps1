param(
    [switch]$Strict,
    [switch]$NoColor
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Bash = Get-Command bash -ErrorAction SilentlyContinue

if (-not $Bash) {
    Write-Error "Git Bash is required to run the canonical repository validation on Windows."
    exit 2
}

$Arguments = @("scripts/validate-local.sh")
if ($Strict) { $Arguments += "--strict" }
if ($NoColor) { $Arguments += "--no-color" }

Push-Location $Root
try {
    & $Bash.Source @Arguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
