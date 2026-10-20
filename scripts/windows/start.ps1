param([string]$DataDirectory = "$env:LOCALAPPDATA\FacultyRegister")
$ErrorActionPreference = 'Stop'
$projectPath = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
Set-Location -LiteralPath $projectPath
& (Join-Path $projectPath '.venv\Scripts\python.exe') -m operations.runtime --data-dir $DataDirectory
exit $LASTEXITCODE
