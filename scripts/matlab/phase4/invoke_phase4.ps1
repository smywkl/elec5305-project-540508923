param(
    [ValidateSet('music','probe','regression','science-test','test','play','ui-test','four-test','four-play','four-ui-test','music-test','studio-test','motion-test','motion-ui-test','progress-test','export-test','export-ui-test','export-audition')][string]$Mode = 'music',
    [int]$FrameSize = 1024,
    [string]$Driver = 'WASAPI',
    [string]$Device = '',
    [string]$RunName = '',
    [string]$TestInputDir = '',
    [switch]$ShowUI,
    [string]$MatlabExecutable = $env:ELEC5305_MATLAB,
    [string]$PythonExecutable = $env:ELEC5305_PYTHON
)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
if (-not $MatlabExecutable) {
    $MatlabExecutable = (Get-Command matlab -ErrorAction Stop).Source
}
if (-not (Test-Path -LiteralPath $MatlabExecutable -PathType Leaf)) {
    throw 'MATLAB not found. Use -MatlabExecutable or ELEC5305_MATLAB.'
}
if ($TestInputDir) { $TestInputDir = (Resolve-Path -LiteralPath $TestInputDir).Path }
if (-not $RunName) { $RunName = (Get-Date -Format 'yyyyMMdd_HHmmss_fff') + '_' + $Mode }
if ($RunName -notmatch '^[a-zA-Z0-9_-]+$') { throw 'RunName must be a simple directory name.' }
$runPath = Join-Path $repoRoot "outputs/phase4/$RunName"
if (Test-Path -LiteralPath $runPath) { throw "Refusing to overwrite $runPath" }
$prefsPath = Join-Path $runPath 'runtime/prefs'
New-Item -ItemType Directory -Path $prefsPath -Force | Out-Null
$sourceDirectories = @($PSScriptRoot, (Join-Path $repoRoot 'src/matlab/phase4'), (Join-Path $repoRoot 'scripts/python/phase4'), (Join-Path $repoRoot 'tests/matlab/phase4'), (Join-Path $repoRoot 'src/matlab/phase2'))
$sourceHashes = Get-ChildItem -LiteralPath $sourceDirectories -File -Recurse | Where-Object { $_.Extension -in @('.m','.py','.ps1') } | Sort-Object FullName | ForEach-Object {
    [pscustomobject]@{ file = $_.FullName.Substring($repoRoot.Length + 1); sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash }
}
$sourceHashes | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runPath 'source_hashes.json') -Encoding utf8
function Quote-Matlab([string]$Value) { return "'" + $Value.Replace("'", "''") + "'" }
$setup = 'addpath(' + (Quote-Matlab $PSScriptRoot) + ',' + (Quote-Matlab (Join-Path $repoRoot 'src/matlab/phase4')) + ',' + (Quote-Matlab (Join-Path $repoRoot 'tests/matlab/phase4')) + ');'
$outArg = Quote-Matlab $runPath
switch ($Mode) {
    'science-test' { $expression = $setup + 'addpath(' + (Quote-Matlab (Join-Path $repoRoot 'tests/matlab/phase2')) + ");phase2_regression($outArg)" }
    'regression' { $expression = $setup + "phase4_regression($outArg)" }
    'probe' { $expression = $setup + "phase4_probe($outArg)" }
    'test' { $expression = $setup + "phase4_validate($outArg)" }
    'four-test' { $expression = $setup + "phase4_four_validate($outArg)" }
    'motion-test' { $expression = $setup + "phase4_motion_validate($outArg)" }
    'progress-test' { $show = if ($ShowUI) { 'true' } else { 'false' }; $expression = $setup + "phase4_progress_validate($outArg,$show)" }
    'motion-ui-test' { $show = if ($ShowUI) { 'true' } else { 'false' }; $expression = $setup + "phase4_four_realtime('OutputDir',$outArg,'AutoTest',true,'MotionTest',true,'ShowUI',$show)" }
    'export-test' { $expression = $setup + "phase4_export_validate($outArg)" }
    'export-ui-test' { $show = if ($ShowUI) { 'true' } else { 'false' }; $expression = $setup + "phase4_four_realtime('OutputDir',$outArg,'AutoTest',true,'ExportTest',true,'ShowUI',$show)" }
    'export-audition' { $expression = $setup + "phase4_export_audition($outArg," + (Quote-Matlab $TestInputDir) + ')' }
    'studio-test' { $expression = $setup + "phase4_studio_validate($outArg)" }
    'music-test' { $expression = $setup + "phase4_music_validate($outArg," + (Quote-Matlab $TestInputDir) + ')' }
    'music' { $expression = $setup + "phase4_music('OutputDir',$outArg,'FrameSize',$FrameSize,'Driver'," + (Quote-Matlab $Driver) + ",'Device'," + (Quote-Matlab $Device) + ')' }
    'four-ui-test' { $show = if ($ShowUI) { 'true' } else { 'false' }; $expression = $setup + "phase4_four_realtime('OutputDir',$outArg,'FrameSize',$FrameSize,'Driver'," + (Quote-Matlab $Driver) + ",'Device'," + (Quote-Matlab $Device) + ",'AutoTest',true,'ShowUI',$show)" }
    'four-play' { $expression = $setup + "phase4_four_realtime('OutputDir',$outArg,'FrameSize',$FrameSize,'Driver'," + (Quote-Matlab $Driver) + ",'Device'," + (Quote-Matlab $Device) + ')' }
    'ui-test' { $expression = $setup + "phase4_realtime('OutputDir',$outArg,'FrameSize',$FrameSize,'Driver'," + (Quote-Matlab $Driver) + ",'Device'," + (Quote-Matlab $Device) + ",'AutoTest',true)" }
    'play' { $expression = $setup + "phase4_realtime('OutputDir',$outArg,'FrameSize',$FrameSize,'Driver'," + (Quote-Matlab $Driver) + ",'Device'," + (Quote-Matlab $Device) + ')'
    }
}
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $MatlabExecutable
$psi.WorkingDirectory = $repoRoot
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
$psi.EnvironmentVariables['MATLAB_PREFDIR'] = $prefsPath
if ($PythonExecutable) { $psi.EnvironmentVariables['ELEC5305_PYTHON'] = $PythonExecutable }
if ($Mode -in @('music','four-play','play')) {
    # -batch forbids blocking file dialogs, even when a uifigure is visible.
    $interactiveExpression = "try;" + $expression + ";catch ME;disp(getReport(ME,'extended'));exit(1);end;exit(0);"
    $psi.Arguments = '-wait -nodesktop -logfile "' + (Join-Path $runPath 'matlab.log') + '" -r "' + $interactiveExpression + '"'
} else {
    $psi.Arguments = '-logfile "' + (Join-Path $runPath 'matlab.log') + '" -batch "' + $expression + '"'
}
$process = [System.Diagnostics.Process]::Start($psi)
$process.WaitForExit()
Write-Output "PHASE4_RUN=$runPath EXIT=$($process.ExitCode)"
if ($process.ExitCode -ne 0) { exit $process.ExitCode }
exit 0
