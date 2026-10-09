param([int]$MorningHour=8,[int]$EveningHour=20)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { throw '找不到 python.exe，請先確認 Python 已安裝並加入 PATH' }
$batch = Join-Path $root 'RUN_MONITOR.bat'
$task = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument ('/c "' + $batch + '"') -WorkingDirectory $root
$triggers = @( (New-ScheduledTaskTrigger -Daily -At ("{0:D2}:00" -f $MorningHour)), (New-ScheduledTaskTrigger -Daily -At ("{0:D2}:00" -f $EveningHour)) )
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew
# Default interactive user's task: runs when logged in, including a locked screen.
Register-ScheduledTask -TaskName 'FlightLeaveOptimizer_PriceMonitor' -Action $task -Trigger $triggers -Settings $settings -Description 'Flight Leave Optimizer twice daily price monitoring' -Force | Out-Null
Write-Host '已建立每日兩次排程：' $MorningHour ':00 與 ' $EveningHour ':00'
Write-Host '注意：此排程預設使用目前登入帳號；未登入時不保證執行。請在工作排程器中另設「不論使用者是否登入都執行」並提供 Windows 憑證。'
