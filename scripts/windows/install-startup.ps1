param([string]$DataDirectory = "$env:LOCALAPPDATA\FacultyRegister")
$ErrorActionPreference = 'Stop'
$projectPath = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
Set-Location -LiteralPath $projectPath
& (Join-Path $projectPath '.venv\Scripts\python.exe') -c 'import sys; from pathlib import Path; from operations.runtime import runtime_config; runtime_config(Path(sys.argv[1]))' $DataDirectory
if ($LASTEXITCODE -ne 0) { throw 'Complete setup before enabling startup.' }
$startScript = Join-Path $PSScriptRoot 'start.ps1'
$resolvedData = [System.IO.Path]::GetFullPath($DataDirectory)
$hasher = [System.Security.Cryptography.SHA256]::Create()
$suffix = ([BitConverter]::ToString($hasher.ComputeHash([Text.Encoding]::UTF8.GetBytes($resolvedData)))).Replace('-','').Substring(0,12)
$taskName = "FacultyRegister-$suffix"
$taskArgs = "-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File `"$startScript`" -DataDirectory `"$resolvedData`""
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $taskArgs -WorkingDirectory $projectPath
$userName = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $userName
$principal = New-ScheduledTaskPrincipal -UserId $userName -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Write-Host "Installed startup task: $taskName. Starts when this Windows account signs in."
