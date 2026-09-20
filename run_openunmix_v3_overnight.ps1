param(
    [string]$PythonPath,
    [double]$TargetEpoch = 5.0,
    [double]$PerTargetWallHours = 3.0,
    [int]$BatchSize = 16,
    [int]$Workers = 2,
    [switch]$DryRun,
    [ValidateSet("", "vocals", "drums", "bass", "other")]
    [string]$SimulateFailureTarget = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = $PSScriptRoot
$python = $null
$trainer = Join-Path $projectRoot "scripts\openunmix_v2\train_target_v3.py"
$orchestrator = Join-Path $projectRoot "scripts\openunmix_v2\v3_orchestration.py"
$v3Root = Join-Path $projectRoot "outputs\training\openunmix_v3"

if ($PythonPath) {
    $python = $PythonPath
} elseif ($env:CONDA_DEFAULT_ENV -eq "elec5305") {
    $activePython = Get-Command python -ErrorAction SilentlyContinue
    if ($null -ne $activePython) { $python = $activePython.Source }
} elseif ($env:CONDA_PREFIX -and (Split-Path -Leaf $env:CONDA_PREFIX) -eq "elec5305") {
    $candidate = Join-Path $env:CONDA_PREFIX "python.exe"
    if (Test-Path -LiteralPath $candidate) { $python = $candidate }
}
if (-not $python) {
    $fallbackPython = "D:\anaconda\envs\elec5305\python.exe"
    if (Test-Path -LiteralPath $fallbackPython) { $python = $fallbackPython }
}
if (-not $python -or -not (Test-Path -LiteralPath $python)) {
    throw "elec5305 Python not found. Activate it or pass -PythonPath."
}
if (-not (Test-Path -LiteralPath $trainer) -or -not (Test-Path -LiteralPath $orchestrator)) {
    throw "V3 trainer/orchestrator is missing."
}
if ($TargetEpoch -le 0 -or $TargetEpoch -gt 5.0) {
    throw "TargetEpoch must be in (0, 5]."
}
if ($PerTargetWallHours -le 0) {
    throw "PerTargetWallHours must be positive."
}

New-Item -ItemType Directory -Force -Path $v3Root | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$totalLog = Join-Path $v3Root "overnight_$timestamp.log"
$queueStarted = Get-Date

function Write-QueueLog([string]$Message) {
    $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Write-Host $line
    Add-Content -LiteralPath $totalLog -Value $line -Encoding utf8
}

function Get-TargetStatus([string]$Target) {
    $statusJson = & $python $orchestrator status --root $v3Root --target $Target --target-epoch $TargetEpoch
    if ($LASTEXITCODE -ne 0) { throw "Could not inspect $Target checkpoint." }
    return ($statusJson | ConvertFrom-Json)
}

Write-QueueLog "QUEUE START target_epoch=$TargetEpoch per_target_wall_hours=$PerTargetWallHours dry_run=$DryRun"
$targets = @("vocals", "drums", "bass", "other")

foreach ($target in $targets) {
    try {
        $status = Get-TargetStatus $target
        if ($status.action -eq "skip") {
            Write-QueueLog (
                "SKIP $target epoch={0} already_complete=true best_validation={1}@{2} best_si_sdr={3}@{4}" -f
                $status.epoch_equivalent,
                $status.best_validation_loss,
                $status.best_validation_epoch,
                $status.best_si_sdr_db,
                $status.best_si_sdr_epoch
            )
            continue
        }

        $targetStarted = Get-Date
        Write-QueueLog "START $target action=$($status.action) epoch=$($status.epoch_equivalent)"
        if ($SimulateFailureTarget -eq $target) {
            Write-QueueLog "FAILED $target simulated=true elapsed=$((Get-Date) - $targetStarted) exit_code=97"
            exit 97
        }
        if ($DryRun) {
            Write-QueueLog "DRYRUN $target action=$($status.action)"
            continue
        }

        $targetDir = Join-Path $v3Root $target
        New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
        $targetLog = Join-Path $targetDir "console_$timestamp.log"
        $trainArgs = @(
            "-u", $trainer,
            "--target", $target,
            "--output-dir", $targetDir,
            "--batch-size", $BatchSize,
            "--workers", $Workers,
            "--max-epoch-equivalents", $TargetEpoch,
            "--max-wall-hours", $PerTargetWallHours
        )
        if ($status.action -eq "resume") {
            $trainArgs += @("--resume", $status.latest_checkpoint)
        }

        & $python @trainArgs 2>&1 |
            Tee-Object -FilePath $targetLog -Append |
            Tee-Object -FilePath $totalLog -Append
        $targetExitCode = $LASTEXITCODE
        if ($targetExitCode -ne 0) {
            Write-QueueLog "FAILED $target elapsed=$((Get-Date) - $targetStarted) exit_code=$targetExitCode"
            exit $targetExitCode
        }

        $after = Get-TargetStatus $target
        if ($after.action -ne "skip") {
            Write-QueueLog "FAILED $target elapsed=$((Get-Date) - $targetStarted) exit_code=3 reason=target_epoch_not_reached epoch=$($after.epoch_equivalent)"
            exit 3
        }
        $summary = Get-Content -Raw (Join-Path $targetDir "summary.json") | ConvertFrom-Json
        Write-QueueLog (
            "COMPLETE $target epoch={0} elapsed={1} best_validation={2}@{3} best_si_sdr={4}@{5} exit_code=0" -f
            $after.epoch_equivalent,
            ((Get-Date) - $targetStarted),
            $summary.best_validation_loss,
            $summary.best_validation_epoch,
            $summary.best_si_sdr_db,
            $summary.best_si_sdr_epoch
        )
    } catch {
        Write-QueueLog "FAILED $target exit_code=1 error=$($_.Exception.Message)"
        exit 1
    }
}

if ($DryRun) {
    Write-QueueLog "QUEUE DRYRUN COMPLETE elapsed=$((Get-Date) - $queueStarted)"
    exit 0
}

$summaryJson = & $python $orchestrator summary --root $v3Root --target-epoch $TargetEpoch
if ($LASTEXITCODE -ne 0) {
    Write-QueueLog "QUEUE FAILED exit_code=4 reason=four_stem_summary"
    exit 4
}
Write-QueueLog "QUEUE COMPLETE elapsed=$((Get-Date) - $queueStarted) exit_code=0"
Write-Host $summaryJson
exit 0
