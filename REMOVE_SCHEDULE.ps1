Unregister-ScheduledTask -TaskName 'FlightLeaveOptimizer_PriceMonitor' -Confirm:$false -ErrorAction SilentlyContinue
Write-Host '已移除 FlightLeaveOptimizer_PriceMonitor 排程'
