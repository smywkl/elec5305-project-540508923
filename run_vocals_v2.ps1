param(
    [string]$PythonPath,
    [switch]$Resume,
    [double]$MaxWallHours = 6.0,
    [double]$MaxEpochEquivalents = 20.0,
    [int]$BatchSize = 16,
    [int]$Workers = 2,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = $PSScriptRoot
$python = $null
$trainer = Join-Path $projectRoot "scripts\openunmix_v2\train_vocals_v2.py"
$outputDir = Join-Path $projectRoot "outputs\training\openunmix_v2\vocals"
$latestCheckpoint = Join-Path $outputDir "latest_checkpoint.pt"

if ($PythonPath) {
    $python = $PythonPath
} elseif ($env:CONDA_DEFAULT_ENV -eq "elec5305") {
    $activePython = Get-Command python -ErrorAction SilentlyContinue
    if ($null -ne $activePython) {
        $python = $activePython.Source
    }
} elseif ($env:CONDA_PREFIX -and (Split-Path -Leaf $env:CONDA_PREFIX) -eq "elec5305") {
    $candidate = Join-Path $env:CONDA_PREFIX "python.exe"
    if (Test-Path -LiteralPath $candidate) {
        $python = $candidate
    }
}

if (-not $python) {
    $fallbackPython = "D:\anaconda\envs\elec5305\python.exe"
    if (Test-Path -LiteralPath $fallbackPython) {
        $python = $fallbackPython
    }
}

if (-not $python -or -not (Test-Path -LiteralPath $python)) {
    throw "elec5305 Python not found. Activate the environment or pass -PythonPath explicitly."
}
if (-not (Test-Path -LiteralPath $trainer)) {
    throw "V2 trainer not found: $trainer"
}
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$consoleLog = Join-Path $outputDir "console_$timestamp.log"
$trainArgs = @(
    "-u",
    $trainer,
    "--output-dir", $outputDir,
    "--batch-size", $BatchSize,
    "--workers", $Workers,
    "--max-epoch-equivalents", $MaxEpochEquivalents,
    "--max-wall-hours", $MaxWallHours
)

if ($Resume) {
    if (-not (Test-Path -LiteralPath $latestCheckpoint)) {
        throw "Cannot resume; checkpoint not found: $latestCheckpoint"
    }
    $trainArgs += @("--resume", $latestCheckpoint)
} elseif (Test-Path -LiteralPath $latestCheckpoint) {
    throw "V2 checkpoint already exists. Use -Resume to continue it instead of overwriting it."
}

$displayCommand = '& "{0}" {1}' -f $python, (($trainArgs | ForEach-Object { '"{0}"' -f $_ }) -join " ")
Write-Host "Open-Unmix V2 command:"
Write-Host $displayCommand
Write-Host "Console log: $consoleLog"

if ($DryRun) {
    Write-Host "DryRun: training was not started."
    exit 0
}

& $python @trainArgs 2>&1 | Tee-Object -FilePath $consoleLog
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    throw "V2 trainer exited with code $exitCode. See $consoleLog"
}
exit 0
