param([string]$Target = "$env:USERPROFILE\Documents\Claude\Flight-Leave-Optimizer")
$p = Join-Path $Target 'app.py'
$h = Join-Path $Target 'history_io.py'
if (!(Test-Path $p) -or !(Test-Path $h)) { throw 'Project files not found.' }
Write-Host "APP path: $p"
Write-Host "BACKUP path: $h"
Select-String -Path $p -Pattern 'v0.6.2-WINBACKUP-FIX','SQLite 完整備份' | Select-Object -First 5 | ForEach-Object { $_.Line.Trim() }
Select-String -Path $h -Pattern 'TemporaryDirectory','snapshot.serialize' | ForEach-Object { "history_io.py line $($_.LineNumber): $($_.Line.Trim())" }
