param([string]$Target = "$env:USERPROFILE\Documents\Claude\Flight-Leave-Optimizer")
$ErrorActionPreference = 'Stop'
$source = $PSScriptRoot
$targetFull = [System.IO.Path]::GetFullPath($Target)
Write-Host "Source: $source"
Write-Host "Target: $targetFull"
if (-not (Test-Path (Join-Path $source 'app.py'))) { throw 'Source package missing app.py.' }
if (-not (Test-Path (Join-Path $targetFull 'app.py'))) { throw 'Target project missing app.py. Use -Target to specify its folder.' }
if ([System.IO.Path]::GetFullPath($source).TrimEnd('\') -eq $targetFull.TrimEnd('\')) { throw 'Source and target are the same folder; please extract the update separately.' }
Write-Host 'Please stop running Streamlit (Ctrl+C) and any automatic monitor before continuing.' -ForegroundColor Yellow
$answer = Read-Host 'Continue and overwrite Python source files? (Y/N)'
if ($answer -notmatch '^[Yy]$') { Write-Host 'Cancelled.'; exit 0 }
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$backupDir = Join-Path $targetFull "backup\source_before_v062_$stamp"
New-Item -Path $backupDir -ItemType Directory -Force | Out-Null
# Back up any existing app and modules before patching. Never touch data, .env, Git metadata.
$names = @('app.py','history_io.py','history.py','analytics.py','automation.py','core.py','forecast.py','ollama_analysis.py','providers.py','report.py','serpapi_provider.py','requirements.txt','START_WINDOWS.bat','INSTALL_SCHEDULE.ps1','REMOVE_SCHEDULE.ps1','RUN_MONITOR.bat')
foreach ($name in $names) {
    $dst = Join-Path $targetFull $name
    if (Test-Path $dst) { Copy-Item -LiteralPath $dst -Destination (Join-Path $backupDir $name) -Force }
}
foreach ($name in $names) {
    $src = Join-Path $source $name
    if (Test-Path $src) { Copy-Item -LiteralPath $src -Destination (Join-Path $targetFull $name) -Force }
}
# Clear only compiled Python cache to prevent stale imports.
$cache = Join-Path $targetFull '__pycache__'
if (Test-Path $cache) { Remove-Item -LiteralPath $cache -Recurse -Force -ErrorAction SilentlyContinue }
Write-Host "Updated. Previous source backed up: $backupDir" -ForegroundColor Green
Write-Host 'Confirm the main page says v0.6.2-WINBACKUP-FIX. Your data folder and API key are untouched.'
Write-Host "To start: cd `"$targetFull`"; python -m streamlit run app.py"
