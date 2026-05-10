param(
  [string]$TaskName = "Liberty CTI RSS Collection Refresh",
  [string]$Time = "06:30"
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$scriptPath = Join-Path $root "update_rss_collection.ps1"

if (-not (Test-Path -LiteralPath $scriptPath)) {
  throw "Collector script not found: $scriptPath"
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""
$trigger = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 20)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description "Refresh Liberty CTI RSS candidate collection for the Production Center." -Force | Out-Null

Write-Host "Installed scheduled task: $TaskName"
Write-Host "Daily run time: $Time"
Write-Host "Collector: $scriptPath"
