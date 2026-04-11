#Requires -Version 5.1
$ErrorActionPreference = "Stop"
$TaskName = "CafeDoorTicker"
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Write-Host "Removed task '$TaskName' (if it existed)."
