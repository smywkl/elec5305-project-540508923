param(
    [ValidateSet('probe','test','play','ui-test','four-test','four-play','four-ui-test')][string]$Mode = 'probe',
    [int]$FrameSize = 1024,
    [string]$Driver = 'WASAPI',
    [string]$Device = '',
    [string]$RunName = '',
    [switch]$ShowUI
)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
if (-not $RunName) { $RunName = (Get-Date -Format 'yyyyMMdd_HHmmss_fff') + '_' + $Mode }
if ($RunName -notmatch '^[a-zA-Z0-9_-]+$') { throw 'RunName must be a simple directory name.' }
$runPath = Join-Path $repoRoot "outputs/phase4/$RunName"
if (Test-Path -LiteralPath $runPath) { throw "Refusing to overwrite $runPath" }
$prefsPath = Join-Path $runPath 'runtime/prefs'
New-Item -ItemType Directory -Path $prefsPath -Force | Out-Null
$sourceDirectories = @($PSScriptRoot, (Join-Path $repoRoot 'src/matlab/phase4')) | Where-Object { Test-Path -LiteralPath $_ }
$sourceHashes = Get-ChildItem -LiteralPath $sourceDirectories -File | Sort-Object FullName | ForEach-Object {
    [pscustomobject]@{ file = $_.FullName.Substring($repoRoot.Length + 1); sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash }
}
$sourceHashes | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runPath 'source_hashes.json') -Encoding utf8
function Quote-Matlab([string]$Value) { return "'" + $Value.Replace("'", "''") + "'" }
$setup = 'addpath(' + (Quote-Matlab $PSScriptRoot) + ');'
$outArg = Quote-Matlab $runPath
switch ($Mode) {
    'probe' { $expression = $setup + "phase4_probe($outArg)" }
    'test' { $expression = $setup + "phase4_validate($outArg)" }
    'four-test' { $expression = $setup + "phase4_four_validate($outArg)" }
    'four-ui-test' { $show = if ($ShowUI) { 'true' } else { 'false' }; $expression = $setup + "phase4_four_realtime('OutputDir',$outArg,'FrameSize',$FrameSize,'Driver'," + (Quote-Matlab $Driver) + ",'Device'," + (Quote-Matlab $Device) + ",'AutoTest',true,'ShowUI',$show)" }
    'four-play' { $expression = $setup + "phase4_four_realtime('OutputDir',$outArg,'FrameSize',$FrameSize,'Driver'," + (Quote-Matlab $Driver) + ",'Device'," + (Quote-Matlab $Device) + ')' }
    'ui-test' { $expression = $setup + "phase4_realtime('OutputDir',$outArg,'FrameSize',$FrameSize,'Driver'," + (Quote-Matlab $Driver) + ",'Device'," + (Quote-Matlab $Device) + ",'AutoTest',true)" }
    'play' { $expression = $setup + "phase4_realtime('OutputDir',$outArg,'FrameSize',$FrameSize,'Driver'," + (Quote-Matlab $Driver) + ",'Device'," + (Quote-Matlab $Device) + ')'
    }
}
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = 'D:\matlab2026a\bin\matlab.exe'
$psi.WorkingDirectory = $repoRoot
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
$psi.EnvironmentVariables['MATLAB_PREFDIR'] = $prefsPath
$psi.Arguments = '-logfile "' + (Join-Path $runPath 'matlab.log') + '" -batch "' + $expression + '"'
$process = [System.Diagnostics.Process]::Start($psi)
$process.WaitForExit()
Write-Output "PHASE4_RUN=$runPath EXIT=$($process.ExitCode)"
if ($process.ExitCode -ne 0) { exit $process.ExitCode }
exit 0
