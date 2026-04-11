#Requires -Version 5.1
# Run once: registers a daily task at 10:30 AM (hidden). Right-click -> Run with PowerShell, or:
#   powershell -ExecutionPolicy Bypass -File scripts\install_cafe_door_schedule.ps1
$ErrorActionPreference = "Stop"
$TaskName = "CafeDoorTicker"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$Vbs = Join-Path $ScriptDir "run_cafe_door_hidden.vbs"
if (-not (Test-Path -LiteralPath $Vbs)) {
    Write-Error "Missing: $Vbs"
    exit 1
}

$Action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "//B //Nologo `"$Vbs`"" -WorkingDirectory $RepoRoot
$Trigger = New-ScheduledTaskTrigger -Daily -At "10:30"
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

try {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
} catch {}

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Description "Daily 10:30: cafe_door.bat (generate ticker + push)" -Force | Out-Null
Write-Host "OK: Task '$TaskName' runs daily at 10:30 (background). Repo: $RepoRoot"
